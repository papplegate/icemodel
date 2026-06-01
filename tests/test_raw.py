"""Tests for raw_query and RawResultRow."""

import dataclasses
import re
import sqlite3

import pytest

from icemodel import (
    RawResultRow,
    raw_query,
    require_bytes,
    require_float,
    require_int,
    require_not_none,
    require_str,
)


@dataclasses.dataclass(frozen=True)
class ArtistRow(RawResultRow):
    ArtistId: int
    Name: str | None


@dataclasses.dataclass(frozen=True)
class ArtistName(RawResultRow):
    Name: str | None


@dataclasses.dataclass(frozen=True)
class AggRow(RawResultRow):
    artist_count: int


@dataclasses.dataclass(frozen=True)
class ArtistWithDefault(RawResultRow):
    ArtistId: int
    Name: str | None = None


@dataclasses.dataclass(frozen=True)
class ValidatedArtist(RawResultRow):
    ArtistId: int
    Name: str

    def __post_init__(self) -> None:
        if not self.Name:
            raise ValueError("Name must be non-empty")


@dataclasses.dataclass(frozen=True)
class LineTotal(RawResultRow):
    InvoiceLineId: int
    line_total: float


@dataclasses.dataclass(frozen=True)
class AlbumCountByArtist(RawResultRow):
    ArtistId: int
    Name: str | None
    album_count: int


@dataclasses.dataclass(frozen=True)
class CustomerRevenue(RawResultRow):
    CustomerId: int
    total_spent: float


@dataclasses.dataclass(frozen=True)
class WholeNumberResult(RawResultRow):
    amount: float


class TestRawResultRow:
    def test_subclass_is_frozen_dataclass(self) -> None:
        assert dataclasses.is_dataclass(ArtistRow)
        row = ArtistRow(ArtistId=1, Name="AC/DC")
        with pytest.raises(dataclasses.FrozenInstanceError):
            row.Name = "changed"  # type: ignore[misc]

    def test_subclass_is_instance_of_raw_result_row(self) -> None:
        row = ArtistRow(ArtistId=1, Name="AC/DC")
        assert isinstance(row, RawResultRow)


