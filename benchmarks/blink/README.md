# Blink benchmarks

This folder is one SbatchMan project (`./install.sh` ran `sbatchman init` here). It holds four
jobs files that run [Blink](../../crab-wrappers/blink/README.md) microbenchmarks through CRAB's
worker on Leonardo. All four use the CPU config `crab_run_<nodes>` of
`../../.local/configs.leonardo.yaml`, which `install.sh` fills from `../../configs/leonardo.yaml`.

## Files

| File | What it measures | Jobs |
|---|---|---|
| `smoke.yaml` | An all-to-all (`alltoall_b`) alone on 2 nodes, 4 ranks per node, 1 MiB messages, 100 iterations. Run it first: it shows that the project, the configs file and CRAB's worker all work. | 1 job, 2 nodes |
| `blink-noise.yaml` | How much continuous incast noise slows an all-to-all. The victim gets 2 of the 4 nodes, the aggressor the other 2; 1 MiB messages. Baseline and noise run in the same allocation, alternating three times (six experiments). | 1 job, 4 nodes |
| `a2a-vs-incast.yaml` | The same measurement swept over `nodes` 4, 8, 16 and `msgsize` 1 KiB, 64 KiB, 1 MiB, 4 MiB. | 12 jobs, 4 to 16 nodes |
| `a2a-vs-a2a.yaml` | The same sweep with all-to-all noise instead of incast. | 12 jobs, 4 to 16 nodes |

Every job asks for 30 minutes (`time` in the configs template) and runs its experiments back to
back, so the largest sweep jobs (16 nodes, 4 MiB) may need a longer `time`: raise it in
`../../configs/leonardo.yaml` and run `./install.sh` again.

## Launch

From the umbrella root run `source env.sh` once per shell: it activates the environment and exports
`SBATCHMAN_CLUSTER_NAME=leonardo`, which must equal the cluster block name of the configs file. Then,
from this folder, a dry run first:

```bash
source env.sh
cd benchmarks/blink
sbatchman launch -f smoke.yaml --dry-run
sbatchman launch -f smoke.yaml
sbatchman status
```

## Run a job again

SbatchMan skips a job identical to one that already ran in the project. To run it again either:

- change the `tag` AND the `"name"` in the heredoc's `global_options` together (they must stay
  equal), then launch as usual; or
- launch with `sbatchman launch -f <file> --force`.

## Where results land

`SbatchMan/experiments/<cluster>/<config>/<tag>/<timestamp>/` inside this folder, for example
`SbatchMan/experiments/leonardo/crab_run_4/blink-noise-4n-1048576B/<timestamp>/`. In it:
`config.json` (what the job ran), one folder per experiment (`r1_baseline/`, `r1_noise/`, ...)
with `data_app_0.csv` (the victim's measurements), `crab_run.json` (the worker's summary) and
SbatchMan's `metadata.yaml`.

## What you may change

- The `nodes` list under `variables`. Every value needs a `crab_run_<nodes>` config, so keep it
  inside the `nodes` list of `../../configs/leonardo.yaml`.
- The `tag`, together with the `"name"` in the heredoc (see above).
- The `args` of an app, for example `-msgsize` or `-iter` of the victim.

Change anything else (allocation, experiment order, partitions) only if you keep the victim and
the allocation identical in every experiment of a job: the comparison depends on it.
