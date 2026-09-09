---
name: diagram-c4-drawio
description: >-
  Turn C4 PlantUML into laid-out, properly routed draw.io diagrams, render them
  to PNG/SVG, and measure layout quality. Use when converting .puml to .drawio,
  when an architecture diagram has edges crossing through boxes or overlapping
  labels, when boundaries or nested C4 components render wrong, or when
  rendering/exporting a .drawio file. Handles C4 L1-L3 (Person, System,
  Container, Component), nested boundaries, tag palettes, Microsoft/Azure icons,
  and hand-polish overrides.
---

# C4 PlantUML → draw.io

Everything runs through one command. Check it first:

```bash
c4drawio doctor
```

## The one command you usually want

```bash
c4drawio build diagrams/plantuml/arch.puml
```

`build` = convert → render → score. It writes `diagrams/drawio/arch.drawio`,
renders `arch.png` beside it, and prints the quality score.

Then **look at the PNG with the Read tool** — always. The score catches geometry,
not whether the diagram says the right thing.

## Subcommands

| Command | Does |
|---|---|
| `c4drawio build <file.puml>` | convert + render + score (the default choice) |
| `c4drawio convert <file.puml>` | PlantUML → `.drawio` only |
| `c4drawio render <file.drawio>` | `.drawio` → PNG/SVG/PDF |
| `c4drawio score <path...>` | measure layout quality |
| `c4drawio doctor` | check the toolchain |

Useful flags:

```bash
c4drawio build arch.puml --force            # overwrite an existing .drawio
c4drawio render arch.drawio --format svg    # svg / pdf, --scale 1|2|3
c4drawio score diagrams/drawio --json       # machine-readable
c4drawio score diagrams/drawio --max-crossings 0   # exit 2 if any diagram fails
c4drawio score arch.puml                    # score a source without writing a file
```

Exit codes: `0` ok, `1` error, `2` quality gate failed.

## Conventions

```
diagrams/
  plantuml/
    arch.puml                 # source
    arch.overrides.json       # optional hand-polish (see below)
    _style.puml               # shared AddElementTag palette; underscore = not a diagram
  drawio/
    icons.json                # optional sprite -> shape map
    arch.drawio               # generated
    arch.png                  # rendered
```

`convert` infers `plantuml/x.puml → drawio/x.drawio` and finds `icons.json` and
the overrides sidecar automatically. Override with `-o`, `--icons`, `--overrides`.

**Existing `.drawio` files are never overwritten without `--force`.**

## Layout comes from ELK, not draw.io

This is the thing that makes the output usable, and it is worth understanding.

draw.io's orthogonal router is **local**: it routes around an edge's endpoints,
never around the nodes in between. Any edge spanning more than adjacent ranks
gets drawn straight through whatever is in the way. That cannot be fixed by
tweaking ports or spacing.

So layout and routing are computed by the **Eclipse Layout Kernel**, which ships
inside `plantuml.jar` (along with EMF and Guava) — no extra dependency, works
offline. ELK does global, hierarchy-aware, obstacle-avoiding orthogonal routing
and returns exact bend points, emitted as `<Array as="points">`, which draw.io
honours. It also reserves space for edge labels, so labels do not land on nodes
and are never truncated.

Measured over 37 real diagrams when this replaced the previous heuristic engine:
**209 → 0 edge–node crossings**; label overlap **86,740 → 642 px²**.

### Consequences you must know

- **`Lay_D` / `Lay_U` are inert.** Edge direction drives the layering.
- **`Lay_R` / `Lay_L` order same-layer siblings only.** Between two nodes joined
  by a `Rel` they cannot apply: the edge defines the rank, and a node cannot be
  both below and beside its predecessor.
- This matches PlantUML's own `!pragma layout elk`, so the PlantUML render and
  the draw.io render now agree.

## Reading the score

```
25 nodes, 29 edges | edge-node crossings: 0 | edge-edge crossings: 7 |
label overlap: 0px2 | node overlap: 0px2 | 2682x1758 (ar 1.53)
```

