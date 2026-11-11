# Partner umbrella (working title)

One checkout that holds everything a partner needs to run co-running HPC benchmarks on Leonardo and
to add their own: [CRAB](CRAB/README.md), the shared wrappers, a pinned SbatchMan, the shipped
benchmarks and an installer. The versions in one checkout match, because the two submodules are
pinned to the commits that were tested together.

**Tested and not yet tested.**

- Tested: the installer logic with stubs (the automated tests in `tests/`); the smoke job launched
  on Leonardo from a hand-made umbrella-style checkout; `crab web` and a small `sbatchman fetch`
  over the certificate login; `sbatchman visualize` on real Blink noise results (both Blink plots
  render in a browser).
- Not yet tested: a fresh `git clone --recurse-submodules` plus `./install.sh` on Leonardo; large
  or repeated fetches across rotating login nodes; `visualize` on a login node through a tunnel;
  the QE plots (not seen yet); the "Add your own benchmark" tutorial.

## What this is

CRAB runs one or more applications at the same time on a Slurm allocation and records what each one
measures. SbatchMan submits the Slurm jobs and keeps one record per job. A wrapper tells CRAB how
to launch an application and how to read its output. This repository ties them together:

| Path | What it is |
|---|---|
| `CRAB/` | Submodule: the CRAB engine, pinned. Its docs are in `CRAB/docs/`. |
| `crab-wrappers/` | Submodule: the shared wrappers (Blink, Quantum ESPRESSO, ...). |
| `install.sh` | Installs everything on a cluster or on a laptop. Safe to run again. |
| `configs/leonardo.yaml` | Template of the SbatchMan configs file (account, partition, modules, GPUs). |
| `site/leonardo.env` | Site defaults: partition, qos, cluster name. |
| `benchmarks/` | One folder per benchmark, each its own SbatchMan project. |

The same checkout is installed on two kinds of machine:

| | Cluster (login node) | Laptop |
|---|---|---|
| Role | `--role cluster` (the default) | `--role laptop` |
| Runs | The benchmarks: `sbatchman launch`, then `crab worker` on the compute nodes. | Two dashboards: `crab web` (write and watch experiments) and `sbatchman visualize` (plots). |
| Installs | CRAB, SbatchMan, the filled configs file, the `crab setup` wizard. | CRAB with the web dashboard, SbatchMan with its plots. Nothing in your home folder. |
| Required | Yes: the benchmarks run here. | No: it is a convenience. |

## Install on the cluster

Leonardo's default `python3` is 3.6.8 and CRAB needs Python 3.10 or newer, so load a Python module
before anything else. The installer checks this and tells you.

```bash
git clone --recurse-submodules <umbrella-url>
cd <umbrella-dir>
module load python
./install.sh --account <YOUR_ACCOUNT>
source env.sh
cd benchmarks/blink && sbatchman launch -f smoke.yaml
```

- `git clone --recurse-submodules` fetches the umbrella and both submodules. `<umbrella-url>` and
  `<umbrella-dir>` are the clone address you were given and the folder it creates.
- `module load python` gives a Python 3.10 or newer. A cluster Python module also exports
  `PYTHONPATH`, which breaks the virtual environment: `install.sh` and `env.sh` unset it.
- `./install.sh --account <YOUR_ACCOUNT>` installs, prints every command before it runs it and ends
  with the interactive `crab setup` wizard (skip it with `--no-setup`). The account is saved in the
  untracked `site/local.env`, so later runs need no `--account`.
- `source env.sh` is needed **in every new shell**. It clears `PYTHONPATH` and `PYTHONHOME`,
  activates `CRAB/.venv`, exports `SBATCHMAN_CLUSTER_NAME` (SbatchMan 2.0.4 reads it, so
  `sbatchman set-cluster-name` is not needed) and `CRAB_PATH_WRAPPERS`, and prints where `crab` and
  `sbatchman` come from. Check that both paths are inside `CRAB/.venv`. (`source CRAB/.venv/bin/activate`
  clears `PYTHONPATH` too; `env.sh` also sets the other variables.)
- `sbatchman launch -f smoke.yaml` submits the smallest job: an all-to-all on 2 nodes. Launch from
  inside the benchmark folder, because every folder is its own SbatchMan project.

