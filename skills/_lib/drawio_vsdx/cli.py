"""drawiovsdx — command line interface.

Converts draw.io diagrams to Visio .vsdx, as the terminal step of the
diagramming pipeline: c4drawio turns PlantUML into .drawio, this turns .drawio
into something a client can open in Visio.

    drawiovsdx convert diagrams/drawio/arch.drawio
    drawiovsdx convert diagrams/drawio --all
    drawiovsdx doctor

Exit codes:
    0  converted with no fidelity loss
    1  error (bad input, missing toolchain, failed conversion)
    2  bad usage
    3  converted, but shapes or icons were lost

Exit 3 is the one that matters. draw.io renders an unresolvable shape as a
plain rectangle and drops an icon it cannot load, so a degraded conversion
opens cleanly in Visio and is quietly wrong. The wrapper never flattens that
into success.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import bootstrap

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_DEGRADED = 3

# Where draw.io Desktop keeps the webapp whose img/lib/ tree holds the bundled
# Azure and Microsoft icons. Matches the DRAWIO_APP path c4drawio renders with.
DRAWIO_IMAGE_ROOTS = [
    "/Applications/draw.io.app/Contents/Resources/app.asar",
    "/Applications/draw.io.app/Contents/Resources/app",
    "/opt/drawio/resources/app.asar",
]


def discover_image_roots() -> list[str]:
    """Image roots to hand the converter, in priority order.

    Without one, every bundled icon a diagram references silently disappears,
    so this is worth reporting in doctor rather than leaving implicit.
    """
    roots: list[str] = []
    env = os.environ.get("DRAWIO_IMAGE_ROOT")
    if env:
        roots.extend(p for p in env.split(os.pathsep) if p)
    roots.extend(DRAWIO_IMAGE_ROOTS)
    return [r for r in roots if Path(r).exists()]


def default_output(src: Path) -> Path:
    """diagrams/drawio/arch.drawio -> diagrams/vsdx/arch.vsdx

    Mirrors c4drawio's convert convention, and falls back to a `vsdx/` sibling
    when the source is not inside a diagrams/ tree.
    """
    src = Path(src)
    if src.parent.name == "drawio":
        return src.parent.parent / "vsdx" / (src.stem + ".vsdx")
    return src.parent / "vsdx" / (src.stem + ".vsdx")


def _node_version() -> str | None:
    if shutil.which("node") is None:
        return None
    proc = subprocess.run(["node", "--version"], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _run_converter(argv: list[str], home: Path | None = None) -> subprocess.CompletedProcess:
    """Invokes the Node CLI. Separated out so tests can stub the boundary."""
    home = home or bootstrap.converter_home()
    return subprocess.run(
        ["node", str(Path(home) / "src" / "cli.js"), *argv],
        capture_output=True,
        text=True,
    )


def _drawio_files(target: Path, recurse: bool) -> list[Path]:
    if target.is_dir():
        pattern = "**/*.drawio" if recurse else "*.drawio"
        return sorted(target.glob(pattern))
    return [target]


def cmd_convert(args) -> int:
    target = Path(args.input)
    if not target.exists():
        print(f"error: input not found: {target}", file=sys.stderr)
        return EXIT_ERROR

    sources = _drawio_files(target, args.all)
    if not sources:
        print(f"error: no .drawio files under {target}", file=sys.stderr)
        return EXIT_ERROR
    if len(sources) > 1 and args.output:
        print("error: -o cannot be combined with multiple inputs", file=sys.stderr)
        return EXIT_USAGE

    try:
        home = bootstrap.ensure_installed()
    except bootstrap.BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    image_roots = list(args.image_root or []) or discover_image_roots()

    worst = EXIT_OK
    reports = []

    for src in sources:
        out = Path(args.output) if args.output else default_output(src)
        out.parent.mkdir(parents=True, exist_ok=True)

        argv = [str(src), str(out), "--json"]
        if not args.strict:
            argv.append("--no-strict")
        if args.remote_images:
            argv.append("--remote-images")
        for root in image_roots:
            argv.extend(["--image-root", root])

        proc = _run_converter(argv, home=home)

        try:
            report = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError:
            report = {"ok": False, "error": (proc.stderr or proc.stdout).strip()}

        report["input"] = str(src)
        reports.append(report)

        if proc.returncode == EXIT_DEGRADED:
            worst = max(worst, EXIT_DEGRADED)
        elif proc.returncode != 0:
            worst = EXIT_ERROR

        if not args.json:
            if report.get("ok"):
                pages = len(report.get("pages") or [])
                print(f"wrote {out} ({pages} page(s), {report.get('bytes', 0)} bytes)")
                if report.get("degradation"):
                    print(f"  fidelity loss: {report['degradation']}", file=sys.stderr)
            else:
                print(
                    f"error: {src}: {report.get('error', 'conversion failed')}",
                    file=sys.stderr,
                )

    if args.json:
        print(json.dumps(reports[0] if len(reports) == 1 else reports, indent=2))

    return worst


def cmd_doctor(args) -> int:
    node = _node_version()
    home = bootstrap.converter_home()
    installed = bootstrap.is_installed(home)
    image_roots = discover_image_roots()

    checks = {
        "node": node,
        "gh": shutil.which("gh"),
        "npm": shutil.which("npm"),
        "converter": str(home) if installed else None,
        "pinned_ref": bootstrap.PINNED_REF,
        "installed_ref": bootstrap.installed_ref(home) if installed else None,
        "image_roots": image_roots,
    }
    # Conversion works without an image root; it just quietly loses every
    # bundled icon, so it is a warning rather than a hard requirement.
    ok = bool(node) and installed

    if args.json:
        print(json.dumps({**checks, "ok": ok}, indent=2))
        return EXIT_OK if ok else EXIT_ERROR

    for name in ("node", "gh", "npm", "converter"):
        found = checks[name]
        mark = "ok " if found else "MISSING"
        print(f"  [{mark}] {name:<14} {found or ''}")

    roots = checks["image_roots"]
    mark = "ok " if roots else "WARN   "
    print(f"  [{mark}] image root     {roots[0] if roots else ''}")
    print()

    if not node:
        print("  node: install Node 18+ (brew install node)")
    if not checks["gh"]:
        print("  gh: needed to fetch the private converter repo (brew install gh)")
    if not installed:
        print(f"  converter: not installed; it bootstraps on first convert into {home}")
    if not roots:
        print("  image root: no draw.io webapp found. Bundled Azure/Microsoft icons")
        print("              will be dropped from every conversion. Install draw.io")
        print("              Desktop, or set DRAWIO_IMAGE_ROOT.")

    installed_ref = checks["installed_ref"]
    if installed and installed_ref and not installed_ref.startswith(bootstrap.PINNED_REF[:12]):
        print(f"  converter: checked out {installed_ref[:12]}, pinned {bootstrap.PINNED_REF[:12]}")

    return EXIT_OK if ok else EXIT_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawiovsdx",
        description="Convert draw.io diagrams to Visio .vsdx. Strict by default: "
        "a conversion that loses shapes or icons exits 3 rather than pretending "
        "to have succeeded.",
    )
    sub = parser.add_subparsers(dest="command")

    conv = sub.add_parser("convert", help="convert a .drawio file or directory")
    conv.add_argument("input", help="a .drawio file, or a directory of them")
    conv.add_argument("-o", "--output", help="output path (single input only)")
    conv.add_argument("--all", action="store_true", help="recurse into subdirectories")
    conv.add_argument(
        "--no-strict", dest="strict", action="store_false",
        help="accept fidelity loss and exit 0",
    )
    conv.add_argument(
        "--remote-images", action="store_true",
        help="allow the converter to fetch http(s) images",
    )
    conv.add_argument(
        "--image-root", action="append",
        help="where to resolve draw.io-internal icon paths (repeatable)",
    )
    conv.add_argument("--json", action="store_true", help="machine-readable report")
    conv.set_defaults(func=cmd_convert, strict=True)

    doc = sub.add_parser("doctor", help="check the toolchain")
    doc.add_argument("--json", action="store_true")
    doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not getattr(args, "command", None):
        parser.print_help()
        print("\ntry: drawiovsdx convert diagrams/drawio/arch.drawio")
        return EXIT_USAGE
    return args.func(args)
