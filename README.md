# icemodel

A minimal, dependency-free ORM for Python inspired by [objection.js](https://vincit.github.io/objection.js/). Fluent query builder, relations with lazy and eager loading, SQLite backend.

## Quick Start

### Define Models

Models are frozen dataclasses with a `_meta` ModelMeta instance for table metadata:

```python
from dataclasses import dataclass
from typing import ClassVar
from icemodel import Model, ModelMeta, HasMany, BelongsTo, field_names

@field_names
@dataclass(eq=False, frozen=True)
class Artist(Model):
    _meta = ModelMeta(table="Artist", id_column="ArtistId")
    
    albums: ClassVar[HasMany] = HasMany(
        "Album", foreign_key="ArtistId", local_key="ArtistId"
    )
    
    ArtistId: int = 0
    Name: str | None = None

@field_names
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

```python
from icemodel._query_builder import Op

# Fetch all (iterate over results)
artists = tuple(Artist.query())

# Filter, order, limit
top_artists = tuple(
    Artist.query()
    .where(Artist.Fields.NAME, Op.LIKE, "The %")
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
# Update specific fields of filtered records (keys must be Fields enum members)
rows_affected = Album.query().where(Album.Fields.ARTISTID, 1).patch(
    {Album.Fields.TITLE: "New Title"}
)
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

### Required vs. Optional Fields

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

### Field Validation

Define field validators using dataclass field metadata for semantic constraints (format, range, etc.). Validators run **before insert/update/patch** operations, ensuring data integrity at the application layer:

```python
from dataclasses import dataclass, field
from icemodel import Model, ModelMeta, field_names

def is_email(value: str) -> bool:
    return "@" in value

def is_positive(value: int) -> bool:
    return value > 0

@field_names
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

icemodel doesn't hide SQL—use `query.to_sql()` to inspect generated queries anytime.

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

### Field Name Equivalence

**Design Decision:** Dataclass field names must exactly match database column names. There is no mapping or translation layer.

```python
from icemodel import Model, ModelMeta, field_names

@field_names
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

**Column Name Validation:** There is no lightweight way to validate dataclass field names at the Python layer without significant runtime overhead. Instead, the database enforces column name errors. If you reference a non-existent column in a query, the SQL will fail with a database error at execution time.

```python
# This compiles and runs, but SQLite will error if "InvalidColumn" doesn't exist
tuple(Artist.query().where("InvalidColumn", "value"))
# sqlite3.OperationalError: no such column: InvalidColumn
```

If your database uses different naming conventions (snake_case columns, CamelCase classes), rename the fields to match the actual column names.

### Field Names as Enums

Each model with the `@field_names` decorator automatically generates a `Fields` enum that maps to field names. Use it to reference columns in queries:

```python
from icemodel import field_names

@field_names
@dataclass(eq=False, frozen=True)
class Artist(Model):
    ...

# Access field names via enum members
_results = tuple(Artist.query().where(Artist.Fields.ARTISTID, 1).limit(1))
artist = _results[0] if _results else None
tuple(Artist.query().where(Artist.Fields.NAME, "AC/DC"))
tuple(Artist.query().order_by(Artist.Fields.ARTISTID))
```

The enum provides:
- **IDE autocomplete** — discover available fields as you type
- **Refactoring safety** — rename a field, rename the enum member, queries stay in sync
- **Type hints** — document which fields are valid for a query

### Schema Mapping at System Boundaries

Field name mapping should happen at **system boundaries**, not in the ORM. This keeps the ORM simple and transparent while giving you full control over schema transformation where it actually belongs.

```python
from icemodel import Model, ModelMeta, field_names

# Database layer: direct correspondence, no mapping
@field_names
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

### Graceful Database Errors

Rather than using type-based validation to catch column name errors at runtime, icemodel takes a simpler approach: **let the database catch the error and report it clearly**.

All SQL execution is wrapped to catch database errors (`sqlite3.OperationalError`) and display the full query alongside the error:

```python
tuple(Artist.query().where("InvalidColumn", "value"))

# Raises:
# sqlite3.OperationalError: no such column: InvalidColumn
# 
# Failed query:
#   SQL: SELECT * FROM Artist WHERE InvalidColumn = ?
#   Params: ['value']
```

**Why this beats type-based solutions:**

Type-safe query APIs (like those using Field objects) require boilerplate:
```python
# Type-safe approach (high boilerplate)
class Artist(Model):
    ArtistId: int = 0
    Name: str | None = None
    
    # Need helper methods or metaclass tricks to extract fields
    _fields = {"ArtistId": ..., "Name": ...}

# Then in queries:
Artist.query().where(Artist.field("Name"), Op.LIKE, "The %")
# Or with a field registry:
Artist.query().where(Artist.fields.Name, Op.LIKE, "The %")
```

The string-based approach is simpler:
```python
# String-based approach (no boilerplate)
Artist.query().where("Name", Op.LIKE, "The %")
```

**Trade-offs:**
- ✓ No Field metadata or helper methods needed
- ✓ Queries are simpler and more readable
- ✓ No tight coupling between Python types and query construction
- ✓ Errors are clear and include the actual query
- ✗ Typos aren't caught until query execution
- ✗ IDE autocomplete won't help with column names

**When errors occur**, the full context is displayed: the exact SQL, parameters, and the database error. This makes debugging straightforward and surfaces issues that would be hidden by compile-time checking (e.g., when you rename a database column but forget to update code).

### Relations

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

### Query Builder

The `QueryBuilder` provides a fluent API for building type-safe queries. Column references are specified via the `Fields` enum:

```python
from icemodel._query_builder import Op

Artist.query().where(Artist.Fields.NAME, Op.LIKE, "The %")
Album.query().where_in(Album.Fields.ARTISTID, [1, 2, 3])
Track.query().order_by(Track.Fields.NAME, "DESC")
```

**Query Methods (return QueryBuilder for chaining):**

- `where(field, value)` — equality filter  
  `where(field, Op.EQ, value)` — explicit equality
- `where(field, op, value)` — filter with `Op` enum operator
- `where_in(field, [values])` — IN clause
- `order_by(field, "ASC"|"DESC")` — sort
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

**Op Enum** — Comparison operators:
```python
Op.EQ, Op.NE, Op.LT, Op.LE, Op.GT, Op.GE, Op.LIKE, Op.NOT_LIKE, Op.IS, Op.IS_NOT
```

All builder methods return the builder for chaining. Iteration (implicit via tuple() or explicit loops) fetches results. Collection-returning methods (`insert()`, `update()`) return immutable tuples.

## Type Safety

All code passes:
- **mypy strict** — full type checking, no `Any` escapes
- **pylint 10.00/10** — code quality and style
- **pytest** — 103 tests covering queries, CRUD, relations, transactions, schema generation, field validation

Use `@dataclass(eq=False, frozen=True)` with typed fields for IDE autocomplete and static type checking.

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

## Dependencies

**None.** Uses only Python stdlib: `sqlite3`, `dataclasses`, `typing`.

## Testing

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
uv run pylint src/icemodel
```

Test database: [Chinook](https://github.com/lerocha/chinook-database) (music store sample DB).

## Limitations (Intentional)

- **SQLite only** — no other databases
- **No migrations** — use a migration tool separately
- **No N+1 prevention** — use `with_related()` for eager loading
- **No automatic dirty tracking** — mutate via `dataclasses.replace()` + `patch()`
- **No lazy properties** — relations are eagerly computed on access or pre-loaded with `with_related()`

## Future Work

### Multi-Database Support

The architecture is designed to support additional databases (PostgreSQL, MySQL) without major rewrites. To add a new backend:

1. **Abstract the connection layer** — Create a `_backends/` module with dialect-specific code for:
   - Connection initialization and row factory setup
   - Parameter binding (SQLite `?`, PostgreSQL `$1/$2`, MySQL `?`)
   - Result row hydration (different drivers return rows differently)

2. **Dialect-aware query building** — Modify `_query_builder.py` to:
   - Track which database is in use
   - Render SQL with correct parameter placeholders
   - Handle dialect-specific features (e.g., PostgreSQL's `RETURNING` clause for INSERT)

3. **Optional driver dependencies** — Add to `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   postgres = ["psycopg>=3.0"]
   mysql = ["pymysql>=1.0"]
   ```
   Users install: `pip install icemodel[postgres]` or `pip install icemodel[mysql]`

4. **Shared test suite** — Use the same tests across all backends via parameterized fixtures.

The core model, relation, and query builder logic remains database-agnostic. Only the connection, SQL rendering, and row hydration need backend-specific code.
