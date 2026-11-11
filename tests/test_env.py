"""Tests the env.sh that install.sh writes. Standard library and pytest only.

Reuses the tmp-umbrella fixture of test_install.py; the venv stub gets an activate script.
"""

import shutil
import subprocess
from pathlib import Path

from test_install import _write, make_umbrella, run_install

CORE_SH_WITH_ACTIVATE = """\
mkdir -p .venv/bin
cp stub/python stub/pip stub/crab .venv/bin/
cp stub/activate .venv/bin/activate
"""

STUB_ACTIVATE = """\
VIRTUAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd -P)"
export VIRTUAL_ENV
PATH="$VIRTUAL_ENV/bin:$PATH"
export PATH
"""

PROBE = (
    'echo "PP=[${PYTHONPATH-unset}] PH=[${PYTHONHOME-unset}] '
    'NAME=[${SBATCHMAN_CLUSTER_NAME-unset}] WR=[$CRAB_PATH_WRAPPERS] '
    'PORT=[${CRAB_WEB_PORT-unset}]"'
)


def make_env_umbrella(tmp_path: Path) -> Path:
    root = make_umbrella(tmp_path)
    _write(root / "CRAB" / "stub" / "core.sh", CORE_SH_WITH_ACTIVATE)
    _write(root / "CRAB" / "stub" / "activate", STUB_ACTIVATE)
    return root


def install_cluster(root: Path) -> subprocess.CompletedProcess:
    result = run_install(root, "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    return result


def source_env(
    shell: str,
    env_sh: Path,
    cwd: Path,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    env = {
        "HOME": str(cwd),
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": "/junk",
        "PYTHONHOME": "/junk2",
    }
    env.update(extra_env or {})
    args = ["env", "-i", *[f"{k}={v}" for k, v in env.items()]]
    return subprocess.run(
        [*args, shell, "-c", f". {env_sh}; {PROBE}"],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


def test_env_sh_is_written_without_absolute_path_and_is_stable(tmp_path):
    root = make_env_umbrella(tmp_path)
    first = install_cluster(root)
    env_sh = root / "env.sh"
    assert env_sh.is_file()
    assert f"+ write {env_sh}" in first.stdout
    text = env_sh.read_text()
    assert str(root) not in text
    assert str(tmp_path) not in text
    before = env_sh.read_bytes()
    second = install_cluster(root)
    assert env_sh.read_bytes() == before
    assert "env.sh" not in second.stdout.replace("Next: source env.sh", "")
    assert "+ write" not in second.stdout


def test_sourcing_in_a_bare_shell_activates_the_venv_and_cleans_python_vars(tmp_path):
    root = make_env_umbrella(tmp_path)
    install_cluster(root)
    result = source_env("bash", root / "env.sh", tmp_path)
    assert result.returncode == 0, result.stderr
    venv_bin = root / "CRAB" / ".venv" / "bin"
    lines = result.stdout.splitlines()
    assert f"crab:      {venv_bin}/crab" in lines
    assert f"sbatchman: {venv_bin}/sbatchman" in lines
    assert (
        f"PP=[unset] PH=[unset] NAME=[leonardo] WR=[{root}/crab-wrappers] PORT=[unset]" in lines
    )


def test_cluster_name_comes_from_the_site_env(tmp_path):
    root = make_env_umbrella(tmp_path)
    site = root / "site" / "leonardo.env"
    site.write_text(site.read_text() + 'SBATCHMAN_CLUSTER_NAME="othercluster"\n')
    install_cluster(root)
    assert 'export SBATCHMAN_CLUSTER_NAME="othercluster"' in (root / "env.sh").read_text()


def test_real_site_env_declares_the_cluster_name():
    repo = Path(__file__).resolve().parent.parent
    assert 'SBATCHMAN_CLUSTER_NAME="leonardo"' in (repo / "site" / "leonardo.env").read_text()


def test_laptop_role_sets_the_dashboard_port_and_no_cluster_name(tmp_path):
    root = make_env_umbrella(tmp_path)
    result = run_install(root, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    env_sh = root / "env.sh"
    assert "SBATCHMAN_CLUSTER_NAME" not in env_sh.read_text()
    out = source_env("bash", env_sh, tmp_path).stdout
    assert "NAME=[unset]" in out
    assert "PORT=[8899]" in out
    kept = source_env("bash", env_sh, tmp_path, {"CRAB_WEB_PORT": "9000"}).stdout
    assert "PORT=[9000]" in kept


def test_copied_umbrella_finds_its_own_folder_from_any_cwd(tmp_path):
    root = make_env_umbrella(tmp_path)
    install_cluster(root)
    new_parent = tmp_path / "moved"
    new_parent.mkdir()
    new_root = (new_parent / "copy").resolve()
    shutil.copytree(root, new_root, symlinks=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = source_env("bash", new_root / "env.sh", elsewhere)
    assert result.returncode == 0, result.stderr
    venv_bin = new_root / "CRAB" / ".venv" / "bin"
    lines = result.stdout.splitlines()
    assert f"crab:      {venv_bin}/crab" in lines
    assert f"sbatchman: {venv_bin}/sbatchman" in lines
    assert any(f"WR=[{new_root}/crab-wrappers]" in line for line in lines)
    assert str(root) + "/" not in result.stdout


def test_sourcing_works_when_the_caller_uses_set_u(tmp_path):
    root = make_env_umbrella(tmp_path)
    install_cluster(root)
    env = ["env", "-i", f"HOME={tmp_path}", "PATH=/usr/bin:/bin"]
    result = subprocess.run(
        [*env, "bash", "-c", f"set -u; . {root / 'env.sh'}; {PROBE}"],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "NAME=[leonardo]" in result.stdout


def test_zsh_sources_it_like_bash(tmp_path):
    root = make_env_umbrella(tmp_path)
    install_cluster(root)
    env_sh = root / "env.sh"
    zsh = shutil.which("zsh")
    if zsh is None:
        # No zsh here: check that the text only uses constructs that resolve under zsh.
        text = env_sh.read_text()
        assert '"${BASH_SOURCE[0]:-$0}"' in text
        assert "readlink -f" not in text
        return
    result = source_env(zsh, env_sh, tmp_path)
    assert result.returncode == 0, result.stderr
    venv_bin = root / "CRAB" / ".venv" / "bin"
    lines = result.stdout.splitlines()
    assert f"crab:      {venv_bin}/crab" in lines
    assert f"sbatchman: {venv_bin}/sbatchman" in lines
    assert f"PP=[unset] PH=[unset] NAME=[leonardo] WR=[{root}/crab-wrappers] PORT=[unset]" in lines


def test_dry_run_lists_the_env_write_and_creates_no_file(tmp_path):
    root = make_env_umbrella(tmp_path)
    result = run_install(root, "--dry-run", "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    assert f"+ write {root / 'env.sh'}" in result.stdout.splitlines()
    assert not (root / "env.sh").exists()
    assert "Next: source env.sh" not in result.stdout


def test_real_run_ends_with_the_next_line(tmp_path):
    root = make_env_umbrella(tmp_path)
    result = install_cluster(root)
    lines = result.stdout.splitlines()
    assert lines[-2] == "install.sh finished: role cluster"
    assert lines[-1] == "Next: source env.sh"
