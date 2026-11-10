"""Locks the layout of the umbrella repo. Standard library only, no network."""

import configparser
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def _tracked_files() -> list[str]:
    return [line for line in _git("ls-files").splitlines() if line]


def test_gitmodules_lists_exactly_two_https_submodules():
    gitmodules = ROOT / ".gitmodules"
    assert gitmodules.is_file()
    parser = configparser.ConfigParser()
    parser.read(gitmodules)
    sections = {s: dict(parser[s]) for s in parser.sections()}
    assert len(sections) == 2
    by_path = {entry["path"]: entry for entry in sections.values()}
    assert set(by_path) == {"CRAB", "crab-wrappers"}
    for entry in by_path.values():
        assert entry["url"].startswith("https://")
        assert "git@" not in entry["url"]
    assert by_path["CRAB"]["branch"] == "sbatchman"


def test_submodules_are_gitlinks_and_crab_is_pinned():
    gitlinks = {}
    for line in _git("ls-files", "-s").splitlines():
        meta, path = line.split("\t", 1)
        mode, commit, _stage = meta.split()
        gitlinks[path] = (mode, commit)
    assert gitlinks["CRAB"][0] == "160000"
    assert gitlinks["crab-wrappers"][0] == "160000"
    assert gitlinks["CRAB"][1].startswith("f4e7190a")


def test_tracked_folders_exist_and_site_file_has_placeholder():
    for folder in ("benchmarks/blink", "benchmarks/qe", "configs", "site"):
        assert (ROOT / folder).is_dir(), folder
    leonardo = (ROOT / "site" / "leonardo.env").read_text()
    assert "<YOUR_ACCOUNT>" in leonardo
    assert "ACCOUNT_PREFIX" not in leonardo


def test_gitignore_has_local_files():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    for entry in ("env.sh", ".local/", "site/local.env"):
        assert entry in lines, entry


def test_no_undecided_repo_name_in_tracked_text():
    submodule_paths = {"CRAB", "crab-wrappers"}
    forbidden = re.compile(r"crab-suite|net4exa|github\.com/HLC-Lab/(?!CRAB\b|crab-wrappers\b)")
    for name in _tracked_files():
        if name == ".gitmodules" or name in submodule_paths:
            continue
        if name == "tests/test_layout.py":
            continue
        try:
            text = (ROOT / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue
        assert not forbidden.search(text), name
