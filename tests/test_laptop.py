"""Tests the help block that the laptop role of install.sh prints. Standard library and pytest only.

Reuses the tmp-umbrella fixture of test_install.py. HOME points to an empty tmp folder: the
script must leave it empty (the sbatchman config is printed, never written).
"""

import tomllib
from pathlib import Path

import pytest
from test_install import make_umbrella, run_install

START = "--- remotes-config.toml ---"
END = "--- end ---"
FLAGS = ("--login-host", "login.example.org", "--user", "alice", "--remote-dir", "~/umb")


def laptop(tmp_path: Path, *args: str, root: Path | None = None):
    """Runs install.sh with HOME set to an empty tmp folder; returns (result, root, home)."""
    root = root or make_umbrella(tmp_path)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    result = run_install(root, *args, env_extra={"HOME": str(home)})
    return result, root, home


def toml_block(stdout: str) -> dict:
    lines = stdout.splitlines()
    assert lines.count(START) == 1 and lines.count(END) == 1
    body = lines[lines.index(START) + 1 : lines.index(END)]
    return tomllib.loads("\n".join(body))


def test_profile_lines_carry_the_given_values(tmp_path):
    result, _, _ = laptop(tmp_path, "--role", "laptop", *FLAGS)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert "== crab web: add the cluster" in lines
    for expected in (
        "Name: leonardo",
        "Transport: ssh",
        "Host: login.example.org",
        "User: alice",
        "Port: 22",
        "Auth: agent (ssh-agent / cert)",
        "Host key: insecure (rotating login nodes)",
        "Install dir: ~/umb",
        "Crab command: (leave empty)",
        "Preset: (leave empty)",
    ):
        assert any(line.strip() == expected for line in lines), expected
    assert "<login-host>" not in result.stdout
    assert "<your-user>" not in result.stdout
    assert "Install CRAB" in result.stdout
    assert "ssh agent" in result.stdout


def test_toml_block_parses_and_lists_every_benchmark(tmp_path):
    result, root, _ = laptop(tmp_path, "--role", "laptop", *FLAGS)
    assert result.returncode == 0, result.stderr
    assert (
        "== sbatchman fetch: results to this laptop"
        in result.stdout.splitlines()
    )
    assert (
        "Save this as ~/.config/sbatchman/remotes-config.toml (merge by hand if the file exists):"
        in result.stdout.splitlines()
    )
    data = toml_block(result.stdout)
    assert data["global"]["transfer_backend"] == "rsync"
    assert data["global"]["fetch_excludes"] == ["scratch"]
    assert data["global"]["local_base"] == f"{root}/benchmarks"
    (cluster,) = data["clusters"]
    assert cluster["name"] == "leonardo"
    assert cluster["host"] == "login.example.org"
    assert cluster["user"] == "alice"
    assert cluster["port"] == 22
    assert cluster["fetch_dirs"] == [
        {
            "remote": "~/umb/benchmarks/blink/SbatchMan",
            "local": f"{root}/benchmarks/blink/SbatchMan",
        },
        {
            "remote": "~/umb/benchmarks/qe/SbatchMan",
            "local": f"{root}/benchmarks/qe/SbatchMan",
        },
    ]


def test_start_the_tools_section(tmp_path):
    result, _, _ = laptop(tmp_path, "--role", "laptop", *FLAGS)
    lines = result.stdout.splitlines()
    at = lines.index("== start the tools")
    assert lines[at + 1 :][:3] == [
        "source env.sh",
        "crab web          # dashboard, http://127.0.0.1:8899",
        "cd benchmarks/blink && sbatchman fetch && sbatchman visualize"
        "   # plots, http://127.0.0.1:8765",
    ]


def test_help_block_comes_after_the_finish_line_in_order(tmp_path):
    result, _, _ = laptop(tmp_path, "--role", "laptop", *FLAGS)
    lines = result.stdout.splitlines()
    finish = lines.index("install.sh finished: role laptop")
    assert lines[finish + 1] == "Next: source env.sh"
    heads = [
        lines.index("== crab web: add the cluster"),
        lines.index("== sbatchman fetch: results to this laptop"),
        lines.index("== start the tools"),
    ]
    assert finish < heads[0] < heads[1] < heads[2]


