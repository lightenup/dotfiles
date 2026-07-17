# Central Microsoft product-icon library

Curated, renamed subset of the official Microsoft icon packs, shared across
projects via the `puml_drawio` converter lib and the `diagram-convert-puml-drawio`
skill. Icons are base64-embedded into the `.drawio` so they render through the
draw.io CLI without relying on its bundled shape libraries.

## Layout
- `azure/`, `dynamics/`, `entra/` - curated SVGs, stable snake_case names.
- `catalog.tsv` - the map: `KEY  FILE  PACK  ALIASES`. Sprite/component-id names
  (aliases) resolve to a file here.
- `LICENSES/` - Microsoft Terms of Use / FAQ. **Keep these with the icons.**

## Use from the converter
```python
import sys
sys.path.insert(0, str(__import__('pathlib').Path.home() / '.factory/skills/_lib'))
from puml_drawio import icons
icons.load_catalog()                 # defaults to this catalog.tsv
uri = icons.datauri('azure/logic_apps.svg')   # base64 data URI for a style
rel = icons.sprite_file('AzureLogicApps')     # alias -> 'azure/logic_apps.svg'
```
The `puml_drawio` generator consults this catalog automatically: a PlantUML
`$sprite=AzureLogicApps` (or a matching component id) embeds the official SVG.

## Add an icon (grow on demand)
1. Copy the SVG from the source pack into `azure/`|`dynamics/`|`entra/`, renamed
   to a stable snake_case name.
2. Add a row to `catalog.tsv` with its KEY, FILE, PACK and the sprite/id ALIASES.
3. Reference it from PlantUML via `$sprite=<Alias>`.

## Licensing
Microsoft grants use of these icons in architecture diagrams under the terms in
`LICENSES/`. Do not modify the icon artwork, and do not use them to imply a
partnership beyond fact. The full raw packs (and an AWS pack, excluded here) live
outside git; only this curated subset is version-controlled.
