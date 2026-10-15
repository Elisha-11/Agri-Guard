"""Register a converted TensorFlow.js model as a release, after checking its files and labels.

    python manage.py register_model path/to/2026.11.0 \\
        --base-url https://cdn.example.org/models/2026.11.0/ \\
        --min-app-version 0.1.0 [--confident 0.7 --uncertain 0.4] [--notes "..."] [--make-current]

The folder must contain model.json, every weight shard it lists, and labels.json. The command refuses, and
records nothing, unless:

- every shard listed in model.json exists, each is at most 4 MB, and the total is at most 15 MB;
- labels.json has this model_version, the backend's taxonomy_version, and exactly the backend's classes at
  exactly the same indices (otherwise predictions would be stored under the wrong disease);
- the version isn't registered yet, and --base-url ends with /<model_version>/.

It then computes size_bytes and the SHA-256 of model.json, records the release, and writes manifest.json into
the folder so it can be uploaded with the model. A new release is NOT current unless --make-current is given:
upload the folder first, check the URLs work, then make it current (here or in the admin).
See docs/backend/model-releases.md.
"""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Disease
from apps.releases.models import MAX_MODEL_BYTES, ModelRelease

MAX_SHARD_BYTES = 4 * 1024 * 1024  # docs/model-output.md §1: shards of at most 4 MB, for progressive download


def mb(n):
    return f"{n / 1024 / 1024:.1f} MB"


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CommandError(f"Missing {path.name} in {path.parent}.") from exc
    except ValueError as exc:
        raise CommandError(f"{path.name} isn't valid JSON: {exc}") from exc


def check_weights(folder, model_json):
    """Return the total size of model.json + shards, after checking every shard exists and is small enough."""
    manifest = model_json.get("weightsManifest")
    if not isinstance(manifest, list) or not manifest:
        raise CommandError("model.json has no weightsManifest. Is this a TensorFlow.js model?")
    total = (folder / "model.json").stat().st_size
    for group in manifest:
        for name in group.get("paths", []):
            shard = folder / name
            if not shard.is_file():
                raise CommandError(f"model.json lists {name}, which isn't in the folder.")
            size = shard.stat().st_size
            if size > MAX_SHARD_BYTES:
                raise CommandError(f"{name} is {mb(size)}; shards must be at most {mb(MAX_SHARD_BYTES)}.")
            total += size
    if total > MAX_MODEL_BYTES:
        raise CommandError(f"Model is {mb(total)} in total; the limit is {mb(MAX_MODEL_BYTES)}.")
    return total


def check_labels(labels, version):
    """labels.json must describe exactly the backend's taxonomy, index for index."""
    if labels.get("model_version") != version:
        raise CommandError(
            f"labels.json says model_version {labels.get('model_version')!r}, not {version!r}."
        )

    diseases = list(Disease.objects.all())
    if not diseases:
        raise CommandError("The backend has no diseases. Run `manage.py load_taxonomy` first.")
    backend_taxonomy = diseases[0].taxonomy_version
    if labels.get("taxonomy_version") != backend_taxonomy:
        raise CommandError(
            f"labels.json is taxonomy {labels.get('taxonomy_version')!r}, but the backend has "
            f"{backend_taxonomy!r}. Load the new taxonomy first (`load_taxonomy`)."
        )

    theirs = {(c.get("index"), c.get("id")) for c in labels.get("classes", [])}
    ours = {(d.class_index, d.class_id) for d in diseases}
    if theirs != ours:
        problems = [f"  model has {i}: {c}" for i, c in sorted(theirs - ours, key=str)]
        problems += [f"  backend has {i}: {c}" for i, c in sorted(ours - theirs, key=str)]
        raise CommandError("labels.json classes don't match the backend:\n" + "\n".join(problems))
    return backend_taxonomy


class Command(BaseCommand):
    help = "Check a converted model folder and register it as a release (writes manifest.json)."

    def add_arguments(self, parser):
        parser.add_argument("folder", help="Folder with model.json, its shards and labels.json")
        parser.add_argument("--base-url", required=True, help="Public URL of the folder, ending in /")
        parser.add_argument("--min-app-version", required=True, help="Oldest PWA version that can run it")
        parser.add_argument(
            "--model-version", dest="model_version", help="Defaults to labels.json model_version"
        )
        parser.add_argument("--confident", type=float, default=0.7)
        parser.add_argument("--uncertain", type=float, default=0.4)
        parser.add_argument("--notes", default="")
        parser.add_argument("--make-current", action="store_true", help="Switch phones to it immediately")

    def handle(self, *args, **opts):
        folder = Path(opts["folder"])
        if not folder.is_dir():
            raise CommandError(f"{folder} is not a folder.")
        base_url = opts["base_url"]
        if not base_url.endswith("/"):
            raise CommandError("--base-url must end with /")
        if not base_url.startswith("https://") and not settings.DEBUG:
            raise CommandError("--base-url must be https:// outside development.")

        model_json = read_json(folder / "model.json")
        labels = read_json(folder / "labels.json")
        version = opts["model_version"] or labels.get("model_version", "")
        if not base_url.endswith(f"/{version}/"):
            # docs/model-output.md §1: each version has its own path, so cached copies are never overwritten.
            raise CommandError(f"--base-url must end with /{version}/ (each model version has its own path).")
        if ModelRelease.objects.filter(model_version=version).exists():
            raise CommandError(f"{version} is already registered. Each version is published once.")

        size = check_weights(folder, model_json)
        taxonomy = check_labels(labels, version)
        release = ModelRelease(
            model_version=version,
            taxonomy_version=taxonomy,
            model_url=base_url + "model.json",
            labels_url=base_url + "labels.json",
            size_bytes=size,
            sha256=hashlib.sha256((folder / "model.json").read_bytes()).hexdigest(),
            threshold_confident=opts["confident"],
            threshold_uncertain=opts["uncertain"],
            min_app_version=opts["min_app_version"],
            notes=opts["notes"],
        )
        try:
            release.full_clean()
        except ValidationError as exc:
            lines = [f"  {field}: {' '.join(msgs)}" for field, msgs in exc.message_dict.items()]
            raise CommandError("Release is invalid:\n" + "\n".join(lines)) from exc

        with transaction.atomic():
            release.save()
            (folder / "manifest.json").write_text(
                json.dumps(release.manifest(), indent=2) + "\n", encoding="utf-8"
            )
            if opts["make_current"]:
                release.make_current()

        self.stdout.write(
            self.style.SUCCESS(f"Registered {version}: {mb(size)}, sha256 {release.sha256[:12]}...")
        )
        self.stdout.write(f"Wrote {folder / 'manifest.json'}. Upload the whole folder to {base_url}")
        if release.is_current:
            self.stdout.write(self.style.WARNING("It is now CURRENT: phones will download it."))
        else:
            self.stdout.write(
                "Not current yet. After uploading, make it current in the admin (Model releases)."
            )