| Metric | Target | Meaning |
|---|---|---|
| **edge-node crossings** | **0** | an edge cut through a box. Never acceptable |
| edge-edge crossings | ≲ edge count | edges crossing each other. Sometimes unavoidable |
| label overlap | ~0 | label area sitting on a node, px² |
| node overlap | 0 | two boxes overlapping. Always a bug |
| aspect ratio | 0.4–4.0 | width/height. Slides are landscape |

If edge–node crossings are not 0, that is a bug in this tool, not something to
work around. Investigate rather than hand-editing the output.

## Hand-polish: sidecar, never the .drawio

Manual nudges go in `<name>.overrides.json` beside the `.puml`. Editing the
generated `.drawio` means the next regeneration destroys the work.

```json
{
  "nodes": { "apim": { "x": 420, "y": 300 } },
  "edges": { "web->apim": { "points": [[430, 210], [430, 290]] } }
}
```

Edge keys are `"<sourceId>-><targetId>"`. Anything unspecified keeps its computed
value, and unknown ids are ignored — a stale sidecar never breaks a build.

## Authoring notes

Structure a diagram so ELK can lay it out well:

- **Use `Rel_D` for the primary flow.** Layering follows edge direction, so a
  consistent direction gives a clean top-to-bottom read.
- **Put shared styling in `_style.puml`** and `!include` it. Includes are
  resolved, so the tag palette and legend apply. Files starting with `_` are
  partials, not diagrams.
- **Fill = one dimension, border = another.** Tags merge *per property*, first
  tag wins, so a border-only tag can overlay a fill tag:

  ```
  AddElementTag("ey",  $bgColor="#2E6DB4")
  AddElementTag("gap", $borderColor="#E8590C", $borderThickness="3", $borderStyle="dashed")
  Container(x, "X", ".NET", "d", $tags="gap+ey")   ' EY-owned, interface undefined
  ```

- **Icons**: `$sprite="AzureServiceBus"` resolves against the bundled Microsoft
  icon library (see `reference/icons.md`). Anything else needs `icons.json`.

## Supported PlantUML

- **Elements**: `Person`, `System`, `Container`, `Component`, plus every
  `Db` / `Queue` / `_Ext` variant (`ContainerDb`, `ComponentQueue`,
  `SystemDb_Ext`, …). `Container*`/`Component*` take
  `(alias, label, technology, description)`; `Person*`/`System*` take
  `(alias, label, description)`.
- **Boundaries**: `System_Boundary`, `Container_Boundary`,
  `Enterprise_Boundary`, bare `Boundary`, nested arbitrarily.
- **Includes**: local `!include`; stdlib `<C4/...>` skipped.
- **Relationships**: `Rel`, `Rel_D/U/L/R`, freeform arrows.
- **Tags**: `$bgColor`, `$fontColor`, `$legendText`, `$borderColor`,
  `$borderThickness`, `$borderStyle`.

Sequence diagrams are **not** C4 — render those with `diagram-render-plantuml`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `layout engine: UNAVAILABLE` | no JDK or no `plantuml.jar`. `c4drawio doctor` |
| Boundary renders empty | old converter bug; ensure this skill's version is in use |
| Colours missing, no legend | `!include _style.puml` unresolved — use a path relative to the `.puml` |
| Every node has the same icon | no `$sprite`, or the sprite is not in `icons.json` / the MS catalog |
| `render` fails on a huge canvas | texture limit; retried at `--scale 1` automatically |
| Empty PNG | check the `.drawio` has content: `grep -c '<mxCell' file.drawio` > 2 |

## Deeper reference

- `reference/architecture.md` — how the pipeline fits together, extending it
- `reference/icons.md` — the Microsoft icon catalog and adding icons
- `reference/python-api.md` — programmatic use

Library: `skills/_lib/puml_drawio`. Tests: `python3 -m pytest skills/_lib/puml_drawio/tests`.
