import dataclasses
import inspect
import sqlite3
from collections.abc import Sequence
from typing import Any, TypeVar

from ._connection import get_connection
from ._utils import _coerce_row


@dataclasses.dataclass(frozen=True)
class RawResultRow:
    """Base class for raw SQL query result rows.

    Subclasses must be decorated with @dataclass(frozen=True):

        @dataclass(frozen=True)
        class AlbumCount(RawResultRow):
            ArtistId: int
            album_count: int

    Use __post_init__ for validation as you would with any frozen dataclass.
    """


T = TypeVar("T", bound=RawResultRow)


# ---------------------------------------------------------------------------
# Validation helpers for use in __post_init__
# ---------------------------------------------------------------------------


def require_int(value: object) -> None:
    """Raise TypeError if value is not an int."""
    if not isinstance(value, int):
        raise TypeError(f"expected int, got {type(value).__name__}")


def require_float(value: object) -> None:
    """Raise TypeError if value is not a float."""
    if not isinstance(value, float):
        raise TypeError(f"expected float, got {type(value).__name__}")


def require_str(value: object) -> None:
    """Raise TypeError if value is not a str."""
    if not isinstance(value, str):
        raise TypeError(f"expected str, got {type(value).__name__}")


def require_bytes(value: object) -> None:
    """Raise TypeError if value is not bytes."""
    if not isinstance(value, bytes):
        raise TypeError(f"expected bytes, got {type(value).__name__}")


def require_not_none(value: object) -> None:
    """Raise TypeError if value is None."""
    if value is None:
        raise TypeError("expected a value, got None")


def raw_query(
    sql: str,
    params: Sequence[Any] = (),
    *,
    result_type: type[T],
) -> tuple[T, ...]:
    """Execute a raw SQL SELECT and map rows to instances of result_type.

    Columns are matched to constructor parameters by name. Required parameters
    (those without defaults) must be present in the query result; extra columns
    are ignored. Validation is delegated to the constructor — use __post_init__
    to enforce constraints.

    Args:
        sql: Raw SQL string. Use ? placeholders for parameters.
        params: Positional query parameters bound to ? placeholders.
        result_type: A RawResultRow subclass describing the expected row shape.

    Returns:
        Tuple of result_type instances.

    Raises:
        ValueError: If any required constructor parameter is absent from the result columns.
        sqlite3.OperationalError: If the query fails, with the SQL appended for context.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(
            f"{exc}\n\nFailed query:\n  SQL: {sql}\n  Params: {list(params)}"
        ) from exc

    rows = cursor.fetchall()
    if not rows:
        return ()

    sig = inspect.signature(result_type)
    required = {
        name
        for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty
        and p.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    }
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    row_keys = set(rows[0].keys())
    missing = required - row_keys
    if missing:
        raise ValueError(
            f"Query result is missing required columns for"
            f" {result_type.__name__!r}: {sorted(missing)}"
        )

    accepted = row_keys if has_var_keyword else set(sig.parameters) & row_keys
    return tuple(
        result_type(**_coerce_row(result_type, {k: row[k] for k in accepted}))
        for row in rows
    )
