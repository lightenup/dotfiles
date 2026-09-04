#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_FILE="$HOME/.config/certs/zscaler.pem"

# shellcheck source=scripts/links.sh
. "$DOTFILES/scripts/links.sh"

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

while IFS="$(printf '\t')" read -r src dst; do
  [ -n "$dst" ] || continue
  check_link "$src" "$dst"
done <<EOF
$(dotfiles_links "$DOTFILES")
EOF

# Not a symlink, but install.sh generates it and the shell exports
# NODE_EXTRA_CA_CERTS from it, so a missing file breaks node-based tools.
if [ -s "$CERT_FILE" ]; then
  echo "OK: $CERT_FILE ($(grep -c 'BEGIN CERTIFICATE' "$CERT_FILE") certificate(s))"
else
  echo "MISSING: $CERT_FILE is empty or absent — run: task certs:zscaler"
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi
