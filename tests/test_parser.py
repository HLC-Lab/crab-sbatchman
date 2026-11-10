"""Tests the generic SbatchMan parser (benchmarks/parser.py). Standard library and pytest.

The parser is not a package: SbatchMan loads it from the working directory, so the tests load it
by path. A duck-typed job stands in for the SbatchMan Job (only the fields the parser reads).
"""

import importlib.util
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
PARSER = REPO / "benchmarks" / "parser.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "parser" / "data_app_0.csv"

BLINK_COLUMNS = [
    "run_id",
    "msg_size",
    "0_Avg-Duration_s",
    "0_Min-Duration_s",
    "0_Max-Duration_s",
    "0_Median-Duration_s",
    "0_MainRank-Duration_s",
]
EXTRA_COLUMNS = ["app", "tag", "config", "job_id", "experiment"]


def _load_parser() -> Any:
    spec = importlib.util.spec_from_file_location("sbatchman_parser", PARSER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeJob:
    def __init__(
        self,
        base: Path,
        status: str = "COMPLETED",
        variables: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.tag = "a2a-smoke"
        self.config_name = "crab_run_2"
        self.job_id = 4242
        self.variables = variables
        self._base = base

    def get_job_base_path(self) -> Path:
        return self._base


@pytest.fixture
def parse() -> Any:
    return _load_parser().parse


def _put_fixture(folder: Path, name: str = "data_app_0.csv") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    shutil.copy(FIXTURE, target)
    return target


def test_completed_blink_job_gives_one_table_with_typed_columns(
    parse: Any, tmp_path: Path
) -> None:
    _put_fixture(tmp_path / "run")
    (tmp_path / "run" / "bindings_app_0.log").write_text("not a csv, ignored\n")

    result = parse(FakeJob(tmp_path, variables={"nodes": 2}))

    assert list(result) == ["app_0"]
    rows = result["app_0"]
    assert len(rows) == 25
    first = rows[0]
    assert list(first) == [*BLINK_COLUMNS, *EXTRA_COLUMNS, "var_nodes"]
    assert first["run_id"] == 1 and isinstance(first["run_id"], int)
    assert first["msg_size"] == 1048576 and isinstance(first["msg_size"], int)
    assert first["0_Avg-Duration_s"] == 0.000920592
    assert isinstance(first["0_Avg-Duration_s"], float)
    assert first["app"] == 0 and isinstance(first["app"], int)
    assert first["tag"] == "a2a-smoke"
    assert first["config"] == "crab_run_2"
    assert first["job_id"] == 4242 and isinstance(first["job_id"], int)
    assert first["experiment"] == ""
    assert first["var_nodes"] == 2


@pytest.mark.parametrize("status", ["FAILED", "RUNNING"])
def test_a_job_that_did_not_complete_is_skipped(parse: Any, tmp_path: Path, status: str) -> None:
    _put_fixture(tmp_path / "run")

    assert parse(FakeJob(tmp_path, status=status)) is None


def test_no_csv_gives_none(parse: Any, tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "bindings_app_0.log").write_text("log\n")

    assert parse(FakeJob(tmp_path)) is None


def test_missing_run_folder_gives_none(parse: Any, tmp_path: Path) -> None:
    assert parse(FakeJob(tmp_path)) is None


def test_two_apps_with_different_columns_give_two_tables(parse: Any, tmp_path: Path) -> None:
    run = tmp_path / "run"
    _put_fixture(run)
    (run / "data_app_1.csv").write_text("run_id,time_s,label\n1,2.5,fast\n2,3,slow\n")

    result = parse(FakeJob(tmp_path))

    assert sorted(result) == ["app_0", "app_1"]
    assert list(result["app_1"][0]) == ["run_id", "time_s", "label", *EXTRA_COLUMNS]
    assert [r["time_s"] for r in result["app_1"]] == [2.5, 3]
    assert [r["label"] for r in result["app_1"]] == ["fast", "slow"]
    assert {r["app"] for r in result["app_1"]} == {1}
    assert {r["app"] for r in result["app_0"]} == {0}


def test_experiment_subfolders_share_the_app_table(parse: Any, tmp_path: Path) -> None:
    run = tmp_path / "run"
    _put_fixture(run / "exp_b")
    _put_fixture(run / "exp_a")

    result = parse(FakeJob(tmp_path))

    assert list(result) == ["app_0"]
    rows = result["app_0"]
    assert len(rows) == 50
    assert [r["experiment"] for r in rows] == ["exp_a"] * 25 + ["exp_b"] * 25


def test_nested_experiment_path_is_relative_to_run(parse: Any, tmp_path: Path) -> None:
    _put_fixture(tmp_path / "run" / "outer" / "inner")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert {r["experiment"] for r in rows} == {"outer/inner"}


def test_variables_none_adds_no_var_columns(parse: Any, tmp_path: Path) -> None:
    _put_fixture(tmp_path / "run")

    rows = parse(FakeJob(tmp_path, variables=None))["app_0"]

    assert list(rows[0]) == [*BLINK_COLUMNS, *EXTRA_COLUMNS]


def test_every_variable_becomes_a_var_column(parse: Any, tmp_path: Path) -> None:
    _put_fixture(tmp_path / "run")

    rows = parse(FakeJob(tmp_path, variables={"nodes": 4, "mode": "a2a"}))["app_0"]

    assert rows[0]["var_nodes"] == 4
    assert rows[0]["var_mode"] == "a2a"


def test_a_broken_csv_is_skipped(parse: Any, tmp_path: Path) -> None:
    run = tmp_path / "run"
    _put_fixture(run)
    (run / "data_app_1.csv").write_text("")
    (run / "data_app_2.csv").write_bytes(b"\xff\xfe\x00\x01 not text\n\x00\x00")
    (run / "data_app_3.csv").write_text("a,b\n1\n")

    result = parse(FakeJob(tmp_path))

    assert list(result) == ["app_0"]


def test_only_broken_csv_gives_none(parse: Any, tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "data_app_0.csv").write_text("")

    assert parse(FakeJob(tmp_path)) is None


def test_header_only_csv_gives_none(parse: Any, tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "data_app_0.csv").write_text("run_id,msg_size\n")

    assert parse(FakeJob(tmp_path)) is None


def test_rows_load_into_sqlite_with_quoted_column_names(parse: Any, tmp_path: Path) -> None:
    _put_fixture(tmp_path / "run")
    rows = parse(FakeJob(tmp_path))["app_0"]

    connection = sqlite3.connect(":memory:")
    columns = ", ".join(f'"{name}"' for name in rows[0])
    connection.execute(f"CREATE TABLE app_0 ({columns})")
    marks = ", ".join("?" for _ in rows[0])
    connection.executemany(
        f"INSERT INTO app_0 VALUES ({marks})", [tuple(r.values()) for r in rows]
    )

    values = [v for (v,) in connection.execute('SELECT "0_Avg-Duration_s" FROM app_0')]
    assert len(values) == 25
    assert values[0] == 0.000920592
    assert all(isinstance(v, float) for v in values)
