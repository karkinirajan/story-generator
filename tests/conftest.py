import io

import pytest

from storylens import create_app
from storylens.config import Config

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


class FakeGenerator:
    """Stands in for the OpenAI call and records what it was given."""

    def __init__(self, result=None, error=None):
        self.result = result or {"title": "A Day at the Lake", "story": "The light was golden."}
        self.error = error
        self.calls = []

    def generate(self, image, mime, meta):
        self.calls.append((image, mime, meta))
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def generator():
    return FakeGenerator()


@pytest.fixture
def make_client(generator):
    def make(config=None, generator=generator):
        app = create_app(
            config or Config(openai_api_key="demo", rate_limit_per_minute=0), generator=generator
        )
        return app.test_client()

    return make


@pytest.fixture
def client(make_client):
    return make_client()


def upload(client, data=PNG, filename="photo.png", **fields):
    form = {
        "photo": (io.BytesIO(data), filename),
        "name": "Grandma",
        "date": "2026-10-01",
        "note": "",
        **fields,
    }
    return client.post("/generate-vision-story", data=form, content_type="multipart/form-data")
