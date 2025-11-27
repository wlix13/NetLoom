# Shell Completion

NetLoom supports tab completion for bash, zsh, and fish shells.

## Installation

### Automatic (Recommended)

```bash
netloom install-completion --install bash
netloom install-completion --install zsh
netloom install-completion --install fish
```

This automatically adds the completion script to your shell configuration file.

### Manual

Add the appropriate line to your shell config:

**Bash** (`~/.bashrc`):

```bash
eval "$(_NETLOOM_COMPLETE=bash_source netloom)"
```

**Zsh** (`~/.zshrc`):

```bash
eval "$(_NETLOOM_COMPLETE=zsh_source netloom)"
```

**Fish** (`~/.config/fish/config.fish`):

```fish
eval (env _NETLOOM_COMPLETE=fish_source netloom)
```

Then reload your shell: `source ~/.bashrc` (or equivalent).

## Usage

Press `Tab` to complete commands, options, and file paths:

```bash
netloom <TAB>              # Shows all commands
netloom --<TAB>            # Shows all options
netloom --topology <TAB>   # Completes file paths
```

## Troubleshooting

If completion doesn't work:

1. Restart your terminal or run `source ~/.bashrc` (or equivalent)
2. Verify the completion line exists in your shell config file
3. Check you're using the correct shell: `echo $SHELL`
