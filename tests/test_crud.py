"""CRUD tests against a fresh in-memory STRICT schema (writable_db fixture)."""

import sqlite3
from dataclasses import dataclass
from typing import ClassVar

import pytest

from icemodel import HasMany, ManyToMany, Model, ModelMeta, add_field_types
from icemodel._query_builder import Operator

# ------------------------------------------------------------------ #
# Local models for the writable schema                                #
# ------------------------------------------------------------------ #


@add_field_types
@dataclass(eq=False, frozen=True)
class Book(Model):
    _meta = ModelMeta(table="Book", id_column="BookId")

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


@add_field_types
@dataclass(eq=False, frozen=True)
class Tag(Model):
    _meta = ModelMeta(table="Tag", id_column="TagId")

    books: ClassVar[HasMany] = HasMany("Book", foreign_key="BookId", local_key="TagId")

    TagId: int = 0
    Label: str = ""


# ------------------------------------------------------------------ #
# Tests                                                               #
# ------------------------------------------------------------------ #


class TestInsert:
    def test_insert_returns_models(self, writable_db: sqlite3.Connection) -> None:
        book = Book(
            BookId=1, Title="Dune", Author="Frank Herbert", Year=1965, Price=9.99
        )
        results = Book.query().insert([book])
        assert isinstance(results, tuple)
        assert len(results) == 1
        fetched = results[0]
        assert isinstance(fetched, Book)
        assert fetched.BookId == 1
        assert fetched.Title == "Dune"
        assert fetched.Author == "Frank Herbert"
        assert fetched.Year == 1965
        assert fetched.Price == pytest.approx(9.99)

    def test_insert_persists(self, writable_db: sqlite3.Connection) -> None:
        book = Book(BookId=1, Title="Dune", Price=9.99)
        Book.query().insert([book])
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.Title == "Dune"

    def test_insert_empty_raises(self, writable_db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="insert()"):
            Book.query().insert([])

    def test_insert_multiple(self, writable_db: sqlite3.Connection) -> None:
        books = [
            Book(BookId=1, Title="Dune", Price=9.99),
            Book(BookId=2, Title="Foundation", Price=12.99),
        ]
        results = Book.query().insert(books)
        assert isinstance(results, tuple)
        assert len(results) == 2
        assert {r.BookId for r in results} == {1, 2}
        assert {r.Title for r in results} == {"Dune", "Foundation"}


class TestSave:
    def test_save_single_instance(self, writable_db: sqlite3.Connection) -> None:
        from dataclasses import replace

        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        original = _results[0]
        modified = replace(original, Title="Dune Messiah")
        results = Book.query().save([modified])
        assert isinstance(results, tuple)
        assert len(results) == 1
        assert results[0].Title == "Dune Messiah"

    def test_save_multiple_fields(self, writable_db: sqlite3.Connection) -> None:
        from dataclasses import replace

        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        original = _results[0]
        modified = replace(original, Title="Children of Dune", Price=12.50)
        results = Book.query().save([modified])
        assert len(results) == 1
        assert results[0].Title == "Children of Dune"
        assert results[0].Price == pytest.approx(12.50)

    def test_save_multiple_instances(self, writable_db: sqlite3.Connection) -> None:
        from dataclasses import replace

        Book.query().insert(
            [
                Book(BookId=1, Title="A", Price=1.0),
                Book(BookId=2, Title="B", Price=2.0),
            ]
        )
        _results1 = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results1) > 0
        book1 = _results1[0]
        _results2 = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 2).limit(1)
        )
        assert len(_results2) > 0
        book2 = _results2[0]
        modified1 = replace(book1, Title="A Modified")
        modified2 = replace(book2, Title="B Modified")
        results = Book.query().save([modified1, modified2])
        assert isinstance(results, tuple)
        assert len(results) == 2
        assert {r.Title for r in results} == {"A Modified", "B Modified"}

    def test_save_empty_raises(self, writable_db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="save()"):
            Book.query().save([])

    def test_save_with_where_raises(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="A", Price=1.0)])
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        book = _results[0]
        with pytest.raises(ValueError, match="WHERE"):
            Book.query().where(Book.Fields.BOOKID, Operator.EQUAL, 1).save([book])


