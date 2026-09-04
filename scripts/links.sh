#!/usr/bin/env bash
# Single source of truth for the dotfiles symlinks: install.sh creates them,
# symlinks-check.sh verifies them. Keeping two lists meant the check silently
# stopped covering whatever the installer gained. Sourced, never executed.
#
# Emits one "<source>\t<target>" line per link.

dotfiles_links() {
  local d="$1"

  printf '%s\t%s\n' \
    "$d/shell/zshrc" "$HOME/.zshrc" \
    "$d/shell/zprofile" "$HOME/.zprofile" \
    "$d/git/gitconfig" "$HOME/.gitconfig" \
    "$d/git/gitconfig_ey" "$HOME/Development/ey/gh-enterprise/.gitconfig_ey" \
    "$d/git/gitconfig_private" "$HOME/Development/private/.gitconfig_private" \
    "$d/git/gitconfig_wilhem" "$HOME/Development/wilhem/.gitconfig_wilhem" \
    "$d/hooks/commit-msg" "$HOME/.config/git/hooks/commit-msg" \
    "$d/ssh/config" "$HOME/.ssh/config" \
    "$d/act/actrc" "$HOME/.actrc" \
    "$d/mise/config.toml" "$HOME/.config/mise/config.toml"

  local f
  for f in "$d"/zsh-completions/_*; do
    [ -e "$f" ] || continue
    printf '%s\t%s\n' "$f" "$HOME/.zsh/completions/$(basename "$f")"
  done
}
