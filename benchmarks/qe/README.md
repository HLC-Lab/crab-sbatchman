# Quantum ESPRESSO benchmarks

This folder is one SbatchMan project (`./install.sh` ran `sbatchman init` here). It holds two jobs
files that run Quantum ESPRESSO `pw.x` through CRAB's worker on Leonardo, and `qe/`, the input
they read. Both use the GPU config `crab_qe_<nodes>` (4 GPUs per node) of
`../../.local/configs.leonardo.yaml`, which `install.sh` fills from `../../configs/leonardo.yaml`:
the Leonardo QE module is a CUDA build and aborts at start without GPUs.

## Before the first launch

Register `qe` with `crab setup` (run it from the umbrella's CRAB environment). On Leonardo the
module command is `module load profile/chem-phys quantum-espresso` and the executable is `pw.x`;
the receipt must load the `profile/chem-phys` profile, or `quantum-espresso` is not found.
`qe-noise.yaml` also runs a Blink incast aggressor, so Blink must be registered too, with a
`pre_run` hook that starts with `module purge` (QE and Blink come from different module stacks).

## Files

| File | What it measures | Jobs |
|---|---|---|
| `qe-alone.yaml` | `pw.x` (a silicon SCF run) alone on 2 nodes, 4 ranks per node: the reference run. The metric is `wall_time`, in seconds. | 1 job, 2 nodes |
| `qe-noise.yaml` | How much a continuous Blink incast slows the same `pw.x` run. QE gets 2 of the 4 nodes, the aggressor the other 2. Baseline and noise run in the same allocation, alternating three times (six experiments, 5 successful runs each). | 1 job, 4 nodes |
| `qe/` | `si-scf.in` and the pseudopotential `Si.pz-vbc.UPF`; see `qe/README.md`. | |

One `pw.x` run takes about 20 to 25 seconds. The jobs files read the input and the pseudopotential
from `qe/` through `$SBATCHMAN_WD`, the folder you launch from, so launch from this folder.

## Launch

From the umbrella root run `source env.sh` once per shell: it activates the environment and exports
`SBATCHMAN_CLUSTER_NAME=leonardo`, which must equal the cluster block name of the configs file. Then,
from this folder:

```bash
source env.sh
cd benchmarks/qe
sbatchman launch -f qe-alone.yaml --dry-run
sbatchman launch -f qe-alone.yaml
sbatchman status
```

## Run a job again

SbatchMan skips a job identical to one that already ran in the project. To run it again either:

- change the `tag` AND the `"name"` in the heredoc's `global_options` together (they must stay
  equal), then launch as usual; or
- launch with `sbatchman launch -f <file> --force`.

## Where results land

`SbatchMan/experiments/<cluster>/<config>/<tag>/<timestamp>/` inside this folder, for example
`SbatchMan/experiments/leonardo/crab_qe_2/qe-alone-2n/<timestamp>/`. In it: `config.json`, one
folder per experiment with `data_app_0.csv` (the QE measurements), `crab_run.json` and SbatchMan's
`metadata.yaml`.

## Plots

`plots.json` here holds two starter plots (wall time per run, and average wall time per job tag)
for `sbatchman visualize`, with `parser.py` (a symlink to `../parser.py`). On the laptop, in this
folder, run `sbatchman fetch` and then `sbatchman visualize`, and open `http://127.0.0.1:8765`. The
tables, the columns and the limits are in "Explore results with `sbatchman visualize`" in the
[umbrella README](../../README.md).

## Known limitation: disk use

`pw.x` writes its scratch files (wavefunctions, charge density) into the experiment folders, which
sit inside this project. `qe-alone.yaml` writes about 16 GB there and `qe-noise.yaml` about
190 GB. If this folder is under your home directory, that can exceed
the quota and make the job fail. Put the umbrella on a larger filesystem (for example your scratch
or work area) before launching, and remove the scratch of finished jobs once you have the results.

## What you may change

- The `nodes` list under `variables`. Every value needs a `crab_qe_<nodes>` config, so keep it
  inside the `nodes` list of `../../configs/leonardo.yaml`.
- The `tag`, together with the `"name"` in the heredoc (see above).
- The `args` of an app, and `minruns` in `qe-noise.yaml` (raise it for a real study, and `time` in
  the configs template with it).
