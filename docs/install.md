# Install

This page installs the umbrella on the cluster, where the jobs run, and on your laptop, where you watch them.

## Before you start

You need a login on a Slurm cluster, Python 3.10 or newer (on a cluster, a module such as `module load python`), git with
submodule support, and a Slurm account you may charge. The laptop install is optional. Four words are new:

| Word | Meaning |
|---|---|
| Wrapper | A Python file that tells CRAB how to start an application and how to read its output. |
| Receipt | A record, written by `crab setup`, of where an application's binary is on this machine and which modules to load. |
| Jobs file | A YAML file in `benchmarks/` that lists jobs for `sbatchman launch -f`. |
| Configs file | The SbatchMan file that holds the Slurm settings (account, partition, nodes, modules) of each config. |

## Install on the cluster

Run this on a login node. Each command is explained below the block.

```bash
git clone --recurse-submodules <umbrella-url> <umbrella-dir>
cd <umbrella-dir>
module load python
./install.sh --account <YOUR_ACCOUNT>
source env.sh
```

- `git clone --recurse-submodules` fetches the umbrella and its two submodules, CRAB and the wrappers. `<umbrella-url>` is the
  address you were given and `<umbrella-dir>` the folder it creates.
- `module load python` gives Python 3.10 or newer. Use the module name your site has for it.
- `./install.sh --account <YOUR_ACCOUNT>` runs the installer. `--account` names the Slurm account to charge. The installer
  saves it in the untracked `site/local.env`, so later runs need no `--account`. Without the flag the installer asks on a
  terminal and otherwise stops with `no Slurm account`.
- `source env.sh` activates the environment. Run it in every new shell: it clears `PYTHONPATH` and `PYTHONHOME`, which a
  cluster Python module sets and which break the virtual environment, activates `CRAB/.venv`, and exports
  `SBATCHMAN_CLUSTER_NAME` and `CRAB_PATH_WRAPPERS`. It prints where `crab` and `sbatchman` come from.

The installer prints every command with a `+` in front before it runs it. It does these steps, in order:

1. Clears `PYTHONPATH` and `PYTHONHOME`, and stops if `python3` is older than 3.10.
2. Runs `git submodule update --init` if the CRAB folder is empty, so a clone without `--recurse-submodules` still works.
3. Links `CRAB/wrappers` to `crab-wrappers/`, so CRAB finds the shared wrappers.
4. Creates `CRAB/.venv`, installs CRAB into it, then installs SbatchMan at the version this umbrella pins.
5. Saves your account, then fills `configs/leonardo.yaml` into `.local/configs.leonardo.yaml` (account, partition, qos, CRAB path).
6. Runs `sbatchman init` in each folder of `benchmarks/` without a `SbatchMan/` yet (each is one project), then writes `env.sh`.
7. Runs the self-check (next section).

Running `./install.sh` again is safe: it prints the same commands and rewrites only what changed.
`--dry-run` prints every command and file write and runs and writes nothing.

### The setup wizard

`crab setup` registers the benchmarks you will run: it turns a recipe into a receipt, which is how a job finds the binary. In
the menu choose "Install or configure a supported benchmark", tick suites with Space, confirm with Enter. Run it after
`source env.sh`. Answers for the shipped benchmarks:

| Prompt | Blink (every Blink jobs file) | Quantum ESPRESSO (the `qe` jobs files) |
|---|---|---|
| Suite | Blink Suite | Quantum ESPRESSO |
| Versions | none asked | Keep only "Quantum ESPRESSO v7" ticked |
| Configuration strategy | `4`, Download and compile from source layout | `3`, Map via cluster Environment Module system |
| Module line | A line that loads a compiler and MPI, for example `module load gcc/12.2.0 openmpi/4.1.6--gcc--12.2.0-cuda-12.2`. CMake 3.16 or newer must be on the path after it: add its module if needed. | `module load profile/chem-phys quantum-espresso` |
| Next prompt | GPU backend: `auto` | Executable the module provides: `pw.x` |

