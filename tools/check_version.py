"""Check the package version in pyproject.toml.

Usage:
    python tools/check_version.py
    python tools/check_version.py v0.5.1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^version = "([^"]+)"$', flags=re.MULTILINE)


def read_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if not match:
        raise SystemExit("Could not find project version in pyproject.toml")
    return match.group(1)


def main() -> None:
    version = read_version()
    if len(sys.argv) == 1:
        print(version)
        return

    expected_tag = f"v{version}"
    actual_tag = sys.argv[1]
    if actual_tag != expected_tag:
        raise SystemExit(
            f"Tag {actual_tag!r} does not match pyproject version {version!r}; "
            f"expected {expected_tag!r}"
        )
    print(f"Version check passed: {actual_tag}")


if __name__ == "__main__":
    main()
