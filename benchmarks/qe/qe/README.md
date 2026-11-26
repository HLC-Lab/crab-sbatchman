# Quantum ESPRESSO input for the QE benchmarks

The jobs files `qe-alone.yaml` and `qe-noise.yaml` (one folder up) run Quantum ESPRESSO `pw.x` on
this input.

| File | What it is |
|---|---|
| `si-scf.in` | A `pw.x` self-consistent-field input for a 128-atom silicon supercell (2x2x4 diamond cells of 10.26 bohr, `ecutwfc = 60`, a 2x2x1 k-point grid). One run takes about 20 s on one Leonardo node with 4 GPUs. `disk_io = 'none'` keeps `pw.x` from writing wavefunction files (about 1.6 GB per run without it, measured on Leonardo). |
| `si-cp.in` | A `cp.x` input on the same 128-atom silicon cell (`ecutwfc = 30`, 250 steps of damped electron dynamics, read by `cp-alone.yaml`). One run takes about 20 s on one Leonardo node with 4 GPUs. `cp.x` writes a restart folder of about 190 MB per run even with `disk_io = 'none'`, so the jobs file sets `"retain_files": false`. |
| `get-upf.sh` | Downloads `Si.pz-vbc.UPF` into this folder and checks its sha256. Run it on the login node before the first launch. |
| `Si.pz-vbc.UPF` | The silicon LDA norm-conserving pseudopotential `si-scf.in` names under `ATOMIC_SPECIES`. It is not in git (`.gitignore` lists it, its licence is unclear): `get-upf.sh` fetches it from the Quantum ESPRESSO pseudopotential library, <https://pseudopotentials.quantum-espresso.org/upf_files/Si.pz-vbc.UPF>. |
| `README.md` | This file. |

Run `get-upf.sh` once on the login node, from the umbrella folder:

```bash
benchmarks/qe/qe/get-upf.sh
```

It prints `saved ... (sha256 ok)`. It stops with exit code 1 and deletes the download when the sha256 differs from the expected one. A second run prints `already there` and changes nothing. Without the file `pw.x` stops at start, so run it before the first `sbatchman launch`.

The jobs files read both through `$SBATCHMAN_WD`, the folder you launch from (`benchmarks/qe`):
`input_file` and `pseudo_dir` point at this folder, so nothing needs copying. The CRAB wrapper rewrites the `outdir` and
`pseudo_dir` lines of the input into the run folder, which is why the input carries placeholder
values for them. No download happens on a compute node: the pseudopotential must already be here, see `get-upf.sh` above.

Both jobs files use the `crab_qe_<nodes>` config of `.local/configs.leonardo.yaml` (filled by `install.sh` from `configs/leonardo.yaml`), not `crab_run_<nodes>`.
The only QE module on Leonardo is a CUDA build behind the `profile/chem-phys` profile
(`module load profile/chem-phys quantum-espresso`): without a GPU, `pw.x` aborts at start with
`error in Message Passing (mp) module, error code 9100`. `crab_qe_<nodes>` therefore requests 4 GPUs
per node and loads that module. The receipt `crab setup` writes must load the profile too, or
`module load quantum-espresso` finds nothing.

`qe-noise.yaml` also needs the Blink receipt's `pre_run` hook to start with `module purge`
(`"pre_run": ["module purge", "module load gcc openmpi"]` in `CRAB/local/receipts/blink.json`), see
"Apps built with different module stacks" in `CRAB/docs/using/sbatchman-integration.md`.

The input is sized from a timing on Leonardo (one node, 4 A100 GPUs, 4 MPI ranks): CRAB repeats an
experiment until it converges (10 successful runs by default; `qe-noise.yaml` asks for 5) and
`qe-noise.yaml` runs six experiments in one job under a 30-minute limit, so one run has to stay
short. To make a run longer or shorter, change the supercell, `ecutwfc` (the plane-wave cutoff, in
Ry) or the k-point grid on the `K_POINTS` line, and time it on the cluster.

Disk: with `disk_io = 'none'` a run leaves nothing but a few KB. The jobs files also set `"retain_files": false`, so CRAB deletes the folder of every successful run, `pw.out` included. A failed run keeps its folder for debugging.
