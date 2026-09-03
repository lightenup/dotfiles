#!/bin/bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="ai.dotfiles.check.plist"
CERT_FILE="$HOME/.config/certs/zscaler.pem"

# Plain counter plus a text log rather than an array: /bin/bash on macOS is 3.2,
# where expanding an empty array under `set -u` aborts the script.
FAILURE_COUNT=0
FAILURE_LOG=""

info() { printf '  [ \033[00;34m..\033[0m ] %s\n' "$1"; }
ok()   { printf '  [ \033[00;32mOK\033[0m ] %s\n' "$1"; }
warn() { printf '  [ \033[0;33m!!\033[0m ] %s\n' "$1"; }
fail() {
  warn "$1"
  FAILURE_COUNT=$((FAILURE_COUNT + 1))
  FAILURE_LOG="${FAILURE_LOG}      - ${1}
"
}

# Homebrew may not be on PATH yet on a fresh machine (~/.zprofile is not read by
# this script), and every step below depends on tools it installs.
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

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

# ── Task scripts ───────────────────────────────────────────────────────────
# Early: later steps invoke these helpers.
info "Ensuring helper scripts are executable"
chmod +x "$DOTFILES"/scripts/*.sh 2>/dev/null || true

# ── mise ───────────────────────────────────────────────────────────────────
info "Linking mise config"
mkdir -p "$HOME/.config/mise"
link_file "$DOTFILES/mise/config.toml" "$HOME/.config/mise/config.toml"

# ── Corporate TLS root CA ──────────────────────────────────────────────────
# Must run before Homebrew: `brew bundle` installs the VS Code extensions, and
# their CDN is TLS-intercepted. node-based tools ignore the macOS keychain.
info "Exporting corporate root CA for node-based tools"
mkdir -p "$(dirname "$CERT_FILE")"
if security find-certificate -a -p -c "Zscaler" /Library/Keychains/System.keychain > "$CERT_FILE" 2>/dev/null \
   && [ -s "$CERT_FILE" ]; then
  export NODE_EXTRA_CA_CERTS="$CERT_FILE"
  ok "Exported $(grep -c 'BEGIN CERTIFICATE' "$CERT_FILE") certificate(s) to $CERT_FILE"
else
  rm -f "$CERT_FILE"
  warn "No corporate root CA found in the System keychain — skipping"
fi

# ── VS Code extensions ─────────────────────────────────────────────────────
# Before Homebrew on purpose: brew scrubs NODE_EXTRA_CA_CERTS, so `brew bundle`
# cannot install extensions behind the TLS-intercepting proxy. Doing it here
# first means brew bundle finds them already present.
info "Installing VS Code extensions"
"$DOTFILES/scripts/vscode-extensions.sh" || fail "VS Code extension install failed"

# ── Homebrew ───────────────────────────────────────────────────────────────
if command -v brew &>/dev/null; then
  info "Installing Homebrew packages from Brewfile"
  if ! brew bundle install --file="$DOTFILES/Brewfile" --no-upgrade; then
    fail "brew bundle install failed. Re-run with details: task -d $DOTFILES brew:install"
  fi
else
  fail "Homebrew not found — skipped Brewfile. Install: https://brew.sh"
fi

# ── mise tools (dotnet, java) ──────────────────────────────────────────────
if command -v mise &>/dev/null; then
  info "Installing mise-managed tools (dotnet, java)"
  mise install || fail "mise install failed"
else
  fail "mise not found — skipped dotnet/java provisioning"
fi

# ── pipx ───────────────────────────────────────────────────────────────────
if command -v pipx &>/dev/null; then
  info "Installing pipx packages"
  if pipx list --short 2>/dev/null | grep -q '^pre-commit '; then
    ok "pre-commit already installed"
  else
    pipx install pre-commit || fail "pipx install pre-commit failed"
  fi
else
  fail "pipx not found — skipped pre-commit"
fi

# ── npm globals ────────────────────────────────────────────────────────────
if command -v npm &>/dev/null; then
  info "Installing global npm packages"
  npm install -g wscat || fail "npm install -g wscat failed"
else
  fail "npm not found — skipped global npm packages"
fi

# ── Skills ─────────────────────────────────────────────────────────────────
if command -v npx &>/dev/null; then
  info "Installing and linking skills"
  "$DOTFILES/scripts/skills-install.sh" || fail "skills-install failed"
else
  fail "npx not found — skipped skills installation"
fi

# ── MCP servers ────────────────────────────────────────────────────────────
if command -v jq &>/dev/null; then
  info "Distributing MCP servers to AI clients"
  "$DOTFILES/scripts/mcp-install.sh" install || fail "mcp-install failed"
else
  fail "jq not found — skipped MCP server distribution"
fi

# ── Tessdata for liteparse OCR fallback ────────────────────────────────────
if command -v task &>/dev/null; then
  info "Provisioning tessdata for Tesseract OCR fallback"
  task -d "$DOTFILES" ocr:provision-tessdata || fail "tessdata provisioning failed"
else
  fail "task not found — skipped tessdata provisioning"
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
  fail "Could not load launchd job $PLIST_NAME"
fi

echo ""
warn "Manual steps:"
echo "  1. Copy SSH keys to ~/.ssh/ (not stored in dotfiles)"
echo "  2. Run: nvm install 20 (if Node needed; dotnet and java come from mise)"
echo "  3. Run: task -d $DOTFILES status"

if [ "$FAILURE_COUNT" -gt 0 ]; then
  echo ""
  warn "Dotfiles installed with $FAILURE_COUNT failure(s):"
  printf '%s' "$FAILURE_LOG"
  echo ""
  echo "  Open a new terminal to pick up changes, then re-run ./install.sh once"
  echo "  the causes above are resolved (a fresh machine often needs two passes)."
  exit 1
fi

echo ""
ok "Dotfiles installed. Open a new terminal to pick up changes."
