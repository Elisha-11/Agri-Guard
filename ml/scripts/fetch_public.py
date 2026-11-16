"""Download approved public maize datasets into ml/data/external/<source>/ (git-ignored) and record them.

Usage:  python ml/scripts/fetch_public.py --list              # known sources and whether each may be fetched
        python ml/scripts/fetch_public.py zmld karaagro       # download (resumes; skips verified files)
        python ml/scripts/fetch_public.py zmld --extract      # also unpack the archives

Every download is checked against the checksum the repository publishes (Zenodo / Dataverse MD5) before it is
kept, and recorded in ml/data/external/sources.json with its URL, licence, DOI, citation and download date.
Only sources with status "approved" can be fetched: a licence must be confirmed, and the team must have
agreed to the download size, before a source is switched on here. Standard library only.
See docs/ml/public-datasets.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "ml" / "data" / "external"
MANIFEST = EXTERNAL / "sources.json"
USER_AGENT = "AgriGuard-dataset-fetch/1.0"
CHUNK = 1 << 20

DATAVERSE_FILES = (
    "https://dataverse.harvard.edu/api/datasets/:persistentId/versions/:latest/files"
    "?persistentId=doi:10.7910/DVN/CXUMDS"
)

# Status: approved = may be downloaded; not-approved = licence fine but the download wasn't agreed;
# licence-unclear = must not be downloaded until the licence is confirmed in writing.
SOURCES = {
    "zmld": {
        "title": "Zambia Maize Leaf Dataset",
        "status": "approved",
        "licence": "CC-BY-4.0",
        "doi": "10.5281/zenodo.18430185",
        "url": "https://zenodo.org/records/18430185",
        "citation": "Kalunga, P. (2026). Zambia Maize Leaf Dataset [Data set]. Zenodo. "
        "https://doi.org/10.5281/zenodo.18430185",
        "files": [
            {
                "name": "Zambia_Maize_Leaf_Dataset_split.zip",
                "url": "https://zenodo.org/records/18430185/files/"
                "Zambia_Maize_Leaf_Dataset_split.zip?download=1",
                "md5": "9e26e70da3c2f6a75334caa0435d2b02",
                "bytes": 143483952,
            }
        ],
        "note": "Downloaded 2026-11-16, then excluded by public_maize.py: the upload holds 1,388 of the "
        "19,990 images described, mostly Kaggle/PlantVillage 'Corn_Gray_Spot' copies, with contradictory "
        "labels.",
    },
    "karaagro": {
        "title": "The KaraAgro AI Maize Dataset (V4.1)",
        "status": "approved",
        "licence": "CC0-1.0",
        "doi": "10.7910/DVN/CXUMDS",
        "url": "https://doi.org/10.7910/DVN/CXUMDS",
        "citation": "Akogo, D., Samori, I., Acquaye, C., Addo, M., Amoako, E., Ezroa-Cudjoe, F., Buaba, J., "
        "Seloame, T. N., Mavis, A., Bright, H., Gyasi-Darko, K., Ababio, Y. O., & Clinton, D. A. (2022). "
        "The KaraAgro AI Maize Dataset (V4.1) [Data set]. Harvard Dataverse. "
        "https://doi.org/10.7910/DVN/CXUMDS",
        # Approved subset only: one healthy and one streak archive (~4.3 GB of 41.2 GB). MD5s come from
        # the Dataverse file listing at download time.
        "files": [
            {
                "name": "healthy_01.rar",
                "url": "https://dataverse.harvard.edu/api/access/datafile/6417970",
                "dataverse_id": 6417970,
                "bytes": 2344875657,
            },
            {
                "name": "maize_streak_01.rar",
                "url": "https://dataverse.harvard.edu/api/access/datafile/6417320",
                "dataverse_id": 6417320,
                "bytes": 1910669961,
            },
        ],
    },
    "tanzania": {
        "title": "Maize Imagery Dataset - Tanzania",
        "status": "approved",
        "licence": "CC-BY-4.0",
        "doi": "10.17632/fkw49mz3xs.1",
        "url": "https://data.mendeley.com/datasets/fkw49mz3xs/1",
        "citation": "Mduma, N., & Mayo, F. (2023). Maize imagery dataset - Tanzania (Version 1) [Data set]. "
        "Mendeley Data. https://doi.org/10.17632/fkw49mz3xs.1",
        # SHA-256 from the Mendeley public API file listing (content_details.sha256_hash), 2026-11-16.
        "files": [
            {
                "name": "HEALTHY.zip",
                "url": "https://data.mendeley.com/public-files/datasets/fkw49mz3xs/files/"
                "5dd32b08-bd7a-41bf-9800-a3b59095fd7c/file_downloaded",
                "sha256": "1d7932d934ae8e45281f45a2b1457605d4f7c6b9f8a7b22caab2ccc51e33d6ab",
                "bytes": 2512057437,
            },
            {
                "name": "MLN.zip",
                "url": "https://data.mendeley.com/public-files/datasets/fkw49mz3xs/files/"
                "d520d003-ee5e-46ac-bdfe-3091496b46b0/file_downloaded",
                "sha256": "1bbc8a48d4e2b71283f4802e7250fec37c29ff38e71157db6357d8e03aff320e",
                "bytes": 2399024212,
            },
            {
                "name": "MSV.zip",
                "url": "https://data.mendeley.com/public-files/datasets/fkw49mz3xs/files/"
                "992c1710-e858-4af8-b1bc-e3c8d1652d90/file_downloaded",
                "sha256": "9e8ea3bb248d4b26efc78678641e77384372e4b31fe939b7ba4bd178350dd6d9",
                "bytes": 2576832390,
            },
        ],
        "note": "Only source with MLN (3,231). Approved 2026-11-16: three per-class zips, 7.49 GB.",
    },
    "ghana_mendeley": {
        "title": "Dataset for Crop Pest and Disease Detection",
        "status": "not-approved",
        "licence": "CC-BY-4.0",
        "doi": "10.17632/bwh3zbpkpv.1",
        "url": "https://data.mendeley.com/datasets/bwh3zbpkpv/1",
        "citation": "Mensah Kwabena, P., Akoto-Adjepong, V., Adu, K., et al. (2023). Dataset for Crop Pest "
        "and Disease Detection (Version 1) [Data set]. Mendeley Data. https://doi.org/10.17632/bwh3zbpkpv.1",
        "files": [],
        "note": "Use the raw maize images only, never the augmented set. Download size not yet known.",
    },
    "wiesner_hanks_nlb": {
        "title": "Image set for deep learning: field images of maize annotated with disease symptoms",
        "status": "licence-unclear",
        "licence": "",
        "doi": "",
        "url": "https://osf.io/p67rz/",
        "citation": "Wiesner-Hanks, T., et al. (2018). BMC Research Notes 11:440. "
        "https://doi.org/10.1186/s13104-018-3548-6",
        "files": [],
        "note": "No licence recorded on the OSF project (API: node_license null). Do not download.",
    },
}


class FetchError(RuntimeError):
    pass


def checksum_kind(file):
    """The checksum the publisher gives for a file: Zenodo and Dataverse publish MD5, Mendeley SHA-256."""
    return "sha256" if "sha256" in file else "md5"


def hash_of(path, kind="md5"):
    digest = hashlib.new(kind)  # MD5 only to match the publisher's checksum, not for security
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_of(path):
    return hash_of(path, "md5")


def read_manifest(path=MANIFEST):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).is_file() else {}


def write_manifest(manifest, path=MANIFEST):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record(manifest, key, source, entry, now=None):
    """Add or replace one downloaded file in the manifest under its source."""
    now = now or datetime.now(UTC)
    item = manifest.setdefault(
        key,
        {k: source[k] for k in ("title", "licence", "doi", "url", "citation")},
    )
    files = [f for f in item.get("files", []) if f["name"] != entry["name"]]
    files.append({**entry, "downloaded_at": now.isoformat(timespec="seconds").replace("+00:00", "Z")})
    item["files"] = sorted(files, key=lambda f: f["name"])
    return manifest


def require_approved(key):
    if key not in SOURCES:
        raise FetchError(f"unknown source {key!r}; known: {', '.join(sorted(SOURCES))}")
    source = SOURCES[key]
    if source["status"] != "approved":
        raise FetchError(f"{key} is {source['status']}: {source.get('note', 'not approved for download')}")
    return source


def open_url(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=60)  # noqa: S310 - fixed https URLs from SOURCES


def dataverse_md5s(opener=open_url):
    """{datafile id: md5} from the Dataverse file listing."""
    with opener(DATAVERSE_FILES) as response:
        data = json.load(response)["data"]
    return {f["dataFile"]["id"]: f["dataFile"]["md5"] for f in data}


def download(file, dest, opener=open_url, progress=None):
    """Stream `file["url"]` to `dest` via a .part file, verify its MD5, then move it into place."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    kind = checksum_kind(file)
    digest, done = hashlib.new(kind), 0
    with opener(file["url"]) as response, part.open("wb") as out:
        for chunk in iter(lambda: response.read(CHUNK), b""):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done)
    if digest.hexdigest() != file[kind]:
        part.unlink()
        raise FetchError(
            f"{dest.name}: {kind.upper()} {digest.hexdigest()} does not match the published {file[kind]}"
        )
    part.replace(dest)
    return {"name": dest.name, "bytes": done, kind: file[kind], "source_url": file["url"]}


