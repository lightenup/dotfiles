---
name: ey-marp
description: Create EY-branded Marp presentations. Use when the user asks you to create slides, a presentation, or a deck that should follow EY visual identity. Provides a custom CSS theme, layout heuristics with a lint script, visual spot-check workflow, and slide-pattern guidance for workshop, decision, and architecture presentations.
compatibility: Requires marp-cli (brew install marp-cli). EYInterstate font optional (falls back to Segoe UI / Calibri). Visual spot-check requires agent-browser.
license: proprietary
metadata:
  author: Andreas Jacobsen
  version: "2.0.0"
---

# EY Marp Presentation Skill

Create EY-branded presentations using Marp (Markdown Presentation Ecosystem).

---

## Step 0 — Verify Marp CLI

```bash
marp --version
```

If not installed: `brew install marp-cli` (managed via dotfiles Brewfile).

---

## Step 1 — Theme Location

The EY theme CSS is bundled with this skill at:

```
~/.factory/skills/ey-marp/ey-marp.css
```

Alternative paths (all symlinked to the same file):
- `~/.agents/skills/ey-marp/ey-marp.css`
- `~/Development/private/dotfiles/skills/ey-marp/ey-marp.css`

---

## Step 2 — Frontmatter

Every EY Marp deck MUST start with this frontmatter:

```yaml
---
marp: true
theme: ey
paginate: true
---
```

---

## Step 3 — Build Commands

All commands require `--theme` to load the EY CSS:

```bash
# HTML (for presenting)
marp --theme ~/.factory/skills/ey-marp/ey-marp.css --html --allow-local-files slides.md -o slides.html

# PDF
marp --theme ~/.factory/skills/ey-marp/ey-marp.css --pdf --allow-local-files slides.md -o slides.pdf

# Live preview server
marp --theme ~/.factory/skills/ey-marp/ey-marp.css --server .
```

When creating a Taskfile.yml for the project, use this pattern:

```yaml
version: "3"
vars:
  MARP: marp --theme ~/.factory/skills/ey-marp/ey-marp.css
tasks:
  html:
    cmds:
      - "{{.MARP}} --html --allow-local-files slides.md -o slides.html"
  serve:
    cmds:
      - "{{.MARP}} --server ."
```

---

## Step 4 — Slide Types (CSS Classes)

The theme provides 5 slide-type classes. Apply them with Marp's HTML comment directive.

### Title slide (dark background, yellow heading)

```markdown
<!-- _class: title -->

# Presentation Title
## Subtitle or context line

**Date** · **Location**
**Participants:** Name, Name, Name
```

### Section divider (blue background, centered)

```markdown
<!-- _class: section -->

# Section Name
## Optional subtitle
```

### Decision slide (yellow top border, footer badge)

Use for slides where the audience must choose between options. A small "⬡ Decision" badge appears in the bottom-left footer.

```markdown
<!-- _class: decision -->

# Decision: Topic Name

| | Option A | Option B |
|---|---|---|
| **Pro** | ... | ... |
| **Con** | ... | ... |

**We decide now.**
```

### Discovery slide (teal top border, footer badge)

Use for slides that gather information from the audience. A small "? Discovery" badge appears in the bottom-left footer.

```markdown
<!-- _class: discovery -->

# Topic — Questions for the Audience

> Discovery — we need to understand your current baseline.

- Question 1?
- Question 2?
- Question 3?

**What does this look like on your side today?**
```

### Checklist slide (yellow top border, footer badge)

Use for the summary/decision-check slide at the end of a session. A small "☑ Checklist" badge appears in the bottom-left footer.

```markdown
<!-- _class: checklist -->

# Summary — Decision Check

| # | Decision | Resolved? |
|---|---|---|
| 1 | First decision | [ ] |
| 2 | Second decision | [ ] |
| 3 | Third decision | [ ] |

**Unresolved items → backlog with owner and deadline.**
```

### Accent slide (yellow top border only)

A plain content slide with a yellow accent bar. Use for emphasis without a specific type.

```markdown
<!-- _class: accent -->

# Important Slide
Content here.
```

---

## Step 5 — Slide Structure Patterns

These patterns are proven in EY integration workshops. Follow them for consistency.

### Workshop deck structure

```
1. Title slide (title class)
2. Agenda (table: Time | Topic | Format)
3-N. Content slides (one topic per slide)
N+1. Decision check (checklist class)
N+2. Next steps
```

### One topic per slide

Never pack multiple topics into one slide. Each slide should have:
- One clear heading
- One table, one diagram, OR one short bullet list
- One question for the audience (if interactive)

