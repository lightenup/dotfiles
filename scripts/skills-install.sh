#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${SKILLS_DIR:-$HOME/.agents/skills}"
FACTORY_SKILLS_DIR="$HOME/.factory/skills"

mkdir -p "$SKILLS_DIR"
mkdir -p "$FACTORY_SKILLS_DIR"
echo "Target skills directory: $SKILLS_DIR"
echo "Factory skills directory: $FACTORY_SKILLS_DIR"

link_dir() {
  local src="$1" dst="$2"
  if [ -L "$dst" ]; then
    rm "$dst"
  elif [ -d "$dst" ]; then
    mv "$dst" "${dst}.backup"
  fi
  ln -s "$src" "$dst"
}

# Shared libraries from dotfiles/skills/_lib
if [ -d "$DOTFILES/skills/_lib" ]; then
  link_dir "$DOTFILES/skills/_lib" "$SKILLS_DIR/_lib"
  link_dir "$DOTFILES/skills/_lib" "$FACTORY_SKILLS_DIR/_lib"
  echo "Linked shared lib: _lib"
fi

# Custom local skills from dotfiles/skills
for skill_dir in "$DOTFILES"/skills/*; do
  [ -d "$skill_dir" ] || continue
  [ -f "$skill_dir/SKILL.md" ] || continue
  skill_name="$(basename "$skill_dir")"
  link_dir "$skill_dir" "$SKILLS_DIR/$skill_name"
  link_dir "$skill_dir" "$FACTORY_SKILLS_DIR/$skill_name"
  echo "Linked custom skill: $skill_name"
done

# Upstream skills managed by skills CLI
if [ ! -f "$DOTFILES/skills.yml" ]; then
  echo "No skills.yml found, skipping upstream skills."
  exit 0
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found; cannot install upstream skills."
  exit 0
fi

while IFS='|' read -r repo skill; do
  [ -n "$repo" ] || continue
  [ -n "$skill" ] || continue
  echo "Installing upstream skill: $skill from $repo"
  npx --yes skills add "$repo" --skill "$skill" --yes --global
done < <(
  awk '
    /^[[:space:]]*-[[:space:]]*repo:[[:space:]]*/ {
      repo=$0
      sub(/^[[:space:]]*-[[:space:]]*repo:[[:space:]]*/, "", repo)
      gsub(/"/, "", repo)
    }
    /^[[:space:]]*skill:[[:space:]]*/ {
      skill=$0
      sub(/^[[:space:]]*skill:[[:space:]]*/, "", skill)
      gsub(/"/, "", skill)
      if (repo != "" && skill != "") {
        print repo "|" skill
      }
    }
  ' "$DOTFILES/skills.yml"
)
