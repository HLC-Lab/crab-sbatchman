"""Tests install.sh against a tmp copy of the umbrella. Standard library and pytest only.

CRAB's Makefile, pip, sbatchman and crab are stubs: no network, no real venv.
"""

import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

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

STUB_PYTHON = "#!/bin/sh\nexit 0\n"

STUB_PIP = """\
#!/bin/sh
echo "$@" >> "@LOG@/pip.log"
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
exit 0
"""

STUB_CRAB = """\
#!/bin/sh
if [ "$1" = setup ]; then
  touch "@LOG@/crab-setup-called"
fi
exit 0
"""

LOGS = {"pip.log", "sbatchman.log"}


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
    _write(root / "CRAB" / "stub" / "python", STUB_PYTHON, executable=True)
    _write(root / "CRAB" / "stub" / "pip", STUB_PIP.replace("@LOG@", log), executable=True)
    _write(
        root / "CRAB" / "stub" / "sbatchman",
        STUB_SBATCHMAN.replace("@LOG@", log),
        executable=True,
    )
    _write(root / "CRAB" / "stub" / "crab", STUB_CRAB.replace("@LOG@", log), executable=True)
    _write(root / "crab-wrappers" / "README.md", "wrappers\n")
    _write(root / "benchmarks" / "blink" / "smoke.yaml", "a: 1\n")
    _write(root / "benchmarks" / "qe" / "qe-alone.yaml", "a: 1\n")
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
    result = run_install(root, "--dry-run", "--account", "TESTACCT", "--no-setup")
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
    result = run_install(root, "--account", "TESTACCT", "--no-setup")
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
    assert not (tmp_path / "crab-setup-called").exists()
    assert "+ make -C" in result.stdout
    assert "+ " + str(root / "CRAB" / ".venv" / "bin" / "pip") + " install" in result.stdout
    assert "install.sh finished: role cluster" in result.stdout


def test_second_run_changes_nothing(tmp_path):
    root = make_umbrella(tmp_path)
    first = run_install(root, "--account", "TESTACCT", "--no-setup")
    assert first.returncode == 0, first.stderr

    def snapshot():
        return {k: v for k, v in hashes(root).items() if Path(k).name not in LOGS}

    before = snapshot()
    second = run_install(root, "--account", "TESTACCT", "--no-setup")
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
    assert not (tmp_path / "crab-setup-called").exists()


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
    result = run_install(root, "--no-setup")
    assert result.returncode == 2
    assert "--account" in result.stderr
    assert not (root / "site" / "local.env").exists()


def test_local_env_is_used_and_account_flag_replaces_one_line(tmp_path):
    root = make_umbrella(tmp_path)
    _write(root / "site" / "local.env", 'SLURM_ACCOUNT="FROMFILE"\nSLURM_QOS="myqos"\n')
    result = run_install(root, "--no-setup")
    assert result.returncode == 0, result.stderr
    configs = (root / ".local" / "configs.leonardo.yaml").read_text()
    assert "FROMFILE" in configs
    assert "myqos" in configs
    assert (root / "site" / "local.env").read_text() == (
        'SLURM_ACCOUNT="FROMFILE"\nSLURM_QOS="myqos"\n'
    )
    result = run_install(root, "--account", "X", "--no-setup")
    assert result.returncode == 0, result.stderr
    assert (root / "site" / "local.env").read_text() == 'SLURM_ACCOUNT="X"\nSLURM_QOS="myqos"\n'
    assert "account: X\n" in (root / ".local" / "configs.leonardo.yaml").read_text()


def test_sbatchman_version_comes_from_the_environment(tmp_path):
    root = make_umbrella(tmp_path)
    result = run_install(
        root, "--account", "TESTACCT", "--no-setup", env_extra={"SBATCHMAN_VERSION": "9.9.9"}
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

    result = run_install(root, "--account", "TESTACCT", "--no-setup")

    assert result.returncode == 0, result.stderr
    assert (root / "benchmarks" / "blink" / "SbatchMan").is_dir()
    assert (root / "benchmarks" / "qe" / "SbatchMan").is_dir()
    assert not (root / "benchmarks" / "__pycache__" / "SbatchMan").exists()
    assert not (root / "benchmarks" / "notes" / "SbatchMan").exists()
    log_lines = (tmp_path / "sbatchman.log").read_text().splitlines()
    assert sorted(Path(line).name for line in log_lines) == ["blink", "qe"]
