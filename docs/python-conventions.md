---
globs:
    - '**/*.py'
    - '**/*.pyi'
---

# Python Conventions

All Python code must fully comply with these rules. Deviations are allowed only if unavoidable (e.g., third-party library constraints) and must be explicitly commented.

## Coding Style

1. **Python version:**
    - Unpublished tools must use modern Python 3.14+ features.
    - Published tools must comply with Python 3.10+.
2. **Linting:**
    - All code must pass `ruff check` with zero errors/warnings.
    - All code must pass `basedpyright` with zero errors/warnings.
    - If a linting or typechecking rule cannot be fixed without significant overhead, it can be disabled for the line in question with a comment explaining why.
3. **Formatting:**
    - All code must be formatted with `ruff format`.
    - Import sorting is handled by `ruff format`.
4. **Imports:**
    - Group imports in this order: standard library, third-party, local
    - Use absolute imports when possible
    - Avoid wildcard imports (`from module import *`)
    - Each import on its own line (except for closely related imports from same module)
5. **Naming:**
    - `snake_case` for functions and variables.
    - `PascalCase` for classes.
    - `UPPER_SNAKE_CASE` for constants.
    - Functions and variables should have descriptive names; avoid single-letter names.
    - Functions and variables that are intended for internal use only should be prefixed with a single underscore (`_`).
6. **Error handling:**
    - Use standard Python exceptions where possible.
    - Avoid bare `except:` clauses; always catch specific exceptions.
    - When catching multiple exceptions, use a tuple (e.g., `except (ValueError, TypeError):`).
    - Always provide informative error messages when raising exceptions.
7. **Type hints:**
    - For consistency, all non-empty modules must include `from __future__ import annotations`.
    - Add type hints for all function parameters and return values.
    - Never quote type hints except in `typing.cast()` calls or if it is unavoidable.
    - Use type aliases where appropriate (do not overuse).
    - Avoid `typing.Any` unless a type cannot be expressed appropriately; use `object` for arguments that accept all values.
    - For arguments, prefer protocols and abstract types (`Mapping`, `Sequence`, `Iterable`, etc.).
    - Import protocols and abstract types from `collections.abc` rather than `typing`.
    - Always use shorthand union syntax with `None` last:

        ```python
        def foo(x: str | int) -> None: ...
        def bar(x: str | None) -> int | None: ...
        ```

8. **Generics:**
    - Always use built-in generics (`list[str]`, `dict[str, int]`). Never use `typing.List`, `Dict`, `Iterable`, etc..
    - Example:

        ```python
        from collections.abc import Iterable

        def foo(x: type[MyClass]) -> list[str]: ...
        def bar(x: Iterable[str]) -> None: ...
        ```

9. **TypedDict:**
    - Declare `TypedDict` subclasses where appropriate (prefix with `_` for internal use).
    - Use `NotRequired` to mark optional fields.
    - Example:

        ```python
        from typing import NotRequired, TypedDict

        class RuleDef(TypedDict):
            sequence: list[object]
            choice: list[str]
            optional: NotRequired[str]
            repeat: NotRequired[str]
            repeat1: NotRequired[str]
        ```

10. **Docstrings:**
    - Use triple double quotes for all module, class, and function docstrings
    - Follow Google docstring format for functions with parameters/returns
    - Keep docstrings concise but informative
    - Document complex logic or edge cases
