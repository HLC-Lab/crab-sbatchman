# Quantum ESPRESSO benchmarks

Quantum ESPRESSO `pw.x` alone and against Blink incast noise, and `cp.x` alone. Without `disk_io = 'none'`, `pw.x` leaves about 1.6 GB of wavefunction files in every run folder (measured on Leonardo, one node with 4 GPUs). The input sets it, so a run leaves nothing. Every jobs file also sets `"retain_files": false`, so CRAB removes the folder of every successful run. A failed run keeps its folder for debugging. Launch as in [Launch](../../docs/launch.md) and read as in [Results](../../docs/results.md).

| File | What it is |
|---|---|
| `qe-alone.yaml` | `pw.x` alone on 2 nodes, the reference run (1 job). |
| `qe-noise.yaml` | `pw.x` against Blink incast noise on 4 nodes (1 job). |
| `cp-alone.yaml` | `cp.x` (damped electron dynamics, 250 steps) alone on 1 node, about 20 s per run. It writes a restart folder of about 190 MB per run, which `"retain_files": false` removes (1 job). |
| `qe/` | The `pw.x` and `cp.x` inputs and `get-upf.sh`, which downloads the pseudopotential. |
| `plots.json` | Two starter plots for `sbatchman visualize`. |

## Why 4 nodes

`pw.x` needs 2 nodes for its traffic to cross the network. On 1 node it never leaves the node and the aggressor cannot reach it. The Blink aggressor gets the other 2 nodes. The nodes are exclusive, so nothing else runs there. On shared nodes the noise showed no slowdown.

Ask Slurm to put the 4 nodes under one switch by exporting this variable in front of the launch (SbatchMan has no setting for it, and `sbatch` reads it like `--switches`):

```bash
SBATCH_REQ_SWITCH=1 sbatchman launch -f qe-noise.yaml
```

Slurm may ignore it on a topology without switch tiers. After the job, check which nodes it got:

```bash
sacct -j <job id> -X -o JobID,NodeList
```

The pseudopotential is not in git. Before the first launch, download it once on the login node (compute nodes have no internet):

```bash
benchmarks/qe/qe/get-upf.sh
```

A good result prints `saved ... (sha256 ok)`, or `already there` on a second run. Then check the jobs:

```bash
cd benchmarks/qe && sbatchman launch -f qe-alone.yaml --dry-run
```
