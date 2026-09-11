# Backlog

Work that is understood but not done. Each item states the **evidence** it rests
on, so it can be re-judged later rather than taken on faith — and dropped if the
evidence goes stale.

Effort: **S** = hours · **M** = about a day · **L** = multi-day.

---

## diagram-c4-drawio

Layout *correctness* is solved: 209 → 0 edge–node crossings across 37 diagrams,
label overlap 86,740 → 642 px². What remains is **legibility** and **aesthetics**,
which are different problems and need different tools.

### Measured weaknesses (2026-09-09)

| Finding | Evidence |
|---|---|
| Most diagrams are the wrong shape for a slide | aspect ratios 0.55 / 0.56 / 0.84 / 1.16 / 1.53 |
| Icons are mostly generic | 11 of 25 nodes resolve a real icon; the other 14 share one blue window |
| Author content is silently dropped | `caption` lost entirely; `note`, `AddRelTag`, `Rel_Back`, `BiRel` ignored by the parser |
| Small text fails WCAG AA on 3 of 6 fills | `ce` 3.45, `warn` 3.58, `ms` 4.29 against white — AA needs 4.5, and descriptions render at 8px |

Reproduce with `c4drawio score <dir> --json` and the contrast/deuteranopia check
in the session notes.

### A. Layout geometry

| # | Item | Impact | Effort |
|---|---|---|---|
| A1 | **Wrapping.** `WrappingStrategy.MULTI_EDGE` + `CuttingStrategy.ARD`. Measured: a 12-node chain went 179×1348 (ar 0.13) → 767×400 (ar **1.92**). Note `aspectRatio` alone does nothing — it only takes effect with wrapping on. Should be opt-in or auto-triggered below an ar threshold: wrapping breaks one top-to-bottom read into stacked bands, which costs narrative clarity. | high | S |
| A2 | **Routing mode.** Measured bendpoints on the same graph: ORTHOGONAL 18, POLYLINE 5, SPLINES 83. Splines are the Microsoft-reference curved look; draw.io renders them with `curved=1`. | medium | S |
| A3 | **Compaction.** `GraphCompactionStrategy` (`LEFT_RIGHT_CONNECTION_LOCKING`, `EDGE_LENGTH`) to squeeze whitespace and shorten the long edges. | medium | S |
| A4 | **Layer unzipping.** `ALTERNATING` staggers wide rows — the Willhem internal-integration boundary is 5 nodes abreast. | low–med | S |
| A5 | **Auto-tuning search.** Generate N layouts across an option grid, score each with the existing metrics, keep the best. This is the payoff of having a scoring function: it turns option tuning from guesswork into search, and is the reason not to add more ELK options speculatively. | high | M |

**Rejected:** `thoroughness`. No effect at 7 / 20 / 100 on a representative graph.

### B. Comprehension

| # | Item | Impact | Effort |
|---|---|---|---|
| B1 | **Stop dropping author content.** The `caption` bug is a correctness issue, not polish — the Willhem overview's caption explains the entire fill/border encoding and never reaches the `.drawio`. `note` matters too; architects annotate constantly. | high | S |
| B2 | **`AddRelTag` — semantic edge styling.** Every edge currently looks identical. For integration diagrams the sync/async distinction *is* the architecture; async dashed-purple vs sync solid-black carries more meaning than any node styling. | high | M |
| B3 | **Cut in-node text.** Three lines of 8px description per box today. The Microsoft reference uses none — name + technology only. Options: one line, or move descriptions to draw.io tooltips (hover, zero visual cost). | high | S |
| B4 | **Structure the legend.** Currently a flat 4-column strip mixing two orthogonal dimensions. Group as *Ownership* and *State* with subheadings. | medium | S |
| B5 | **Numbered flow.** Annotate the primary path 1..N. Usually the largest single comprehension win for a stakeholder audience — turns a topology picture into a narrative. | high | M |
| B6 | **Title block.** Title, subtitle, status, date. Currently a bare title string. | medium | S |

### C. Look and feel

| # | Item | Impact | Effort |
|---|---|---|---|
| C1 | **Style presets** — `--style c4 \| ms \| minimal`. The target spec already exists: `BanenorERP/scripts/style-guide/NORTH-STAR.md` is a complete Microsoft-Architecture-Center style guide (white fills, 36px icons as the visual anchor, thin grey borders, black curved edges, no legend). It was never implementable before because the layout engine couldn't deliver; it can now. | high | M |
| C2 | **Resolve the fill conflict.** NORTH-STAR wants white fills; we use fill for ownership. Not a real conflict — move ownership to a **coloured accent bar** (left edge or top stripe, emitted as a child cell exactly as the icon already is). Keeps two independent semantic channels *and* gets the clean look. | high | S–M |
| C3 | **Icon coverage.** 14 of 25 nodes fall back to a generic shape — the most visible defect. Three parts: extend the MS catalog (Power Automate and Fabric have official assets), add brand marks for third parties (BankID, Creditsafe, Scrive, Optimizely), give actors a distinct person glyph. Mostly asset sourcing and licensing, not code. | high | M |
| C4 | **Fix the contrast failures.** Darken `ce` (#2F9E44 → ~#237A35) and `warn`; lighten description text. A real accessibility defect at 8px, and cheap. | medium | S |

**Colourblind status — mostly fine, keep the discipline.** build-green vs
legacy-grey is risky under deuteranopia (distance 57), but build is solid and
legacy is dashed, so the dash pattern rescues it. gap vs legacy are both dashed
and rely on hue alone (distance 152 — acceptable). The rule to preserve: **every
colour distinction needs a redundant non-colour channel.** Worth stating
explicitly in `SKILL.md`.

### D. Process

| # | Item | Impact | Effort |
|---|---|---|---|
| D1 | **VLM critique loop.** The honest remaining gap. Metrics score geometry; nothing judges reading order, grouping, emphasis, or whether the diagram says the right thing. Now cheap: `c4drawio build` → Read the PNG → critique against a rubric. | high | M |
| D2 | **`c4drawio lint`.** Author-level checks geometry cannot see: orphan nodes, missing descriptions, contradictory `Lay_*` hints, node count over budget, edges to undefined ids. | medium | M |
| D3 | **Golden-image regression.** Catch visual regressions the metrics miss. | medium | M |

### Suggested sequence

| Wave | Items | Rationale |
|---|---|---|
| 1 | B1, C4, B3, A1 | Fixes a data-loss bug and the two most visible defects. All small. |
| 2 | C2, C1, A2, B4 | Coherent visual overhaul — best done as one change, not piecemeal |
| 3 | B2, B5, C3 | Highest comprehension value, more effort |
| 4 | A5, D1 | Compounding leverage; needs the rest stable first |

### Argued against

- **Chasing the remaining edge–edge crossings** (68 across 37 diagrams). Far less
  harmful than edge–node crossings, and often unavoidable.
- **Adding ELK options speculatively** without A5's search to say whether they
  help. That is how the previous heuristic engine accreted 632 lines.

### Open decision — settle before Track C

Does the default style stay **C4-canonical** (saturated semantic fills) or move to
the **Microsoft-reference look** (white fills, ownership as an accent bar)? The
choice cascades through all of Track C and restyles every existing diagram, so it
should be settled first. Mocking both against the Willhem overview would decide it
in one look.
