import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Disease

pytestmark = pytest.mark.django_db


def write_labels(tmp_path, classes, version="0.2"):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"taxonomy_version": version, "classes": classes}), encoding="utf-8")
    return str(path)


MAIZE = [
    {"index": 0, "id": "maize__healthy", "crop": "maize", "is_healthy": True},
    {"index": 1, "id": "maize__northern_leaf_blight", "crop": "maize", "is_healthy": False},
]


def test_loads_the_real_labels_file(taxonomy):
    assert len(taxonomy) == 19
    assert taxonomy["maize__healthy"].class_index == 0
    assert taxonomy["maize__healthy"].is_healthy
    assert sum(d.is_healthy for d in taxonomy.values()) == 5  # one healthy class per crop


def test_running_twice_changes_nothing(taxonomy):
    call_command("load_taxonomy", verbosity=0)
    assert Disease.objects.count() == 19


def test_retired_flag_is_loaded(tmp_path):
    call_command("load_taxonomy", write_labels(tmp_path, MAIZE), verbosity=0)
    retired = [MAIZE[0], {**MAIZE[1], "retired": True}]
    call_command("load_taxonomy", write_labels(tmp_path, retired), verbosity=0)
    assert Disease.objects.get(class_id="maize__northern_leaf_blight").is_retired


def test_refuses_to_move_a_class_to_another_index(tmp_path):
    call_command("load_taxonomy", write_labels(tmp_path, MAIZE), verbosity=0)
    swapped = [{**MAIZE[0], "index": 1}, {**MAIZE[1], "index": 0}]
    with pytest.raises(CommandError, match="Indices are fixed forever"):
        call_command("load_taxonomy", write_labels(tmp_path, swapped), verbosity=0)


def test_refuses_a_class_that_disappears(tmp_path):
    call_command("load_taxonomy", write_labels(tmp_path, MAIZE), verbosity=0)
    with pytest.raises(CommandError, match="Mark them retired"):
        call_command("load_taxonomy", write_labels(tmp_path, MAIZE[:1]), verbosity=0)


def test_refuses_a_new_class_on_a_taken_index(tmp_path):
    call_command("load_taxonomy", write_labels(tmp_path, MAIZE), verbosity=0)
    clash = [*MAIZE, {"index": 1, "id": "maize__common_rust", "crop": "maize", "is_healthy": False}]
    with pytest.raises(CommandError, match="share an index"):
        call_command("load_taxonomy", write_labels(tmp_path, clash), verbosity=0)


def test_refuses_a_class_id_that_does_not_match_its_crop(tmp_path):
    bad = [{"index": 0, "id": "maize__healthy", "crop": "cassava", "is_healthy": True}]
    with pytest.raises(Exception, match="cassava__"):
        call_command("load_taxonomy", write_labels(tmp_path, bad), verbosity=0)
    assert not Disease.objects.exists()  # all-or-nothing


def test_unreadable_file_gives_a_clear_error(tmp_path):
    with pytest.raises(CommandError, match="Can't read a taxonomy"):
        call_command("load_taxonomy", str(tmp_path / "nope.json"), verbosity=0)
