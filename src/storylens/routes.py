import logging
import time

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from .images import InvalidImage, read_image
from .stories import Metadata, StoryError

logger = logging.getLogger(__name__)
bp = Blueprint("storylens", __name__)

LIMITS = {"name": 100, "date": 50, "note": 500}
LABELS = {"name": "Name", "date": "Date", "note": "Note"}


def _state():
    return current_app.extensions["storylens"]


def _json(payload, status=200, **headers):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"  # the content is private to the person who asked
    response.headers.update(headers)
    return response


def _metadata():
    values = {}
    for field, limit in LIMITS.items():
        value = request.form.get(field, "").strip()
        if len(value) > limit:
            raise ValueError(f"{LABELS[field]} is too long (at most {limit} characters).")
        values[field] = value
    return Metadata(**values)


@bp.get("/")
def index():
    return render_template("index.html", max_upload_mb=_state()["config"].max_upload_mb)


@bp.get("/healthz")
def healthz():
    return {"status": "ok"}


@bp.post("/generate-vision-story")
def generate_vision_story():
    """Photo and details in, ``{"title", "story"}`` out. The photo is read into memory, sent to OpenAI
    and dropped: it is never written to disk (the old code saved it to a temp file and deleted it after)."""
    state = _state()
    wait = state["limiter"].check(request.remote_addr or "unknown")
    if wait:
        return _json(
            {"error": "Too many requests. Please wait a moment."},
            429,
            **{"Retry-After": str(int(wait) + 1)},
        )
    generator = state["generator"]
    if generator is None:
        return _json({"error": "The story writer is not set up on this server."}, 503)

    photo = request.files.get("photo")
    if photo is None or not photo.filename:
        return _json({"error": "Choose a photo first."}, 400)
    try:
        meta = _metadata()
        image, mime = read_image(photo, state["config"].max_upload_bytes)
    except InvalidImage as error:
        status = 413 if "too large" in str(error) else 415
        return _json({"error": str(error)}, status)
    except ValueError as error:
        return _json({"error": str(error)}, 400)

    started = time.monotonic()
    try:
        result = generator.generate(image, mime, meta)
    except StoryError as error:
        # What failed goes to the log (without the photo or the story); the visitor gets a plain message.
        logger.error("Story generation failed: %s", error)
        return _json({"error": "The story could not be written right now. Please try again."}, 502)
    logger.info("Story written: %d bytes in, %.1fs", len(image), time.monotonic() - started)
    return _json(result)


@bp.app_errorhandler(413)
def too_large(_error):
    mb = _state()["config"].max_upload_mb
    return _json({"error": f"The photo is too large (at most {mb} MB)."}, 413)


@bp.app_errorhandler(HTTPException)
def http_error(error):
    # 404, 405 and the like, as JSON for the API route and the default page otherwise
    if request.path.startswith("/generate-vision-story"):
        return _json({"error": error.name}, error.code)
    return error


@bp.app_errorhandler(Exception)
def unexpected(error):
    # The old handler returned str(error) to the visitor.
    logger.exception("Unexpected error")
    return _json({"error": "Something went wrong."}, 500)
