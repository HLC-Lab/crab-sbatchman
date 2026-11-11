# Partner umbrella (working title)

CRAB benchmarks co-running HPC applications on a Slurm cluster, and SbatchMan launches the jobs. This repo
installs both, pins matching versions of them, and ships example benchmarks you can run or copy.

## Install on the cluster

Run this on a login node. The pages in `docs/` cover the rest; [Install](docs/install.md) also has the laptop install.

```bash
git clone --recurse-submodules <umbrella-url> <umbrella-dir>
cd <umbrella-dir>
module load python
./install.sh --account <YOUR_ACCOUNT>
source env.sh
```

- `module load python` gives Python 3.10 or newer, which CRAB needs. The installer stops with a message if it is older.
- `./install.sh --account <YOUR_ACCOUNT>` installs CRAB and SbatchMan into `CRAB/.venv` and fills the Slurm configs
  file with your account. It prints every command before it runs it, and it is safe to run again.
- The installer then starts the `crab setup` wizard, which asks which benchmarks to register. Skip it with `--no-setup`.
- The install ends with a self-check that submits no job. It passes when it prints `install.sh: all checks passed`.
- `source env.sh` activates the environment. Run it in every new shell.

Optional last step, to see a real job run (one all-to-all on 2 nodes, submitted to Slurm):

```bash
cd benchmarks/blink && sbatchman launch -f smoke.yaml
```

| Page | What it answers |
|---|---|
| [Install](docs/install.md) | How do I install the umbrella on the cluster and on my laptop? |
| [Add your own benchmark](docs/own-benchmark.md) | How do I add an application of my own? |
| [Launch](docs/launch.md) | How do I submit the jobs and follow them? |
| [Results](docs/results.md) | How do I collect the results and plot them? |
| [Troubleshooting](docs/troubleshooting.md) | What do I do when something fails? |
| [Reference](docs/reference.md) | Which files are in the repo, and which may I change? |
