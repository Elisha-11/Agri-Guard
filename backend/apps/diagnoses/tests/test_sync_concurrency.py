"""Two sync requests carrying the same diagnosis at the same moment (docs/offline-sync.md, idempotency).

This is the race the IntegrityError branch in sync.py handles: both requests look up the client_id, find
nothing, and both try to insert it. Each test holds every request just before its first insert, so all of
them have already done that lookup, then lets them go together. A "duplicate" result can then only come from
the IntegrityError branch.

Only PostgreSQL shows the real behaviour (the second insert waits on the first one's unique-index entry, then
fails), so these tests skip on SQLite and run in CI. To run them locally, point DATABASE_URL at PostgreSQL
(docker compose up -d db).
"""

import threading

import pytest
from django.core.management import call_command
from django.db import connection, connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.tests.factories import FarmerFactory
from apps.diagnoses import sync
from apps.diagnoses.models import Diagnosis

from .test_sync_api import URL, item

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL; runs in CI"),
]


@pytest.fixture(autouse=True)
def _taxonomy(transactional_db):
    """The real disease classes, committed so the request threads can see them."""
    call_command("load_taxonomy", verbosity=0)


def signed_in(farmer):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(farmer).access_token}")
    return api


def send_together(monkeypatch, *requests):
    """POST each (api, items) from its own thread, all released at once just before their first insert.

    Returns each request's results, in the order given.
    """
    barrier = threading.Barrier(len(requests), timeout=10)
    held = threading.local()
    build_diagnosis = sync.build_diagnosis

    def build_after_the_others_arrive(*args, **kwargs):
        if not getattr(held, "done", False):
            held.done = True
            barrier.wait()
        return build_diagnosis(*args, **kwargs)

    monkeypatch.setattr(sync, "build_diagnosis", build_after_the_others_arrive)

    responses = [None] * len(requests)
    failures = []

    def send(index, api, items):
        try:
            responses[index] = api.post(URL, {"items": items}, format="json")
        except BaseException as exc:  # surfaced in the main thread below
            failures.append(exc)
            barrier.abort()
        finally:
            connections.close_all()

    threads = [threading.Thread(target=send, args=(i, api, items)) for i, (api, items) in enumerate(requests)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads), "a request hung (deadlock?)"
    assert not failures, failures

    for response in responses:
        assert response.status_code == 200, response.content
    return [response.json()["results"] for response in responses]


def test_same_diagnosis_from_two_requests_is_stored_once(monkeypatch):
    """The phone flushes its queue twice at once: two tabs, or a retry while the first request still runs."""
    farmer = FarmerFactory()
    payload = item()

    [a], [b] = send_together(monkeypatch, (signed_in(farmer), [payload]), (signed_in(farmer), [payload]))

    assert sorted([a["status"], b["status"]]) == ["created", "duplicate"]
    assert a["id"] == b["id"]
    assert Diagnosis.objects.filter(client_id=payload["client_id"]).count() == 1


def test_same_client_id_from_two_farmers_is_a_conflict_for_the_loser(monkeypatch):
    """A cloned phone: the second farmer gets "conflict" and never sees the first farmer's record."""
    first, second = FarmerFactory(), FarmerFactory()
    payload = item()

    [a], [b] = send_together(monkeypatch, (signed_in(first), [payload]), (signed_in(second), [payload]))

    winner, loser = (a, b) if a["status"] == "created" else (b, a)
    assert (winner["status"], loser["status"]) == ("created", "conflict")
    assert loser["id"] is None
    stored = Diagnosis.objects.get(client_id=payload["client_id"])
    assert stored.farmer == (first if winner is a else second)


def test_overlapping_batches_store_each_item_once(monkeypatch):
    farmer = FarmerFactory()
    batch = [item() for _ in range(10)]

    a, b = send_together(monkeypatch, (signed_in(farmer), batch), (signed_in(farmer), batch))

    for mine, theirs in zip(a, b, strict=True):
        assert sorted([mine["status"], theirs["status"]]) == ["created", "duplicate"]
        assert mine["id"] == theirs["id"]
    assert Diagnosis.objects.count() == 10


def test_batches_in_opposite_order_do_not_deadlock(monkeypatch):
    """Each insert commits on its own (no request-wide transaction), so two requests never wait on each other.

    If sync ever wraps the whole batch in one transaction, this test fails with a deadlock.
    """
    farmer = FarmerFactory()
    batch = [item() for _ in range(10)]

    a, b = send_together(monkeypatch, (signed_in(farmer), batch), (signed_in(farmer), batch[::-1]))

    statuses = {r["client_id"]: [r["status"]] for r in a}
    for r in b:
        statuses[r["client_id"]].append(r["status"])
    assert all(sorted(pair) == ["created", "duplicate"] for pair in statuses.values())
    assert Diagnosis.objects.count() == 10
