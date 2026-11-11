# Launch and follow jobs

Submit the jobs of a benchmark, follow them in the queue and run them again after a change.

## Before you start

- You ran `source env.sh` in this shell.
- You are in the benchmark folder: `cd benchmarks/<benchmark>`. Each benchmark folder is one SbatchMan project.

## Launch the jobs

1. Check the jobs without submitting them. Start with the small `smoke.yaml` of Blink.

   ```bash
   sbatchman launch -f smoke.yaml --dry-run
   ```

   The command prints a `Would generate` line for each job.

2. Launch them.

   ```bash
   sbatchman launch -f smoke.yaml
   ```

   The output ends with `Submitted successfully N jobs`. Read `N`: a failed `sbatch` prints `Failed to submit job:` and the exit code stays 0.

3. Follow the jobs.

   ```bash
   sbatchman status
   ```

   The table lists the Slurm job id, status, config and tag of each job. The status is `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` or `TIMEOUT`. Press `r` to refresh and `q` to quit.

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

Next: [Results](results.md).