def test_placeholders_appear_without_the_flags_and_toml_still_parses(tmp_path):
    result, root, _ = laptop(tmp_path, "--role", "laptop")
    assert result.returncode == 0, result.stderr
    lines = [line.strip() for line in result.stdout.splitlines()]
    assert "Host: <login-host>" in lines
    assert "User: <your-user>" in lines
    assert "Install dir: <umbrella-folder-on-the-cluster>" in lines
    data = toml_block(result.stdout)
    (cluster,) = data["clusters"]
    assert cluster["host"] == "<login-host>"
    assert cluster["user"] == "<your-user>"
    assert cluster["fetch_dirs"][0]["remote"] == (
        "<umbrella-folder-on-the-cluster>/benchmarks/blink/SbatchMan"
    )


def test_home_stays_empty(tmp_path):
    result, _, home = laptop(tmp_path, "--role", "laptop", *FLAGS)
    assert result.returncode == 0, result.stderr
    assert list(home.rglob("*")) == []
    assert not (home / ".config").exists()


def test_dry_run_prints_the_block_and_writes_nothing(tmp_path):
    root = make_umbrella(tmp_path)
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    result, _, home = laptop(tmp_path, "--role", "laptop", "--dry-run", *FLAGS, root=root)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    finish = lines.index("install.sh finished: role laptop (dry run, nothing was changed)")
    assert finish < lines.index("== crab web: add the cluster")
    assert "== start the tools" in lines
    assert toml_block(result.stdout)["clusters"][0]["host"] == "login.example.org"
    assert sorted(str(p.relative_to(root)) for p in root.rglob("*")) == before
    assert list(home.rglob("*")) == []


def test_cluster_role_prints_no_laptop_help(tmp_path):
    result, _, _ = laptop(tmp_path, "--account", "TESTACCT", "--no-setup")
    assert result.returncode == 0, result.stderr
    assert "== crab web" not in result.stdout
    assert START not in result.stdout
    assert END not in result.stdout


@pytest.mark.parametrize(
    "flag",
    [
        ("--login-host", "login.example.org"),
        ("--user", "alice"),
        ("--remote-dir", "~/umb"),
    ],
)
def test_the_flags_are_refused_with_the_cluster_role(tmp_path, flag):
    result, _, _ = laptop(tmp_path, "--role", "cluster", "--account", "T", "--no-setup", *flag)
    assert result.returncode == 2
    assert "Usage:" in result.stderr


@pytest.mark.parametrize(
    "flag",
    [
        ("--login-host", "a b"),
        ("--user", "x;y"),
        ("--remote-dir", "$(x)"),
    ],
)
def test_invalid_values_exit_2(tmp_path, flag):
    result, _, home = laptop(tmp_path, "--role", "laptop", *flag)
    assert result.returncode == 2
    assert len([line for line in result.stderr.splitlines() if "install.sh:" in line]) == 1
    assert "== crab web" not in result.stdout
    assert list(home.rglob("*")) == []


def test_site_local_env_supplies_values_and_the_flags_win(tmp_path):
    root = make_umbrella(tmp_path)
    (root / "site" / "local.env").write_text(
        'SITE_LOGIN_HOST="from.file"\nSITE_USER="fileuser"\nSITE_REMOTE_DIR="/file/dir"\n'
    )
    from_file, _, _ = laptop(tmp_path, "--role", "laptop", root=root)
    assert from_file.returncode == 0, from_file.stderr
    lines = [line.strip() for line in from_file.stdout.splitlines()]
    assert "Host: from.file" in lines
    assert "User: fileuser" in lines
    assert "Install dir: /file/dir" in lines
    flagged, _, _ = laptop(tmp_path, "--role", "laptop", "--login-host", "flag.example", root=root)
    lines = [line.strip() for line in flagged.stdout.splitlines()]
    assert "Host: flag.example" in lines
    assert "User: fileuser" in lines
    # The values are never written into a file: local.env keeps its three lines.
    assert (root / "site" / "local.env").read_text().count("\n") == 3


def test_cluster_name_comes_from_the_site_env(tmp_path):
    root = make_umbrella(tmp_path)
    site = root / "site" / "leonardo.env"
    site.write_text(site.read_text() + 'SBATCHMAN_CLUSTER_NAME="othercluster"\n')
    result, _, _ = laptop(tmp_path, "--role", "laptop", root=root)
    assert "Name: othercluster" in [line.strip() for line in result.stdout.splitlines()]
    assert toml_block(result.stdout)["clusters"][0]["name"] == "othercluster"


def test_real_site_env_mentions_the_optional_variables():
    text = (Path(__file__).resolve().parent.parent / "site" / "leonardo.env").read_text()
    for name in ("SITE_LOGIN_HOST", "SITE_USER", "SITE_REMOTE_DIR"):
        assert name in text
        assert f'{name}="' not in text
