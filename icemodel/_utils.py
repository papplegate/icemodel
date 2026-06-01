import dataclasses
import datetime
import types
import typing
from typing import Any

# Stored as a constant to avoid calling type() in comparisons (pylint C0123).
_NoneType: type = type(None)


def _unwrap_optional(hint: Any) -> Any:
    """Unwrap Optional[X] or X | None to X. Returns hint unchanged otherwise."""
    origin = typing.get_origin(hint)
    # typing.Union — covers Optional[X] = Union[X, None]
    if origin is typing.Union:
        args = [a for a in typing.get_args(hint) if a is not _NoneType]
        return args[0] if len(args) == 1 else hint
    # Python 3.10+ X | Y union syntax (types.UnionType)
    if isinstance(hint, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not _NoneType]
        return args[0] if len(args) == 1 else hint
    return hint


def _coerce_row(model_class: type[Any], data: dict[str, Any]) -> dict[str, Any]:
    """Coerce DB values to Python types declared on a dataclass model.

    Currently handles TEXT → datetime.datetime and TEXT → datetime.date.
    """
    if not dataclasses.is_dataclass(model_class):
        return data
    try:
        hints = typing.get_type_hints(model_class)
    except (NameError, AttributeError, TypeError):  # pragma: no cover
        return data

    result: dict[str, Any] = {}
    for k, v in data.items():
        hint = hints.get(k)
        if hint is not None and v is not None:
            inner = _unwrap_optional(hint)
            if inner is datetime.datetime and isinstance(v, str):
                v = datetime.datetime.fromisoformat(v)
            elif inner is datetime.date and isinstance(v, str):
                v = datetime.date.fromisoformat(v)
            elif inner is float and isinstance(v, int):
                v = float(v)
        result[k] = v
    return result


def validate_model(model_instance: Any) -> None:
    """Validate a model instance using field validators.

    Field validators are defined via dataclass field metadata: {"validator": callable}.
    The validator should be a callable(value) -> bool that returns True if valid.
    Raises ValueError if any field fails validation.
    """
    if not dataclasses.is_dataclass(model_instance):
        return

    for field in dataclasses.fields(model_instance):
        if "validator" not in field.metadata:
            continue

        validator = field.metadata["validator"]
        value = getattr(model_instance, field.name)

        # Skip validation for None values (assume nullable fields are optional)
        if value is None:
            continue

        # Call validator; if it returns False, raise ValueError
        if not validator(value):
            raise ValueError(f"Validation failed for {field.name}={value!r}")


def validate_fields(model_class: type[Any], data: dict[str, Any]) -> None:
    """Validate a dictionary of field values against field validators.

    Used for patch() operations where only some fields are being updated.
    Only validates fields that are present in data and have validators.
    """
    if not dataclasses.is_dataclass(model_class):
        return

    field_map = {f.name: f for f in dataclasses.fields(model_class)}
    for field_name, value in data.items():
        if field_name not in field_map:
            continue

        field = field_map[field_name]
        if "validator" not in field.metadata:
            continue

        validator = field.metadata["validator"]

        # Skip validation for None values
        if value is None:
            continue

        # Call validator; if it returns False, raise ValueError
        if not validator(value):
            raise ValueError(f"Validation failed for {field_name}={value!r}")


def from_row(model_class: type[Any], row: Any) -> Any:
    """Instantiate a model from a sqlite3.Row with validation.

    For dataclass models: filters to declared fields, coerces types, validates, calls __init__.
    For plain Model subclasses: falls back to __new__ + __dict__ update.
    """
    data = dict(row)
    if dataclasses.is_dataclass(model_class):
        field_names = {f.name for f in dataclasses.fields(model_class)}
        filtered = {k: v for k, v in data.items() if k in field_names}
        instance = model_class(**_coerce_row(model_class, filtered))
        validate_model(instance)
        return instance
    obj: Any = object.__new__(model_class)
    obj.__dict__.update(data)
    return obj
