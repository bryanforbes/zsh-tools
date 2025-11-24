from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Final

import typer
from jsonschema import validators
from jsonschema.exceptions import SchemaError, ValidationError
from rich import print

from zsh_grammar.common import GRAMMAR_SCHEMA_PATH

_SCHEMA: Final = json.loads(GRAMMAR_SCHEMA_PATH.read_text())


def validate(files: list[Path]) -> None:
    for file in files:
        data = json.loads(file.read_text())
        try:
            if '$schema' in data and data['$schema'].startswith('./'):
                validators.validate(data, _SCHEMA)
            else:
                validators.validator_for(data).check_schema(data)
        except (SchemaError, ValidationError) as e:
            print(f'{e}')
            raise typer.Exit(code=1) from e


def main() -> None:
    typer.run(validate)


if __name__ == '__main__':
    main()
