"""
Demonstrates where icemodel's apparent type safety breaks down under mypy.
Run:  uv run python -m mypy type_gaps.py
"""

from tests.models import Artist, Album

# --- Gap 1: Fields and Partial don't exist as far as mypy is concerned ---
# All of the following are errors to mypy, even though they work at runtime.
# The entire Fields/Partial API is invisible because add_field_types generates
# these attributes dynamically and mypy cannot see through that.

_ = Artist.Fields.ARTISTID          # error: "type[Artist]" has no attribute "Fields"
_ = Artist.Fields.NONEXISTENT       # same error — mypy can't distinguish this from above

data: Artist.Partial = {"Name": "x"}  # error: Name "Artist.Partial" is not defined

# --- Gap 2: where() and order_by() accept any Enum, not just the model's Fields ---
# If Fields were visible, mypy still couldn't enforce that the right model's
# Fields are used — where() is typed as taking Enum, not specifically T.Fields.
# These would silently pass mypy even with a fully typed Fields attribute:

Artist.query().where(Album.Fields.ALBUMID, 1)   # wrong model's field, runtime error
Artist.query().order_by(Album.Fields.TITLE)      # wrong model's field, runtime error

# --- Gap 3: patch() accepts any string keys and any value types ---
# dict[str, Any] means mypy cannot catch key typos or wrong value types.
# The wrong value type case is particularly subtle — SQLite won't reject it either.

Artist.query().where(Artist.Fields.ARTISTID, 1).patch({"Nmae": "typo"})  # key typo
Artist.query().where(Artist.Fields.ARTISTID, 1).patch({"Name": 99999})   # wrong type, silently stored
