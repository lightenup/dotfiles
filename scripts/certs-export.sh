#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$HOME/.config/certs"
ROOT_CA="$CERT_DIR/zscaler.pem"
CA_BUNDLE="$CERT_DIR/ca-bundle.pem"
SYSTEM_CA="/etc/ssl/cert.pem"
KEYCHAIN="/Library/Keychains/System.keychain"

count_certs() { grep -c 'BEGIN CERTIFICATE' "$1" || true; }

export_root_ca() {
  mkdir -p "$CERT_DIR"

  local tmp
  tmp="$(mktemp)"
  if ! security find-certificate -a -p -c "Zscaler" "$KEYCHAIN" > "$tmp" 2>/dev/null \
     || [ ! -s "$tmp" ]; then
    rm -f "$tmp"
    echo "No corporate root CA found in the System keychain" >&2
    return 1
  fi

  mv "$tmp" "$ROOT_CA"
  chmod 644 "$ROOT_CA"
  echo "Exported $(count_certs "$ROOT_CA") certificate(s) to $ROOT_CA"
}

# SSL_CERT_FILE and REQUESTS_CA_BUNDLE replace the trust store instead of
# extending it, so a file holding only the corporate root would break every
# host the proxy leaves alone. Apple's roots have to travel in the same file.
build_bundle() {
  mkdir -p "$CERT_DIR"

  if [ ! -s "$ROOT_CA" ]; then
    echo "Missing $ROOT_CA — run: task certs:zscaler" >&2
    return 1
  fi
  if [ ! -s "$SYSTEM_CA" ]; then
    echo "Missing $SYSTEM_CA — cannot build a combined bundle" >&2
    return 1
  fi

  local tmp
  tmp="$(mktemp)"
  cat "$SYSTEM_CA" "$ROOT_CA" > "$tmp"

  # A truncated concatenation silently narrows trust for every tool pointed at
  # this file, so never publish one OpenSSL cannot parse.
  if ! openssl crl2pkcs7 -nocrl -certfile "$tmp" >/dev/null 2>&1; then
    rm -f "$tmp"
    echo "Combined bundle failed to parse — left $CA_BUNDLE untouched" >&2
    return 1
  fi

  mv "$tmp" "$CA_BUNDLE"
  chmod 644 "$CA_BUNDLE"
  echo "Wrote $(count_certs "$CA_BUNDLE") certificate(s) to $CA_BUNDLE"
}

case "${1:-all}" in
  root)   export_root_ca ;;
  bundle) build_bundle ;;
  all)    export_root_ca && build_bundle ;;
  *)
    echo "usage: $(basename "$0") [root|bundle|all]" >&2
    exit 64
    ;;
esac
