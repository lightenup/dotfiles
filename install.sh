#!/bin/bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="ai.dotfiles.check.plist"

info() { printf '  [ \033[00;34m..\033[0m ] %s\n' "$1"; }
ok()   { printf '  [ \033[00;32mOK\033[0m ] %s\n' "$1"; }
warn() { printf '  [ \033[0;33m!!\033[0m ] %s\n' "$1"; }

link_file() {
  local src="$1" dst="$2"
  if [ -L "$dst" ]; then
    rm "$dst"
  elif [ -f "$dst" ]; then
    mv "$dst" "${dst}.backup"
    warn "Backed up existing $dst → ${dst}.backup"
  fi
  ln -s "$src" "$dst"
  ok "Linked $dst → $src"
}

# ── Shell ──────────────────────────────────────────────────────────────────
info "Linking shell config"
link_file "$DOTFILES/shell/zshrc"    "$HOME/.zshrc"
link_file "$DOTFILES/shell/zprofile" "$HOME/.zprofile"

# ── Git ────────────────────────────────────────────────────────────────────
info "Linking git config"
mkdir -p "$HOME/Development/ey/gh-enterprise"
mkdir -p "$HOME/Development/private"
mkdir -p "$HOME/Development/wilhem"
link_file "$DOTFILES/git/gitconfig"         "$HOME/.gitconfig"
link_file "$DOTFILES/git/gitconfig_ey"      "$HOME/Development/ey/gh-enterprise/.gitconfig_ey"
link_file "$DOTFILES/git/gitconfig_private" "$HOME/Development/private/.gitconfig_private"
link_file "$DOTFILES/git/gitconfig_wilhem"  "$HOME/Development/wilhem/.gitconfig_wilhem"

# ── Git hooks ──────────────────────────────────────────────────────────────
info "Installing global git hooks"
mkdir -p "$HOME/.config/git/hooks"
link_file "$DOTFILES/hooks/commit-msg" "$HOME/.config/git/hooks/commit-msg"

# ── SSH ────────────────────────────────────────────────────────────────────
info "Linking SSH config (keys are manual)"
mkdir -p "$HOME/.ssh"
link_file "$DOTFILES/ssh/config" "$HOME/.ssh/config"

# ── Zsh completions ───────────────────────────────────────────────────────
info "Linking zsh completions"
mkdir -p "$HOME/.zsh/completions"
for f in "$DOTFILES"/zsh-completions/_*; do
  link_file "$f" "$HOME/.zsh/completions/$(basename "$f")"
done

# ── Act ────────────────────────────────────────────────────────────────────
info "Linking act config"
link_file "$DOTFILES/act/actrc" "$HOME/.actrc"

# ── Homebrew ───────────────────────────────────────────────────────────────
if command -v brew &>/dev/null; then
  info "Installing Homebrew packages from Brewfile"
  if ! brew bundle install --file="$DOTFILES/Brewfile" --no-upgrade; then
    warn "brew bundle install failed. Re-run with details: task -d $DOTFILES brew:install"
  fi
else
  warn "Homebrew not found — skipping Brewfile. Install: https://brew.sh"
fi

# ── pipx ───────────────────────────────────────────────────────────────────
if command -v pipx &>/dev/null; then
  info "Installing pipx packages"
  pipx install pre-commit 2>/dev/null || true
else
  warn "pipx not found — skipping"
fi

# ── npm globals ────────────────────────────────────────────────────────────
if command -v npm &>/dev/null; then
  info "Installing global npm packages"
  npm install -g wscat 2>/dev/null || true
else
  warn "npm not found — skipping"
fi

# ── Task scripts ───────────────────────────────────────────────────────────
info "Ensuring helper scripts are executable"
chmod +x "$DOTFILES"/scripts/*.sh 2>/dev/null || true

# ── Skills ─────────────────────────────────────────────────────────────────
if command -v npx &>/dev/null; then
  info "Installing and linking skills"
  "$DOTFILES/scripts/skills-install.sh" || warn "skills-install failed"
else
  warn "npx not found — skipping skills installation"
fi

# ── Launchd drift checks ───────────────────────────────────────────────────
info "Installing launchd drift check"
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/.local/state/dotfiles"

sed \
  -e "s|__DOTFILES__|$DOTFILES|g" \
  -e "s|__HOME__|$HOME|g" \
  "$DOTFILES/launchd/$PLIST_NAME" > "$HOME/Library/LaunchAgents/$PLIST_NAME"

launchctl unload "$HOME/Library/LaunchAgents/$PLIST_NAME" >/dev/null 2>&1 || true
if launchctl load "$HOME/Library/LaunchAgents/$PLIST_NAME" >/dev/null 2>&1; then
  ok "Loaded launchd job $PLIST_NAME"
else
  warn "Could not load launchd job $PLIST_NAME"
fi

echo ""
ok "Dotfiles installed. Open a new terminal to pick up changes."
echo ""
warn "Manual steps:"
echo "  1. Copy SSH keys to ~/.ssh/ (not stored in dotfiles)"
echo "  2. Run: sdk install java (if SDKMAN needed)"
echo "  3. Run: nvm install 20 (if Node needed)"
echo "  4. Run: task -d $DOTFILES status"
