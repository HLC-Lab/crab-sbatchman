"""Tests install.sh against a tmp copy of the umbrella. Standard library and pytest only.

CRAB's Makefile, pip, sbatchman and crab are stubs: no network, no real venv.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

TOKEN_TEMPLATE = """\
account: <YOUR_ACCOUNT>
partition: <SLURM_PARTITION>
qos: <SLURM_QOS>
crab_dir: <CRAB_DIR>
"""

SITE_ENV = """\
SLURM_ACCOUNT="<YOUR_ACCOUNT>"
SLURM_PARTITION="testpart"
SLURM_QOS="testqos"
"""

MAKEFILE = """\
core:
\tsh stub/core.sh
"""

CORE_SH = """\
mkdir -p .venv/bin
cp stub/python stub/pip stub/crab .venv/bin/
"""

# The venv's python is the interpreter running the tests (it has PyYAML), unless STUB_PYTHON_FAIL
# is set: then it answers every call with exit 1, like a venv whose Python is too old.
STUB_PYTHON = """\
#!/bin/sh
if [ -n "$STUB_PYTHON_FAIL" ]; then exit 1; fi
exec "@PYTHON@" "$@"
"""

JOBS_FILE = """\
configs: ../../.local/configs.leonardo.yaml
variables:
  nodes:
    - 2
    - 4
jobs:
  - config: crab_run_{nodes}
    tag: t-{nodes}
    preprocess: |
      mkdir -p "$SBATCHMAN_JOB_DIR"
      cat > "$SBATCHMAN_JOB_DIR/config.json" <<JSON
      {"nodes": "{nodes}", "input": "$SBATCHMAN_WD/in.txt", "root": "$CRAB_ROOT"}
      JSON
    command: crab worker --workdir "$SBATCHMAN_JOB_DIR"
"""

STUB_PIP = """\
#!/bin/sh
echo "$@" >> "@LOG@/pip.log"
if [ "$1" = show ]; then
  printf 'Name: sbatchman\nVersion: %s\n' "${STUB_PIP_SHOW_VERSION:-${SBATCHMAN_VERSION:-2.0.4}}"
  exit 0
fi
for a in "$@"; do
  case "$a" in
    sbatchman*) cp "$(dirname "$0")/../../stub/sbatchman" "$(dirname "$0")/sbatchman" ;;
  esac
done
exit 0
"""

STUB_SBATCHMAN = """\
#!/bin/sh
if [ "$1" = init ]; then
  mkdir -p SbatchMan/configs SbatchMan/experiments
  echo "$PWD" >> "@LOG@/sbatchman.log"
fi
if [ "$1" = launch ]; then
  echo "$PWD: $*" >> "@LOG@/launch.log"
  echo "SBATCHMAN_CLUSTER_NAME=$SBATCHMAN_CLUSTER_NAME" >> "@LOG@/launch.log"
  if [ -n "$STUB_LAUNCH_FAIL" ]; then
    echo "stub: no configs file" >&2
    exit 1
  fi
fi
exit 0
"""

STUB_CRAB = """\
#!/bin/sh
echo "$*" >> "@LOG@/crab.log"
if [ "$1" = validate ]; then
  mkdir -p "@LOG@/validated"
  cp "$2" "@LOG@/validated/$(basename "$2")"
  echo "$CRAB_PATH_WRAPPERS" > "@LOG@/validate-wrappers"
  if [ -n "$STUB_VALIDATE_FAIL" ]; then
    case "$2" in
      *"$STUB_VALIDATE_FAIL"*)
        echo "crab: stub rejects this config" >&2
        exit 1
        ;;
    esac
  fi
  echo "ok: $2"
