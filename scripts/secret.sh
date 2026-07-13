#!/usr/bin/env bash
# secret.sh — thin secrets accessor for dotfiles skills, backed by Bitwarden (rbw).
#
# Secrets live in your Bitwarden vault (cloud). Nothing sensitive is stored in
# this repo or on disk in plaintext. The rbw agent caches the unlock, so scripts
# can read secrets without juggling session tokens.
#
# Usage:
#   secret.sh get   <item>            Print the item's password field to stdout.
#   secret.sh field <item> <field>    Print a named field (e.g. username, a custom field).
#   secret.sh has   <item>            Exit 0 if the item is retrievable, else 1.
#   secret.sh unlocked                Exit 0 if the Bitwarden vault is unlocked.
#
# One-time setup:
#   brew install rbw pinentry-mac
#   rbw config set email <you@example.com>
#   rbw config set pinentry pinentry-mac
#   rbw login && rbw unlock
#   # then create the vault items this repo references, e.g. "nextcloud/app-password"
set -euo pipefail

die() { echo "secret: $*" >&2; exit 1; }

command -v rbw >/dev/null 2>&1 || die "rbw not installed — run: brew install rbw pinentry-mac"

require_unlocked() {
  if ! rbw unlocked >/dev/null 2>&1; then
    die "Bitwarden vault is locked. Run:  rbw unlock"
  fi
}

cmd="${1:-}"; shift || true
case "$cmd" in
  get)
    [ $# -ge 1 ] || die "usage: secret.sh get <item>"
    require_unlocked
    rbw get "$1"
    ;;
  field)
    [ $# -ge 2 ] || die "usage: secret.sh field <item> <field>"
    require_unlocked
    rbw get "$1" --field "$2"
    ;;
  has)
    [ $# -ge 1 ] || die "usage: secret.sh has <item>"
    rbw unlocked >/dev/null 2>&1 || exit 1
    rbw get "$1" >/dev/null 2>&1
    ;;
  unlocked)
    rbw unlocked >/dev/null 2>&1
    ;;
  *)
    die "usage: secret.sh {get|field|has|unlocked} <item> [field]"
    ;;
esac
