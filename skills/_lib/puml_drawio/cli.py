"""c4drawio — command line interface.

Turns C4 PlantUML into laid-out, routed draw.io diagrams, renders them, and
scores the result. Every operation is a subcommand; nothing needs a Python
one-liner.

    c4drawio build   diagrams/plantuml/arch.puml     # convert + render + score
    c4drawio convert diagrams/plantuml/arch.puml
    c4drawio render  diagrams/drawio/arch.drawio
    c4drawio score   diagrams/drawio --max-crossings 0
    c4drawio doctor

Exit codes:
    0  success
    1  error (bad input, missing toolchain, failed render)
    2  quality gate failed (used by `score --max-crossings`)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import elk_layout
from .drawio_generator import generate, load_icon_map
from .metrics import Metrics, measure, measure_file
from .puml_parser import parse_file

DRAWIO_APP = "/Applications/draw.io.app/Contents/MacOS/draw.io"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_QUALITY = 2


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _default_output(src: Path) -> Path:
    """diagrams/plantuml/x.puml -> diagrams/drawio/x.drawio.

    Falls back to a `drawio/` sibling directory when the source is not in a
    `plantuml/` directory.
    """
    if src.parent.name == "plantuml":
        return src.parent.parent / "drawio" / (src.stem + ".drawio")
    return src.parent / "drawio" / (src.stem + ".drawio")


def _find_icons(src: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    for cand in (
        _default_output(src).parent / "icons.json",
        src.parent / "icons.json",
    ):
        if cand.is_file():
            return cand
    return None


def _drawio_files(targets: list[str]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            out.extend(sorted(p.glob("*.drawio")))
        elif p.is_file():
            out.append(p)
    return out


def _metrics_row(path: Path, m: Metrics) -> dict:
    return {
        "file": str(path),
        "nodes": m.node_count,
        "edges": m.edge_count,
        "edge_node_crossings": m.edge_node_crossings,
        "edge_edge_crossings": m.edge_edge_crossings,
        "label_overlap_area": round(m.label_overlap_area, 1),
        "node_overlap_area": round(m.node_overlap_area, 1),
        "width": round(m.width, 1),
        "height": round(m.height, 1),
        "aspect_ratio": round(m.aspect_ratio, 2),
    }


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def cmd_convert(args) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"error: input not found: {src}", file=sys.stderr)
        return EXIT_ERROR

    out = Path(args.output) if args.output else _default_output(src)
    if out.exists() and not args.force:
        print(f"skip: {out} already exists (pass --force to overwrite)")
        return EXIT_OK

    icons = _find_icons(src, args.icons)
    if icons:
        load_icon_map(icons)

    overrides = (
        json.loads(Path(args.overrides).read_text(encoding="utf-8"))
        if args.overrides
        else elk_layout.load_overrides(src)
    )

    try:
        xml = generate(parse_file(src), overrides=overrides)
    except Exception as e:                                    # noqa: BLE001
        print(f"error: conversion failed: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_ERROR

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")

    note = ""
    if overrides:
        note = (f"  (+{len(overrides.get('nodes', {}))} node / "
                f"{len(overrides.get('edges', {}))} edge overrides)")
    print(f"wrote {out}{note}")
    print(f"  {measure(xml).summary()}")
    return EXIT_OK


def cmd_render(args) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"error: input not found: {src}", file=sys.stderr)
        return EXIT_ERROR
    if not Path(DRAWIO_APP).exists():
        print(f"error: draw.io desktop not found at {DRAWIO_APP}\n"
              "       install from https://github.com/jgraph/drawio-desktop/releases",
              file=sys.stderr)
        return EXIT_ERROR

    out = Path(args.output) if args.output else src.with_suffix("." + args.format)

    def _run(scale: int):
        return subprocess.run(
            [DRAWIO_APP, "-x", "-f", args.format, "-s", str(scale),
             "-o", str(out), str(src)],
            capture_output=True, text=True,
        )

    proc = _run(args.scale)
    # Very large canvases blow the rasteriser's texture limit; halving the
    # scale is the standard escape and beats failing outright.
    if proc.returncode != 0 and "texture" in (proc.stdout + proc.stderr).lower():
        print(f"note: texture limit hit at scale {args.scale}, retrying at 1")
        proc = _run(1)

    if proc.returncode != 0 or not out.exists():
        print(f"error: render failed\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        return EXIT_ERROR

    print(f"wrote {out}")
    return EXIT_OK


def cmd_score(args) -> int:
    rows: list[dict] = []
    for t in args.targets:
        p = Path(t)
        if p.is_file() and p.suffix == ".puml":
            # Score a source without committing to an output file.
            icons = _find_icons(p, None)
            if icons:
                load_icon_map(icons)
            m = measure(generate(parse_file(p), overrides=elk_layout.load_overrides(p)))
            rows.append(_metrics_row(p, m))
            continue
        for f in _drawio_files([t]):
            rows.append(_metrics_row(f, measure_file(f)))

    if not rows:
        print("error: nothing to score", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max(len(Path(r["file"]).name) for r in rows)
        for r in rows:
            print(
                f"{Path(r['file']).name:<{width}}  "
                f"{r['nodes']:>3} nodes {r['edges']:>3} edges | "
                f"edge-node crossings: {r['edge_node_crossings']:>3} | "
                f"edge-edge: {r['edge_edge_crossings']:>3} | "
                f"label overlap: {r['label_overlap_area']:>7.0f}px2 | "
                f"ar {r['aspect_ratio']:.2f}"
            )

    if args.max_crossings is not None:
        bad = [r for r in rows if r["edge_node_crossings"] > args.max_crossings]
        if bad:
            print(
                f"\nQUALITY GATE FAILED: {len(bad)} diagram(s) exceed "
                f"--max-crossings {args.max_crossings}",
                file=sys.stderr,
            )
            for r in bad:
                print(f"  {Path(r['file']).name}: {r['edge_node_crossings']}",
                      file=sys.stderr)
            return EXIT_QUALITY
    return EXIT_OK


def cmd_build(args) -> int:
    """convert -> render -> score, the everyday command."""
    conv = argparse.Namespace(
        input=args.input, output=None, force=args.force,
        icons=args.icons, overrides=None,
    )
    rc = cmd_convert(conv)
    if rc != EXIT_OK:
        return rc

    drawio = _default_output(Path(args.input))
    if not drawio.is_file():
        return EXIT_OK      # skipped an existing file; nothing new to render

    rend = argparse.Namespace(
        input=str(drawio), output=None, format=args.format, scale=args.scale,
    )
    rc = cmd_render(rend)
    if rc != EXIT_OK:
        return rc

    if args.max_crossings is not None:
        return cmd_score(argparse.Namespace(
            targets=[str(drawio)], json=False, max_crossings=args.max_crossings,
        ))
    return EXIT_OK


def cmd_doctor(args) -> int:
    jar = elk_layout.plantuml_jar()
    checks = {
        "java": shutil.which("java"),
        "javac": shutil.which("javac"),
        "plantuml.jar": str(jar) if jar else None,
        "draw.io": DRAWIO_APP if Path(DRAWIO_APP).exists() else None,
    }
    required = ("java", "javac", "plantuml.jar")
    ok = all(checks[k] for k in required)

    if args.json:
        print(json.dumps({**{k: v or "" for k, v in checks.items()}, "ok": ok}, indent=2))
        return EXIT_OK if ok else EXIT_ERROR

    for name, found in checks.items():
        mark = "ok " if found else "MISSING"
        print(f"  [{mark}] {name:<14} {found or ''}")
    print()
    if not checks["java"] or not checks["javac"]:
        print("  java/javac: install a JDK (brew install openjdk)")
    if not checks["plantuml.jar"]:
        print("  plantuml.jar: expected at ~/.local/share/plantuml/plantuml.jar")
        print("                or set PLANTUML_JAR. ELK layout lives inside it.")
    if not checks["draw.io"]:
        print("  draw.io: only needed for `render`; convert and score work without it.")
        print("           https://github.com/jgraph/drawio-desktop/releases")
    print("layout engine:", "ready" if elk_layout.available() else "UNAVAILABLE")
    return EXIT_OK if ok else EXIT_ERROR


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="c4drawio",
        description="C4 PlantUML -> laid-out, routed draw.io diagrams.",
        epilog="Layout and orthogonal edge routing come from ELK "
               "(bundled in plantuml.jar). Run `c4drawio doctor` to check the toolchain.",
    )
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("convert", help="PlantUML -> .drawio (does not render)")
    c.add_argument("input", help="path to a .puml file")
    c.add_argument("-o", "--output", help="output .drawio (default: ../drawio/<name>.drawio)")
    c.add_argument("-f", "--force", action="store_true",
                   help="overwrite an existing .drawio")
    c.add_argument("--icons", help="icon map JSON (default: drawio/icons.json if present)")
    c.add_argument("--overrides", help="overrides JSON (default: <name>.overrides.json)")
    c.set_defaults(func=cmd_convert)

    r = sub.add_parser("render", help=".drawio -> PNG/SVG/PDF via draw.io desktop")
    r.add_argument("input", help="path to a .drawio file")
    r.add_argument("-o", "--output", help="output image (default: alongside input)")
    r.add_argument("--format", default="png", choices=["png", "svg", "pdf"])
    r.add_argument("--scale", type=int, default=2, help="raster scale (default 2)")
    r.set_defaults(func=cmd_render)

    s = sub.add_parser("score", help="measure layout quality (crossings, overlaps)")
    s.add_argument("targets", nargs="+",
                   help=".drawio files, directories, or a .puml to score in memory")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.add_argument("--max-crossings", type=int, metavar="N",
                   help="exit 2 if any diagram exceeds N edge-node crossings")
    s.set_defaults(func=cmd_score)

    b = sub.add_parser("build", help="convert + render + score in one step")
    b.add_argument("input", help="path to a .puml file")
    b.add_argument("-f", "--force", action="store_true")
    b.add_argument("--icons")
    b.add_argument("--format", default="png", choices=["png", "svg", "pdf"])
    b.add_argument("--scale", type=int, default=2)
    b.add_argument("--max-crossings", type=int, metavar="N")
    b.set_defaults(func=cmd_build)

    d = sub.add_parser("doctor", help="check the toolchain")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not getattr(args, "command", None):
        parser.print_usage()
        print("\nsubcommands: convert, render, score, build, doctor")
        print("try: c4drawio build diagrams/plantuml/arch.puml")
        return EXIT_ERROR
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
