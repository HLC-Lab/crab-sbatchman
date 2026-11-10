"""Generic SbatchMan parser for CRAB results: `sbatchman visualize` calls parse(job) per job.

Run it from the benchmark folder that holds plots.json (benchmarks/blink or benchmarks/qe; each
has a symlink to this file). It reads every data_app_<i>.csv of a COMPLETED job (under <job folder>/run
for one experiment, directly under the job folder for several) and returns one table per app: "app_<i>" holds every CSV column (numbers typed), then app,
tag, config, job_id, experiment (the CSV's folder relative to run/, "" when directly in it) and
one var_<name> column per SbatchMan variable of the job. Files of one app share its table.
"""

import csv
import re
from pathlib import Path

FILE_NAME = re.compile(r"^data_app_(\d+)\.csv$")
INTEGER = re.compile(r"^[+-]?\d+$")


def _number(text):
    """int if the text is an integer, else float if it is a number, else the text itself."""
    if INTEGER.match(text):
        return int(text)
    if "_" in text:
        return text
    try:
        return float(text)
    except ValueError:
        return text


def _read(path):
    """The typed rows of one CSV file, or None when it is empty, malformed or unreadable."""
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return None
            rows = []
            for raw in reader:
                if None in raw or None in raw.values():
                    return None
                rows.append({name: _number(value) for name, value in raw.items()})
    except (OSError, UnicodeDecodeError, csv.Error):
        return None
    return rows or None


def parse(job):
    if job.status != "COMPLETED":
        return None
    base = Path(job.get_job_base_path())
    # One experiment writes into <job>/run; several experiments (r1_baseline, r1_noise, ...) sit
    # directly under the job folder.
    run = base / "run" if (base / "run").is_dir() else base
    if not run.is_dir():
        return None
    variables = {f"var_{name}": value for name, value in (job.variables or {}).items()}
    tables = {}
    for path in sorted(run.rglob("data_app_*.csv")):
        match = FILE_NAME.match(path.name)
        if not match or not path.is_file():
            continue
        rows = _read(path)
        if rows is None:
            continue
        app = int(match.group(1))
        experiment = path.parent.relative_to(run).as_posix()
        experiment = "" if experiment == "." else experiment
        extra = {
            "app": app,
            "tag": job.tag,
            "config": job.config_name,
            "job_id": job.job_id,
            "experiment": experiment,
            **variables,
        }
        tables.setdefault(f"app_{app}", []).extend({**row, **extra} for row in rows)
    return tables or None
