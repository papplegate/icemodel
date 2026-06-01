"""Schema generation tests."""

import sqlite3

import pytest

from icemodel import schema_for, schema_for_all
from tests.models import Album, Artist, Track


class TestSchemaFor:
    def test_schema_for_artist(self) -> None:
        sql = schema_for(Artist)
        assert "CREATE TABLE Artist" in sql
        assert "ArtistId INTEGER" in sql
        assert "Name TEXT" in sql  # Optional
        assert "PRIMARY KEY (ArtistId)" in sql
        assert "STRICT" in sql

    def test_schema_for_album(self) -> None:
        sql = schema_for(Album)
        assert "CREATE TABLE Album" in sql
        assert "AlbumId INTEGER" in sql
        assert "Title TEXT NOT NULL" in sql
        assert "ArtistId INTEGER NOT NULL" in sql
        assert "PRIMARY KEY (AlbumId)" in sql

    def test_schema_for_track(self) -> None:
        sql = schema_for(Track)
        assert "CREATE TABLE Track" in sql
        assert "TrackId INTEGER" in sql
        assert "Name TEXT NOT NULL" in sql
        assert "AlbumId INTEGER" in sql  # Optional
        assert "PRIMARY KEY (TrackId)" in sql


class TestSchemaForAll:
    def test_schema_for_all_returns_multiple(self) -> None:
        models = [Artist, Album, Track]
        statements = schema_for_all(models)
        assert len(statements) == 3
        assert all("CREATE TABLE" in s for s in statements)

    def test_generated_schema_is_valid_sql(
        self, writable_db: sqlite3.Connection
    ) -> None:
        """Verify generated schema can be executed."""
        from dataclasses import dataclass
        from typing import ClassVar

        from icemodel import Model, ModelMeta

        @dataclass(eq=False, frozen=True)
        class TestModel(Model):
            _meta = ModelMeta(table="TestModel", id_column="id")

            id: int = 0
            name: str = ""
            value: int | None = None

        sql = schema_for(TestModel)
        # Should be able to execute without errors
        writable_db.execute(sql)
        writable_db.commit()

        # Verify table was created
        cursor = writable_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='TestModel'"
        )
        assert cursor.fetchone() is not None

    def test_chinook_schema_generation(self, chinook: sqlite3.Connection) -> None:
        """Generate schema from Chinook models and verify it matches the actual database."""
        from pathlib import Path

        # Extract actual schema from loaded Chinook database
        cursor = chinook.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        actual_tables = {row[0] for row in cursor.fetchall()}

        # Generate schema from models
        from icemodel._model import _model_registry

        chinook_models = [
            _model_registry[name] for name in actual_tables if name in _model_registry
        ]

        generated = schema_for_all(chinook_models)

        # Verify we can create a fresh database from generated schema
        fresh_db = sqlite3.connect(":memory:")
        for stmt in generated:
            fresh_db.execute(stmt)
        fresh_db.commit()

        # Verify the generated database has the same tables as actual Chinook
        cursor = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        generated_tables = {row[0] for row in cursor.fetchall()}

        # All generated tables should exist in actual Chinook
        assert generated_tables.issubset(
            actual_tables
        ), f"Extra tables in generated schema: {generated_tables - actual_tables}"

        # Verify column structure matches for key tables (column names only)
        # Note: we don't compare types since Chinook uses SQL Server types (NVARCHAR)
        # while our models generate SQLite types (TEXT)
        for table in ["Artist", "Album", "Track", "Customer"]:
            actual_cols = chinook.execute(f"PRAGMA table_info({table})").fetchall()
            generated_cols = fresh_db.execute(f"PRAGMA table_info({table})").fetchall()

            # Extract column names only
            actual_names = {row[1] for row in actual_cols}
            generated_names = {row[1] for row in generated_cols}

            assert (
                actual_names == generated_names
            ), f"{table} column names mismatch: {actual_names} vs {generated_names}"
