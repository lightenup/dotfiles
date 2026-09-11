#!/usr/bin/env bash
#
# lint-api.sh — run the rest-api-design ruleset over one or more OpenAPI documents.
#
# Reports by default and exits 0. This is a tool for producing recommendations, not a
# gate: findings feed the ranked backlog in references/backlog-template.md, where they
# get weighed against consumer blast radius and effort. Pass --gate if you also want it
# to fail a pipeline on errors.
#
#   ./lint-api.sh openapi/my-api.yaml
#   ./lint-api.sh --profile ./api-style.yaml openapi/*.yaml
#   ./lint-api.sh --format json --out findings.json openapi/my-api.yaml
#   ./lint-api.sh --gate openapi/my-api.yaml
#
# With no --profile, the script looks for api-style.yaml in the document's directory and
# then upwards to the repo root. Without one it runs base rules only — an estate that has
# not recorded any decisions gets no style findings it cannot act on.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPECTRAL_VERSION="${SPECTRAL_VERSION:-6.15.0}"
SPECTRAL_PKG="@stoplight/spectral-cli@${SPECTRAL_VERSION}"

PROFILE=""
FORMAT="stylish"
OUT=""
GATE=0
KEEP_RULESET=0
DOCS=()

die() { printf 'lint-api: %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --profile)  PROFILE="${2:-}"; shift 2 ;;
    --format)   FORMAT="${2:-}"; shift 2 ;;
    --out)      OUT="${2:-}"; shift 2 ;;
    --gate)     GATE=1; shift ;;
    --keep-ruleset) KEEP_RULESET=1; shift ;;
    -h|--help)
      sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*)         die "unknown option: $1" ;;
    *)          DOCS+=("$1"); shift ;;
  esac
done

[ ${#DOCS[@]} -gt 0 ] || die "no OpenAPI document given. Try --help."
command -v npx >/dev/null 2>&1 || die "npx not found — install Node (brew install node)."

# ── Locate a style profile ───────────────────────────────────────────────────
find_profile() {
  local dir; dir="$(cd "$(dirname "$1")" && pwd)"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/api-style.yaml" ]; then printf '%s\n' "$dir/api-style.yaml"; return 0; fi
    if [ -d "$dir/.git" ]; then break; fi
    dir="$(dirname "$dir")"
  done
  return 1
}

if [ -z "$PROFILE" ]; then
  PROFILE="$(find_profile "${DOCS[0]}" || true)"
fi

# ── Derive the ruleset ───────────────────────────────────────────────────────
RULESET_DIR="$(mktemp -d)"
RULESET="$RULESET_DIR/rest-api-design.yaml"
# Spectral resolves `functionsDir` relative to the file that declares it, and does not
# inherit function declarations across `extends`. The generated ruleset therefore needs
# the functions reachable at ./functions beside it.
ln -s "$HERE/spectral/functions" "$RULESET_DIR/functions"
cleanup() { [ "$KEEP_RULESET" -eq 1 ] || rm -rf "$RULESET_DIR"; }
trap cleanup EXIT

if [ -n "$PROFILE" ] && [ -f "$PROFILE" ]; then
  printf 'lint-api: style profile %s\n' "$PROFILE" >&2
  node "$HERE/spectral/profile-overlay.mjs" --profile "$PROFILE" --out "$RULESET"
else
  printf 'lint-api: no api-style.yaml found — running base rules only.\n' >&2
  printf 'lint-api: record your conventions in a profile to get style findings too\n' >&2
  printf '          (see %s/style/api-style.example.yaml).\n' "$HERE" >&2
  node "$HERE/spectral/profile-overlay.mjs" --out "$RULESET"
fi

[ "$KEEP_RULESET" -eq 1 ] && printf 'lint-api: derived ruleset kept at %s\n' "$RULESET" >&2

# ── Run ──────────────────────────────────────────────────────────────────────
SPECTRAL_ARGS=(lint --ruleset "$RULESET" --format "$FORMAT")
[ -n "$OUT" ] && SPECTRAL_ARGS+=(--output "$OUT")

# Spectral appends a human-readable summary line to stdout even for machine-readable
# formats, which corrupts the document. Suppress it when the output is meant to be parsed.
case "$FORMAT" in
  json|sarif|code-climate|gitlab|junit|teamcity)
    SPECTRAL_ARGS+=(--quiet) ;;
esac

# Report everything. Spectral exits 1 when findings reach --fail-severity; in report
# mode we swallow that and only surface genuine failures (status > 1).
SPECTRAL_ARGS+=(--fail-severity error)

set +e
npx --yes "$SPECTRAL_PKG" "${SPECTRAL_ARGS[@]}" "${DOCS[@]}"
STATUS=$?
set -e

if [ "$GATE" -eq 1 ]; then
  exit "$STATUS"
fi

# Spectral still exits non-zero on a genuine failure (unreadable document, broken
# ruleset). Distinguish that from "findings were reported".
if [ "$STATUS" -gt 1 ]; then
  die "spectral failed with status $STATUS"
fi
exit 0
