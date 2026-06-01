import os
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest
from mypy import api as mypy_api

_PROJECT_ROOT = Path(__file__).parent.parent.parent

# Minimal model used across plugin tests — defined inline to avoid
# depending on the chinook test fixtures or database.
MODEL_PREAMBLE = """
from dataclasses import dataclass
from icemodel import Model, ModelMeta, add_field_types

@add_field_types
@dataclass(eq=False, frozen=True)
class Book(Model):
    _meta = ModelMeta(table="Book", id_column="BookId")
    BookId: int = 0
    Title: str = ""
    Price: float = 0.0
    Year: int | None = None
"""


@pytest.fixture
def check() -> Callable[[str], tuple[str, int]]:
    """Run mypy on a source string and return (output, exit_code).

    The source is written to a temporary file at the project root so that
    icemodel and plugin are importable. The file is removed after each call.
    """
    temp_file = _PROJECT_ROOT / f"_mypy_check_{os.getpid()}.py"

    def _check(source: str) -> tuple[str, int]:
        temp_file.write_text(textwrap.dedent(source).lstrip())
        try:
            out, _, exit_code = mypy_api.run(
                [
                    "--config-file",
                    str(_PROJECT_ROOT / "pyproject.toml"),
                    "--no-error-summary",
                    "--no-incremental",
                    str(temp_file),
                ]
            )
            return out, exit_code
        finally:
            temp_file.unlink(missing_ok=True)

    return _check
