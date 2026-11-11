"""Generic SbatchMan parser for CRAB results: `sbatchman visualize` calls parse(job) per job.

Run it from the benchmark folder that holds plots.json (benchmarks/blink or benchmarks/qe; each
has a symlink to this file). It reads every data_app_<i>.csv of a finished job (status COMPLETED,
FAILED, TIMEOUT or CHECK_FAIL, so the experiments that did finish are not lost; running, queued
and cancelled jobs are skipped) and returns one table per app: "app_<i>" holds every CSV column
(numbers typed, an empty cell is None), then app, tag, config, job_id, experiment and one
var_<name> column per SbatchMan variable of the job. A CSV column with the name of one of those
extra columns is dropped: the extra wins. Files of one app share its table. A row with more or fewer cells than the header is
skipped and a file that cannot be used is dropped; each prints one warning line on stderr.

Where it looks (base = the job folder): a CSV directly in <base>/run is experiment "" (a job with
one experiment), always, even if that folder is a multi-experiment job's experiment named "run";
a CSV in <base>/run/<folder> has the folder relative to run/ as its experiment; a CSV in
<base>/<folder> (several experiments: r1_baseline, r1_noise, ...) has the folder relative to the
job folder, and one directly in <base> is experiment "". The search goes two folders deep and never
enters an app's working folders (run_<n>, app_<n>, artifacts, scratch): they can be large.
"""

import csv
import re
import sys
from pathlib import Path

FILE_NAME = re.compile(r"^data_app_(\d+)\.csv$")
# Folders CRAB creates inside an experiment folder for the apps themselves: never searched.
APP_FOLDER = re.compile(r"^(run_\d+|app_\d+|artifacts|scratch)$")
FINISHED = {"COMPLETED", "FAILED", "TIMEOUT", "CHECK_FAIL"}
MAX_DEPTH = 2
INTEGER = re.compile(r"^[+-]?\d+$")


def _number(text):
    """None if the cell is empty, int if it is an integer, else float if a number, else the text."""
    if not text.strip():
        return None
    if INTEGER.match(text):
        return int(text)
    if "_" in text:
        return text
    try:
        return float(text)
    except ValueError:
        return text


def _warn(path, message):
    """One line on stderr about one file, so a skipped row or file is never silent."""
    print(f"parser: {path}: {message}", file=sys.stderr)


def _lines(numbers):
    return "skipped line(s) " + ", ".join(str(number) for number in numbers)


def _read(path):
    """The typed rows of one CSV file, or None when the file is dropped whole (empty, header only,
    unreadable, malformed, or no good row). A row with more or fewer cells than the header (a job
    killed mid-write cuts the last one) is skipped and the good rows stay. One warning on stderr
    per affected file, with the reason or the line numbers."""
    bad_lines = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                _warn(path, "file skipped (empty file)")
                return None
            rows = []
            for raw in reader:
                if None in raw or None in raw.values():
                    bad_lines.append(reader.line_num)
                    continue
                rows.append({name: _number(value) for name, value in raw.items()})
    except UnicodeDecodeError:
        _warn(path, "file skipped (not valid UTF-8)")
        return None
    except csv.Error as error:
        _warn(path, f"file skipped (malformed CSV: {error})")
        return None
    except OSError as error:
        _warn(path, f"file skipped (unreadable: {error.strerror or error})")
        return None
    if not rows:
        if bad_lines:
            _warn(path, f"file skipped (no good rows; {_lines(bad_lines)})")
        else:
            _warn(path, "file skipped (no data rows)")
        return None
    if bad_lines:
        _warn(path, f"{_lines(bad_lines)} (cell count differs from the header)")
    return rows


def _csv_files(folder, skip=()):
    """(path, folder relative to `folder`) of the data_app_<i>.csv files in `folder` and up to
    MAX_DEPTH folders below it; skips the named folders of `folder` and every app folder."""
    found = []

    def walk(current, depth):
        try:
            entries = sorted(current.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                if entry.is_symlink():
                    continue
                if depth < MAX_DEPTH and not APP_FOLDER.match(entry.name):
                    if depth > 0 or entry.name not in skip:
                        walk(entry, depth + 1)
            elif FILE_NAME.match(entry.name) and entry.is_file():
                found.append((entry, entry.parent.relative_to(folder).as_posix()))

    walk(folder, 0)
    return found


def parse(job):
    if getattr(job.status, "value", job.status) not in FINISHED:
        return None
    base = Path(job.get_job_base_path())
    if not base.is_dir():
        return None
    # One experiment writes into <job>/run (its experiment is relative to run/); several experiments
    # (r1_baseline, r1_noise, ...) sit directly under the job folder (relative to it). Both places
    # are always searched, so a folder named "run" never hides the others.
    found = _csv_files(base / "run") + _csv_files(base, skip=("run",))
    files = [(path, "" if folder == "." else folder) for path, folder in found]
    variables = {f"var_{name}": value for name, value in (job.variables or {}).items()}
    tables = {}
    for path, experiment in sorted(files, key=lambda item: str(item[0])):
        rows = _read(path)
        if rows is None:
            continue
        app = int(FILE_NAME.match(path.name).group(1))
        extra = {
            "app": app,
            "tag": job.tag,
            "config": job.config_name,
            "job_id": job.job_id,
            "experiment": experiment,
            **variables,
        }
        tables.setdefault(f"app_{app}", []).extend(
            {**{k: v for k, v in row.items() if k not in extra}, **extra} for row in rows
        )
    return tables or None