Register the applications in the `crab setup` wizard (run `crab setup` again later if you skipped
it), before the jobs that need them run. The wizard is described in
[`CRAB/docs/using/installation.md`](CRAB/docs/using/installation.md) and
[`CRAB/docs/extending/receipts.md`](CRAB/docs/extending/receipts.md).

| Application | Wizard answers |
|---|---|
| Blink (every Blink job) | Pick the Blink suite and "Download and compile from source layout". The module line is the one your site needs (on Leonardo `module load gcc openmpi`, plus `cmake` if it is a module). GPU backend: `auto`. |
| Quantum ESPRESSO (the two QE jobs) | Pick the QE suite and keep only "Quantum ESPRESSO v7" ticked, strategy "Map via cluster Environment Module system", module `module load profile/chem-phys quantum-espresso`, executable `pw.x`. |

`qe-noise.yaml` also runs Blink next to QE, and the two come from different module stacks: start the
`pre_run` hook of `CRAB/local/receipts/blink.json` with `module purge`
(`"pre_run": ["module purge", "module load gcc openmpi"]`). See "Apps built with different module
stacks" in [`CRAB/docs/using/sbatchman-integration.md`](CRAB/docs/using/sbatchman-integration.md#apps-built-with-different-module-stacks).
Check the result with `crab list-benchmarks` and `crab wrappers list`: no wrapper you use may show
`missing`.

## Install on your laptop

The laptop runs the two dashboards. It needs Python 3.10 or newer and the same clone:

```bash
git clone --recurse-submodules <umbrella-url>
cd <umbrella-dir>
./install.sh --role laptop --login-host <login-host> --user <your-user> --remote-dir <umbrella-folder-on-the-cluster>
source env.sh
```

- `--login-host`, `--user` and `--remote-dir` (the umbrella's folder on the cluster) only fill the
  help block that the installer prints at the end. Nothing is saved. You can put `SITE_LOGIN_HOST`,
  `SITE_USER` and `SITE_REMOTE_DIR` in the untracked `site/local.env` instead; the flags win.
- The installer puts CRAB with the web dashboard and SbatchMan with plots into the same
  `CRAB/.venv`, and writes nothing into your home folder.
- On the laptop `source env.sh` also sets `CRAB_WEB_PORT=8899` (a value you set yourself is kept),
  so `crab web` runs on `http://127.0.0.1:8899`. `sbatchman visualize` is fixed to
  `http://127.0.0.1:8765`, so the two never collide.

**`crab web`: connect the cluster.** Start the dashboard from the shell that holds your ssh agent
(the certificate login), because it finds the agent through `SSH_AUTH_SOCK`. Open Remotes, press
"+ Add cluster" and type the values the installer printed:

| Field | Value |
|---|---|
| Name | `leonardo` |
| Transport | `ssh` |
| Host, User | `<login-host>`, `<your-user>` |
| Port | `22` |
| Auth | agent (ssh-agent / cert) |
| Host key | insecure (rotating login nodes) |
| Install dir | `<umbrella-folder-on-the-cluster>` |
| Crab command, Preset | leave empty |

**Never press "Install CRAB" for this cluster.** The umbrella already installed it, and the button
would add a second, separate CRAB. If a cluster profile with that name already exists on the laptop,
the dashboard keeps the old one and saves the new one as `<name>2`: connect the one whose line shows
the pinned CRAB version and a path ending in `umbrella-folder/CRAB`. The dashboard reaches the
umbrella's CRAB through a plain ssh command, so it works without `module load python` (checked on
Leonardo, where that shell's `python3` is 3.6.8). What the dashboard does is in
[`CRAB/docs/using/dashboard.md`](CRAB/docs/using/dashboard.md).

**`sbatchman fetch`: results to the laptop.** The installer also prints a `remotes-config.toml`
block. Save it as `~/.config/sbatchman/remotes-config.toml` (merge by hand if the file exists).
Then, in a benchmark folder, `sbatchman fetch` copies the cluster's `SbatchMan/` folder (without
`scratch/`) with rsync. Tested against Leonardo with the certificate login: the smoke job's folder
(about 115 KB) came to the laptop in one run. Large result folders and repeated fetches that land
on different login nodes are not tested yet; if a fetch fails, copy the results with rsync by hand.
A laptop has no `squeue`, and that is fine: SbatchMan only asks the scheduler about jobs that have
not finished, and ignores a failed query, so fetched jobs keep the status they had on the cluster.
To plot the fetched results, see "Explore results with `sbatchman visualize`" under "Run the shipped
benchmarks".

