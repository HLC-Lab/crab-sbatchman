"""Locks the layout of the umbrella repo. Standard library only, no network."""

import configparser
import re
import subprocess
from pathlib import Path

from forbidden import forbidden_or_skip

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
    assert gitlinks["CRAB"][1].startswith("5e3d855a")


def test_tracked_folders_exist_and_site_file_has_placeholder():
    for folder in ("benchmarks/blink", "configs", "site"):
        assert (ROOT / folder).is_dir(), folder
    leonardo = (ROOT / "site" / "leonardo.env").read_text()
    assert "<YOUR_ACCOUNT>" in leonardo


def test_no_tracked_benchmark_config_or_site_file_names_the_qe_example():
    """The Quantum ESPRESSO example is not shipped: its folder and its config must not creep back."""
    pattern = re.compile(r"benchmarks/qe|crab_qe")
    for name in _tracked_files():
        if not name.startswith(("benchmarks/", "configs/", "site/")):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        assert not name.startswith("benchmarks/qe"), name
        text = path.read_text(errors="replace")
        assert not pattern.search(text), f"the QE example is named in {name}"


def test_gitignore_has_local_files():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    for entry in ("env.sh", ".local/", "site/local.env", "tests/forbidden-words.txt"):
        assert entry in lines, entry


def test_gitignore_ignores_the_sbatchman_projects_but_not_the_jobs_files():
    """`sbatchman init` makes benchmarks/<name>/SbatchMan/ on every machine: it is never tracked."""
    for path in (
        "benchmarks/blink/SbatchMan/configs/leonardo/crab_run_2.sh",
        "benchmarks/blink/SbatchMan/experiments/leonardo/crab_run_4/smoke-4n/data_app_0.csv",
    ):
        ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, check=False)
        assert ignored.returncode == 0, path
    for path in ("benchmarks/blink/smoke.yaml", "benchmarks/blink/README.md"):
        kept = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, check=False)
        assert kept.returncode == 1, path


def test_no_undecided_repo_name_in_tracked_text():
    submodule_paths = {"CRAB", "crab-wrappers"}
    forbidden = re.compile(r"crab-suite|net4exa|github\.com/HLC-Lab/(?!CRAB\b|crab-wrappers\b|crab-sbatchman\b)")
    for name in _tracked_files():
        if name == ".gitmodules" or name in submodule_paths:
            continue
        if name in ("tests/test_layout.py", "tests/test_docs.py"):
            continue  # both tests list the forbidden words themselves
        try:
            text = (ROOT / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue
        assert not forbidden.search(text), name


def _tracked_text() -> list[tuple[str, str]]:
    """(name, text) of every tracked text file except the submodules (gitlinks are folders)."""
    found = []
    for name in _tracked_files():
        try:
            found.append((name, (ROOT / name).read_text()))
        except (UnicodeDecodeError, OSError):
            continue
    return found


def test_no_tracked_text_file_has_a_personal_word():
    words = forbidden_or_skip()
    texts = _tracked_text()
    assert len(texts) > 20
    for name, text in texts:
        for word in words:
            assert word.lower() not in text.lower(), f"{word!r} in {name}"


# Written as joined pieces so that this file does not match its own patterns.
CLUSTER_PATH = re.compile(
    "/leonardo" + r"/home/[^/\s]+/" + "|/leonardo" + "_work/" + "|/leonardo" + "/pub/"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
NOREPLY = "@users.noreply.github.com"


def test_no_tracked_text_file_has_a_cluster_home_path_or_a_real_email():
    texts = _tracked_text()
    assert len(texts) > 20
    for name, text in texts:
        assert not CLUSTER_PATH.search(text), f"a cluster home or work path in {name}"
        for match in EMAIL.finditer(text):
            assert match.group(0).endswith(NOREPLY), f"{match.group(0)!r} in {name}"


def test_the_path_and_email_patterns_catch_what_they_should():
    home = "/leonardo" + "/home/userexample/CRAB"
    assert CLUSTER_PATH.search(home)
    assert CLUSTER_PATH.search("/leonardo" + "_work/ACCOUNT/x")
    assert CLUSTER_PATH.search("/leonardo" + "/pub/x")
    assert not CLUSTER_PATH.search("/opt/umbrella/CRAB")
    assert EMAIL.search("write to someone" + "@example.org now")
    assert EMAIL.search("12345+name" + NOREPLY).group(0).endswith(NOREPLY)
