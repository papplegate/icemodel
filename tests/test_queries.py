"""Read-only query tests against the Chinook database."""

from __future__ import annotations

import sqlite3

import pytest

from tests.models import Album, Artist, Employee, Genre, Invoice, Track


class TestAll:
    def test_returns_all_rows(self, chinook: sqlite3.Connection) -> None:
        artists = Artist.query().all()
        assert len(artists) == 275

    def test_instances_are_typed(self, chinook: sqlite3.Connection) -> None:
        artist = Artist.query().first()
        assert artist is not None
        assert isinstance(artist.ArtistId, int)
        assert isinstance(artist.Name, str | type(None))

    def test_genre_count(self, chinook: sqlite3.Connection) -> None:
        assert Genre.query().count() == 25


class TestWhere:
    def test_equality(self, chinook: sqlite3.Connection) -> None:
        results = Artist.query().where("Name", "AC/DC").all()
        assert len(results) == 1
        assert results[0].ArtistId == 1

    def test_operator_gt(self, chinook: sqlite3.Connection) -> None:
        results = Invoice.query().where("Total", ">", 20).all()
        assert all(inv.Total > 20 for inv in results)
        assert len(results) > 0

    def test_operator_like(self, chinook: sqlite3.Connection) -> None:
        results = Artist.query().where("Name", "LIKE", "The %").all()
        assert all(a.Name is not None and a.Name.startswith("The ") for a in results)
        assert len(results) > 0

    def test_chained_where(self, chinook: sqlite3.Connection) -> None:
        # Albums with ArtistId=1 and AlbumId > 1
        results = (
            Album.query()
            .where("ArtistId", 1)
            .where("AlbumId", ">", 1)
            .all()
        )
        assert all(a.ArtistId == 1 and a.AlbumId > 1 for a in results)

    def test_invalid_operator_raises(self, chinook: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="Invalid operator"):
            Artist.query().where("Name", "DROP TABLE", "x").all()


class TestWhereIn:
    def test_where_in(self, chinook: sqlite3.Connection) -> None:
        results = Artist.query().where_in("ArtistId", [1, 2, 3]).all()
        assert {a.ArtistId for a in results} == {1, 2, 3}

    def test_empty_where_in_returns_nothing(self, chinook: sqlite3.Connection) -> None:
        results = Artist.query().where_in("ArtistId", []).all()
        assert results == []


class TestOrderBy:
    def test_asc(self, chinook: sqlite3.Connection) -> None:
        names = [a.Name for a in Artist.query().order_by("Name").limit(5).all()]
        assert names == sorted(names)

    def test_desc(self, chinook: sqlite3.Connection) -> None:
        totals = [inv.Total for inv in Invoice.query().order_by("Total", "DESC").limit(5).all()]
        assert totals == sorted(totals, reverse=True)

    def test_invalid_direction_raises(self, chinook: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="direction"):
            Artist.query().order_by("Name", "SIDEWAYS")


class TestLimitOffset:
    def test_limit(self, chinook: sqlite3.Connection) -> None:
        assert len(Artist.query().limit(10).all()) == 10

    def test_offset(self, chinook: sqlite3.Connection) -> None:
        first_ten = [a.ArtistId for a in Artist.query().order_by("ArtistId").limit(10).all()]
        second_ten = [
            a.ArtistId
            for a in Artist.query().order_by("ArtistId").limit(10).offset(10).all()
        ]
        assert len(set(first_ten) & set(second_ten)) == 0


class TestFindById:
    def test_finds_existing(self, chinook: sqlite3.Connection) -> None:
        artist = Artist.query().find_by_id(1)
        assert artist is not None
        assert artist.ArtistId == 1
        assert artist.Name == "AC/DC"

    def test_returns_none_for_missing(self, chinook: sqlite3.Connection) -> None:
        assert Artist.query().find_by_id(999_999) is None


class TestFirst:
    def test_first_returns_one(self, chinook: sqlite3.Connection) -> None:
        track = Track.query().order_by("TrackId").first()
        assert track is not None
        assert track.TrackId == 1

    def test_first_on_empty_result_returns_none(self, chinook: sqlite3.Connection) -> None:
        result = Artist.query().where("ArtistId", -1).first()
        assert result is None


class TestSelect:
    def test_select_subset(self, chinook: sqlite3.Connection) -> None:
        # Only request the Name column — ArtistId will be absent from the row.
        results = Artist.query().select("Name").limit(3).all()
        # Dataclass default kicks in: ArtistId will be 0 (the field default)
        assert all(isinstance(a.Name, str | type(None)) for a in results)
        assert all(a.ArtistId == 0 for a in results)


class TestDatetimeCoercion:
    def test_employee_birthdate_is_datetime(self, chinook: sqlite3.Connection) -> None:
        import datetime

        emp = Employee.query().find_by_id(1)
        assert emp is not None
        assert isinstance(emp.BirthDate, datetime.datetime)
        assert isinstance(emp.HireDate, datetime.datetime)
