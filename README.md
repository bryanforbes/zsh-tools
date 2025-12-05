# Zsh Tools

A collection of tools to help develop Zsh scripts and plugins.

## Development

This project uses [mise](https://mise.jdx.dev/) to manage tools and environment variables. The environment needs to be
set up a specific way on different platforms, so the `mise` configuration has been split to facilitate that. Add the
following to your `.zshrc` (or equivalent file in your setup):

```sh
if (( ${+commands[mise]} )); then
    # Ties MISE_ENV and mise_env together like PATH and path
    typeset -xTU MISE_ENV mise_env ','

    if [[ "$OSTYPE" == darwin* ]]; then
        mise_env+=('macos')
    elif [[ "$OSTYPE" == linux* ]]; then
        mise_env+=('linux')
    fi

    # For monorepo tasks
    export MISE_EXPERIMENTAL=1
fi

```