### Decision slides

Present options as a comparison table with columns per option and rows for pros/cons/criteria.
Always end with **"We decide now."** or **"Which of these should we decide now vs. log for later?"**

### Discovery slides

Use blockquotes for the discovery framing, then bullet questions.
Always end with **"What does this look like on your side today?"** or similar open question.

### Agenda slide

Always use a timed agenda table:

```markdown
| Time | Topic | Format |
|---|---|---|
| 09:00 | Introduction | Walkthrough |
| 09:15 | Design decisions | Present → validate |
| 09:40 | Open questions | Alternatives → decisions |
| 09:55 | **Summary** | **Checklist** |
```

### Two-column layout

For side-by-side comparisons outside of tables, use the columns utility (requires `--html`):

```html
<div class="columns">
<div>

Left column content

</div>
<div>

Right column content

</div>
</div>
```

---

## Step 6 — EY Brand Reference

### Colors (available as CSS variables)

| Variable | Hex | Usage |
|---|---|---|
| `--ey-yellow` | #FFE600 | Primary brand, title accents, borders |
| `--ey-charcoal` | #2E2E38 | Text, dark backgrounds |
| `--ey-dark` | #1A1A24 | Deepest dark |
| `--ey-blue` | #1F3864 | H2 headings, section dividers |
| `--ey-teal` | #27ACAA | Accent, links, code borders, discovery |
| `--ey-gray-700` | #333333 | H3/H4 headings |
| `--ey-gray-500` | #6C6C6C | Secondary text, page numbers |
| `--ey-gray-300` | #C4C4CD | Table borders |
| `--ey-gray-100` | #F0F0F5 | Table stripes, code backgrounds |

### Fonts

| Weight | EY font | Fallback |
|---|---|---|
| Regular | EYInterstate Light | Segoe UI, Calibri |
| Bold | EYInterstate Regular | Segoe UI Semibold, Calibri |
| Monospace | — | Cascadia Code, Consolas |

### Style rules

