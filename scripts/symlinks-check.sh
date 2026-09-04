#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_FILE="$HOME/.config/certs/zscaler.pem"
CA_BUNDLE="$HOME/.config/certs/ca-bundle.pem"

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

# Not symlinks, but install.sh generates both: the shell exports
# NODE_EXTRA_CA_CERTS from the root CA, and CA-file-based tools (anything
# bundling its own Python) are pointed at the combined bundle.
check_generated_cert() {
  local path="$1" hint="$2"

  if [ -s "$path" ]; then
    echo "OK: $path ($(grep -c 'BEGIN CERTIFICATE' "$path") certificate(s))"
  else
    echo "MISSING: $path is empty or absent — run: $hint"
    fail=1
  fi
}

check_generated_cert "$CERT_FILE" "task certs:zscaler"
check_generated_cert "$CA_BUNDLE" "task certs:bundle"

if [ "$fail" -ne 0 ]; then
  exit 1
fi
