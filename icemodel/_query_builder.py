from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from ._connection import in_transaction_context
from ._utils import from_row, validate_model, validate_fields

if TYPE_CHECKING:
    from ._model import Model

_MISSING: object = object()

T = TypeVar("T", bound="Model")


def _unwrap_column(column: Enum) -> str:
    """Extract column name from enum member."""
    return str(column.value)


def _column_to_enum(model_class: type[Any], column: str) -> Enum:
    """Convert column name string to the corresponding Fields enum member."""
    fields_enum: Any = model_class.Fields
    for member in fields_enum:
        if member.value == column:
            return member  # type: ignore[no-any-return]
    raise ValueError(f"No field found for column {column!r} in {model_class.__name__}")


class Operator(Enum):
    """SQL comparison operators."""

    EQUAL = "="
    NOT_EQUAL = "!="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IS = "IS"
    IS_NOT = "IS NOT"


class Direction(Enum):
    """SQL ORDER BY directions."""

    ASCENDING = "ASC"
    DESCENDING = "DESC"


class QueryBuilder(Generic[T]):  # pylint: disable=too-many-instance-attributes
    def __init__(
        self, model_class: type[T], table: str, conn: sqlite3.Connection
    ) -> None:
        self._model_class = model_class
        self._table = table
        self._conn = conn
        self._selects: list[str] | None = None
        self._wheres: list[tuple[str, str, Any]] = []
        self._order_bys: list[tuple[str, Direction]] = []
        self._limit_val: int | None = None
        self._offset_val: int | None = None
        self._eager: list[str] = []

    # ------------------------------------------------------------------ #
    # Fluent API                                                           #
    # ------------------------------------------------------------------ #

    def select(self, *columns: Enum) -> QueryBuilder[T]:
        if columns:
            self._selects = [_unwrap_column(c) for c in columns]
        else:
            fields_enum: Any = self._model_class.Fields  # type: ignore[attr-defined]
            self._selects = [_unwrap_column(c) for c in fields_enum]
        return self

    def where(
        self,
        column: Enum,
        op_or_value: Operator | Any,
        value: Any = _MISSING,
    ) -> QueryBuilder[T]:
        col = _unwrap_column(column)
        if value is _MISSING:
            # where(column, value) → equality
            self._wheres.append((col, "=", op_or_value))
        else:
            # where(column, Operator.GREATER_THAN, value) → Operator with value
            op_str = op_or_value.value
            self._wheres.append((col, op_str, value))
        return self

    def where_in(self, column: Enum, values: list[Any]) -> QueryBuilder[T]:
        col = _unwrap_column(column)
        if not values:
            self._wheres.append(("1", "=", 0))  # always-false: WHERE 1 = 0
        else:
            self._wheres.append((col, "__IN__", values))
        return self

    def order_by(
        self, column: Enum, direction: Direction = Direction.ASCENDING
    ) -> QueryBuilder[T]:
        col = _unwrap_column(column)
        self._order_bys.append((col, direction))
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

    def to_sql(self) -> tuple[str, list[Any]]:
        """Return the generated SQL and parameters for inspection."""
        return self._build_select()

    def _execute_safe(self, sql: str, params: list[Any]) -> sqlite3.Cursor:
        """Execute SQL with helpful error messages showing the query."""
        try:
            return self._conn.execute(sql, params)
        except sqlite3.OperationalError as e:
            raise sqlite3.OperationalError(
                f"{e}\n\nFailed query:\n  SQL: {sql}\n  Params: {params}"
            ) from e

    # ------------------------------------------------------------------ #
    # Iterator Protocol                                                    #
    # ------------------------------------------------------------------ #

    def __iter__(self) -> QueryBuilder[T]:
        """Begin iteration over query results."""
        sql, params = self._build_select()
        self._rows = self._execute_safe(sql, params).fetchall()
        self._result_list: list[T] = [
            cast(T, from_row(self._model_class, r)) for r in self._rows
        ]
        if self._eager:
            self._load_eager(self._result_list)
        self._index = 0
        return self

    def __next__(self) -> T:
        """Get next result from iteration."""
        if self._index >= len(self._result_list):
            raise StopIteration
        result = self._result_list[self._index]
        self._index += 1
        return result

    # ------------------------------------------------------------------ #
    # Execution                                                            #
    # ------------------------------------------------------------------ #

    def count(self) -> int:
        saved = self._selects
        self._selects = ["COUNT(*) AS n"]
        sql, params = self._build_select()
        self._selects = saved
        row = self._execute_safe(sql, params).fetchone()
        return int(row["n"])

    def insert(
        self, models: Iterable[T]
    ) -> tuple[T, ...]:  # pylint: disable=too-many-locals
        """Insert multiple model instances. Returns tuple of fetched instances.

        Args:
            models: Iterable of model instances to insert.

        Returns:
            Tuple of inserted instances fetched from the database.
        """
        instances = list(models)
        if not instances:
            raise ValueError("insert() requires at least one model instance.")

        # Validate all instances before insertion
        for instance in instances:
            validate_model(instance)

        # Extract dicts from model instances
        dicts = [dataclasses.asdict(cast(Any, m)) for m in instances]

        # Get column names from first dict
        cols = list(dicts[0].keys())
        col_str = ", ".join(cols)
        ph_row = ", ".join("?" * len(cols))
        values_placeholders = ", ".join([f"({ph_row})"] * len(dicts))

        # Flatten all values
        all_values: list[Any] = []
        for d in dicts:
            all_values.extend(d[c] for c in cols)

        sql = f"INSERT INTO {self._table} ({col_str}) VALUES {values_placeholders}"
        self._execute_safe(sql, all_values)

        if not in_transaction_context():
            self._conn.commit()

        # Fetch inserted instances using their primary keys
        id_col = self._model_class._meta.id_column  # pylint: disable=protected-access
        inserted_ids = [d[id_col] for d in dicts]
        id_field = _column_to_enum(self._model_class, id_col)
        results = tuple(self.select().where_in(id_field, inserted_ids))
        return results

    def update(self, models: Iterable[T]) -> tuple[T, ...]:
        """Update rows using model instances' primary keys and field values.

        Args:
            models: Iterable of model instances to use for updates.

        Returns:
            Tuple of updated instances fetched from the database.
        """
        if self._wheres:
            raise ValueError(
                "update() with model instances uses primary keys, not WHERE clauses. "
                "Use patch(dict) with a where clause for filtered updates."
            )
        instances = list(models)
        if not instances:
            raise ValueError("update() requires at least one model instance.")

        # Validate all instances before update
        for instance in instances:
            validate_model(instance)

        id_col = self._model_class._meta.id_column  # pylint: disable=protected-access
        updated_ids = []

        for model in instances:
            data = dataclasses.asdict(cast(Any, model))
            if not data:
                raise ValueError("update() requires at least one column.")
            id_val = data[id_col]
            updated_ids.append(id_val)

            set_sql = ", ".join(f"{k} = ?" for k in data.keys())
            sql = f"UPDATE {self._table} SET {set_sql} WHERE {id_col} = ?"
            self._execute_safe(sql, list(data.values()) + [id_val])

        if not in_transaction_context():
            self._conn.commit()

        # Fetch updated instances
        id_field = _column_to_enum(self._model_class, id_col)
        results = tuple(self.select().where_in(id_field, updated_ids))
        return results

    def patch(self, data: dict[str, Any]) -> int:
        """Partial update of filtered rows with field changes.

        Args:
            data: Dictionary mapping column names to new values (use Model.Partial for typing).

        Returns:
            Number of rows affected.
        """
        if not data:
            raise ValueError("patch() requires at least one column.")
        if not self._wheres:
            raise ValueError(
                "patch() requires a WHERE clause. Use .where() to specify which rows to update."
            )

        validate_fields(self._model_class, data)

        set_sql = ", ".join(f"{k} = ?" for k in data)
        where_sql, where_params = self._build_where()
        sql = f"UPDATE {self._table} SET {set_sql}{where_sql}"
        cursor = self._execute_safe(sql, list(data.values()) + where_params)
        if not in_transaction_context():
            self._conn.commit()
        return cursor.rowcount

    def delete(self) -> int:
        if not self._wheres:
            raise ValueError(
                "delete() requires a WHERE clause. Use .where() to specify which rows to delete."
            )
        where_sql, where_params = self._build_where()
        cursor = self._execute_safe(
            f"DELETE FROM {self._table}{where_sql}", where_params
        )
        if not in_transaction_context():
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

    def _build_select(
        self, force_limit: int | None = None
    ) -> tuple[str, list[Any]]:  # pylint: disable=too-many-locals
        if self._selects is None:
            raise RuntimeError(
                f"Call .select() before issuing a SELECT query on "
                f"{self._model_class.__name__}. Use .select() with no arguments "
                f"to select all fields."
            )
        cols = ", ".join(self._selects)
        sql = f"SELECT {cols} FROM {self._table}"
        where_sql, params = self._build_where()
        sql += where_sql
        if self._order_bys:
            order = ", ".join(f"{c} {d.value}" for c, d in self._order_bys)
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
