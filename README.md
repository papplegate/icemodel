# icemodel

A minimal, dependency-free ORM for Python inspired by [objection.js](https://vincit.github.io/objection.js/). Fluent query builder, relations with lazy and eager loading, SQLite backend.

icemodel treats frozen dataclasses as the single source of truth for both models and query results. Every value that crosses the database boundary — whether fetched through the ORM or via a raw SQL query — arrives as an immutable, typed Python object whose shape is declared in code and checked by mypy. The raw query escape hatch is a first-class feature: write arbitrary SQL for joins, aggregations, and window functions, declare the expected result shape as a `RawResultRow` subclass, and get back a typed, validated, frozen dataclass. Most Python database libraries return dicts or loosely-typed row objects and leave interpretation to the caller; icemodel enforces the contract at the boundary so the rest of your code can rely on it.

## Comparison

### vs Other Python ORMs (SQLAlchemy, Django ORM, Tortoise ORM)

| Feature | icemodel | Major ORMs |
|---------|----------|-----------|
| Dependencies | Zero | Multiple |
| Setup complexity | Minimal | Moderate-Complex |
| Type safety | mypy strict | Varies |
| Immutability | Enforced (frozen dataclasses) | Mutable instances |
| Dirty tracking | Manual (via `replace()` + `patch()`) | Automatic |
| Query API | Fluent, composable | Varies (SQLAlchemy is fluent) |
| Databases | SQLite only | Multiple (Postgres, MySQL, etc.) |
| Migrations | Separate tool | Built-in |
| Code size | ~500 LOC | Thousands of LOC |

**When to use icemodel:**
- Small-to-medium projects
- SQLite is sufficient
- You want minimal dependencies
- You prefer explicit over implicit (frozen dataclasses, manual updates)
- You like readable, auditable code

**When to use major ORMs:**
- Multi-database support needed
- Built-in migrations required
- Complex relationships (polymorphism, etc.)
- Automatic dirty tracking desired

### vs Objection.js

icemodel is inspired by [Objection.js](https://vincit.github.io/objection.js/) but tailored for Python:

- **Similar**: Fluent query builder, relations with lazy/eager loading, emphasis on SQL (not hiding it)
- **Different**: Python dataclasses instead of JavaScript classes, frozen instances for immutability, SQLite only (Objection supports any SQL database)

### vs Raw SQL

| Aspect | icemodel | Raw SQL |
|--------|----------|---------|
| Type safety | ✓ mypy strict | ✗ All strings |
| SQL injection prevention | ✓ Auto-parameterized | Manual |
| Type coercion | ✓ Datetime, etc. | Manual casting |
| Model hydration | ✓ Auto row→instance | Manual |
| Relation loading | ✓ Lazy/eager | Manual joins |
| Composable queries | ✓ Builder pattern | String concat |
| Debugging | ✓ `query.to_sql()` | Direct SQL |
| Escape hatch | ✓ Raw SQL when needed | N/A |

**Use icemodel when:** Type safety, composable queries, and automatic hydration matter.

**Use raw SQL when:** Complex analytics, performance-critical queries, or you need full control.

icemodel doesn't hide SQL — use `query.to_sql()` to inspect generated queries anytime.

## Limitations (Intentional)

- **SQLite only** — no other databases
- **No migrations** — use a migration tool separately
- **No N+1 prevention** — use `with_related()` for eager loading
- **No automatic dirty tracking** — mutate via `dataclasses.replace()` + `patch()`
- **No lazy properties** — relations are eagerly computed on access or pre-loaded with `with_related()`

## Installation

icemodel requires Python 3.12 or later. Install it with pip:

```bash
pip install icemodel
```

No further dependencies are needed for runtime use — icemodel relies only on the Python standard library.

## Quick Start

### Define Models

Models are frozen dataclasses with a `_meta` ModelMeta instance for table metadata:

```python
from dataclasses import dataclass
from typing import ClassVar
from icemodel import Model, ModelMeta, HasMany, BelongsTo, add_field_types

@add_field_types
@dataclass(eq=False, frozen=True)
class Artist(Model):
    _meta = ModelMeta(table="Artist", id_column="ArtistId")
    
    albums: ClassVar[HasMany] = HasMany(
        "Album", foreign_key="ArtistId", local_key="ArtistId"
    )
    
    ArtistId: int = 0
    Name: str | None = None

@add_field_types
@dataclass(eq=False, frozen=True)
class Album(Model):
    _meta = ModelMeta(table="Album", id_column="AlbumId")
    
    artist: ClassVar[BelongsTo] = BelongsTo(
        "Artist", foreign_key="ArtistId", owner_key="ArtistId"
    )
    tracks: ClassVar[HasMany] = HasMany(
        "Track", foreign_key="AlbumId", local_key="AlbumId"
    )
    
    AlbumId: int = 0
    Title: str = ""
    ArtistId: int = 0
```

### Connect

```python
import sqlite3
from icemodel import Model

conn = sqlite3.connect("music.db")
Model.bind(conn)
```

### Query

`QueryBuilder` is **lazy**: building a query executes nothing. Results are fetched only when you iterate — either with a `for` loop, by passing to `tuple()`, or inside a comprehension. This means you can construct and pass around a query object without hitting the database, and you can process rows one at a time without loading the full result set into memory.

```python
from icemodel._query_builder import Operator, Direction

# Process rows one at a time — only one row in memory at once
for artist in Artist.query().order_by(Artist.Fields.NAME):
    print(artist.Name)

# Collect everything into a tuple
artists = tuple(Artist.query())

# Comprehension — combines iteration with transformation
names = [a.Name for a in Artist.query().where(Artist.Fields.NAME, Operator.LIKE, "The %")]

# Filter, order, limit
top_artists = tuple(
    Artist.query()
    .where(Artist.Fields.NAME, Operator.LIKE, "The %")
    .order_by(Artist.Fields.NAME)
    .limit(10)
)

# Find by primary key
_results = tuple(Artist.query().where(Artist.Fields.ARTISTID, 1).limit(1))
artist = _results[0] if _results else None

# Count
num_artists = Artist.query().count()

# Get first (with ordering)
_results = tuple(Artist.query().order_by(Artist.Fields.NAME).limit(1))
first = _results[0] if _results else None
```

### Relations — Lazy Loading

Access related records lazily (one query per access):

```python
_results = tuple(Artist.query().where(Artist.Fields.ARTISTID, 1).limit(1))
artist = _results[0] if _results else None
albums = artist.albums  # Fetches all albums for this artist
```

### Relations — Eager Loading

Batch-fetch related records in one query per relation:

```python
artists = tuple(Artist.query().with_related("albums"))
for artist in artists:
    albums = artist.albums  # Already loaded, no extra queries
```

### CRUD

**Insert:**
```python
# Single or multiple instances; always returns a tuple
artists = Artist.query().insert([
    Artist(ArtistId=500, Name="New Artist"),
    Artist(ArtistId=501, Name="Another Artist"),
])
# Returns tuple of inserted instances fetched from the database
assert len(artists) == 2
assert isinstance(artists, tuple)
```

**Update (full instance):**
```python
# Fetch, modify with dataclasses.replace(), then update by primary key
from dataclasses import replace

_results = tuple(Artist.query().where(Artist.Fields.ARTISTID, 1).limit(1))
if len(_results) > 0:
    artist = _results[0]
    modified = replace(artist, Name="Changed")
    result = Artist.query().update([modified])
    # Returns tuple of updated instances
```

**Patch (partial fields with where clause):**
```python
# Update specific fields of filtered records
rows_affected = Album.query().where(Album.Fields.ARTISTID, 1).patch(
    {"Title": "New Title"}
)

# Use Model.Partial for type-checked patch data
def rename_album(album_id: int, new_title: str) -> int:
    data: Album.Partial = {"Title": new_title}
    return Album.query().where(Album.Fields.ALBUMID, album_id).patch(data)
```

**Delete:**
```python
Artist.query().where(Artist.Fields.ARTISTID, 1).delete()
```

### Transactions

Use transactions to batch multiple operations with automatic rollback on exception:

```python
with Artist.transaction():
    artist = Artist.query().insert([Artist(ArtistId=1, Name="Beatles")])
    Album.query().insert([Album(AlbumId=1, ArtistId=1, Title="Abbey Road")])
    # Commits automatically on success; rolls back entirely on exception
```

## Required vs. Optional Fields

Field nullability is determined by type hints and enforced at the database layer:

```python
@dataclass(frozen=True)
class User(Model):
    name: str              # Non-Optional → NOT NULL in schema
    phone: str | None = None  # Optional → nullable in schema
```

Generated schema:
```sql
CREATE TABLE User (
    name TEXT NOT NULL,
    phone TEXT,
    ...
)
```

SQLite enforces `NOT NULL` constraints automatically. If you try to insert `None` into a required field, the database rejects it with a constraint violation. **This is the single source of truth for field requirements.**

## Field Validation

Define field validators using dataclass field metadata for semantic constraints (format, range, etc.). Validators run **before insert/update/patch** operations, ensuring data integrity at the application layer:

```python
from dataclasses import dataclass, field
from icemodel import Model, ModelMeta, add_field_types

def is_email(value: str) -> bool:
    return "@" in value

def is_positive(value: int) -> bool:
    return value > 0

@add_field_types
@dataclass(eq=False, frozen=True)
class User(Model):
    _meta = ModelMeta(table="User", id_column="UserId")
    
    UserId: int = 0
    Email: str = field(default="", metadata={"validator": is_email})
    Age: int = field(default=0, metadata={"validator": is_positive})
```

Validation runs on:
- **Write operations**: `insert()`, `update()`, `patch()` validate before SQL executes
- **Read operations**: Iterator protocol and eager loading validate when hydrating models from database rows

Validation **skips** `None` values (nullable fields are treated as optional). Invalid data raises `ValueError`:

```python
# Valid: inserts successfully
User.query().insert([User(UserId=1, Email="alice@example.com", Age=30)])

# Invalid: raises ValueError before SQL
User.query().insert([User(UserId=2, Email="invalid", Age=30)])
# ValueError: Validation failed for Email='invalid'

# Read also validates: catches data corruption from external writes
_results = tuple(User.query().where(User.Fields.USERID, 1).limit(1))
user = _results[0] if _results else None  # Validates on hydration
# If data was corrupted (e.g., via direct SQL), ValueError is raised
```

Validators are callable(value) -> bool returning True if valid. **Validation runs both at write time (insert/update/patch) and read time (iterator protocol, eager loading), ensuring data integrity throughout the model lifecycle.**

**Division of concerns:**
- **Type hints & schema** (`NOT NULL`, data types) — enforced by database, prevents structural violations
- **Custom validators** (format, range, business logic) — enforced by Python, prevents semantic violations

This design lets each layer do what it does best: SQLite handles structural constraints, Python handles semantic validation.

## Schema Generation

Generate SQL CREATE TABLE statements from model definitions:

```python
from icemodel import schema_for, schema_for_all
from myapp.models import Artist, Album

# Single model
print(schema_for(Artist))

# All models
for sql in schema_for_all([Artist, Album]):
    print(sql)
    db.execute(sql)
```

Or use the CLI:

```bash
python -m icemodel.schema
```

## Raw Queries

For queries that the ORM cannot express — joins, aggregations, window functions, CTEs — use `raw_query`. Define the expected result shape as a frozen `RawResultRow` subclass and pass it as `result_type`. Columns are matched to fields by name; required fields (no default) must be present in the result or a `ValueError` is raised. The result is a tuple of immutable, typed instances.

```python
from dataclasses import dataclass
from icemodel import RawResultRow, raw_query

@dataclass(frozen=True)
class AlbumCount(RawResultRow):
    ArtistId: int
    Name: str | None
    album_count: int

rows = raw_query(
    """
    SELECT ar.ArtistId, ar.Name, COUNT(al.AlbumId) AS album_count
    FROM Artist ar
    LEFT JOIN Album al ON al.ArtistId = ar.ArtistId
    GROUP BY ar.ArtistId
    HAVING album_count > 0
    """,
    result_type=AlbumCount,
)
# rows: tuple[AlbumCount, ...] — mypy knows the shape
for row in rows:
    print(row.Name, row.album_count)
```

Use `__post_init__` to validate result data at construction time:

```python
@dataclass(frozen=True)
class RevenueRow(RawResultRow):
    CustomerId: int
    total: float

    def __post_init__(self) -> None:
        if self.total < 0:
            raise ValueError(f"Negative revenue for customer {self.CustomerId}")
```

icemodel provides helpers for common `__post_init__` checks:

```python
from icemodel import require_int, require_float, require_str, require_not_none

@dataclass(frozen=True)
class SummaryRow(RawResultRow):
    label: str
    amount: float

    def __post_init__(self) -> None:
        require_str(self.label)
        require_float(self.amount)
        require_not_none(self.label)
```

**Warning: fields with defaults.** If a `RawResultRow` field has a default value and the corresponding column is absent from the query result, the default is used silently — no error is raised. This can mask mistakes in the SQL. The safe practice is to select all columns that the result type declares, and reserve defaults only for fields that are genuinely optional in the result.

```python
@dataclass(frozen=True)
class Risky(RawResultRow):
    ArtistId: int
    Name: str | None = None  # if SELECT omits Name, silently gets None

rows = raw_query("SELECT ArtistId FROM Artist LIMIT 1", result_type=Risky)
# rows[0].Name is None — not because the DB value is NULL,
# but because Name was never fetched
```

## Error Reporting

All SQL execution is wrapped to provide clear error messages. When a query fails, the full context is shown — the exact SQL and parameters alongside the database error — making it straightforward to diagnose issues that would be hidden by compile-time checking alone (e.g. renaming a database column without updating code).

```python
# Example: validation error
corrupted = ValidatedModel(id=1, name="", email="invalid", age=0)
ValidatedModel.query().insert([corrupted])

# Raises:
# ValueError: Validation failed for name: value must be non-empty
```

## Design

### Frozen Dataclasses

Models are **frozen dataclasses**, making instances immutable. This enforces the intended pattern:
- Fetch from DB, read data
- Use the query builder (`query().patch()`) for updates
- No accidental out-of-sync state

To modify a fetched instance, create a copy with `dataclasses.replace()`:
```python
from dataclasses import replace

_results = tuple(Artist.query().where(Artist.Fields.ARTISTID, 1).limit(1))
artist = _results[0] if _results else None
if artist is not None:
    updated = replace(artist, Name="New Name")
    Artist.query().where(Artist.Fields.ARTISTID, updated.ArtistId).patch({"Name": updated.Name})
```

### Model Metadata

Each model declares a `_meta` ModelMeta instance:
```python
from icemodel import ModelMeta

_meta = ModelMeta(table="TableName", id_column="PrimaryKeyColumn")
```

- `table`: SQL table name (required)
- `id_column`: Primary key column (default: `"id"`)

### Field Names and Type Safety

The `@add_field_types` decorator generates a `Fields` enum on each model at runtime. The mypy plugin (see below) additionally synthesizes a `Partial` TypedDict and gives `Fields` proper member-level type checking.

**`Fields` enum** — type-safe column references for queries:

```python
from icemodel import add_field_types

@add_field_types
@dataclass(eq=False, frozen=True)
class Artist(Model):
    ArtistId: int = 0
    Name: str | None = None

# Type-safe queries using enum members
_results = tuple(Artist.query().where(Artist.Fields.ARTISTID, 1).limit(1))
artist = _results[0] if _results else None
tuple(Artist.query().where(Artist.Fields.NAME, "AC/DC"))
tuple(Artist.query().order_by(Artist.Fields.ARTISTID))

# Unpack all fields into select()
tuple(Artist.query().select(*Artist.Fields))
```

**`Partial` TypedDict** — typed partial row for `patch()` (plugin-synthesized, annotation-only):

```python
# All fields are optional; include only the ones you want to change
data: Artist.Partial = {"Name": "New Name"}
Artist.query().where(Artist.Fields.ARTISTID, 1).patch(data)

# mypy catches invalid field names and wrong value types
bad: Artist.Partial = {"InvalidField": 1}   # ✗ Unknown key
bad2: Artist.Partial = {"Name": 99999}       # ✗ Wrong value type
```

**Type safety benefits (with mypy plugin configured):**

- **`Fields` member checking** — `Artist.Fields.TYPO` is a mypy error
- **`Partial` key and value checking** — wrong keys and wrong value types caught at compile time
- **Operator and direction safety** — `Operator` and `Direction` enums are validated
- **IDE autocomplete** — discover available fields, operators, and directions as you type

```python
# All caught at compile time by mypy
tuple(Artist.query().where(Artist.Fields.INVALID, "x"))           # ✗ No such member
tuple(Artist.query().order_by(Artist.Fields.NAME, "INVALID"))     # ✗ Invalid direction
tuple(Artist.query().where(Artist.Fields.NAME, Operator.INVALID)) # ✗ Invalid operator
```

### Query Builder Reference

The `QueryBuilder` provides a fluent API for building type-safe queries. Column references are specified via the `Fields` enum:

```python
from icemodel._query_builder import Operator, Direction

Artist.query().where(Artist.Fields.NAME, Operator.LIKE, "The %")
Album.query().where_in(Album.Fields.ARTISTID, [1, 2, 3])
Track.query().order_by(Track.Fields.NAME, Direction.DESCENDING)
```

**Query Methods (return QueryBuilder for chaining):**

- `where(field, value)` — equality filter  
  `where(field, Operator.EQUAL, value)` — explicit equality
- `where(field, op, value)` — filter with `Operator` enum
- `where_in(field, [values])` — IN clause
- `order_by(field, Direction.ASCENDING|Direction.DESCENDING)` — sort
- `limit(n)` — limit results
- `offset(n)` — skip results
- `select(*fields)` — select specific columns
- `with_related(name, ...)` — eager load relations

**Execution (via iterator protocol or explicit methods):**

- Iterate with `tuple(query)` or `for row in query` — fetch all matching rows
- `count()` — count matching rows
- `insert(models)` — insert multiple model instances, return tuple
- `update(models)` — update model instances by primary key, return tuple
- `patch(dict)` — partial update of filtered rows with field changes, return row count
- `delete()` — delete matching rows
- `to_sql()` — inspect generated SQL (returns tuple of sql string and params)

**`Operator` enum** — comparison operators:
```python
Operator.EQUAL, Operator.NOT_EQUAL, Operator.LESS_THAN, Operator.LESS_THAN_OR_EQUAL,
Operator.GREATER_THAN, Operator.GREATER_THAN_OR_EQUAL,
Operator.LIKE, Operator.NOT_LIKE, Operator.IS, Operator.IS_NOT
```

**`Direction` enum** — sort direction:
```python
Direction.ASCENDING, Direction.DESCENDING
```

All builder methods return the builder for chaining. Iteration (implicit via tuple() or explicit loops) fetches results. Collection-returning methods (`insert()`, `update()`) return immutable tuples.

### Relations Reference

Supported relation types:

| Type | Usage | Example |
|---|---|---|
| `HasMany` | One-to-many | Artist → many Albums |
| `BelongsTo` | Many-to-one | Album → one Artist |
| `HasOne` | One-to-one | Person → one Passport |
| `ManyToMany` | Many-to-many (via join table) | Playlist ↔ Tracks |

All relations are declared as `ClassVar` on the model:
```python
@dataclass(eq=False, frozen=True)
class Album(Model):
    artist: ClassVar[BelongsTo] = BelongsTo(
        "Artist",                    # Related model
        foreign_key="ArtistId",      # Foreign key column on this table
        owner_key="ArtistId"         # Primary key column on related table
    )
```

### Field Name Equivalence

**Design Decision:** Dataclass field names must exactly match database column names. There is no mapping or translation layer.

```python
from icemodel import Model, ModelMeta, add_field_types

@add_field_types
@dataclass(frozen=True)
class Artist(Model):
    _meta = ModelMeta(table="Artist", id_column="ArtistId")
    
    ArtistId: int = 0          # Field name == column name "ArtistId"
    Name: str | None = None    # Field name == column name "Name"
```

This ensures:
- Simple, predictable behavior — what you see is what you get
- Schema generation and hydration are trivial — no mapping metadata needed
- Clear correspondence between Python types and SQL columns

### Schema Mapping at System Boundaries

Field name mapping should happen at **system boundaries**, not in the ORM. This keeps the ORM simple and transparent while giving you full control over schema transformation where it actually belongs.

```python
from icemodel import Model, ModelMeta, add_field_types

# Database layer: direct correspondence, no mapping
@add_field_types
@dataclass(frozen=True)
class Artist(Model):
    _meta = ModelMeta(table="Artist", id_column="ArtistId")
    ArtistId: int = 0
    Name: str | None = None

# API boundary: transform to external schema
@app.get("/artists/{id}")
def get_artist(id: int):
    _results = tuple(Artist.query().where(Artist.Fields.ARTISTID, id).limit(1))
    db_artist = _results[0] if _results else None
    if db_artist is None:
        raise NotFound()
    return {
        "artist_id": db_artist.ArtistId,      # Map to API schema
        "artist_name": db_artist.Name,
        "url": f"/artists/{db_artist.ArtistId}"
    }

# Data import boundary: map legacy schema
def import_legacy_data(legacy_dict):
    artist = Artist(
        ArtistId=legacy_dict["id"],           # Map from legacy field names
        Name=legacy_dict["fullName"]
    )
    Artist.query().insert([artist])
```

**Why at boundaries, not in the ORM?**
- ORM stays simple and transparent
- Schema mapping is explicit and visible in application code
- Different parts of your system can have different external schemas
- No hidden metadata or configuration
- Easy to audit where transformations happen

## Mypy Plugin

icemodel ships a mypy plugin (`plugin/mypy_plugin.py`) that synthesizes typed `Fields` and `Partial` attributes for each model class. Without it, mypy accepts any attribute access on `Fields` and `Partial` is unknown.

Add to `pyproject.toml` or `mypy.ini`:

```toml
[tool.mypy]
plugins = ["plugin.mypy_plugin"]
```

The plugin provides:
- A synthetic `Fields` enum subtype with one member per model field — invalid members are caught at type-check time
- A `Partial` TypedDict (total=False) — wrong keys and incompatible value types are caught when building patch data

`Partial` is annotation-only: it exists as a type for mypy but has no runtime presence. Use it to annotate patch data dicts; passing those dicts to `patch()` works normally at runtime.

See `plugin/README.md` for full details on how the plugin works and its limitations.

## Development

### Setup

After cloning, activate the pre-commit hook (runs black, mypy, pylint, and pytest before each commit):

```bash
git config core.hooksPath .githooks
```

This configures the hook for this repository only and does not affect any other repos on your machine.

### Testing and static analysis

Run tests:
```bash
uv run pytest
```

Type check:
```bash
uv run mypy
```

Lint:
```bash
uv run pylint icemodel plugin
```

Test database: [Chinook](https://github.com/lerocha/chinook-database) (music store sample DB).

## Dependency stability

icemodel has no runtime dependencies — it relies only on the Python standard library.

The stdlib dependencies are among the most stable in Python. `sqlite3`, `dataclasses`, `inspect`, and `enum` have not had breaking API changes in years and are unlikely to. The one area worth watching is `typing`: `get_type_hints()`, `get_origin()`, `get_args()`, and `TypeVar` are all stable, but the typing module evolves across Python versions. The `types.UnionType` handling in the coercion layer (supporting the `X | Y` union syntax introduced in 3.10) is the most recent addition and is solid for 3.12+.

The mypy plugin is the shakiest dependency. mypy's internal plugin API (`mypy.nodes`, `mypy.plugin`, `mypy.types`) is explicitly unstable — mypy reserves the right to change it between versions. The plugin tests catch breakage when dev dependencies are updated.
