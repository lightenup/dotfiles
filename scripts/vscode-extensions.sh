#!/usr/bin/env bash
set -euo pipefail

# Install the VS Code extensions declared in the Brewfile.
#
# `brew bundle` cannot do this behind a TLS-intercepting proxy: Homebrew scrubs
# NODE_EXTRA_CA_CERTS from its environment, so the `code` CLI it spawns cannot
# verify the marketplace CDN and every extension fails with "unable to get local
# issuer certificate". Running the same command ourselves, with the CA exported,
# works. The Brewfile stays the source of truth so `brew bundle check` keeps
# reporting drift.

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BREWFILE="${BREWFILE:-$DOTFILES/Brewfile}"
CERT_FILE="$HOME/.config/certs/zscaler.pem"

info() { printf '  [ \033[00;34m..\033[0m ] %s\n' "$1"; }
ok()   { printf '  [ \033[00;32mOK\033[0m ] %s\n' "$1"; }
warn() { printf '  [ \033[0;33m!!\033[0m ] %s\n' "$1"; }

if ! command -v code >/dev/null 2>&1; then
  warn "VS Code CLI (code) not found — skipping extensions"
  exit 0
fi

if [ ! -f "$BREWFILE" ]; then
  warn "Brewfile not found: $BREWFILE"
  exit 0
fi

[ -r "$CERT_FILE" ] && export NODE_EXTRA_CA_CERTS="$CERT_FILE"

lower() { tr '[:upper:]' '[:lower:]'; }

declared="$(sed -nE 's/^vscode "([^"]+)".*/\1/p' "$BREWFILE")"
if [ -z "$declared" ]; then
  ok "No VS Code extensions declared"
  exit 0
fi

installed="$(code --list-extensions 2>/dev/null | lower || true)"

missing=""
while IFS= read -r ext; do
  [ -n "$ext" ] || continue
  if printf '%s\n' "$installed" | grep -qxF "$(printf '%s' "$ext" | lower)"; then
    continue
  fi
  missing="${missing}${ext}
"
done <<< "$declared"

if [ -z "$missing" ]; then
  ok "All $(printf '%s\n' "$declared" | grep -c .) VS Code extensions present"
  exit 0
fi

count="$(printf '%s' "$missing" | grep -c .)"
info "Installing $count missing VS Code extension(s)"

args=""
while IFS= read -r ext; do
  [ -n "$ext" ] || continue
  args="$args --install-extension $ext"
done <<< "$missing"

# shellcheck disable=SC2086  # deliberate word splitting to batch one CLI call
code $args >/dev/null 2>&1 || true

installed="$(code --list-extensions 2>/dev/null | lower || true)"
still_missing=""
while IFS= read -r ext; do
  [ -n "$ext" ] || continue
  if ! printf '%s\n' "$installed" | grep -qxF "$(printf '%s' "$ext" | lower)"; then
    still_missing="${still_missing}      - ${ext}
"
  fi
done <<< "$missing"

if [ -n "$still_missing" ]; then
  warn "These extensions did not install:"
  printf '%s' "$still_missing"
  exit 1
fi

ok "Installed $count VS Code extension(s)"
