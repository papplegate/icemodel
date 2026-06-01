"""Regression tests for Gap 1: Fields and Partial are fully visible to mypy.

These tests mirror the scenarios described at the top of type_gaps.py — valid
accesses pass and invalid ones are caught — and serve as a permanent record
that this gap stays fixed.
"""

from collections.abc import Callable

from .conftest import MODEL_PREAMBLE

_QUERY_PREAMBLE = (
    MODEL_PREAMBLE
    + """
from icemodel._query_builder import Operator
"""
)


class TestFieldsVisible:
    def test_valid_field_member_passes(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(MODEL_PREAMBLE + "_ = Book.Fields.BOOKID\n")
        assert code == 0, out

    def test_nonexistent_field_member_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(MODEL_PREAMBLE + "_ = Book.Fields.NONEXISTENT\n")
        assert code != 0
        assert "attr-defined" in out or "has no attribute" in out

    def test_fields_member_accepted_by_where(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            _QUERY_PREAMBLE
            + "Book.query().where(Book.Fields.TITLE, Operator.EQUAL, 'x')\n"
        )
        assert code == 0, out


class TestPartialVisible:
    def test_valid_partial_annotation_passes(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(MODEL_PREAMBLE + 'data: Book.Partial = {"Title": "x"}\n')
        assert code == 0, out

    def test_unknown_partial_key_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(MODEL_PREAMBLE + 'data: Book.Partial = {"Titlee": "typo"}\n')
        assert code != 0
        assert "typeddict" in out.lower() or "extra key" in out.lower()

    def test_wrong_partial_value_type_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(MODEL_PREAMBLE + 'data: Book.Partial = {"Title": 999}\n')
        assert code != 0
        assert "typeddict" in out.lower() or "incompatible" in out.lower()
