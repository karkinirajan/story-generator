"""Checks what an upload really is. The old code looked at the file *name* only and then labelled
every image ``image/jpeg``."""

PNG = b"\x89PNG\r\n\x1a\n"


class InvalidImage(ValueError):
    """The upload is not a JPEG, PNG or WebP image."""


def detect_mime(data: bytes) -> str | None:
    if data.startswith(PNG):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def read_image(file_storage, max_bytes: int) -> tuple[bytes, str]:
    """The upload's bytes (never written to disk) and its real type."""
    data = file_storage.stream.read(max_bytes + 1)
    if not data:
        raise InvalidImage("The file is empty.")
    if len(data) > max_bytes:
        raise InvalidImage("The photo is too large.")
    mime = detect_mime(data)
    if mime is None:
        raise InvalidImage("Please upload a JPEG, PNG or WebP photo.")
    return data, mime
