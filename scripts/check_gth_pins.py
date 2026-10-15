"""Check that requirements.txt's greentechhub pins agree with each other.

PyFinBot pins greentechhub-core itself (it imports core directly and needs
its [sqlalchemy,crypto,testing] extras), and greentechhub-fastapi pins core
too. Two different git tags of one package can't both be installed, so pip
refuses with an opaque ResolutionImpossible. This says which pin to bump.

For each pinned greentechhub package, it reads that repo's pyproject.toml at
the pinned tag and compares the greentechhub packages in its runtime
`dependencies` (not its dev/test extras) with the tags pinned here.

    python scripts/check_gth_pins.py            # exit 1 on a mismatch

Stdlib only, so CI runs it before installing anything.
"""

from __future__ import annotations

import re
import sys
import tomllib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"
RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/{tag}/pyproject.toml"

_GTH_PIN = re.compile(
    r"^\s*(?P<package>greentechhub-[a-z]+)(?:\[[^\]]*\])?\s*@\s*"
    r"git\+https://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/@\s]+?)(?:\.git)?@(?P<tag>[^\s#]+)"
)


@dataclass(frozen=True)
class Pin:
    package: str
    owner: str
    repo: str
    tag: str


def parse_pins(text: str) -> dict[str, Pin]:
    """The greentechhub-* git pins in requirements-style `text`, by package."""
    pins = {}
    for line in text.splitlines():
        match = _GTH_PIN.match(line.split("#", 1)[0])
        if match:
            pins[match["package"]] = Pin(**match.groupdict())
    return pins


def required_tags(pyproject_text: str) -> dict[str, str]:
    """The greentechhub-* packages a pyproject's runtime dependencies pin, with their tags."""
    dependencies = tomllib.loads(pyproject_text).get("project", {}).get("dependencies", [])
    return {pin.package: pin.tag for pin in parse_pins("\n".join(dependencies)).values()}


def mismatches(pins: dict[str, Pin], requires: dict[str, dict[str, str]]) -> list[str]:
    """One message per disagreement. `requires` maps a pinned package to what its own
    dependencies pin (required_tags); a package that isn't pinned here is ignored."""
    problems = []
    for package, needed in sorted(requires.items()):
        for dependency, tag in sorted(needed.items()):
            ours = pins.get(dependency)
            if ours is not None and ours.tag != tag:
                problems.append(
                    f"{dependency} is pinned at {ours.tag}, but {package} {pins[package].tag} needs "
                    f"{tag}: bump {dependency} to {tag} in requirements.txt"
                )
    return problems


def _fetch(pin: Pin) -> str:
    url = RAW_URL.format(owner=pin.owner, repo=pin.repo, tag=pin.tag)
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https host
        return response.read().decode("utf-8")


def main() -> int:
    pins = parse_pins(REQUIREMENTS.read_text(encoding="utf-8"))
    requires = {package: required_tags(_fetch(pin)) for package, pin in pins.items()}
    problems = mismatches(pins, requires)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if not problems:
        print("gth pins agree: " + ", ".join(f"{p} {pin.tag}" for p, pin in sorted(pins.items())))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
