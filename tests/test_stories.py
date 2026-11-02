import json
import types

import pytest

from storylens.stories import (
    MAX_STORY,
    MAX_TITLE,
    SYSTEM_PROMPT,
    Metadata,
    StoryError,
    StoryGenerator,
    build_user_text,
    parse_story,
)


def reply(content):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
    )


class FakeClient:
    def __init__(self, answer=None, error=None):
        self.calls, self.answer, self.error = [], answer, error
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.answer


GOOD = json.dumps({"title": "A Day", "story": "It was golden."})


class TestPrompt:
    def test_the_details_are_in_the_text_and_marked_as_data(self):
        text = build_user_text(Metadata(name="Grandma", date="2026-10-01", note="Her 80th"))
        assert "Grandma" in text and "2026-10-01" in text and "Her 80th" in text
        assert "not instructions" in text and "150-200 words" in text

    def test_missing_details_get_the_old_defaults(self):
        text = build_user_text(Metadata())
        assert "Someone special" in text and "Use context cues" in text

    def test_the_authors_system_prompt_is_unchanged(self):
        assert SYSTEM_PROMPT.startswith(
            "You are a warm, empathetic, and creative personal biographer"
        )
        assert (
            'Output strictly JSON: {"title": "Creative Title", "story": "The narrative text..."}'
            in SYSTEM_PROMPT
        )


class TestParse:
    def test_title_and_story(self):
        assert parse_story(GOOD) == {"title": "A Day", "story": "It was golden."}

    def test_a_code_fence_around_the_json_is_tolerated(self):
        assert parse_story(f"```json\n{GOOD}\n```")["title"] == "A Day"

    def test_whitespace_is_trimmed_and_length_is_capped(self):
        out = parse_story(json.dumps({"title": "  " + "t" * 500, "story": "s" * 9000 + "  "}))
        assert len(out["title"]) == MAX_TITLE and len(out["story"]) == MAX_STORY

    @pytest.mark.parametrize(
        "text",
        [None, "", "   ", "not json", "[1, 2]", '"a string"', '{"title": "t"}', '{"story": "s"}', '{"title": "", "story": "s"}',
         '{"title": 5, "story": "s"}', '{"title": "t", "story": ["a"]}', '{"title": "  ", "story": "s"}'],
    )  # fmt: skip
    def test_anything_else_is_an_error(self, text):
        with pytest.raises(StoryError):
            parse_story(text)


class TestGenerator:
    def make(self, **kw):
        client = FakeClient(**kw)
        return StoryGenerator(client, "vision-model", 321), client

    def test_the_request_has_the_prompt_the_photo_with_its_real_type_and_the_settings(self):
        generator, client = self.make(answer=reply(GOOD))
        result = generator.generate(b"\x89PNG-bytes", "image/png", Metadata(name="Max"))
        assert result == {"title": "A Day", "story": "It was golden."}
        call = client.calls[0]
        assert call["model"] == "vision-model" and call["max_completion_tokens"] == 321
        assert call["response_format"] == {"type": "json_object"}
        system, user = call["messages"]
        assert system == {"role": "system", "content": SYSTEM_PROMPT}
        text_part, image_part = user["content"]
        assert text_part["type"] == "text" and "Max" in text_part["text"]
        url = image_part["image_url"]["url"]
        assert url.startswith(
            "data:image/png;base64,"
        )  # the old code labelled everything image/jpeg

    @pytest.mark.parametrize("mime", ["image/jpeg", "image/webp"])
    def test_other_types_keep_their_type(self, mime):
        generator, client = self.make(answer=reply(GOOD))
        generator.generate(b"x", mime, Metadata())
        assert client.calls[0]["messages"][1]["content"][1]["image_url"]["url"].startswith(
            f"data:{mime};base64,"
        )

    def test_the_photo_is_sent_as_it_is(self):
        import base64

        generator, client = self.make(answer=reply(GOOD))
        generator.generate(b"\x00\x01\x02 raw", "image/png", Metadata())
        url = client.calls[0]["messages"][1]["content"][1]["image_url"]["url"]
        assert base64.b64decode(url.split(",", 1)[1]) == b"\x00\x01\x02 raw"

    def test_an_sdk_failure_becomes_a_story_error_carrying_only_the_error_type(self):
        generator, _ = self.make(error=RuntimeError("401 incorrect API key sk-demo-value-123"))
        with pytest.raises(StoryError) as caught:
            generator.generate(b"x", "image/png", Metadata())
        assert str(caught.value) == "RuntimeError" and "sk-demo" not in str(caught.value)

    @pytest.mark.parametrize(
        "answer", [reply(None), reply("not json"), types.SimpleNamespace(choices=[])]
    )
    def test_an_unusable_answer_is_a_story_error(self, answer):
        generator, _ = self.make(answer=answer)
        with pytest.raises(StoryError):
            generator.generate(b"x", "image/png", Metadata())
