"""Tests the shipped benchmarks and the configs template. Standard library, pytest and PyYAML.

The real validation runs the pinned CRAB code (`CRAB/src` of this repository, put first on
`sys.path`) on the config.json each jobs file writes, with the wrappers of `crab-wrappers/`.
"""

import importlib
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from forbidden import forbidden_or_skip

REPO = Path(__file__).resolve().parent.parent
BENCHMARKS = REPO / "benchmarks"
TEMPLATE = REPO / "configs" / "leonardo.yaml"

JOBS_FILES = {
    "blink": ["smoke.yaml", "blink-noise.yaml", "a2a-vs-a2a.yaml", "a2a-vs-incast.yaml"],
    "qe": ["qe-alone.yaml", "qe-noise.yaml"],
}
JOBS_PATHS = [BENCHMARKS / folder / name for folder, names in JOBS_FILES.items() for name in names]
QE_PATHS = [BENCHMARKS / "qe" / name for name in JOBS_FILES["qe"]]
READMES = [
    BENCHMARKS / "blink" / "README.md",
    BENCHMARKS / "qe" / "README.md",
    BENCHMARKS / "qe" / "qe" / "README.md",
]
QE_INPUTS = [
    BENCHMARKS / "qe" / "qe" / "si-scf.in",
    BENCHMARKS / "qe" / "qe" / "Si.pz-vbc.UPF",
]

CONFIGS_PATH = "../../.local/configs.leonardo.yaml"
TOKENS = {"<YOUR_ACCOUNT>", "<SLURM_PARTITION>", "<SLURM_QOS>", "<CRAB_DIR>"}
# A quoted heredoc (<<'JSON') keeps the text as it is; the QE files use an unquoted one (<<JSON)
# so the shell expands $SBATCHMAN_WD in the input paths.
HEREDOC = re.compile(r"<<'?JSON'?\n(.*?)\nJSON\n", re.DOTALL)


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def _combinations(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Every assignment of the file's SbatchMan variables (their Cartesian product)."""
    variables = doc["variables"]
    names = list(variables)
    return [
        dict(zip(names, values, strict=True)) for values in itertools.product(*variables.values())
    ]


def _heredoc(job: dict[str, Any]) -> str:
    match = HEREDOC.search(job["preprocess"])
    assert match, f"job {job.get('tag')}: no config.json heredoc in preprocess"
    return match.group(1)


def _all_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and "SbatchMan" not in p.parts]


def _fill(text: str) -> str:
    """The four replacements install.sh makes, with test values."""
    values = {
        "<YOUR_ACCOUNT>": "testaccount",
        "<SLURM_PARTITION>": "testpart",
        "<SLURM_QOS>": "testqos",
        "<CRAB_DIR>": "/opt/umbrella/CRAB",
    }
    for token, value in values.items():
        text = text.replace(token, value)
    return text


@pytest.fixture(scope="module")
def pinned_crab() -> Any:
    """The CRAB of this repository's submodule, imported before any other checkout."""
    src = str(REPO / "CRAB" / "src")
    if src in sys.path:
        sys.path.remove(src)
    sys.path.insert(0, src)
    for name in [n for n in sys.modules if n == "crab" or n.startswith("crab.")]:
        del sys.modules[name]
    importlib.invalidate_caches()
    validate = importlib.import_module("crab.cli.validate")
    wrapper_paths = importlib.import_module("crab.core.wrapper_paths")
    crab_file = Path(importlib.import_module("crab").__file__ or "").resolve()
    assert (REPO / "CRAB" / "src") in crab_file.parents, crab_file
    return validate.check_config_problems, wrapper_paths.wrapper_path_problem


def test_the_expected_files_exist() -> None:
    for path in [TEMPLATE, *JOBS_PATHS, *READMES, *QE_INPUTS]:
        assert path.is_file(), path


@pytest.mark.parametrize("path", JOBS_PATHS, ids=lambda p: p.name)
def test_every_jobs_file_loads_and_points_at_the_filled_configs(path: Path) -> None:
    doc = _load(path)

    assert doc["configs"] == CONFIGS_PATH
    assert doc["variables"]["nodes"]
    assert len(doc["jobs"]) == 1


@pytest.mark.parametrize("path", [*JOBS_PATHS, *READMES], ids=lambda p: p.name)
def test_no_unfilled_token_in_a_jobs_file_or_readme(path: Path) -> None:
    text = path.read_text()

    assert "<YOUR_ACCOUNT>" not in text
    assert "<CRAB_DIR>" not in text


