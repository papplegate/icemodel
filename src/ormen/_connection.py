import sqlite3

# Mutable container avoids a module-level `global` statement.
_state: dict[str, sqlite3.Connection] = {}


def set_connection(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    _state["conn"] = conn


def get_connection() -> sqlite3.Connection:
    try:
        return _state["conn"]
    except KeyError as exc:
        raise RuntimeError("No database connection. Call Model.bind(conn) first.") from exc
