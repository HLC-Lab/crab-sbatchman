# Install

Install the umbrella twice: on the cluster login node, where the jobs run, and on your laptop, where you plot the results and run the dashboard.

## Before you start

- A login on Leonardo. The shipped Slurm configuration is for that cluster.
- A Slurm account you can charge.
- A laptop that can ssh to the login node.
- Python 3.11 or newer on both. On a cluster this is a module, such as `module load python`. On a Mac, install it from python.org or Homebrew.
- git on both.

## Install on the cluster

The login node needs two things before you start:

- Python 3.11 or newer. After `module load python`, run `python3 --version`. A good result is `Python 3.11.x` or a higher number. With an older one the installer stops at once and says which version it found.
- Outbound https access. `git clone` and the submodule update fetch from `github.com`, and `pip` downloads the packages from the Python package index. If your login node cannot reach them, the install stops there; for the `pip` part see `--offline` in [Reference](reference.md#installsh).

On a login node:

```bash
git clone --recurse-submodules https://github.com/HLC-Lab/crab-sbatchman.git
cd crab-sbatchman
module load python
./install.sh --account <YOUR_ACCOUNT>
source env.sh
```

Replace `<YOUR_ACCOUNT>` with the Slurm account to charge.

The installer checks the account first, with `sacctmgr` when it is on `PATH`. Add `--skip-account-check` if the lookup is wrong for your site. The installer saves the account, so later runs need no `--account`. Run `source env.sh` in every new shell. Add `--dry-run` to print the commands without running them.

The install ends with a self-check that submits no job. A pass prints `install.sh: all checks passed`. If a check fails, see [Troubleshooting](troubleshooting.md).

## Install on your laptop

The laptop is part of the setup: it runs the dashboard, copies the results with `sbatchman fetch` and draws the plots.

```bash
git clone --recurse-submodules https://github.com/HLC-Lab/crab-sbatchman.git
cd crab-sbatchman
./install.sh --role laptop
source env.sh
```

The install prints hundreds of lines while it works, including warnings that are normal. Wait until the prompt returns, then look for the pass line `install.sh: all checks passed`. After it come `install.sh finished: role laptop` and `Next: source env.sh`. A failed run has `FAIL` lines for the checks that failed, then `install.sh: N check(s) failed` in place of the pass line, where N is a number. `Next: source env.sh` prints even then, so it is not a sign of a pass. For a failure, see [Troubleshooting](troubleshooting.md).

`crab web` serves the dashboard on port 8899. `sbatchman visualize` serves the result plots on port 8765.

Next: [Connect](connect.md).

## Update

```bash
git pull
git submodule update --init
./install.sh
```

On a laptop, run `./install.sh --role laptop` instead: a bare `./install.sh` runs the cluster role.

Do not run `crab update` in the umbrella: it pins CRAB and the wrappers to tested commits.
