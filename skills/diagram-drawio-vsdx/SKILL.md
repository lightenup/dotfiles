---
name: diagram-drawio-vsdx
description: >-
  Convert draw.io diagrams to editable Microsoft Visio .vsdx files. Use when a
  client or colleague needs Visio rather than draw.io, when exporting an
  architecture diagram for a deliverable, or when a .drawio file has to become
  .vsdx. Handles multi-page files, compressed .drawio payloads, AWS/Azure/BPMN
  stencils, connector glue, and icon rasterisation. Runs offline after first
  install. Produces .drawio input with the diagram-c4-drawio or
  diagram-ey-architecture skills.
---

# draw.io → Visio (.vsdx)

The last step of the diagram pipeline: `c4drawio` turns PlantUML into
`.drawio`, this turns `.drawio` into something that opens in Visio.

Check the toolchain first:

```bash
drawiovsdx doctor
```

## The one command you usually want

```bash
drawiovsdx convert diagrams/drawio/arch.drawio
```

Writes `diagrams/vsdx/arch.vsdx`, mirroring the `diagrams/plantuml/` →
`diagrams/drawio/` convention. A whole directory works too:

```bash
drawiovsdx convert diagrams/drawio --all
```

## Exit codes carry the verdict

| code | meaning |
|---|---|
| 0 | converted, nothing lost |
| 1 | error — bad input, missing toolchain, failed conversion |
| 2 | bad usage |
| 3 | **converted, but shapes or icons were lost** |

Exit 3 is the point of this tool. draw.io renders a shape it cannot resolve as
a plain rectangle, and silently drops an icon it cannot load. The resulting
`.vsdx` opens cleanly in Visio and is quietly wrong — the worst outcome for
something going to a client. So conversion is **strict by default** and says
what went missing:

```
wrote diagrams/vsdx/arch.vsdx (1 page(s), 48622 bytes)
  fidelity loss: 2 image(s) dropped [image-not-found]
```

Use `--no-strict` only when you have looked at the loss and accepted it.

## Icons need draw.io Desktop

`diagram-c4-drawio` writes Azure and Microsoft icons as paths into draw.io's
own bundled library (`img/lib/azure2/...`). Those resolve inside draw.io
Desktop, which is why `c4drawio render` works — but a headless converter has
nothing to resolve them against.

So the converter is pointed at draw.io Desktop's webapp, including the
`app.asar` archive it ships in. `doctor` reports whether one was found; if not,
every bundled icon is dropped and you will see it in the exit code. Override
with `--image-root` or `$DRAWIO_IMAGE_ROOT`.

Icons from `diagram-ey-architecture` are embedded SVG and need no image root —
they are rasterised into the package automatically, since Visio cannot hold
vector images.

## Options

```
drawiovsdx convert <input> [options]

  -o, --output PATH   output path (single input only)
  --all               recurse into subdirectories
  --no-strict         accept fidelity loss and exit 0
  --remote-images     allow fetching http(s) images over the network
  --image-root PATH   where to resolve draw.io-internal icon paths (repeatable)
  --json              machine-readable report
```

`--json` emits the converter's own report — pages, byte count, every warning,
and a prose description of any degradation. That is the interface to use from
a script.

## First run

The Node converter lives in a private repo
(`lightenup/lightenup-drawio-vsdx`) rather than in dotfiles, because dotfiles
is public and the converter vendors ~40 MB of draw.io stencils. It bootstraps
on first `convert` into `~/.local/share/drawio-vsdx/<pin>/`, using `gh` for
auth. Needs `gh`, `npm` and Node 18+ once; offline thereafter.

The install is **pinned to a specific commit**, and installs are keyed by the
pin so a bump lands alongside the old one rather than mutating it. Bumping is a
deliberate edit to `PINNED_REF` in `_lib/drawio_vsdx/bootstrap.py` — a
converter change can alter the appearance of a client deliverable, so it should
never arrive on its own. Point `$DRAWIO_VSDX_HOME` at your own checkout when
working on the converter itself.

## What survives conversion

Multi-page files (each page becomes a Visio page, names preserved), compressed
`.drawio` payloads, ~766 programmatic shapes plus ~8,163 stencil shapes,
connector glue (arrows stay attached when boxes move in Visio), geometry in
inches, fills, strokes, arrowheads, text, and images.

Round-trip fidelity is inherently lossy — jgraph's own position is that the
draw.io and Visio data models differ. Boxes-and-arrows convert very well;
elaborate diagrams less so. Text placement drifts slightly, because the
converter has no browser layout engine and approximates label metrics.

## Tests

```bash
task skills:test
```
