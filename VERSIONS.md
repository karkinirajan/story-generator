# Versions

Read from `uv.lock` and the installed packages on 2026-11-02.

| Component | Version | Was | Where it is set |
|---|---|---|---|
| Python | 3.13 (3.13.18 here) | unpinned (the Dockerfile of the sibling repo used 3.9) | `.python-version`, `pyproject.toml`, `Dockerfile` |
| Flask | 3.1.3 | `>=3.0.0` | `pyproject.toml` (lower bound), `uv.lock` |
| Werkzeug | 3.1.9 | unpinned | |
| openai | 3.42.1 | `>=1.0.0` | |
| gunicorn | 26.2.0 | unpinned | |
| python-dotenv | 1.2.4 | unpinned | |
| pytest / pytest-cov (dev) | 9.2.0 / 7.1.0 | absent | |
| ruff (dev) | 0.17.3 | absent | |
| uv (in the image) | 0.13.6 | | `Dockerfile` |

34 packages are locked. The old `requirements.txt` listed 57 unpinned packages, most of them unused: `midjourney_api`, `aiohttp`, `starlette`, `uvicorn`, `typer`, `rich`, `orjson`, `ujson`, `uvloop`, `watchfiles`, `websockets`, `Flask-SQLAlchemy`, `SQLAlchemy`, `pydantic*`, `email-validator`, `dnspython`, `requests`, and a dozen more. The app uses Flask, the OpenAI SDK, gunicorn and python-dotenv.

The default model is `gpt-4o`, as before; whether it is still available to your account was not checked (it is a setting).

## Verified here

- 95 tests pass (100% of lines of `src/storylens`); ruff is clean.
- Production `gunicorn` with a local stand-in for OpenAI (the real SDK pointed at it): a real 3 MB PNG named `holiday.jpg` reaches OpenAI byte for byte with the type `image/png`; an HTML file named `cute.jpg` gets 415; an overlong name gets 400; the 11th request in a minute gets 429; and `TMPDIR` and the working directory stay empty. The server log holds sizes and timings only.
- The real page in Chromium (Electron): a file chosen, the form submitted through the page's own script, the story shown, no console errors or CSP violations; screenshots look right.
- The Docker image builds (342 MB, non-root) and its health check turns healthy.

## Not verified here

- A real OpenAI answer (a stand-in server was used), including whether `gpt-4o` is available to your account.
- A GitHub Actions run.
