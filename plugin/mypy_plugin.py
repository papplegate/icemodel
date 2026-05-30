from typing import Callable, Optional

from mypy.nodes import (
    MDEF,
    Block,
    ClassDef,
    PassStmt,
    SymbolTable,
    SymbolTableNode,
    TypeAlias,
    TypeInfo,
    Var,
)
from mypy.plugin import ClassDefContext, Plugin
from mypy.types import AnyType, Instance, Type, TypeOfAny, TypeType, TypedDictType


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


def _synthesize_fields(ctx: ClassDefContext, field_items: dict[str, Type]) -> None:
    info = ctx.cls.info
    enum_instance = ctx.api.named_type_or_none("enum.Enum")
    if enum_instance is None:
        var = Var("Fields", AnyType(TypeOfAny.special_form))
        var.info = info
        info.names["Fields"] = SymbolTableNode(MDEF, var)
        return

    # Register the TypeInfo under a private name in the class's own namespace.
    # This gives it a resolvable fullname (<class>.__<Name>Fields__) that fixup
    # can find without conflicting with the public 'Fields' Var.
    private_name = f"__{ctx.cls.name}Fields__"

    fields_cls_def = ClassDef(f"{ctx.cls.name}Fields", Block([PassStmt()]))
    fields_cls_def.fullname = f"{info.fullname}.{private_name}"
    fields_info = TypeInfo(SymbolTable(), fields_cls_def, info.module_name)
    fields_info.bases = [enum_instance]
    fields_info.mro = [fields_info] + enum_instance.type.mro
    fields_info.is_enum = True
    fields_cls_def.info = fields_info

    fields_instance = Instance(fields_info, [])
    for field_name in field_items:
        member = Var(field_name.upper(), fields_instance)
        member.info = fields_info
        # pylint: disable-next=unsupported-assignment-operation
        fields_info.names[field_name.upper()] = SymbolTableNode(MDEF, member)

    # Register TypeInfo in class names under private name so fixup resolves it.
    info.names[private_name] = SymbolTableNode(MDEF, fields_info)

    var = Var("Fields", TypeType(fields_instance))
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
    _synthesize_fields(ctx, field_items)
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
