"""Pytest fixtures for the icemodel test suite.

``chinook`` is session-scoped (loaded once, read-only). Uses the Chinook sample
database (https://github.com/lerocha/chinook-database) by Luis Rocha, licensed
under the MIT License.

``writable_db`` is function-scoped (fresh in-memory DB per test, for CRUD tests).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from icemodel import Model

# Import models so they register in _model_registry before any test runs.
import tests.models  # noqa: F401

CHINOOK_SQL = Path(__file__).parent / "chinook.sql"

_WRITABLE_SCHEMA = """
CREATE TABLE Book (
    BookId   INTEGER NOT NULL,
    Title    TEXT    NOT NULL,
    Author   TEXT,
    Year     INTEGER,
    Price    REAL    NOT NULL DEFAULT 0.0,
    PRIMARY KEY (BookId)
) STRICT;

CREATE TABLE Tag (
    TagId  INTEGER NOT NULL,
    Label  TEXT    NOT NULL,
    PRIMARY KEY (TagId)
) STRICT;

CREATE TABLE BookTag (
    BookId INTEGER NOT NULL,
    TagId  INTEGER NOT NULL,
    PRIMARY KEY (BookId, TagId)
) STRICT;

CREATE TABLE ValidatedModel (
    id    INTEGER NOT NULL,
    name  TEXT    NOT NULL,
    email TEXT    NOT NULL,
    age   INTEGER NOT NULL,
    PRIMARY KEY (id)
) STRICT;

CREATE TABLE NullableModel (
    id    INTEGER NOT NULL,
    email TEXT,
    PRIMARY KEY (id)
) STRICT;
"""


@pytest.fixture(scope="session")
def chinook() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(CHINOOK_SQL.read_text(encoding="utf-8"))
    Model.bind(conn)
    return conn


@pytest.fixture
def writable_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_WRITABLE_SCHEMA)
    Model.bind(conn)
    return conn
