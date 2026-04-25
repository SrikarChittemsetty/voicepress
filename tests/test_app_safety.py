"""
Integration tests for auth, publishing visibility, ownership, and account deletion.

Uses a temporary SQLite file via NEW_PROJECT_TEST_DB so the real app.db is never modified.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def app_bundle(tmp_path, monkeypatch):
    """Fresh Flask app + DB per test (reload app module so init_db runs on the temp file)."""
    db_path = tmp_path / "pytest_blog.sqlite"
    monkeypatch.setenv("NEW_PROJECT_TEST_DB", str(db_path))

    if "src.app" in sys.modules:
        importlib.reload(sys.modules["src.app"])
    import src.app as app_module

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
    """User can sign up and then log in; session reaches the dashboard."""
    c = app_bundle.client
    _register(c, "dana", "dana-secret-99")
    r = _login(c, "dana", "dana-secret-99")
    assert r.status_code == 200
    assert b"Dashboard" in r.data


def test_invalid_login_fails(app_bundle):
    """Wrong password does not create a session."""
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
    """Home feed only shows public published posts."""
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

    r_get = c.get(f"/posts/{post_id}/edit")
    assert r_get.status_code == 404


def test_deleted_account_removes_user_data_and_engagement(app_bundle):
    m = app_bundle.m
    c = app_bundle.client

    _register(c, "alice2", "alice2-pass-33")
    _register(c, "bob2", "bob2-pass-22")
    _login(c, "alice2", "alice2-pass-33")
    _new_post(c, "Post to delete", "Body text", "public", "published")
    posts = m.get_posts_for_user("alice2", "all")
    post_id = posts[0]["id"]
    row = m.get_public_post_by_id(post_id)
    assert row is not None
    slug = row["slug"]

    _login(c, "bob2", "bob2-pass-22")
    c.post(
        f"/posts/{slug}",
        data={"body": "Nice post!"},
        follow_redirects=True,
    )

    conn = m.get_db_connection()
    n_comments_before = conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]
    conn.close()
    assert n_comments_before >= 1

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
    bob_row = conn.execute("SELECT id FROM users WHERE username = ?", ("bob2",)).fetchone()
    conn.close()

    assert alice_row is None
    assert posts_left == 0
    assert comments_left == 0
    assert bob_row is not None


def test_change_password_keeps_session(app_bundle):
    c = app_bundle.client
    _register(c, "chris", "old-pass-00")
    _login(c, "chris", "old-pass-00")

    r = c.post(
        "/settings",
        data={
            "action": "change_password",
            "current_password": "old-pass-00",
            "new_password": "new-pass-11-long",
            "new_password_confirm": "new-pass-11-long",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"password was updated" in r.data.lower()

    dash = c.get("/dashboard")
    assert dash.status_code == 200

    c.post("/logout", follow_redirects=True)
    bad = _login(c, "chris", "old-pass-00")
    assert b"Invalid username or password" in bad.data
    good = _login(c, "chris", "new-pass-11-long")
    assert good.status_code == 200


def test_custom_404_page(app_bundle):
    r = app_bundle.client.get("/this-route-does-not-exist-xyz")
    assert r.status_code == 404
    assert b"Page not found" in r.data
    assert b"Back to home" in r.data
