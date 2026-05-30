from typing import Callable, Optional

from mypy.nodes import MDEF, SymbolTableNode, TypeAlias, Var
from mypy.plugin import ClassDefContext, Plugin
from mypy.types import AnyType, Type, TypeOfAny, TypedDictType


def _get_dataclass_fields(ctx: ClassDefContext) -> dict[str, Type]:
    result: dict[str, Type] = {}
    for name, sym in ctx.cls.info.names.items():
        if name.startswith("_"):
            continue
        node = sym.node
        if not isinstance(node, Var):
            continue
        if node.is_classvar:
            continue
        result[name] = node.type or AnyType(TypeOfAny.special_form)
    return result


def _synthesize_fields(
    ctx: ClassDefContext,
) -> None:
    # Typed as Any: synthesizing a proper Enum subtype with named members requires
    # registering the TypeInfo in the module symbol table, which the ClassDefContext
    # API does not expose. The runtime Fields enum handles member access; this just
    # makes the attribute visible to mypy.
    info = ctx.cls.info
    var = Var("Fields", AnyType(TypeOfAny.special_form))
    var.info = info
    info.names["Fields"] = SymbolTableNode(MDEF, var)


def _synthesize_partial(ctx: ClassDefContext, field_items: dict[str, Type]) -> None:
    info = ctx.cls.info
    str_type = ctx.api.named_type("builtins.str")
    object_type = ctx.api.named_type("builtins.object")
    dict_fallback = ctx.api.named_type("builtins.dict", [str_type, object_type])

    td_type = TypedDictType(
        items=field_items,
        required_keys=set(),  # total=False — all fields optional
        readonly_keys=set(),
        fallback=dict_fallback,
    )
    alias = TypeAlias(
        target=td_type,
        fullname=f"{info.fullname}.Partial",
        module=info.module_name,
        line=ctx.cls.line,
        column=ctx.cls.column,
    )
    info.names["Partial"] = SymbolTableNode(MDEF, alias)


def _add_field_types_hook(ctx: ClassDefContext) -> None:
    if ctx.cls.info is None:
        return
    field_items = _get_dataclass_fields(ctx)
    _synthesize_fields(ctx)
    _synthesize_partial(ctx, field_items)


class IcemodelPlugin(Plugin):
    def get_class_decorator_hook(
        self, fullname: str
    ) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname == "icemodel._model.add_field_types":
            return _add_field_types_hook
        return None


def plugin(_version: str) -> type[IcemodelPlugin]:
    return IcemodelPlugin
