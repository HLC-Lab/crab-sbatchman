"""Tests the starter workspaces for `sbatchman visualize` (benchmarks/blink).

SbatchMan loads plots.json from the working directory and fills one sqlite table per key the
parser returns. The tests rebuild that database in memory from the real (trimmed) Leonardo
results in tests/fixtures/results/ and run every tab's SQL against it. Standard library and pytest.
"""

import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
BENCHMARKS = REPO / "benchmarks"
RESULTS = Path(__file__).resolve().parent / "fixtures" / "results" / "leonardo"

# Verified against sbatchman 2.0.4: GET /api/plot_types, and the register_plot(...) calls in
# sbatchman/visualize/utils/plots.py.
PLOT_TYPES = {"line", "bar", "scatter", "histogram", "box", "violin", "heatmap", "pie"}
STATE_CASE = "CASE WHEN experiment LIKE '%noise' THEN 'noise' ELSE 'baseline' END"

# folder -> the job folders (tag, config, job id, variables) its fixtures hold
JOBS = {
    "blink": [
        (
            RESULTS / "crab_run_4" / "blink-noise-4n-1048576B" / "20261110_104331",
            "blink-noise-4n-1048576B",
            "crab_run_4",
            64054665,
            {"nodes": 4, "msgsize": 1048576},
        ),
    ],
}


class RealJob:
    def __init__(self, base: Path, tag: str, config: str, job_id: int, variables: dict) -> None:
        self.status = "COMPLETED"
        self.tag = tag
        self.config_name = config
        self.job_id = job_id
        self.variables = variables
        self._base = base

    def get_job_base_path(self) -> Path:
        return self._base


