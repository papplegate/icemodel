import dataclasses
import sqlite3
from contextlib import contextmanager
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Generator, TypeVar

from ._connection import (
    get_connection,
    set_connection,
    set_transaction_context,
)
from ._relations import Relation

if TYPE_CHECKING:
    from ._query_builder import QueryBuilder

_model_registry: "dict[str, type[Model]]" = {}

T = TypeVar("T", bound="Model")


@dataclasses.dataclass(frozen=True)
class ModelMeta:
    """Metadata configuration for a model: table name and primary key column."""

    table: str
    id_column: str = "id"


def add_field_types(cls: type[T]) -> type[T]:
    """Decorator to create a Fields enum for a model class.

    Apply after @dataclass decorator:
        @add_field_types
        @dataclass(eq=False, frozen=True)
        class MyModel(Model):
            ...
    """
    field_dict = {f.name.upper(): f.name for f in dataclasses.fields(cls)}
    cls.Fields = Enum(f"{cls.__name__}Fields", field_dict)  # type: ignore[attr-defined,misc]
    return cls


class _ModelMeta(type):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)
        _model_registry[name] = cls  # type: ignore[assignment]
        if "__relations__" not in cls.__dict__:
            cls.__relations__: dict[str, Relation] = {}
        for attr_name, val in namespace.items():
            if isinstance(val, Relation) and not hasattr(val, "name"):
                val.name = attr_name
                cls.__relations__[attr_name] = val

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls.__name__ == "Model":
            raise TypeError(
                "Model cannot be instantiated directly. Subclass it instead."
            )
        return super().__call__(*args, **kwargs)


@dataclasses.dataclass(eq=False, frozen=True)
class Model(metaclass=_ModelMeta):
    """Base class for ORM models. Do not instantiate directly; subclass instead.

    Subclasses should be decorated with ``@dataclass(eq=False, frozen=True)`` so that
    ``Model.__eq__`` (primary-key equality) is preserved rather than the
    field-wise equality that @dataclass generates.

    Class-level relations (``HasMany``, ``BelongsTo``, etc.) must be declared
    as ``ClassVar`` so the ``@dataclass`` decorator skips them as instance fields.

    Metadata (table name, primary key column) is defined as a frozen ModelMeta instance:
        _meta = ModelMeta(table="artist", id_column="ArtistId")
    """

    _meta: ClassVar[ModelMeta] = ModelMeta("")
    __relations__: ClassVar[dict[str, Relation]]

    def __repr__(self) -> str:
        attrs = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        pairs = ", ".join(f"{k}={v!r}" for k, v in attrs.items())
        return f"{self.__class__.__name__}({pairs})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Model):
            return NotImplemented
        if type(self) is not type(other):
            return False
        id_col = self._meta.id_column
        return self.__dict__.get(id_col) == other.__dict__.get(id_col)

    # ------------------------------------------------------------------ #
    # Class-level API                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def bind(cls, conn: sqlite3.Connection) -> None:
        set_connection(conn)

    @classmethod
    def query(cls: type[T]) -> "QueryBuilder[T]":
        from ._query_builder import (
            QueryBuilder as _QB,
        )  # pylint: disable=import-outside-toplevel

        return _QB(cls, cls._meta.table, get_connection())

    @classmethod
    @contextmanager
    def transaction(cls) -> Generator[None, None, None]:
        """Context manager for database transactions.

        Automatically commits on success, rolls back on exception.

        Example:
            with Artist.transaction():
                Artist.query().insert({"ArtistId": 1, "Name": "New"})
                Album.query().insert({"AlbumId": 1, "ArtistId": 1})
        """
        conn = get_connection()
        set_transaction_context(True)
        try:
            if not conn.in_transaction:
                conn.execute("BEGIN")
            try:
                yield
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        finally:
            set_transaction_context(False)
