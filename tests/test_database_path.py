"""Tests for configurable SQLite path (DATABASE_PATH, NEW_PROJECT_TEST_DB)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

APP_FILE = Path(__file__).resolve().parents[1] / "src" / "app.py"
MODULE_NAME = "voicepress_app_database_path_test"


def load_app_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, APP_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def test_new_project_test_db_overrides_database_path(tmp_path, monkeypatch):
    """NEW_PROJECT_TEST_DB wins even when DATABASE_PATH is set."""
    test_db = tmp_path / "pytest_only.sqlite"
    other_db = tmp_path / "should_not_be_used.sqlite"
    monkeypatch.setenv("NEW_PROJECT_TEST_DB", str(test_db))
    monkeypatch.setenv("DATABASE_PATH", str(other_db))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    m = load_app_module()
    assert m.get_database_path() == test_db.resolve()


def test_database_path_used_and_creates_parent_dirs(tmp_path, monkeypatch):
    """When NEW_PROJECT_TEST_DB is unset, DATABASE_PATH is used and parent dirs are created."""
    monkeypatch.delenv("NEW_PROJECT_TEST_DB", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = tmp_path / "disk" / "nested" / "app.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))

    m = load_app_module()
    assert m.get_database_path() == db_file.resolve()
    assert db_file.exists(), "init_db on import should create the SQLite file"


def test_new_project_test_db_keeps_tests_on_sqlite_even_with_database_url(tmp_path, monkeypatch):
    """Tests must never hit a real hosted database by accident."""
    test_db = tmp_path / "pytest_only.sqlite"
    monkeypatch.setenv("NEW_PROJECT_TEST_DB", str(test_db))
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/voicepress")

    m = load_app_module()
    assert m.uses_postgres() is False
    assert m.get_database_path() == test_db.resolve()


def test_database_path_keeps_sqlite_even_with_database_url(tmp_path, monkeypatch):
    """Explicit DATABASE_PATH should keep SQLite selected on hosts that inject DATABASE_URL."""
    db_file = tmp_path / "persistent" / "app.db"
    monkeypatch.delenv("NEW_PROJECT_TEST_DB", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/voicepress")

    m = load_app_module()
    assert m.uses_postgres() is False
    assert m.get_database_path() == db_file.resolve()
    assert db_file.exists()


def test_postgres_sql_translation(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NEW_PROJECT_TEST_DB", str(tmp_path / "translation.sqlite"))
    m = load_app_module()

    translated = m.prepare_sql_for_postgres(
        "SELECT * FROM users WHERE username = ? ORDER BY username COLLATE NOCASE"
    )

    assert translated == "SELECT * FROM users WHERE username = %s ORDER BY username"
