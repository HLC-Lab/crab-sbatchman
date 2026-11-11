# Write a campaign

A campaign is a jobs file that SbatchMan launches. Write one by hand, or in the `crab web` dashboard.

## Before you start

- The umbrella installed on the cluster (see [Install](install.md)), with `source env.sh` run in your shell.
- A benchmark you can run (see [Register a benchmark](benchmarks.md)).

## Add your config

The jobs file names a SbatchMan config, which holds the modules and the GPUs of its jobs. Skip this section if `crab_run_{nodes}` (CPU) or `crab_qe_{nodes}` (4 GPUs per node) fits your application.

1. Add a block under `configs:` in `configs/leonardo.yaml`. Edit the template, never the filled copy in `.local/`.

   ```yaml
       - name: "myapp_{nodes}"
         nodes: "{nodes}"
         gpus: 4                # drop this line for a CPU-only application
         modules:
           - "some-module"      # include one that puts mpirun on PATH
   ```

2. Refill the copy:

   ```bash
   ./install.sh
   ```

The name is what a job writes in its `config:` key. Every `nodes` value a job uses must be in the `nodes` list at the top of the template.

## Write the jobs file by hand

1. Make the folder `benchmarks/<benchmark>`. It sits two levels under the umbrella root, because the file loads `../../.local/configs.leonardo.yaml`.
2. Save this file in it as `<job>.yaml`. It is `benchmarks/blink/smoke.yaml` without the comments.

   ```yaml
   configs: ../../.local/configs.leonardo.yaml
   variables:
     nodes:
       - 2
   jobs:
     - config: crab_run_{nodes}
       tag: a2a-smoke-{nodes}
       preprocess: |
         mkdir -p "$SBATCHMAN_JOB_DIR"
         cat > "$SBATCHMAN_JOB_DIR/config.json" <<'JSON'
         {
           "schema_version": 2,
           "global_options": {"numnodes": "{nodes}", "ppn": "4", "name": "a2a-smoke-{nodes}"},
           "experiments": {
             "run": {
               "apps": {
                 "0": {"path": "blink/alltoall/alltoall_b.py", "args": "-msgsize 1048576 -iter 100",
                       "collect": true, "start": "0", "end": ""}
               }
             }
           }
         }
         JSON
       command: crab worker --workdir "$SBATCHMAN_JOB_DIR"
   ```

3. Change the keys you need:

   | Key | Meaning |
   |---|---|
   | `variables` | SbatchMan runs one job per value. Write `{nodes}` where the value goes. |
   | `config` | The name of a config in the configs file. |
   | `tag` | The job name and its result folder. Keep it equal to `"name"` in the JSON. |
   | `"numnodes"`, `"ppn"` | The nodes and the ranks per node. Stay within the config's `nodes` and `tasks_per_node`. |
   | `"path"`, `"args"` | The wrapper and its flags. |

4. Run `./install.sh` once more. It runs `sbatchman init` in the new folder and checks every jobs file with `crab validate`.

Write the heredoc marker quoted (`<<'JSON'`) so the shell leaves the JSON as it is. Write `$SBATCHMAN_JOB_DIR` for the job folder: SbatchMan does not replace `{EXP_DIR}` there. To co-run applications, add apps `"1"`, `"2"` with a `partition`, as in `benchmarks/blink/blink-noise.yaml`.

Check the file without submitting anything:

```bash
cd benchmarks/<benchmark> && sbatchman launch -f <job>.yaml --dry-run
```

## Write it in the dashboard

The dashboard writes the jobs file for you. It stages the file on the cluster and does not launch it.

1. Connect the cluster as in [Install](install.md#connect-your-cluster-in-crab-web), then open **SbatchMan**.
2. Type a name in **Campaign name**. It names the file.
3. In **Group**, fill **Tag**, **SbatchMan preset** (the config name, such as `crab_run_{nodes}`), **Nodes** and **Processes per node**.
4. In **Variables**, press **+ Add variable**. Give a name and comma-separated values.
5. In **Experiment**, press **+ Add app**, pick a wrapper and write its args. Press **+** in the group list for another group.
6. Pick the cluster under **Write to cluster**. If a problem count shows next to **Write files**, press it to see what blocks the write.
7. Press **Write files**. The dashboard shows the path on the cluster and a local copy.
8. On the cluster, copy the file from `<umbrella-dir>/CRAB/.web_staging/` into `benchmarks/<benchmark>`. Its name is the campaign name in lower case.
9. Add the line `configs: ../../.local/configs.leonardo.yaml` at the top of the copy. The dashboard does not write it.
10. Run `./install.sh`, then the `--dry-run` command of [Write the jobs file by hand](#write-the-jobs-file-by-hand).

Next: [Launch](launch.md).
