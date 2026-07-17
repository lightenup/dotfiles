"""Central Microsoft product-icon library for draw.io embedding.

Base64-embeds curated official SVGs (see ../ms_icons/) into the .drawio so icons
render via the draw.io CLI without relying on its bundled shape libraries. Backed
by ms_icons/catalog.tsv (KEY  FILE  PACK  ALIASES).

    from puml_drawio import icons
    icons.load_catalog()                        # defaults to ../ms_icons/catalog.tsv
    icons.sprite_file("AzureLogicApps")         # -> "azure/logic_apps.svg"
    icons.datauri("azure/logic_apps.svg")       # -> "data:image/svg+xml,<base64>"
    icons.resolve(sprite="AzureLogicApps")      # -> embedded data URI (or "")
"""
from __future__ import annotations

import base64
from pathlib import Path

# Curated icon library, sibling package directory of puml_drawio.
ICON_DIR = Path(__file__).resolve().parent.parent / "ms_icons"
CATALOG = ICON_DIR / "catalog.tsv"

_alias_to_file: dict[str, str] | None = None
_datauri_cache: dict[str, str] = {}


def load_catalog(path: str | Path | None = None) -> dict[str, str]:
    """Parse catalog.tsv into an alias/key -> relative-file map."""
    global _alias_to_file
    p = Path(path) if path else CATALOG
    mapping: dict[str, str] = {}
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            key, rel = parts[0], parts[1]
            mapping[key] = rel
            if len(parts) >= 4:
                for alias in parts[3].split(","):
                    alias = alias.strip()
                    if alias:
                        mapping[alias] = rel
    _alias_to_file = mapping
    return mapping


def catalog() -> dict[str, str]:
    if _alias_to_file is None:
        load_catalog()
    return _alias_to_file  # type: ignore[return-value]


def sprite_file(name: str) -> str | None:
    """Return the catalog file for a sprite/alias/key, or None."""
    return catalog().get(name)


def datauri(rel_or_key: str) -> str:
    """Base64 SVG data URI for a catalog file (relative path or alias/key).

    Returns "" if the file is missing. The encoding matches the format proven to
    render through the draw.io CLI.
    """
    rel = catalog().get(rel_or_key, rel_or_key)
    if rel in _datauri_cache:
        return _datauri_cache[rel]
    uri = ""
    p = ICON_DIR / rel
    if p.exists():
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        uri = f"data:image/svg+xml,{b64}"
    _datauri_cache[rel] = uri
    return uri


def resolve(sprite: str | None = None, comp_id: str | None = None) -> str:
    """Embedded data URI for a component's id (first) or sprite, else ""."""
    for key in (comp_id, sprite):
        if key:
            rel = catalog().get(key)
            if rel:
                uri = datauri(rel)
                if uri:
                    return uri
    return ""