## Run the shipped benchmarks

Every folder under `benchmarks/` is one SbatchMan project. `source env.sh` once per shell, `cd` into
the folder, dry run first, then launch:

```bash
source env.sh
cd benchmarks/blink
sbatchman launch -f smoke.yaml --dry-run
sbatchman launch -f smoke.yaml
sbatchman status
```

- `-f smoke.yaml` names the jobs file. `--dry-run` lists the jobs and submits nothing.
- `sbatchman status` lists the jobs and their state.
- A healthy launch prints `Loading configs from file ...`, a `Submitted <config> / <tag>` line per
  job and ends with `Submitted successfully N jobs`. Read that count: a failed `sbatch` prints
  `Failed to submit job: ...` and the exit code is still 0.

| Folder | Jobs file | What it measures | Jobs |
|---|---|---|---|
| `benchmarks/blink` | `smoke.yaml` | An all-to-all alone on 2 nodes. Run it first. | 1 |
| | `blink-noise.yaml` | An all-to-all against continuous incast noise, 4 nodes, six experiments in one allocation. | 1 |
| | `a2a-vs-incast.yaml` | The same, swept over 4, 8, 16 nodes and four message sizes. | 12 |
| | `a2a-vs-a2a.yaml` | The same sweep with all-to-all noise. | 12 |
| `benchmarks/qe` | `qe-alone.yaml` | Quantum ESPRESSO `pw.x` alone on 2 nodes (4 GPUs per node): the reference. | 1 |
| | `qe-noise.yaml` | The same `pw.x` run next to an incast aggressor, 4 nodes. | 1 |

The folder READMEs explain each file: [`benchmarks/blink/README.md`](benchmarks/blink/README.md) and
[`benchmarks/qe/README.md`](benchmarks/qe/README.md). The QE jobs write very large scratch folders:
read Known limits before the first QE launch.

**Where results land.** `SbatchMan/experiments/<cluster>/<config>/<tag>/<timestamp>/` inside the
benchmark folder. In it: `config.json` (what the job ran), one folder per experiment (`r1_baseline/`,
`r1_noise/`, ...) with `data_app_<i>.csv` per collected app, `crab_run.json`, and SbatchMan's
`metadata.yaml`. A failed run does not fail the job, so check that the CSVs are not empty.

**Run a job again.** A job is a duplicate when cluster, config and tag match one already in the
project, archived and failed jobs included. Either change the `tag` **and** the `"name"` in the
heredoc's `global_options` together (they must stay equal), or launch with
`sbatchman launch -f <file> --force`.

### Explore results with `sbatchman visualize`

`sbatchman visualize` loads the results of one benchmark folder into a small SQL database and shows
them as plots on a local page. Run it on the laptop, on results you fetched, from the folder that
holds the results:

```bash
source env.sh
cd benchmarks/blink
sbatchman fetch
sbatchman visualize
```

Then open `http://127.0.0.1:8765` in a browser.

- `source env.sh` is needed in every new shell, as everywhere else.
- `cd benchmarks/blink` (or `benchmarks/qe`) matters twice: `fetch` copies the results into the
  project of the current folder, and `visualize` reads `./parser.py` and `./plots.json` from the
  current folder, so it must be started in the folder that holds them.
- `sbatchman fetch` copies the cluster's results to the laptop (see "Install on your laptop").
  Fetch again after new jobs finish.
- `sbatchman visualize` serves the page on port 8765. The port is fixed, there is no option for it.
  `crab web` runs on 8899 on the laptop, so the two can run side by side. `--presets` is accepted
  and ignored.

**What the umbrella ships.**

| File | What it is |
|---|---|
| `benchmarks/parser.py` | The parser SbatchMan calls once per job. Generic, standard library only. Each benchmark folder has a `parser.py` symlink to it. |
| `benchmarks/blink/plots.json` | Two starter plots for Blink results. |
| `benchmarks/qe/plots.json` | Two starter plots for Quantum ESPRESSO results. |