class TestRawQueryBasic:
    def test_returns_instances(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            "SELECT ArtistId, Name FROM Artist WHERE ArtistId = ?",
            [1],
            result_type=ArtistRow,
        )
        assert len(rows) == 1
        assert rows[0].ArtistId == 1
        assert rows[0].Name == "AC/DC"

    def test_returns_correct_type(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            "SELECT ArtistId, Name FROM Artist LIMIT 3", result_type=ArtistRow
        )
        assert len(rows) == 3
        assert all(isinstance(r, ArtistRow) for r in rows)

    def test_empty_result_returns_empty_tuple(
        self, chinook: sqlite3.Connection
    ) -> None:
        rows = raw_query(
            "SELECT ArtistId, Name FROM Artist WHERE ArtistId = ?",
            [-1],
            result_type=ArtistRow,
        )
        assert rows == ()

    def test_no_params_defaults(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            "SELECT COUNT(*) AS artist_count FROM Artist", result_type=AggRow
        )
        assert len(rows) == 1
        assert rows[0].artist_count == 275

    def test_subset_of_columns(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query("SELECT Name FROM Artist LIMIT 2", result_type=ArtistName)
        assert all(isinstance(r, ArtistName) for r in rows)
        assert all(hasattr(r, "Name") for r in rows)
        assert not any(hasattr(r, "ArtistId") for r in rows)


class TestRawQueryExtraColumns:
    def test_extra_columns_are_ignored(self, chinook: sqlite3.Connection) -> None:
        # Query returns ArtistId + Name, but ArtistName only has Name
        rows = raw_query(
            "SELECT ArtistId, Name FROM Artist LIMIT 1",
            result_type=ArtistName,
        )
        assert len(rows) == 1
        assert isinstance(rows[0], ArtistName)
        assert not hasattr(rows[0], "ArtistId")


class TestRawQueryDefaultParams:
    def test_missing_optional_field_uses_default(
        self, chinook: sqlite3.Connection
    ) -> None:
        # ArtistWithDefault.Name has a default — query needn't return it
        rows = raw_query(
            "SELECT ArtistId FROM Artist LIMIT 1",
            result_type=ArtistWithDefault,
        )
        assert len(rows) == 1
        assert rows[0].Name is None


class TestRawQueryConstructorValidation:
    def test_constructor_validation_runs(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            "SELECT ArtistId, Name FROM Artist WHERE ArtistId = 1",
            result_type=ValidatedArtist,
        )
        assert rows[0].Name == "AC/DC"

    def test_constructor_can_reject_rows(self, chinook: sqlite3.Connection) -> None:
        # Force a NULL Name; ValidatedArtist.__post_init__ should raise
        with pytest.raises(ValueError, match="non-empty"):
            raw_query(
                "SELECT ArtistId, NULL AS Name FROM Artist LIMIT 1",
                result_type=ValidatedArtist,
            )


class TestRawQueryComputedColumns:
    def test_arithmetic_expression(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            "SELECT InvoiceLineId, UnitPrice * Quantity AS line_total FROM InvoiceLine",
            result_type=LineTotal,
        )
        assert all(isinstance(r, LineTotal) for r in rows)
        assert all(r.line_total > 0 for r in rows)

    def test_aggregate_with_group_by(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            "SELECT CustomerId, SUM(Total) AS total_spent FROM Invoice GROUP BY CustomerId",
            result_type=CustomerRevenue,
        )
        assert all(isinstance(r, CustomerRevenue) for r in rows)
        assert all(r.total_spent > 0 for r in rows)

    def test_join_with_computed_column(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query(
            """
            SELECT ar.ArtistId, ar.Name, COUNT(al.AlbumId) AS album_count
            FROM Artist ar
            LEFT JOIN Album al ON al.ArtistId = ar.ArtistId
            GROUP BY ar.ArtistId
            HAVING album_count > 0
            """,
            result_type=AlbumCountByArtist,
        )
        assert all(isinstance(r, AlbumCountByArtist) for r in rows)
        assert all(r.album_count > 0 for r in rows)

    def test_computed_column_value_is_correct(
        self, chinook: sqlite3.Connection
    ) -> None:
        rows = raw_query(
            "SELECT InvoiceLineId, UnitPrice * Quantity AS line_total"
            " FROM InvoiceLine WHERE InvoiceLineId = 1",
            result_type=LineTotal,
        )
        assert len(rows) == 1
        assert rows[0].line_total == pytest.approx(0.99)


class TestRawQueryTypeCoercion:
    def test_integer_db_value_coerced_to_float(
        self, chinook: sqlite3.Connection
    ) -> None:
        # SELECT 2 returns int from SQLite; the float annotation must trigger coercion.
        rows = raw_query("SELECT 2 AS amount", result_type=WholeNumberResult)
        assert len(rows) == 1
        assert isinstance(rows[0].amount, float)
        assert rows[0].amount == 2.0

    def test_fractional_float_unchanged(self, chinook: sqlite3.Connection) -> None:
        rows = raw_query("SELECT 2.5 AS amount", result_type=WholeNumberResult)
        assert rows[0].amount == 2.5
        assert isinstance(rows[0].amount, float)


class TestRawQueryErrors:
    def test_missing_required_column_raises(self, chinook: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="missing required columns"):
            raw_query("SELECT Name FROM Artist LIMIT 1", result_type=ArtistRow)

    def test_bad_sql_raises_operational_error(
        self, chinook: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.OperationalError, match="Failed query"):
            raw_query("SELECT * FROM nonexistent_table", result_type=ArtistRow)

    def test_error_message_includes_sql(self, chinook: sqlite3.Connection) -> None:
        bad_sql = "SELECT * FROM no_such_table"
        with pytest.raises(sqlite3.OperationalError, match=re.escape(bad_sql)):
            raw_query(bad_sql, result_type=ArtistRow)


class TestRequireInt:
    def test_accepts_int(self) -> None:
        require_int(42)

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="expected int, got float"):
            require_int(1.0)

    def test_rejects_str(self) -> None:
        with pytest.raises(TypeError, match="expected int, got str"):
            require_int("1")

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="expected int, got NoneType"):
            require_int(None)


class TestRequireFloat:
    def test_accepts_float(self) -> None:
        require_float(3.14)

    def test_rejects_int(self) -> None:
        with pytest.raises(TypeError, match="expected float, got int"):
            require_float(2)

    def test_rejects_str(self) -> None:
        with pytest.raises(TypeError, match="expected float, got str"):
            require_float("3.14")

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="expected float, got NoneType"):
            require_float(None)


class TestRequireStr:
    def test_accepts_str(self) -> None:
        require_str("hello")

    def test_accepts_empty_str(self) -> None:
        require_str("")

    def test_rejects_int(self) -> None:
        with pytest.raises(TypeError, match="expected str, got int"):
            require_str(1)

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="expected str, got NoneType"):
            require_str(None)


class TestRequireBytes:
    def test_accepts_bytes(self) -> None:
        require_bytes(b"data")

    def test_rejects_str(self) -> None:
        with pytest.raises(TypeError, match="expected bytes, got str"):
            require_bytes("data")

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="expected bytes, got NoneType"):
            require_bytes(None)


class TestRequireNotNone:
    def test_accepts_int(self) -> None:
        require_not_none(0)

    def test_accepts_empty_str(self) -> None:
        require_not_none("")

    def test_accepts_false(self) -> None:
        require_not_none(False)

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError, match="got None"):
            require_not_none(None)
