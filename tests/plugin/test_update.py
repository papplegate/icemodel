"""Tests that update() validates keys and value types against the model's Partial."""

from collections.abc import Callable

from .conftest import MODEL_PREAMBLE

_QUERY = "Book.query().where(Book.Fields.BOOKID, Operator.EQUAL, 1)"

_IMPORTS = """
from icemodel._query_builder import Operator
"""


class TestUpdateAccepts:
    def test_single_valid_key(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Title": "Dune"}})
"""
        )
        assert code == 0, out

    def test_multiple_valid_keys(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Title": "Dune", "Price": 9.99}})
"""
        )
        assert code == 0, out

    def test_empty_dict(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{}})
"""
        )
        assert code == 0, out

    def test_nullable_field_set_to_none(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Year": None}})
"""
        )
        assert code == 0, out

    def test_partial_typed_variable(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
data: Book.Partial = {{"Title": "Dune"}}
{_QUERY}.update(data)
"""
        )
        assert code == 0, out


class TestUpdateRejects:
    def test_unknown_key_caught(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Titlee": "typo"}})
"""
        )
        assert code != 0
        assert "typeddict" in out.lower() or "extra key" in out.lower()

    def test_wrong_value_type_str_field(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Title": 12345}})
"""
        )
        assert code != 0
        assert "typeddict" in out.lower() or "incompatible" in out.lower()

    def test_wrong_value_type_float_field(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Price": "not a float"}})
"""
        )
        assert code != 0
        assert "typeddict" in out.lower() or "incompatible" in out.lower()

    def test_wrong_value_type_nullable_field(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            MODEL_PREAMBLE
            + _IMPORTS
            + f"""
{_QUERY}.update({{"Year": "not an int"}})
"""
        )
        assert code != 0
        assert "typeddict" in out.lower() or "incompatible" in out.lower()
