# Run a benchmark

Run a benchmark that is already supported, Blink first, from registering it to finding its results. Run every step on the cluster login node. [Results](results.md) then copies the results to your laptop.

## Before you start

- You installed the umbrella on the cluster, as in [Install](install.md#install-on-the-cluster). The installer saved your Slurm account, so no step here asks for it.
- You connected the laptop to the cluster, as in [Connect](connect.md). Launching needs no connection. Copying the results does.
- You ran `source env.sh` in this shell. Run it again in every new shell.

## Register Blink

Register a benchmark once on each cluster. The wizard writes a receipt, a small file that records where the binary is and which modules it needs. Jobs read it. Any benchmark that `crab setup` offers registers the same way.

```bash
crab setup
```

1. Choose "Install or configure a supported benchmark".
2. Tick the Blink Suite and untick the others.
3. At the strategy prompt, type `4` for "Download and compile from source layout". Enter picks `1`, auto-detect, which does not build Blink. For a binary that is already built, type `2` for "Provide explicit manual path layout" and give its path.
4. At the module prompt, type the Leonardo line. It loads the modules of `crab_run_{nodes}` in `configs/leonardo.yaml`, plus CUDA and CMake for the build. CRAB saves it in the receipt, so jobs load the same modules.

   ```text
   module load gcc/12.2.0 openmpi/4.1.6--gcc--12.2.0-cuda-12.2 cuda/12.2 cmake/3.27.9
   ```

5. At the GPU backend prompt, type `cuda`. CRAB's own documentation checked this answer with that module line on Leonardo. Enter picks `auto`.

On another cluster, change the module answer. At the module prompt type `module load` and the modules of your site: a compiler, an MPI that puts `mpicc` and `mpirun` on `PATH`, and CMake. Leave out the CUDA module on a cluster without GPUs. If `cmake` or `mpicc` is missing, or the module line fails, the wizard says why, waits for Enter and ends without building. Its last panel still says the setup is complete. Run `crab setup` again from step 1. For the GPU question you can type `off` on a cluster without GPUs: it builds Blink for the CPU only, even if a CUDA toolkit is loaded. Enter (`auto`) works too: it gives a CPU-only build when CMake finds no CUDA or HIP toolkit. To find module names, see [Check the limits of your site](presets.md#check-the-limits-of-your-site).

The wizard clones and builds Blink and prints the build log. Then run `crab list-benchmarks`. A good result prints `Installed benchmarks (1):` and the line `blink  (source)`.

## Launch the smoke test

`smoke.yaml` is the jobs file of the smoke test: one all-to-all alone on 2 nodes. The configs file sets a 30-minute limit. Run it first. It shows that the project, the configs file and CRAB's worker all work. Each benchmark folder is one SbatchMan project: run the commands of this section and the next ones in `benchmarks/blink`. For your own benchmark, run the same commands in its folder with your jobs file.

1. See the jobs without submitting them.

   ```bash
   cd benchmarks/blink
   sbatchman launch -f smoke.yaml --dry-run
   ```

   The command prints `Would generate crab_run_2 / a2a-smoke-2` for the job. It then also prints `Submitted successfully 1 jobs.`, which is wrong: nothing is submitted, as its last line `This was a dry-run. No job has run.` says. Confirm with `squeue --me`.

2. Launch the job.

   ```bash
   sbatchman launch -f smoke.yaml
   ```

   A good result prints `Submitted crab_run_2 / a2a-smoke-2` and ends with `Submitted successfully 1 jobs.` Read the number: a failed `sbatch` prints `Failed to submit job:` and the exit code stays 0.

## Follow the jobs

```bash
sbatchman status
```

The table lists the Slurm job id, cluster, status, config, tag, category and command of each job. It asks Slurm again every 90 seconds. Press `r` to ask now, Enter on a job to read its `stdout.log` and `stderr.log`, and `q` to quit. The status is `QUEUED` (waiting in the Slurm queue), `RUNNING`, `COMPLETED` (the job's command exited with 0: the good result), `FAILED` (it exited with another code), `CHECK_FAIL` (the job's check command failed), `FAILED_SUBMISSION` (Slurm refused the job), `CANCELLED` or `TIMEOUT` (the job reached its time limit).

## Run a job again

SbatchMan refuses a job whose cluster, config and tag match a job already in the project, archived and failed jobs included. The launch prints `Skipping job:` and `Submitted successfully 0 jobs`. Change the tag to get a new job: the earlier data stays under the earlier tag.

1. In the jobs file, add a suffix to the `tag` and to the `"name"` in the JSON of `preprocess`. Keep the two equal. In `smoke.yaml`, change `tag: a2a-smoke-{nodes}` to `tag: a2a-smoke-{nodes}-r2`, and `"name": "a2a-smoke-{nodes}"` to `"name": "a2a-smoke-{nodes}-r2"`.
2. Launch the file again.

   ```bash
   sbatchman launch -f smoke.yaml
   ```

To submit an unchanged job again, add `--force`. The run gets a new timestamp folder next to the earlier one.

```bash
sbatchman launch -f smoke.yaml --force
```

## Cancel a job

SbatchMan has no cancel command. Read the job id in `sbatchman status`, then run the Slurm command:

```bash
scancel <job-id>
```

`crab cancel <job-id>` also cancels a Slurm job: it runs `scancel` for an id of digits only.

## Find the results

Each job writes to this folder of the benchmark folder:

```text
SbatchMan/experiments/<cluster>/<config>/<tag>/<timestamp>/
```

It holds the job's `stdout.log` and `stderr.log`, and one folder for each experiment. A finished job has a `data_app_0.csv` with rows in its experiment folder.

Next: [Results](results.md).
