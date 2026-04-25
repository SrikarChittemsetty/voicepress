"""
Integration tests for auth, publishing safety, ownership, and account lifecycle.

Each test points the app at a temporary SQLite file via NEW_PROJECT_TEST_DB,
so the real local app.db is never modified.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

APP_FILE = Path(__file__).resolve().parents[1] / "src" / "app.py"
MODULE_NAME = "voicepress_app_under_test"


def load_app_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, APP_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def app_bundle(tmp_path, monkeypatch):
    """Fresh Flask app module + DB file per test."""
    db_path = tmp_path / "pytest_voicepress.sqlite"
    monkeypatch.setenv("NEW_PROJECT_TEST_DB", str(db_path))

    app_module = load_app_module()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield type("Bundle", (), {"client": client, "app": app_module.app, "m": app_module})()


def _register(client, username: str, password: str) -> None:
    client.post(
        "/register/submit",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def _login(client, username: str, password: str):
    return client.post(
        "/login/submit",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def _new_post(client, title: str, body: str, visibility: str, status: str) -> None:
    client.post(
        "/posts/new",
        data={
            "title": title,
            "body": body,
            "excerpt": "",
            "cover_image_url": "",
            "tags": "",
            "category": "",
            "visibility": visibility,
            "status": status,
        },
        follow_redirects=True,
    )


def test_register_login_persists(app_bundle):
    c = app_bundle.client
    _register(c, "dana", "dana-secret-99")
    r = _login(c, "dana", "dana-secret-99")
    assert r.status_code == 200
    assert b"Writer Control Center" in r.data


def test_invalid_login_fails(app_bundle):
    c = app_bundle.client
    _register(c, "eli", "eli-correct-pass-88")
    r = c.post(
        "/login/submit",
        data={"username": "eli", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"Invalid username or password" in r.data


def test_private_and_draft_posts_not_public(app_bundle):
    c = app_bundle.client
    _register(c, "frank", "frank-pass-77")
    _login(c, "frank", "frank-pass-77")
    _new_post(c, "Secret draft", "Body A", "public", "draft")
    _new_post(c, "Private live", "Body B", "private", "published")

    home = c.get("/")
    assert home.status_code == 200
    assert b"Secret draft" not in home.data
    assert b"Private live" not in home.data


def test_public_published_post_appears_on_home(app_bundle):
    c = app_bundle.client
    _register(c, "gina", "gina-pass-66")
    _login(c, "gina", "gina-pass-66")
    _new_post(c, "Hello world public", "Some **markdown** here.", "public", "published")

    home = c.get("/")
    assert home.status_code == 200
    assert b"Hello world public" in home.data


def test_non_owner_cannot_edit_another_users_post(app_bundle):
    m = app_bundle.m
    c = app_bundle.client
    _register(c, "alice", "alice-pass-55")
    _register(c, "bob", "bob-pass-44")
    _login(c, "alice", "alice-pass-55")
    _new_post(c, "Alice only", "Content", "public", "published")

    posts = m.get_posts_for_user("alice", "all")
    assert len(posts) == 1
    post_id = posts[0]["id"]

    _login(c, "bob", "bob-pass-44")
    r_edit = c.post(
        f"/posts/{post_id}/edit",
        data={
            "title": "Hacked title",
            "body": "Hacked body",
            "excerpt": "",
            "cover_image_url": "",
            "tags": "",
            "category": "",
            "visibility": "public",
            "status": "published",
        },
    )
    assert r_edit.status_code == 404
    assert c.get(f"/posts/{post_id}/edit").status_code == 404


def test_comments_likes_and_bookmarks_basics(app_bundle):
    m = app_bundle.m
    c = app_bundle.client

    _register(c, "writer", "writer-pass")
    _register(c, "reader", "reader-pass")

    _login(c, "writer", "writer-pass")
    _new_post(c, "Public Post", "Body here", "public", "published")

    post = m.get_public_posts("Public Post")[0]
    post_id = post["id"]
    slug = post["slug"]

    _login(c, "reader", "reader-pass")
    c.post(f"/posts/{post_id}/like", follow_redirects=True)
    c.post(f"/posts/{post_id}/bookmark", follow_redirects=True)
    c.post(f"/posts/{slug}", data={"body": "Nice write-up"}, follow_redirects=True)

    detail = m.get_public_post_by_slug(slug)
    comments = m.get_comments_for_post(post_id)
    assert detail["like_count"] == 1
    assert len(comments) == 1

    bookmarks = m.get_bookmarked_posts_for_user("reader")
    assert len(bookmarks) == 1


def test_deleted_account_removes_user_data_and_engagement(app_bundle):
    m = app_bundle.m
    c = app_bundle.client

    _register(c, "alice2", "alice2-pass-33")
    _register(c, "bob2", "bob2-pass-22")
    _login(c, "alice2", "alice2-pass-33")
    _new_post(c, "Post to delete", "Body text", "public", "published")
    post_id = m.get_posts_for_user("alice2", "all")[0]["id"]
    slug = m.get_public_post_by_id(post_id)["slug"]

    _login(c, "bob2", "bob2-pass-22")
    c.post(f"/posts/{slug}", data={"body": "Nice post!"}, follow_redirects=True)
    c.post(f"/posts/{post_id}/like", follow_redirects=True)
    c.post(f"/posts/{post_id}/bookmark", follow_redirects=True)

    _login(c, "alice2", "alice2-pass-33")
    r_del = c.post(
        "/settings",
        data={"action": "delete_account", "confirm_username": "alice2"},
        follow_redirects=True,
    )
    assert r_del.status_code == 200

    conn = m.get_db_connection()
    alice_row = conn.execute("SELECT id FROM users WHERE username = ?", ("alice2",)).fetchone()
    posts_left = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
    comments_left = conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]
    likes_left = conn.execute("SELECT COUNT(*) AS n FROM likes").fetchone()["n"]
    bookmarks_left = conn.execute("SELECT COUNT(*) AS n FROM bookmarks").fetchone()["n"]
    bob_row = conn.execute("SELECT id FROM users WHERE username = ?", ("bob2",)).fetchone()
    conn.close()

    assert alice_row is None
    assert posts_left == 0
    assert comments_left == 0
    assert likes_left == 0
    assert bookmarks_left == 0
    assert bob_row is not None


def test_change_password_without_min_length_still_works(app_bundle):
    c = app_bundle.client
    _register(c, "chris", "old-pass-00")
    _login(c, "chris", "old-pass-00")

    r = c.post(
        "/settings",
        data={
            "action": "change_password",
            "current_password": "old-pass-00",
            "new_password": "x",
            "new_password_confirm": "x",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"password was updated" in r.data.lower()

    dashboard = c.get("/dashboard")
    assert dashboard.status_code == 200

    c.post("/logout", follow_redirects=True)
    assert b"Invalid username or password" in _login(c, "chris", "old-pass-00").data
    assert _login(c, "chris", "x").status_code == 200


def test_custom_404_page(app_bundle):
    r = app_bundle.client.get("/this-route-does-not-exist-xyz")
    assert r.status_code == 404
    assert b"Page not found" in r.data
    assert b"Back to home" in r.data


def test_secret_key_fallback_when_env_not_set(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_PROJECT_TEST_DB", str(tmp_path / "db.sqlite"))
    monkeypatch.delenv("SECRET_KEY", raising=False)

    app_module = load_app_module()
    assert app_module.app.secret_key == "dev-only-change-me"
