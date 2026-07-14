"""Update the package version in pyproject.toml.

Usage:
    python tools/bump_version.py 0.5.1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^version = "([^"]+)"$', flags=re.MULTILINE)
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?$")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tools/bump_version.py 0.5.1")

    new_version = sys.argv[1]
    if not SEMVER_PATTERN.fullmatch(new_version):
        raise SystemExit("Version must look like 0.5.1")

    text = PYPROJECT.read_text(encoding="utf-8")
    updated, count = VERSION_PATTERN.subn(f'version = "{new_version}"', text, count=1)
    if count != 1:
        raise SystemExit("Could not find exactly one project version in pyproject.toml")

    PYPROJECT.write_text(updated, encoding="utf-8")
    print(f"Updated pyproject.toml version to {new_version}")


if __name__ == "__main__":
    main()
