# Results

Copy the results of finished jobs to your laptop and plot them with `sbatchman visualize`.

Run these steps on your laptop, installed as in [Install](install.md#install-on-your-laptop), once at least one job has finished: [Run a benchmark](launch.md#follow-the-jobs) shows how to see that. The first plot needs the whole path: [Install](install.md) on the cluster and the laptop, [Connect](connect.md), [Register Blink](launch.md#register-blink), the [smoke test](launch.md#launch-the-smoke-test) with the status `COMPLETED`, then the fetch in step 2.

## Fetch and plot

1. Tell SbatchMan which folders to copy. Open the `remotes-config.toml` that [Connect](connect.md#add-the-cluster-to-sbatchman) saved, in the SbatchMan config folder named there. Under the cluster block, add one `[[clusters.fetch_dirs]]` block for each benchmark. Add the `[global]` section once. If the file already has one, edit that one. With both pages done, the file looks like this:

   ```toml
   [global]
   transfer_backend = "rsync"
   fetch_excludes = ["scratch"]

   [[clusters]]
   name = "leonardo"
   host = "<login-host>"
   port = 22
   user = "<your-user>"

   [[clusters.fetch_dirs]]
   alias = "<benchmark>"
   remote = "<umbrella-dir>/benchmarks/<benchmark>/SbatchMan"
   local = "<laptop-dir>/benchmarks/<benchmark>/SbatchMan"
   ```

   The first lines keep rsync as the copy tool and skip folders named `scratch`. The cluster block is the one you saved, with your own address and username. In the `fetch_dirs` block, `alias` is a name for that folder: `sbatchman fetch` prints it, and the plot page lists it under "Fetch from remote". `remote` is the absolute path of the benchmark's `SbatchMan` folder on the cluster, under `<umbrella-dir>`. `local` is the same path on your laptop, under `<laptop-dir>`. [Connect](connect.md) defines both folders and says how to print their full paths. For Blink, `<benchmark>` is `blink`.

2. Copy the results. Run this in a shell where you ran `source env.sh` and that holds your ssh agent, and run it again after new jobs finish.

   ```bash
   sbatchman fetch
   ```

   A good result prints `✓ <benchmark> done` for each `[[clusters.fetch_dirs]]` block: the name is the block's `alias`, and a block without one shows `?`. A line `✗ <benchmark> failed` means the copy failed: see the entry `✗ ? failed (rsync exit N)` in [Troubleshooting](troubleshooting.md#results). The command still exits with 0, so read its lines.

3. Go to the benchmark folder and start the plots. Blink already has `parser.py` and `plots.json`, so nothing else is needed. For a benchmark of your own, link `parser.py` before this step ([Use the shared parser](plots.md#use-the-shared-parser)): without it the command stops with `Parser script not found:`.

   ```bash
   cd <laptop-dir>/benchmarks/<benchmark>
   sbatchman visualize
   ```

   A block without `alias` makes the start print `[WARN] No remote systems config: 'alias'`. The page then shows an empty "Fetch from remote" list for every cluster, not only for that block. The warning is harmless, because the plots and `sbatchman fetch` do not use that list. Add the `alias` line of step 1 to remove it.

4. Open `http://127.0.0.1:8765`. The page loads its plotting library (plotly) from `cdn.jsdelivr.net` and its fonts from `fonts.googleapis.com`, so the laptop needs internet access to draw the plots. Without it the library does not load and the plots cannot be drawn.

The port is fixed at 8765, and `sbatchman visualize` has no option to change it. `crab web` serves on 8899 after `source env.sh`, so you can run both. If another program holds 8765, the command stops: [Troubleshooting](troubleshooting.md#sbatchman-visualize-does-not-start-because-port-8765-is-in-use) shows the error and how to find that program.

## What you see

The `plots.json` of Blink holds two starter plots:

- Blink, "Baseline vs noise": the average duration in ms per message size, for baseline and noise.
- Blink, "Per repetition": the same average for each repetition.

Each app has one table: `app_0` for the first app, `app_1` for the second, and so on. Its columns are:

- Every column of the app's `data_app_0.csv`, `data_app_1.csv` and so on, named as CRAB wrote them.
- `app`, `tag`, `config`, `job_id` and `experiment`.
- One column for each variable of the job, named `var_` plus the variable, such as `var_nodes`.

A job appears when its status is `COMPLETED`, `FAILED`, `TIMEOUT` or `CHECK_FAIL`. Running, queued and cancelled jobs do not.

If the fetched jobs have not finished yet, `sbatchman visualize` still starts, but the tables `app_0` and so on do not exist, so the plots of Blink have no data until a job has finished. The umbrella ships no sample results for you to try the plots on: the plots need your own finished jobs. [Run a benchmark](launch.md) starts jobs, and `sbatchman fetch` copies them once they finish.

Use the page's plot builder to draw other plots from these tables. [Plots of your own](plots.md) covers the SQL, the saved plots, and the `parser.py` of a benchmark of your own.
