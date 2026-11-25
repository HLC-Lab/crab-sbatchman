"""The version pins in the docs come from one script, and a hand-typed pin fails here."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

import pins

ROOT = Path(__file__).resolve().parent.parent
PIN_PAGES = ("benchmarks.md", "reference.md", "troubleshooting.md")
ROOT_PAGES = ("README.md", "RELEASING.md", "CONTRIBUTING.md")
WRONG_VERSION = "0.0.1"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


@pytest.fixture
def docs_copy(tmp_path):
    for name in PIN_PAGES:
        shutil.copy(ROOT / "docs" / name, tmp_path / name)
    return tmp_path


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, old
    path.write_text(text.replace(old, new, 1))


def _append(path: Path, sentence: str) -> None:
    with open(path, "a") as handle:
        handle.write(f"\n{sentence}\n")


def test_the_script_reads_the_pins_from_the_sources():
    found = pins.read()
    install = (ROOT / "install.sh").read_text()
    default = re.search(r'^SBATCHMAN_VERSION="\$\{SBATCHMAN_VERSION:-([^}]+)\}"$', install, re.MULTILINE)
    assert found["sbatchman"] == default.group(1)
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / "CRAB/src/crab/__init__.py").read_text())
    assert found["crab_version"] == version.group(1)
    assert found["crab_tag"] == f"v{found['crab_version']}+sbatchman"
    assert found["wrappers_tag"] == f"v{found['crab_version']}"
    gitlink = _git("ls-files", "-s", "CRAB").stdout.split()[1]
    assert found["crab_commit"] == gitlink


def test_a_missing_source_stops_the_script_with_a_message_that_names_it(tmp_path):
    with pytest.raises(SystemExit, match="install.sh is missing"):
        pins.read(root=tmp_path)
    (tmp_path / "install.sh").write_text("echo no pin here\n")
    with pytest.raises(SystemExit, match="no SBATCHMAN_VERSION"):
        pins.read(root=tmp_path)
    (tmp_path / "install.sh").write_text('SBATCHMAN_VERSION="${SBATCHMAN_VERSION:-1.2.3}"\n')
    with pytest.raises(SystemExit, match="git submodule update --init"):
        pins.read(root=tmp_path)
    init = tmp_path / "CRAB" / "src" / "crab" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text("# no version\n")
    with pytest.raises(SystemExit, match="no __version__"):
        pins.read(root=tmp_path)
    init.write_text('__version__ = "1.2.3"\n')
    with pytest.raises(SystemExit, match="lists no CRAB gitlink"):
        pins.read(root=tmp_path)


def test_every_pin_site_in_the_docs_matches_the_source():
    assert pins.check() == []


def test_a_hand_typed_pin_is_caught(docs_copy):
    found = pins.read()
    _edit(docs_copy / "benchmarks.md", f"blob/{found['crab_tag']}/", "blob/v1.4.0+sbatchman/")
    _edit(docs_copy / "reference.md", f"(default `{found['sbatchman']}`)", f"(default `{WRONG_VERSION}`)")
    problems = pins.check(docs_dir=docs_copy)
    assert any(p.startswith("benchmarks.md:") and "crab_tag" in p for p in problems), problems
    assert any(p.startswith("reference.md:") and "sbatchman" in p for p in problems), problems


@pytest.mark.parametrize(
    "token", ["1.4.0", "v1.4.0", "v1.5", "5e3d855ab0", "5e3d855", "ABC1234F", "abc1234"]
)
def test_a_pin_outside_the_known_sites_is_caught(docs_copy, token):
    _append(docs_copy / "reference.md", f"CRAB {token} is required.")
    problems = pins.check(docs_dir=docs_copy)
    assert len(problems) == 1 and problems[0].startswith("reference.md:") and token in problems[0], problems


def test_numbers_and_python_versions_are_not_pins(docs_copy):
    _append(docs_copy / "reference.md", "Python 3.11 reads port 8765 and 1048576 bytes, from 127.0.0.1 with a feedback loop.")
    assert pins.check(docs_dir=docs_copy) == []


def test_a_pin_in_a_root_page_is_caught(tmp_path):
    shutil.copytree(ROOT / "docs", tmp_path / "docs", ignore=shutil.ignore_patterns("img"))
    for name in ROOT_PAGES:
        shutil.copy(ROOT / name, tmp_path / name)
    assert pins.check(root=tmp_path) == []
    for name in ROOT_PAGES:
        _append(tmp_path / name, "CRAB 1.4.0 is required.")
        problems = pins.check(root=tmp_path)
        assert len(problems) == 1 and problems[0].startswith(f"{name}:") and "1.4.0" in problems[0], problems
        shutil.copy(ROOT / name, tmp_path / name)


def test_write_fixes_the_sites_and_is_idempotent(docs_copy):
    found = pins.read()
    _edit(docs_copy / "benchmarks.md", f"blob/{found['crab_tag']}/", "blob/v1.4.0+sbatchman/")
    _edit(docs_copy / "reference.md", f"(default `{found['sbatchman']}`)", f"(default `{WRONG_VERSION}`)")
    _edit(docs_copy / "troubleshooting.md", f"expected {found['sbatchman']}", f"expected {WRONG_VERSION}")
    assert pins.check(docs_dir=docs_copy) != []
    changed = pins.write(docs_dir=docs_copy)
    assert sorted(p.name for p in changed) == list(PIN_PAGES)
    assert pins.check(docs_dir=docs_copy) == []
    assert pins.write(docs_dir=docs_copy) == []


def test_the_crab_pin_commit_matches_the_submodule_checkout():
    """Guards a gitlink whose __version__ disagrees with the pins in the docs, a submodule HEAD that moved
    away from the gitlink, and, where the tag exists in this clone, a tag that points elsewhere.

    It does not guard a bump to a later commit that keeps the same __version__ when the clone has no tags."""
    found = pins.read()
    head = subprocess.run(
        ["git", "-C", str(ROOT / "CRAB"), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    assert found["crab_commit"] == head.stdout.strip()
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / "CRAB/src/crab/__init__.py").read_text())
    assert version.group(1) == found["crab_version"]
    tagged = subprocess.run(
        ["git", "-C", str(ROOT / "CRAB"), "rev-parse", "-q", "--verify", f"refs/tags/{found['crab_tag']}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if tagged.returncode != 0:
        pytest.skip("the tag is not in this clone")
    assert tagged.stdout.strip() == found["crab_commit"]
