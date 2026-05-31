"""Read-only query tests against the Chinook database."""

from __future__ import annotations

import sqlite3

import pytest

from icemodel._query_builder import Direction, Operator
from tests.models import Album, Artist, Employee, Genre, Invoice, Track


class TestAll:
    def test_returns_all_rows(self, chinook: sqlite3.Connection) -> None:
        artists = tuple(Artist.query().select())
        assert len(artists) == 275

    def test_instances_are_typed(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(Artist.query().select().limit(1))
        artist = _results[0] if _results else None
        assert artist is not None
        assert isinstance(artist.ArtistId, int)
        assert isinstance(artist.Name, str | type(None))

    def test_genre_count(self, chinook: sqlite3.Connection) -> None:
        assert Genre.query().count() == 25


class TestWhere:
    def test_equality(self, chinook: sqlite3.Connection) -> None:
        results = tuple(Artist.query().select().where(Artist.Fields.NAME, "AC/DC"))
        assert len(results) == 1
        assert results[0].ArtistId == 1

    def test_operator_gt(self, chinook: sqlite3.Connection) -> None:
        results = tuple(
            Invoice.query()
            .select()
            .where(Invoice.Fields.TOTAL, Operator.GREATER_THAN, 20)
        )
        assert all(inv.Total > 20 for inv in results)
        assert len(results) > 0

    def test_operator_like(self, chinook: sqlite3.Connection) -> None:
        results = tuple(
            Artist.query().select().where(Artist.Fields.NAME, Operator.LIKE, "The %")
        )
        assert all(a.Name is not None and a.Name.startswith("The ") for a in results)
        assert len(results) > 0

    def test_chained_where(self, chinook: sqlite3.Connection) -> None:
        # Albums with ArtistId=1 and AlbumId > 1
        results = tuple(
            Album.query()
            .select()
            .where(Album.Fields.ARTISTID, 1)
            .where(Album.Fields.ALBUMID, Operator.GREATER_THAN, 1)
        )
        assert all(a.ArtistId == 1 and a.AlbumId > 1 for a in results)


class TestWhereIn:
    def test_where_in(self, chinook: sqlite3.Connection) -> None:
        results = tuple(
            Artist.query().select().where_in(Artist.Fields.ARTISTID, [1, 2, 3])
        )
        assert {a.ArtistId for a in results} == {1, 2, 3}

    def test_empty_where_in_returns_nothing(self, chinook: sqlite3.Connection) -> None:
        results = tuple(Artist.query().select().where_in(Artist.Fields.ARTISTID, []))
        assert results == ()


class TestOrderBy:
    def test_asc(self, chinook: sqlite3.Connection) -> None:
        names = [
            a.Name
            for a in tuple(
                Artist.query().select().order_by(Artist.Fields.NAME).limit(5)
            )
            if a.Name is not None
        ]
        assert names == sorted(names)

    def test_desc(self, chinook: sqlite3.Connection) -> None:
        totals = [
            inv.Total
            for inv in tuple(
                Invoice.query()
                .select()
                .order_by(Invoice.Fields.TOTAL, Direction.DESCENDING)
                .limit(5)
            )
        ]
        assert totals == sorted(totals, reverse=True)


class TestLimitOffset:
    def test_limit(self, chinook: sqlite3.Connection) -> None:
        assert len(tuple(Artist.query().select().limit(10))) == 10

    def test_offset(self, chinook: sqlite3.Connection) -> None:
        first_ten = [
            a.ArtistId
            for a in tuple(
                Artist.query().select().order_by(Artist.Fields.ARTISTID).limit(10)
            )
        ]
        second_ten = [
            a.ArtistId
            for a in tuple(
                Artist.query()
                .select()
                .order_by(Artist.Fields.ARTISTID)
                .limit(10)
                .offset(10)
            )
        ]
        assert len(set(first_ten) & set(second_ten)) == 0


class TestFindById:
    def test_finds_existing(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Artist.query().select().where(Artist.Fields.ARTISTID, 1).limit(1)
        )
        assert len(_results) > 0
        artist = _results[0]
        assert artist.ArtistId == 1
        assert artist.Name == "AC/DC"

    def test_returns_none_for_missing(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Artist.query().select().where(Artist.Fields.ARTISTID, 999_999).limit(1)
        )
        assert len(_results) == 0


class TestFirst:
    def test_first_returns_one(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(Track.query().select().order_by(Track.Fields.TRACKID).limit(1))
        track = _results[0] if _results else None
        assert track is not None
        assert track.TrackId == 1

    def test_first_on_empty_result_returns_none(
        self, chinook: sqlite3.Connection
    ) -> None:
        _results = tuple(
            Artist.query().select().where(Album.Fields.ARTISTID, -1).limit(1)
        )
        result = _results[0] if _results else None
        assert result is None


class TestSelect:
    def test_select_subset(self, chinook: sqlite3.Connection) -> None:
        # Only request the Name column — ArtistId will be absent from the row.
        results = tuple(Artist.query().select(Artist.Fields.NAME).limit(3))
        # Dataclass default kicks in: ArtistId will be 0 (the field default)
        assert all(isinstance(a.Name, str | type(None)) for a in results)
        assert all(a.ArtistId == 0 for a in results)

    def test_select_no_args_fetches_all_fields(
        self, chinook: sqlite3.Connection
    ) -> None:
        results = tuple(Artist.query().select().limit(3))
        assert all(isinstance(r, Artist) for r in results)
        assert all(isinstance(r.ArtistId, int) for r in results)

    def test_iterate_without_select_raises(self, chinook: sqlite3.Connection) -> None:
        with pytest.raises(RuntimeError, match="select()"):
            tuple(Artist.query())


class TestDatetimeCoercion:
    def test_employee_birthdate_is_datetime(self, chinook: sqlite3.Connection) -> None:
        import datetime

        _results = tuple(
            Employee.query().select().where(Employee.Fields.EMPLOYEEID, 1).limit(1)
        )
        emp = _results[0] if _results else None
        assert emp is not None
        assert isinstance(emp.BirthDate, datetime.datetime)
        assert isinstance(emp.HireDate, datetime.datetime)


class TestToSql:
    def test_to_sql_without_select_raises(self, chinook: sqlite3.Connection) -> None:
        with pytest.raises(RuntimeError, match="select()"):
            Artist.query().to_sql()

    def test_to_sql_simple(self, chinook: sqlite3.Connection) -> None:
        sql, params = Artist.query().select().to_sql()
        assert sql == "SELECT ArtistId, Name FROM Artist"
        assert params == []

    def test_to_sql_with_where(self, chinook: sqlite3.Connection) -> None:
        sql, params = Artist.query().select().where(Album.Fields.ARTISTID, 1).to_sql()
        assert sql == "SELECT ArtistId, Name FROM Artist WHERE ArtistId = ?"
        assert params == [1]

    def test_to_sql_with_operator(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Invoice.query()
            .select()
            .where(Invoice.Fields.TOTAL, Operator.GREATER_THAN, 20.0)
            .to_sql()
        )
        assert sql == (
            "SELECT InvoiceId, CustomerId, InvoiceDate, BillingAddress, BillingCity, "
            "BillingState, BillingCountry, BillingPostalCode, Total "
            "FROM Invoice WHERE Total > ?"
        )
        assert params == [20.0]

    def test_to_sql_with_like(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Artist.query()
            .select()
            .where(Artist.Fields.NAME, Operator.LIKE, "The %")
            .to_sql()
        )
        assert sql == "SELECT ArtistId, Name FROM Artist WHERE Name LIKE ?"
        assert params == ["The %"]

    def test_to_sql_with_chained_where(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Album.query()
            .select()
            .where(Album.Fields.ARTISTID, 1)
            .where(Album.Fields.ALBUMID, Operator.GREATER_THAN, 1)
            .to_sql()
        )
        assert (
            sql
            == "SELECT AlbumId, Title, ArtistId FROM Album WHERE ArtistId = ? AND AlbumId > ?"
        )
        assert params == [1, 1]

    def test_to_sql_with_where_in(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Artist.query().select().where_in(Artist.Fields.ARTISTID, [1, 2, 3]).to_sql()
        )
        assert sql == "SELECT ArtistId, Name FROM Artist WHERE ArtistId IN (?,?,?)"
        assert params == [1, 2, 3]

    def test_to_sql_with_order_by(self, chinook: sqlite3.Connection) -> None:
        sql, params = Artist.query().select().order_by(Artist.Fields.NAME).to_sql()
        assert sql == "SELECT ArtistId, Name FROM Artist ORDER BY Name ASC"
        assert params == []

    def test_to_sql_with_order_by_desc(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Invoice.query()
            .select()
            .order_by(Invoice.Fields.TOTAL, Direction.DESCENDING)
            .to_sql()
        )
        assert sql == (
            "SELECT InvoiceId, CustomerId, InvoiceDate, BillingAddress, BillingCity, "
            "BillingState, BillingCountry, BillingPostalCode, Total "
            "FROM Invoice ORDER BY Total DESC"
        )
        assert params == []

    def test_to_sql_with_multiple_order_by(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Track.query()
            .select()
            .order_by(Track.Fields.ALBUMID)
            .order_by(Artist.Fields.NAME, Direction.DESCENDING)
            .to_sql()
        )
        assert sql == (
            "SELECT TrackId, Name, AlbumId, MediaTypeId, GenreId, Composer, "
            "Milliseconds, Bytes, UnitPrice "
            "FROM Track ORDER BY AlbumId ASC, Name DESC"
        )
        assert params == []

    def test_to_sql_with_limit(self, chinook: sqlite3.Connection) -> None:
        sql, params = Artist.query().select().limit(10).to_sql()
        assert sql == "SELECT ArtistId, Name FROM Artist LIMIT 10"
        assert params == []

    def test_to_sql_with_limit_and_offset(self, chinook: sqlite3.Connection) -> None:
        sql, params = Artist.query().select().limit(10).offset(20).to_sql()
        assert sql == "SELECT ArtistId, Name FROM Artist LIMIT 10 OFFSET 20"
        assert params == []

    def test_to_sql_with_select(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Artist.query().select(Artist.Fields.ARTISTID, Artist.Fields.NAME).to_sql()
        )
        assert sql == "SELECT ArtistId, Name FROM Artist"
        assert params == []

    def test_to_sql_with_select_all(self, chinook: sqlite3.Connection) -> None:
        sql, params = Artist.query().select(*Artist.Fields).to_sql()
        assert sql == "SELECT ArtistId, Name FROM Artist"
        assert params == []

    def test_to_sql_complex_query(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Artist.query()
            .select(Artist.Fields.ARTISTID, Artist.Fields.NAME)
            .where(Artist.Fields.NAME, Operator.LIKE, "The %")
            .order_by(Artist.Fields.NAME)
            .limit(5)
            .to_sql()
        )
        assert (
            sql
            == "SELECT ArtistId, Name FROM Artist WHERE Name LIKE ? ORDER BY Name ASC LIMIT 5"
        )
        assert params == ["The %"]

    def test_to_sql_empty_where_in(self, chinook: sqlite3.Connection) -> None:
        sql, params = (
            Artist.query().select().where_in(Artist.Fields.ARTISTID, []).to_sql()
        )
        assert sql == "SELECT ArtistId, Name FROM Artist WHERE 1 = ?"
        assert params == [0]
