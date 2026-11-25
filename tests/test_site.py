"""Locks the MkDocs site: config, nav, doc dependencies and the Pages workflow.

Standard library and PyYAML only, no network, no mkdocs import. The strict build runs in CI.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"
WORKFLOWS = ROOT / ".github" / "workflows"

SECTIONS = [
    "Start here",
    "Install",
    "Run a benchmark",
    "Add your benchmark",
    "Results",
    "Advanced",
    "Help",
]


def load_config() -> dict:
    """mkdocs.yml, read with the safe loader: the file must use no `!!python/name:` tag."""
    return yaml.safe_load(MKDOCS.read_text())


def load_workflow(name: str) -> dict:
    """The parsed workflow. PyYAML reads the key `on` as the boolean True: put it back."""
    workflow = yaml.safe_load((WORKFLOWS / name).read_text())
    if True in workflow:
        workflow["on"] = workflow.pop(True)
    return workflow


def nav_files(entries) -> list[str]:
    """Every page file named in the nav, in order (entries nest as lists and one-key dicts)."""
    files = []
    for entry in entries:
        if isinstance(entry, str):
            files.append(entry)
        elif isinstance(entry, dict):
            for value in entry.values():
                files.extend(nav_files(value) if isinstance(value, list) else [value])
    return files


def step_runs(job: dict) -> list[str]:
    return [step["run"] for step in job["steps"] if "run" in step]


def test_mkdocs_config_is_material_with_no_author_and_no_email():
    text = MKDOCS.read_text()
    config = load_config()
    assert config["theme"]["name"] == "material"
    assert "site_author" not in config
    assert "@" not in text
    # Decided at the public flip or later: no address, no edit link, no hidden warnings, no logo.
    for key in ("site_url", "edit_uri", "validation", "strict"):
        assert key not in config, key
    assert "logo" not in config["theme"]
    assert "navigation.instant" not in config["theme"]["features"]


def test_the_requirements_file_is_not_published():
    assert load_config()["exclude_docs"].strip() == "requirements.txt"


def test_nav_names_every_docs_page_once_and_each_file_exists():
    files = nav_files(load_config()["nav"])
    for name in files:
        assert (DOCS / name).is_file(), name
    pages = sorted(path.name for path in DOCS.glob("*.md"))
    assert sorted(files) == pages


def test_nav_has_the_seven_sections_in_order():
    titles = [next(iter(entry)) for entry in load_config()["nav"]]
    assert titles == SECTIONS


def test_docs_requirements_bound_mkdocs_and_the_material_theme():
    lines = [
        line.strip()
        for line in (DOCS / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for package in ("mkdocs", "mkdocs-material"):
        found = [line for line in lines if line.startswith(f"{package}>=")]
        assert len(found) == 1, package
        assert "<" in found[0], f"{package} has no upper bound"


def test_the_site_builds_into_an_ignored_folder_that_is_not_the_tracked_site_folder():
    # `site/` holds the tracked per-cluster files (site/leonardo.env); a build empties its folder.
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert load_config()["site_dir"] == "_site"
    assert "_site/" in lines
    assert "site/" not in lines


def test_pages_workflow_is_skipped_while_the_repo_is_private():
    workflow = load_workflow("pages.yml")
    triggers = workflow["on"]
    assert "workflow_dispatch" in triggers
    assert "pull_request" not in triggers
    assert workflow["permissions"]["pages"] == "write"
    assert workflow["permissions"]["id-token"] == "write"
    assert "github.event.repository.private" in workflow["jobs"]["deploy"]["if"]
    upload = next(
        step for step in workflow["jobs"]["deploy"]["steps"] if "upload-pages-artifact" in step.get("uses", "")
    )
    assert upload["with"]["path"] == load_config()["site_dir"]


def test_ci_builds_the_site_strictly_after_installing_the_docs_requirements():
    jobs = load_workflow("ci.yml")["jobs"]
    builds = [
        runs
        for runs in (step_runs(job) for job in jobs.values())
        if any("mkdocs build --strict" in run for run in runs)
    ]
    assert len(builds) == 1
    runs = builds[0]
    install = next(i for i, run in enumerate(runs) if "pip install -r docs/requirements.txt" in run)
    build = next(i for i, run in enumerate(runs) if "mkdocs build --strict" in run)
    assert install < build
