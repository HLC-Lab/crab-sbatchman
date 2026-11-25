"""The version pins of the docs, generated from their sources. Standard library only.

    python tests/pins.py            print the pins
    python tests/pins.py --check    exit 1 and list every pin that is wrong or hand-typed
    python tests/pins.py --write    rewrite the pin sites in the docs

Sources: SBATCHMAN_VERSION in install.sh, and the CRAB submodule (the gitlink commit in the index and __version__).
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A site is (page name, regex with one capture group holding the pin, pin name).
SITES = [
    ("*", re.compile(r"github\.com/HLC-Lab/CRAB/blob/([^/\s)]+)/"), "crab_tag"),
    ("reference.md", re.compile(r"SBATCHMAN_VERSION` sets the SbatchMan version to install \(default `([^`]+)`\)"), "sbatchman"),
    ("troubleshooting.md", re.compile(r"FAIL sbatchman version: found \S+, expected (\S+)$", re.MULTILINE), "sbatchman"),
]
# Pages that must hold at least one site of that pin: a rewrite that drops it fails the check.
REQUIRED = [("benchmarks.md", "crab_tag"), ("reference.md", "sbatchman"), ("troubleshooting.md", "sbatchman")]
# Version-like text that is not a pin (page name, regex of the text, why).
ALLOWED = [
    ("troubleshooting.md", re.compile(r"Python 3\.6\.8"), "the old system Python that the installer refuses"),
    ("troubleshooting.md", re.compile(r"found 2\.0\.3,"), "a deliberate wrong value in the sample failure line"),
]
ROOT_PAGES = ["README.md", "RELEASING.md", "CONTRIBUTING.md"]
# A dotted version of three parts, a v-prefixed one of two or three parts, or a commit of 7 or more hex digits
# that mixes digits and letters (so a plain number like 1048576 and a plain word do not match).
PIN_LIKE = re.compile(
    r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w]|\.\d)"
    r"|(?<![\w.])v\d+\.\d+(?![\w]|\.\d)"
    r"|\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b",
    re.IGNORECASE,
)


def _fail(message: str) -> SystemExit:
    return SystemExit(f"pins.py: {message}")


def read(root: Path | None = None) -> dict[str, str]:
    root = root or ROOT
    install = root / "install.sh"
    if not install.is_file():
        raise _fail("install.sh is missing, it holds the SbatchMan pin")
    sbatchman = re.search(r'^SBATCHMAN_VERSION="\$\{SBATCHMAN_VERSION:-([^}]+)\}"$', install.read_text(), re.MULTILINE)
    if not sbatchman:
        raise _fail("install.sh has no SBATCHMAN_VERSION=\"${SBATCHMAN_VERSION:-X}\" line")
    init = root / "CRAB" / "src" / "crab" / "__init__.py"
    if not init.is_file():
        raise _fail("CRAB/src is missing, run `git submodule update --init`")
    version = re.search(r'^__version__ = "([^"]+)"$', init.read_text(), re.MULTILINE)
    if not version:
        raise _fail("CRAB/src/crab/__init__.py has no __version__ line")
    listing = subprocess.run(["git", "ls-files", "-s", "CRAB"], cwd=root, capture_output=True, text=True, check=False)
    gitlink = listing.stdout.split()
    if len(gitlink) < 2:
        raise _fail("`git ls-files -s CRAB` lists no CRAB gitlink, run `git add CRAB`")
    return {
        "sbatchman": sbatchman.group(1),
        "crab_version": version.group(1),
        "crab_tag": f"v{version.group(1)}+sbatchman",
        "wrappers_tag": f"v{version.group(1)}",
        "crab_commit": gitlink[1],
    }


def sites(docs_dir: Path | None = None, root: Path | None = None) -> list[Path]:
    """The pages that may hold a pin: the docs pages, plus the root pages unless docs_dir is given."""
    root = root or ROOT
    pages = sorted((docs_dir or root / "docs").glob("*.md"))
    if docs_dir is None:
        pages += [root / name for name in ROOT_PAGES]
    return pages


def _spans(path: Path, line: str, patterns) -> list[tuple[int, int]]:
    found = []
    for page, regex, *_ in patterns:
        if page in ("*", path.name):
            found += [m.span(1) if m.re.groups else m.span() for m in regex.finditer(line)]
    return found


def check(docs_dir: Path | None = None, root: Path | None = None) -> list[str]:
    """Problems as "page:line message". The pins come from the repo's own sources: root only locates the pages."""
    pins = read()
    base = docs_dir or root or ROOT
    pages = docs_dir or (root or ROOT) / "docs"
    problems = []
    for path in sites(docs_dir, root):
        label = path.relative_to(base)
        found_pins = set()
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            known = _spans(path, line, SITES) + _spans(path, line, ALLOWED)
            for page, regex, name in SITES:
                for match in regex.finditer(line):
                    if page in ("*", path.name):
                        found_pins.add(name)
                        if match.group(1) != pins[name]:
                            problems.append(f"{label}:{number} {name} is {match.group(1)}, the source says {pins[name]}")
            for token in PIN_LIKE.finditer(line):
                if not any(start <= token.start() < end for start, end in known):
                    problems.append(f"{label}:{number} {token.group(0)} is a pin that is not a known site")
        for page, name in REQUIRED:
            if path.name == page and name not in found_pins:
                problems.append(f"{label}:1 no {name} pin site found, the page changed its wording")
    for page, _name in REQUIRED:
        if not (pages / page).is_file():
            problems.append(f"{page}:1 page not found")
    return problems


def _swap(match: re.Match, value: str) -> str:
    """The matched text with its capture group replaced by value."""
    start = match.start()
    return match.group(0)[: match.start(1) - start] + value + match.group(0)[match.end(1) - start :]


def write(docs_dir: Path | None = None, root: Path | None = None) -> list[Path]:
    pins = read()
    changed = []
    for path in sites(docs_dir, root):
        text = path.read_text()
        new = text
        for page, regex, name in SITES:
            if page in ("*", path.name):
                new = regex.sub(lambda m, v=pins[name]: _swap(m, v), new)
        if new != text:
            path.write_text(new)
            changed.append(path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Print, check or write the version pins of the docs.")
    parser.add_argument("--check", action="store_true", help="exit 1 and list every wrong or hand-typed pin")
    parser.add_argument("--write", action="store_true", help="rewrite the pin sites in the docs")
    args = parser.parse_args()
    if args.write:
        for path in write():
            print(f"rewrote {path.relative_to(ROOT)}")
        return 0
    if args.check:
        problems = check()
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    for name, value in read().items():
        print(f"{name}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
