#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$HOME/.agents/skills"

if [ ! -d "$SKILLS_DIR" ]; then
  echo "No skills directory found at $SKILLS_DIR"
  exit 0
fi

for path in "$SKILLS_DIR"/*; do
  [ -e "$path" ] || continue
  name="$(basename "$path")"
  if [ -L "$path" ]; then
    target="$(readlink "$path")"
    if [[ "$target" == "$DOTFILES/skills/"* ]]; then
      echo "$name : custom (symlink)"
    else
      echo "$name : symlink"
    fi
  else
    echo "$name : upstream/local dir"
  fi
done
