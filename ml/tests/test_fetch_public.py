"""Public dataset downloader: only approved sources, verified checksums, a complete manifest. No network."""

import hashlib
import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_public as fp  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def opener_for(payloads):
    """An `opener` that serves bytes for known URLs and fails for anything else."""

    def open_url(url):
        if url not in payloads:
            raise AssertionError(f"unexpected download: {url}")
        return FakeResponse(payloads[url])

    return open_url


def test_every_source_records_licence_citation_and_status():
    for key, source in fp.SOURCES.items():
        assert source["status"] in {"approved", "not-approved", "superseded", "licence-unclear"}, key
        assert source["citation"] and source["url"], key
        if source["status"] == "approved":
            assert source["licence"] and source["doi"] and source["files"], key


def test_sources_without_a_confirmed_licence_or_approval_cannot_be_fetched():
    for key, source in fp.SOURCES.items():
        if source["status"] != "approved":
            with pytest.raises(fp.FetchError, match=source["status"]):
                fp.require_approved(key)
    with pytest.raises(fp.FetchError, match="unknown source"):
        fp.require_approved("plantvillage")


def test_the_unclear_licence_source_is_blocked():
    assert fp.SOURCES["wiesner-hanks-nlb"]["status"] == "licence-unclear"


def test_download_keeps_a_file_only_when_its_md5_matches(tmp_path):
    data = b"zip bytes"
    good = {"url": "https://x/a.zip", "md5": hashlib.md5(data).hexdigest()}  # noqa: S324
    entry = fp.download(good, tmp_path / "a.zip", opener_for({good["url"]: data}))
    assert (tmp_path / "a.zip").read_bytes() == data
    assert entry["bytes"] == len(data)

    bad = {"url": "https://x/b.zip", "md5": "0" * 32}
    with pytest.raises(fp.FetchError, match="does not match"):
        fp.download(bad, tmp_path / "b.zip", opener_for({bad["url"]: data}))
    assert not (tmp_path / "b.zip").exists()
    assert not (tmp_path / "b.zip.part").exists()


def test_manifest_records_url_licence_doi_citation_and_date():
    manifest = fp.record(
        {},
        "zmld",
        fp.SOURCES["zmld"],
        {"name": "z.zip", "bytes": 3, "md5": "abc", "source_url": "https://x/z.zip"},
        now=datetime(2026, 11, 16, 12, 0, tzinfo=UTC),
    )
    item = manifest["zmld"]
    assert item["licence"] == "CC-BY-4.0" and item["doi"] == "10.5281/zenodo.18430185"
    assert "Kalunga" in item["citation"] and item["url"].startswith("https://zenodo.org/")
    assert item["files"] == [
        {
            "name": "z.zip",
            "bytes": 3,
            "md5": "abc",
            "source_url": "https://x/z.zip",
            "downloaded_at": "2026-11-16T12:00:00Z",
        }
    ]


def test_fetch_downloads_approved_files_and_skips_verified_ones(tmp_path, monkeypatch):
    data = b"pretend zip"
    source = {
        **fp.SOURCES["zmld"],
        "files": [
            {"name": "z.zip", "url": "https://x/z.zip", "md5": hashlib.md5(data).hexdigest(), "bytes": 11}
        ],  # noqa: S324
    }
    monkeypatch.setitem(fp.SOURCES, "zmld", source)
    manifest_path = tmp_path / "sources.json"

    fp.fetch(
        "zmld", opener=opener_for({"https://x/z.zip": data}), manifest_path=manifest_path, external=tmp_path
    )
    assert (tmp_path / "zmld" / "archives" / "z.zip").read_bytes() == data
    assert json.loads(manifest_path.read_text())["zmld"]["files"][0]["name"] == "z.zip"

    # second run: already verified, so no download (the opener would raise)
    fp.fetch("zmld", opener=opener_for({}), manifest_path=manifest_path, external=tmp_path)


def test_dataverse_checksums_are_looked_up_by_file_id(monkeypatch):
    listing = {
        "data": [{"dataFile": {"id": 6417970, "md5": "aa"}}, {"dataFile": {"id": 6417320, "md5": "bb"}}]
    }
    md5s = fp.dataverse_md5s(opener_for({fp.DATAVERSE_FILES: json.dumps(listing).encode()}))
    assert md5s == {6417970: "aa", 6417320: "bb"}


def test_zip_extraction_refuses_paths_outside_the_target(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape.txt", "x")
    with pytest.raises(fp.FetchError, match="unsafe path"):
        fp.extract(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_extraction_runs_once(tmp_path):
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("healthy/a.jpg", "x")
    out = fp.extract(archive, tmp_path / "out")
    assert (out / "healthy" / "a.jpg").is_file()
    (out / "healthy" / "a.jpg").unlink()
    fp.extract(archive, tmp_path / "out")  # marker present: not unpacked again
    assert not (out / "healthy" / "a.jpg").exists()


def test_mendeley_files_are_checked_with_sha256(tmp_path):
    data = b"mendeley zip"
    file = {"url": "https://x/m.zip", "sha256": hashlib.sha256(data).hexdigest()}
    entry = fp.download(file, tmp_path / "m.zip", opener_for({file["url"]: data}))
    assert entry["sha256"] == file["sha256"] and "md5" not in entry

    tampered = {"url": "https://x/t.zip", "sha256": "0" * 64}
    with pytest.raises(fp.FetchError, match="SHA256"):
        fp.download(tampered, tmp_path / "t.zip", opener_for({tampered["url"]: data}))


def test_every_approved_file_has_a_published_checksum():
    for key, source in fp.SOURCES.items():
        if source["status"] == "approved":
            for f in source["files"]:
                published = "sha256" in f or "md5" in f or "dataverse_id" in f or "dataverse_doi" in source
                assert published, (key, f["name"])


def test_dataverse_files_are_found_by_name_with_their_md5(tmp_path, monkeypatch):
    data = b"tz zip"
    md5 = hashlib.md5(data).hexdigest()  # noqa: S324
    source = {**fp.SOURCES["tz-maize"], "files": [{"name": "MLN.zip"}]}
    monkeypatch.setitem(fp.SOURCES, "tz-maize", source)
    listing = {"data": [{"dataFile": {"id": 42, "filename": "MLN.zip", "md5": md5}}]}
    payloads = {
        fp.DATAVERSE_LISTING.format(doi="10.7910/DVN/GDON8Q"): json.dumps(listing).encode(),
        "https://dataverse.harvard.edu/api/access/datafile/42": data,
    }
    fp.fetch("tz-maize", opener=opener_for(payloads), manifest_path=tmp_path / "s.json", external=tmp_path)
    assert (tmp_path / "tz-maize" / "archives" / "MLN.zip").read_bytes() == data


def test_the_mendeley_tanzania_copy_is_superseded_by_the_reviewed_dataverse_set():
    assert fp.SOURCES["tz-maize-mendeley"]["status"] == "superseded"
    assert fp.SOURCES["tz-maize"]["licence"] == "CC0-1.0"


def test_the_data_root_can_live_outside_the_repo(monkeypatch, tmp_path):
    import importlib

    monkeypatch.setenv("AGRIGUARD_DATA_ROOT", str(tmp_path))
    reloaded = importlib.reload(fp)
    try:
        assert reloaded.EXTERNAL == tmp_path / "raw" / "public"
    finally:
        monkeypatch.delenv("AGRIGUARD_DATA_ROOT")
        importlib.reload(fp)
