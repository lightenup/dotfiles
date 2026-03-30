#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BREWFILE="$DOTFILES/Brewfile"
IGNORE_FILE="$DOTFILES/.Brewfile.ignore"

if ! command -v brew >/dev/null 2>&1; then
  echo "brew not found"
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

declared_lines="$tmpdir/declared.lines"
actual_lines="$tmpdir/actual.lines"
untracked_lines="$tmpdir/untracked.lines"
ignore_names="$tmpdir/ignore.names"

brew bundle dump --file="$tmpdir/Brewfile.actual" --force --describe >/dev/null 2>&1

# Keep only directive lines and normalize whitespace.
grep -E '^(tap|brew|cask|vscode) ' "$BREWFILE" | sed 's/[[:space:]]\+/ /g' | sort -u > "$declared_lines"
grep -E '^(tap|brew|cask|vscode) ' "$tmpdir/Brewfile.actual" | sed 's/[[:space:]]\+/ /g' | sort -u > "$actual_lines"

comm -13 "$declared_lines" "$actual_lines" > "$untracked_lines"

if [ -f "$IGNORE_FILE" ]; then
  grep -Ev '^\s*#|^\s*$' "$IGNORE_FILE" | sed 's/[[:space:]]//g' > "$ignore_names" || true
else
  : > "$ignore_names"
fi

filtered="$tmpdir/untracked.filtered"
: > "$filtered"

while IFS= read -r line; do
  name="$(echo "$line" | sed -E 's/^[a-z]+ "([^"]+)"$/\1/')"
  if grep -Fxq "$name" "$ignore_names"; then
    continue
  fi
  echo "$line" >> "$filtered"
done < "$untracked_lines"

if [ ! -s "$filtered" ]; then
  echo "No untracked Homebrew entries detected."
  exit 0
fi

echo "Untracked entries (installed locally but missing from Brewfile):"
cat "$filtered"

echo
echo "Add names to .Brewfile.ignore if intentionally excluded."
exit 2
