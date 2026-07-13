#!/usr/bin/env python3
"""Reusable mono line-icon library for draw.io.

Icons are emitted as inline (URL-encoded) SVG image shapes so they render
reliably via the draw.io desktop CLI. The bundled CLI does NOT ship
`mxgraph.basic.*` (gear/chart/shield/bulb) or most `mxgraph.ios7.icons.*` —
those export blank. Inline SVG avoids that and gives a consistent, tintable set.

Usage:
    from icons import ICONS, datauri
    style = f"shape=image;imageAspect=0;image={datauri('cloud', '#FFE600')};html=1;"

Preview / QA (writes an icon sheet you can render with diagram-render-drawio):
    python3 icons.py            # -> _icon-probe.drawio

Add an icon: append a 24x24, stroke-only SVG fragment to ICONS, then re-run the
probe. Keep fill="none"; stroke and width are applied by datauri().
"""
from urllib.parse import quote

ICONS = {
    "chart":   '<line x1="4" y1="20" x2="20" y2="20"/><line x1="4" y1="20" x2="4" y2="4"/><rect x="7" y="12" width="3" height="8"/><rect x="12" y="7" width="3" height="13"/><rect x="17" y="14" width="3" height="6"/>',
    "ai":      '<circle cx="12" cy="12" r="3"/><circle cx="5" cy="5" r="1.6"/><circle cx="19" cy="5" r="1.6"/><circle cx="12" cy="21" r="1.6"/><line x1="6.2" y1="6.2" x2="9.8" y2="9.8"/><line x1="17.8" y1="6.2" x2="14.2" y2="9.8"/><line x1="12" y1="15" x2="12" y2="19.4"/>',
    "workflow":'<rect x="3" y="9" width="6" height="6" rx="1"/><rect x="15" y="9" width="6" height="6" rx="1"/><line x1="9" y1="12" x2="14" y2="12"/><polyline points="12.5,10.5 15,12 12.5,13.5"/>',
    "apps":    '<rect x="4" y="4" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1"/>',
    "partner": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19.5c0-3.3 2.5-5.6 5.5-5.6s5.5 2.3 5.5 5.6"/><circle cx="18" cy="9" r="2.3"/><path d="M16.2 19.5c0-2.6 1.5-4.4 3.8-4.4 1 0 1.9.3 2.5.9"/>',
    "integration":'<circle cx="7" cy="7" r="3"/><circle cx="17" cy="17" r="3"/><line x1="9.2" y1="9.2" x2="14.8" y2="14.8"/>',
    "orchestration":'<circle cx="6" cy="12" r="2.3"/><circle cx="18" cy="6" r="2.3"/><circle cx="18" cy="18" r="2.3"/><path d="M8.2 11C12 9.2 13 7.4 15.8 6.6"/><path d="M8.2 13C12 14.8 13 16.6 15.8 17.4"/>',
    "data":    '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    "identity":'<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "platform":'<path d="M12 3 L21 8 L12 13 L3 8 Z"/><polyline points="3,12 12,17 21,12"/><polyline points="3,16 12,21 21,16"/>',
    "erp":     '<path d="M12 3 L20 7 V16 L12 21 L4 16 V7 Z"/><polyline points="4,7 12,11 20,7"/><line x1="12" y1="11" x2="12" y2="21"/>',
    "plm":     '<polygon points="12,3 19,7.5 19,16.5 12,21 5,16.5 5,7.5"/><circle cx="12" cy="12" r="3"/>',
    "mes":     '<path d="M4 16a8 8 0 0 1 16 0"/><line x1="12" y1="16" x2="16" y2="10.5"/><circle cx="12" cy="16" r="1.3"/>',
    "ot":      '<rect x="7.5" y="7.5" width="9" height="9" rx="1"/><rect x="10.5" y="10.5" width="3" height="3"/><path d="M10 7.5V4M14 7.5V4M10 20v-3.5M14 20v-3.5M7.5 10H4M7.5 14H4M20 10h-3.5M20 14h-3.5"/>',
    "legacy":  '<circle cx="12" cy="12" r="8"/><polyline points="12,7.5 12,12 15.5,14"/>',
    "cloud":   '<path d="M7 18.5A4.5 4.5 0 0 1 7.2 9.6 A5.5 5.5 0 0 1 17.6 9 A4 4 0 0 1 17 18.5 Z"/>',
    "hybrid":  '<path d="M6.2 11.5A3.5 3.5 0 0 1 6.6 4.6 A4.6 4.6 0 0 1 15.4 4.2 A3.2 3.2 0 0 1 15.2 11.5 Z"/><rect x="5" y="15" width="14" height="5" rx="1"/><line x1="8" y1="17.5" x2="8.01" y2="17.5"/>',
    "onprem":  '<rect x="4" y="5" width="16" height="5.5" rx="1"/><rect x="4" y="13" width="16" height="5.5" rx="1"/><line x1="7" y1="7.75" x2="7.01" y2="7.75"/><line x1="7" y1="15.75" x2="7.01" y2="15.75"/>',
    "hub":     '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="4" r="1.7"/><circle cx="12" cy="20" r="1.7"/><circle cx="4" cy="12" r="1.7"/><circle cx="20" cy="12" r="1.7"/><line x1="12" y1="9" x2="12" y2="5.7"/><line x1="12" y1="15" x2="12" y2="18.3"/><line x1="9" y1="12" x2="5.7" y2="12"/><line x1="15" y1="12" x2="18.3" y2="12"/>',
    "trust":   '<path d="M12 3 L19 6 V11 C19 16 16 19 12 21 C8 19 5 16 5 11 V6 Z"/><polyline points="9,12 11,14 15,9"/>',
    "innovation":'<path d="M9.5 17.5h5M10.5 20.5h3"/><path d="M12 3a6 6 0 0 1 3.8 10.6c-.7.6-1.1 1.3-1.2 2.4H9.4c-.1-1.1-.5-1.8-1.2-2.4A6 6 0 0 1 12 3Z"/>',
}


