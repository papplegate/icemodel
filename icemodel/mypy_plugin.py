from typing import Callable, Optional

from mypy.nodes import MDEF, SymbolTableNode, Var
from mypy.plugin import ClassDefContext, Plugin
from mypy.types import AnyType, TypeOfAny


def _add_field_types_hook(ctx: ClassDefContext) -> None:
    if ctx.cls.info is None:
        return
    for name in ("Fields", "Partial"):
        var = Var(name, AnyType(TypeOfAny.special_form))
        var.info = ctx.cls.info
        ctx.cls.info.names[name] = SymbolTableNode(MDEF, var)


class IcemodelPlugin(Plugin):
    def get_class_decorator_hook(
        self, fullname: str
    ) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname == "icemodel._model.add_field_types":
            return _add_field_types_hook
        return None


def plugin(_version: str) -> type[IcemodelPlugin]:
    return IcemodelPlugin
