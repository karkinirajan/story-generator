import io
import logging
import re

import pytest

from storylens.config import Config
from storylens.stories import Metadata, StoryError

from .conftest import JPEG, PNG, WEBP, FakeGenerator, upload


class TestHappyPath:
    def test_a_photo_and_details_give_a_title_and_a_story(self, client, generator):
        response = upload(client, name="Grandma & I", date="2026-10-01", note="Her 80th")
        assert response.status_code == 200
        assert response.get_json() == {
            "title": "A Day at the Lake",
            "story": "The light was golden.",
        }
        image, mime, meta = generator.calls[0]
        assert (image, mime) == (PNG, "image/png")
        assert meta == Metadata(name="Grandma & I", date="2026-10-01", note="Her 80th")

    def test_the_answer_is_private_and_not_cached(self, client):
        assert upload(client).headers["Cache-Control"] == "no-store"

    @pytest.mark.parametrize(
        ("data", "mime"), [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")]
    )
    def test_the_type_sent_on_is_the_real_one_not_the_file_name(
        self, client, generator, data, mime
    ):
        assert upload(client, data=data, filename="holiday.txt").status_code == 200
        assert generator.calls[0][1] == mime

    def test_details_are_trimmed_and_the_note_is_optional(self, client, generator):
        upload(client, name="  Max  ", date=" 2026-01-02 ")
        assert generator.calls[0][2] == Metadata(name="Max", date="2026-01-02", note="")


class TestRefusals:
    def test_no_photo(self, client):
        response = client.post(
            "/generate-vision-story", data={"name": "x"}, content_type="multipart/form-data"
        )
        assert response.status_code == 400 and "Choose a photo" in response.get_json()["error"]

    def test_an_empty_file_name(self, client):
        assert upload(client, filename="").status_code == 400

    def test_a_non_image_with_an_image_name_is_refused(self, client, generator):
        """The old code trusted the extension."""
        response = upload(
            client, data=b"<html><script>alert(1)</script></html>", filename="cute.jpg"
        )
        assert response.status_code == 415 and "JPEG, PNG or WebP" in response.get_json()["error"]
        assert generator.calls == []

    def test_an_empty_upload(self, client):
        assert upload(client, data=b"").status_code in (400, 415)

    def test_a_photo_over_the_limit_is_413_with_a_plain_message(self, make_client, generator):
        client = make_client(
            Config(openai_api_key="demo", max_upload_mb=1, rate_limit_per_minute=0)
        )
        response = upload(client, data=PNG + b"\x00" * (2 * 1024 * 1024))
        assert response.status_code == 413
        assert response.get_json() == {"error": "The photo is too large (at most 1 MB)."}
        assert generator.calls == []

    @pytest.mark.parametrize(("field", "limit"), [("name", 100), ("date", 50), ("note", 500)])
    def test_overlong_details_are_refused(self, client, generator, field, limit):
        response = upload(client, **{field: "x" * (limit + 1)})
        assert response.status_code == 400 and f"at most {limit}" in response.get_json()["error"]
        assert generator.calls == []

    def test_details_at_the_limit_are_accepted(self, client):
        assert upload(client, name="n" * 100, date="d" * 50, note="o" * 500).status_code == 200


class TestWhenSomethingFails:
    def test_a_model_failure_is_a_502_with_a_plain_message(self, make_client):
        client = make_client(generator=FakeGenerator(error=StoryError("RateLimitError")))
        response = upload(client)
        assert response.status_code == 502  # the old code answered 200 with a story titled "Error"
        assert response.get_json() == {
            "error": "The story could not be written right now. Please try again."
        }
        assert "RateLimitError" not in response.get_data(as_text=True)

    def test_no_openai_key_is_a_503(self, make_client):
        client = make_client(Config(openai_api_key=""), generator=None)
        assert upload(client).status_code == 503

    def test_an_unexpected_error_does_not_leak_its_text(self, make_client, caplog):
        client = make_client(
            generator=FakeGenerator(error=RuntimeError("secret path /srv/app/.env and key sk-abc"))
        )
        with caplog.at_level(logging.ERROR):
            response = upload(client)
        assert response.status_code == 500 and response.get_json() == {
            "error": "Something went wrong."
        }
        assert "sk-abc" not in response.get_data(as_text=True)
        assert "sk-abc" in caplog.text  # the operator can still see it

    def test_the_api_route_answers_in_json_for_other_methods(self, client):
        response = client.get("/generate-vision-story")
        assert response.status_code == 405 and response.get_json() == {
            "error": "Method Not Allowed"
        }

    def test_other_missing_pages_keep_the_normal_404(self, client):
        assert client.get("/nope").status_code == 404


class TestRateLimit:
    def test_too_many_requests_get_429_with_retry_after(self, make_client, generator):
        client = make_client(Config(openai_api_key="demo", rate_limit_per_minute=2))
        assert [upload(client).status_code for _ in range(3)] == [200, 200, 429]
        refused = upload(client)
        assert (
            int(refused.headers["Retry-After"]) >= 1 and "Too many" in refused.get_json()["error"]
        )
        assert len(generator.calls) == 2  # the refused calls cost nothing

    def test_other_pages_are_not_limited(self, make_client):
        client = make_client(Config(openai_api_key="demo", rate_limit_per_minute=1))
        upload(client)
        assert client.get("/").status_code == 200 and client.get("/healthz").status_code == 200

    def test_behind_a_trusted_proxy_each_real_client_has_its_own_limit(self, make_client):
        client = make_client(
            Config(openai_api_key="demo", rate_limit_per_minute=1, trusted_proxies=1)
        )

        def post(ip):
            data = {"photo": (io.BytesIO(PNG), "a.png")}
            return client.post("/generate-vision-story", data=data, headers={"X-Forwarded-For": ip})

        assert (
            post("1.1.1.1").status_code,
            post("2.2.2.2").status_code,
            post("1.1.1.1").status_code,
        ) == (200, 200, 429)


class TestPrivacy:
    def test_the_photo_is_never_written_to_disk_even_when_it_is_large(
        self, client, monkeypatch, tmp_path
    ):
        """Werkzeug's default is a temporary file for any upload over 500 KB, which is most phone photos."""
        import werkzeug.formparser as formparser

        def forbidden(*args, **kwargs):
            raise AssertionError("an uploaded photo was spooled to a temporary file")

        monkeypatch.setattr(formparser, "SpooledTemporaryFile", forbidden)
        monkeypatch.setattr(formparser, "TemporaryFile", forbidden, raising=False)
        monkeypatch.chdir(tmp_path)
        assert upload(client, data=PNG + b"\x00" * (3 * 1024 * 1024)).status_code == 200
        assert list(tmp_path.iterdir()) == []  # and nothing was left in the working directory

    def test_the_story_and_the_details_are_not_logged(self, make_client, caplog):
        client = make_client(
            generator=FakeGenerator({"title": "Secret Title", "story": "A very private story."})
        )
        with caplog.at_level(logging.DEBUG):
            upload(client, name="Alice Private", note="her diagnosis")
        assert "Secret Title" not in caplog.text and "private story" not in caplog.text
        assert "Alice Private" not in caplog.text and "diagnosis" not in caplog.text
        assert "Story written" in caplog.text  # the size and the time are logged

    def test_a_failure_logs_the_kind_of_error_but_not_the_photo_or_details(
        self, make_client, caplog
    ):
        client = make_client(generator=FakeGenerator(error=StoryError("APIConnectionError")))
        with caplog.at_level(logging.DEBUG):
            upload(client, name="Alice Private")
        assert "APIConnectionError" in caplog.text and "Alice Private" not in caplog.text


class TestPage:
    def test_the_page_renders_with_the_form_and_the_limit(self, client):
        html = client.get("/").get_data(as_text=True)
        assert (
            'id="storyForm"' in html
            and "up to 10 MB" in html
            and 'accept="image/jpeg,image/png,image/webp"' in html
        )

    def test_it_loads_nothing_from_a_third_party_and_has_no_inline_script_or_style(self, client):
        html = client.get("/").get_data(as_text=True)
        assert not re.findall(r'(?:src|href)="https?://', html)
        assert "<style" not in html and not re.search(r"<script(?![^>]*\bsrc=)", html)
        assert " style=" not in html and " onclick=" not in html

    def test_the_security_headers_are_set_everywhere(self, client):
        for path in ("/", "/healthz", "/static/app.js", "/nope"):
            headers = client.get(path).headers
            csp = headers["Content-Security-Policy"]
            assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp, path
            assert (
                headers["X-Content-Type-Options"] == "nosniff"
                and headers["Referrer-Policy"] == "no-referrer"
            )

    def test_the_stylesheet_and_script_are_served_and_use_no_google_fonts(self, client):
        css = client.get("/static/style.css")
        assert (
            css.status_code == 200
            and b"fonts.googleapis" not in css.data
            and b"Playfair" not in css.data
        )
        assert client.get("/static/app.js").status_code == 200

    def test_the_page_says_the_photo_is_sent_to_openai(self, client):
        assert "sent to OpenAI" in client.get("/").get_data(as_text=True)

    def test_the_health_check(self, client):
        assert client.get("/healthz").get_json() == {"status": "ok"}


class TestWiring:
    def test_without_an_injected_generator_one_is_built_from_the_openai_settings(self):
        from unittest.mock import patch

        from storylens import create_app

        config = Config(
            openai_api_key="sk-demo",
            openai_model="vision-x",
            openai_timeout=12.5,
            max_completion_tokens=321,
        )
        with patch("storylens.OpenAI") as factory:
            app = create_app(config)
        factory.assert_called_once_with(api_key="sk-demo", timeout=12.5)
        generator = app.extensions["storylens"]["generator"]
        assert (generator.client, generator.model, generator.max_completion_tokens) == (
            factory.return_value,
            "vision-x",
            321,
        )

    def test_without_a_key_the_app_still_starts_and_serves_the_page(self):
        from storylens import create_app

        app = create_app(Config(openai_api_key=""))
        assert app.extensions["storylens"]["generator"] is None
        assert app.test_client().get("/").status_code == 200

    def test_the_request_size_limit_follows_the_setting(self):
        from storylens import create_app

        app = create_app(Config(openai_api_key="", max_upload_mb=2))
        assert 2 * 1024 * 1024 < app.config["MAX_CONTENT_LENGTH"] < 3 * 1024 * 1024
