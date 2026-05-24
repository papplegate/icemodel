from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from ._connection import get_connection, set_connection
from ._relations import Relation

if TYPE_CHECKING:
    from ._query_builder import QueryBuilder

_model_registry: dict[str, type[Model]] = {}

T = TypeVar("T", bound="Model")


class _ModelMeta(type):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)
        if name != "Model":
            _model_registry[name] = cls  # type: ignore[assignment]
        if "__relations__" not in cls.__dict__:
            cls.__relations__: dict[str, Relation] = {}
        for attr_name, val in namespace.items():
            if isinstance(val, Relation) and not hasattr(val, "name"):
                val.name = attr_name
                cls.__relations__[attr_name] = val


class Model(metaclass=_ModelMeta):
    """Base class for ORM models.

    Subclasses should be decorated with ``@dataclass(eq=False)`` so that
    ``Model.__eq__`` (primary-key equality) is preserved rather than the
    field-wise equality that @dataclass generates.

    Class-level relations (``HasMany``, ``BelongsTo``, etc.) must be declared
    as ``ClassVar`` so the ``@dataclass`` decorator skips them as instance fields.

    Metadata (table name, primary key column) is stored in a ``_meta`` dict:
        _meta = {"table": "artist", "id_column": "ArtistId"}
    """

    _meta: ClassVar[dict[str, str]] = {"table": "", "id_column": "id"}
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
        id_col = self._meta["id_column"]
        return self.__dict__.get(id_col) == other.__dict__.get(id_col)

    # ------------------------------------------------------------------ #
    # Class-level API                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def bind(cls, conn: sqlite3.Connection) -> None:
        set_connection(conn)

    @classmethod
    def query(cls: type[T]) -> QueryBuilder[T]:
        from ._query_builder import QueryBuilder as _QB  # pylint: disable=import-outside-toplevel

        return _QB(cls, cls._meta["table"], get_connection())