**What each start does.** `visualize` runs the parser over every job of the project and rebuilds
`SbatchMan/data.sqlite` (database name `data`). Jobs that are not `COMPLETED` are skipped, so a
running or failed job does not appear. A laptop without Slurm is fine: SbatchMan only asks the
scheduler about unfinished jobs and ignores a failed query.

**The tables.** There is one table per app, named `app_<i>`: the Blink and QE results are in
`app_0`. Its columns are:

- the columns of `data_app_<i>.csv`. Blink: `msg_size`, `0_Avg-Duration_s`, `0_Min-Duration_s`,
  `0_Max-Duration_s`, `0_Median-Duration_s`, `0_MainRank-Duration_s`, `run_id`. QE: `run_id`,
  `msg_size`, `0_wall_time_seconds`;
- then `app`, `tag`, `config`, `job_id` and `experiment`;
- then one `var_<name>` column per variable of the job, for example `var_nodes`.

`experiment` is the name of the experiment folder: empty for a job with a single experiment,
`r1_baseline`, `r1_noise`, `r2_baseline`, ... for the six-experiment noise jobs (`blink-noise`,
`qe-noise`). A job with several experiments keeps those folders directly under the job folder; a job
with one experiment keeps it in `run/`. The starter plots tell baseline from noise with
`CASE WHEN experiment LIKE '%noise' THEN 'noise' ELSE 'baseline' END`.

A column name that starts with a digit or contains a dash must be in double quotes in SQL:

```sql
SELECT "0_Avg-Duration_s" FROM app_0
```

**The starter plots.**

| Benchmark | Plot | Shows |
|---|---|---|
| Blink | Baseline vs noise (bar) | Average duration in ms per message size, grouped by state, job tag and node count. |
| Blink | Per repetition (bar) | The same average, per repetition `r1` to `rN`, one bar per job tag. |
| QE | Wall time per run (line) | The wall time of each run, one line per state and tag. |
| QE | Average wall time (bar) | The average wall time per job tag, baseline against noise. |

They are starters. To change one, edit `plots.json` by hand. The page's plot builder lets you
explore other queries, but the server never writes `plots.json` back and the page's export button
was not tested: save what you want to keep by editing the file.

## install.sh reference

```
./install.sh [--role cluster|laptop] [--account NAME] [--no-setup] [--dry-run]
             [--login-host HOST] [--user NAME] [--remote-dir PATH] [-h|--help]
```

| Flag | Meaning |
|---|---|
| `--role ROLE` | `cluster` (default): CRAB, SbatchMan, the configs file, the setup wizard. `laptop`: CRAB with the web dashboard, SbatchMan with plots. |
| `--account NAME` | Slurm account to charge, saved in `site/local.env` (cluster role). Letters, digits, `_`, `.`, `-`. Without it, and without `site/local.env`, the installer asks (on a terminal) or exits with `no Slurm account`. |
| `--no-setup` | Skip the interactive `crab setup` wizard at the end (cluster role). |
| `--dry-run` | Print every command and file write, run and write nothing. |
| `--login-host HOST` | Laptop only: the cluster's login host, for the help block. |
| `--user NAME` | Laptop only: your user on the cluster, for the help block. |
| `--remote-dir PATH` | Laptop only: the umbrella's folder on the cluster, for the help block. |
| `-h`, `--help` | Print the usage and exit. |

The three laptop flags are refused with `--role cluster`. The environment variable
`SBATCHMAN_VERSION` overrides the pinned SbatchMan version (default `2.0.4`).

**Steps, in order.** Every command is printed with a `+` before it runs.

1. Unsets `PYTHONPATH` and `PYTHONHOME`.
2. Checks `python3` is 3.10 or newer; otherwise it says `module load python` and exits 1.
3. Runs `git submodule update --init` when `CRAB/Makefile` is missing (exit 1 if it still is).
4. Links `CRAB/wrappers` to `../crab-wrappers` when there is no such folder.
5. `make -C CRAB core`: creates `CRAB/.venv` and installs CRAB.
6. Installs SbatchMan into the same venv. Cluster: `sbatchman==2.0.4`. Laptop: CRAB with the `web`
   extra and `sbatchman[visualization]==2.0.4`.
