import sqlite3

# Mutable container avoids a module-level `global` statement.
_state: dict[str, sqlite3.Connection | bool] = {}


def connect(conn: sqlite3.Connection) -> None:
    """Register a SQLite connection for use by all query paths."""
    conn.row_factory = sqlite3.Row
    _state["conn"] = conn


def get_connection() -> sqlite3.Connection:
    try:
        conn = _state["conn"]
        if isinstance(conn, sqlite3.Connection):
            return conn
        raise RuntimeError("No database connection. Call connect(conn) first.")
    except KeyError as exc:
        raise RuntimeError("No database connection. Call connect(conn) first.") from exc


def set_transaction_context(value: bool) -> None:
    """Track whether we're inside a transaction context manager."""
    _state["in_transaction_context"] = value


def in_transaction_context() -> bool:
    """Check if we're inside a transaction context manager."""
    return bool(_state.get("in_transaction_context", False))
