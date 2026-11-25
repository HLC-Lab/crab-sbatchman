# Results

Copy the results of finished jobs to your laptop and plot them with `sbatchman visualize`.

Run these steps on your laptop, installed as in [Install](install.md#install-on-your-laptop), once at least one job has finished: [Run a benchmark](launch.md#follow-the-jobs) shows how to see that.

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
   remote = "<umbrella-dir>/benchmarks/<benchmark>/SbatchMan"
   local = "<laptop-dir>/benchmarks/<benchmark>/SbatchMan"
   ```

   The first lines keep rsync as the copy tool and skip folders named `scratch`. The cluster block is the one you saved, with your own address and username. In the `fetch_dirs` block, `remote` is the absolute path of the benchmark's `SbatchMan` folder on the cluster, under the folder where you cloned the umbrella. `local` is the same path under the umbrella folder on your laptop. For Blink, `<benchmark>` is `blink`.

2. Copy the results. Run this in a shell where you ran `source env.sh` and that holds your ssh agent, and run it again after new jobs finish.

   ```bash
   sbatchman fetch
   ```

   A good result prints `✓ ? done` for each `[[clusters.fetch_dirs]]` block. The `?` stands for the block's alias, which a block without one shows as `?`. A line `✗ ? failed` means the copy failed: see the entry `✗ ? failed (rsync exit N)` in [Troubleshooting](troubleshooting.md#results). The command still exits with 0, so read its lines.

3. Go to the benchmark folder and start the plots. Blink already has `parser.py` and `plots.json`, so nothing else is needed.

   ```bash
   cd benchmarks/<benchmark>
   sbatchman visualize
   ```

4. Open `http://127.0.0.1:8765`.

The port is fixed. `crab web` serves on 8899 after `source env.sh`, so you can run both.

## What you see

The `plots.json` of Blink holds two starter plots:

- Blink, "Baseline vs noise": the average duration in ms per message size, for baseline and noise.
- Blink, "Per repetition": the same average for each repetition.

Each app has one table: `app_0` for the first app, `app_1` for the second, and so on. Its columns are:

- Every column of the app's `data_app_0.csv`, `data_app_1.csv` and so on, named as CRAB wrote them.
- `app`, `tag`, `config`, `job_id` and `experiment`.
- One column for each variable of the job, named `var_` plus the variable, such as `var_nodes`.

A job appears when its status is `COMPLETED`, `FAILED`, `TIMEOUT` or `CHECK_FAIL`. Running, queued and cancelled jobs do not.

Use the page's plot builder to draw other plots from these tables. [Plots of your own](plots.md) covers the SQL, the saved plots, and the `parser.py` of a benchmark of your own.
