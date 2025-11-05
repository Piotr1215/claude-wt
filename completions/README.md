# Shell Completions for claude-wt

## Zsh

### Installation

#### Option 1: System-wide (requires root)
```bash
sudo cp _claude-wt /usr/local/share/zsh/site-functions/_claude-wt
```

#### Option 2: User-specific (recommended)
```bash
# Create completions directory if it doesn't exist
mkdir -p ~/.zsh/completions

# Copy the completion file
cp _claude-wt ~/.zsh/completions/_claude-wt

# Add to your ~/.zshrc (if not already present)
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit
```

#### Option 3: Oh My Zsh
```bash
# Copy to Oh My Zsh completions directory
cp _claude-wt ~/.oh-my-zsh/completions/_claude-wt

# Reload completions
rm -f ~/.zcompdump; compinit
```

### Reload Completions

After installation, reload your shell or run:
```bash
exec zsh
```

Or force rebuild the completion cache:
```bash
rm -f ~/.zcompdump; compinit
```

### Usage

Once installed, you can use tab completion with `claude-wt`:

```bash
claude-wt <TAB>           # Shows all commands
claude-wt new --<TAB>     # Shows all flags for 'new' command
claude-wt clean --<TAB>   # Shows all flags for 'clean' command
```

## Features

- Command completion for all `claude-wt` commands
- Flag completion with descriptions
- Branch name completion for `--branch` flag
- Directory completion for `--scan-dir` and `--repo-path` flags
- Help text displayed for each command

## Bash / Fish

Contributions welcome! Please submit a PR with completion scripts for other shells.
