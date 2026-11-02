import io

import pytest
from werkzeug.datastructures import FileStorage

from storylens.images import InvalidImage, detect_mime, read_image

from .conftest import JPEG, PNG, WEBP


def storage(data):
    return FileStorage(stream=io.BytesIO(data), filename="x")


@pytest.mark.parametrize(
    ("data", "mime"),
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (WEBP, "image/webp"),
        (b"\xff\xd8\xff\xdb" + b"1" * 9, "image/jpeg"),
    ],
)
def test_the_type_comes_from_the_content(data, mime):
    assert detect_mime(data) == mime


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"GIF89a" + b"\x00" * 20,
        b"%PDF-1.7 ...",
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"<html><script>alert(1)</script></html>",
        b"RIFF\x00\x00\x00\x00WAVEfmt ",  # a RIFF file that is not WebP
        b"\x89PNG",  # a truncated signature
        b"MZ\x90\x00 an executable renamed to .jpg",
        b"plain text pretending to be a photo.jpg",
    ],
)
def test_other_content_is_not_an_image_whatever_the_file_name(data):
    assert detect_mime(data) is None


def test_read_image_returns_the_bytes_and_the_real_type():
    assert read_image(storage(PNG), 1000) == (PNG, "image/png")


def test_an_empty_upload_is_refused():
    with pytest.raises(InvalidImage, match="empty"):
        read_image(storage(b""), 1000)


def test_a_file_over_the_limit_is_refused_after_reading_only_a_little_more_than_the_limit():
    stream = io.BytesIO(PNG + b"\x00" * 5000)
    with pytest.raises(InvalidImage, match="too large"):
        read_image(FileStorage(stream=stream), 100)
    assert stream.tell() == 101  # it did not read the whole file


def test_a_file_exactly_at_the_limit_is_accepted():
    assert read_image(storage(PNG), len(PNG))[1] == "image/png"


def test_not_an_image_is_refused_with_a_helpful_message():
    with pytest.raises(InvalidImage, match="JPEG, PNG or WebP"):
        read_image(storage(b"hello"), 1000)
