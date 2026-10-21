"""PUT /api/v1/diagnoses/{client_id}/photo/: consent, ownership, size, JPEG checks and metadata stripping."""

import uuid

import pytest
from rest_framework.test import APIClient

from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import DiagnosisFactory, FarmerFactory
from apps.diagnoses.photos import MAX_PHOTO_BYTES, InvalidPhoto, strip_metadata


def segment(marker, payload):
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


JFIF = segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
EXIF = segment(0xE1, b"Exif\x00\x00GPS -15.416,28.283 Samsung SM-A105")
XMP = segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta/>")
COMMENT = segment(0xFE, b"taken at the Banda farm")
ICC = segment(0xE2, b"ICC_PROFILE\x00\x01\x01profile")
QUANT = segment(0xDB, b"\x00" + bytes(range(64)))
FRAME = segment(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00")  # baseline, 16 x 16, one component
HUFFMAN = segment(0xC4, b"\x00" + bytes(16))
SCAN = segment(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\xff\x00\x56"  # FF 00 is a stuffed byte
START, END = b"\xff\xd8", b"\xff\xd9"


def jpeg(*segments):
    """A structurally valid JPEG (what the server checks), not a decodable picture."""
    return START + b"".join(segments or (JFIF, QUANT, FRAME, HUFFMAN)) + SCAN + END


PHOTO = jpeg()


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def consenting_farmer(farmer):
    farmer.photo_consent = True
    farmer.save(update_fields=["photo_consent"])
    return farmer


@pytest.fixture
def diagnosis(taxonomy, consenting_farmer):
    return DiagnosisFactory(farmer=consenting_farmer)


def url(client_id):
    return f"/api/v1/diagnoses/{client_id}/photo/"


def put(client, diagnosis, body=PHOTO, content_type="image/jpeg"):
    return client.put(url(diagnosis.client_id), body, content_type=content_type)


def assert_error(response, status, code):
    assert response.status_code == status, response.content
    assert_matches_contract(response.json(), "Error")
    assert response.json()["code"] == code, response.json()


class TestUpload:
    def test_stores_the_photo(self, farmer_api, diagnosis, media_root):
        response = put(farmer_api, diagnosis)
        assert response.status_code == 204, response.content
        diagnosis.refresh_from_db()
        assert diagnosis.has_photo
        assert diagnosis.photo.name == f"diagnoses/{diagnosis.farmer_id}/{diagnosis.client_id}.jpg"
        assert (media_root / diagnosis.photo.name).read_bytes() == PHOTO

    def test_history_then_reports_has_photo(self, farmer_api, diagnosis):
        put(farmer_api, diagnosis)
        item = farmer_api.get("/api/v1/diagnoses/").json()["results"][0]
        assert item["has_photo"] is True

    def test_sending_again_replaces_the_photo(self, farmer_api, diagnosis, media_root):
        """A retry after a dropped connection is safe, and leaves one file, not two."""
        put(farmer_api, diagnosis)
        second = jpeg(JFIF, QUANT, FRAME, HUFFMAN, segment(0xDD, b"\x00\x04"))  # a different valid JPEG
        assert put(farmer_api, diagnosis, second).status_code == 204
        diagnosis.refresh_from_db()
        assert diagnosis.photo.name.endswith(f"{diagnosis.client_id}.jpg")
        assert (media_root / diagnosis.photo.name).read_bytes() == second
        assert len(list((media_root / "diagnoses").rglob("*.jpg"))) == 1

    def test_exactly_1_mb_is_accepted(self, farmer_api, diagnosis):
        padding = segment(0xFE, b"x" * 60000)  # comments are dropped, so the stored file is smaller
        body = jpeg(JFIF, QUANT, FRAME, HUFFMAN, *[padding] * 17)
        body = body[:-2] + b"\x00" * (MAX_PHOTO_BYTES - len(body)) + body[-2:]  # pad the scan data
        assert len(body) == MAX_PHOTO_BYTES
        assert put(farmer_api, diagnosis, body).status_code == 204

    def test_metadata_is_removed_before_storing(self, farmer_api, diagnosis, media_root):
        """EXIF can hold GPS, which would get around location consent."""
        put(farmer_api, diagnosis, jpeg(JFIF, EXIF, XMP, COMMENT, ICC, QUANT, FRAME, HUFFMAN))
        diagnosis.refresh_from_db()
        stored = (media_root / diagnosis.photo.name).read_bytes()
        assert stored == jpeg(JFIF, ICC, QUANT, FRAME, HUFFMAN)
        assert b"GPS" not in stored and b"Banda" not in stored and b"xmpmeta" not in stored


class TestRefused:
    def test_without_photo_consent_is_a_403(self, farmer_api, farmer, taxonomy):
        diagnosis = DiagnosisFactory(farmer=farmer)  # photo_consent is off by default
        assert_error(put(farmer_api, diagnosis), 403, "photo_consent_required")
        diagnosis.refresh_from_db()
        assert not diagnosis.has_photo

    def test_unsynced_diagnosis_is_a_404(self, farmer_api, consenting_farmer):
        response = farmer_api.put(url(uuid.uuid4()), PHOTO, content_type="image/jpeg")
        assert_error(response, 404, "not_found")

    def test_someone_elses_diagnosis_is_a_404(self, farmer_api, consenting_farmer, taxonomy):
        """Same answer as "not synced", so the API doesn't reveal that it exists."""
        theirs = DiagnosisFactory(farmer=FarmerFactory(phone="+260961111111", photo_consent=True))
        assert_error(put(farmer_api, theirs), 404, "not_found")
        theirs.refresh_from_db()
        assert not theirs.has_photo

    def test_extension_officers_cannot_upload_to_other_farmers_diagnoses(self, diagnosis):
        officer = FarmerFactory(phone="+260961111111", role="extension_officer", photo_consent=True)
        client = APIClient()
        client.force_authenticate(officer)
        assert_error(put(client, diagnosis), 404, "not_found")

    def test_over_1_mb_is_a_413(self, farmer_api, diagnosis):
        body = PHOTO[:-2] + b"\x00" * (MAX_PHOTO_BYTES - len(PHOTO) + 1) + PHOTO[-2:]
        assert len(body) == MAX_PHOTO_BYTES + 1
        assert_error(put(farmer_api, diagnosis, body), 413, "photo_too_large")

    def test_wrong_content_type_is_a_415(self, farmer_api, diagnosis):
        assert_error(put(farmer_api, diagnosis, content_type="image/png"), 415, "unsupported_media_type")

    @pytest.mark.parametrize(
        "body",
        [
            b"",
            b"\x89PNG\r\n\x1a\n" + bytes(100),
            PHOTO[:-2],  # cut off: no end marker
            START + JFIF + QUANT + HUFFMAN + SCAN + END,  # no frame: there's no image
            START + JFIF + b"\xff\xe1\xff\xff" + END,  # a segment longer than the file
            START + END,
        ],
        ids=["empty", "png", "truncated", "no-frame", "bad-length", "nothing-inside"],
    )
    def test_not_a_jpeg_is_a_400(self, farmer_api, diagnosis, body):
        assert_error(put(farmer_api, diagnosis, body), 400, "invalid_photo")
        diagnosis.refresh_from_db()
        assert not diagnosis.has_photo

    def test_requires_a_token(self, diagnosis):
        assert put(APIClient(), diagnosis).status_code == 401


class TestStripMetadata:
    def test_keeps_a_jpeg_without_metadata_byte_for_byte(self):
        assert strip_metadata(PHOTO) == PHOTO

    def test_trailing_padding_after_the_end_is_allowed(self):
        assert strip_metadata(PHOTO + b"\x00\x00") == PHOTO + b"\x00\x00"

    def test_fill_bytes_before_a_marker_are_accepted_and_dropped(self):
        body = START + JFIF + b"\xff\xff" + QUANT + FRAME + HUFFMAN + SCAN + END
        assert strip_metadata(body) == PHOTO

    def test_rejects_a_second_start_marker(self):
        with pytest.raises(InvalidPhoto):
            strip_metadata(START + JFIF + START + FRAME + SCAN + END)
