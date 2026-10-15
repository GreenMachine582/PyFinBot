"""scripts/check_gth_pins.py: requirements.txt's greentechhub pins must agree
with the tags those packages' own runtime dependencies pin (offline: the pure
functions only)."""

import importlib.util
import sys
from pathlib import Path

# A script, not a package module: load it by path (registered first, as
# dataclasses need its module in sys.modules).
_SPEC = importlib.util.spec_from_file_location(
    "check_gth_pins", Path(__file__).resolve().parent.parent / "scripts" / "check_gth_pins.py")
check = importlib.util.module_from_spec(_SPEC)
sys.modules["check_gth_pins"] = check
_SPEC.loader.exec_module(check)

URL = "git+https://github.com/GreenMachine582/{repo}.git@{tag}"
REQUIREMENTS = f"""\
fastapi~=0.136.3
greentechhub-core[sqlalchemy,crypto,testing] @ {URL.format(repo="greentechhub-core", tag="v0.15.0")}
greentechhub-fastapi[testing] @ {URL.format(repo="greentechhub-fastapi", tag="v0.17.0")}  # a comment
greentechhub-ui @ {URL.format(repo="greentechhub-ui", tag="v0.19.0")}
"""
FASTAPI_PYPROJECT = f"""
[project]
name = "greentechhub-fastapi"
dependencies = [
    "fastapi>=0.110",
    "greentechhub-core @ {URL.format(repo="greentechhub-core", tag="{core}")}",
]
[project.optional-dependencies]
testing = ["greentechhub-core[testing] @ {URL.format(repo="greentechhub-core", tag="v0.1.0")}"]
"""
UI_PYPROJECT = """
[project]
name = "greentechhub-ui"
dependencies = ["jinja2>=3.1"]
[project.optional-dependencies]
dev = ["greentechhub-core @ git+https://github.com/GreenMachine582/greentechhub-core.git@v0.14.0"]
"""


def test_parse_pins_reads_the_gth_lines_with_extras_and_comments():
    pins = check.parse_pins(REQUIREMENTS)
    assert sorted(pins) == ["greentechhub-core", "greentechhub-fastapi", "greentechhub-ui"]
    assert pins["greentechhub-fastapi"].tag == "v0.17.0"
    assert (pins["greentechhub-core"].owner, pins["greentechhub-core"].repo) == (
        "GreenMachine582", "greentechhub-core")


def test_required_tags_reads_runtime_dependencies_only():
    assert check.required_tags(FASTAPI_PYPROJECT.replace("{core}", "v0.15.0")) == {
        "greentechhub-core": "v0.15.0"}
    assert check.required_tags(UI_PYPROJECT) == {}  # its dev extra doesn't count


def _requires(core_tag):
    return {"greentechhub-core": {},
            "greentechhub-fastapi": check.required_tags(FASTAPI_PYPROJECT.replace("{core}", core_tag)),
            "greentechhub-ui": check.required_tags(UI_PYPROJECT)}


def test_agreeing_pins_pass():
    assert check.mismatches(check.parse_pins(REQUIREMENTS), _requires("v0.15.0")) == []


def test_a_core_mismatch_names_the_fix():
    assert check.mismatches(check.parse_pins(REQUIREMENTS), _requires("v0.16.0")) == [
        "greentechhub-core is pinned at v0.15.0, but greentechhub-fastapi v0.17.0 needs v0.16.0: "
        "bump greentechhub-core to v0.16.0 in requirements.txt"]


def test_a_dependency_not_pinned_here_is_ignored():
    pins = check.parse_pins(REQUIREMENTS.replace("greentechhub-core[", "#greentechhub-core["))
    assert "greentechhub-core" not in pins
    assert check.mismatches(pins, {"greentechhub-fastapi": {"greentechhub-core": "v9.9.9"}}) == []