def libarchive_tar():
    """A tar that reads RAR: Windows' own bsdtar (libarchive) first.

    Git for Windows puts GNU tar first on PATH; GNU tar can't read RAR and takes `C:\\...` for a remote host.
    """
    system_tar = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
    if system_tar.is_file():
        return str(system_tar)
    return shutil.which("bsdtar") or shutil.which("tar")


def extract(archive, into):
    """Unpack a .zip (zipfile) or .rar (Windows/BSD tar, libarchive) into `into`, once."""
    archive, into = Path(archive), Path(into)
    marker = into / ".extracted"
    if marker.is_file():
        return into
    into.mkdir(parents=True, exist_ok=True)
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                target = (into / member.filename).resolve()
                if not str(target).startswith(str(into.resolve())):
                    raise FetchError(f"{archive.name}: unsafe path {member.filename!r}")
            z.extractall(into)
    elif archive.suffix.lower() == ".rar":
        tar = libarchive_tar()
        if not tar:
            raise FetchError("extracting .rar needs tar (libarchive): built into Windows 10+")
        subprocess.run([tar, "-xf", str(archive), "-C", str(into)], check=True)  # noqa: S603
    else:
        raise FetchError(f"don't know how to extract {archive.name}")
    marker.write_text(archive.name, encoding="utf-8")
    return into


