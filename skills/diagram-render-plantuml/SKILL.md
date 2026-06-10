---
name: diagram-render-plantuml
description: >-
  Render PlantUML diagrams to PNG/SVG images. Use when the user wants to
  preview, export, or verify a PlantUML diagram (.puml file). Self-bootstraps
  the PlantUML JAR on first use. Requires Java and Graphviz.
---

# Render PlantUML Diagrams

Render PlantUML diagrams to image files using the PlantUML JAR and Graphviz.

## Project Convention

PlantUML source files live in `diagrams/plantuml/` at the project root.
Create the directory if it does not exist. Rendered output goes beside
the source file (e.g. `diagrams/plantuml/arch.puml` -> `diagrams/plantuml/arch.png`).

## Prerequisites

- **Java**: JDK or JRE must be on PATH (`java -version`).
- **Graphviz**: The `dot` command must be available (`brew install graphviz` on macOS).
- **PlantUML JAR**: Auto-downloaded to `~/.local/share/plantuml/plantuml.jar` on first use.

## Bootstrap (first-time setup)

If `~/.local/share/plantuml/plantuml.jar` does not exist, download it:

```bash
mkdir -p ~/.local/share/plantuml
curl -fSL -o ~/.local/share/plantuml/plantuml.jar \
  "https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar"
```

Verify prerequisites:
```bash
java -version
dot -V
```

## Render Instructions

1. Locate the `.puml` input file.

2. Determine the output path: sibling file with `.png` extension by default.
   Use `.svg` if the user requests SVG output.

3. Run the render command:
   ```bash
   PLANTUML_JAR="${HOME}/.local/share/plantuml/plantuml.jar"
   TMPDIR="$(mktemp -d)"
   java -DPLANTUML_LIMIT_SIZE=16384 \
     -jar "$PLANTUML_JAR" \
     -Sdpi=200 \
     -tpng \
     -o "$TMPDIR" \
     "<input-file>"
   # PlantUML names output after the diagram title, not the filename.
   # Find the generated file and move it to the desired output path.
   mv "$TMPDIR"/*.png "<output-file>"
   rm -rf "$TMPDIR"
   ```

   For SVG output, replace `-tpng` with `-tsvg`.

4. After rendering, use the Read tool to display the resulting image to the
   user so they can verify it visually.

5. Report the output path.

## Troubleshooting

- **"dot not found"**: Install Graphviz: `brew install graphviz`
- **"java not found"**: Install Java via SDKMAN, Homebrew, or your package manager.
- **Diagram too large**: The `-DPLANTUML_LIMIT_SIZE=16384` flag allows up to 16384px.
  Increase if needed.

## Verification

- The output file must exist and be non-empty.
- Display the rendered image inline for visual confirmation.
