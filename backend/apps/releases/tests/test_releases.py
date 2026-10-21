"""Model releases: register_model's checks, the current-release switch, and GET /api/v1/model/latest/."""

import hashlib
import io
import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.core.tests.contract import assert_matches_contract
from apps.releases.models import ModelRelease

URL = "/api/v1/model/latest/"
BASE = "https://cdn.example.org/models/2026.11.0/"
REAL_LABELS = Path(settings.BASE_DIR).parent / "ml" / "labels.json"


@pytest.fixture
def model_dir(tmp_path, taxonomy):
    """A converted model folder as the ML pipeline produces it: model.json, two shards, labels.json."""
    folder = tmp_path / "2026.11.0"
    folder.mkdir()
    (folder / "group1-shard1of2.bin").write_bytes(b"\x00" * 1000)
    (folder / "group1-shard2of2.bin").write_bytes(b"\x00" * 500)
    model_json = {
        "modelTopology": {},
        "weightsManifest": [{"paths": ["group1-shard1of2.bin", "group1-shard2of2.bin"], "weights": []}],
    }
    (folder / "model.json").write_text(json.dumps(model_json), encoding="utf-8")
    labels = json.loads(REAL_LABELS.read_text(encoding="utf-8"))
    labels["model_version"] = "2026.11.0"
    (folder / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
    return folder


def register(folder, *extra, **kwargs):
    out = io.StringIO()
    call_command(
        "register_model",
        str(folder),
        "--base-url",
        BASE,
        "--min-app-version",
        "0.1.0",
        *extra,
        stdout=out,
        **kwargs,
    )
    return out.getvalue()


def edit_json(path, change):
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


# Ways a model folder can be broken (used by TestRegister).
def missing_shard(d):
    (d / "group1-shard2of2.bin").unlink()


def oversized_shard(d):
    (d / "group1-shard1of2.bin").write_bytes(b"\x00" * (4 * 1024 * 1024 + 1))


def missing_labels(d):
    (d / "labels.json").unlink()


def corrupt_model_json(d):
    (d / "model.json").write_text("{not json", encoding="utf-8")


def not_a_tfjs_model(d):
    (d / "model.json").write_text("{}", encoding="utf-8")


def labels_for_another_version(d):
    edit_json(d / "labels.json", lambda x: x.update(model_version="2026.12.0"))


def labels_for_another_taxonomy(d):
    edit_json(d / "labels.json", lambda x: x.update(taxonomy_version="0.2"))


def labels_missing_a_class(d):
    edit_json(d / "labels.json", lambda x: x["classes"].pop())


def labels_with_a_moved_class(d):
    edit_json(d / "labels.json", lambda x: x["classes"][0].update(index=99))


class TestRegister:
    def test_registers_and_writes_manifest(self, model_dir):
        output = register(model_dir)
        release = ModelRelease.objects.get()
        assert release.model_version == "2026.11.0"
        assert release.taxonomy_version == "0.1"
        assert release.model_url == BASE + "model.json"
        assert release.labels_url == BASE + "labels.json"
        assert release.size_bytes == (model_dir / "model.json").stat().st_size + 1500
        assert release.sha256 == hashlib.sha256((model_dir / "model.json").read_bytes()).hexdigest()
        assert not release.is_current
        manifest = json.loads((model_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest == release.manifest()
        assert_matches_contract(manifest, "ModelManifest")
        assert "Not current yet" in output

    def test_make_current_flag(self, model_dir):
        register(model_dir, "--make-current")
        assert ModelRelease.objects.get().is_current

    def test_custom_thresholds(self, model_dir):
        register(model_dir, "--confident", "0.8", "--uncertain", "0.5")
        assert ModelRelease.objects.get().manifest()["thresholds"] == {"confident": 0.8, "uncertain": 0.5}

    @pytest.mark.parametrize(
        "break_it, message",
        [
            (missing_shard, "isn't in the folder"),
            (oversized_shard, "at most 4.0 MB"),
            (missing_labels, "Missing labels.json"),
            (corrupt_model_json, "isn't valid JSON"),
            (not_a_tfjs_model, "no weightsManifest"),
            (labels_for_another_version, "end with /2026.12.0/"),
            (labels_for_another_taxonomy, "Load the new taxonomy"),
            (labels_missing_a_class, "don't match the backend"),
            (labels_with_a_moved_class, "model has 99"),
        ],
    )
    def test_refuses_a_broken_folder_and_records_nothing(self, model_dir, break_it, message):
        break_it(model_dir)
        with pytest.raises(CommandError, match=message):
            register(model_dir)
        assert not ModelRelease.objects.exists()
        assert not (model_dir / "manifest.json").exists()

    def test_refuses_a_model_over_15_mb(self, model_dir):
        names = []
        for i in range(4):  # 4 shards of 4 MB = 16 MB
            name = f"big{i}.bin"
            (model_dir / name).write_bytes(b"\x00" * (4 * 1024 * 1024))
            names.append(name)
        edit_json(model_dir / "model.json", lambda m: m["weightsManifest"][0].update(paths=names))
        with pytest.raises(CommandError, match="limit is 15.0 MB"):
            register(model_dir)

    def test_refuses_the_same_version_twice(self, model_dir):
        register(model_dir)
        with pytest.raises(CommandError, match="already registered"):
            register(model_dir)

    @pytest.mark.parametrize(
        "extra, message",
        [
            (["--confident", "0.4", "--uncertain", "0.6"], "lower than"),
            (["--confident", "1.5"], "threshold_confident"),
        ],
    )
    def test_refuses_bad_thresholds(self, model_dir, extra, message):
        with pytest.raises(CommandError, match=message):
            register(model_dir, *extra)

    def test_labels_must_match_an_explicit_version(self, model_dir):
        with pytest.raises(CommandError, match="not '2026.11.1'"):
            call_command(
                "register_model", str(model_dir), "--base-url", "https://cdn.example.org/models/2026.11.1/",
                "--min-app-version", "0.1.0", "--model-version", "2026.11.1",
            )  # fmt: skip

    def test_refuses_untrained_placeholder_version(self, model_dir):
        edit_json(model_dir / "labels.json", lambda x: x.update(model_version="0.0.0-untrained"))
        with pytest.raises(CommandError, match="YYYY.MM.N"):
            call_command(
                "register_model", str(model_dir), "--base-url", "https://cdn.example.org/models/0.0.0-untrained/",
                "--min-app-version", "0.1.0",
            )  # fmt: skip

    def test_base_url_must_end_with_a_slash(self, model_dir):
        with pytest.raises(CommandError, match="end with /"):
            call_command(
                "register_model", str(model_dir), "--base-url", BASE.rstrip("/"), "--min-app-version", "0.1.0"
            )

    def test_https_required_outside_development(self, model_dir, settings):
        settings.DEBUG = False
        with pytest.raises(CommandError, match="https"):
            call_command(
                "register_model",
                str(model_dir),
                "--base-url",
                "http://cdn/2026.11.0/",
                "--min-app-version",
                "0.1.0",
            )


def make_release(version, current=False, **fields):
    defaults = dict(
        taxonomy_version="0.1",
        model_url=f"https://cdn.example.org/models/{version}/model.json",
        labels_url=f"https://cdn.example.org/models/{version}/labels.json",
        size_bytes=9_000_000,
        sha256="a" * 64,
        min_app_version="0.1.0",
        is_current=current,
    )
    return ModelRelease.objects.create(model_version=version, **{**defaults, **fields})


@pytest.mark.django_db
class TestCurrent:
    def test_make_current_switches_atomically(self):
        old = make_release("2026.11.0", current=True)
        new = make_release("2026.12.0")
        new.make_current()
        old.refresh_from_db()
        assert not old.is_current
        assert ModelRelease.objects.filter(is_current=True).get() == new

    def test_rollback_is_making_an_older_one_current(self):
        old = make_release("2026.11.0")
        make_release("2026.12.0", current=True)
        old.make_current()
        assert ModelRelease.objects.get(is_current=True).model_version == "2026.11.0"

    def test_database_allows_only_one_current(self):
        make_release("2026.11.0", current=True)
        with pytest.raises(IntegrityError):
            make_release("2026.12.0", current=True)

    def test_database_requires_uncertain_below_confident(self):
        with pytest.raises(IntegrityError):
            make_release("2026.11.0", threshold_confident=0.5, threshold_uncertain=0.6)


@pytest.mark.django_db
class TestLatestEndpoint:
    def test_returns_the_current_release_manifest(self):
        make_release("2026.11.0")
        make_release("2026.12.0", current=True)
        make_release("2027.1.0")  # registered later but not current: phones must not get it yet
        response = APIClient().get(URL)
        assert response.status_code == 200
        body = response.json()
        assert_matches_contract(body, "ModelManifest")
        assert body["model_version"] == "2026.12.0"
        assert body["thresholds"] == {"confident": 0.7, "uncertain": 0.4}
        assert response["Cache-Control"] == "no-cache"

    def test_404_before_any_model_is_released(self):
        make_release("2026.11.0")  # registered, not current
        response = APIClient().get(URL)
        assert response.status_code == 404
        assert response.json()["code"] == "no_model"
        assert_matches_contract(response.json(), "Error")

    def test_is_public(self):
        make_release("2026.11.0", current=True)
        assert APIClient().get(URL).status_code == 200


@pytest.mark.django_db
def test_admin_make_current_action(client, django_user_model):
    admin = django_user_model.objects.create_superuser(phone="+260970000001", password="admin-pass-123")
    client.force_login(admin)
    release = make_release("2026.11.0")
    response = client.post(
        "/admin/releases/modelrelease/",
        {"action": "make_current", "_selected_action": [release.pk]},
        follow=True,
    )
    assert response.status_code == 200
    release.refresh_from_db()
    assert release.is_current
