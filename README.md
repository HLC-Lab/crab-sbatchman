# Partner umbrella (working title)

CRAB benchmarks co-running HPC applications on a Slurm cluster. SbatchMan creates, launches and monitors the Slurm jobs that run them.
This repo, the umbrella, installs both at matching versions and ships example benchmarks.

## Install on the cluster

On a login node:

```bash
git clone --recurse-submodules <umbrella-url> <umbrella-dir>
cd <umbrella-dir>
module load python
./install.sh --account <YOUR_ACCOUNT>
source env.sh
```

[Install](docs/install.md#install-on-the-cluster) explains each placeholder. The installer saves the account, so later runs need no `--account`.
Run `source env.sh` in every new shell. A pass of the final self-check prints `install.sh: all checks passed`.
If a check fails, see [Troubleshooting](docs/troubleshooting.md).

## Next

Register the benchmarks you run in [Register a benchmark](docs/benchmarks.md).

Optional: run one job to see it work. It needs Blink [registered](docs/benchmarks.md#register-a-supported-benchmark) and submits one 2-node job with a 30-minute limit.

```bash
cd benchmarks/blink && sbatchman launch -f smoke.yaml
```

| Page | What it answers |
|---|---|
| [Install](docs/install.md) | How do I install the umbrella on the cluster and on my laptop? |
| [Register a benchmark](docs/benchmarks.md) | How do I make a benchmark's binary known to the jobs? |
| [Write a campaign](docs/campaigns.md) | How do I describe the jobs a benchmark runs? |
| [Launch](docs/launch.md) | How do I submit the jobs and follow them? |
| [Results](docs/results.md) | How do I collect the results and plot them? |
| [Troubleshooting](docs/troubleshooting.md) | What do I do when something fails? |
| [Reference](docs/reference.md) | Which files are in the repo, and which can I change? |
