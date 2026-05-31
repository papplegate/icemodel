"""Tests for Fields enum synthesis in the mypy plugin."""

from collections.abc import Callable

from .conftest import MODEL_PREAMBLE


class TestFieldsAccepted:
    def test_fields_attribute_exists(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
_ = Book.Fields
"""
        )
        assert code == 0, out

    def test_valid_member_access(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
_ = Book.Fields.TITLE
"""
        )
        assert code == 0, out

    def test_all_members_accessible(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
_ = Book.Fields.BOOKID
_ = Book.Fields.TITLE
_ = Book.Fields.PRICE
_ = Book.Fields.YEAR
"""
        )
        assert code == 0, out

    def test_fields_member_compatible_with_enum(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        # Fields members must be accepted by where(), which takes Enum.
        out, code = check(
            MODEL_PREAMBLE
            + """
from icemodel import Model
q = Book.query().where(Book.Fields.TITLE, "Dune")
"""
        )
        assert code == 0, out

    def test_fields_iterable(self, check: Callable[[str], tuple[str, int]]) -> None:
        # Fields must be iterable so *Book.Fields can be unpacked into select().
        out, code = check(
            MODEL_PREAMBLE
            + """
q = Book.query().select(*Book.Fields)
"""
        )
        assert code == 0, out


class TestFieldsRejects:
    def test_nonexistent_member_caught(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
_ = Book.Fields.COMPLETELY_MADE_UP
"""
        )
        assert code != 0
        assert "attr-defined" in out or "has no attribute" in out
