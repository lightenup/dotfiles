#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$HOME/.local/state/dotfiles"
LAST_DRIFT="$STATE_DIR/last-drift.log"
LAST_CHECK="$STATE_DIR/last-check.log"

mkdir -p "$STATE_DIR"

drift=0
summary_file="$STATE_DIR/summary.tmp"
: > "$summary_file"

ts="$(date '+%Y-%m-%d %H:%M:%S')"

if command -v brew >/dev/null 2>&1; then
  if ! brew bundle check --file="$DOTFILES/Brewfile" --no-upgrade >/dev/null 2>&1; then
    drift=1
    echo "[$ts] brew bundle check failed" >> "$summary_file"
  fi
else
  drift=1
  echo "[$ts] brew command not found" >> "$summary_file"
fi

if ! "$DOTFILES/scripts/symlinks-check.sh" >/dev/null 2>&1; then
  drift=1
  echo "[$ts] symlink drift detected" >> "$summary_file"
fi

if [ -n "$(git -C "$DOTFILES" status --porcelain)" ]; then
  drift=1
  echo "[$ts] dotfiles repo has uncommitted changes" >> "$summary_file"
fi

if [ "$drift" -eq 1 ]; then
  cp "$summary_file" "$LAST_DRIFT"
  osascript -e 'display notification "Dotfiles drift detected. Run: task status" with title "Dotfiles"' >/dev/null 2>&1 || true
  exit 1
fi

rm -f "$LAST_DRIFT"
echo "[$ts] clean" > "$LAST_CHECK"
