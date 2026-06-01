"""
Demonstrates where icemodel's apparent type safety breaks down under mypy.
Run:  uv run python -m mypy type_gaps.py
"""

from tests.models import Artist, Album
from icemodel._query_builder import Operator

# --- Gap 1 (fixed): Fields and Partial are fully visible to mypy ---
# The mypy plugin (plugin/mypy_plugin.py) synthesizes these at check time,
# so valid accesses pass and invalid ones are caught.

_ = Artist.Fields.ARTISTID  # ok
_ = Artist.Fields.NONEXISTENT  # error: "type[ArtistFields]" has no attribute "NONEXISTENT"

data: Artist.Partial = {"Name": "x"}  # ok

# --- Gap 2: where() and order_by() accept any Enum, not just the model's Fields ---
# mypy cannot enforce that the right model's Fields are used — where() and
# order_by() are typed as taking Enum, not specifically T.Fields.
# Both of the following silently pass mypy:
#
# Python has no associated types, so there is no standard way to express
# "the Fields type belonging to T" as a type constraint. Two options:
#
# Option A — QueryBuilder[T, F] where F is bound to the model's Fields enum.
#   The plugin would need to synthesize the correct return type for query(),
#   i.e. QueryBuilder[Artist, ArtistFields] instead of QueryBuilder[Artist].
#   Keeps runtime code clean but leaks F into every QueryBuilder annotation.
#
# Option B — Extend the mypy plugin to check where()/order_by() call sites.
#   When the plugin sees Artist.query().where(...), it verifies the column
#   argument is an ArtistFields member. No API surface change, but the plugin
#   becomes substantially more complex (call expression hooks, not just class
#   decoration hooks).

Artist.query().where(Album.Fields.ALBUMID, Operator.EQUAL, 1)  # wrong model's field, runtime error
Artist.query().order_by(Album.Fields.TITLE)  # wrong model's field, runtime error

# --- Gap 3: patch() accepts any string keys and any value types ---
# dict[str, Any] means mypy cannot catch key typos or wrong value types.
# The wrong value type case is particularly subtle — SQLite won't reject it either.

Artist.query().where(Artist.Fields.ARTISTID, Operator.EQUAL, 1).patch({"Nmae": "typo"})  # key typo
Artist.query().where(Artist.Fields.ARTISTID, Operator.EQUAL, 1).patch(
    {"Name": 99999}
)  # wrong type, silently stored
