"""Migration runner — apply pending SQL migrations to a SQLite database.

Usage:
    uv run python -m icemodel.migrate <db> [--migrations <dir>]
"""

if __name__ == "__main__":
    import argparse
    import sqlite3
    import sys

    from icemodel._migrations import migrate

    parser = argparse.ArgumentParser(
        description="Apply pending SQL migrations to a SQLite database."
    )
    parser.add_argument("db", help="Path to the SQLite database file.")
    parser.add_argument(
        "--migrations",
        default="migrations",
        metavar="DIR",
        help="Migrations directory (default: migrations/).",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        applied = migrate(conn, path=args.migrations)
    except (FileNotFoundError, ValueError, sqlite3.OperationalError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    if applied:
        for filename in applied:
            print(f"Applied: {filename}")
    else:
        print("Nothing to apply.")