def _parse() -> Any:
    spec = importlib.util.spec_from_file_location("sbatchman_parser", BENCHMARKS / "parser.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse


def _sql_type(value: Any) -> str:
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def _database(folder: str) -> sqlite3.Connection:
    """In-memory copy of what `sbatchman visualize` builds: one table per parse key."""
    parse = _parse()
    tables: dict[str, list[dict[str, Any]]] = {}
    for base, tag, config, job_id, variables in JOBS[folder]:
        for name, rows in (parse(RealJob(base, tag, config, job_id, variables)) or {}).items():
            tables.setdefault(name, []).extend(rows)
    connection = sqlite3.connect(":memory:")
    for name, rows in tables.items():
        columns = ", ".join(f'"{key}" {_sql_type(value)}' for key, value in rows[0].items())
        connection.execute(f"CREATE TABLE {name} ({columns})")
        marks = ", ".join("?" for _ in rows[0])
        connection.executemany(
            f"INSERT INTO {name} VALUES ({marks})", [tuple(r.values()) for r in rows]
        )
    return connection


def _workspace(folder: str) -> dict[str, Any]:
    return json.loads((BENCHMARKS / folder / "plots.json").read_text())


def _tabs() -> list[tuple[str, int]]:
    return [(folder, i) for folder in JOBS for i in range(len(_workspace(folder)["tabs"]))]


def _ids(pairs: list[tuple[str, int]]) -> list[str]:
    return [f"{folder}-{i}" for folder, i in pairs]


def _run(folder: str, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    cursor = _database(folder).execute(sql)
    return [column[0] for column in cursor.description], cursor.fetchall()


@pytest.mark.parametrize("folder", list(JOBS))
def test_workspace_has_the_visualize_shape(folder: str) -> None:
    workspace = _workspace(folder)

    assert workspace["version"] == 3
    assert workspace["activeTabIndex"] == 0
    assert workspace["style"] == {}
    assert workspace["script_paths"] == []
    assert len(workspace["tabs"]) >= 2


@pytest.mark.parametrize(("folder", "index"), _tabs(), ids=_ids(_tabs()))
def test_tab_is_a_complete_labelled_plot(folder: str, index: int) -> None:
    tab = _workspace(folder)["tabs"][index]

    assert tab["database"] == "data"
    assert tab["sql"].strip()
    assert tab["plotType"] in PLOT_TYPES
    for key in ("label", "chartTitle", "xLabel", "yLabel"):
        assert isinstance(tab[key], str) and tab[key].strip(), key
    assert isinstance(tab["x"], str) and tab["x"]
    assert isinstance(tab["y"], list) and tab["y"]
    assert isinstance(tab["group"], list)


@pytest.mark.parametrize(("folder", "index"), _tabs(), ids=_ids(_tabs()))
def test_tab_sql_runs_on_the_real_results(folder: str, index: int) -> None:
    tab = _workspace(folder)["tabs"][index]

    columns, rows = _run(folder, tab["sql"])

    assert len(rows) >= 1
    assert len(columns) == len(set(columns))


@pytest.mark.parametrize(("folder", "index"), _tabs(), ids=_ids(_tabs()))
def test_tab_columns_exist_in_the_query_result(folder: str, index: int) -> None:
    tab = _workspace(folder)["tabs"][index]

    columns, _ = _run(folder, tab["sql"])

    named = [tab["x"], *tab["y"], *tab["group"]]
    assert [name for name in named if name not in columns] == []


@pytest.mark.parametrize(("folder", "index"), _tabs(), ids=_ids(_tabs()))
def test_tab_plots_numbers_on_y(folder: str, index: int) -> None:
    tab = _workspace(folder)["tabs"][index]

    columns, rows = _run(folder, tab["sql"])

    for name in tab["y"]:
        values = [row[columns.index(name)] for row in rows]
        assert all(isinstance(v, int | float) for v in values), name


def test_state_expression_labels_blink_baseline_and_noise() -> None:
    connection = _database("blink")

    states = {v for (v,) in connection.execute(f"SELECT DISTINCT {STATE_CASE} FROM app_0")}

    assert states == {"baseline", "noise"}


@pytest.mark.parametrize("folder", list(JOBS))
def test_every_tab_uses_the_state_expression(folder: str) -> None:
    for tab in _workspace(folder)["tabs"]:
        assert STATE_CASE in tab["sql"], tab["label"]


def test_blink_baseline_vs_noise_tab_gives_both_states_in_milliseconds() -> None:
    tab = _workspace("blink")["tabs"][0]

    columns, rows = _run("blink", tab["sql"])

    by_state = {row[columns.index("state")]: row[columns.index(tab["y"][0])] for row in rows}
    assert set(by_state) == {"baseline", "noise"}
    # the real Avg-Duration is about 0.001 s: a millisecond value is about 1, never 0.001
    assert all(0.1 < value < 10 for value in by_state.values())
    assert tab["x"] == "msg_size"
    assert "state" in tab["group"]


def test_blink_per_repetition_tab_has_the_three_repetitions_for_each_state() -> None:
    tab = _workspace("blink")["tabs"][1]

    columns, rows = _run("blink", tab["sql"])

    pairs = {(row[columns.index("state")], row[columns.index("rep")]) for row in rows}
    assert pairs == {(s, r) for s in ("baseline", "noise") for r in ("r1", "r2", "r3")}
    assert tab["x"] == "rep"
    assert "state" in tab["group"]


def test_blink_baseline_vs_noise_tab_keeps_jobs_apart_by_tag() -> None:
    tab = _workspace("blink")["tabs"][0]
    select, _, rest = tab["sql"].partition(" FROM ")
    group_by = rest.split(" GROUP BY ", 1)[1].split(" ORDER BY ", 1)[0]

    assert "tag" in [part.strip() for part in select.split(",")]
    assert "tag" in [part.strip() for part in group_by.split(",")]
    assert "tag" in tab["group"]


def test_blink_baseline_vs_noise_tab_does_not_average_two_jobs_together() -> None:
    tab = _workspace("blink")["tabs"][0]
    connection = _database("blink")
    connection.execute("CREATE TABLE other AS SELECT * FROM app_0")
    connection.execute("UPDATE other SET tag = 'other-job', \"0_Avg-Duration_s\" = \"0_Avg-Duration_s\" * 100")
    connection.execute("INSERT INTO app_0 SELECT * FROM other")

    cursor = connection.execute(tab["sql"])
    columns = [c[0] for c in cursor.description]
    by_tag: dict[str, list[float]] = {}
    for row in cursor.fetchall():
        by_tag.setdefault(row[columns.index("tag")], []).append(row[columns.index("avg_duration_ms")])

    assert set(by_tag) == {"blink-noise-4n-1048576B", "other-job"}
    assert max(by_tag["blink-noise-4n-1048576B"]) < 10 < min(by_tag["other-job"])


def test_blink_per_repetition_tab_keeps_jobs_apart_by_tag() -> None:
    tab = _workspace("blink")["tabs"][1]
    select, _, rest = tab["sql"].partition(" FROM ")
    group_by = rest.split(" GROUP BY ", 1)[1].split(" ORDER BY ", 1)[0]

    assert "tag" in [part.strip() for part in select.split(",")]
    assert "tag" in [part.strip() for part in group_by.split(",")]
    assert "tag" in tab["group"]


def test_blink_per_repetition_tab_does_not_average_two_jobs_together() -> None:
    tab = _workspace("blink")["tabs"][1]
    connection = _database("blink")
    connection.execute("CREATE TABLE other AS SELECT * FROM app_0")
    connection.execute(
        "UPDATE other SET tag = 'other-job', \"0_Avg-Duration_s\" = \"0_Avg-Duration_s\" * 100"
    )
    connection.execute("INSERT INTO app_0 SELECT * FROM other")

    cursor = connection.execute(tab["sql"])
    columns = [c[0] for c in cursor.description]
    by_tag: dict[str, list[float]] = {}
    for row in cursor.fetchall():
        by_tag.setdefault(row[columns.index("tag")], []).append(
            row[columns.index("avg_duration_ms")]
        )

    assert set(by_tag) == {"blink-noise-4n-1048576B", "other-job"}
    assert max(by_tag["blink-noise-4n-1048576B"]) < 10 < min(by_tag["other-job"])
