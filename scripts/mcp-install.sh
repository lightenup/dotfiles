#!/usr/bin/env bash
set -euo pipefail

# Distribute the canonical MCP server definitions (mcp/servers.json) into every
# AI client that speaks the standard {"mcpServers": {...}} schema. Each client's
# config is deep-merged with jq so unrelated keys and other servers are kept;
# entries defined in servers.json win on name conflicts.

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANON="$DOTFILES/mcp/servers.json"

info() { printf '  [ \033[00;34m..\033[0m ] %s\n' "$1"; }
ok()   { printf '  [ \033[00;32mOK\033[0m ] %s\n' "$1"; }
warn() { printf '  [ \033[0;33m!!\033[0m ] %s\n' "$1"; }

if ! command -v jq >/dev/null 2>&1; then
  warn "jq not found — cannot manage MCP configs. Install: brew install jq"
  exit 0
fi

if [ ! -f "$CANON" ]; then
  warn "Canonical MCP source not found: $CANON"
  exit 0
fi

# label|config-path  (parent dir must exist for the client to be considered installed)
TARGETS=(
  "Factory droid|$HOME/.factory/mcp.json"
  "LM Studio|$HOME/.lmstudio/mcp.json"
  "Claude Desktop|$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  "Claude Code|$HOME/.claude.json"
)

ACTION="${1:-install}"

merge_into() {
  local label="$1" target="$2"
  local dir
  dir="$(dirname "$target")"

  if [ ! -d "$dir" ]; then
    warn "$label not detected ($dir missing) — skipping"
    return 0
  fi

  [ -f "$target" ] || echo '{}' > "$target"

  local merged
  merged="$(jq --slurpfile canon "$CANON" \
    '.mcpServers = ((.mcpServers // {}) + $canon[0].mcpServers)' \
    "$target")"

  if [ "$merged" = "$(cat "$target")" ]; then
    ok "$label already up to date"
    return 0
  fi

  cp "$target" "$target.bak"
  printf '%s\n' "$merged" > "$target"
  ok "$label updated ($target, backup at $target.bak)"
}

status_of() {
  local label="$1" target="$2"
  if [ ! -f "$target" ]; then
    warn "$label: no config ($target)"
    return 0
  fi
  local names
  names="$(jq -r '(.mcpServers // {}) | keys | join(", ")' "$target" 2>/dev/null || echo "<invalid json>")"
  ok "$label: ${names:-<none>}"
}

case "$ACTION" in
  install)
    info "Distributing MCP servers from $CANON"
    for entry in "${TARGETS[@]}"; do
      merge_into "${entry%%|*}" "${entry#*|}"
    done
    ;;
  status)
    info "Configured MCP servers per client"
    for entry in "${TARGETS[@]}"; do
      status_of "${entry%%|*}" "${entry#*|}"
    done
    ;;
  *)
    warn "Unknown action: $ACTION (use 'install' or 'status')"
    exit 1
    ;;
esac
