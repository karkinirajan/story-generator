import logging
from io import BytesIO

from flask import Flask, Request
from openai import OpenAI
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .ratelimit import RateLimiter
from .routes import bp
from .stories import StoryGenerator

SECURITY_HEADERS = {
    # Nothing but this site's own files: no third-party fonts, scripts or styles.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class MemoryRequest(Request):
    """Werkzeug keeps an uploaded file over 500 KB in a temporary file on disk while it parses the form,
    which includes most phone photos. Here every upload stays in memory (its size is bounded by
    MAX_CONTENT_LENGTH), so a photo is never written to disk."""

    def _get_file_stream(
        self, total_content_length, content_type, filename=None, content_length=None
    ):
        return BytesIO()


def create_app(config: Config | None = None, generator=None) -> Flask:
    """``generator`` is injectable for tests; by default one is built from the OpenAI settings."""
    config = config or Config.from_env()
    app = Flask(__name__)
    app.request_class = MemoryRequest
    app.config["MAX_CONTENT_LENGTH"] = (
        config.max_upload_bytes + 64 * 1024
    )  # the photo plus the form fields
    if config.trusted_proxies:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=config.trusted_proxies, x_proto=config.trusted_proxies
        )

    if generator is None and config.openai_api_key:
        client = OpenAI(api_key=config.openai_api_key, timeout=config.openai_timeout)
        generator = StoryGenerator(client, config.openai_model, config.max_completion_tokens)
    app.extensions["storylens"] = {
        "config": config,
        "generator": generator,
        "limiter": RateLimiter(config.rate_limit_per_minute),
    }

    @app.after_request
    def add_headers(response):
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    app.register_blueprint(bp)
    logging.getLogger(__name__).info(
        "StoryLens ready (model %s, generator %s)",
        config.openai_model,
        "on" if generator else "NOT configured",
    )
    return app
