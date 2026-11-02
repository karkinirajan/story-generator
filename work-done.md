# Work done: story-generator

Branch: `chore/modernize` (local, not pushed). Date: 2026-11-02.

## The same application lives in two repositories
`story-lens` is a later copy of this project (3 more commits, "keeping improved local version"). The code differs by a few lines (a duplicate line removed, `print` replaced by logging, a fixed `run.py`, a shorter `requirements.txt`, and a Dockerfile). Both are modernized with the same package so that either is usable, but you only need one: **I would keep `story-lens` and archive this one.**

## What was there
A small Flask app (about 215 lines of Python and a 385-line page): upload a photo, send it to GPT-4o Vision, show the story. 22 tracked files, among them an IDE folder (`.idea/`, 5 files), `.vscode/settings.json` and a SQLite `database.db` (one empty table, `story_data`, left from an earlier Tripetto/DALL-E version). No tests. A `requirements.txt` of 57 unpinned packages, most unused. A README that mentions a `redundants/` folder that does not exist.

## Problems found and fixed
| Problem | Fix |
|---|---|
| `python run.py` (the documented way to run it) failed at once: `ImportError: cannot import name 'db' from 'app.main'` (verified on the old code) | One entry point: `uv run flask --app storylens:create_app run`, and `wsgi.py` for gunicorn |
| `app.run(debug=True)`: the Werkzeug debugger on a public app | Debug is only on when you ask for it (`--debug`) |
| **The "delete immediately" promise was weaker than it sounded.** The photo was saved to a temp file and deleted after the request, and Werkzeug additionally spools any upload over 500 KB to its own temporary file. Typical phone photos were written to disk twice | Uploads are kept in memory only (a `Request` subclass, bounded by the size limit). A test makes any temporary-file creation fail while a 3 MB photo is uploaded, and the end-to-end run confirms the temp folder and working directory stay empty |
| The full generated story (derived from a private photo, with names) was logged at INFO | Logs hold sizes and timings only (checked in a real server log) |
| The page said "Privacy First", "deleted immediately", but did not say the photo and details are **sent to OpenAI**; it also loaded fonts from Google | The page states it; no third-party fonts or scripts; a strict Content-Security-Policy |
| The file type was decided by its **name**; every image was then sent to OpenAI labelled `image/jpeg`. No size limit | The type is read from the content (PNG, JPEG, WebP signatures; `415` otherwise), the real type is sent, `MAX_UPLOAD_MB` (413) |
| A model failure was answered with HTTP 200 and a story titled "Error"; unexpected errors returned `str(e)` to the visitor | `502` / `503` / `500` with a short message; details go to the log |
| Anyone who could reach the page could make the server spend OpenAI money, at any rate | Per-client rate limit (429 with `Retry-After`), `TRUSTED_PROXIES` for the real client address |
| `name`, `date` and `note` were unlimited free text | 100, 50 and 500 characters; the details are marked as data in the prompt |
| Inline `<style>`, `<script>` and `onclick` | Moved to `static/style.css` and `static/app.js`; errors show inline instead of `alert()` |
| 57 unpinned dependencies; `database.db`, `.idea/`, `.vscode/` tracked | `pyproject.toml` + `uv.lock` (34 packages); the IDE files and the database are untracked and ignored |
| The model name hard-coded | `OPENAI_MODEL` (default `gpt-4o`, as before), plus a timeout and a token limit |

The author's prompt text is unchanged.

## Changes by file
| Path | Change |
|---|---|
| `app/main.py`, `app/services/vision_service.py`, `app/utils/file_handler.py`, `run.py` | replaced by `src/storylens/` (`__init__`, `config`, `routes`, `images`, `stories`, `ratelimit`) and `wsgi.py`; the temp-file handler is gone |
| `app/templates/index.html` | `src/storylens/templates/index.html` + `static/style.css` + `static/app.js` |
| `requirements.txt` | `pyproject.toml`, `uv.lock`, `.python-version` |
| `database.db`, `.idea/`, `.vscode/` | untracked |
| `tests/` | 95 tests |
| `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`, `.env.example` | new |
| `README.md`, `VERSIONS.md`, `work-done.md` | written to match the code |

## Verification (actual runs)
- `uv run pytest`: **95 passed**, 100% line coverage of `src/storylens`; `ruff check` and `ruff format --check` clean.
- Mutation checks (the defect put back, the suite must fail), 20, all caught: uploads spooled to disk again, any bytes accepted as an image, every image labelled jpeg, size limit not enforced, a model failure answered 200, error text returned to the visitor, answers cacheable, rate limit not applied, the story logged, details unlimited, security headers dropped, a permissive CSP, the photo sent without its real type, SDK error text carried on, a blank title or story accepted, refused calls extending the wait, Google Fonts back, the OpenAI disclosure removed, and a typo in `.env.example`.
- Two things the end-to-end run found in my own work and fixed: INFO logging was not configured under gunicorn, so my first "nothing private is logged" check passed trivially (it now shows 9 log lines and none contains a name, note or story); and my first attempt at a test regex missed line-wrapped calls.
- The real server, the real page in Chromium and the Docker image: see VERSIONS.md.
- A count-only secret scan of the history (67 commits): no OpenAI-shaped keys, private keys or URLs with passwords.
- **Not verified:** a real OpenAI answer; that `gpt-4o` is available to your account; a GitHub Actions run.

## Needs your attention
- **Set `OPENAI_API_KEY`** (and `OPENAI_MODEL` if `gpt-4o` is not right for you). If a key was ever pasted into a `.env` that was shared, rotate it; none is in the repository or its history.
- **Keep the rate limit on, and add one at your proxy.** The page has no login and each story is a paid call. The built-in limit is per worker process.
- The page now tells visitors their photo is sent to OpenAI. Check that this matches your privacy policy and OpenAI's data terms for your account.
- A photo from a phone in HEIC format is refused (`415`); the page asks for JPEG, PNG or WebP, as the old code allowed.
- The stylesheet now uses system fonts instead of Inter and Playfair Display (so no request goes to Google).
- Nothing pushed. To publish: `git push -u origin chore/modernize`
