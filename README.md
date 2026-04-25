# VoicePress (Flask + SQLite)

VoicePress is a multi-user blogging MVP built with Flask and SQLite. Writers can register, manage profiles, draft with free browser dictation, save private drafts, and publish public posts with Markdown.

## What VoicePress Includes

- Account registration, login/logout, and profile pages
- Account settings (change password + destructive account deletion)
- Posts with title/body/excerpt/cover image/tags/category/slug
- Visibility (`public`/`private`) and status (`draft`/`published`)
- Markdown rendering for post detail pages
- Free browser dictation + local cleanup button in the editor
- Public discovery pages: home, authors, user blogs, tags, categories
- Social features: comments, likes, bookmarks
- Dashboard with stats, filters, recent activity, and bookmarks
- Friendly error pages (`404`, `500`)

## Quick Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set a local secret key in `.env` if you want:

```bash
SECRET_KEY=change-me
```

If `SECRET_KEY` is missing, VoicePress uses a development fallback secret.

## Run Locally

```bash
python src/app.py
```

Open: `http://127.0.0.1:5000`

## Run Tests

```bash
pytest -q
```

Tests use temporary SQLite files (`NEW_PROJECT_TEST_DB`) so your real `app.db` is untouched.

## Browser Dictation Limitations

Voice dictation uses the browser Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`):

- Free to use (no paid API key in this MVP)
- Browser/device support varies
- Accuracy varies by mic quality, noise, and browser implementation
- Local cleanup button is rule-based text cleanup, **not** AI grammar correction

## SQLite Notes (`app.db`)

- Local development database is `app.db` in project root
- `app.db` is ignored by git
- Existing DB files are migrated safely on startup for new columns

## Git/GitHub Workflow (simple)

1. Create a branch from `main`
2. Make focused changes
3. Run tests (`pytest -q`)
4. Commit with clear message
5. Open pull request and request review

## Deployment Notes (high-level)

For production later:

- Set a strong `SECRET_KEY` environment variable
- Use a proper WSGI server (gunicorn/uwsgi) behind a reverse proxy
- Move from SQLite to a managed DB if write concurrency grows
- Add centralized logging and monitoring
