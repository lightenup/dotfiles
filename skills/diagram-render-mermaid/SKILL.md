---
name: diagram-render-mermaid
description: >-
  Render Mermaid diagrams to PNG/SVG images. Use when the user wants to
  preview, export, or verify a Mermaid diagram from a .md or .mmd file.
  Requires Node.js >= 22 (use system Node via nvm if needed).
---

# Render Mermaid Diagrams

Render Mermaid diagrams to image files using `@mermaid-js/mermaid-cli` (mmdc).

## Project Convention

Mermaid source files live in `diagrams/mermaid/` at the project root.
Create the directory if it does not exist. Rendered output goes beside
the source file (e.g. `diagrams/mermaid/flow.mmd` -> `diagrams/mermaid/flow.png`).

## Prerequisites

- Node.js >= 22 is required (chevrotain/puppeteer dependency).
- On machines using nvm with an older default, activate the system Node first:
  ```
  source ~/.nvm/nvm.sh && nvm use system
  ```

## Instructions

1. Identify the input file. It can be:
   - A Markdown file (`.md`) containing one or more ` ```mermaid ` code blocks.
   - A raw Mermaid file (`.mmd`).

2. Determine the output path. Default to a sibling file with the same stem
   and a `.png` extension. If the user specifies SVG, use `.svg`.

3. Run the render command, ensuring Node >= 22:
   ```bash
   source ~/.nvm/nvm.sh && nvm use system \
     && npx --yes @mermaid-js/mermaid-cli \
          -i <input-file> \
          -o <output-file> \
          -b transparent
   ```
   - For Markdown inputs with multiple diagrams, mmdc produces numbered
     outputs (e.g. `output-1.png`, `output-2.png`).
   - Add `-t dark` if the user requests a dark theme.
   - Add `-w <width>` to control width (default is auto).

4. After rendering, use the Read tool to display the resulting image to the
   user so they can verify it visually.

5. Report the output path and image dimensions if available.

## Verification

- The output file must exist and be non-empty.
- Display the rendered image inline for visual confirmation.
