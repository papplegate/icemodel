---
name: feedback_uv_run
description: Use uv run instead of .venv/bin/python to invoke commands in this project
metadata:
  type: feedback
---

Use `uv run <command>` instead of `.venv/bin/python -m <command>` or `.venv/bin/<command>` when running tools in this project.

**Why:** User preference — this is a uv-managed project and uv run is the correct invocation pattern.

**How to apply:** Any time a shell command would invoke Python or a dev tool (pytest, mypy, pylint, etc.), use `uv run pytest`, `uv run mypy`, etc. rather than going through .venv directly.