7. Cluster only: resolves the account, fills `configs/leonardo.yaml` into
   `.local/configs.leonardo.yaml`. It refuses (exit 1) when another `<UPPER_CASE>` token is left.
8. Runs `sbatchman init` in every folder under `benchmarks/` that has no `SbatchMan/` yet.
9. Writes `env.sh` (role-specific).
10. Cluster only, unless `--no-setup`: runs `crab setup`.
11. Prints `install.sh finished: role <role>` and `Next: source env.sh`; on the laptop it then
    prints the `crab web` values, the `remotes-config.toml` block and the start commands.

**Safe to repeat.** A second run prints the same commands and changes no file: submodules, the
link, the `SbatchMan/` projects, `env.sh` and the configs copy are only created or rewritten when
they differ. Exit codes: 0 done, 1 an environment problem (Python too old, CRAB or the template
missing, unfilled tokens), 2 a bad argument, bad value or no account.

## Files and what you may change

| Path | In git? | Who edits it |
|---|---|---|
| `install.sh` | tracked | Maintainers. |
| `env.sh` | no, written by `install.sh` | Nobody: source it. |
| `CRAB/` | submodule, pinned | Nobody. Private files go in `CRAB/local/` (git-ignored): wrappers, receipts. |
| `CRAB/.venv/`, `CRAB/wrappers` | no, created by `install.sh` | Nobody. |
| `crab-wrappers/` | submodule, pinned | Maintainers, through pull requests. |
| `configs/leonardo.yaml` | tracked template | **You**: allocation, modules, GPUs, your own config blocks. |
| `.local/configs.leonardo.yaml` | no, filled copy | Nobody: `install.sh` overwrites it. |
| `site/leonardo.env` | tracked | Maintainers: shared defaults for partition, qos, cluster name. |
| `site/local.env` | no | **You**: your account and any override of `site/leonardo.env`. |
| `benchmarks/<name>/` | tracked | **You**: jobs files, your own folders. |
| `benchmarks/<name>/SbatchMan/` | no, created by `sbatchman init` | Nobody: SbatchMan's records and results. |
| `tests/` | tracked | Maintainers: the checks that keep the installer and this README true. |

**Edit the template, never the filled copy.** After every edit run `./install.sh` again (safe): it
refills `.local/configs.leonardo.yaml`. These tokens in the template are replaced:

| Placeholder | Filled with |
|---|---|
| `<YOUR_ACCOUNT>` | `--account`, or `SLURM_ACCOUNT` in `site/local.env`. |
| `<SLURM_PARTITION>` | `SLURM_PARTITION` of `site/leonardo.env` (`boost_usr_prod`); `site/local.env` wins. |
| `<SLURM_QOS>` | `SLURM_QOS` of `site/leonardo.env` (`normal`); `site/local.env` wins. |
| `<CRAB_DIR>` | The absolute path of the umbrella's `CRAB/` folder. |

Do not write any other `<UPPER_CASE>` token in the template: the installer refuses to write the
copy. The lower-case placeholders in this README (`<umbrella-url>`, `<login-host>`, ...) are for you
to replace when you type a command.

**The knobs.**

| Where | Knob | Default | Notes |
|---|---|---|---|
| `site/local.env` | `SLURM_PARTITION`, `SLURM_QOS` | `boost_usr_prod`, `normal` | `boost_qos_dbg` is the short debug qos: read its node and time limits first. |
| template, `default_conf` | `time` | `00:30:00` | Slurm kills a job past it. A job runs all its experiments in a row: raise it for the 16-node sweeps and for a real `minruns`. |
| template, `default_conf` | `tasks_per_node` | `4` | Ranks per node; keep it at least the experiment's `ppn`. |
| template, `default_conf` | `exclusive: true` | not set | Shared nodes start sooner but timings are not clean. Add it for clean measurements. |
| template, `variables` | `nodes` | `[2, 4, 8, 16]` | One config per value. Every `nodes` of a jobs file needs its config. |
| template, per config | `modules` | gcc and Open MPI (`crab_run_*`); `profile/chem-phys`, `quantum-espresso` (`crab_qe_*`) | Set per config, not in `default_conf` (lists are appended, not replaced). Each config's modules must put an MPI `mpirun` on `PATH`. |
| template, per config | `gpus` | `4` for `crab_qe_*`, none for `crab_run_*` | `#SBATCH --gres=gpu:<n>`, per node. |
| jobs file | `tag` and `"name"` | | Change both together to run again. |
| jobs file | `nodes` list | | Total allocation. In the noise files the victim gets half. |
| jobs file | `args` | | The application's own flags, for example `-msgsize` and `-iter`. |

