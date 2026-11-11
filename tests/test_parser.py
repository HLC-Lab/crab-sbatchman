"""Tests the generic SbatchMan parser (benchmarks/parser.py). Standard library and pytest.

The parser is not a package: SbatchMan loads it from the working directory, so the tests load it
by path. A duck-typed job stands in for the SbatchMan Job (only the fields the parser reads).
"""

import enum
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
        status: Any = "COMPLETED",
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


@pytest.mark.parametrize("status", ["RUNNING", "PENDING", "QUEUED", "CANCELLED", "UNKNOWN"])
def test_a_job_that_is_not_finished_is_skipped(parse: Any, tmp_path: Path, status: str) -> None:
    _put_fixture(tmp_path / "run")

    assert parse(FakeJob(tmp_path, status=status)) is None


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "TIMEOUT", "CHECK_FAIL"])
def test_a_finished_job_keeps_its_csvs_whatever_its_status(
    parse: Any, tmp_path: Path, status: str
) -> None:
    _put_fixture(tmp_path / "run")

    rows = parse(FakeJob(tmp_path, status=status))["app_0"]

    assert len(rows) == 25


def test_the_status_may_be_an_enum_as_in_sbatchman(parse: Any, tmp_path: Path) -> None:
    class Status(enum.Enum):
        TIMEOUT = "TIMEOUT"
        RUNNING = "RUNNING"

    _put_fixture(tmp_path / "run")

    assert len(parse(FakeJob(tmp_path, status=Status.TIMEOUT))["app_0"]) == 25
    assert parse(FakeJob(tmp_path, status=Status.RUNNING)) is None


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


def test_apps_working_folders_are_not_read(parse: Any, tmp_path: Path) -> None:
    run = tmp_path / "run"
    _put_fixture(run)
    _put_fixture(run / "run_1" / "app_0")
    _put_fixture(run / "artifacts" / "run_1" / "app_0")
    _put_fixture(run / "exp_a" / "run_1" / "app_0")
    _put_fixture(run / "a" / "b" / "c")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert len(rows) == 25
    assert {r["experiment"] for r in rows} == {""}


def test_apps_working_folders_of_a_multi_experiment_job_are_not_read(
    parse: Any, tmp_path: Path
) -> None:
    _put_fixture(tmp_path / "r1_baseline")
    _put_fixture(tmp_path / "r1_baseline" / "run_1" / "app_0")
    _put_fixture(tmp_path / "r1_noise")
    _put_fixture(tmp_path / "r1_noise" / "run_3" / "app_1")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert [r["experiment"] for r in rows] == ["r1_baseline"] * 25 + ["r1_noise"] * 25


def test_an_empty_cell_is_none_not_an_empty_string(parse: Any, tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "data_app_0.csv").write_text("run_id,time_s,label\n1,,fast\n2,3.5,\n")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert [r["time_s"] for r in rows] == [None, 3.5]
    assert [r["label"] for r in rows] == ["fast", None]
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE app_0 (time_s)")
    connection.executemany("INSERT INTO app_0 VALUES (?)", [(r["time_s"],) for r in rows])
    assert connection.execute("SELECT AVG(time_s) FROM app_0").fetchone() == (3.5,)


def test_a_csv_column_named_like_an_extra_keeps_the_extra(parse: Any, tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "data_app_0.csv").write_text("run_id,tag,job_id,var_nodes,time_s\n1,mine,7,9,2.5\n")
    (run / "data_app_1.csv").write_text("run_id,time_s\n1,2.5\n")

    result = parse(FakeJob(tmp_path, variables={"nodes": 2}))

    row = result["app_0"][0]
    assert row["tag"] == "a2a-smoke"
    assert row["job_id"] == 4242
    assert row["var_nodes"] == 2
    assert row["time_s"] == 2.5
    assert list(row) == ["run_id", "time_s", *EXTRA_COLUMNS, "var_nodes"]
    assert list(result["app_1"][0]) == ["run_id", "time_s", *EXTRA_COLUMNS, "var_nodes"]


def test_a_csv_directly_in_the_run_folder_is_experiment_empty_next_to_others(
    parse: Any, tmp_path: Path
) -> None:
    _put_fixture(tmp_path / "run")
    _put_fixture(tmp_path / "r1_baseline")
    _put_fixture(tmp_path / "r1_noise")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert len(rows) == 75
    assert sorted({r["experiment"] for r in rows}) == ["", "r1_baseline", "r1_noise"]


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


def _warnings(capsys: Any) -> list[str]:
    return [line for line in capsys.readouterr().err.splitlines() if line.strip()]