def datauri(name, color="#FFE600", sw=2.0):
    """Return an inline (URL-encoded) SVG data URI for `name`, tinted `color`."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round">{ICONS[name]}</svg>')
    return "data:image/svg+xml," + quote(svg, safe="")


def emit_probe(path="_icon-probe.drawio", color="#FFE600"):
    """Write a dark icon sheet (labelled grid) for visual QA."""
    names = list(ICONS)
    cols, size, sx, sy, x0, y0 = 6, 70, 150, 130, 40, 50
    W = x0 + cols * sx
    H = y0 + ((len(names) + cols - 1) // cols) * sy + 40
    cells = [f'<mxCell id="bg" value="" style="rounded=0;html=1;fillColor=#1A1A24;strokeColor=none;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="{W}" height="{H}" as="geometry"/></mxCell>']
    for i, n in enumerate(names):
        r, c = divmod(i, cols)
        cells.append(f'<mxCell id="ic{i}" value="{n}" style="shape=image;imageAspect=0;image={datauri(n, color)};verticalLabelPosition=bottom;verticalAlign=top;fontColor=#FFFFFF;fontSize=9;html=1;" vertex="1" parent="1"><mxGeometry x="{x0 + c * sx}" y="{y0 + r * sy}" width="{size}" height="{size}" as="geometry"/></mxCell>')
    xml = (f'<mxfile host="app.diagrams.net"><diagram id="p" name="icons"><mxGraphModel dx="{W}" dy="{H}" grid="0" page="1" pageWidth="{W}" pageHeight="{H}"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
           + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
    open(path, "w").write(xml)
    print("wrote", path, f"({len(names)} icons)")


if __name__ == "__main__":
    emit_probe()
