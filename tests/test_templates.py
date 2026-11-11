"""Tests templates/: the commented jobs file stays valid and the README stays short.

Standard library, pytest and PyYAML. The CRAB JSON the template writes is checked with the
`crab validate` of this repository's submodule (`CRAB/.venv/bin/crab`).
"""

import itertools
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
JOBS_TEMPLATE = TEMPLATES / "jobs-template.yaml"
README = TEMPLATES / "README.md"
CRAB_BIN = REPO / "CRAB" / ".venv" / "bin" / "crab"

# The same heredoc pattern install.sh and tests/test_benchmarks.py use.
HEREDOC = re.compile(r"<<'?JSON'?\n(.*?)\nJSON\n", re.DOTALL)
KEY_LINE = re.compile(r"^\s*(?:- )?[A-Za-z_][\w-]*:")
BANNED = re.compile(
    r"—|–|\b(simply|just|easy|please|usually|above|below|may|should)\b"
    r"|note that|in order to|the following|this page",
    re.IGNORECASE,
)


def _doc() -> dict[str, Any]:
    return yaml.safe_load(JOBS_TEMPLATE.read_text())


def _key_lines(text: str) -> list[tuple[int, str, str]]:
    """(line number, line, previous line) of every YAML key line outside the preprocess script."""
    lines = text.splitlines()
    found = []
    block_indent: int | None = None
    for number, line in enumerate(lines):
        indent = len(line) - len(line.lstrip())
        if block_indent is not None:
            if not line.strip() or indent > block_indent:
                continue
            block_indent = None
        if KEY_LINE.match(line):
            found.append((number + 1, line, lines[number - 1] if number else ""))
            if re.match(r"^\s*(?:- )?preprocess:\s*\|\s*$", line):
                block_indent = indent + 2 if line.lstrip().startswith("- ") else indent
    return found


def test_the_template_files_exist() -> None:
    assert JOBS_TEMPLATE.is_file()
    assert README.is_file()


def test_the_template_is_a_jobs_file_with_configs_variables_and_jobs() -> None:
    doc = _doc()

    assert isinstance(doc["configs"], str)
    assert doc["variables"]["nodes"]
    assert len(doc["jobs"]) == 1
    job = doc["jobs"][0]
    for key in ("config", "tag", "command", "preprocess"):
        assert job[key], key
    assert HEREDOC.search(job["preprocess"])


def test_the_template_is_at_most_60_lines() -> None:
    assert len(JOBS_TEMPLATE.read_text().splitlines()) <= 60


def test_every_key_line_follows_a_change_comment() -> None:
    keys = _key_lines(JOBS_TEMPLATE.read_text())

    assert len(keys) >= 8
    for number, line, previous in keys:
        assert previous.lstrip().startswith("#"), f"line {number} has no comment before it: {line}"
        assert "Change:" in previous, f"line {number}: the comment has no 'Change:' part"


def test_the_embedded_json_passes_crab_validate(tmp_path: Path) -> None:
    if not CRAB_BIN.is_file():
        pytest.skip("CRAB/.venv/bin/crab is not present (run ./install.sh first)")
    doc = _doc()
    job = doc["jobs"][0]
    match = HEREDOC.search(job["preprocess"])
    assert match
    names = list(doc["variables"])
    env = {
        **os.environ,
        "CRAB_PATH_WRAPPERS": str(REPO / "crab-wrappers"),
        "CRAB_ROOT": str(REPO / "CRAB"),
    }
    checked = 0

    for values in itertools.product(*doc["variables"].values()):
        text = match.group(1)
        for name, value in zip(names, values, strict=True):
            text = text.replace("{" + name + "}", str(value))
        text = text.replace("$SBATCHMAN_WD", str(JOBS_TEMPLATE.parent))
        text = text.replace("$CRAB_ROOT", str(REPO / "CRAB"))
        assert not re.search(r"\{[a-z_]+\}", text)
        checked += 1
        config = tmp_path / f"config-{checked}.json"
        config.write_text(text + "\n")

        result = subprocess.run(
            [str(CRAB_BIN), "validate", str(config)],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    assert checked >= 1


def test_the_readme_has_at_most_20_lines() -> None:
    assert len(README.read_text().splitlines()) <= 20


@pytest.mark.parametrize("path", [JOBS_TEMPLATE, README], ids=lambda p: p.name)
def test_the_writing_rules_hold(path: Path) -> None:
    text = path.read_text()

    assert not BANNED.search(text), BANNED.search(text)
    assert "**" not in text
