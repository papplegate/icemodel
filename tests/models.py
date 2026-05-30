"""Chinook database model definitions used across the test suite.

All models use ``@add_field_types`` then ``@dataclass(eq=False, frozen=True)`` so that
Model's primary-key equality is preserved rather than the field-wise equality that
@dataclass would generate.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import ClassVar

from icemodel import BelongsTo, HasMany, ManyToMany, Model, ModelMeta, add_field_types


@add_field_types
@dataclass(eq=False, frozen=True)
class Artist(Model):
    _meta = ModelMeta(table="Artist", id_column="ArtistId")

    albums: ClassVar[HasMany] = HasMany(
        "Album", foreign_key="ArtistId", local_key="ArtistId"
    )

    ArtistId: int = 0
    Name: str | None = None


@add_field_types
@dataclass(eq=False, frozen=True)
class Album(Model):
    _meta = ModelMeta(table="Album", id_column="AlbumId")

    artist: ClassVar[BelongsTo] = BelongsTo(
        "Artist", foreign_key="ArtistId", owner_key="ArtistId"
    )
    tracks: ClassVar[HasMany] = HasMany(
        "Track", foreign_key="AlbumId", local_key="AlbumId"
    )

    AlbumId: int = 0
    Title: str = ""
    ArtistId: int = 0


@add_field_types
@dataclass(eq=False, frozen=True)
class Track(Model):
    _meta = ModelMeta(table="Track", id_column="TrackId")

    album: ClassVar[BelongsTo] = BelongsTo(
        "Album", foreign_key="AlbumId", owner_key="AlbumId"
    )
    playlists: ClassVar[ManyToMany] = ManyToMany(
        "Playlist",
        join_table="PlaylistTrack",
        local_fk="TrackId",
        related_fk="PlaylistId",
        local_key="TrackId",
        related_pk="PlaylistId",
    )

    TrackId: int = 0
    Name: str = ""
    AlbumId: int | None = None
    MediaTypeId: int = 0
    GenreId: int | None = None
    Composer: str | None = None
    Milliseconds: int = 0
    Bytes: int | None = None
    UnitPrice: float = 0.0


@add_field_types
@dataclass(eq=False, frozen=True)
class Playlist(Model):
    _meta = ModelMeta(table="Playlist", id_column="PlaylistId")

    tracks: ClassVar[ManyToMany] = ManyToMany(
        "Track",
        join_table="PlaylistTrack",
        local_fk="PlaylistId",
        related_fk="TrackId",
        local_key="PlaylistId",
        related_pk="TrackId",
    )

    PlaylistId: int = 0
    Name: str | None = None


@add_field_types
@dataclass(eq=False, frozen=True)
class Customer(Model):
    _meta = ModelMeta(table="Customer", id_column="CustomerId")

    invoices: ClassVar[HasMany] = HasMany(
        "Invoice", foreign_key="CustomerId", local_key="CustomerId"
    )

    CustomerId: int = 0
    FirstName: str = ""
    LastName: str = ""
    Company: str | None = None
    Address: str | None = None
    City: str | None = None
    State: str | None = None
    Country: str | None = None
    PostalCode: str | None = None
    Phone: str | None = None
    Fax: str | None = None
    Email: str = ""
    SupportRepId: int | None = None


@add_field_types
@dataclass(eq=False, frozen=True)
class Invoice(Model):
    _meta = ModelMeta(table="Invoice", id_column="InvoiceId")

    customer: ClassVar[BelongsTo] = BelongsTo(
        "Customer", foreign_key="CustomerId", owner_key="CustomerId"
    )
    lines: ClassVar[HasMany] = HasMany(
        "InvoiceLine", foreign_key="InvoiceId", local_key="InvoiceId"
    )

    InvoiceId: int = 0
    CustomerId: int = 0
    InvoiceDate: datetime.datetime = datetime.datetime(1970, 1, 1)
    BillingAddress: str | None = None
    BillingCity: str | None = None
    BillingState: str | None = None
    BillingCountry: str | None = None
    BillingPostalCode: str | None = None
    Total: float = 0.0


@add_field_types
@dataclass(eq=False, frozen=True)
class InvoiceLine(Model):
    _meta = ModelMeta(table="InvoiceLine", id_column="InvoiceLineId")

    invoice: ClassVar[BelongsTo] = BelongsTo(
        "Invoice", foreign_key="InvoiceId", owner_key="InvoiceId"
    )

    InvoiceLineId: int = 0
    InvoiceId: int = 0
    TrackId: int = 0
    UnitPrice: float = 0.0
    Quantity: int = 0


@add_field_types
@dataclass(eq=False, frozen=True)
class Employee(Model):
    _meta = ModelMeta(table="Employee", id_column="EmployeeId")

    manager: ClassVar[BelongsTo] = BelongsTo(
        "Employee", foreign_key="ReportsTo", owner_key="EmployeeId"
    )
    direct_reports: ClassVar[HasMany] = HasMany(
        "Employee", foreign_key="ReportsTo", local_key="EmployeeId"
    )

    EmployeeId: int = 0
    LastName: str = ""
    FirstName: str = ""
    Title: str | None = None
    ReportsTo: int | None = None
    BirthDate: datetime.datetime | None = None
    HireDate: datetime.datetime | None = None
    Address: str | None = None
    City: str | None = None
    State: str | None = None
    Country: str | None = None
    PostalCode: str | None = None
    Phone: str | None = None
    Fax: str | None = None
    Email: str | None = None


@add_field_types
@dataclass(eq=False, frozen=True)
class Genre(Model):
    _meta = ModelMeta(table="Genre", id_column="GenreId")

    GenreId: int = 0
    Name: str | None = None