def test_no_real_account_host_or_user_under_benchmarks_or_configs() -> None:
    words = forbidden_or_skip()
    files = [*_all_files(BENCHMARKS), *_all_files(REPO / "configs")]
    assert len(files) > 10
    for path in files:
        text = path.read_text(errors="replace")
        for word in words:
            assert word not in text, f"{word!r} in {path}"


def test_the_template_has_exactly_the_four_tokens() -> None:
    text = TEMPLATE.read_text()

    assert set(re.findall(r"<[A-Z_]+>", text)) == TOKENS


def test_the_filled_template_is_the_leonardo_cluster_with_both_config_names() -> None:
    doc = yaml.safe_load(_fill(TEMPLATE.read_text()))

    assert not re.search(r"<[A-Z_]+>", _fill(TEMPLATE.read_text()))
    assert list(doc["leonardo"]) == ["scheduler", "default_conf", "configs"]
    assert doc["leonardo"]["default_conf"]["account"] == "testaccount"
    assert doc["leonardo"]["default_conf"]["partition"] == "testpart"
    assert doc["leonardo"]["default_conf"]["qos"] == "testqos"
    names = [config["name"] for config in doc["leonardo"]["configs"]]
    assert names == ["crab_run_{nodes}", "crab_qe_{nodes}"]
    env = doc["leonardo"]["default_conf"]["env"]
    assert "CRAB_ROOT=/opt/umbrella/CRAB" in env
    assert "CRAB_PATH_WRAPPERS=/opt/umbrella/CRAB/wrappers" in env
    assert any(
        entry.startswith("CRAB_PATH_WRAPPERS=") and entry.endswith("/CRAB/wrappers")
        for entry in env
    )
    # The node counts of every jobs file are covered by the template's `nodes` list.
    for path in JOBS_PATHS:
        for values in _combinations(_load(path)):
            assert values["nodes"] in doc["variables"]["nodes"], path.name


@pytest.mark.parametrize("path", QE_PATHS, ids=lambda p: p.name)
def test_the_qe_files_read_input_and_pseudos_from_this_folder(path: Path) -> None:
    job = _load(path)["jobs"][0]
    text = path.read_text()

    # The heredoc is unquoted so the shell expands $SBATCHMAN_WD: no other `$` or backtick may be in it.
    assert "<<JSON\n" in job["preprocess"]
    assert "<<'JSON'" not in job["preprocess"]
    assert "$CRAB_ROOT/examples" not in text
    assert "$SBATCHMAN_WD/qe/si-scf.in" in _heredoc(job)
    assert not re.search(r"[$`]", _heredoc(job).replace("$SBATCHMAN_WD", ""))


@pytest.mark.parametrize("path", JOBS_PATHS, ids=lambda p: p.name)
def test_every_embedded_config_passes_crab_validation(
    path: Path, pinned_crab: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    check_config_problems, wrapper_path_problem = pinned_crab
    monkeypatch.setenv("CRAB_PATH_WRAPPERS", str(REPO / "crab-wrappers"))
    monkeypatch.setenv("CRAB_ROOT", str(REPO / "CRAB"))
    doc = _load(path)
    job = doc["jobs"][0]
    qe_dir = BENCHMARKS / "qe"
    checked = 0

    for values in _combinations(doc):
        text = _heredoc(job)
        for name, value in values.items():
            text = text.replace("{" + name + "}", str(value))
        text = text.replace("$SBATCHMAN_WD", str(qe_dir)).replace("$CRAB_ROOT", str(REPO / "CRAB"))
        assert not re.search(r"\{[a-z_]+\}", text)
        config = json.loads(text)

        errors, _warnings = check_config_problems(config)

        assert errors == [], (path.name, values)
        for experiment in config["experiments"].values():
            for app in experiment["apps"].values():
                assert wrapper_path_problem(app["path"]) is None, app["path"]
                if "input_file" in app:
                    assert Path(app["input_file"]) == qe_dir / "qe" / "si-scf.in"
                    assert Path(app["input_file"]).is_file()
                    assert Path(app["pseudo_dir"]) == qe_dir / "qe"
                    assert list(Path(app["pseudo_dir"]).glob("*.UPF"))
        checked += 1

    assert checked == len(_combinations(doc)) >= 1


def test_no_set_cluster_name_and_no_checkout_example_path() -> None:
    """env.sh exports SBATCHMAN_CLUSTER_NAME, and the QE input comes from benchmarks/qe/qe."""
    for path in [*_all_files(BENCHMARKS), *_all_files(REPO / "configs")]:
        assert "set-cluster-name" not in path.read_text(errors="replace"), path
    for path in JOBS_PATHS:
        assert "$CRAB_ROOT/examples" not in path.read_text(), path
