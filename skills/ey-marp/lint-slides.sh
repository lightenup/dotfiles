#!/usr/bin/env bash
# lint-slides.sh — Static layout heuristics for Marp slide decks.
# Usage: lint-slides.sh slides.md [--fix-hints]
#
# Checks each slide against content-density and layout rules.
# With --fix-hints, prints suggested fixes (split/move to notes).
# Exit code: 0 = all pass, 1 = warnings found.
set -euo pipefail

FILE="${1:?Usage: lint-slides.sh <slides.md> [--fix-hints]}"
FIX_HINTS="${2:-}"

if [ ! -f "$FILE" ]; then
  echo "ERROR: File not found: $FILE" >&2
  exit 2
fi

# ── Thresholds ──────────────────────────────────────────────────
MAX_BULLET_POINTS=7
MAX_TABLE_ROWS=8          # including header
MAX_TABLE_COLS=5
MAX_CODE_LINES=10
MAX_CONTENT_LINES=18      # total non-empty lines per slide
MAX_HEADING_CHARS=55
MAX_NEST_DEPTH=2           # bullet nesting levels
MAX_VISUAL_ELEMENTS=1      # images or code blocks per slide (tables excluded)
MAX_SLIDES_PER_HOUR=15     # pacing heuristic
# ────────────────────────────────────────────────────────────────

WARNINGS=0
SLIDE_NUM=0
SLIDE_START_LINE=0
IN_CODE=0
IN_FRONTMATTER=0
FRONTMATTER_DONE=0

# Accumulate per-slide stats
reset_slide() {
  BULLET_COUNT=0
  TABLE_ROW_COUNT=0
  TABLE_COL_COUNT=0
  CODE_LINE_COUNT=0
  CODE_BLOCK_COUNT=0
  CONTENT_LINES=0
  IMAGE_COUNT=0
  MAX_NEST=0
  HAS_HEADING=0
  HEADING_TEXT=""
}

warn() {
  local msg="$1"
  echo "  WARN (slide $SLIDE_NUM, line ~$SLIDE_START_LINE): $msg"
  WARNINGS=$((WARNINGS + 1))
}

hint() {
  if [ "$FIX_HINTS" = "--fix-hints" ]; then
    echo "       FIX: $1"
  fi
}

check_slide() {
  [ "$SLIDE_NUM" -eq 0 ] && return

  # Skip title/section slides (minimal content by design)
  if [ "$HAS_HEADING" -eq 1 ] && [ "$CONTENT_LINES" -le 4 ]; then
    return
  fi

  if [ "$HAS_HEADING" -eq 0 ]; then
    warn "No heading (# ...) found on slide"
    hint "Every slide should have exactly one h1 heading"
  fi

  if [ -n "$HEADING_TEXT" ] && [ "${#HEADING_TEXT}" -gt "$MAX_HEADING_CHARS" ]; then
    warn "Heading too long (${#HEADING_TEXT} chars, max $MAX_HEADING_CHARS): \"$HEADING_TEXT\""
    hint "Shorten heading or move detail to subtitle (## ...)"
  fi

  if [ "$BULLET_COUNT" -gt "$MAX_BULLET_POINTS" ]; then
    warn "Too many bullet points ($BULLET_COUNT, max $MAX_BULLET_POINTS)"
    hint "Split into two slides or move lower-priority items to <!-- notes -->"
  fi

  if [ "$TABLE_ROW_COUNT" -gt "$MAX_TABLE_ROWS" ]; then
    warn "Table too tall ($TABLE_ROW_COUNT rows, max $MAX_TABLE_ROWS)"
    hint "Split table across slides or move to an appendix slide"
  fi

  if [ "$TABLE_COL_COUNT" -gt "$MAX_TABLE_COLS" ]; then
    warn "Table too wide ($TABLE_COL_COUNT columns, max $MAX_TABLE_COLS)"
    hint "Remove a column, transpose the table, or split into two tables"
  fi

  if [ "$CODE_LINE_COUNT" -gt "$MAX_CODE_LINES" ]; then
    warn "Code block too tall ($CODE_LINE_COUNT lines, max $MAX_CODE_LINES)"
    hint "Trim to the essential lines or split across slides"
  fi

  if [ "$CONTENT_LINES" -gt "$MAX_CONTENT_LINES" ]; then
    warn "Slide too dense ($CONTENT_LINES content lines, max $MAX_CONTENT_LINES)"
    hint "Split into two slides — prefer splitting over reducing font size"
  fi

  if [ "$MAX_NEST" -gt "$MAX_NEST_DEPTH" ]; then
    warn "Bullet nesting too deep ($MAX_NEST levels, max $MAX_NEST_DEPTH)"
    hint "Flatten nested bullets or restructure as a table"
  fi

  visual_elements=$((IMAGE_COUNT + CODE_BLOCK_COUNT))
  if [ "$visual_elements" -gt "$MAX_VISUAL_ELEMENTS" ] && [ "$TABLE_ROW_COUNT" -gt 0 ]; then
    warn "Mixed visual elements (image/code + table on same slide)"
    hint "One visual element per slide: image OR table OR code block"
  fi
}

