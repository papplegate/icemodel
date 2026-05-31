"""Relation tests: lazy loading and eager loading (with_related)."""

from __future__ import annotations

import sqlite3

from icemodel._query_builder import Operator
from tests.models import Album, Artist, Customer, Employee, Invoice, Playlist, Track


class TestHasManyLazy:
    def test_artist_albums_lazy(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Artist.query().select().where(Artist.Fields.ARTISTID, 1).limit(1)
        )
        assert len(_results) > 0
        artist = _results[0]
        albums = artist.albums
        assert isinstance(albums, list)
        assert len(albums) > 0
        assert all(isinstance(a, Album) for a in albums)
        assert all(a.ArtistId == 1 for a in albums)

    def test_lazy_result_cached(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Artist.query().select().where(Artist.Fields.ARTISTID, 1).limit(1)
        )
        assert len(_results) > 0
        artist = _results[0]
        first_call = artist.albums
        second_call = artist.albums
        assert first_call is second_call  # same list object — no second query

    def test_customer_invoices(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Customer.query().select().where(Customer.Fields.CUSTOMERID, 1).limit(1)
        )
        assert len(_results) > 0
        customer = _results[0]
        assert all(inv.CustomerId == 1 for inv in customer.invoices)


class TestHasManyEager:
    def test_eager_loads_albums_for_all_artists(
        self, chinook: sqlite3.Connection
    ) -> None:
        artists = tuple(Artist.query().select().with_related("albums").limit(10))
        # Every artist should have the _rel_albums key populated (even if empty list)
        for artist in artists:
            assert f"_rel_albums" in artist.__dict__
            assert all(isinstance(a, Album) for a in artist.albums)

    def test_eager_albums_correct_fk(self, chinook: sqlite3.Connection) -> None:
        artists = tuple(
            Artist.query()
            .select()
            .with_related("albums")
            .where_in(Artist.Fields.ARTISTID, [1, 4])
        )
        by_id = {a.ArtistId: a for a in artists}
        for album in by_id[1].albums:
            assert album.ArtistId == 1
        for album in by_id[4].albums:
            assert album.ArtistId == 4


class TestBelongsToLazy:
    def test_album_artist_lazy(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(Album.query().select().where(Album.Fields.ALBUMID, 1).limit(1))
        assert len(_results) > 0
        album = _results[0]
        artist = album.artist
        assert isinstance(artist, Artist)
        assert artist.ArtistId == album.ArtistId

    def test_track_album_lazy(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(Track.query().select().where(Track.Fields.TRACKID, 1).limit(1))
        assert len(_results) > 0
        track = _results[0]
        album = track.album
        assert isinstance(album, Album)
        assert album.AlbumId == track.AlbumId

    def test_invoice_customer_lazy(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Invoice.query().select().where(Invoice.Fields.INVOICEID, 1).limit(1)
        )
        assert len(_results) > 0
        invoice = _results[0]
        customer = invoice.customer
        assert isinstance(customer, Customer)
        assert customer.CustomerId == invoice.CustomerId


class TestBelongsToEager:
    def test_eager_album_artist(self, chinook: sqlite3.Connection) -> None:
        albums = tuple(Album.query().select().with_related("artist").limit(5))
        for album in albums:
            assert isinstance(album.artist, Artist)
            assert album.artist.ArtistId == album.ArtistId


class TestSelfReferentialRelation:
    def test_employee_manager_lazy(self, chinook: sqlite3.Connection) -> None:
        # EmployeeId=2 reports to EmployeeId=1
        _results = tuple(
            Employee.query().select().where(Employee.Fields.EMPLOYEEID, 2).limit(1)
        )
        assert len(_results) > 0
        emp = _results[0]
        manager = emp.manager
        assert isinstance(manager, Employee)
        assert manager.EmployeeId == emp.ReportsTo

    def test_top_level_employee_has_no_manager(
        self, chinook: sqlite3.Connection
    ) -> None:
        _results = tuple(
            Employee.query().select().where(Employee.Fields.EMPLOYEEID, 1).limit(1)
        )
        assert len(_results) > 0
        emp = _results[0]
        assert emp.manager is None

    def test_direct_reports(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Employee.query().select().where(Employee.Fields.EMPLOYEEID, 1).limit(1)
        )
        assert len(_results) > 0
        boss = _results[0]
        reports = boss.direct_reports
        assert len(reports) > 0
        assert all(r.ReportsTo == 1 for r in reports)


class TestManyToManyLazy:
    def test_playlist_tracks_lazy(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(
            Playlist.query().select().where(Playlist.Fields.PLAYLISTID, 1).limit(1)
        )
        assert len(_results) > 0
        playlist = _results[0]
        tracks = playlist.tracks
        assert isinstance(tracks, list)
        assert len(tracks) > 0
        assert all(isinstance(t, Track) for t in tracks)

    def test_track_playlists_lazy(self, chinook: sqlite3.Connection) -> None:
        _results = tuple(Track.query().select().where(Track.Fields.TRACKID, 1).limit(1))
        assert len(_results) > 0
        track = _results[0]
        playlists = track.playlists
        assert isinstance(playlists, list)
        assert all(isinstance(p, Playlist) for p in playlists)


class TestManyToManyEager:
    def test_eager_playlist_tracks(self, chinook: sqlite3.Connection) -> None:
        playlists = tuple(Playlist.query().select().with_related("tracks").limit(3))
        for pl in playlists:
            assert "_rel_tracks" in pl.__dict__
            assert all(isinstance(t, Track) for t in pl.tracks)

    def test_eager_unknown_relation_raises(self, chinook: sqlite3.Connection) -> None:
        import pytest

        with pytest.raises(AttributeError, match="no relation"):
            tuple(Artist.query().select().with_related("nonexistent"))
