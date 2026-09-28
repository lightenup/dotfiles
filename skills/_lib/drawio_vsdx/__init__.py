"""draw.io -> Visio (.vsdx) conversion for the diagramming pipeline.

Wraps the Node converter (a rescued build of draw.io's own VSDX exporter) so
the rest of the pipeline can stay Python. See bootstrap.py for why the
converter is fetched rather than vendored.
"""

from . import bootstrap, cli  # noqa: F401

__all__ = ["bootstrap", "cli"]
