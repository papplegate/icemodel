"""Tests for the migration runner."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest

from icemodel._migrations import _collect, _parse_sequence, migrate


@pytest.fixture
def db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    d = tmp_path / "migrations"
    d.mkdir()
    return d


class TestParseSequence:
    def test_plain_integer(self) -> None:
        assert _parse_sequence("1_add_users.sql") == 1

    def test_multi_digit(self) -> None:
        assert _parse_sequence("42_add_index.sql") == 42

    def test_date_prefix(self) -> None:
        assert _parse_sequence("20260531_initial.sql") == 20260531

    def test_no_leading_integer_raises(self) -> None:
        with pytest.raises(ValueError, match="must start with an integer"):
            _parse_sequence("add_users.sql")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="must start with an integer"):
            _parse_sequence("_add_users.sql")


class TestCollect:
    def test_returns_sorted_by_sequence(self, migrations_dir: Path) -> None:
        (migrations_dir / "10_second.sql").write_text("SELECT 1;")
        (migrations_dir / "2_first.sql").write_text("SELECT 1;")
        result = _collect(migrations_dir)
        assert [m.filename for m in result] == ["2_first.sql", "10_second.sql"]

    def test_same_sequence_sorted_by_name(self, migrations_dir: Path) -> None:
        (migrations_dir / "1_b.sql").write_text("SELECT 1;")
        (migrations_dir / "1_a.sql").write_text("SELECT 1;")
        result = _collect(migrations_dir)
        assert [m.filename for m in result] == ["1_a.sql", "1_b.sql"]

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            _collect(tmp_path / "nonexistent")

    def test_invalid_filename_raises(self, migrations_dir: Path) -> None:
        (migrations_dir / "no_prefix.sql").write_text("SELECT 1;")
        with pytest.raises(ValueError, match="must start with an integer"):
            _collect(migrations_dir)

    def test_ignores_non_sql_files(self, migrations_dir: Path) -> None:
        (migrations_dir / "1_initial.sql").write_text("SELECT 1;")
        (migrations_dir / "README.md").write_text("notes")
        result = _collect(migrations_dir)
        assert len(result) == 1


class TestMigrate:
    def test_creates_migrations_table(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        migrate(db, path=migrations_dir)
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
        ).fetchone()
        assert row is not None

    def test_applies_pending_migration(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "1_initial.sql").write_text(
            "CREATE TABLE Foo (id INTEGER PRIMARY KEY);"
        )
        applied = migrate(db, path=migrations_dir)
        assert applied == ["1_initial.sql"]
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Foo'"
        ).fetchone()
        assert row is not None

    def test_records_applied_migration(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "1_initial.sql").write_text("SELECT 1;")
        migrate(db, path=migrations_dir)
        row = db.execute(
            "SELECT filename FROM _migrations WHERE filename = '1_initial.sql'"
        ).fetchone()
        assert row is not None

    def test_skips_already_applied(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "1_initial.sql").write_text("SELECT 1;")
        migrate(db, path=migrations_dir)
        applied = migrate(db, path=migrations_dir)
        assert applied == []

    def test_applies_only_pending(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "1_initial.sql").write_text("SELECT 1;")
        migrate(db, path=migrations_dir)
        (migrations_dir / "2_second.sql").write_text("SELECT 1;")
        applied = migrate(db, path=migrations_dir)
        assert applied == ["2_second.sql"]

    def test_applies_in_sequence_order(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "2_second.sql").write_text(
            "CREATE TABLE Bar (id INTEGER PRIMARY KEY);"
        )
        (migrations_dir / "1_first.sql").write_text(
            "CREATE TABLE Foo (id INTEGER PRIMARY KEY);"
        )
        applied = migrate(db, path=migrations_dir)
        assert applied == ["1_first.sql", "2_second.sql"]

    def test_nothing_to_apply_returns_empty(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        applied = migrate(db, path=migrations_dir)
        assert applied == []

    def test_failed_migration_raises(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "1_bad.sql").write_text("NOT VALID SQL;")
        with pytest.raises(sqlite3.OperationalError, match="1_bad.sql"):
            migrate(db, path=migrations_dir)

    def test_failed_migration_not_recorded(
        self, db: sqlite3.Connection, migrations_dir: Path
    ) -> None:
        (migrations_dir / "1_bad.sql").write_text("NOT VALID SQL;")
        with pytest.raises(sqlite3.OperationalError):
            migrate(db, path=migrations_dir)
        row = db.execute(
            "SELECT filename FROM _migrations WHERE filename = '1_bad.sql'"
        ).fetchone()
        assert row is None

    def test_missing_directory_raises(self, db: sqlite3.Connection) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            migrate(db, path="nonexistent_dir")
