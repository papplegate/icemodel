"""Tests for Partial TypedDict synthesis in the mypy plugin."""

from collections.abc import Callable

from .conftest import MODEL_PREAMBLE


class TestPartialAccepts:
    def test_single_valid_field(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Title": "Dune"}
"""
        )
        assert code == 0, out

    def test_multiple_valid_fields(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Title": "Dune", "Price": 9.99}
"""
        )
        assert code == 0, out

    def test_empty_dict(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {}
"""
        )
        assert code == 0, out

    def test_nullable_field_set_to_none(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Year": None}
"""
        )
        assert code == 0, out

    def test_all_fields(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"BookId": 1, "Title": "Dune", "Price": 9.99, "Year": 1965}
"""
        )
        assert code == 0, out


class TestPartialRejects:
    def test_unknown_key(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Titlee": "typo"}
"""
        )
        assert code != 0
        assert "typeddict-unknown-key" in out or "Extra key" in out

    def test_wrong_value_type_str_field(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Title": 12345}
"""
        )
        assert code != 0
        assert "typeddict-item" in out or "Incompatible types" in out

    def test_wrong_value_type_float_field(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Price": "not a float"}
"""
        )
        assert code != 0
        assert "typeddict-item" in out or "Incompatible types" in out

    def test_wrong_value_type_nullable_field(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + """
data: Book.Partial = {"Year": "not an int"}
"""
        )
        assert code != 0
        assert "typeddict-item" in out or "Incompatible types" in out
