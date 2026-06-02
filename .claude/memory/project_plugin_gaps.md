---
name: project-plugin-gaps
description: Status of icemodel mypy plugin gap resolution — Gaps 1/2/3 are now fully addressed
metadata:
  type: project
---

Gap 1 (Fields + Partial synthesis) was already fixed via the @add_field_types class decorator hook.

Gap 2 (cross-model fields in where/order_by) and Gap 3 (patch accepting any dict) were fixed by adding `get_method_signature_hook` to IcemodelPlugin (plugin/mypy_plugin.py):
- `where`, `where_in`, `order_by`: column param narrowed from Enum → T.Fields instance type
- `patch`: data param narrowed from dict[str, Any] → T.Partial TypedDictType

**Why:** The hooks only fire when the QueryBuilder's type arg is a concrete model Instance; when T is still a TypeVar (inside QueryBuilder's own methods), helpers return None and the original signature is preserved.

**How to apply:** Keep these hooks when changing the plugin. The --no-incremental flag was added to the mypy_api.run() call in tests/plugin/conftest.py to prevent stale-cache false passes.

Test coverage:
- tests/plugin/test_gap1_fields_and_partial.py — Gap 1 regression
- tests/plugin/test_patch.py — Gap 3 (patch key/type checking)
- tests/plugin/test_cross_model.py — Gap 2 (cross-model field rejection)

type_gaps.py still documents the gaps as narrative; the plugin tests are the executable spec.

Also fixed genuine bugs in tests/test_queries.py where Album.Fields / Artist.Fields were used on the wrong model's QueryBuilder (coincidental column name match masked the error).
