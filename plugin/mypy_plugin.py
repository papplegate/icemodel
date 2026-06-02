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
from mypy.plugin import ClassDefContext, MethodSigContext, Plugin
from mypy.types import (
    AnyType,
    FunctionLike,
    Instance,
    Type,
    TypeOfAny,
    TypeType,
    TypedDictType,
    get_proper_type,
)


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

    enum_meta = ctx.api.named_type_or_none("enum.EnumMeta")
    if enum_meta is not None:
        fields_info.declared_metaclass = enum_meta
        fields_info.metaclass_type = enum_meta

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


def _fields_instance_from_querybuilder(  # pylint: disable=too-many-return-statements
    self_type: Type,
) -> Optional[Instance]:
    """Extract Instance(TFields, []) from a QueryBuilder[T] type.

    Returns None when the model type arg is unresolved (e.g. still a TypeVar),
    which causes the caller to fall back to the original signature.
    """
    proper = get_proper_type(self_type)
    if not isinstance(proper, Instance) or not proper.args:
        return None
    model_type = get_proper_type(proper.args[0])
    if not isinstance(model_type, Instance):
        return None
    fields_sym = model_type.type.names.get("Fields")
    if fields_sym is None:
        return None
    node = fields_sym.node
    if not isinstance(node, Var) or node.type is None:
        return None
    fields_var_type = get_proper_type(node.type)
    if not isinstance(fields_var_type, TypeType):
        return None
    fields_item = get_proper_type(fields_var_type.item)
    if not isinstance(fields_item, Instance):
        return None
    return fields_item


def _partial_type_from_querybuilder(self_type: Type) -> Optional[TypedDictType]:
    """Extract T.Partial TypedDictType from a QueryBuilder[T] type.

    Returns None when the model type arg is unresolved, causing the caller to
    fall back to the original dict[str, Any] signature.
    """
    proper = get_proper_type(self_type)
    if not isinstance(proper, Instance) or not proper.args:
        return None
    model_type = get_proper_type(proper.args[0])
    if not isinstance(model_type, Instance):
        return None
    partial_sym = model_type.type.names.get("Partial")
    if partial_sym is None:
        return None
    node = partial_sym.node
    if not isinstance(node, TypeAlias):
        return None
    target = get_proper_type(node.target)
    if not isinstance(target, TypedDictType):
        return None
    return target


def _column_sig_hook(ctx: MethodSigContext) -> FunctionLike:
    """Narrow the column parameter from Enum to the model's own Fields type."""
    sig = ctx.default_signature
    fields_type = _fields_instance_from_querybuilder(ctx.type)
    if fields_type is None:
        return sig
    new_arg_types = list(sig.arg_types)
    if not new_arg_types:
        return sig
    new_arg_types[0] = fields_type
    return sig.copy_modified(arg_types=new_arg_types)


def _patch_sig_hook(ctx: MethodSigContext) -> FunctionLike:
    """Narrow the data parameter from dict[str, Any] to T.Partial."""
    sig = ctx.default_signature
    partial_type = _partial_type_from_querybuilder(ctx.type)
    if partial_type is None:
        return sig
    new_arg_types = list(sig.arg_types)
    if not new_arg_types:
        return sig
    new_arg_types[0] = partial_type
    return sig.copy_modified(arg_types=new_arg_types)


_COLUMN_METHODS = frozenset(
    {
        "icemodel._query_builder.QueryBuilder.where",
        "icemodel._query_builder.QueryBuilder.where_in",
        "icemodel._query_builder.QueryBuilder.order_by",
    }
)


class IcemodelPlugin(Plugin):
    def get_class_decorator_hook(
        self, fullname: str
    ) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname == "icemodel._model.add_field_types":
            return _add_field_types_hook
        return None

    def get_method_signature_hook(
        self, fullname: str
    ) -> Optional[Callable[[MethodSigContext], FunctionLike]]:
        if fullname in _COLUMN_METHODS:
            return _column_sig_hook
        if fullname == "icemodel._query_builder.QueryBuilder.update":
            return _patch_sig_hook
        return None


def plugin(_version: str) -> type[IcemodelPlugin]:
    return IcemodelPlugin
