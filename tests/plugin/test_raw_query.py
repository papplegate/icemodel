"""Tests verifying that mypy correctly type-checks raw_query call sites."""

from collections.abc import Callable

RAW_PREAMBLE = """
from dataclasses import dataclass
from icemodel import RawResultRow, raw_query

@dataclass(frozen=True)
class ArtistRow(RawResultRow):
    ArtistId: int
    Name: str | None

@dataclass(frozen=True)
class ArtistName(RawResultRow):
    Name: str | None
"""


class TestRawQueryTypeAccepts:
    def test_result_typed_as_list_of_result_class(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
rows: tuple[ArtistRow, ...] = raw_query(
    "SELECT ArtistId, Name FROM Artist",
    result_type=ArtistRow,
)
""")
        assert code == 0, out

    def test_int_field_typed_correctly(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
rows = raw_query("SELECT ArtistId, Name FROM Artist", result_type=ArtistRow)
x: int = rows[0].ArtistId
""")
        assert code == 0, out

    def test_optional_field_typed_correctly(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
rows = raw_query("SELECT ArtistId, Name FROM Artist", result_type=ArtistRow)
x: str | None = rows[0].Name
""")
        assert code == 0, out

    def test_result_passable_to_typed_function(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
def consume(rows: tuple[ArtistRow, ...]) -> None: ...

rows = raw_query("SELECT ArtistId, Name FROM Artist", result_type=ArtistRow)
consume(rows)
""")
        assert code == 0, out


class TestRawQueryTypeRejects:
    def test_nonexistent_attribute_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
rows = raw_query("SELECT ArtistId, Name FROM Artist", result_type=ArtistRow)
_ = rows[0].NonExistent
""")
        assert code != 0
        assert "attr-defined" in out or "has no attribute" in out

    def test_field_used_as_wrong_type_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
rows = raw_query("SELECT ArtistId, Name FROM Artist", result_type=ArtistRow)
x: str = rows[0].ArtistId
""")
        assert code != 0
        assert "assignment" in out or "Incompatible types" in out

    def test_non_raw_result_row_class_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
from dataclasses import dataclass

@dataclass
class PlainRow:
    ArtistId: int

rows = raw_query("SELECT ArtistId FROM Artist", result_type=PlainRow)
""")
        assert code != 0
        assert "type-var" in out or "cannot be" in out or "RawResultRow" in out

    def test_wrong_result_type_on_assignment_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(RAW_PREAMBLE + """
rows: tuple[ArtistRow, ...] = raw_query(
    "SELECT Name FROM Artist",
    result_type=ArtistName,
)
""")
        assert code != 0
        assert "assignment" in out or "Incompatible types" in out or "arg-type" in out
