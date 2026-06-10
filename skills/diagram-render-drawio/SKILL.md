---
name: diagram-render-drawio
description: >-
  Render draw.io diagrams to PNG/SVG images. Use when the user wants to
  export or verify a draw.io diagram (.drawio file). Requires the draw.io
  desktop app installed on macOS.
---

# Render draw.io Diagrams

Render draw.io diagrams to image files using the draw.io desktop CLI.

## Project Convention

draw.io source files live in `diagrams/drawio/` at the project root.
Create the directory if it does not exist. Rendered output goes beside
the source file (e.g. `diagrams/drawio/arch.drawio` -> `diagrams/drawio/arch.png`).

## Prerequisites

- **draw.io desktop app**: Must be installed at `/Applications/draw.io.app/` (macOS).
  Download from: https://github.com/jgraph/drawio-desktop/releases

Verify:
```bash
/Applications/draw.io.app/Contents/MacOS/draw.io --version
```

## Render Instructions

1. Locate the `.drawio` input file.

2. Determine the output path: sibling file with `.png` extension by default.

3. Run the render command:
   ```bash
   DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
   "$DRAWIO" -x -f png -s 2 -o "<output-file>" "<input-file>"
   ```

   Options:
   - `-f png|svg|pdf`: Output format (default: png).
   - `-s 2`: Scale factor for rasterisation (default: 2 for retina).
   - `-p <page>`: Export specific page index (0-based).

4. If the render fails with "exceeds the max texture size", retry with scale=1:
   ```bash
   "$DRAWIO" -x -f png -s 1 -o "<output-file>" "<input-file>"
   ```

5. After rendering, use the Read tool to display the resulting image to the
   user so they can verify it visually.

6. Report the output path.

## Batch Rendering

To render all `.drawio` files in the diagrams directory:
```bash
DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
for f in diagrams/drawio/*.drawio; do
  out="${f%.drawio}.png"
  "$DRAWIO" -x -f png -s 2 -o "$out" "$f"
done
```

## Troubleshooting

- **"draw.io not found"**: Install from https://github.com/jgraph/drawio-desktop/releases
- **Empty output**: Check that the `.drawio` file has content beyond the root cells
  (`grep -c '<mxCell' file.drawio` should be > 2).
- **Texture limit exceeded**: Use `-s 1` instead of `-s 2` for very large diagrams.

## Verification

- The output file must exist and be non-empty.
- Display the rendered image inline for visual confirmation.