## Add your own benchmark

You do not need to touch CRAB to run an application that is not shipped. The path has six steps. The
shipped benchmarks are the worked example: read `benchmarks/blink/smoke.yaml` while you go.

**1. A wrapper for the application.** A wrapper is one Python file that names the binary and turns
the output into rows. After `source env.sh`:

```bash
crab wrappers new myapp            # creates myapp/myapp.py, README.md, samples/example/
crab wrappers test myapp --strict  # passes as generated
```

Edit `read_data()`: it receives the application's output in `self.stdout` and returns one dict per
sample. Declare each measured value in `metadata` (name, unit, and `conv: True` for the values CRAB
repeats a run until they converge) and any sweep dimension in `keys`. Never return placeholder
zeros. Replace the example in `myapp/samples/` with **real output** of your application and the
rows it must produce, then run `crab wrappers test myapp` again; `crab parse` tries one output by
hand. The wrapper lives in one of two places:

- `crab-wrappers/` (the first folder of `CRAB_PATH_WRAPPERS`, so the default after `source env.sh`):
  a wrapper others can use. Send it as a pull request to crab-wrappers with the real sample.
- `CRAB/local/wrappers/` (`crab wrappers new myapp --local`): private, git-ignored. Jobs run on the
  cluster, so the file must be there.

The contract, the binary lookup order and the samples are explained in
[`CRAB/docs/extending/wrappers.md`](CRAB/docs/extending/wrappers.md).

**2. Register the binary.** A receipt records where the binary lives on this machine, its module
loads and an optional launcher. Either run `crab setup` and pick "Register a custom already-installed
benchmark", or in one line:

```bash
crab receipts set myapp --binary /path/to/myapp --pre-run "module load openmpi" --launcher srun
```

- The first argument is the `benchmark_id` that the wrapper declares.
- `--pre-run` (repeatable) is a command run before each launch, normally a `module load`.
- `--launcher` overrides the preset's launcher (`srun` or `mpirun`); leave it out for the default.

The receipt is written to `CRAB/local/receipts/myapp.json` and describes one machine. An
application that is already on `PATH` in the job needs no receipt. See
[`CRAB/docs/extending/receipts.md`](CRAB/docs/extending/receipts.md).

**3. A config block in the template.** If `crab_run_<nodes>` (CPU) or `crab_qe_<nodes>` (GPU)
already has the modules and GPUs your application needs, reuse it. Otherwise add a block under
`configs:` in `configs/leonardo.yaml`:

```yaml
    - name: "myapp_{nodes}"
      nodes: "{nodes}"
      gpus: 4                # drop this line for a CPU-only application
      modules:
        - "some-module"      # the modules your build needs, including one that gives mpirun
```

Then run `./install.sh --no-setup` again to refill the copy. Keep the cluster block name
`leonardo`: it must equal `SBATCHMAN_CLUSTER_NAME`. How the file is built is in
[`CRAB/docs/using/sbatchman-integration.md`](CRAB/docs/using/sbatchman-integration.md#5-get-the-sbatchman-configs-file).

**4. A jobs file.** Make a folder `benchmarks/<yours>/` (two levels below the umbrella root, because
the jobs file loads `../../.local/configs.leonardo.yaml`), copy `benchmarks/blink/smoke.yaml` into it
and edit it:

```yaml
configs: ../../.local/configs.leonardo.yaml
variables:
  nodes:
    - 2
jobs:
  - config: myapp_{nodes}
    tag: myapp-{nodes}
    preprocess: |
      mkdir -p "$SBATCHMAN_JOB_DIR"
      cat > "$SBATCHMAN_JOB_DIR/config.json" <<'JSON'
      {
        "schema_version": 2,
        "global_options": {"numnodes": "{nodes}", "ppn": "4", "name": "myapp-{nodes}"},
        "experiments": {
          "run": {
            "apps": {
              "0": {"path": "myapp/myapp.py", "args": "-n 1000", "collect": true, "start": "0", "end": ""}
            }
          }
        }
      }
      JSON
    command: crab worker --workdir "$SBATCHMAN_JOB_DIR"
```

- `config` is the template's config name; `tag` names the job and its result folder.
- The heredoc writes CRAB's experiment. `path` is the wrapper (`myapp/myapp.py`), `args` the
  application's flags, `numnodes` the allocation (at most the config's `nodes`), `ppn` the ranks per
  node (at most `tasks_per_node`), `"name"` equals `tag`.
