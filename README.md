# Zsh Tools

A collection of tools to help develop Zsh scripts and plugins.

## Development

This project uses [mise](https://mise.jdx.dev/) to manage tools and environment variables. The environment needs to be set up a specific way on different platforms, so the `mise` configuration has been split to facilitate that. Add the following to your `.zshrc` (or equivalent file in your setup):

```sh
if (( ${+commands[mise]} )); then
    cache_file="${ZCACHEDIR}/shellenv/mise.zsh"

    if [[ "$commands[mise]:A" -nt "$cache_file" || ! -s "$cache_file" ]]; then
        mkdir -p "$cache_file:h"
        # Cache the result.
        mise activate zsh >! "$cache_file" 2> /dev/null
    fi

    source "$cache_file"
    unset cache_file

    # Ties MISE_ENV and mise_env together like PATH and path
    typeset -xTU MISE_ENV mise_env ','

    if [[ "$OSTYPE" == darwin* ]]; then
        mise_env+=('macos')
    elif [[ "$OSTYPE" == linux* ]]; then
        mise_env+=('linux')
    fi
fi

```
