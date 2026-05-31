"""Field validation tests."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import ClassVar

import pytest

from icemodel import Model, ModelMeta, add_field_types


def is_positive(value: int) -> bool:
    """Validator: value must be positive."""
    return value > 0


def is_email(value: str) -> bool:
    """Validator: value must contain @."""
    return "@" in value


def is_non_empty(value: str) -> bool:
    """Validator: value must be non-empty."""
    return len(value) > 0


@add_field_types
@dataclass(eq=False, frozen=True)
class ValidatedModel(Model):
    _meta = ModelMeta(table="ValidatedModel", id_column="id")

    id: int = 0
    name: str = field(default="", metadata={"validator": is_non_empty})
    email: str = field(default="", metadata={"validator": is_email})
    age: int = field(default=0, metadata={"validator": is_positive})


class TestValidation:
    def test_insert_valid_data(self, writable_db: sqlite3.Connection) -> None:
        """Valid data should insert successfully."""
        model = ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)
        results = ValidatedModel.query().insert([model])
        assert len(results) == 1
        assert results[0].id == 1

    def test_insert_invalid_name_raises(self, writable_db: sqlite3.Connection) -> None:
        """Empty name should fail validation."""
        model = ValidatedModel(id=1, name="", email="alice@example.com", age=30)
        with pytest.raises(ValueError, match="Validation failed for name"):
            ValidatedModel.query().insert([model])

    def test_insert_invalid_email_raises(self, writable_db: sqlite3.Connection) -> None:
        """Email without @ should fail validation."""
        model = ValidatedModel(id=1, name="Alice", email="invalid", age=30)
        with pytest.raises(ValueError, match="Validation failed for email"):
            ValidatedModel.query().insert([model])

    def test_insert_invalid_age_raises(self, writable_db: sqlite3.Connection) -> None:
        """Non-positive age should fail validation."""
        model = ValidatedModel(id=1, name="Alice", email="alice@example.com", age=0)
        with pytest.raises(ValueError, match="Validation failed for age"):
            ValidatedModel.query().insert([model])

    def test_insert_multiple_invalid_fails(
        self, writable_db: sqlite3.Connection
    ) -> None:
        """First invalid model in batch should fail."""
        valid = ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)
        invalid = ValidatedModel(id=2, name="", email="bob@example.com", age=25)
        with pytest.raises(ValueError, match="Validation failed"):
            ValidatedModel.query().insert([valid, invalid])

    def test_update_valid_data(self, writable_db: sqlite3.Connection) -> None:
        """Valid data should update successfully."""
        from dataclasses import replace

        ValidatedModel.query().insert(
            [ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)]
        )
        _results = tuple(
            ValidatedModel.query().where(ValidatedModel.Fields.ID, 1).limit(1)
        )
        assert len(_results) > 0
        original = _results[0]
        modified = replace(original, name="Alice Updated")
        results = ValidatedModel.query().update([modified])
        assert results[0].name == "Alice Updated"

    def test_update_invalid_data_raises(self, writable_db: sqlite3.Connection) -> None:
        """Invalid update data should fail validation."""
        from dataclasses import replace

        ValidatedModel.query().insert(
            [ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)]
        )
        _results = tuple(
            ValidatedModel.query().where(ValidatedModel.Fields.ID, 1).limit(1)
        )
        assert len(_results) > 0
        original = _results[0]
        invalid = replace(original, name="")
        with pytest.raises(ValueError, match="Validation failed for name"):
            ValidatedModel.query().update([invalid])

    def test_patch_valid_data(self, writable_db: sqlite3.Connection) -> None:
        """Valid patch data should succeed."""
        ValidatedModel.query().insert(
            [ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)]
        )
        rows_affected = (
            ValidatedModel.query()
            .where(ValidatedModel.Fields.ID, 1)
            .patch({"name": "Alice Updated"})
        )
        assert rows_affected == 1
        _results = tuple(
            ValidatedModel.query().where(ValidatedModel.Fields.ID, 1).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.name == "Alice Updated"

    def test_patch_invalid_data_raises(self, writable_db: sqlite3.Connection) -> None:
        """Invalid patch data should fail validation."""
        ValidatedModel.query().insert(
            [ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)]
        )
        with pytest.raises(ValueError, match="Validation failed for name"):
            ValidatedModel.query().where(ValidatedModel.Fields.ID, 1).patch(
                {"name": ""}
            )

    def test_nullable_field_skips_validation(
        self, writable_db: sqlite3.Connection
    ) -> None:
        """None values should skip validation."""

        @add_field_types
        @dataclass(eq=False, frozen=True)
        class NullableModel(Model):
            _meta = ModelMeta(table="NullableModel", id_column="id")

            id: int = 0
            email: str | None = field(default=None, metadata={"validator": is_email})

        # Insert with None email should succeed (no validation)
        model = NullableModel(id=1, email=None)
        results = NullableModel.query().insert([model])
        assert len(results) == 1

        # Insert with valid email should succeed
        model2 = NullableModel(id=2, email="test@example.com")
        results = NullableModel.query().insert([model2])
        assert len(results) == 1

        # Insert with invalid email should fail
        model3 = NullableModel(id=3, email="invalid")
        with pytest.raises(ValueError, match="Validation failed"):
            NullableModel.query().insert([model3])

    def test_read_valid_data(self, writable_db: sqlite3.Connection) -> None:
        """Reading valid data should succeed."""
        ValidatedModel.query().insert(
            [ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)]
        )
        _results = tuple(
            ValidatedModel.query().where(ValidatedModel.Fields.ID, 1).limit(1)
        )
        assert len(_results) > 0
        fetched = _results[0]
        assert fetched.name == "Alice"

    def test_read_corrupted_data_raises(self, writable_db: sqlite3.Connection) -> None:
        """Reading data that fails validation should raise ValueError."""
        ValidatedModel.query().insert(
            [ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30)]
        )
        # Corrupt the data by directly updating the database
        writable_db.execute(
            "UPDATE ValidatedModel SET email = ? WHERE id = 1", ("invalid",)
        )
        writable_db.commit()

        # Attempting to read should fail validation
        with pytest.raises(ValueError, match="Validation failed for email"):
            _results = tuple(
                ValidatedModel.query().where(ValidatedModel.Fields.ID, 1).limit(1)
            )
            assert len(_results) > 0
            result = _results[0]

    def test_read_all_with_corrupted_data_raises(
        self, writable_db: sqlite3.Connection
    ) -> None:
        """Reading multiple rows where one is corrupted should raise on the bad row."""
        ValidatedModel.query().insert(
            [
                ValidatedModel(id=1, name="Alice", email="alice@example.com", age=30),
                ValidatedModel(id=2, name="Bob", email="bob@example.com", age=25),
            ]
        )
        # Corrupt one row
        writable_db.execute("UPDATE ValidatedModel SET name = ? WHERE id = 2", ("",))
        writable_db.commit()

        # all() should fail when it encounters the corrupted row
        with pytest.raises(ValueError, match="Validation failed for name"):
            tuple(ValidatedModel.query())

    def test_eager_loading_with_corrupted_data_raises(
        self, writable_db: sqlite3.Connection
    ) -> None:
        """Eager loading should validate fetched related records."""
        from dataclasses import dataclass
        from typing import ClassVar

        from icemodel import HasMany

        @add_field_types
        @dataclass(eq=False, frozen=True)
        class Parent(Model):
            _meta = ModelMeta(table="Parent", id_column="id")

            children: ClassVar[HasMany] = HasMany(
                "Child", foreign_key="parent_id", local_key="id"
            )

            id: int = 0
            name: str = field(default="", metadata={"validator": is_non_empty})

        @add_field_types
        @dataclass(eq=False, frozen=True)
        class Child(Model):
            _meta = ModelMeta(table="Child", id_column="id")

            id: int = 0
            parent_id: int = 0
            title: str = field(default="", metadata={"validator": is_non_empty})

        # Create tables
        writable_db.execute("""
            CREATE TABLE Parent (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            ) STRICT
        """)
        writable_db.execute("""
            CREATE TABLE Child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER NOT NULL,
                title TEXT NOT NULL
            ) STRICT
        """)
        writable_db.commit()

        # Insert valid data
        Parent.query().insert([Parent(id=1, name="Parent 1")])
        Child.query().insert([Child(id=1, parent_id=1, title="Child 1")])

        # Corrupt child data
        writable_db.execute("UPDATE Child SET title = ? WHERE id = 1", ("",))
        writable_db.commit()

        # Eager loading should fail when validating the corrupted child
        with pytest.raises(ValueError, match="Validation failed for title"):
            tuple(Parent.query().with_related("children"))


class TestTypeCoercion:
    def test_model_int_coerced_to_float_for_float_field(
        self, writable_db: sqlite3.Connection
    ) -> None:
        # NUMERIC affinity (non-STRICT) stores whole numbers as INTEGER and returns
        # them as int. The float-annotated field must be coerced before construction.
        writable_db.execute(
            "CREATE TABLE Measurement (id INTEGER PRIMARY KEY, value NUMERIC)"
        )
        writable_db.execute("INSERT INTO Measurement VALUES (1, 2)")
        writable_db.commit()

        # Confirm SQLite actually returned int here — that's the case we're coercing.
        row = writable_db.execute(
            "SELECT value FROM Measurement WHERE id = 1"
        ).fetchone()
        assert isinstance(row[0], int)

        @add_field_types
        @dataclass(eq=False, frozen=True)
        class Measurement(Model):
            _meta = ModelMeta(table="Measurement", id_column="id")
            id: int = 0
            value: float = 0.0

        results = tuple(Measurement.query())
        assert len(results) == 1
        assert isinstance(results[0].value, float)
        assert results[0].value == 2.0

    def test_model_non_integer_float_unchanged(
        self, writable_db: sqlite3.Connection
    ) -> None:
        writable_db.execute(
            "CREATE TABLE Measurement (id INTEGER PRIMARY KEY, value NUMERIC)"
        )
        writable_db.execute("INSERT INTO Measurement VALUES (1, 2.5)")
        writable_db.commit()

        @add_field_types
        @dataclass(eq=False, frozen=True)
        class Measurement(Model):
            _meta = ModelMeta(table="Measurement", id_column="id")
            id: int = 0
            value: float = 0.0

        results = tuple(Measurement.query())
        assert results[0].value == 2.5
        assert isinstance(results[0].value, float)
