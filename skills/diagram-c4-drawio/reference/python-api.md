# Python API

The CLI covers normal use. Reach for the API when embedding the pipeline in a
larger script.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".agents/skills/_lib"))

from puml_drawio import parse_file, generate, load_icon_map
from puml_drawio.elk_layout import load_overrides
from puml_drawio.metrics import measure

load_icon_map(Path("diagrams/drawio/icons.json"))        # optional
src = Path("diagrams/plantuml/arch.puml")

xml = generate(parse_file(src), overrides=load_overrides(src))
Path("diagrams/drawio/arch.drawio").write_text(xml, encoding="utf-8")

m = measure(xml)
assert m.edge_node_crossings == 0, m.crossing_detail
print(m.summary())
```

Use `parse_file` rather than `parse` — it resolves `!include` relative to the
source, which is what makes a shared `_style.puml` palette work. `parse(text)`
takes an optional `base_dir` if you already have the source in memory.

## Entry points

| Callable | Purpose |
|---|---|
| `parse_file(path) -> Diagram` | parse, resolving includes |
| `parse(text, base_dir=None) -> Diagram` | parse a string |
| `generate(diagram, overrides=None) -> str` | draw.io XML |
| `load_icon_map(path)` | register a sprite → shape map |
| `elk_layout.layout(diagram, ...) -> ElkResult` | layout only, no XML |
| `elk_layout.load_overrides(puml_path) -> dict` | read the sidecar |
| `elk_layout.available() -> bool` | is the Java toolchain present |
| `metrics.measure(xml) -> Metrics` | score XML |
| `metrics.measure_file(path) -> Metrics` | score a file |
| `cli.main(argv) -> int` | the CLI, for scripting |

## Types

`Diagram` — `title`, `components`, `boundaries`, `relationships`,
`layout_hints`, `tag_styles`.

`Metrics` — `node_count`, `edge_count`, `edge_node_crossings`,
`edge_edge_crossings`, `label_overlap_area`, `node_overlap_area`, `width`,
`height`, `aspect_ratio`, `boxes`, `crossing_detail`. Plus `.summary()` and
`.is_worse_than(other)` for before/after comparison.

`ElkResult` — `nodes` (id → parent-relative `(x, y, w, h)`), `edges`
(`"src->tgt"` → `EdgeRoute`), `abs_rect(id)`, `abs_origin(id)`, `width`,
`height`.

## Custom layout options

```python
from puml_drawio import elk_layout

result = elk_layout.layout(
    diagram,
    options={"direction": "RIGHT",
             "layered.spacing.nodeNodeBetweenLayers": "90"},
)
```

Supported keys are the `case` labels in `elk/ElkDriver.java`. Unknown keys are
ignored silently, so assert on the resulting geometry.

## Comparing two layouts

```python
from puml_drawio.metrics import measure

before = measure(old_xml)
after = measure(new_xml)
assert not after.is_worse_than(before), f"{before.summary()} -> {after.summary()}"
```
