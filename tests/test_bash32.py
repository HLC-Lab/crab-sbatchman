"""Tests that install.sh stays runnable by bash 3.2, the /bin/bash of macOS.

Three layers: a static scan for syntax newer than 3.2 (always runs), a behavior test of the
configs substitution under the default bash, and a run of the stubbed installer inside the
`bash:3.2` container image (skipped unless docker and that image are already there; tests never
pull). Standard library and pytest only.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from test_install import REPO, TOKEN_TEMPLATE, _write, hashes, make_umbrella, run_install

INSTALL = REPO / "install.sh"

# Syntax or builtins that bash 3.2 lacks, or handles differently from newer bashes.
FORBIDDEN = [
    (r"local\s+-[a-zA-Z]*n", "local -n (nameref, bash 4.3)"),
    (r"declare\s+-[a-zA-Z]*[AnG]", "declare -A/-n/-g (bash 4.0 and later)"),
    (r"typeset\s+-[a-zA-Z]*[AnG]", "typeset -A/-n/-g (bash 4.0 and later)"),
    (r"\bmapfile\b", "mapfile (bash 4.0)"),
    (r"\breadarray\b", "readarray (bash 4.0)"),
    (r"\$\{[^}]*(,,|\^\^)", "${var,,} / ${var^^} (bash 4.0)"),
    (r"\$\{[^}]*(?<![,^])[,^][^,^}]*\}", "${var,} / ${var^} (bash 4.0)"),
    (r"\[\[\s+-v\b", "[[ -v VAR ]] (bash 4.2)"),
    (r"\bwait\s+-n\b", "wait -n (bash 4.3)"),
    (r"\bcoproc\b", "coproc (bash 4.0)"),
    (r"&>>", "&>> (bash 4.0)"),
    (r"\|&", "|& (bash 4.0)"),
    (r"\$\{[^}]*//\"", 'nested double quotes in a replacement: ${v//"a"/"b"} (3.2 keeps them)'),
    (r"\$\{[^}]*/\"[^}]*\"\}", 'nested double quotes in a replacement: ${v/"a"/"b"}'),
    (r"\bprintf\s+-v\s+\S+\[", "printf -v into an array element (bash 4.1)"),
    (r"\bread\s[^\n]*-i\s", "read -i (readline text, bash 4)"),
    (r"\bread\s[^\n]*-t\s+0\.", "read -t with a fraction (bash 4)"),
    (r"\bglobstar\b|\bcheckwinsize\b|\bnocasematch\b|\bautocd\b", "a shopt option of bash 4"),
]


def code_lines() -> list[tuple[int, str]]:
    """The lines of install.sh with whole-line comments dropped."""
    out = []
    for number, line in enumerate(INSTALL.read_text().splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        out.append((number, line))
    return out


@pytest.mark.parametrize(("pattern", "what"), FORBIDDEN, ids=[w for _, w in FORBIDDEN])
def test_install_uses_no_syntax_newer_than_bash_3_2(pattern, what):
    hits = [f"{n}: {line.strip()}" for n, line in code_lines() if re.search(pattern, line)]
    assert not hits, f"{what}:\n" + "\n".join(hits)


def test_every_array_expansion_is_guarded_or_cannot_be_empty():
    """Bash 3.2 and 4.3 fail on "${arr[@]}" of an empty array under `set -u`."""
    text = INSTALL.read_text()
    assert "set -euo pipefail" in text
    # The only expanded arrays are all/picked in check_jobs_file; both are filled before use.
    expansions = re.findall(r'"\$\{(\w+)\[@\]\}"', text)
    assert sorted(set(expansions)) == ["all", "picked"]
    assert "if [[ $total -eq 0 ]]" in text


def test_configs_substitution_is_literal_for_pattern_special_characters(tmp_path):
    """Partition and QOS come from site/local.env and may hold & / * \\ and quotes."""
    base = tmp_path / "a&b"
    base.mkdir()
    root = make_umbrella(base)
    _write(
        root / "site" / "local.env",
        "SLURM_PARTITION='p&q/r*s\\t\"u'\nSLURM_QOS='&&x'\n",
    )
    result = run_install(root, "--account", "A.B-c_1", "--no-check")
    assert result.returncode == 0, result.stderr
    filled = (root / ".local" / "configs.leonardo.yaml").read_text()
    assert filled == (
        "account: A.B-c_1\n"
        'partition: p&q/r*s\\t"u\n'
        "qos: &&x\n"
        f"crab_dir: {root}/CRAB\n"
    )
    assert TOKEN_TEMPLATE.count("\n") == filled.count("\n")


def test_configs_template_without_final_newline_stays_byte_exact(tmp_path):
    root = make_umbrella(tmp_path)
    _write(root / "configs" / "leonardo.yaml", "account: <YOUR_ACCOUNT>\n\n\n  tail: <SLURM_QOS>")
    result = run_install(root, "--account", "ACC", "--no-check")
    assert result.returncode == 0, result.stderr
    filled = (root / ".local" / "configs.leonardo.yaml").read_bytes()
    assert filled == b"account: ACC\n\n\n  tail: testqos"


# ---- the container run -------------------------------------------------------------------

IMAGE = "bash:3.2"

# One shell script stands in for python3 and for the venv's python: no python in the image. It
# answers the version checks, and plays the part of EXTRACT_PY: three configs per jobs file.
STUB_SHELL_PYTHON = """\
#!/bin/sh
case "$1" in
  --version) echo "Python 3.12.0" ;;
  -c)
    case "$2" in
      *itertools*)
        stem="$(basename "$3" .yaml)"
        i=1
        while [ "$i" -le 3 ]; do
          printf '{}\\n' > "$4/$stem-$i.json"
          echo "$4/$stem-$i.json"
          i=$((i + 1))
        done
        ;;
      *) exit 0 ;;
    esac
    ;;
