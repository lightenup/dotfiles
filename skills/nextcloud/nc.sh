#!/usr/bin/env bash
# nc.sh — Nextcloud WebDAV helper for the `nextcloud` skill.
#
# Non-secret config comes from ./config (or matching env vars); the app password
# is read from Bitwarden at runtime via scripts/secret.sh. The password is passed
# to curl via a `-K -` config on stdin, so it never appears in the process list.
#
#   nc.sh put   <local> <remotepath>   Upload a file (creates parent folders).
#   nc.sh get   <remotepath> <local>   Download a file.
#   nc.sh ls    [remotepath]           List a folder (Depth 1).
#   nc.sh mkdir <remotepath>           Create a folder (recursive).
#   nc.sh rm    <remotepath>           Delete a file or folder.
#
# Remote paths are relative to your Nextcloud files root, e.g. "Finance/budget.xlsx".
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES="$(cd "$HERE/../.." && pwd)"
SECRET_BIN="${SECRET_BIN:-$DOTFILES/scripts/secret.sh}"

# shellcheck disable=SC1091
[ -f "$HERE/config" ] && . "$HERE/config"
: "${NEXTCLOUD_URL:?NEXTCLOUD_URL not set}"
: "${NEXTCLOUD_LOGIN:?NEXTCLOUD_LOGIN not set}"
: "${NEXTCLOUD_USERID:?NEXTCLOUD_USERID not set}"
: "${NEXTCLOUD_SECRET_ITEM:=nextcloud/app-password}"

die() { echo "nc: $*" >&2; exit 1; }
[ -x "$SECRET_BIN" ] || die "secret helper not executable: $SECRET_BIN"

dav() { printf '%s/remote.php/dav/files/%s' "$NEXTCLOUD_URL" "$NEXTCLOUD_USERID"; }
remote_url() { printf '%s/%s' "$(dav)" "${1#/}"; }

# Run curl with WebDAV auth supplied via a stdin config (keeps the password off argv).
nc_curl() {
  local pw
  pw="$("$SECRET_BIN" get "$NEXTCLOUD_SECRET_ITEM")" || die "could not read Bitwarden item '$NEXTCLOUD_SECRET_ITEM' (is the vault unlocked? run: rbw unlock)"
  printf 'user = "%s:%s"\n' "$NEXTCLOUD_LOGIN" "$pw" | curl -sS -m 300 -K - "$@"
}

mkcol_p() {
  local path="${1#/}" acc="" p
  local -a parts
  IFS='/' read -ra parts <<< "$path"
  for p in "${parts[@]}"; do
    [ -n "$p" ] || continue
    acc="${acc:+$acc/}$p"
    # MKCOL returns 405 when the folder already exists — ignore.
    nc_curl -o /dev/null -w '' -X MKCOL "$(dav)/$acc" >/dev/null 2>&1 || true
  done
}

case "${1:-}" in
  put)
    [ $# -eq 3 ] || die "usage: nc.sh put <local> <remotepath>"
    [ -f "$2" ] || die "local file not found: $2"
    dir="$(dirname "${3#/}")"; [ "$dir" != "." ] && mkcol_p "$dir"
    nc_curl -o /dev/null -w "put %{http_code}  $3\n" -T "$2" "$(remote_url "$3")"
    ;;
  get)
    [ $# -eq 3 ] || die "usage: nc.sh get <remotepath> <local>"
    nc_curl -o "$3" -w "get %{http_code}  -> $3\n" "$(remote_url "$2")"
    ;;
  ls)
    nc_curl -X PROPFIND -H "Depth: 1" "$(remote_url "${2:-/}")" \
      | grep -oE '<d:href>[^<]*</d:href>' | sed 's/<[^>]*>//g'
    ;;
  mkdir)
    [ $# -eq 2 ] || die "usage: nc.sh mkdir <remotepath>"
    mkcol_p "$2"; echo "mkdir ok  $2"
    ;;
  rm)
    [ $# -eq 2 ] || die "usage: nc.sh rm <remotepath>"
    nc_curl -o /dev/null -w "rm %{http_code}  $2\n" -X DELETE "$(remote_url "$2")"
    ;;
  *)
    grep -E '^#   nc\.sh' "$0" | sed 's/^#   //' >&2
    exit 1
    ;;
esac