The two module lines are the ones `configs/leonardo.yaml` uses on Leonardo. On another cluster, use the modules that put the
compiler, `mpirun` and Quantum ESPRESSO there. `qe-noise.yaml` also runs Blink next to Quantum ESPRESSO, and the two come from
different module stacks: read [Apps built with different module stacks](../CRAB/docs/using/sbatchman-integration.md#apps-built-with-different-module-stacks)
before you launch it. The other wizard strategies are in [CRAB's installation page](../CRAB/docs/using/installation.md#set-up-benchmarks-crab-setup).
Check the result with `crab list-benchmarks` and `crab wrappers list`. For an application that is not shipped, see
[Add your own benchmark](own-benchmark.md).

## The self-check

The last step of the install checks that everything works. It submits no Slurm job. It prints one line per check, `OK` or
`FAIL`, and a summary. A run that passes prints this on the cluster:

```text
Checking the install (no Slurm job is submitted):
OK python 3.10 or newer in the venv
OK sbatchman 2.0.4 installed in the venv
OK crab resolves inside CRAB/.venv/bin
OK sbatchman resolves inside CRAB/.venv/bin
OK wrappers folders are not empty
OK jobs file benchmarks/blink/smoke.yaml passes crab validate (1 config(s))
...
OK sbatchman launch --dry-run on benchmarks/blink/smoke.yaml (submits nothing)
install.sh: all checks passed
install.sh finished: role cluster
Next: source env.sh
```

There is one `jobs file` line per `*.yaml` file in `benchmarks/`. A failed check prints `FAIL`, its name and the reason. The
later checks still run, the summary says `install.sh: 2 check(s) failed` (2 is the count) and the installer exits with 1.

| Check | A FAIL means | Fix |
|---|---|---|
| `python in the venv` | The environment's Python is older than 3.10. | `module load python`, remove `CRAB/.venv`, run `./install.sh` again. |
| `sbatchman version`, `crab in the venv`, `sbatchman in the venv` | SbatchMan is missing or not the pinned version, or a command does not resolve inside the environment. | Run `./install.sh` again. |
| `wrappers folder` | `crab-wrappers/` or the CRAB link to it is missing or empty. | Run `git submodule update --init`, then the installer again. |
| `jobs file` and a path | A jobs file is not valid YAML, or one of its embedded configs fails `crab validate`. The reason is on the line. | Fix the file named on the line. |
| `sbatchman launch --dry-run on benchmarks/blink/smoke.yaml` | SbatchMan could not read the configs file or the smoke file. The reason is on the line. | Fix the cause it names, then run `./install.sh` again. |

The last check runs `sbatchman launch -f smoke.yaml --dry-run` in `benchmarks/blink`. SbatchMan lists the job it would submit
and submits nothing, but it writes one config script per config into `benchmarks/blink/SbatchMan/configs`, as any launch does.
`--no-check` skips the whole self-check. More failures are in [Troubleshooting](troubleshooting.md); to run the smoke job for
real, see [Launch](launch.md).

## Install on your laptop

The laptop runs `crab web`, a dashboard to write and watch experiments, and `sbatchman visualize`, which plots results. It needs
Python 3.10 or newer and a clone of the same umbrella.

```bash
git clone --recurse-submodules <umbrella-url> <umbrella-dir>
cd <umbrella-dir>
./install.sh --role laptop
source env.sh
```

- `--role laptop` installs CRAB with its web dashboard and SbatchMan with its plots into `CRAB/.venv`. It skips the account
  and the configs file, and writes nothing into your home folder.
- `source env.sh` also sets `CRAB_WEB_PORT` to 8899 unless you set it.

The laptop self-check runs the same checks except the dry-run launch. Then `crab web` serves `http://127.0.0.1:8899` and
`sbatchman visualize` serves `http://127.0.0.1:8765` (fetching and plotting results is in [Results](results.md)).

## Update

```bash
git pull
git submodule update --init
./install.sh
```

- `git pull` brings the umbrella's new pins. `git submodule update --init` moves CRAB and the wrappers to them.
  `./install.sh` reinstalls what changed and refills the configs file.
- Never run `crab update` inside the umbrella: the umbrella pins CRAB and the wrappers to commits that were tested together,
  and CRAB refuses the command there.
- A Python environment cannot be moved. If you move the umbrella folder, run `./install.sh` again.
