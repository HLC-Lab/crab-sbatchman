# Blink benchmarks

Blink microbenchmarks that measure how much noise slows an all-to-all. Launch the jobs as in [Run a benchmark](../../docs/launch.md) and read them as in [Results](../../docs/results.md).

| File | What it is |
|---|---|
| `smoke.yaml` | An all-to-all alone on 2 nodes (1 job). Run it first. |
| `blink-noise.yaml` | The all-to-all against incast noise on 4 nodes (1 job). |
| `a2a-vs-incast.yaml` | The same measurement for 4, 8 and 16 nodes and four message sizes (12 jobs). |
| `a2a-vs-a2a.yaml` | The same sweep with all-to-all noise (12 jobs). |

```bash
cd benchmarks/blink && sbatchman launch -f smoke.yaml --dry-run
```
