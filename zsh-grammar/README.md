# Zsh Grammar

A machine-readable, declarative grammar that accurately represents Zsh syntax. This will be used to generate multiple parser targets.

## Structure

The canonical grammar is JSON-based and located at `./canonical_grammar.json`. Because of the nature of Zsh as a language, the grammar is split up into "sub-languages":

- Main shell grammar
- Parameter expansion
- Arithmetic expansion
- Command substitution
- Conditionals
- Globbing / pattern matching
- Strings / quoting

At this time, the schema for the grammar is defined in `./src/zsh_grammar/_types.py`.

### Example

```json
{
    "languages": {
        "zsh": {
            "tokens": {
                "SEMICOLON": {"pattern": ";"},
                "NEWLINE": {"pattern": "\n"}
            },
            "rules": {
                "command_list": {"type": "sequence", "elements": ["simple_command", "pipeline"]},
                "arithmetic_expansion": {
                    "type": "subgrammar",
                    "name": "arith",
                    "entry_rule": "expr"
                },
            },
        },
        "arith": {
            "rules": {
                "expr": {
                    "type": "binary_expr",
                    "operators": ["+", "-", "*", "/", "%"],
                    "precedence": [[["*", "/"], 2], [["+", "-"], 1]]
                }
            }
        },
    },
    "extension_points": [
        {"module": "Modules/zregex", "hook_type": "regex_operator", "description": "Adds additional pattern matching operators"},
        {"module": "Modules/complist", "hook_type": "completion"}
    ],
    "metadata": {"version": "5.9"},
}
```

## Getting Started

### Preparing the Zsh source for parsing

Run the following commands in `vendor/zsh`:

```sh
mise clean-zsh-source
mise prepare-zsh-source
```

## Workflow

1. Run `mise extract-zsh-raw` to extract the raw grammar from the Zsh source code.
