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

## Demo Preview

Screenshots are being refreshed and will be added soon.

For now, the fastest way to evaluate VoicePress is the local demo flow below.

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

## 5-Minute Local Demo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python src/app.py
```

Then:

1. Open `http://127.0.0.1:5000`
2. Create an account from **Register**
3. Log in and open **Create Post**
4. Create a post with:
   - title and body
   - `visibility = public`
   - `status = published`
5. Save the post and verify it appears on the public home feed
6. Optionally test comments, likes, and bookmarks from another account

## Run Tests

```bash
pytest -q
```

Tests use a temporary SQLite database (`NEW_PROJECT_TEST_DB`) so the real `app.db` is not touched.

## Persistent storage on Render

Render’s **free** filesystem is **ephemeral**: redeploys and restarts can wipe files that are not on a [persistent disk](https://render.com/docs/disks). VoicePress keeps using SQLite, but you should put `app.db` on a disk that survives those events.

1. In the Render dashboard, open your **Web Service** → **Disks** → add a **persistent disk**.
2. Mount it to a path such as **`/var/data`** (create this mount path in the UI; it must exist on the instance for the mount).
3. Set an environment variable so VoicePress writes the database **on that disk** (the file path’s parent should match the mount):

   ```bash
   DATABASE_PATH=/var/data/app.db
   ```

   The mount path (e.g. `/var/data`) must be the **parent directory** of the database file (`app.db` lives inside the mounted folder).

4. Redeploy. On first boot, VoicePress creates missing parent directories and opens SQLite at `DATABASE_PATH`.

**Path priority:** `NEW_PROJECT_TEST_DB` (tests only) overrides everything, then `DATABASE_PATH`, then the default `app.db` next to the project root.

## Configuration and Security Notes

- Set `SECRET_KEY` in production. The fallback key is only for local development convenience.
- SQLite works well for local/dev usage. Hosted deployment should use persistent storage to keep post data durable across restarts.
- VoicePress is an evolving personal publishing tool, currently optimized for learning, iteration, and product polish.

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