esac
exit 0
"""

# The image has no make: this stands in for `make -C DIR core` of the stub Makefile.
STUB_MAKE = """\
#!/bin/sh
[ "$1" = -C ] || exit 2
cd "$2" && exec sh stub/"$3".sh
"""

SPECIAL_LOCAL_ENV = "SLURM_PARTITION='p&q/r*s\\t\"u'\nSLURM_QOS='&&x'\n"

SCENARIOS = {
    "help": (["--help"], None),
    "dry-run-cluster": (["--dry-run", "--account", "TESTACCT"], None),
    "dry-run-laptop": (["--dry-run", "--role", "laptop"], None),
    "dry-run-no-check": (["--dry-run", "--no-check", "--account", "TESTACCT"], None),
    "cluster-no-check": (["--no-check", "--account", "TESTACCT"], None),
    "cluster-special-characters": (["--no-check", "--account", "A.B-c_1"], SPECIAL_LOCAL_ENV),
    "laptop-no-check": (["--no-check", "--role", "laptop"], None),
    "cluster-check": (["--account", "TESTACCT"], None),
    "cluster-full-check": (["--full-check", "--account", "TESTACCT"], None),
    "laptop-check": (["--role", "laptop"], None),
    "usage-error": (["--bogus"], None),
    "no-account": ([], None),
}


def docker_skip_reason() -> str | None:
    if shutil.which("docker") is None:
        return "docker is not on PATH"
    probe = subprocess.run(
        ["docker", "image", "inspect", IMAGE], capture_output=True, text=True, timeout=60
    )
    if probe.returncode != 0:
        return f"the image {IMAGE} is not present locally (tests never pull: docker pull {IMAGE})"
    return None


def in_container(workdir: Path, stubs: Path, argv: list[str]) -> subprocess.CompletedProcess:
    path = f"{stubs}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{workdir}:{workdir}",
            "-w",
            str(workdir),
            "-e",
            f"PATH={path}",
            "-e",
            "HOME=/tmp",
            IMAGE,
            *argv,
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
    )


def build_scenario(base: Path, local_env: str | None) -> tuple[Path, Path]:
    """A stubbed umbrella whose python is a shell script, plus the stub tools for PATH."""
    root = make_umbrella(base)
    _write(root / "CRAB" / "stub" / "python", STUB_SHELL_PYTHON, executable=True)
    if local_env is not None:
        _write(root / "site" / "local.env", local_env)
    stubs = base / "stubs"
    _write(stubs / "python3", STUB_SHELL_PYTHON, executable=True)
    _write(stubs / "make", STUB_MAKE, executable=True)
    return root, stubs


def wipe(base: Path) -> None:
    for child in base.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def run_twice(base: Path, args: list[str], local_env: str | None, container: bool) -> dict:
    """Runs install.sh twice (the second run proves idempotence), returns what it did.

    Both sides get the same stub make and python3 first on PATH, so the output is comparable.
    """
    root, stubs = build_scenario(base, local_env)
    runs = []
    for _ in range(2):
        if container:
            argv = ["bash", str(root / "install.sh"), *args]
            proc = in_container(base, stubs, argv)
        else:
            proc = run_install(root, *args, path_prefix=stubs)
        runs.append((proc.returncode, proc.stdout, proc.stderr))
    return {"runs": runs, "files": hashes(root)}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_stubbed_install_behaves_the_same_under_bash_3_2_and_the_host_bash(tmp_path, name):
    reason = docker_skip_reason()
    if reason:
        pytest.skip(reason)
    args, local_env = SCENARIOS[name]
    version = in_container(tmp_path, tmp_path, ["bash", "-c", "echo $BASH_VERSION"])
    assert version.stdout.startswith("3.2"), version.stdout + version.stderr
    host = run_twice(tmp_path, args, local_env, container=False)
    wipe(tmp_path)
    old = run_twice(tmp_path, args, local_env, container=True)
    assert old["runs"] == host["runs"]
    assert old["files"] == host["files"]
    if name in ("cluster-no-check", "cluster-special-characters"):
        assert (tmp_path / "umbrella" / ".local" / "configs.leonardo.yaml").is_file()
    if name == "cluster-full-check":
        assert "(3 config(s))" in old["runs"][0][1]
