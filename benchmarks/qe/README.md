# Quantum ESPRESSO benchmarks

Quantum ESPRESSO `pw.x` alone and against Blink incast noise. Without `disk_io = 'none'`, `pw.x` leaves about 1.6 GB of wavefunction files in every run folder (measured on Leonardo, one node with 4 GPUs). The input sets it, so a run leaves nothing. Both jobs files also set `"retain_files": false`, so CRAB removes the folder of every successful run. A failed run keeps its folder for debugging. Launch as in [Launch](../../docs/launch.md) and read as in [Results](../../docs/results.md).

| File | What it is |
|---|---|
| `qe-alone.yaml` | `pw.x` alone on 2 nodes, the reference run (1 job). |
| `qe-noise.yaml` | `pw.x` against Blink incast noise on 4 nodes (1 job). |
| `qe/` | The `pw.x` input and `get-upf.sh`, which downloads the pseudopotential. |
| `plots.json` | Two starter plots for `sbatchman visualize`. |

The pseudopotential is not in git. Before the first launch, download it once on the login node (compute nodes have no internet):

```bash
benchmarks/qe/qe/get-upf.sh
```

A good result prints `saved ... (sha256 ok)`, or `already there` on a second run. Then check the jobs:

```bash
cd benchmarks/qe && sbatchman launch -f qe-alone.yaml --dry-run
```
