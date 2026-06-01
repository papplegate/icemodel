# icemodel mypy plugin

The icemodel mypy plugin synthesizes two type-level attributes — `Fields` and `Partial` — on every model class decorated with `@add_field_types`. Without it, mypy has no knowledge of these attributes and cannot check their usage.

## What it provides

### `Fields`

A synthetic enum subtype with one uppercase member per model field. mypy uses it to catch references to non-existent fields at type-check time.

```python
from icemodel._query_builder import Operator

# Caught by mypy with the plugin:
Artist.query().select().where(Artist.Fields.NAEM, Operator.EQUAL, "AC/DC")   # error: has no attribute "NAEM"

# Accepted:
Artist.query().select().where(Artist.Fields.NAME, Operator.EQUAL, "AC/DC")
```

Without the plugin, `Artist.Fields` is typed as `Any` and all member access passes silently.

### `Partial`

A `TypedDict` (with `total=False`, so all keys optional) covering every field on the model. Intended for use as a type annotation on patch data passed to `.patch()`.

```python
data: Artist.Partial = {"Name": "New Name"}          # accepted
data: Artist.Partial = {"Naem": "typo"}              # error: extra key
data: Artist.Partial = {"Name": 99}                  # error: wrong value type
```

`Partial` is annotation-only — it exists as a type for mypy but has no runtime presence. Passing a correctly-typed dict to `.patch()` works normally at runtime.

## How it works

The plugin hooks into mypy's `get_class_decorator_hook` and fires whenever it sees `@add_field_types` applied to a class. It reads the class's declared `Var` members (skipping private names and `ClassVar`s), then:

1. Builds a synthetic `TypeInfo` that subclasses `enum.Enum` and populates it with one member per field (uppercased), registering it as the type of `Fields` on the class.
2. Constructs a `TypedDictType` with `required_keys=set()` (all optional) and registers it as a `TypeAlias` named `Partial` on the class.

Both attributes are injected directly into the class's mypy symbol table, so they behave like ordinarily declared members from the perspective of downstream type checking.

## Configuration

Add the plugin to your mypy configuration:

```toml
# pyproject.toml
[tool.mypy]
plugins = ["plugin.mypy_plugin"]
```

```ini
# mypy.ini or setup.cfg
[mypy]
plugins = plugin.mypy_plugin
```

The path `plugin.mypy_plugin` assumes the `plugin/` directory is on the Python path (i.e. the project root is the working directory or is in `PYTHONPATH`). mypy resolves plugin paths relative to the config file location.

## Limitations

- Only fires on classes decorated with `@add_field_types`. Classes that subclass `Model` without the decorator get no synthesis.
- Field types in `Partial` reflect what mypy knows at decoration time. If a field's type annotation is not yet resolved (e.g. a forward reference in a complex import cycle), mypy may fall back to `Any` for that field.
- `Fields` members are typed as instances of the synthetic enum, not as `str`. This is correct for use with `.where()`, `.order_by()`, and `.select()`, which accept `Enum` arguments.
