"""Tests for Fields enum synthesis in the mypy plugin.

Fields is currently typed as Any, so member access is not checked by mypy.
These tests document both current behaviour and the remaining gap.
"""

from collections.abc import Callable

from .conftest import MODEL_PREAMBLE


class TestFieldsAccepted:
    def test_fields_attribute_exists(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(MODEL_PREAMBLE + """
_ = Book.Fields
""")
        assert code == 0, out

    def test_valid_member_access(self, check: Callable[[str], tuple[str, int]]) -> None:
        out, code = check(MODEL_PREAMBLE + """
_ = Book.Fields.TITLE
""")
        assert code == 0, out


class TestFieldsGap:
    def test_nonexistent_member_not_caught(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        # Fields is typed as Any — mypy cannot catch this invalid member.
        # Synthesizing a proper Enum subtype requires module-level TypeInfo
        # registration not available through ClassDefContext.
        out, code = check(MODEL_PREAMBLE + """
_ = Book.Fields.COMPLETELY_MADE_UP
""")
        assert code == 0, (
            "This should pass (gap): Fields is Any so mypy accepts any member. "
            "If this assertion fails, Fields typing has been improved."
        )
