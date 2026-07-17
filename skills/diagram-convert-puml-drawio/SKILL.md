---
name: diagram-convert-puml-drawio
description: >-
  Convert PlantUML C4 diagrams to draw.io XML format with automatic layout.
  Use when the user wants to convert a .puml file to .drawio for hand-polishing
  in the draw.io desktop app. Supports boundaries, tags, icons, and layout hints.
---

# Convert PlantUML C4 to draw.io

Convert PlantUML C4 architecture diagrams into draw.io XML format with
automatic layout, ready for hand-polishing in the draw.io desktop app.

## Project Convention

- PlantUML sources: `diagrams/plantuml/*.puml`
- draw.io output: `diagrams/drawio/*.drawio` (beside or in drawio subfolder)
- Icon map (optional): `diagrams/drawio/icons.json`

Create directories if they do not exist.

## Prerequisites

- Python 3.12+
- The shared library at `~/.factory/skills/_lib/puml_drawio/` (installed via dotfiles)

## Conversion Instructions

1. Locate the `.puml` input file.

2. Determine the output path. Default: same stem with `.drawio` extension,
   placed in `diagrams/drawio/`. If the output file already exists, **skip it**
   to protect manual edits (unless the user explicitly asks to overwrite).

3. Optionally load a project-specific icon map. If `diagrams/drawio/icons.json`
   exists, load it before generating.

4. Run the conversion:
   ```python
   import sys
   sys.path.insert(0, str(__import__('pathlib').Path.home() / '.factory/skills/_lib'))

   from puml_drawio import parse, generate, load_icon_map
   from pathlib import Path

   # Optional: load project icon map
   icons_path = Path('diagrams/drawio/icons.json')
   if icons_path.exists():
       load_icon_map(icons_path)

   puml_path = Path('<input-file>')
   out_path = Path('diagrams/drawio') / puml_path.with_suffix('.drawio').name

   # Skip existing files to protect manual edits
   if out_path.exists():
       print(f'SKIP: {out_path} exists (use --force to overwrite)')
   else:
       text = puml_path.read_text(encoding='utf-8')
       diagram = parse(text)
       xml = generate(diagram)
       out_path.parent.mkdir(parents=True, exist_ok=True)
       out_path.write_text(xml, encoding='utf-8')
       print(f'Created: {out_path}')
   ```

5. If the user wants to overwrite, remove the existence check.

## Central MS icon library (embedded official SVGs)

For Microsoft/Azure architecture diagrams, the converter ships a curated library
of **official Microsoft product SVGs** at `~/.factory/skills/_lib/ms_icons/`
(`azure/`, `dynamics/`, `entra/` + `catalog.tsv` + `LICENSES/`). When a PlantUML
`$sprite` (or a component id) matches an alias in `catalog.tsv`, the generator
**base64-embeds** that SVG into the `.drawio`, so it renders reliably via the
draw.io CLI (no dependence on the bundled `azure2` shapes, which are incomplete).

```python
from puml_drawio import icons
icons.load_catalog()                     # defaults to ms_icons/catalog.tsv
icons.sprite_file("AzureLogicApps")      # -> "azure/logic_apps.svg"
icons.datauri("azure/logic_apps.svg")    # -> "data:image/svg+xml,<base64>"
```

Add an icon: drop the SVG in the right category folder (stable snake_case name),
add a row to `catalog.tsv` (`KEY  FILE  PACK  ALIASES`), reference it via
`$sprite=<Alias>`. Keep the Microsoft Terms of Use in `LICENSES/` with the icons.
This central library takes priority; the `icons.json` sidecar below still works
for project-specific overrides and non-MS shapes.

## Icon Map

The converter uses a JSON sidecar file to map PlantUML sprite names to
draw.io image library paths. Create `diagrams/drawio/icons.json`:

```json
{
  "AzureAPIManagement": "img/lib/azure2/integration/API_Management_Services.svg",
  "AzureKubernetesService": "img/lib/azure2/containers/Kubernetes_Services.svg",
  "apachekafka_original": "img/lib/mscae/Event_Hub.svg"
}
```

Without an icon map, components use generic fallback icons based on their
type (System, Container, Person, System_Ext).

## Supported PlantUML Features

- **Components**: `Person`, `System`, `System_Ext`, `Container`
- **Boundaries**: `System_Boundary` with nesting
- **Relationships**: `Rel`, `Rel_D`, `Rel_R`, `Rel_L`, `Rel_U`, freeform arrows
- **Layout hints**: `Lay_R`, `Lay_D`, `Lay_L`, `Lay_U`
- **Tags**: `AddElementTag` with `$bgColor`, `$fontColor`, `$legendText`
- **Sprites**: `$sprite` parameter mapped via icons.json
- **Titles**: Rendered as header text in draw.io

## Layout Engine

The converter includes a layout engine that:
- Assigns rows based on `Lay_D` hints and relationship direction
- Orders columns based on `Lay_R` hints and barycenter optimization
- Centers rows within boundaries
- Normalizes row heights for visual balance
- Detects satellite components and places them beside their target boundary
- Spreads edge ports for high-fanin/fanout nodes to reduce overlapping

## Workflow

1. Author diagram in PlantUML (`.puml`)
2. Convert to draw.io with this skill
3. Open `.drawio` in draw.io desktop app for visual polish
4. Render to PNG with the `diagram-render-drawio` skill
