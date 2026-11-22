"""
Refresh public report data for GitHub Pages.

NOTE: docs/index.html / share/index.html are the source of truth for UI.
This script no longer regenerates HTML (that was overwriting the polished site).
It rebuilds performance.json used by the live markets report.
"""

from __future__ import annotations

from build_performance_json import main as build_performance


def main() -> None:
    build_performance()
    print(
        "UI HTML not regenerated (by design). "
        "Edit docs/index.html directly; this command only refreshes performance.json."
    )


if __name__ == "__main__":
    main()
