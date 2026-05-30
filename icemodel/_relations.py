from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, overload

from ._utils import from_row

if TYPE_CHECKING:
    from ._model import Model

# Relations access model._meta which is internal but part of the ORM contract
# pylint: disable=protected-access

_UNLOADED: object = object()


def _resolve_model(ref: str | type[Model]) -> type[Model]:
    from ._model import _model_registry  # pylint: disable=import-outside-toplevel

    if isinstance(ref, str):
        try:
            return _model_registry[ref]
        except KeyError as exc:
            raise NameError(f"No model named {ref!r} has been defined.") from exc
    return ref


class Relation:
    name: str

    def __set_name__(self, owner: type[Model], name: str) -> None:
        self.name = name
        # Use __dict__ (not hasattr) to avoid writing into an inherited dict
        # shared with the Model base class or sibling models.
        if "__relations__" not in owner.__dict__:
            owner.__relations__ = {}
        owner.__relations__[name] = self

    @overload
    def __get__(self, obj: None, objtype: type[Model]) -> Relation: ...

    @overload
    def __get__(self, obj: Model, objtype: type[Model]) -> Any: ...

    def __get__(self, obj: Model | None, objtype: type[Model] | None = None) -> Any:
        raise NotImplementedError

    def load_for(self, instances: list[Model], conn: sqlite3.Connection) -> None:
        raise NotImplementedError


class HasMany(Relation):
    """One-to-many: the foreign key lives on the related table."""

    def __init__(
        self,
        related: str | type[Model],
        *,
        foreign_key: str,
        local_key: str = "id",
    ) -> None:
        self._related = related
        self.foreign_key = foreign_key
        self.local_key = local_key

    def __get__(self, obj: Model | None, objtype: type[Model] | None = None) -> Any:
        if obj is None:
            return self
        cached = obj.__dict__.get(f"_rel_{self.name}", _UNLOADED)
        if cached is not _UNLOADED:
            return cached
        related_cls = _resolve_model(self._related)
        from ._connection import get_connection  # pylint: disable=import-outside-toplevel

        conn = get_connection()
        local_val = obj.__dict__[self.local_key]
        rows = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.foreign_key} = ?",
            (local_val,),
        ).fetchall()
        result = [from_row(related_cls, r) for r in rows]
        obj.__dict__[f"_rel_{self.name}"] = result
        return result

    def load_for(self, instances: list[Model], conn: sqlite3.Connection) -> None:
        related_cls = _resolve_model(self._related)
        ids = [inst.__dict__[self.local_key] for inst in instances]
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.foreign_key} IN ({ph})",
            ids,
        ).fetchall()
        grouped: dict[Any, list[Model]] = {}
        for row in rows:
            fk = row[self.foreign_key]
            grouped.setdefault(fk, []).append(from_row(related_cls, row))
        for inst in instances:
            lv = inst.__dict__[self.local_key]
            inst.__dict__[f"_rel_{self.name}"] = grouped.get(lv, [])


class BelongsTo(Relation):
    """Many-to-one: the foreign key lives on this model's table."""

    def __init__(
        self,
        related: str | type[Model],
        *,
        foreign_key: str,
        owner_key: str = "id",
    ) -> None:
        self._related = related
        self.foreign_key = foreign_key
        self.owner_key = owner_key

    def __get__(self, obj: Model | None, objtype: type[Model] | None = None) -> Any:
        if obj is None:
            return self
        cached = obj.__dict__.get(f"_rel_{self.name}", _UNLOADED)
        if cached is not _UNLOADED:
            return cached
        related_cls = _resolve_model(self._related)
        from ._connection import get_connection  # pylint: disable=import-outside-toplevel

        conn = get_connection()
        fk_val = obj.__dict__.get(self.foreign_key)
        if fk_val is None:
            obj.__dict__[f"_rel_{self.name}"] = None
            return None
        row = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.owner_key} = ?",
            (fk_val,),
        ).fetchone()
        result = from_row(related_cls, row) if row else None
        obj.__dict__[f"_rel_{self.name}"] = result
        return result

    def load_for(self, instances: list[Model], conn: sqlite3.Connection) -> None:
        related_cls = _resolve_model(self._related)
        fk_vals = list({inst.__dict__.get(self.foreign_key) for inst in instances} - {None})
        if not fk_vals:
            for inst in instances:
                inst.__dict__[f"_rel_{self.name}"] = None
            return
        ph = ",".join("?" * len(fk_vals))
        rows = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.owner_key} IN ({ph})",
            fk_vals,
        ).fetchall()
        by_key: dict[Any, Model] = {
            row[self.owner_key]: from_row(related_cls, row) for row in rows
        }
        for inst in instances:
            fk = inst.__dict__.get(self.foreign_key)
            inst.__dict__[f"_rel_{self.name}"] = by_key.get(fk)


