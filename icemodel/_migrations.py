import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    filename  TEXT NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


@dataclass(frozen=True)
class _Migration:
    sequence: int
    filename: str
    path: Path


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_TABLE)
    conn.commit()


def _applied(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT filename FROM _migrations")}


def _parse_sequence(filename: str) -> int:
    """Extract and return the leading integer from a migration filename."""
    match = re.match(r"^(\d+)", filename)
    if not match:
        raise ValueError(f"Migration filename must start with an integer: {filename!r}")
    return int(match.group(1))


def _collect(migrations_dir: Path) -> list[_Migration]:
    """Return all .sql migrations in the directory, sorted by sequence then name."""
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")
    migrations = []
    for p in migrations_dir.glob("*.sql"):
        seq = _parse_sequence(p.name)
        migrations.append(_Migration(seq, p.name, p))
    return sorted(migrations, key=lambda m: (m.sequence, m.filename))


def migrate(conn: sqlite3.Connection, path: str | Path = "migrations") -> list[str]:
    """Apply pending migrations from a directory of numbered SQL files.

    Migration filenames must start with an integer that determines application
    order. Files already recorded in the _migrations table are skipped.

    Args:
        conn: SQLite connection.
        path: Path to the migrations directory. Defaults to "migrations".

    Returns:
        List of filenames applied in this call, in order.

    Raises:
        FileNotFoundError: If the migrations directory does not exist.
        ValueError: If any migration filename does not start with an integer.
        sqlite3.OperationalError: If a migration fails, with the filename and
            original error appended for context.
    """
    migrations_dir = Path(path)
    _ensure_table(conn)
    applied = _applied(conn)
    pending = [m for m in _collect(migrations_dir) if m.filename not in applied]

    applied_now: list[str] = []
    for migration in pending:
        sql = migration.path.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
        except sqlite3.Error as exc:
            raise sqlite3.OperationalError(
                f"Migration {migration.filename!r} failed: {exc}"
            ) from exc
        conn.execute(
            "INSERT INTO _migrations (filename) VALUES (?)",
            [migration.filename],
        )
        conn.commit()
        applied_now.append(migration.filename)

    return applied_now
