"""Demonstrates cases where the mypy plugin catches type errors at check time.

Runtime tests verify the runtime behaviour still holds; type: ignore suppresses
the mypy errors that the plugin correctly raises so that the test module itself
compiles cleanly under strict mode.
"""

import sqlite3

import pytest

from icemodel._query_builder import Operator
from tests.models import Artist, Album


class TestCrossModelFields:
    def test_wrong_model_fields_in_where(self, chinook: sqlite3.Connection) -> None:
        # mypy now catches this: AlbumFields is not compatible with ArtistFields.
        # Still fails at runtime when SQLite finds no such column on the Artist table.
        with pytest.raises(sqlite3.OperationalError):
            tuple(
                Artist.query()
                .select()
                .where(Album.Fields.ALBUMID, Operator.EQUAL, 1)  # type: ignore[arg-type]
            )

    def test_wrong_model_fields_in_order_by(self, chinook: sqlite3.Connection) -> None:
        # mypy now catches this: AlbumFields is not compatible with ArtistFields.
        # Still fails at runtime when SQLite finds no such column on the Artist table.
        with pytest.raises(sqlite3.OperationalError):
            tuple(
                Artist.query()
                .select()
                .order_by(Album.Fields.TITLE)  # type: ignore[arg-type]
                .limit(3)
            )


class TestPatchKeyTyping:
    def test_typo_in_patch_key_silently_does_nothing(
        self, chinook: sqlite3.Connection
    ) -> None:
        # mypy now catches the key typo via the TypedDict-narrowed patch() signature.
        # SQLite still raises OperationalError at runtime.
        with pytest.raises(sqlite3.OperationalError):
            Artist.query().where(Artist.Fields.ARTISTID, Operator.EQUAL, 1).patch(
                {"Nmae": "test"}  # type: ignore[typeddict-unknown-key]
            )

    def test_wrong_model_partial_in_patch(self, chinook: sqlite3.Connection) -> None:
        # mypy now catches this: dict[str, str] is not compatible with Artist.Partial.
        # SQLite still raises OperationalError at runtime when the column is absent.
        album_data = {"Title": "test"}
        with pytest.raises(sqlite3.OperationalError):
            Artist.query().where(Artist.Fields.ARTISTID, Operator.EQUAL, 1).patch(
                album_data  # type: ignore[arg-type]
            )


class TestFieldsEnumAccess:
    def test_nonexistent_fields_member(self, chinook: sqlite3.Connection) -> None:
        # mypy catches this (type: ignore is required for the test to compile).
        # AttributeError is still raised at runtime since TYPO is not a real member.
        with pytest.raises(AttributeError):
            _ = Artist.Fields.TYPO  # type: ignore[attr-defined]