class TestUpdate:
    def test_update_updates_filtered_rows(
        self, writable_db: sqlite3.Connection
    ) -> None:
        Book.query().insert(
            [
                Book(BookId=1, Title="A", Year=2000, Price=1.0),
                Book(BookId=2, Title="B", Year=2010, Price=2.0),
            ]
        )
        rows_affected = (
            Book.query()
            .where(Book.Fields.YEAR, Operator.GREATER_THAN, 2005)
            .update({"Author": "Unknown"})
        )
        assert rows_affected == 1
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 2).limit(1)
        )
        assert len(_results) > 0
        book = _results[0]
        assert book.Author == "Unknown"

    def test_update_multiple_fields(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        rows_affected = (
            Book.query()
            .where(Book.Fields.BOOKID, Operator.EQUAL, 1)
            .update({"Title": "Children of Dune", "Price": 12.50})
        )
        assert rows_affected == 1
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        book = _results[0]
        assert book.Title == "Children of Dune"
        assert book.Price == pytest.approx(12.50)

    def test_update_without_where_raises(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert(
            [
                Book(BookId=1, Title="A", Price=1.0),
                Book(BookId=2, Title="B", Price=2.0),
            ]
        )
        with pytest.raises(ValueError, match="WHERE clause"):
            Book.query().update({"Author": "Unknown"})

    def test_update_empty_raises(self, writable_db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="update()"):
            Book.query().update({})


class TestDelete:
    def test_delete_removes_row(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        rows_affected = (
            Book.query().where(Book.Fields.BOOKID, Operator.EQUAL, 1).delete()
        )
        assert rows_affected == 1
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) == 0

    def test_delete_without_where_raises(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="A", Price=1.0)])
        Book.query().insert([Book(BookId=2, Title="B", Price=2.0)])
        with pytest.raises(ValueError, match="WHERE clause"):
            Book.query().delete()

    def test_delete_returns_rowcount(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="A", Price=1.0)])
        Book.query().insert([Book(BookId=2, Title="B", Price=2.0)])
        n = Book.query().where(Book.Fields.BOOKID, Operator.GREATER_THAN, 0).delete()
        assert n == 2


class TestCount:
    def test_count_empty_table(self, writable_db: sqlite3.Connection) -> None:
        assert Book.query().count() == 0

    def test_count_after_inserts(self, writable_db: sqlite3.Connection) -> None:
        for i in range(5):
            Book.query().insert([Book(BookId=i + 1, Title=f"Book {i}", Price=1.0)])
        assert Book.query().count() == 5

    def test_count_with_where(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="A", Year=2000, Price=1.0)])
        Book.query().insert([Book(BookId=2, Title="B", Year=2010, Price=1.0)])
        assert (
            Book.query().where(Book.Fields.YEAR, Operator.GREATER_THAN, 2005).count()
            == 1
        )


class TestTransactions:
    def test_transaction_commits_on_success(
        self, writable_db: sqlite3.Connection
    ) -> None:
        with Book.transaction():
            Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        # Should be persisted after context exits
        assert Book.query().count() == 1
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        book = _results[0]
        assert book.Title == "Dune"

    def test_transaction_rolls_back_on_exception(
        self, writable_db: sqlite3.Connection
    ) -> None:
        try:
            with Book.transaction():
                Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
                raise ValueError("Something went wrong")
        except ValueError:
            pass
        # Should be rolled back
        assert Book.query().count() == 0

    def test_transaction_multiple_inserts(
        self, writable_db: sqlite3.Connection
    ) -> None:
        with Book.transaction():
            Book.query().insert([Book(BookId=1, Title="Book 1", Price=1.0)])
            Book.query().insert([Book(BookId=2, Title="Book 2", Price=2.0)])
            Tag.query().insert([Tag(TagId=1, Label="Fiction")])
        assert Book.query().count() == 2
        assert Tag.query().count() == 1

    def test_transaction_partial_rollback(
        self, writable_db: sqlite3.Connection
    ) -> None:
        Book.query().insert([Book(BookId=1, Title="Existing", Price=5.0)])
        try:
            with Book.transaction():
                Book.query().insert([Book(BookId=2, Title="New", Price=10.0)])
                raise RuntimeError("Rollback this transaction")
        except RuntimeError:
            pass
        # Original should exist, new should be rolled back
        assert Book.query().count() == 1
        _results1 = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results1) > 0
        result1 = _results1[0]
        _results2 = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 2).limit(1)
        )
        assert len(_results2) == 0


