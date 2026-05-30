"""Demonstrates cases where apparent type safety is not enforced by mypy."""

from dataclasses import dataclass
from typing import ClassVar

import sqlite3
import pytest

from icemodel import Model, ModelMeta, HasMany, BelongsTo, add_field_types
from tests.models import Artist, Album


class TestCrossModelFields:
    def test_wrong_model_fields_in_where(self, chinook: sqlite3.Connection) -> None:
        # mypy accepts this: where() takes Enum, and Album.Fields.ALBUMID is an Enum.
        # Only fails at runtime when SQLite finds no such column on the Artist table.
        with pytest.raises(sqlite3.OperationalError):
            tuple(Artist.query().where(Album.Fields.ALBUMID, 1))

    def test_wrong_model_fields_in_order_by(self, chinook: sqlite3.Connection) -> None:
        # mypy accepts this: order_by() takes Enum, no check that it belongs to Artist.
        # Only fails at runtime when SQLite finds no such column on the Artist table.
        with pytest.raises(sqlite3.OperationalError):
            tuple(Artist.query().order_by(Album.Fields.TITLE).limit(3))


class TestPatchKeyTyping:
    def test_typo_in_patch_key_silently_does_nothing(
        self, chinook: sqlite3.Connection
    ) -> None:
        # dict[str, Any] means mypy cannot catch the typo "Nmae"
        # The patch executes — SQLite will raise OperationalError at runtime
        # but mypy is silent
        with pytest.raises(sqlite3.OperationalError):
            Artist.query().where(Artist.Fields.ARTISTID, 1).patch({"Nmae": "test"})

    def test_wrong_model_partial_in_patch(self, chinook: sqlite3.Connection) -> None:
        # Album.Partial applied to an Artist query — mypy cannot distinguish these
        # since patch() takes dict[str, Any]
        album_data = {"Title": "test"}
        with pytest.raises(sqlite3.OperationalError):
            Artist.query().where(Artist.Fields.ARTISTID, 1).patch(album_data)


class TestFieldsEnumAccess:
    def test_nonexistent_fields_member(self, chinook: sqlite3.Connection) -> None:
        # Fields is typed as Any — mypy cannot catch nonexistent member access.
        # Synthesizing a proper Enum subtype requires module-level symbol table
        # registration that the ClassDefContext API does not expose.
        with pytest.raises(AttributeError):
            _ = Artist.Fields.TYPO