- Any other key of an app (for example `input_file`) becomes an attribute of the wrapper. QE does
  this and uses an unquoted heredoc (`<<JSON`) so `$SBATCHMAN_WD`, the folder you launch from, expands.
- To co-run, add apps `"1"`, `"2"`, ... with a `partition`; `qe-noise.yaml` is the example. A job
  holds several experiments that run one after another in the same allocation.
- Run `./install.sh --no-setup` once more: it runs `sbatchman init` in your new folder.

The jobs file shape and the co-run rules are in
[`CRAB/docs/using/sbatchman-integration.md`](CRAB/docs/using/sbatchman-integration.md#6-write-a-campaign).
To check the experiment alone, copy the JSON into a file and run `crab validate config.json`.

**5. Launch from the benchmark folder.**

```bash
cd benchmarks/<yours>
sbatchman launch -f myapp.yaml --dry-run
sbatchman launch -f myapp.yaml
sbatchman status
```

Start with one node count. Read the `Submitted successfully N jobs` line, as above.

**6. Read the results and run again.** Each experiment folder holds `data_app_<i>.csv`: one row per
sample, columns `run_id`, `msg_size` (0 unless the app's `args` have `-msgsize`), your `keys`, then one
`<app>_<metric>_<unit>` column per metric. Read it with a spreadsheet or a notebook, or parse
saved output again with `crab parse`. Compare a baseline with noise only inside one job. To change
and run again, change `tag` and `"name"` together, or use `--force`
([`CRAB/docs/using/sbatchman-integration.md`](CRAB/docs/using/sbatchman-integration.md#9-read-the-results)).
A `PARSE FAILED` line in the job log means the wrapper could not read the output: fix it against a
real sample.

## Update

```bash
git pull
git submodule update --init
./install.sh
```

- `git pull` brings the new pins, `git submodule update --init` moves `CRAB/` and `crab-wrappers/`
  to them, `./install.sh` reinstalls what changed (safe to repeat) and refills the configs copy.
- Do not run `crab update` inside the umbrella: it would move CRAB off the pinned commit.
- A Python venv is not relocatable. If you move the umbrella folder, run `./install.sh` again to
  rebuild the environment. `env.sh` itself finds its own folder.

## Troubleshooting

Start with the job's `stderr.log` and `stdout.log` in its job folder.

| Symptom | Cause | Fix |
|---|---|---|
| `python3 is Python 3.6.8: 3.10 or newer is needed.` | The login node's default Python is too old. | `module load python`, then `./install.sh` again. |
| `Disk quota exceeded`, for example from `git clone` or a job | `$HOME` is full (50 GB quota). QE scratch folders are the usual cause. | Check with `cinQuota` (it lags a few minutes), delete `scratch/` folders of finished jobs (see Known limits), or put the umbrella on a larger filesystem. |
| `ImportError` naming a path outside `CRAB/.venv` | A cluster Python module exports `PYTHONPATH`, and the venv reads it. | `source env.sh` (it unsets `PYTHONPATH` and `PYTHONHOME`); `install.sh` does the same. |
| `crab: command not found`, `sbatchman: command not found`, or `command -v` shows another path | A new shell without the environment. | `source env.sh` from the umbrella root. |
| `install.sh: CRAB/Makefile is missing` | Cloned without submodules. | `git submodule update --init`, then `./install.sh`. |
| `install.sh: the configs template still has unfilled tokens` | The template has a `<UPPER_CASE>` token the installer does not know. | Remove it from `configs/leonardo.yaml`. |
| `no Slurm account: pass --account NAME or create site/local.env ...` (exit 2) | No account, and no terminal to ask on. | `./install.sh --account <YOUR_ACCOUNT>`. |
| `invalid account` from `sbatch` | The account is not yours or not enabled for the partition. | Fix it in `site/local.env`, run `./install.sh` again, relaunch with `--force`. |
| `Skipping job: An identical job already exists`, or `Submitted successfully 0 jobs` | A job with the same cluster, config and tag exists, in any status, archived or not. Also printed when every `sbatch` failed. | Change `tag` and `"name"` together, or `--force`. |
| `Error: No configurations found for cluster '<name>'.` | The cluster block name in the template differs from `SBATCHMAN_CLUSTER_NAME`. | Keep the block named as in `site/leonardo.env` (`leonardo`), run `./install.sh`, `source env.sh`. |
| `Failed to submit job: ...` | `sbatch` failed (for example a transient controller error). The exit code is still 0. | Read the summary count and `sbatchman status`, then launch again with `--force`. |
| `SbatchMan root not found. Please run 'sbatchman init'` | `sbatchman` ran outside a benchmark folder. | `cd benchmarks/<name>`. |
| `No binary for ... Tried: ...` in the job log | No receipt, `binary` key or `PATH` entry for that wrapper. | Register it: `crab setup` or `crab receipts set`. |
| `Cannot find 'mpirun' to detect its MPI` in the job log | The config the job uses loads no MPI module. | Add the module to that config's `modules` in the template. |
| `error in Message Passing (mp) module ... error code 9100` from `pw.x` | The QE module is a GPU build and the job had no GPU. | Use a `crab_qe_<nodes>` config (`gpus: 4`). |
| `symbol lookup error` in `bindings_app_<n>.log`, exit code 127 | Two apps from different module stacks share a job. | Start the receipts' `pre_run` with `module purge`. |
| Job `COMPLETED`, but no or an empty `data_app_0.csv` | A failed run does not fail the job. | Read `bindings_app_0.log`, `error_app_0.log` and the job's `stderr.log`. |
| `crab web` or `sbatchman visualize` will not start: port in use | Another program holds the port (`crab web` 8899 here, `visualize` 8765). | `crab web --port <other port>`; `visualize` cannot change its port. |
| The `visualize` page opens but has no data or no plots | No job of the project is `COMPLETED` (running and failed jobs are skipped), or `visualize` was started in another folder than the fetched results. | `sbatchman status`, then `sbatchman fetch` again once the jobs have finished, in the benchmark folder you start `visualize` from. |
| `Parser script not found` from `sbatchman visualize` | `visualize` was started outside the benchmark folder, so there is no `./parser.py`. | `cd benchmarks/blink` (or `benchmarks/qe`), then `sbatchman visualize`. |
| `unrecognized token "0_Avg"` in the plot builder's SQL | A column name that starts with a digit or contains a dash is not in double quotes. | Write `"0_Avg-Duration_s"`, with the quotes. |
| `crab` or `sbatchman` stops starting after you moved the folder | The venv is not relocatable. | `./install.sh` again. |
| Timings differ between jobs of one campaign | Shared nodes (no `exclusive`). | Add `exclusive: true` to `default_conf` and relaunch with `--force`. |

More rows are in the [CRAB troubleshooting table](CRAB/docs/using/sbatchman-integration.md#troubleshooting).

## Known limits

- **QE scratch size.** `pw.x` writes its working folders, named `scratch/`, inside the experiment
  folders: about 16 GB for `qe-alone.yaml` and about 190 GB for `qe-noise.yaml`. A 50 GB `$HOME`
  cannot hold `qe-noise`, and a full `$HOME` makes `git clone` fail with `Disk quota exceeded`. Put
  the umbrella on a larger filesystem (your scratch or work area) before the QE launch. The
  `scratch/` folders of finished jobs hold no results and can be deleted. List them with
  `find benchmarks/qe/SbatchMan -type d -name scratch -prune`.
- **The fetch route is tested lightly.** `sbatchman fetch` through the laptop's `remotes-config.toml`
  worked against Leonardo for the smoke job's folder only. Large folders and fetches that land on
  different login nodes are not tested.
- **The QE plots were not seen in a browser yet.** The two Blink plots were seen rendering in a
  browser on real Blink noise results. The QE plot definitions return the right rows and build a
  plot through the server's HTTP API on real QE results, but how they look on the page is not
  checked. `visualize` on a login node through an ssh tunnel is untested.
