#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the empty local runtime directory layout without creating state data."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIRS = (
    "core-overrides/state",
    "core-overrides/state/backup",
    "publish-interval-guard/state",
    "publish-loop-guard/state",
    "timeliness-window/state",
    "update-checker/state",
    "xhs-risk-guard/state",
)


def main() -> int:
    for relative in RUNTIME_DIRS:
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
    print(f"OK runtime directories ready ({len(RUNTIME_DIRS)} directories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
