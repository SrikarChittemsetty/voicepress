# VoicePress

> A learning-focused, multi-user blogging MVP for writing, dictating, and publishing Markdown posts.

VoicePress is a Flask + SQLite blog platform where users can register, write public or private posts, save drafts, publish polished posts, and interact through comments, likes, and bookmarks.

## Project Status

**Learning MVP** — built to practice full-stack fundamentals and ship a coherent, end-to-end product.

## Tech Stack

- **Backend:** Python, Flask, SQLite
- **Frontend:** Jinja templates, vanilla JavaScript, CSS
- **Writing:** Markdown rendering with Bleach sanitization
- **Testing:** Pytest
- **Packaging:** `pyproject.toml` (Hatchling)

## Core Features

- User auth, profiles, and account settings
- Post editor with:
  - visibility (`public`/`private`)
  - status (`draft`/`published`)
  - tags, category, excerpt, cover image URL, slug
  - free browser dictation + local cleanup button
  - live Markdown preview
- Public discovery pages:
  - home (recent + popular)
  - authors directory
  - user blog pages
  - tag/category pages
- Social interactions:
  - comments
  - likes
  - bookmarks
- Writer dashboard:
  - stats and filters
  - recent activity
  - bookmarked posts
- Friendly error pages (`404`, `500`)

## Screenshots

Add screenshots to these paths and update as needed:

- `docs/screenshots/home.png`
- `docs/screenshots/dashboard.png`
- `docs/screenshots/editor-dictation.png`
- `docs/screenshots/post-detail.png`

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set your local secret key in `.env`:

```bash
SECRET_KEY=change-me
```

If `SECRET_KEY` is not set, VoicePress uses a development fallback key.

## Run Locally

```bash
python src/app.py
```

Open: `http://127.0.0.1:5000`

## Run Tests

```bash
pytest -q
```

Tests use a temporary SQLite database (`NEW_PROJECT_TEST_DB`) so the real `app.db` is not touched.

## Known Limitations

- Browser dictation depends on Web Speech API support and can vary by browser/device.
- Local cleanup is rule-based text cleanup, not AI grammar correction.
- SQLite is great for local MVP usage but not ideal for high-concurrency production traffic.
- `app.py` is intentionally monolithic for readability; larger growth would benefit from module splits.

## What I Learned

- How to build a multi-user Flask app with ownership checks and public/private safety rules.
- How to evolve schema safely with SQLite migration helpers.
- How to add frontend-only dictation/cleanup without paid APIs.
- How to write integration tests against a temporary DB for safe, repeatable verification.
- How product polish (copy, navigation, empty states, safety UX) meaningfully improves usability.

## Git / GitHub Workflow

1. Create a branch from `main`.
2. Make focused changes.
3. Run tests (`pytest -q`).
4. Commit with a clear message.
5. Open a pull request and request review.

## License

MIT. See [`LICENSE`](LICENSE).