def fetch(key, *, do_extract=False, opener=open_url, manifest_path=MANIFEST, external=EXTERNAL):
    source = require_approved(key)
    manifest = read_manifest(manifest_path)
    files = [dict(f) for f in source["files"]]
    if any("dataverse_id" in f for f in files):
        md5s = dataverse_md5s(opener)
        for f in files:
            f["md5"] = md5s[f["dataverse_id"]]

    for f in files:
        dest = Path(external) / key / "archives" / f["name"]
        kind = checksum_kind(f)
        if dest.is_file() and hash_of(dest, kind) == f[kind]:
            print(f"{key}/{f['name']}: already downloaded and verified")
        else:
            print(f"{key}/{f['name']}: downloading {f['bytes'] / 1e9:.2f} GB")
            entry = download(f, dest, opener)
            record(manifest, key, source, entry)
            write_manifest(manifest, manifest_path)
        if do_extract:
            extract(dest, Path(external) / key / "extracted" / dest.stem)
            print(f"{key}/{f['name']}: extracted")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sources", nargs="*")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args(argv)

    if args.list or not args.sources:
        for key, s in SOURCES.items():
            size = sum(f.get("bytes", 0) for f in s["files"]) / 1e9
            print(f"{key:18} {s['status']:16} {s['licence'] or '?':10} {size:6.2f} GB  {s['title']}")
        return 0
    try:
        for key in args.sources:
            fetch(key, do_extract=args.extract)
    except FetchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
