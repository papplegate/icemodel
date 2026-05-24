from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from ._utils import from_row

if TYPE_CHECKING:
    from ._model import Model

_VALID_OPS: frozenset[str] = frozenset(
    {"=", "!=", "<>", "<", ">", "<=", ">=", "LIKE", "NOT LIKE", "IS", "IS NOT"}
)

_MISSING: object = object()

T = TypeVar("T", bound="Model")


def _check_op(op: str) -> str:
    upper = op.upper()
    if upper not in _VALID_OPS:
        raise ValueError(f"Invalid operator {op!r}. Allowed: {sorted(_VALID_OPS)}")
    return upper


class QueryBuilder(Generic[T]):  # pylint: disable=too-many-instance-attributes
    def __init__(
        self, model_class: type[T], table: str, conn: sqlite3.Connection
    ) -> None:
        self._model_class = model_class
        self._table = table
        self._conn = conn
        self._selects: list[str] = ["*"]
        self._wheres: list[tuple[str, str, Any]] = []
        self._order_bys: list[tuple[str, str]] = []
        self._limit_val: int | None = None
        self._offset_val: int | None = None
        self._eager: list[str] = []

    # ------------------------------------------------------------------ #
    # Fluent API                                                           #
    # ------------------------------------------------------------------ #

    def select(self, *columns: str) -> QueryBuilder[T]:
        self._selects = list(columns)
        return self

    def where(
        self,
        column: str,
        op_or_value: Any,
        value: Any = _MISSING,
    ) -> QueryBuilder[T]:
        if value is _MISSING:
            self._wheres.append((column, "=", op_or_value))
        else:
            self._wheres.append((column, _check_op(str(op_or_value)), value))
        return self

    def where_in(self, column: str, values: list[Any]) -> QueryBuilder[T]:
        if not values:
            self._wheres.append(("1", "=", 0))  # always-false: WHERE 1 = 0
        else:
            self._wheres.append((column, "__IN__", values))
        return self

    def order_by(self, column: str, direction: str = "ASC") -> QueryBuilder[T]:
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"direction must be 'ASC' or 'DESC', got {direction!r}")
        self._order_bys.append((column, direction))
        return self

    def limit(self, n: int) -> QueryBuilder[T]:
        self._limit_val = n
        return self

    def offset(self, n: int) -> QueryBuilder[T]:
        self._offset_val = n
        return self

    def with_related(self, *names: str) -> QueryBuilder[T]:
        self._eager.extend(names)
        return self

    # ------------------------------------------------------------------ #
    # Execution                                                            #
    # ------------------------------------------------------------------ #

    def all(self) -> list[T]:
        sql, params = self._build_select()
        rows = self._conn.execute(sql, params).fetchall()
        results: list[T] = [cast(T, from_row(self._model_class, r)) for r in rows]
        if self._eager:
            self._load_eager(results)
        return results

    def first(self) -> T | None:
        sql, params = self._build_select(force_limit=1)
        row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return None
        result: T = cast(T, from_row(self._model_class, row))
        if self._eager:
            self._load_eager([result])
        return result

    def find_by_id(self, id_val: Any) -> T | None:
        id_col = self._model_class._meta.get("id_column", "id")  # pylint: disable=protected-access
        return self.where(id_col, id_val).first()

    def count(self) -> int:
        saved = self._selects
        self._selects = ["COUNT(*) AS n"]
        sql, params = self._build_select()
        self._selects = saved
        row = self._conn.execute(sql, params).fetchone()
        return int(row["n"])

    def insert(self, data: dict[str, Any]) -> T:
        if not data:
            raise ValueError("insert() requires at least one column.")
        cols = ", ".join(data.keys())
        ph = ", ".join("?" * len(data))
        cursor = self._conn.execute(
            f"INSERT INTO {self._table} ({cols}) VALUES ({ph})",
            list(data.values()),
        )
        self._conn.commit()
        result = QueryBuilder(self._model_class, self._table, self._conn).find_by_id(
            cursor.lastrowid
        )
        assert result is not None, "Inserted row could not be fetched."
        return result

    def patch(self, data: dict[str, Any]) -> int:
        if not data:
            raise ValueError("patch() requires at least one column.")
        set_sql = ", ".join(f"{k} = ?" for k in data.keys())
        where_sql, where_params = self._build_where()
        sql = f"UPDATE {self._table} SET {set_sql}{where_sql}"
        cursor = self._conn.execute(sql, list(data.values()) + where_params)
        self._conn.commit()
        return cursor.rowcount

    def delete(self) -> int:
        where_sql, where_params = self._build_where()
        cursor = self._conn.execute(
            f"DELETE FROM {self._table}{where_sql}", where_params
        )
        self._conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _build_where(self) -> tuple[str, list[Any]]:
        if not self._wheres:
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for col, op, val in self._wheres:
            if op == "__IN__":
                ph = ",".join("?" * len(val))
                clauses.append(f"{col} IN ({ph})")
                params.extend(val)
            else:
                clauses.append(f"{col} {op} ?")
                params.append(val)
        return " WHERE " + " AND ".join(clauses), params

    def _build_select(self, force_limit: int | None = None) -> tuple[str, list[Any]]:
        cols = ", ".join(self._selects)
        sql = f"SELECT {cols} FROM {self._table}"
        where_sql, params = self._build_where()
        sql += where_sql
        if self._order_bys:
            order = ", ".join(f"{c} {d}" for c, d in self._order_bys)
            sql += f" ORDER BY {order}"
        effective_limit = force_limit if force_limit is not None else self._limit_val
        if effective_limit is not None:
            sql += f" LIMIT {effective_limit}"
        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"
        return sql, params

    def _load_eager(self, instances: list[T]) -> None:
        relations: dict[str, Any] = getattr(self._model_class, "__relations__", {})
        for name in self._eager:
            if name not in relations:
                raise AttributeError(
                    f"{self._model_class.__name__!r} has no relation {name!r}."
                )
            relations[name].load_for(instances, self._conn)