fi
exit 0
"""

LOGS = {"pip.log", "sbatchman.log", "launch.log", "validate-wrappers", "crab.log"}


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def make_umbrella(tmp_path: Path) -> Path:
    root = (tmp_path / "umbrella").resolve()
    root.mkdir()
    shutil.copy2(REPO / "install.sh", root / "install.sh")
    _write(root / "CRAB" / "Makefile", MAKEFILE)
    _write(root / "CRAB" / "stub" / "core.sh", CORE_SH)
    log = str(root.parent)
    _write(
        root / "CRAB" / "stub" / "python",
        STUB_PYTHON.replace("@PYTHON@", sys.executable),
        executable=True,
    )
    _write(root / "CRAB" / "stub" / "pip", STUB_PIP.replace("@LOG@", log), executable=True)
    _write(
        root / "CRAB" / "stub" / "sbatchman",
        STUB_SBATCHMAN.replace("@LOG@", log),
        executable=True,
    )
    _write(root / "CRAB" / "stub" / "crab", STUB_CRAB.replace("@LOG@", log), executable=True)
    _write(root / "crab-wrappers" / "README.md", "wrappers\n")
    _write(root / "benchmarks" / "blink" / "smoke.yaml", JOBS_FILE)
    _write(root / "benchmarks" / "qe" / "qe-alone.yaml", JOBS_FILE)
    _write(root / "site" / "leonardo.env", SITE_ENV)
    _write(root / "configs" / "leonardo.yaml", TOKEN_TEMPLATE)
    return root


def run_install(
    root: Path, *args: str, env_extra: dict | None = None, path_prefix: Path | None = None
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("SLURM_ACCOUNT", None)
    env.pop("SBATCHMAN_VERSION", None)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    env.update(env_extra or {})
    return subprocess.run(
        [str(root / "install.sh"), *args],
        cwd=root.parent,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


def crab_calls(tmp_path: Path) -> list[str]:
    """The arguments of every call the stub crab received (empty when it was never called)."""
    log = tmp_path / "crab.log"
    return log.read_text().splitlines() if log.exists() else []


def listing(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def hashes(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = "link:" + os.readlink(p)
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            out[rel] = "dir"
    return out


def test_dry_run_prints_commands_and_writes_nothing(tmp_path):
    root = make_umbrella(tmp_path)
    before = listing(root)
    result = run_install(root, "--dry-run", "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    plus = [line for line in result.stdout.splitlines() if line.startswith("+ ")]
    joined = "\n".join(plus)
    assert "make -C" in joined
    assert "pip install" in joined
    assert "ln -s ../crab-wrappers" in joined
    assert "sbatchman init" in joined
    assert "+ write" in joined
    assert listing(root) == before
    assert not (root / "CRAB" / "wrappers").is_symlink()
    assert not (tmp_path / "pip.log").exists()


def test_full_run_installs_everything(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    link = root / "CRAB" / "wrappers"
    assert link.is_symlink()
    assert os.readlink(link) == "../crab-wrappers"
    assert "sbatchman==2.0.4" in (tmp_path / "pip.log").read_text()
    configs = (root / ".local" / "configs.leonardo.yaml").read_text()
    assert "TESTACCT" in configs
    assert "testpart" in configs
    assert "testqos" in configs
    assert str(root / "CRAB") in configs
    assert "<" not in configs
    assert 'SLURM_ACCOUNT="TESTACCT"' in (root / "site" / "local.env").read_text()
    assert (root / "benchmarks" / "blink" / "SbatchMan").is_dir()
    assert (root / "benchmarks" / "qe" / "SbatchMan").is_dir()
    assert not any(call.split()[0] == "setup" for call in crab_calls(tmp_path))
    assert "+ make -C" in result.stdout
    assert "+ " + str(root / "CRAB" / ".venv" / "bin" / "pip") + " install" in result.stdout
    assert "install.sh finished: role cluster" in result.stdout


def test_second_run_changes_nothing(tmp_path):
    root = make_umbrella(tmp_path)
    first = run_install(root, "--account", "TESTACCT")
    assert first.returncode == 0, first.stderr

    def snapshot():
        return {k: v for k, v in hashes(root).items() if Path(k).name not in LOGS}

    before = snapshot()
    second = run_install(root, "--account", "TESTACCT")
    assert second.returncode == 0, second.stderr
    assert snapshot() == before
    assert "+ write" not in second.stdout
    assert "sbatchman init" not in second.stdout
    log_lines = (tmp_path / "sbatchman.log").read_text().splitlines()
    assert len(log_lines) == 2
    assert os.readlink(root / "CRAB" / "wrappers") == "../crab-wrappers"


def test_laptop_role_installs_web_extra_and_no_configs(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    pip_log = (tmp_path / "pip.log").read_text()
    assert "[web]" in pip_log
    assert "sbatchman[visualization]==2.0.4" in pip_log
    assert not (root / ".local" / "configs.leonardo.yaml").exists()
    assert not (root / "site" / "local.env").exists()
    assert (root / "benchmarks" / "blink" / "SbatchMan").is_dir()
    assert (root / "benchmarks" / "qe" / "SbatchMan").is_dir()
    assert not any(call.split()[0] == "setup" for call in crab_calls(tmp_path))


def test_old_python_stops_before_changing_anything(tmp_path):
    root = make_umbrella(tmp_path)
    stubs = tmp_path / "oldpy"
    _write(
        stubs / "python3",
        '#!/bin/sh\ncase "$1" in\n  --version) echo "Python 3.6.8" ;;\n  *) exit 1 ;;\nesac\n',
        executable=True,
    )
    before = listing(root)
    result = run_install(root, "--account", "TESTACCT", path_prefix=stubs)
    assert result.returncode == 1
    assert "module load python" in result.stderr
    assert "Python 3.6.8" in result.stderr
    assert listing(root) == before


def test_no_account_and_no_terminal_exits_2(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root)
    assert result.returncode == 2
    assert "--account" in result.stderr
    assert not (root / "site" / "local.env").exists()


def test_local_env_is_used_and_account_flag_replaces_one_line(tmp_path):
    root = make_umbrella(tmp_path)
    _write(root / "site" / "local.env", 'SLURM_ACCOUNT="FROMFILE"\nSLURM_QOS="myqos"\n')
    result = run_install(root)
    assert result.returncode == 0, result.stderr
    configs = (root / ".local" / "configs.leonardo.yaml").read_text()
    assert "FROMFILE" in configs
    assert "myqos" in configs
    assert (root / "site" / "local.env").read_text() == (
        'SLURM_ACCOUNT="FROMFILE"\nSLURM_QOS="myqos"\n'
    )
    result = run_install(root, "--account", "X")
    assert result.returncode == 0, result.stderr
    assert (root / "site" / "local.env").read_text() == 'SLURM_ACCOUNT="X"\nSLURM_QOS="myqos"\n'
    assert "account: X\n" in (root / ".local" / "configs.leonardo.yaml").read_text()


def test_sbatchman_version_comes_from_the_environment(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root, "--account", "TESTACCT", env_extra={"SBATCHMAN_VERSION": "9.9.9"}
    )
    assert result.returncode == 0, result.stderr
    pip_log = (tmp_path / "pip.log").read_text()
    assert "sbatchman==9.9.9" in pip_log
    assert "2.0.4" not in pip_log


def test_unknown_flag_prints_usage_and_exits_2(tmp_path):
    root = make_umbrella(tmp_path)
    before = listing(root)
    result = run_install(root, "--bogus")
    assert result.returncode == 2
    assert "Usage" in result.stderr
    assert listing(root) == before


def test_a_stray_benchmarks_folder_without_yaml_gets_no_sbatchman_init(tmp_path):
    root = make_umbrella(tmp_path)
    (root / "benchmarks" / "__pycache__").mkdir()
    _write(root / "benchmarks" / "__pycache__" / "parser.cpython-314.pyc", "x")
    (root / "benchmarks" / "notes").mkdir()

    result = run_install(root, "--account", "TESTACCT")

    assert result.returncode == 0, result.stderr
    assert (root / "benchmarks" / "blink" / "SbatchMan").is_dir()
    assert (root / "benchmarks" / "qe" / "SbatchMan").is_dir()
    assert not (root / "benchmarks" / "__pycache__" / "SbatchMan").exists()
    assert not (root / "benchmarks" / "notes" / "SbatchMan").exists()
    log_lines = (tmp_path / "sbatchman.log").read_text().splitlines()
    assert sorted(Path(line).name for line in log_lines) == ["blink", "qe"]


# ---- the self-check at the end of install.sh ----


def check_lines(result: subprocess.CompletedProcess) -> list[str]:
    return [ln for ln in result.stdout.splitlines() if ln.startswith(("OK ", "FAIL "))]


def line_with(lines: list[str], *needles: str) -> str:
    found = [ln for ln in lines if all(n in ln for n in needles)]
    assert len(found) == 1, (needles, lines)
    return found[0]


def test_check_cluster_run_prints_ok_for_every_check(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    lines = check_lines(result)
    assert all(ln.startswith("OK ") for ln in lines), lines
    line_with(lines, "python 3.10")
    line_with(lines, "sbatchman 2.0.4")
    line_with(lines, "crab", "CRAB/.venv/bin")
    line_with(lines, "sbatchman", "resolves", "CRAB/.venv/bin")
    line_with(lines, "wrappers")
    line_with(lines, "benchmarks/blink/smoke.yaml", "crab validate")
    line_with(lines, "benchmarks/qe/qe-alone.yaml", "crab validate")
    line_with(lines, "launch --dry-run", "benchmarks/blink/smoke.yaml")
    assert len(lines) == 8
    out = result.stdout.splitlines()
    assert "install.sh: all checks passed" in out
    assert out.index("install.sh: all checks passed") < out.index("install.sh finished: role cluster")
    # The jobs file's variables are filled in, one config per value, and the wrappers are found.
    validated = tmp_path / "validated"
    configs = {p.name: json.loads(p.read_text()) for p in validated.iterdir()}
    assert sorted(c["nodes"] for c in configs.values()) == ["2", "2", "4", "4"]
    assert all(c["root"] == str(root / "CRAB") for c in configs.values())
    assert {c["input"] for c in configs.values()} == {
        str(root / "benchmarks" / "blink" / "in.txt"),
        str(root / "benchmarks" / "qe" / "in.txt"),
    }
    assert (tmp_path / "validate-wrappers").read_text().strip() == str(root / "crab-wrappers")
    launch = (tmp_path / "launch.log").read_text()
    assert f"{root / 'benchmarks' / 'blink'}: launch -f smoke.yaml --dry-run" in launch
    assert "SBATCHMAN_CLUSTER_NAME=leonardo" in launch
    assert not any(call.split()[0] == "setup" for call in crab_calls(tmp_path))


def test_check_leaves_no_temporary_files_in_the_umbrella(tmp_path):
    root = make_umbrella(tmp_path)
    first = run_install(root, "--account", "TESTACCT")
    assert first.returncode == 0, first.stderr
    assert not list(root.rglob("*.json"))


def test_check_failed_validate_names_the_file_and_later_checks_still_run(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root,
        "--account",
        "TESTACCT",
        env_extra={"STUB_VALIDATE_FAIL": "qe-alone"},
    )
    assert result.returncode == 1
    lines = check_lines(result)
    failed = [ln for ln in lines if ln.startswith("FAIL ")]
    assert len(failed) == 1, lines
    assert "benchmarks/qe/qe-alone.yaml" in failed[0]
    assert "stub rejects this config" in failed[0]
    line_with(lines, "benchmarks/blink/smoke.yaml", "crab validate")
    # The dry-run launch comes after the failed file and still ran.
    assert lines[-1].startswith("OK ") and "launch --dry-run" in lines[-1]
    assert "install.sh: 1 check(s) failed" in result.stdout.splitlines()
    # Everything before the check ran.
    assert (root / ".local" / "configs.leonardo.yaml").is_file()
    assert (root / "env.sh").is_file()
    assert "install.sh finished: role cluster" in result.stdout


def test_check_failed_dry_run_launch_fails_the_run(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root, "--account", "TESTACCT", env_extra={"STUB_LAUNCH_FAIL": "1"}
    )
    assert result.returncode == 1
    lines = check_lines(result)
    failed = [ln for ln in lines if ln.startswith("FAIL ")]
    assert len(failed) == 1, lines
    assert "launch --dry-run" in failed[0]
    assert "stub: no configs file" in failed[0]
    assert "install.sh: 1 check(s) failed" in result.stdout.splitlines()


def test_check_empty_wrappers_folder_fails_but_the_rest_runs(tmp_path):
    root = make_umbrella(tmp_path)
    (root / "crab-wrappers" / "README.md").unlink()
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 1
    lines = check_lines(result)
    failed = [ln for ln in lines if ln.startswith("FAIL ")]
    assert len(failed) == 1 and "wrappers" in failed[0] and "empty" in failed[0], lines
    line_with(lines, "launch --dry-run")


def test_check_old_venv_python_fails_loudly_and_the_other_checks_still_run(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root, "--account", "TESTACCT", env_extra={"STUB_PYTHON_FAIL": "1"}
    )
    assert result.returncode == 1
    lines = check_lines(result)
    assert line_with(lines, "python").startswith("FAIL ")
    # The jobs files cannot be read without the venv's python: a FAIL naming each file, not a crash.
    assert line_with(lines, "jobs file", "benchmarks/blink/smoke.yaml").startswith("FAIL ")
    line_with(lines, "wrappers")
    line_with(lines, "launch --dry-run")


def test_check_wrong_sbatchman_version_fails_with_both_versions(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root, "--account", "TESTACCT", env_extra={"STUB_PIP_SHOW_VERSION": "1.0.0"}
    )
    assert result.returncode == 1
    failed = [ln for ln in check_lines(result) if ln.startswith("FAIL ")]
    assert len(failed) == 1, failed
    assert "sbatchman" in failed[0] and "1.0.0" in failed[0] and "2.0.4" in failed[0]


def test_no_check_skips_the_whole_block(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root,
        "--account",
        "TESTACCT",
        "--no-check",
        env_extra={"STUB_VALIDATE_FAIL": "smoke", "STUB_LAUNCH_FAIL": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert check_lines(result) == []
    assert "Checking the install" not in result.stdout
    assert "all checks passed" not in result.stdout
    assert "check(s) failed" not in result.stdout
    assert not (tmp_path / "validated").exists()
    assert not (tmp_path / "launch.log").exists()
    assert "install.sh finished: role cluster" in result.stdout


def test_dry_run_lists_the_checks_and_runs_none(tmp_path):
    root = make_umbrella(tmp_path)
    before = listing(root)
    result = run_install(root, "--dry-run", "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    would = [ln for ln in result.stdout.splitlines() if ln.startswith("would check: ")]
    assert len(would) == 8, would
    line_with(would, "python 3.10")
    line_with(would, "sbatchman 2.0.4")
    line_with(would, "wrappers")
    line_with(would, "jobs file", "benchmarks/blink/smoke.yaml")
    line_with(would, "benchmarks/qe/qe-alone.yaml")
    line_with(would, "launch --dry-run")
    assert check_lines(result) == []
    assert "check(s) failed" not in result.stdout
    assert "all checks passed" not in result.stdout
    assert listing(root) == before
    assert not (tmp_path / "validated").exists()
    assert not (tmp_path / "launch.log").exists()
    assert not (tmp_path / "validate-wrappers").exists()


def test_dry_run_with_no_check_lists_nothing(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--dry-run", "--no-check", "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    assert "would check" not in result.stdout


def test_second_run_prints_the_same_check_lines_and_changes_no_file(tmp_path):
    root = make_umbrella(tmp_path)
    first = run_install(root, "--account", "TESTACCT")
    assert first.returncode == 0, first.stderr

    def snapshot():
        return {k: v for k, v in hashes(root).items() if Path(k).name not in LOGS}

    before = snapshot()
    second = run_install(root, "--account", "TESTACCT")
    assert second.returncode == 0, second.stderr
    assert check_lines(second) == check_lines(first)
    assert len(check_lines(second)) == 8
    assert snapshot() == before
    assert "+ write" not in second.stdout


def test_laptop_role_runs_only_the_checks_that_apply(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    lines = check_lines(result)
    assert all(ln.startswith("OK ") for ln in lines), lines
    line_with(lines, "python 3.10")
    line_with(lines, "sbatchman 2.0.4")
    line_with(lines, "wrappers")
    line_with(lines, "benchmarks/blink/smoke.yaml", "crab validate")
    line_with(lines, "benchmarks/qe/qe-alone.yaml", "crab validate")
    assert not any("launch" in ln for ln in lines)
    assert len(lines) == 7
    assert not (tmp_path / "launch.log").exists()
    assert "install.sh: all checks passed" in result.stdout.splitlines()


def test_laptop_role_dry_run_lists_no_launch_check(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--role", "laptop", "--dry-run")
    assert result.returncode == 0, result.stderr
    would = [ln for ln in result.stdout.splitlines() if ln.startswith("would check: ")]
    assert len(would) == 7, would
    assert not any("launch" in ln for ln in would)


def test_laptop_role_failed_validate_exits_1(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--role", "laptop", env_extra={"STUB_VALIDATE_FAIL": "smoke"})
    assert result.returncode == 1
    assert "install.sh: 1 check(s) failed" in result.stdout.splitlines()


def test_the_check_needs_no_account_on_the_laptop(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    assert not (root / "site" / "local.env").exists()


def test_cluster_run_never_calls_crab_setup_and_reads_no_stdin(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    calls = crab_calls(tmp_path)
    assert calls, "the self-check should have called crab validate"
    assert all(call.split()[0] == "validate" for call in calls), calls
    assert "crab setup" not in result.stdout
    assert "wizard" not in result.stdout


@pytest.mark.parametrize(
    "flag",
    [
        ("--no-setup",),
        ("--login-host", "login.example.org"),
        ("--user", "alice"),
        ("--remote-dir", "~/umb"),
    ],
)
@pytest.mark.parametrize("role", ["cluster", "laptop"])
def test_removed_flags_are_unknown_arguments(tmp_path, role, flag):
    root = make_umbrella(tmp_path)
    before = listing(root)
    result = run_install(root, "--role", role, "--account", "T", *flag)
    assert result.returncode == 2
    assert f"install.sh: unknown argument: {flag[0]}" in result.stderr
    assert "Usage:" in result.stderr
    assert listing(root) == before


def test_usage_lists_only_the_kept_flags(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--help")
    assert result.returncode == 0
    for gone in ("--no-setup", "--login-host", "--user", "--remote-dir", "wizard", "SITE_"):
        assert gone not in result.stdout, gone
    for kept in ("--role", "--account", "--no-check", "--dry-run"):
        assert kept in result.stdout, kept


def test_site_user_in_local_env_is_ignored_on_both_roles(tmp_path):
    root = make_umbrella(tmp_path)
    (root / "site" / "local.env").write_text('SLURM_ACCOUNT="TESTACCT"\nSITE_USER=x\n')
    cluster = run_install(root)
    assert cluster.returncode == 0, cluster.stderr
    assert "SITE_USER" not in cluster.stdout + cluster.stderr
    laptop = run_install(root, "--role", "laptop")
    assert laptop.returncode == 0, laptop.stderr
    assert "SITE_USER" not in laptop.stdout + laptop.stderr


def test_a_jobs_file_without_an_embedded_config_fails_naming_the_file(tmp_path):
    root = make_umbrella(tmp_path)
    _write(root / "benchmarks" / "blink" / "smoke.yaml", "a: 1\n")
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 1
    failed = [ln for ln in check_lines(result) if ln.startswith("FAIL ")]
    assert len(failed) == 1 and "benchmarks/blink/smoke.yaml" in failed[0], failed


def test_missing_smoke_file_fails_the_dry_run_launch_check(tmp_path):
    root = make_umbrella(tmp_path)
    (root / "benchmarks" / "blink" / "smoke.yaml").unlink()
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 1
    failed = [ln for ln in check_lines(result) if ln.startswith("FAIL ")]
    assert len(failed) == 1 and "launch --dry-run" in failed[0], failed
    assert "smoke.yaml" in failed[0]


def test_usage_documents_no_check(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(root, "--help")
    assert result.returncode == 0
    assert "--no-check" in result.stdout
    assert "[--no-check]" in result.stdout.split("\n\n")[0]
    text = result.stdout
    assert "no Slurm job" in text
