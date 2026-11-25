# Troubleshooting

The stages are Install, Self-check, Launch and Results.

Messages are quoted as the program prints them. Where a message holds a version or a path, the one you see can differ.

## Install

### "python3 is Python 3.6.8: 3.11 or newer is needed"

```text
python3 is Python 3.6.8: 3.11 or newer is needed. On a cluster run 'module load python' first. On a Mac install Python 3.11 or newer from python.org or Homebrew and put it first on PATH. Then run install.sh again.
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

The installer found no account and has no terminal to ask on. Pass it (the installer checks it first and saves it in `site/local.env`):

```bash
./install.sh --account <YOUR_ACCOUNT>
```

### "the account ... is not among the Slurm accounts"

```text
install.sh: the account <YOUR_ACCOUNT> is not among the Slurm accounts of user <your-user> (sacctmgr). Pass the right one with --account NAME, or --skip-account-check to skip this lookup.
```

`sacctmgr` answered, and the name you gave is not one of your Slurm accounts (the comparison ignores case). The installer stops before it installs anything. Run it again with an account you have:

```bash
./install.sh --account <YOUR_ACCOUNT>
```

If your site lists accounts in another way, skip the lookup:

```bash
./install.sh --account <YOUR_ACCOUNT> --skip-account-check
```

### "the account ... was not checked against Slurm"

```text
install.sh: note: sacctmgr is not on PATH, so the account <YOUR_ACCOUNT> was not checked against Slurm.
```

This is a note, not an error: the install goes on. It also prints with the words `sacctmgr gave no answer` (the accounting service did not reply) or `(--skip-account-check)` (you asked to skip the lookup). A wrong account then shows up at launch, as in [Launch](#failed-to-submit-job-job-submission-failed-with-error-code-1).

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

### "crab: command not found"

The environment is not active in this shell. Run this from the umbrella folder, in every new shell:

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
FAIL python in the venv: CRAB/.venv/bin/python needs 3.11 or newer, found: Python 3.6.8
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

The check covers the first and the last combination of the variables of each jobs file. Run `./install.sh --full-check` to check every combination. The line names the jobs file and the reason: the file is not valid YAML, a job has no config, a config has an unfilled variable or is not valid JSON, or `crab validate` rejects it (its message follows `crab validate:`). Fix the file named on the line, then run the installer again.

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

The cluster name SbatchMan uses (`SBATCHMAN_CLUSTER_NAME`) matches no cluster block of the configs file. Name the block with the value of `SBATCHMAN_CLUSTER_NAME` in `site/local.env`, or in `site/leonardo.env` when `site/local.env` does not set it. Then run `./install.sh` and `source env.sh`.

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

The command prints a long Python error in a box. On Linux its last line is `OSError: [Errno 98] Address already in use`. Another program listens on port 8765, and `sbatchman visualize` has no option to change its port. List the programs that hold it:

```bash
lsof -nP -i :8765
```

`-i :8765` selects the port. `-n` and `-P` keep numbers instead of host and service names. A good result is a table whose `COMMAND` and `PID` columns name the program, with `LISTEN` in its last column.

A Linux machine without `lsof` has `ss`:

```bash
ss -ltnp 'sport = :8765'
```

`-l` lists listening sockets, `-t` only TCP, `-n` keeps numbers and `-p` adds the program. A good result is a `LISTEN` line for port 8765 that ends with `users:` and the program's name.

Without root, `lsof` and `ss` show only your own programs. `lsof` prints nothing for a program of another user, and `ss` shows the `LISTEN` line without `users:`. Then ask the administrator of that machine, or restart it. Otherwise stop the program, then start `sbatchman visualize` again. If it is `crab web`, start it again from a shell where you ran `source env.sh`: it then uses port 8899.

### The page opens with no data or no plots

`sbatchman visualize` reads the jobs of the folder you start it from, and only those with status `COMPLETED`, `FAILED`, `TIMEOUT` or `CHECK_FAIL`. Check the status, copy the results, then start it from the benchmark folder:

```bash
sbatchman status
```

### "Parser script not found:"

The folder you started `sbatchman visualize` in has no `parser.py`. Go into a benchmark folder, then start it again:

```bash
cd <laptop-dir>/benchmarks/<benchmark>
```

A folder you made yourself needs one: [Use the shared parser](plots.md#use-the-shared-parser) links it.

### "✗ ? failed (rsync exit N)"

`sbatchman fetch` prints this for a `[[clusters.fetch_dirs]]` block that failed. The `?` is the block's `alias`, which a block without one shows as `?`. rsync prints its reason in the lines before it. Check that `ssh <your-user>@<login-host>` works from the same shell and that `remote` is a folder that exists on the cluster. Login nodes rotate, and a node that answers with a new host key stops the fetch the same way.

### "parser: ...: file skipped (no data rows)"

The job ended, but its `data_app_0.csv` has no rows, so the plots stay empty. A failed run does not fail the job. Read `bindings_app_0.log` and `error_app_0.log` in that experiment folder, and the job's `stderr.log`.

### `sbatchman visualize` runs out of memory or is slow with many jobs

`sbatchman visualize` keeps every parsed row in memory while it builds its database. That costs about 2 KB per row at the peak, so 500000 rows need about 1 GB. Start it from a benchmark folder with fewer jobs, or on a machine with more memory.

### `sbatchman fetch` takes minutes

The first fetch of 100000 small files and 600 MB took about 7 minutes from a laptop to a login node. A repeat with nothing new took about 1 minute. Later fetches send only the new files.
