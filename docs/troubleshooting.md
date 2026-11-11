# Troubleshooting

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

For any other reason, fix the cause it names, then run the installer again. This SbatchMan message means the cluster name in the configs file differs from the one `env.sh` exports:

```text
Error: No configurations found for cluster 'leonardo'.
```

Keep the cluster block named as in `site/leonardo.env` (`SBATCHMAN_CLUSTER_NAME`), run `./install.sh`, then `source env.sh`.
