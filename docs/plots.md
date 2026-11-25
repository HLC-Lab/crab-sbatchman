# Plots of your own

`sbatchman visualize` draws the results of a benchmark in your browser. Two files in the benchmark folder steer it: `parser.py` turns the jobs into tables, and `plots.json` holds the plots you saved. Blink ships both, as [Results](results.md#fetch-and-plot) shows. Write them here for a benchmark of your own. Run every step on your laptop, installed as in [Install](install.md#install-on-your-laptop), in a shell where you ran `source env.sh`.

## What visualize reads

`sbatchman visualize` reads three things from the folder you start it in:

- `SbatchMan/`, the SbatchMan project that holds the jobs and their result files. SbatchMan looks in the folder, then in each parent folder. `sbatchman fetch` creates its `SbatchMan/` folder from the `local` path of the benchmark's `[[clusters.fetch_dirs]]` block.
- `parser.py`. Without it the command stops with `Parser script not found:` ([Troubleshooting](troubleshooting.md#parser-script-not-found)).
- `plots.json`. Without `plots.json`, the page opens with no saved plots and you build them in the plot builder.

Each start runs the parser on every job, writes the tables to `SbatchMan/data.sqlite` and serves them on `http://127.0.0.1:8765`, the address to open in your browser. A good start prints `DBs   : data` and, when `plots.json` loaded, `Workspace: loaded from ./plots.json`.

## Use the shared parser

`sbatchman visualize` reads `./parser.py` of the folder you start it from. The umbrella ships one for CRAB results, `benchmarks/parser.py`, and `benchmarks/blink/parser.py` is a symbolic link to it. For a benchmark that CRAB runs, link the same file. The link needs only the shared file and the folder `benchmarks/<benchmark>`, which `mkdir -p` makes, so it does not wait for the fetch: make it before the first `sbatchman visualize`. Run this in the umbrella folder, and `ls -l` then shows `parser.py -> ../parser.py`:

```bash
mkdir -p benchmarks/<benchmark>
ln -s ../parser.py benchmarks/<benchmark>/parser.py
ls -l benchmarks/<benchmark>/parser.py
```

The shared parser reads the `data_app_0.csv`, `data_app_1.csv` and so on of finished jobs, which an app writes when it has `"collect": true`, and returns one table for each app, `app_0`, `app_1` and so on. [Results](results.md#what-you-see) lists their columns. A wrapper's metric column is named with the app number, the metric and its unit: the metric `latency` in `us` of app 0 is `0_latency_us`. [The results files of CRAB](https://github.com/HLC-Lab/CRAB/blob/v1.5.1+sbatchman/docs/using/results.md#data_app_icsv) explain the other columns.

## The parser contract

SbatchMan runs `parser.py` as a Python file and calls its function `parse(job)` once for each job of the project, archived jobs included, in no fixed order. The function sees a job of any status and decides what to read.

- `job.status`: text such as `COMPLETED`, `FAILED`, `TIMEOUT` or `RUNNING`.
- `job.tag`, `job.config_name`, `job.cluster_name` and `job.job_id`: the tag, the config, the cluster and the Slurm job id. `job.variables` is the variables of the job as a dict, or `None`.
- `job.get_job_base_path()`: the job folder, as a `Path`.

`parse(job)` returns `None` or `{}` when the job adds no rows, and any other falsy value (`[]`, `0`) skips the job the same way. Otherwise it returns a dict from table name to rows. A row is a dict from column name to value, and a table takes one row or a list of rows.

- Each table name becomes an SQL table in `SbatchMan/data.sqlite`. The columns are the row keys, in the order they first appear, and a row without a key gets an empty value.
- When `parse` raises for one job, SbatchMan prints the traceback and that job adds no rows. The other jobs go on.
- SbatchMan stops with the Python error when `parser.py` does not import, has no `parse(job)` function, returns a truthy value that is not a dict, or puts something other than a row or a list of rows in a table.

## Write a parser of your own

Write one when your numbers are not in a `data_app_0.csv`, or you want other tables. This example is for a benchmark `myapp` whose jobs write `times.csv` in the job folder. A job runs from the folder you launched in and finds its job folder in `$SBATCHMAN_JOB_DIR` ([Change the keys](campaigns.md#change-the-keys)).

```csv
iteration,time_us
1,12.5
2,12.1
```

If the folder holds the link of the previous section, remove it first. Saving a file over the link overwrites the shared `benchmarks/parser.py`, and Blink would then use your parser:

```bash
rm benchmarks/<benchmark>/parser.py
```

Save this as `benchmarks/<benchmark>/parser.py`. It adds no rows for a job that did not complete or has no `times.csv`, and it names the tag, config and variables as the shared parser does:

```python
import csv


def parse(job):
    path = job.get_job_base_path() / "times.csv"
    if job.status != "COMPLETED" or not path.is_file():
        return None
    extra = {"tag": job.tag, "config": job.config_name}
    extra.update({f"var_{name}": value for name, value in (job.variables or {}).items()})
    with path.open(newline="") as handle:
        rows = csv.DictReader(handle)
        return {"myapp": [{"iteration": int(r["iteration"]), "time_us": float(r["time_us"]), **extra} for r in rows]}
```

Start `sbatchman visualize` once so that it writes `SbatchMan/data.sqlite`, stop it with Ctrl+C, then run `sbatchman visualize --describe SbatchMan/data.sqlite` in the benchmark folder. For a completed job with the tag `myapp-smoke`, the config `myapp_2` and `nodes` set to 2, the output ends with the rows of the table `myapp`:

```text
 iteration  time_us         tag  config  var_nodes
         1     12.5 myapp-smoke myapp_2          2
         2     12.1 myapp-smoke myapp_2          2
```

## The plots.json file

`plots.json` holds a workspace, one plot for each tab. Build a plot in the page, press **Export workspace**, choose **Download JSON file** and save the file as `plots.json` in the benchmark folder. The export writes every script folder you saved in the page into `script_paths`: delete the entries that name your own folders before you commit `plots.json`. `sbatchman visualize` reads the file at its start, so restart it after a change. To write one by hand, start from `benchmarks/blink/plots.json`. Its first plot is:

```json
{
  "version": 3, "label": "Baseline vs noise", "mode": "grid", "rendererBackend": "matplotlib", "database": "data",
  "sql": "SELECT CASE WHEN experiment LIKE '%noise' THEN 'noise' ELSE 'baseline' END AS state, tag, var_nodes, msg_size, AVG(\"0_Avg-Duration_s\") * 1000.0 AS avg_duration_ms FROM app_0 GROUP BY state, tag, var_nodes, msg_size ORDER BY msg_size, var_nodes, tag, state",
  "plotType": "bar", "chartTitle": "Blink victim: baseline vs noise",
  "x": "msg_size", "y": ["avg_duration_ms"], "group": ["state", "tag", "var_nodes"],
  "xLabel": "Message size (bytes)", "yLabel": "Average duration (ms)",
  "showLegend": true, "legendTitle": "State"
}
```

The file around the plots holds `version` (write `3`), `activeTabIndex` (the tab shown first, counted from 0), `tabs` (the list of plots, one entry like this one; the file is refused without one), `style` (the settings of the Style tab, shared by all plots) and `script_paths` (folders with Python files that a plot's own scripts import). A tab that the page writes keeps its keys in a `single` block and a `grid` block, and keys at the top of a tab, as Blink writes them, load as one plot. The page writes every other setting, such as `markerBy`, `dashBy`, `xScale`, `yScale`, `legendPosition` and `extra`, only when it differs from its default: set it in the page, export, and read the value. Needed means the plot cannot draw without the key, and `by type` means the plot type decides.

| Key | Meaning | Default | Needed |
|---|---|---|---|
| `mode`, `rendererBackend`, `database` | Write them as Blink does. `mode` also takes `facet` and `rendererBackend` also takes `plotly`, and any other value loads as the default. SbatchMan builds one database, `data`. | `grid`, `matplotlib`, `data` | no |
| `sql` | The query that feeds the plot, read-only: `SELECT` or `WITH`. Its tables are the keys that `parse` returned. SbatchMan runs it at load only when it is not empty. | none | yes |
| `plotType` | `line`, `bar`, `scatter`, `histogram`, `box`, `violin`, `heatmap` or `pie`. Another name fails with `Unknown plot type:`. | `line` | no |
| `x`, `y`, `z` | Columns of the query's result, after any `AS`. `x` is one name, `y` is a list and `z` is the third column of a `heatmap`. `heatmap` and `pie` read the first `y`. | none | by type |
| `group` | A list of columns of the result. The plot draws one series for each value. | none | no |
| `label`, `chartTitle`, `xLabel`, `yLabel`, `legendTitle` | The name of the tab and the texts of the plot. | `Plot` and a number for `label`, none for the rest | no |
| `showLegend` | `true` or `false`: draw the legend or not. | `true` | no |

`line`, `bar` and `scatter` need `x` and a `y`. `histogram` needs `x`, `box` and `violin` need a `y`, `heatmap` needs `x`, `y` and `z`, and `pie` needs `x` for the labels and `y` for the values. SQL needs double quotes around a column name that starts with a digit or contains a dash, as in `SELECT "0_Avg-Duration_s" FROM app_0`. Sort with `ORDER BY`: the rows of different jobs come in no fixed order.

## When a plot shows nothing or fails

Print the tables first, with the `--describe` command of the parser section. It prints each table with its columns and first rows, or `No tables found in` the path. Then check the causes.

- No tables: `parse` returned `None` for every job. Check the status of the jobs and that the result file exists ([The page opens with no data or no plots](troubleshooting.md#the-page-opens-with-no-data-or-no-plots)). SbatchMan lists only job folders with a readable `metadata.yaml`.
- A table you no longer write is still listed: `SbatchMan/data.sqlite` keeps the tables of earlier runs. Delete the file and start again.
- `unrecognized token: "0_time_us"` or `no such column: Avg`: quote the name in `sql`. `no such table: app_1`: the name is not in the `--describe` output.
- `bar chart requires x and at least one y.`, or a message that is only a name in quotes such as `'avg_ms'`: `x` or `y` names a column that the query does not return. Use the name after `AS`.
- The page opens empty although `plots.json` is there: the file is not valid JSON (the shell prints `Failed to load` and the reason), or you used `--presets`, which SbatchMan accepts and ignores. Only `./plots.json` of the folder you start in is read.
- An edit changed nothing: `plots.json` loads at the start, so restart. For `parser.py`, press **Re-parse selected DB** in the **Actions** tab of the sidebar, or restart.