reset_slide

while IFS= read -r line || [ -n "$line" ]; do
  SLIDE_START_LINE=$((SLIDE_START_LINE + 1))

  # Track frontmatter
  if [ "$FRONTMATTER_DONE" -eq 0 ]; then
    if [ "$SLIDE_START_LINE" -eq 1 ] && [ "$line" = "---" ]; then
      IN_FRONTMATTER=1
      continue
    fi
    if [ "$IN_FRONTMATTER" -eq 1 ]; then
      if [ "$line" = "---" ]; then
        IN_FRONTMATTER=0
        FRONTMATTER_DONE=1
      fi
      continue
    fi
  fi

  # Track code blocks
  if echo "$line" | grep -qE '^\s*```'; then
    if [ "$IN_CODE" -eq 0 ]; then
      IN_CODE=1
      CODE_BLOCK_COUNT=$((CODE_BLOCK_COUNT + 1))
    else
      IN_CODE=0
    fi
    continue
  fi
  if [ "$IN_CODE" -eq 1 ]; then
    CODE_LINE_COUNT=$((CODE_LINE_COUNT + 1))
    CONTENT_LINES=$((CONTENT_LINES + 1))
    continue
  fi

  # Slide separator
  if [ "$line" = "---" ]; then
    check_slide
    SLIDE_NUM=$((SLIDE_NUM + 1))
    SLIDE_START_LINE=$((SLIDE_START_LINE))
    reset_slide
    continue
  fi

  # Skip HTML comments and empty lines for content count
  if echo "$line" | grep -qE '^\s*<!--'; then
    continue
  fi
  if [ -z "$(echo "$line" | tr -d '[:space:]')" ]; then
    continue
  fi

  CONTENT_LINES=$((CONTENT_LINES + 1))

  # Heading
  if echo "$line" | grep -qE '^# [^#]'; then
    HAS_HEADING=1
    HEADING_TEXT="${line#\# }"
  fi

  # Bullets
  if echo "$line" | grep -qE '^\s*[-*+] '; then
    BULLET_COUNT=$((BULLET_COUNT + 1))
    # Count nesting depth
    stripped="${line%%[-*+]*}"
    spaces="${#stripped}"
    nest=$((spaces / 2 + 1))
    if [ "$nest" -gt "$MAX_NEST" ]; then
      MAX_NEST=$nest
    fi
  fi

  # Table rows
  if echo "$line" | grep -qE '^\|'; then
    TABLE_ROW_COUNT=$((TABLE_ROW_COUNT + 1))
    # Count columns from first table row (skip separator rows)
    if ! echo "$line" | grep -qE '^\|\s*-'; then
      cols=$(echo "$line" | tr -cd '|' | wc -c)
      cols=$((cols - 1))
      if [ "$cols" -gt "$TABLE_COL_COUNT" ]; then
        TABLE_COL_COUNT=$cols
      fi
    fi
  fi

  # Images
  if echo "$line" | grep -qE '!\['; then
    IMAGE_COUNT=$((IMAGE_COUNT + 1))
  fi

done < "$FILE"

# Check last slide
check_slide

# Pacing check
if [ "$SLIDE_NUM" -gt 0 ]; then
  echo ""
  echo "Deck: $FILE"
  echo "Slides: $SLIDE_NUM"
  if [ "$WARNINGS" -eq 0 ]; then
    echo "Result: ALL PASS"
  else
    echo "Result: $WARNINGS warning(s)"
  fi
fi

exit $(( WARNINGS > 0 ? 1 : 0 ))
