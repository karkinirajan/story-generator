# StoryLens

**Turn your favorite memories into timeless narratives.**

Upload a photo, say who is in it and when it was taken, and a vision model writes a short personal story about the moment. The photo is **not stored**: it is held in memory, sent to OpenAI to write the story, and dropped.

> `story-lens` is the same application, a later copy. Use one of the two repositories.

## How it works

1. The page (`/`) takes a JPEG, PNG or WebP photo (up to 10 MB), a name, a date and an optional note.
2. `POST /generate-vision-story` checks what the file really is (by content, not by name), reads it into memory and asks the model (`gpt-4o` by default) for `{"title", "story"}` in a warm, personal style.
3. The page shows the story. Errors are plain HTTP errors (`400`, `413`, `415`, `429`, `502`, `503`) with a short message.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13).

```bash
uv sync
cp .env.example .env              # set OPENAI_API_KEY
uv run flask --app storylens:create_app run --debug     # http://127.0.0.1:5000
```

Without `OPENAI_API_KEY` the page loads and the story endpoint answers `503`.

## Configuration

Environment variables or a local `.env`; an empty value counts as unset. [`.env.example`](./.env.example) lists them.

| Variable | Default | |
|---|---|---|
| `OPENAI_API_KEY` | none | Required to write stories |
| `OPENAI_MODEL` | `gpt-4o` | A vision-capable model your account can use |
| `OPENAI_TIMEOUT`, `MAX_COMPLETION_TOKENS` | `60`, `700` | |
| `MAX_UPLOAD_MB` | `10` | Largest photo accepted (`413` above it) |
| `RATE_LIMIT_PER_MINUTE` | `10` | Per client address; `0` turns it off. **Every story costs an OpenAI call and the page has no login**, so keep a limit on (and add one at your proxy) |
| `TRUSTED_PROXIES` | `0` | Number of reverse proxies in front (1 behind nginx), so the limit sees the real client address |
| `LOG_LEVEL` | `INFO` | |

## Privacy

- The photo never touches the disk: uploads are kept in memory (Werkzeug would otherwise spool anything over 500 KB to a temporary file), sent to OpenAI as a base64 image, and dropped when the request ends.
- Logs hold sizes and timings only: no photo, name, note or story.
- The page loads no third-party fonts, scripts or styles, and has a strict Content-Security-Policy.
- The photo and the details *are* sent to OpenAI to write the story (the page says so). Check OpenAI's data terms for your account.

## Project structure

```
src/storylens/
├── __init__.py    create_app(), in-memory uploads, security headers
├── config.py      settings
├── routes.py      /, /healthz, POST /generate-vision-story, error handlers
├── images.py      what an upload really is (PNG, JPEG, WebP signatures)
├── stories.py     the prompt, the OpenAI call, parsing the answer
├── ratelimit.py   per-client limit
├── templates/     index.html
└── static/        style.css, app.js
wsgi.py            gunicorn wsgi:app
tests/             pytest
```

## Testing

```bash
uv run pytest -q                       # 95 tests, 100% line coverage
uv run ruff check . && uv run ruff format --check .
```

## Deployment

```bash
docker build -t storylens .
docker run -p 8000:8000 -e OPENAI_API_KEY=... storylens
```

Non-root image, gunicorn with two workers of four threads, a health check on `/healthz`. Put TLS (and a request limit) in front. The rate limit is per worker process, so with several workers a limit at the proxy is the stronger one.

## Versions

[VERSIONS.md](./VERSIONS.md). What changed and what needs your attention: [work-done.md](./work-done.md).

## License

MIT, see [LICENSE](./LICENSE).
