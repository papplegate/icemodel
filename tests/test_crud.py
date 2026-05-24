"""CRUD tests against a fresh in-memory STRICT schema (writable_db fixture)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import ClassVar

import pytest

from ormen import HasMany, ManyToMany, Model


# ------------------------------------------------------------------ #
# Local models for the writable schema                                #
# ------------------------------------------------------------------ #


@dataclass(eq=False, frozen=True)
class Book(Model):
    _meta = {"table": "Book", "id_column": "BookId"}

    tags: ClassVar[ManyToMany] = ManyToMany(
        "Tag",
        join_table="BookTag",
        local_fk="BookId",
        related_fk="TagId",
        local_key="BookId",
        related_pk="TagId",
    )

    BookId: int = 0
    Title: str = ""
    Author: str | None = None
    Year: int | None = None
    Price: float = 0.0


@dataclass(eq=False, frozen=True)
class Tag(Model):
    _meta = {"table": "Tag", "id_column": "TagId"}

    books: ClassVar[HasMany] = HasMany(
        "Book", foreign_key="BookId", local_key="TagId"
    )

    TagId: int = 0
    Label: str = ""


# ------------------------------------------------------------------ #
# Tests                                                               #
# ------------------------------------------------------------------ #


class TestInsert:
    def test_insert_returns_model(self, writable_db: sqlite3.Connection) -> None:
        book = Book.query().insert(
            {"BookId": 1, "Title": "Dune", "Author": "Frank Herbert", "Year": 1965, "Price": 9.99}
        )
        assert isinstance(book, Book)
        assert book.BookId == 1
        assert book.Title == "Dune"
        assert book.Author == "Frank Herbert"
        assert book.Year == 1965
        assert book.Price == pytest.approx(9.99)

    def test_insert_persists(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "Dune", "Price": 9.99})
        fetched = Book.query().find_by_id(1)
        assert fetched is not None
        assert fetched.Title == "Dune"

    def test_insert_empty_raises(self, writable_db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="insert()"):
            Book.query().insert({})

    def test_insert_strict_type_error(self, writable_db: sqlite3.Connection) -> None:
        # STRICT mode: inserting TEXT for an INTEGER column should raise.
        with pytest.raises(Exception):
            Book.query().insert({"BookId": "not-an-int", "Title": "Bad", "Price": 1.0})


class TestPatch:
    def test_patch_updates_field(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "Dune", "Price": 9.99})
        rows_affected = Book.query().where("BookId", 1).patch({"Title": "Dune Messiah"})
        assert rows_affected == 1
        book = Book.query().find_by_id(1)
        assert book is not None
        assert book.Title == "Dune Messiah"

    def test_patch_multiple_fields(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "Dune", "Price": 9.99})
        Book.query().where("BookId", 1).patch({"Title": "Children of Dune", "Price": 12.50})
        book = Book.query().find_by_id(1)
        assert book is not None
        assert book.Title == "Children of Dune"
        assert book.Price == pytest.approx(12.50)

    def test_patch_without_where_updates_all(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "A", "Price": 1.0})
        Book.query().insert({"BookId": 2, "Title": "B", "Price": 2.0})
        rows_affected = Book.query().patch({"Author": "Unknown"})
        assert rows_affected == 2

    def test_patch_empty_raises(self, writable_db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="patch()"):
            Book.query().patch({})


class TestDelete:
    def test_delete_removes_row(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "Dune", "Price": 9.99})
        rows_affected = Book.query().where("BookId", 1).delete()
        assert rows_affected == 1
        assert Book.query().find_by_id(1) is None

    def test_delete_without_where_clears_table(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "A", "Price": 1.0})
        Book.query().insert({"BookId": 2, "Title": "B", "Price": 2.0})
        Book.query().delete()
        assert Book.query().count() == 0

    def test_delete_returns_rowcount(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "A", "Price": 1.0})
        Book.query().insert({"BookId": 2, "Title": "B", "Price": 2.0})
        n = Book.query().where("BookId", ">", 0).delete()
        assert n == 2


class TestCount:
    def test_count_empty_table(self, writable_db: sqlite3.Connection) -> None:
        assert Book.query().count() == 0

    def test_count_after_inserts(self, writable_db: sqlite3.Connection) -> None:
        for i in range(5):
            Book.query().insert({"BookId": i + 1, "Title": f"Book {i}", "Price": 1.0})
        assert Book.query().count() == 5

    def test_count_with_where(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert({"BookId": 1, "Title": "A", "Year": 2000, "Price": 1.0})
        Book.query().insert({"BookId": 2, "Title": "B", "Year": 2010, "Price": 1.0})
        assert Book.query().where("Year", ">", 2005).count() == 1
