"""Keeps README.md true: headings, install.sh flags, links, forbidden text, tables.

Standard library and pytest only, no network. The flags come from the real `install.sh --help`.
"""

import re
import subprocess
from pathlib import Path

from forbidden import forbidden_or_skip

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

HEADINGS = [
    "What this is",
    "Install on the cluster",
    "Install on your laptop",
    "Run the shipped benchmarks",
    "install.sh reference",
    "Files and what you may change",
    "Add your own benchmark",
    "Update",
    "Troubleshooting",
    "Known limits",
]

# Project names that are not decided yet. The personal words (account, user, host names) are in
# the untracked tests/forbidden-words.txt, see tests/forbidden.py.
FORBIDDEN = (
    "crab-suite",
    "net4exa",
)
FORBIDDEN_URL = re.compile(r"github\.com/HLC-Lab/(?!CRAB\b|crab-wrappers\b)")

# One distinctive phrase per row that the troubleshooting table must have.
ROW_PHRASES = [
    "3.10 or newer",
    "Disk quota exceeded",
    "ImportError",
    "An identical job already exists",
    "No configurations found for cluster",
    "no Slurm account",
    "Failed to submit job",
    "port in use",
]


def _text() -> str:
    return README.read_text()


def _outside_fences(text: str) -> list[str]:
    """The lines of `text` that are not inside a ``` fence (the fence lines are dropped)."""
    lines = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            lines.append(line)
    return lines


def _section(title: str) -> list[str]:
    """The lines of the `## title` section, fences included."""
    lines = _text().splitlines()
    start = lines.index(f"## {title}")
    end = len(lines)
    inside = False
    for at in range(start + 1, len(lines)):
        if lines[at].lstrip().startswith("```"):
            inside = not inside
        if not inside and lines[at].startswith("## "):
            end = at
            break
    return lines[start + 1 : end]


def test_headings_are_exactly_the_ten_agreed_ones_in_order():
    found = [line[3:] for line in _outside_fences(_text()) if line.startswith("## ")]
    assert found == HEADINGS


def test_every_install_flag_is_in_the_reference_section():
    help_text = subprocess.run(
        ["bash", "install.sh", "--help"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    flags = sorted(set(re.findall(r"--[a-z][a-z-]*", help_text)))
    assert {"--role", "--account", "--no-setup", "--dry-run", "--login-host"} <= set(flags)
    section = "\n".join(_section("install.sh reference"))
    for flag in flags:
        assert flag in section, flag


def test_relative_links_point_at_existing_files():
    body = "\n".join(_outside_fences(_text()))
    targets = re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", body)
    assert targets, "the README links to nothing"
    checked = 0
    for target in targets:
        if target.startswith(("http", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        assert (ROOT / path).exists(), target
        checked += 1
    assert checked >= 5


def test_no_forbidden_string_and_the_placeholders_are_there():
    text = _text()
    for word in FORBIDDEN:
        assert word not in text, word
    assert not FORBIDDEN_URL.search(text)
    assert "<umbrella-url>" in text
    assert "<umbrella-dir>" in text


def test_the_readme_has_none_of_the_personal_words():
    text = _text()
    for word in forbidden_or_skip():
        assert word not in text, word


def test_troubleshooting_table_has_the_header_and_the_agreed_rows():
    section = _section("Troubleshooting")
    assert "| Symptom | Cause | Fix |" in section
    rows = [line for line in section if line.startswith("|") and not line.startswith("|---")]
    rows = [row for row in rows if row != "| Symptom | Cause | Fix |"]
    assert len(rows) >= 8
    hits = []
    for phrase in ROW_PHRASES:
        matching = [at for at, row in enumerate(rows) if phrase in row]
        assert matching, phrase
        hits.append(matching[0])
    assert len(set(hits)) == len(ROW_PHRASES), "two phrases share one row"
    skipping = next(row for row in rows if "An identical job already exists" in row)
    assert "Submitted successfully 0 jobs" in skipping
    for row in rows:
        assert row.count("|") >= 4, row


def test_code_fences_are_balanced():
    fences = [line for line in _text().splitlines() if line.lstrip().startswith("```")]
    assert len(fences) % 2 == 0


def test_every_top_level_tracked_path_is_named():
    listing = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    skip = {"tests", ".gitignore", ".gitmodules", "README.md", "pytest.ini"}
    top = {line.split("/", 1)[0] for line in listing.splitlines() if line}
    text = _text()
    missing = sorted(name for name in top - skip if name not in text)
    assert missing == []
