# dotfiles

Mac setup: shell, git, hooks, SSH, zsh completions, Brewfile, launchd checks, and agent skills.

## New machine

```bash
git clone git@github.com:lightenup/dotfiles.git ~/Development/private/dotfiles
cd ~/Development/private/dotfiles
./install.sh
```

Then manually copy SSH keys to ~/.ssh/.

## Daily operations

```bash
cd ~/Development/private/dotfiles
task status
```

Useful commands:

```bash
task brew:check
task brew:install
task brew:reconcile
task symlinks:check
task skills:install
task skills:status
```

## Drift detection

- A launchd job runs once per day and checks:
	- Homebrew state vs Brewfile
	- Symlink integrity
	- Dotfiles repo dirty state
- On drift, you get a macOS notification.
- On next shell startup, zsh also prints a warning once per day.

Launchd plist template: launchd/ai.dotfiles.check.plist

## Brewfile reconciliation

- `task brew:reconcile` compares installed entries with Brewfile.
- Add intentional exclusions to .Brewfile.ignore (one entry name per line).
- This is report-only by design. You decide what to commit.

## Skills model

- `skills/` is for your custom skills (symlinked into ~/.agents/skills).
- `skills.yml` declares upstream skills installed via `npx skills add`.
- Current upstream skill declaration includes liteparse.