- **No emojis** in headings or body text (except the theme's built-in markers)
- **Tables** use dark header row with white text, alternating row stripes
- **Blockquotes** have a yellow left border (or teal in discovery slides)
- **Code blocks** have a teal left border
- **Keep slides sparse** — large font, ample whitespace, one idea per slide

---

## Facilitation Guide Template

When creating a workshop, also create a facilitation guide alongside the slides:

```markdown
# Session Name: Facilitation Guide

**Time:** Date, HH:MM–HH:MM (X min)
**Slides:** `path/to/slides.md` (run `task open-X`)

## Timing

| Time | Topic | Format | Min |
|---|---|---|---|
| HH:MM | Topic | Present / Discuss / Decide | NN |

## Key Questions

### Topic (NN min)
- Question 1?
- Question 2?

## Decision Checklist (N min)

| # | Decision | Resolved? |
|---|---|---|
| 1 | ... | [ ] |
```

---

## Backlog Template

When creating a workshop with multiple sessions, track preparation in a backlog:

```markdown
# Workshop Backlog

## Preparation Tasks
- [ ] Share pre-read material with participants
- [ ] Prepare context/case for discussion

## Session-to-Decision Mapping

| Decision | Primary session | Also informs |
|---|---|---|

## Post-Workshop Deliverables

| # | Deliverable | Source session | Status |
|---|---|---|---|
```

---

## Step 7 — Layout Heuristics

These rules prevent slides from overflowing, becoming unreadable on projectors, or turning into walls of text. The cardinal rule: **prefer splitting into a new slide over reducing font size.**

### Content density limits

| Rule | Limit | What to do when exceeded |
|---|---|---|
| Bullet points per slide | max 7 | Split into two slides, or move lower-priority items to `<!-- notes -->` |
| Table rows (incl. header) | max 8 | Split table across slides, or move to an appendix slide |
| Table columns | max 5 | Remove a column, transpose, or split into two tables |
| Code block lines | max 10 | Trim to essential lines, or split across slides |
| Total content lines per slide | max 18 | Split into two slides |
| Heading length | max ~55 chars | Shorten, or move detail to a `## subtitle` |
| Bullet nesting depth | max 2 levels | Flatten, or restructure as a table |

### Visual element limits

| Rule | Rationale |
|---|---|
| One visual element per slide (image OR table OR code block) | Mixed visuals (image + table, or code + table) are almost always too dense |
| If a slide has an image, text should be minimal (heading + 1-2 lines) | The image is the content; text is the label |
| Title/section slides should have max 4-6 lines total | These are visual anchors, not content carriers |

### Pacing

| Session length | Target slide count | Avg. minutes per slide |
|---|---|---|
| 1 hour | 10–15 | 4–6 min |
| 2 hours | 20–30 | 4–6 min |
| Half-day (3-4h) | 30–45 | 5–8 min |

### Font size decisions

When content is too dense for a slide:
1. **First choice:** split into two slides (one topic per slide)
2. **Second choice:** move supporting detail to `<!-- notes -->` (presenter notes)
3. **Third choice:** remove content that doesn't serve the slide's purpose
4. **Last resort only:** reduce table font size via inline style — never below 0.7em

Never reduce body text or heading font sizes. If a heading doesn't fit, shorten the text.

---

## Step 8 — Lint Before Building

A static lint script checks slides against the heuristics above. Run it BEFORE rendering to catch issues early.

### Location

```
~/.factory/skills/ey-marp/lint-slides.sh
```

### Usage

```bash
# Check a deck
~/.factory/skills/ey-marp/lint-slides.sh slides.md

# Check with fix suggestions
~/.factory/skills/ey-marp/lint-slides.sh slides.md --fix-hints
```

### Example output

```
  WARN (slide 7, line ~107): Table too tall (9 rows, max 8)
       FIX: Split table across slides or move to an appendix slide
  WARN (slide 8, line ~132): Code block too tall (16 lines, max 10)
       FIX: Trim to the essential lines or split across slides

Deck: slides.md
Slides: 19
Result: 2 warning(s)
```

### When to lint

Run the linter:
1. After creating a new deck (before first render)
2. After adding slides or content to an existing deck
3. Before sharing the deck with stakeholders

Fix all warnings before rendering. The lint script exits with code 0 (all pass) or 1 (warnings found).

### Adding lint to Taskfile

```yaml
tasks:
  lint:
    desc: Lint all slide decks
    cmds:
      - "~/.factory/skills/ey-marp/lint-slides.sh session-1/slides.md --fix-hints || true"
      - "~/.factory/skills/ey-marp/lint-slides.sh session-2/slides.md --fix-hints || true"
```

---

## Step 9 — Visual Spot-Check (Render → Screenshot → Inspect)

Static linting catches most issues, but some problems only show up visually: SVG overflow, table column squeezing, font rendering differences, color contrast on projectors. After linting and rendering, do a targeted visual check.

### When to spot-check

Not every slide — focus on the **high-risk slides**:
- Slides with tables (especially 5+ rows or 4+ columns)
- Slides with embedded images/SVGs
- Slides with code blocks
- The title slide (brand presence)
- The checklist slide (often the densest)

### Spot-check workflow

```bash
# 1. Render to HTML
marp --theme ~/.factory/skills/ey-marp/ey-marp.css --html --allow-local-files slides.md -o slides.html

# 2. Open in headless browser
agent-browser open file:///absolute/path/to/slides.html

# 3. Screenshot the title slide
agent-browser screenshot /tmp/slide-check-title.png

# 4. Navigate to a high-risk slide (e.g., slide 7)
# Press ArrowRight to advance slides
agent-browser press ArrowRight   # repeat N times to reach target slide
agent-browser screenshot /tmp/slide-check-table.png

# 5. Read the screenshot to visually inspect
# (use the Read tool on the PNG)

# 6. Close browser
agent-browser close
```

### What to look for

| Issue | How it appears | Fix |
|---|---|---|
| **Table overflow** | Columns squeezed, text wrapping mid-word | Reduce columns, shorten cell text, or split table |
| **Text truncation** | Content cut off at bottom of slide | Split into two slides (do NOT shrink font) |
| **SVG overflow** | Diagram extends beyond slide edges | Reduce `w:` directive or use a smaller viewBox |
| **Heading wrap** | H1 breaks onto two lines | Shorten heading text |
| **Empty slide** | Only heading + 1-2 lines, looks sparse | Merge with adjacent slide or add supporting content |
| **Low contrast** | Light gray text hard to read | Use `--ey-gray-700` (#333) minimum for body text |
| **Misaligned layout** | Content shifted or unbalanced | Check for stray HTML or missing blank lines between elements |

### The full quality loop

```
Write slides
    ↓
Lint (static checks)
    ↓ fix warnings
Render to HTML
    ↓
Visual spot-check (screenshot high-risk slides)
    ↓ fix visual issues
Final render
    ↓
Present
```

Run the lint + fix cycle first (fast, catches 80% of issues). Only spot-check after lint passes. This keeps the feedback loop tight without screenshotting every slide on every iteration.