class TestFieldsEnum:
    def test_fields_enum_usable_in_queries(
        self, writable_db: sqlite3.Connection
    ) -> None:
        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        # Can use enum members to reference field names in queries
        results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert results
        assert results[0].Title == "Dune"

    def test_fields_enum_with_order_by(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        Book.query().insert([Book(BookId=2, Title="Foundation", Price=12.99)])
        # Can use enum members in order_by
        results = tuple(Book.query().select().order_by(Book.Fields.TITLE))
        assert [r.Title for r in results] == ["Dune", "Foundation"]

    def test_fields_enum_with_select(self, writable_db: sqlite3.Connection) -> None:
        Book.query().insert([Book(BookId=1, Title="Dune", Price=9.99)])
        # Can use enum members in select
        results = tuple(Book.query().select(Book.Fields.TITLE, Book.Fields.PRICE))
        assert len(results) == 1
        assert results[0].Title == "Dune"


class TestRoundTrip:
    def test_insert_and_fetch_all_fields(self, writable_db: sqlite3.Connection) -> None:
        """Verify all field types survive insert and fetch unchanged."""
        original = Book(
            BookId=42,
            Title="The Name of the Wind",
            Author="Patrick Rothfuss",
            Year=2007,
            Price=15.99,
        )
        Book.query().insert([original])

        # Fresh fetch from database (not the returned value from insert)
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 42).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.BookId == 42
        assert fetched.Title == "The Name of the Wind"
        assert fetched.Author == "Patrick Rothfuss"
        assert fetched.Year == 2007
        assert fetched.Price == pytest.approx(15.99)

    def test_insert_and_fetch_with_nulls(self, writable_db: sqlite3.Connection) -> None:
        """Verify nullable fields store and retrieve None correctly."""
        original = Book(
            BookId=99, Title="Standalone", Author=None, Year=None, Price=5.0
        )
        Book.query().insert([original])

        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 99).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.BookId == 99
        assert fetched.Title == "Standalone"
        assert fetched.Author is None
        assert fetched.Year is None
        assert fetched.Price == pytest.approx(5.0)

    def test_update_and_fetch_all_fields(self, writable_db: sqlite3.Connection) -> None:
        """Verify update preserves all field types correctly."""
        from dataclasses import replace

        Book.query().insert([Book(BookId=1, Title="Original", Price=1.0)])
        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        original = _results[0]

        modified = replace(
            original,
            Title="Updated Title",
            Author="New Author",
            Year=2025,
            Price=29.99,
        )
        Book.query().save([modified])

        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.BookId == 1
        assert fetched.Title == "Updated Title"
        assert fetched.Author == "New Author"
        assert fetched.Year == 2025
        assert fetched.Price == pytest.approx(29.99)

    def test_patch_and_fetch_all_fields(self, writable_db: sqlite3.Connection) -> None:
        """Verify patch preserves all field types correctly."""
        Book.query().insert(
            [Book(BookId=1, Title="Original", Author="Original Author", Price=10.0)]
        )

        Book.query().where(Book.Fields.BOOKID, Operator.EQUAL, 1).update(
            {
                "Title": "Patched Title",
                "Year": 2020,
                "Price": 19.99,
            }
        )

        _results = tuple(
            Book.query().select().where(Book.Fields.BOOKID, Operator.EQUAL, 1).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.BookId == 1
        assert fetched.Title == "Patched Title"
        assert fetched.Author == "Original Author"  # unchanged
        assert fetched.Year == 2020
        assert fetched.Price == pytest.approx(19.99)


class TestModelInstantiation:
    def test_cannot_instantiate_model_directly(self) -> None:
        """Model base class cannot be instantiated directly."""
        with pytest.raises(TypeError, match="cannot be instantiated directly"):
            Model()

    def test_can_instantiate_model_subclass(
        self, writable_db: sqlite3.Connection
    ) -> None:
        """Model subclasses can be instantiated."""
        book = Book(BookId=1, Title="Test", Price=9.99)
        assert book.BookId == 1
        assert book.Title == "Test"
