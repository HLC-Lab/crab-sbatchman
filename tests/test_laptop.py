"""Tests what the laptop role of install.sh prints and leaves alone. Standard library and pytest only.

Reuses the tmp-umbrella fixture of test_install.py. HOME points to an empty tmp folder: the
script must leave it empty. The laptop role prints no help block: registering a cluster is
done in the dashboard, and the docs explain it.
"""

from pathlib import Path

from test_install import listing, make_umbrella, run_install


def laptop(tmp_path: Path, *args: str, root: Path | None = None):
    """Runs install.sh with HOME set to an empty tmp folder; returns (result, root, home)."""
    root = root or make_umbrella(tmp_path)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    result = run_install(root, *args, env_extra={"HOME": str(home)})
    return result, root, home


def test_laptop_run_ends_with_the_finish_and_next_lines_and_nothing_after(tmp_path):
    result, _, _ = laptop(tmp_path, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[-2:] == ["install.sh finished: role laptop", "Next: source env.sh"]


def test_laptop_run_prints_no_dashboard_or_fetch_help(tmp_path):
    result, _, _ = laptop(tmp_path, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    for gone in (
        "== crab web",
        "== sbatchman fetch",
        "== start the tools",
        "remotes-config.toml",
        "Add cluster",
        "Install CRAB",
        "<login-host>",
        "<your-user>",
        "<umbrella-folder-on-the-cluster>",
    ):
        assert gone not in out, gone


def test_laptop_dry_run_prints_no_help_and_writes_nothing(tmp_path):
    root = make_umbrella(tmp_path)
    before = listing(root)
    result, _, home = laptop(tmp_path, "--role", "laptop", "--dry-run", root=root)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[-1] == "install.sh finished: role laptop (dry run, nothing was changed)"
    assert "remotes-config.toml" not in result.stdout
    assert "== crab web" not in result.stdout
    assert listing(root) == before
    assert list(home.rglob("*")) == []


def test_home_stays_empty(tmp_path):
    result, _, home = laptop(tmp_path, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    assert list(home.rglob("*")) == []
    assert not (home / ".config").exists()


def test_cluster_role_prints_no_laptop_help(tmp_path):
    result, _, _ = laptop(tmp_path, "--account", "TESTACCT")
    assert result.returncode == 0, result.stderr
    assert "== crab web" not in result.stdout
    assert "remotes-config.toml" not in result.stdout


def test_laptop_env_sh_keeps_the_dashboard_port(tmp_path):
    result, root, _ = laptop(tmp_path, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    env_sh = (root / "env.sh").read_text()
    assert 'export CRAB_WEB_PORT="${CRAB_WEB_PORT:-8899}"' in env_sh


def test_real_site_env_no_longer_mentions_the_laptop_variables():
    text = (Path(__file__).resolve().parent.parent / "site" / "leonardo.env").read_text()
    for name in ("SITE_LOGIN_HOST", "SITE_USER", "SITE_REMOTE_DIR"):
        assert name not in text
