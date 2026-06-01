"""Tests that where/order_by/where_in reject fields from the wrong model."""

from collections.abc import Callable

TWO_MODEL_PREAMBLE = """
from dataclasses import dataclass
from icemodel import Model, ModelMeta, add_field_types
from icemodel._query_builder import Operator

@add_field_types
@dataclass(eq=False, frozen=True)
class Alpha(Model):
    _meta = ModelMeta(table="Alpha", id_column="AlphaId")
    AlphaId: int = 0
    Name: str = ""

@add_field_types
@dataclass(eq=False, frozen=True)
class Beta(Model):
    _meta = ModelMeta(table="Beta", id_column="BetaId")
    BetaId: int = 0
    Label: str = ""
"""


class TestCrossModelWhere:
    def test_same_model_where_accepted(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            TWO_MODEL_PREAMBLE
            + """
Alpha.query().where(Alpha.Fields.ALPHAID, Operator.EQUAL, 1)
"""
        )
        assert code == 0, out

    def test_wrong_model_where_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            TWO_MODEL_PREAMBLE
            + """
Alpha.query().where(Beta.Fields.BETAID, Operator.EQUAL, 1)
"""
        )
        assert code != 0
        assert "arg-type" in out or "argument" in out.lower()

    def test_same_model_where_in_accepted(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            TWO_MODEL_PREAMBLE
            + """
Alpha.query().where_in(Alpha.Fields.ALPHAID, [1, 2, 3])
"""
        )
        assert code == 0, out

    def test_wrong_model_where_in_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            TWO_MODEL_PREAMBLE
            + """
Alpha.query().where_in(Beta.Fields.BETAID, [1, 2, 3])
"""
        )
        assert code != 0
        assert "arg-type" in out or "argument" in out.lower()


class TestCrossModelOrderBy:
    def test_same_model_order_by_accepted(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            TWO_MODEL_PREAMBLE
            + """
Alpha.query().order_by(Alpha.Fields.NAME)
"""
        )
        assert code == 0, out

    def test_wrong_model_order_by_rejected(
        self, check: Callable[[str], tuple[str, int]]
    ) -> None:
        out, code = check(
            TWO_MODEL_PREAMBLE
            + """
Alpha.query().order_by(Beta.Fields.LABEL)
"""
        )
        assert code != 0
        assert "arg-type" in out or "argument" in out.lower()
