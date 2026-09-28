"""Bootstrap for the Node-side draw.io -> Visio converter.

The converter lives in a private repo rather than in dotfiles, because dotfiles
is public and the converter vendors ~40 MB of draw.io stencils. So it is fetched
on first use, the way diagram-render-plantuml self-bootstraps the PlantUML JAR.

The install is pinned. A converter change can silently alter the appearance of
a client deliverable, so a bump has to be a deliberate edit here rather than
something that arrives on its own. Installs are keyed by the pin, so bumping
puts the new version alongside the old rather than mutating it in place.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO = "lightenup/lightenup-drawio-vsdx"

# A tag or a full commit SHA. Tags are nicer to read; a SHA is used when the
# tag has not been pushed. Both are fetched the same way below.
PINNED_REF = "635ef3f02885e5d515d4a682e2122fa95c66ad37"

DEFAULT_ROOT = Path.home() / ".local" / "share" / "drawio-vsdx"


class BootstrapError(RuntimeError):
    """Raised when the converter cannot be installed, with a fixable reason."""


def converter_home() -> Path:
    """Where the converter checkout lives.

    DRAWIO_VSDX_HOME overrides, for a manual checkout or a shared install.
    """
    override = os.environ.get("DRAWIO_VSDX_HOME")
    if override:
        return Path(override).expanduser()
    return DEFAULT_ROOT / PINNED_REF


def is_installed(home: Path | None = None) -> bool:
    home = home or converter_home()
    return (home / "src" / "cli.js").is_file() and (home / "node_modules").is_dir()


def _run(argv: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(
        argv, cwd=str(cwd) if cwd else None, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise BootstrapError(
            "command failed: " + " ".join(argv) + "\n" + (proc.stderr or proc.stdout or "")
        )


def install(home: Path | None = None) -> Path:
    """Clones the pinned converter and installs its dependencies.

    Uses `gh` so the private repo works with whatever auth is already set up,
    without this script handling tokens or SSH keys.
    """
    home = Path(home) if home is not None else converter_home()

    if shutil.which("gh") is None:
        raise BootstrapError(
            "the GitHub CLI (gh) is required to fetch the private converter repo.\n"
            "  install:       brew install gh\n"
            "  authenticate:  gh auth login\n"
            "  or point DRAWIO_VSDX_HOME at an existing checkout"
        )
    if shutil.which("npm") is None:
        raise BootstrapError("npm is required to install the converter's dependencies")

    home.parent.mkdir(parents=True, exist_ok=True)

    # --no-checkout then an explicit fetch of the pin: `--branch` only accepts a
    # branch or tag, and the pin may be a commit SHA.
    _run(["gh", "repo", "clone", REPO, str(home), "--", "--no-checkout"])
    _run(["git", "fetch", "--depth", "1", "origin", PINNED_REF], cwd=home)
    _run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=home)
    _run(["npm", "install", "--omit=dev", "--no-audit", "--no-fund"], cwd=home)

    return home


def ensure_installed(home: Path | None = None) -> Path:
    """Returns the converter home, installing it first if necessary."""
    home = Path(home) if home is not None else converter_home()
    if is_installed(home):
        return home
    return install(home)


def installed_ref(home: Path | None = None) -> str | None:
    """The commit actually checked out, for doctor to compare against the pin."""
    home = home or converter_home()
    if not (home / ".git").exists():
        return None
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(home), capture_output=True, text=True
    )
    return proc.stdout.strip() if proc.returncode == 0 else None
