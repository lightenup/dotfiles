# Architecture

How the pipeline fits together, and where to change things.

```
 arch.puml
    │  puml_parser.parse_file()      resolves !include, reads C4 macros + tags
    ▼
 Diagram                            components, boundaries, relationships, tag_styles
    │  elk_layout.layout()           emits a line protocol on stdin
    ▼
 ElkDriver (Java)                   org.eclipse.elk from plantuml.jar
    │                               returns JSON: node rects, edge bendpoints, label rects
    ▼
 ElkResult                          + overrides sidecar merged here
    │  drawio_generator.generate()   styles, icons, waypoints, legend
    ▼
 arch.drawio
    │  metrics.measure()             crossings, overlaps, aspect ratio
    ▼
 score                              gate: edge-node crossings must be 0
```

## Modules

| File | Responsibility |
|---|---|
| `puml_parser.py` | PlantUML C4 → `Diagram`. Include resolution, tag parsing. No geometry. |
| `elk_layout.py` | `Diagram` → `ElkResult`. Drives the Java driver, merges overrides. |
| `elk/ElkDriver.java` | Thin ELK wrapper. Line protocol in, JSON out. |
| `drawio_generator.py` | `Diagram` + `ElkResult` → draw.io XML. All styling lives here. |
| `metrics.py` | draw.io XML → `Metrics`. Reads the *output*, not the intent. |
| `icons.py` | Sprite/alias → embedded SVG data URI. |
| `cli.py` | The `c4drawio` command. |

The split that matters: **`metrics.py` parses the emitted XML rather than
inspecting the layout result.** It therefore scores what the renderer will
actually draw, including any hand-polish overrides, and would catch a bug in the
generator that the layout engine knew nothing about.

## The Java driver

ELK lives inside `plantuml.jar` (`org.eclipse.elk.*`, plus EMF and Guava), which
the diagram toolchain already downloads. `elk/ElkDriver.java` is compiled on
first use into `~/.cache/puml_drawio/elk` and recompiled when the source changes.

`plantuml.jar` bundles no JSON parser, so **input** uses a line protocol and only
**output** is JSON, which Java can emit with `printf`. All emitted values are
numbers or caller-supplied ids, so no string escaping is needed.

```
OPT  <key> <value>                        root layout option
NODE <id> <parentId|-> <w> <h>            parents must precede children
PAD  <id> <top> <right> <bottom> <left>   boundary header room
MINSIZE <id> <w> <h>                      keeps a boundary wider than its title
EDGE <id> <srcId> <tgtId> <lblW> <lblH>   0 0 = no label
```

Output geometry is **parent-relative** for nodes (draw.io's cell model), and edge
points are in the coordinate space of the edge's ELK container; `elk_layout.py`
converts those to absolute.

### Traps worth knowing

- **ELK transposes `NODE_SIZE_MINIMUM` for vertical directions.** It works
  left-to-right internally and rotates. `addMinSize` swaps the axes for
  `DOWN`/`UP`. Covered by `TestBoundaryMinimumWidth`.
- **`considerModelOrder` weighs node *and* edge declaration order.** Both must be
  sorted consistently or a `Lay_R` hint loses to the edge order. See
  `_ordered_components` and the sorting of `rels` in `elk_layout.layout`.
- **Only leaf nodes are obstacles** in `metrics.py`. A boundary legitimately
  contains its children, and edges legitimately enter it.

## Adding a layout option

1. Add a `case` in `ElkDriver.applyOption` mapping the name to the ELK property.
2. Add the default to `DEFAULT_OPTIONS` in `elk_layout.py`.
3. Add a test asserting the geometric consequence, not the option value.

Unknown options are ignored rather than fatal, so a stale option name fails
quietly — which is why step 3 matters.

## Changing styling

All of it is in `drawio_generator.py`: `_comp_style`, `_boundary_style`,
`_edge_style`, `_html_value`, and the `FALLBACK_ICONS` map. Node *size* comes
from `_comp_width` / `_comp_height`, which are wrap-aware — if you change fonts
or padding, update `_wrapped_line_count`'s glyph-advance constant too, or text
will overflow its box.

## Testing

```bash
python3 -m pytest skills/_lib/puml_drawio/tests -q
```

| File | Covers |
|---|---|
| `test_puml_parser.py` | macros, includes, tags, boundaries |
| `test_drawio_generator.py` | styling, icons, waypoint emission, tag merging |
| `test_elk_layout.py` | the ELK backend, hierarchy, obstacle avoidance, overrides |
| `test_metrics.py` | the geometry primitives and the scorer |
| `test_layout_quality.py` | **the gate** — budgets on a dense, cyclic diagram |
| `test_cli.py` | subcommands, exit codes, output shape |

`test_layout_quality.py` is the one that stops regressions. It asserts
consequences ("no edge crosses a node") rather than implementation, so it stays
valid if the engine is replaced.

Tests requiring Java skip cleanly when it is absent.