def test_a_clean_file_prints_nothing_to_stderr(parse: Any, tmp_path: Path, capsys: Any) -> None:
    _put_fixture(tmp_path / "run")

    parse(FakeJob(tmp_path))

    assert capsys.readouterr().err == ""


def test_a_cut_last_row_is_dropped_and_the_good_rows_stay(
    parse: Any, tmp_path: Path, capsys: Any
) -> None:
    lines = FIXTURE.read_text().splitlines()
    run = tmp_path / "run"
    run.mkdir()
    path = run / "data_app_0.csv"
    path.write_text("\n".join([*lines[:25], "25,1048576"]))  # header + 24 rows + a cut row

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert len(rows) == 24
    assert rows[0]["msg_size"] == 1048576
    warnings = _warnings(capsys)
    assert warnings == [
        f"parser: {path}: skipped line(s) 26 (cell count differs from the header)"
    ]


def test_a_row_with_an_extra_cell_in_the_middle_is_skipped(
    parse: Any, tmp_path: Path, capsys: Any
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    path = run / "data_app_0.csv"
    path.write_text("run_id,time_s\n1,1.5\n2,2.5,oops\n3,3.5\n")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert [r["run_id"] for r in rows] == [1, 3]
    assert _warnings(capsys) == [
        f"parser: {path}: skipped line(s) 3 (cell count differs from the header)"
    ]


def test_several_bad_rows_in_one_file_give_one_warning_with_every_line(
    parse: Any, tmp_path: Path, capsys: Any
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    path = run / "data_app_0.csv"
    path.write_text("a,b\n1,1\n2\n3,3\n4,4,4\n5,5\n6\n")

    rows = parse(FakeJob(tmp_path))["app_0"]

    assert [r["a"] for r in rows] == [1, 3, 5]
    assert _warnings(capsys) == [
        f"parser: {path}: skipped line(s) 3, 5, 7 (cell count differs from the header)"
    ]


def test_a_file_with_no_good_row_is_dropped_with_one_warning(
    parse: Any, tmp_path: Path, capsys: Any
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    path = run / "data_app_0.csv"
    path.write_text("a,b\n1\n")
    (run / "data_app_1.csv").write_text("a,b\n1,2\n")

    result = parse(FakeJob(tmp_path))

    assert list(result) == ["app_1"]
    assert _warnings(capsys) == [
        f"parser: {path}: file skipped (no good rows; skipped line(s) 2)"
    ]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"", "empty file"),
        (b"run_id,msg_size\n", "no data rows"),
        (b"\xff\xfe\x00\x01 not text\n\x00\x00", "not valid UTF-8"),
    ],
)
def test_a_file_dropped_whole_gives_one_warning_with_the_reason(
    parse: Any, tmp_path: Path, capsys: Any, content: bytes, reason: str
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    path = run / "data_app_0.csv"
    path.write_bytes(content)

    assert parse(FakeJob(tmp_path)) is None
    assert _warnings(capsys) == [f"parser: {path}: file skipped ({reason})"]


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


# --- real Leonardo results (trimmed copies in tests/fixtures/results/) ---------------------

RESULTS = Path(__file__).resolve().parent / "fixtures" / "results" / "leonardo"
BLINK_NOISE_JOB = RESULTS / "crab_run_4" / "blink-noise-4n-1048576B" / "20261110_104331"


class RealJob:
    """The fields the parser reads, for a job folder copied from a real run."""

    def __init__(
        self, base: Path, tag: str, config_name: str, job_id: int, variables: dict[str, Any]
    ) -> None:
        self.status = "COMPLETED"
        self.tag = tag
        self.config_name = config_name
        self.job_id = job_id
        self.variables = variables
        self._base = base

    def get_job_base_path(self) -> Path:
        return self._base


def test_real_blink_noise_job_gives_one_table_with_the_six_experiment_folders(
    parse: Any,
) -> None:
    job = RealJob(
        BLINK_NOISE_JOB,
        "blink-noise-4n-1048576B",
        "crab_run_4",
        64054665,
        {"nodes": 4, "msgsize": 1048576},
    )

    result = parse(job)

    assert list(result) == ["app_0"]
    rows = result["app_0"]
    assert len(rows) == 6 * 12
    assert {r["experiment"] for r in rows} == {
        "r1_baseline",
        "r1_noise",
        "r2_baseline",
        "r2_noise",
        "r3_baseline",
        "r3_noise",
    }
    assert list(rows[0])[:7] == BLINK_COLUMNS
    assert {r["var_nodes"] for r in rows} == {4}
    assert {r["var_msgsize"] for r in rows} == {1048576}
    assert {r["tag"] for r in rows} == {"blink-noise-4n-1048576B"}
    assert {r["config"] for r in rows} == {"crab_run_4"}
