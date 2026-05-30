"""Schema generation from model definitions."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING, Any, cast, get_args, get_origin, get_type_hints

from ._model import _model_registry
from ._relations import Relation

if TYPE_CHECKING:
    from ._model import Model


def _python_to_sqlite_type(python_type: Any) -> str:
    """Convert Python type annotation to SQLite type."""
    origin = get_origin(python_type)

    # Handle Optional[X] (Union[X, None])
    none_type = type(None)  # pylint: disable=unidiomatic-typecheck
    if origin is none_type:
        return "NULL"
    if origin is not None:
        # It's a generic like Union, Optional, etc.
        args = get_args(python_type)
        # Filter out NoneType to get the actual type
        non_none_args = [
            arg for arg in args if arg is not none_type
        ]  # pylint: disable=unidiomatic-typecheck
        if non_none_args:
            return _python_to_sqlite_type(non_none_args[0])

    # Direct type mapping
    if python_type in (int, float, str, bool, bytes):
        type_map = {
            int: "INTEGER",
            str: "TEXT",
            float: "REAL",
            bool: "INTEGER",
            bytes: "BLOB",
        }
        return type_map[python_type]

    # Fallback
    return "TEXT"


def _is_required(python_type: Any) -> bool:
    """Check if a field is required (not Optional)."""
    origin = get_origin(python_type)
    if origin is not None:
        args = get_args(python_type)
        return type(None) not in args
    return True


def schema_for(model_class: type[Model]) -> str:  # pylint: disable=too-many-locals
    """Generate CREATE TABLE statement for a model.

    Args:
        model_class: A Model subclass.

    Returns:
        A CREATE TABLE SQL statement.
    """
    from ._relations import BelongsTo  # pylint: disable=import-outside-toplevel

    meta = model_class._meta  # pylint: disable=protected-access
    table_name = meta.table
    id_column = meta.id_column

    # Get type hints to resolve string annotations
    hints = get_type_hints(model_class)

    # Get all dataclass fields
    field_specs = []
    for field in fields(cast(Any, model_class)):
        if field.name.startswith("_"):
            continue
        # Use resolved type hint instead of field.type (which may be a string)
        field_type = hints.get(field.name, field.type)
        sqlite_type = _python_to_sqlite_type(field_type)
        is_required = _is_required(field_type)
        constraint = " NOT NULL" if is_required and field.name != id_column else ""
        field_specs.append(f"  {field.name} {sqlite_type}{constraint}")

    # Add primary key
    pk_spec = f"  PRIMARY KEY ({id_column})"
    field_specs.append(pk_spec)

    # Add foreign key constraints from BelongsTo relations
    relations: dict[str, Relation] = getattr(model_class, "__relations__", {})
    for relation in relations.values():
        if isinstance(relation, BelongsTo):
            fk_col = relation.foreign_key
            related_model_name = relation._related  # pylint: disable=protected-access
            owner_key = relation.owner_key
            fk_spec = (
                f"  FOREIGN KEY ({fk_col}) REFERENCES {related_model_name}({owner_key})"
            )
            field_specs.append(fk_spec)

    fields_str = ",\n".join(field_specs)
    return f"CREATE TABLE {table_name} (\n{fields_str}\n) STRICT;"


def schema_for_all(models: list[type[Model]] | None = None) -> list[str]:
    """Generate CREATE TABLE statements for all models.

    Args:
        models: List of model classes. If None, uses all registered models.

    Returns:
        List of CREATE TABLE statements in dependency order.
    """
    if models is None:
        models = list(_model_registry.values())

    # For now, return in arbitrary order (dependency ordering is complex)
    # In practice, users should create tables in order or use PRAGMA foreign_keys OFF
    return [schema_for(model) for model in models]


if __name__ == "__main__":
    # CLI: generate schema for all models
    import sys

    # Try to import models from common locations
    try:
        # Check if we can import from the current directory
        import importlib.util

        spec = importlib.util.spec_from_file_location("models", "models.py")
        if spec and spec.loader:
            models_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(models_module)
    except (ImportError, FileNotFoundError):
        pass

    statements = schema_for_all()
    if statements:
        for stmt in statements:
            print(stmt)
            print()
    else:
        print(
            "No models found. Make sure to import your model definitions.",
            file=sys.stderr,
        )
        sys.exit(1)
