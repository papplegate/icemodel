# ormen

A minimal, dependency-free ORM for Python inspired by [objection.js](https://vincit.github.io/objection.js/). Fluent query builder, relations with lazy and eager loading, SQLite backend.

## Quick Start

### Define Models

Models are frozen dataclasses with a `_meta` dict for table metadata:

```python
from dataclasses import dataclass
from typing import ClassVar
from ormen import Model, HasMany, BelongsTo

@dataclass(eq=False, frozen=True)
class Artist(Model):
    _meta = {"table": "Artist", "id_column": "ArtistId"}
    
    albums: ClassVar[HasMany] = HasMany(
        "Album", foreign_key="ArtistId", local_key="ArtistId"
    )
    
    ArtistId: int = 0
    Name: str | None = None

@dataclass(eq=False, frozen=True)
class Album(Model):
    _meta = {"table": "Album", "id_column": "AlbumId"}
    
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
from ormen import Model

conn = sqlite3.connect("music.db")
Model.bind(conn)
```

### Query

```python
# Fetch all
artists = Artist.query().all()

# Filter, order, limit
top_artists = (
    Artist.query()
    .where("Name", "LIKE", "The %")
    .order_by("Name")
    .limit(10)
    .all()
)

# Find by primary key
artist = Artist.query().find_by_id(1)

# Count
num_artists = Artist.query().count()

# First
first = Artist.query().order_by("Name").first()
```

### Relations — Lazy Loading

Access related records lazily (one query per access):

```python
artist = Artist.query().find_by_id(1)
albums = artist.albums  # Fetches all albums for this artist
```

### Relations — Eager Loading

Batch-fetch related records in one query per relation:

```python
artists = Artist.query().with_related("albums").all()
for artist in artists:
    albums = artist.albums  # Already loaded, no extra queries
```

### CRUD

**Insert:**
```python
new_artist = Artist.query().insert({
    "ArtistId": 500,
    "Name": "New Artist"
})
```

**Update:**
```python
# Fetch, create modified copy, then patch the database
artist = Artist.query().find_by_id(1)
modified = __import__("dataclasses").replace(artist, Name="Changed")

Artist.query().where("ArtistId", 1).patch({
    "Name": modified.Name
})
```

**Delete:**
```python
Artist.query().where("ArtistId", 1).delete()
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

artist = Artist.query().find_by_id(1)
updated = replace(artist, Name="New Name")
Artist.query().where("ArtistId", updated.ArtistId).patch({"Name": updated.Name})
```

### Model Metadata

Each model declares a `_meta` dict:
```python
_meta = {"table": "TableName", "id_column": "PrimaryKeyColumn"}
```

- `table`: SQL table name (required)
- `id_column`: Primary key column (default: `"id"`)

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

The `QueryBuilder` provides a fluent API for building queries:

- `where(column, value)` — equality filter
- `where(column, op, value)` — filter with operator (`=`, `!=`, `<`, `>`, `<=`, `>=`, `LIKE`, `IS`, etc.)
- `where_in(column, [values])` — IN clause
- `order_by(column, "ASC"|"DESC")` — sort
- `limit(n)` — limit results
- `offset(n)` — skip results
- `with_related(name, ...)` — eager load relations
- `all()` — fetch all matching rows as model instances
- `first()` — fetch first row (or None)
- `find_by_id(id)` — fetch by primary key (or None)
- `count()` — count matching rows
- `insert(dict)` — insert a row, return new instance
- `patch(dict)` — update matching rows
- `delete()` — delete matching rows

All methods except terminal ones (`all()`, `first()`, `find_by_id()`, `count()`, `insert()`, `patch()`, `delete()`) return the builder for chaining.

## Type Safety

All code passes:
- **mypy strict** — full type checking, no `Any` escapes
- **pylint 10.00/10** — code quality and style
- **pytest** — 51 tests against real SQLite

Use `@dataclass(eq=False, frozen=True)` with typed fields for IDE autocomplete and static type checking.

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
uv run pylint src/ormen
```

Test database: [Chinook](https://github.com/lerocha/chinook-database) (music store sample DB).

## Limitations (Intentional)

- **SQLite only** — no other databases
- **No migrations** — use a migration tool separately
- **No N+1 prevention** — use `with_related()` for eager loading
- **No automatic dirty tracking** — mutate via `dataclasses.replace()` + `patch()`
- **No lazy properties** — relations are eagerly computed on access or pre-loaded with `with_related()`
