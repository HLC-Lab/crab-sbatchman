# `crab-sbatchman`

CRAB benchmarks co-running HPC applications on a Slurm cluster. SbatchMan creates, launches and monitors the Slurm jobs that run them.
This repo, the umbrella, installs both at matching versions and ships example benchmarks.

## Where to start

Read [Start here](docs/index.md), then [Install](docs/install.md): it has every step for the cluster and for your laptop. First clone the umbrella:

```bash
git clone --recurse-submodules https://github.com/HLC-Lab/crab-sbatchman.git
```

| Page | What it answers |
|---|---|
| [Start here](docs/index.md) | What is this repo, and which page do I read first? |
| [Install](docs/install.md) | How do I install the umbrella on the cluster and on my laptop? |
| [Connect](docs/connect.md) | How do I tell the dashboard and SbatchMan where the cluster is? |
| [Register a benchmark](docs/benchmarks.md) | How do I make a benchmark's binary known to the jobs? |
| [Write a campaign](docs/campaigns.md) | How do I describe the jobs a benchmark runs? |
| [Launch](docs/launch.md) | How do I submit the jobs and follow them? |
| [Results](docs/results.md) | How do I collect the results and plot them? |
| [Troubleshooting](docs/troubleshooting.md) | What do I do when something fails? |
| [Reference](docs/reference.md) | Which files are in the repo, and which can I change? |
