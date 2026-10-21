"""Leaf photos for `PUT /diagnoses/{client_id}/photo/`: check the bytes are a JPEG and strip its metadata.

Phone cameras write EXIF into JPEGs: GPS coordinates, the time, the phone model. GPS would get around
`location_consent` (docs/offline-sync.md, "Location privacy"), so the server removes every metadata segment
before storing, whatever the PWA did. Only the segments needed to show the image are kept. See ADR 0011.

This walks the JPEG's segment structure in plain Python rather than decoding the image (no Pillow): enough to
reject things that aren't JPEGs and to drop metadata, without a new dependency or re-encoding the photo.
"""

from rest_framework import exceptions, status
from rest_framework.parsers import BaseParser

MAX_PHOTO_BYTES = 1024 * 1024  # contract: "max 1 MB"

SOI, EOI, SOS = 0xD8, 0xD9, 0xDA
# Segments that only carry metadata: APP1 (EXIF, XMP), APP3-APP13 (IPTC, maker notes, ...), APP15 and COM.
# Kept: APP0 (JFIF), APP2 (ICC colour profile) and APP14 (Adobe colour transform), which affect how the
# image looks.
METADATA_MARKERS = {0xE1, *range(0xE3, 0xEE), 0xEF, 0xFE}
# Start-of-frame markers, i.e. an actual image. C4, C8 and CC share the range but are something else.
FRAME_MARKERS = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
# Markers with no length field after them.
STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}


class InvalidPhoto(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The photo is not a valid JPEG."
    default_code = "invalid_photo"


class PhotoTooLarge(exceptions.APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = f"The photo is larger than {MAX_PHOTO_BYTES // 1024} KB. Resize it on the device first."
    default_code = "photo_too_large"


class JpegParser(BaseParser):
    """Reads a raw `image/jpeg` body as bytes, stopping as soon as it is over the limit."""

    media_type = "image/jpeg"

    def parse(self, stream, media_type=None, parser_context=None):
        data = stream.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoTooLarge()
        return data


def strip_metadata(data):
    """Return the JPEG `data` without its metadata segments. Raises InvalidPhoto if it isn't a JPEG.

    A JPEG is a list of segments, each `FF <marker> <2-byte length> <payload>`, up to the start-of-scan (SOS)
    segment; after that comes the compressed image itself, ending with `FF D9`. Everything from SOS on is
    copied unchanged.
    """
    if not isinstance(data, bytes | bytearray) or data[:2] != bytes([0xFF, SOI]):
        raise InvalidPhoto()

    kept = [data[:2]]
    has_frame = False
    pos = 2
    while True:
        if pos >= len(data) or data[pos] != 0xFF:
            raise InvalidPhoto()
        while pos < len(data) and data[pos] == 0xFF:  # a marker may be preceded by fill bytes
            pos += 1
        if pos >= len(data):
            raise InvalidPhoto()
        marker = data[pos]
        start = pos - 1
        pos += 1
        if marker in STANDALONE_MARKERS:
            kept.append(data[start:pos])
            continue
        if marker in (SOI, EOI) or pos + 2 > len(data):
            raise InvalidPhoto()  # a second start, or the end before any image data
        length = int.from_bytes(data[pos : pos + 2], "big")
        end = pos + length
        if length < 2 or end > len(data):
            raise InvalidPhoto()
        if marker == SOS:
            break
        has_frame = has_frame or marker in FRAME_MARKERS
        if marker not in METADATA_MARKERS:
            kept.append(data[start:end])
        pos = end

    # Encoders sometimes pad after the end marker; ignore that when checking the image is complete.
    if not has_frame or not data.rstrip(b"\x00").endswith(bytes([0xFF, EOI])):
        raise InvalidPhoto()
    kept.append(data[start:])
    return b"".join(kept)
