# Troubleshooting

The stages are Install, Self-check, Launch and Results.

Messages are quoted as the program prints them. Where a message holds a version or a path, the one you see can differ.

## Install

### "python3 is Python 3.6.8: 3.10 or newer is needed"

```text
python3 is Python 3.6.8: 3.10 or newer is needed. On a cluster run 'module load python' first, then run install.sh again.
```

The login node's default Python is too old. Load a newer one and run the installer again:

```bash
module load python
./install.sh
```

### "no Slurm account"

```text
no Slurm account: pass --account NAME or create site/local.env with SLURM_ACCOUNT="NAME"
```

The installer found no account and has no terminal to ask on. Pass it (the installer saves it in `site/local.env`):

```bash
./install.sh --account <YOUR_ACCOUNT>
```

### The installer rejects the account name

```text
install.sh: the account may only contain letters, digits, '_', '.' and '-'
```

The account name has another character, such as a space. Run the installer again with the exact account name.

### "CRAB/Makefile is missing"

```text
CRAB/Makefile is missing. Run 'git submodule update --init' and try again.
```

The clone has no submodules. Fetch them, then run the installer again:

```bash
git submodule update --init
./install.sh
```

### "the configs template still has unfilled tokens"

```text
install.sh: the configs template still has unfilled tokens:
```

The message ends with the tokens it found. `configs/leonardo.yaml` holds a token in angle brackets and capitals that the installer does not know. Remove or rename it in that file, then run the installer again.

### ImportError naming a path outside CRAB/.venv

A cluster Python module sets `PYTHONPATH`, and the environment reads it. `source env.sh` clears it in your shell. The installer clears it for its own run.

```bash
source env.sh
```

### The crab and sbatchman commands stop starting after you move the umbrella folder

The environment in `CRAB/.venv` cannot move with the folder. Run the installer again from the new place:

```bash
./install.sh
```

### "Disk quota exceeded"

Your home folder is full, so `git clone` or the install fails. Free space, or clone the umbrella into a larger filesystem such as your scratch or work area.

## Self-check

A failed check does not stop the later ones. The installer prints `install.sh: 2 check(s) failed` (2 is the count of failed checks) and exits with status 1. Run it with `--no-check` to skip the check.

### "FAIL python in the venv"

```text
FAIL python in the venv: CRAB/.venv/bin/python needs 3.10 or newer, found: Python 3.6.8
```

The environment was built with an old Python. Load a newer one, remove the environment and install again:

```bash
module load python
rm -rf CRAB/.venv
./install.sh
```

### "FAIL sbatchman version"

```text
FAIL sbatchman version: found 2.0.3, expected 2.0.4
FAIL sbatchman version: pip show sbatchman failed:
```

SbatchMan is missing from the environment or is not the version the umbrella pins. Run the installer again:

```bash
./install.sh
```

### "FAIL crab in the venv" and "FAIL sbatchman in the venv"

```text
FAIL crab in the venv: it resolves to nothing, not CRAB/.venv/bin/crab
```

The command is not in `CRAB/.venv/bin`. A command of another install, if there is one, answers instead. Run the installer again:

```bash
./install.sh
```

### "FAIL wrappers folder"

```text
FAIL wrappers folder: crab-wrappers is empty (run: git submodule update --init)
```

`crab-wrappers` or the link `CRAB/wrappers` is missing or empty. Fetch the submodule, then run the installer again:

```bash
git submodule update --init
./install.sh
```

### "FAIL jobs file"

```text
FAIL jobs file benchmarks/blink/smoke.yaml: it has no 'jobs' list
```

The line names the jobs file and the reason: the file is not valid YAML, a job has no config, a config has an unfilled variable or is not valid JSON, or `crab validate` rejects it (its message follows `crab validate:`). Fix the file named on the line, then run the installer again.

### "FAIL sbatchman launch --dry-run"

```text
FAIL sbatchman launch --dry-run on benchmarks/blink/smoke.yaml: benchmarks/blink/smoke.yaml is missing
```

The reason follows the colon. A missing file is part of the clone: restore it.

```bash
git checkout -- benchmarks/blink/smoke.yaml
```

For any other reason, fix the cause it names, then run the installer again. For `No configurations found for cluster`, see [Launch](#launch).

## Launch

Read the line `Submitted successfully N jobs`: the exit code of `sbatchman launch` is 0 even when `N` is 0.

### "Skipping job: An identical job already exists"

```text
Skipping job: An identical job already exists for config 'crab_run_2' with tag 'a2a-smoke-2'.
Use '--force' to submit it anyway.
```

A job with the same cluster, config and tag is already in the project, in any status. Change the tag or add `--force`, as in [Run a job again](launch.md#run-a-job-again).

### "Error: No configurations found for cluster 'leonardo'."

The cluster name SbatchMan uses (`SBATCHMAN_CLUSTER_NAME`) matches no cluster block of the configs file. Keep the block named as in `site/leonardo.env`, run `./install.sh`, then `source env.sh`.

### "Failed to submit job: Job submission failed with error code 1."

```text
Failed to submit job: Job submission failed with error code 1.
Output stream:
Error stream:
```

`sbatch` refused the job. The scheduler's reason follows `Error stream:`, and SbatchMan keeps it in the job's `stderr.log`. Fix the reason: an `invalid account` means the account in `site/local.env` is wrong, so correct it and run `./install.sh`.
Then launch again with `--force`, because the failed job counts as an existing one.

### "SbatchMan root not found"

The message goes on with `run 'sbatchman init'`. The command ran outside a benchmark folder. Go into one:

```bash
cd benchmarks/<benchmark>
```

### A job shows FAILED or TIMEOUT in sbatchman status

Read `stderr.log` and `stdout.log` in the job folder, `SbatchMan/experiments/<cluster>/<config>/<tag>/<timestamp>/`. The files `bindings_app_0.log` and `error_app_0.log` in each experiment folder hold the output of each app.

`TIMEOUT` means Slurm stopped the job at its `time` limit, 30 minutes in `configs/leonardo.yaml`. Raise `time` there and run `./install.sh`.
Then launch again with `--force`.

## Results

### `sbatchman visualize` does not start because port 8765 is in use

Another program listens on the port, and `sbatchman visualize` cannot change its port. Stop that program. If it is `crab web`, start it again from a shell where you ran `source env.sh`: it then uses port 8899.

### The page opens with no data or no plots

`sbatchman visualize` reads the jobs of the folder you start it from, and only those with status `COMPLETED`, `FAILED`, `TIMEOUT` or `CHECK_FAIL`. Check the status, copy the results, then start it from the benchmark folder:

```bash
sbatchman status
```

### "Parser script not found:"

`sbatchman visualize` reads `./parser.py`, and only the benchmark folders hold it. Go into one, then start `sbatchman visualize` again:

```bash
cd benchmarks/<benchmark>
```

### "✗ ? failed (rsync exit N)"

`sbatchman fetch` prints this for a `[[clusters.fetch_dirs]]` block without an `alias`, so the name shows as `?`. rsync prints its reason in the lines before it. Check that `ssh <your-user>@<login-host>` works from the same shell and that `remote` is a folder that exists on the cluster. Login nodes rotate, and a node that answers with a new host key stops the fetch the same way.

### "parser: ...: file skipped (no data rows)"

The job ended, but its `data_app_0.csv` has no rows, so the plots stay empty. A failed run does not fail the job. Read `bindings_app_0.log` and `error_app_0.log` in that experiment folder, and the job's `stderr.log`.