class HasOne(Relation):
    """One-to-one: the foreign key lives on the related table."""

    def __init__(
        self,
        related: str | type[Model],
        *,
        foreign_key: str,
        local_key: str = "id",
    ) -> None:
        self._related = related
        self.foreign_key = foreign_key
        self.local_key = local_key

    def __get__(self, obj: Model | None, objtype: type[Model] | None = None) -> Any:
        if obj is None:
            return self
        cached = obj.__dict__.get(f"_rel_{self.name}", _UNLOADED)
        if cached is not _UNLOADED:
            return cached
        related_cls = _resolve_model(self._related)
        from ._connection import get_connection  # pylint: disable=import-outside-toplevel

        conn = get_connection()
        local_val = obj.__dict__[self.local_key]
        row = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.foreign_key} = ? LIMIT 1",
            (local_val,),
        ).fetchone()
        result = from_row(related_cls, row) if row else None
        obj.__dict__[f"_rel_{self.name}"] = result
        return result

    def load_for(self, instances: list[Model], conn: sqlite3.Connection) -> None:
        related_cls = _resolve_model(self._related)
        ids = [inst.__dict__[self.local_key] for inst in instances]
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.foreign_key} IN ({ph})",
            ids,
        ).fetchall()
        by_fk: dict[Any, Model] = {}
        for row in rows:
            fk = row[self.foreign_key]
            if fk not in by_fk:
                by_fk[fk] = from_row(related_cls, row)
        for inst in instances:
            lv = inst.__dict__[self.local_key]
            inst.__dict__[f"_rel_{self.name}"] = by_fk.get(lv)


class ManyToMany(Relation):
    """Many-to-many through a join table. Issues two queries to avoid column aliasing issues."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        related: str | type[Model],
        *,
        join_table: str,
        local_fk: str,
        related_fk: str,
        local_key: str = "id",
        related_pk: str = "id",
    ) -> None:
        self._related = related
        self.join_table = join_table
        self.local_fk = local_fk
        self.related_fk = related_fk
        self.local_key = local_key
        self.related_pk = related_pk

    def _fetch(
        self, local_ids: list[Any], conn: sqlite3.Connection
    ) -> dict[Any, list[Model]]:
        related_cls = _resolve_model(self._related)
        ph = ",".join("?" * len(local_ids))
        join_rows = conn.execute(
            f"SELECT {self.local_fk}, {self.related_fk} FROM {self.join_table}"
            f" WHERE {self.local_fk} IN ({ph})",
            local_ids,
        ).fetchall()
        related_ids = list({r[self.related_fk] for r in join_rows})
        if not related_ids:
            return {}
        ph2 = ",".join("?" * len(related_ids))
        related_rows = conn.execute(
            f"SELECT * FROM {related_cls._meta.table} WHERE {self.related_pk} IN ({ph2})",
            related_ids,
        ).fetchall()
        by_pk: dict[Any, Model] = {
            row[self.related_pk]: from_row(related_cls, row) for row in related_rows
        }
        grouped: dict[Any, list[Model]] = {}
        for jr in join_rows:
            lv = jr[self.local_fk]
            rv = jr[self.related_fk]
            if rv in by_pk:
                grouped.setdefault(lv, []).append(by_pk[rv])
        return grouped

    def __get__(self, obj: Model | None, objtype: type[Model] | None = None) -> Any:
        if obj is None:
            return self
        cached = obj.__dict__.get(f"_rel_{self.name}", _UNLOADED)
        if cached is not _UNLOADED:
            return cached
        from ._connection import get_connection  # pylint: disable=import-outside-toplevel

        conn = get_connection()
        local_val = obj.__dict__[self.local_key]
        grouped = self._fetch([local_val], conn)
        result = grouped.get(local_val, [])
        obj.__dict__[f"_rel_{self.name}"] = result
        return result

    def load_for(self, instances: list[Model], conn: sqlite3.Connection) -> None:
        ids = [inst.__dict__[self.local_key] for inst in instances]
        grouped = self._fetch(ids, conn)
        for inst in instances:
            lv = inst.__dict__[self.local_key]
            inst.__dict__[f"_rel_{self.name}"] = grouped.get(lv, [])
