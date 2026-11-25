"""Locks the two workflows: ci.yml runs on Linux only, macos.yml runs the laptop installer on its own.

Standard library and PyYAML only, no network.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

MACOS_PATHS = {
    "install.sh",
    "tests/test_bash32.py",
    "tests/test_install.py",
    "tests/test_laptop.py",
    "tests/test_env.py",
    "CRAB",
    "crab-wrappers",
    ".github/workflows/macos.yml",
}


def load(name: str) -> dict:
    """The parsed workflow. PyYAML reads the key `on` as the boolean True: put it back."""
    workflow = yaml.safe_load((WORKFLOWS / name).read_text())
    if True in workflow:
        workflow["on"] = workflow.pop(True)
    return workflow


def run_text(workflow: dict) -> str:
    """Every `run` script of the first job, joined."""
    steps = next(iter(workflow["jobs"].values()))["steps"]
    return "\n".join(step["run"] for step in steps if "run" in step)


def test_ci_runs_on_linux_only_and_is_blocking():
    text = (WORKFLOWS / "ci.yml").read_text()
    assert "macos" not in text.lower()
    assert "continue-on-error" not in text
    matrix = load("ci.yml")["jobs"]["tests"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest"]
    assert matrix["python-version"] == ["3.11", "3.12"]


def test_macos_workflow_runs_only_on_main_pull_requests_and_by_hand_for_the_install_files():
    workflow = load("macos.yml")
    triggers = workflow["on"]
    assert set(triggers) == {"push", "pull_request", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["main"]
    assert set(triggers["push"]["paths"]) == MACOS_PATHS
    assert set(triggers["pull_request"]["paths"]) == MACOS_PATHS


def test_macos_workflow_is_one_job_on_macos_with_python_3_12_and_a_concurrency_group():
    workflow = load("macos.yml")
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert len(workflow["jobs"]) == 1
    job = next(iter(workflow["jobs"].values()))
    assert job["runs-on"] == "macos-latest"
    assert "strategy" not in job
    setup = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/setup-python")]
    assert [str(step["with"]["python-version"]) for step in setup] == ["3.12"]
    checkout = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout")]
    assert checkout[0]["with"]["submodules"] == "recursive"


def test_macos_workflow_proves_bash_3_2_and_runs_the_real_laptop_installer_twice():
    text = run_text(load("macos.yml"))
    assert "/bin/bash" in text and "BASH_VERSINFO[0]" in text and "-eq 3" in text
    assert "pip install pytest pyyaml" in text
    assert "UMBRELLA_TEST_BASH=/bin/bash" in text
    for name in ("test_install.py", "test_laptop.py", "test_bash32.py", "test_env.py"):
        assert f"tests/{name}" in text
    assert text.count("/bin/bash ./install.sh --role laptop") == 2
    assert text.count("install.sh: all checks passed") >= 2
    assert "zsh -c" in text and "command -v crab" in text and "CRAB/.venv/bin" in text
    assert "rsync --version" in text and "rsync -zvrh --update" in text


def test_installer_job_starts_at_the_python_the_installer_accepts():
    """SbatchMan imports tomllib (Python 3.11+), so the installer, its docs and the job share one floor."""
    matrix = load("ci.yml")["jobs"]["installer"]["strategy"]["matrix"]
    assert matrix["python-version"] == ["3.11", "3.12"]
    assert "sys.version_info >= (3, 11)" in (ROOT / "install.sh").read_text()
    assert "Python 3.11 or newer" in (ROOT / "docs" / "install.md").read_text()
