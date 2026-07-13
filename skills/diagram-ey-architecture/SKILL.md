---
name: diagram-ey-architecture
description: >-
  Generate EY-branded, dark-theme layered "Systems of…" enterprise / enablement
  architecture diagrams as draw.io, using a Python generator and a reusable mono
  line-icon SVG library. Use when building an EY capability-stack picture
  (CONSUME / ENABLE / CONNECT / RUN, an enablement layer, cross-cutting Trust &
  Innovation rails, a business-outcomes banner) for slides or proposals. Render
  and export with the diagram-render-drawio skill.
---

# EY draw.io Architecture Diagrams

Generate a dark, EY-branded layered architecture stack as draw.io XML with flat
mono EY-yellow line icons. A Python generator builds the XML; render and export
with the **`diagram-render-drawio`** skill.

## What it produces

A 16:9 dark canvas (`#1A1A24`) with:

- A **title** and a **Business Outcomes** banner (EY yellow on charcoal).
- Four stacked bands: **CONSUME** (Systems of Engagement + Insight) ·
  **ENABLEMENT LAYER** (yellow hero — the focus) · **CONNECT** (Systems of
  Record) · **RUN** (Foundation).
- An L-shaped **Systems of Trust** rail (left + base band) and a **Systems of
  Innovation** rail (right).
- Upward value-flow arrows.

Variants (CLI modes):

| Mode | Result |
|---|---|
| `layer` | one icon per band header + rails — cleanest for exec decks |
| `capability` | an icon in every capability box — richest, closest to a vendor reference |
| `… transparent` | omit the background rect for a transparent export |

## Files

- `icons.py` — reusable mono line-icon library (24×24 stroke SVG) + `datauri()`;
  run it to emit an icon-probe sheet for visual QA.
- `generate.py` — the diagram generator; edit its **CONTENT** section to retarget.

## Prerequisites

- `python3`
- draw.io desktop for rendering / exporting — see **`diagram-render-drawio`**.

## Use

1. Copy `generate.py` and `icons.py` into the project's `diagrams/drawio/`.
2. Edit the **CONTENT** section of `generate.py` (the `CONSUME`, `PILLARS`,
   `CONNECT`, `RUN` lists and the `TITLE` / `H_*` / `*RAIL` / `OUTCOMES` /
   `BASEBAND` strings) for the client. Set `OUTDIR` / `BASENAME` at the top.
3. Generate the variants:
   ```bash
   python3 diagrams/drawio/generate.py layer
   python3 diagrams/drawio/generate.py capability
   python3 diagrams/drawio/generate.py capability transparent
   ```
4. Render / export — see `diagram-render-drawio` → **Export Options**:
   ```bash
   DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
   "$DRAWIO" -x -f png -s 2 -o out.png            in.drawio              # preview
   "$DRAWIO" -x -f svg      -o out.svg            in.drawio              # vector
   "$DRAWIO" -x -t -f png -s 4 -o out@4x.png      in-transparent.drawio  # transparent 4x
   ```

## EY palette

| token | hex | use |
|---|---|---|
| yellow | `#FFE600` | enablement hero, icons, accents, arrows |
| dark | `#1A1A24` | canvas |
| charcoal | `#2E2E38` | cards, text on yellow |
| blue | `#1F3864` | Systems of Trust rail |
| teal | `#27ACAA` | Systems of Innovation rail |

## Icon library

`chart, ai, workflow, apps, partner, integration, orchestration, data, identity,
platform, erp, plm, mes, ot, legacy, cloud, hybrid, onprem, hub, trust,
innovation`.

Add one by appending a 24×24, stroke-only SVG fragment to `ICONS` in `icons.py`,
then `python3 icons.py` to preview. Tint per use via `datauri(name, color)`.

## Conventions & gotchas

The inline-SVG icon technique, XML double-escaping for `html=1` labels,
transparent export, and the "don't use `mxgraph.basic.*`" finding are documented
in **`diagram-render-drawio`** (Authoring Gotchas / Export Options). Keep
`icons.py` next to `generate.py` (it imports `from icons import datauri`).
