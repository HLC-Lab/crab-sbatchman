# Quantum ESPRESSO benchmarks

Quantum ESPRESSO `pw.x` alone and against Blink incast noise. It writes `scratch/` folders under `SbatchMan/`, about 16 GB for `qe-alone.yaml` and 190 GB for `qe-noise.yaml`: launch from a large filesystem and delete the folders of finished jobs. Launch as in [Launch](../../docs/launch.md) and read as in [Results](../../docs/results.md).

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
