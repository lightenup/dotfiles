#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail=0

check_link() {
  local expected="$1"
  local dst="$2"

  if [ ! -L "$dst" ]; then
    echo "MISSING: $dst is not a symlink"
    fail=1
    return
  fi

  local actual
  actual="$(readlink "$dst")"
  if [ "$actual" != "$expected" ]; then
    echo "DRIFT: $dst -> $actual (expected: $expected)"
    fail=1
    return
  fi

  echo "OK: $dst"
}

check_link "$DOTFILES/shell/zshrc" "$HOME/.zshrc"
check_link "$DOTFILES/shell/zprofile" "$HOME/.zprofile"
check_link "$DOTFILES/git/gitconfig" "$HOME/.gitconfig"
check_link "$DOTFILES/git/gitconfig_ey" "$HOME/Development/ey/gh-enterprise/.gitconfig_ey"
check_link "$DOTFILES/git/gitconfig_private" "$HOME/Development/private/.gitconfig_private"
check_link "$DOTFILES/hooks/commit-msg" "$HOME/.config/git/hooks/commit-msg"
check_link "$DOTFILES/ssh/config" "$HOME/.ssh/config"
check_link "$DOTFILES/act/actrc" "$HOME/.actrc"

for f in "$DOTFILES"/zsh-completions/_*; do
  check_link "$f" "$HOME/.zsh/completions/$(basename "$f")"
done

if [ "$fail" -ne 0 ]; then
  exit 1
fi
