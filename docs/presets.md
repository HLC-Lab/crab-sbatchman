# Configs file

The configs file tells SbatchMan what to ask Slurm for: partition, time limit, modules and environment of each job. The umbrella ships one for Leonardo. SbatchMan reads more (a `scheduler` in each config, `per_cluster` and `map` variables, the `pbs` and `local` schedulers). The tables here cover what a Slurm config of the umbrella uses.

The template is `configs/leonardo.yaml`. `./install.sh` fills its tokens and writes the copy `.local/configs.leonardo.yaml`, which every jobs file loads with `configs: ../../.local/configs.leonardo.yaml`. Edit the template, never the filled copy: the next install overwrites the copy. After each edit, refill the copy on the cluster. A good result ends with `install.sh: all checks passed`.

```bash
./install.sh
```

The template is a tracked file, so a plain `git pull` stops while it has edits. Run `git stash`, then `git pull`, then `git stash pop`, then `./install.sh`. If the pull changed the same lines, `git stash pop` reports a conflict and keeps the stash: fix the file by hand.

## Layout of the file

The file is a `variables` block and a cluster block. The block's name is the cluster name (`leonardo` in the template). A default of `none` means SbatchMan writes no line for it and Slurm applies its own default.

| Field | Meaning | Example | Default | Required |
|---|---|---|---|---|
| `variables` | Values SbatchMan sweeps. A config that writes `{nodes}` becomes one config for each value. A value can also be the path of a file with one value per line. A relative path is read from `.local/`, the folder of the filled copy: write `../configs/nodes.txt` or an absolute path. | `nodes: [2, 4, 8, 16]` | none | no |
| `include_variables` | The path of another YAML file with more variables, or a list of paths. A relative path is read from `.local/`, as for `variables`. | `include_variables: ../configs/shared-vars.yaml` | none | no |
| `scheduler` | The scheduler of the cluster block. This umbrella is for `slurm`. | `scheduler: slurm` | none | yes |
| `default_conf` | The fields every config starts from. A value in a config replaces it. A list in a config is added to the list here. | `default_conf: {time: "00:30:00"}` | none | no |
| `configs` | The list of configs. | `configs: [{name: "crab_run_{nodes}"}]` | none | no |

## Fields of a config

Each entry of `configs` holds these fields. A key written with hyphens is read with underscores. A misspelled key stops SbatchMan with `got an unexpected keyword argument`.

| Field | Meaning | Example | Default | Required |
|---|---|---|---|---|
| `name` | The name of the config. A job writes it in its `config:` key. `{nodes}` makes one config for each value of that variable. | `name: "myapp_{nodes}"` | none | yes |
| `partition` | The Slurm partition (`--partition`). The template holds a token here. | `partition: "mypartition"` | none | no |
| `nodes` | The nodes to ask for (`--nodes`). For CRAB it must cover the job's `"numnodes"`. | `nodes: "{nodes}"` | none | no |
| `ntasks` | The total number of tasks (`--ntasks`). | `ntasks: 16` | none | no |
| `tasks_per_node` | The ranks per node (`--ntasks-per-node`). Keep it at least the job's `"ppn"`. | `tasks_per_node: 4` | none | no |
| `cpus_per_task` | The cores of each task (`--cpus-per-task`). | `cpus_per_task: 8` | none | no |
| `mem` | The memory (`--mem`). | `mem: "64G"` | none | no |
| `account` | The account to charge (`--account`). The template holds a token here. | `account: "<YOUR_ACCOUNT>"` | none | no |
| `time` | The time limit (`--time`). Quote it. A job past it ends as `TIMEOUT`. | `time: "01-00:00:00"` | none | no |
| `gpus` | The GPUs of each node (`--gres=gpu:N`). Leave it out for a CPU config. | `gpus: 4` | none | no |
| `constraint` | The node features the job needs (`--constraint`). | `constraint: "gpu"` | none | no |
| `nodelist` | The nodes the job must use (`--nodelist`). A string or a list. | `nodelist: ["node001"]` | none | no |
| `exclude` | The nodes the job must not use (`--exclude`). A list. | `exclude: ["node002"]` | none | no |
| `qos` | The quality of service (`--qos`). | `qos: "normal"` | none | no |
| `reservation` | The Slurm reservation to run in (`--reservation`). | `reservation: "maintenance"` | none | no |
| `exclusive` | `true` gives the job its nodes alone (`--exclusive`). Some clusters refuse it. | `exclusive: true` | `false` | no |
| `modules` | The modules to load, in one `module load` line. A list in a config is added to the one in `default_conf`. | `modules: ["some-module"]` | none | no |
| `env` | `NAME=value` entries, each written as an `export` line. Added to the list in `default_conf`. | `env: ["OMP_NUM_THREADS=4"]` | none | no |
| `custom_headers` | Whole header lines for any other Slurm option. | `custom_headers: ["#SBATCH --mail-type=END"]` | none | no |

## Tokens the installer fills

A token is a name in capitals between angle brackets, such as `<YOUR_ACCOUNT>`. The installer replaces four of them when it writes the copy, and stops if any other one is left.

| Token | Filled with |
|---|---|
| `YOUR_ACCOUNT` | Your Slurm account, from `site/local.env`. `./install.sh --account NAME` saves it there. |
| `SLURM_PARTITION` | The partition in the site files. `site/local.env` wins over `site/leonardo.env`. |
| `SLURM_QOS` | The quality of service in the site files. |
| `CRAB_DIR` | The absolute path of the `CRAB` folder of the umbrella. |

## Add your config

A jobs file names a config in its `config:` key. Skip this section when `crab_run_{nodes}` (CPU) fits your application.

1. Add a block under `configs:` in `configs/leonardo.yaml`.

   ```yaml
       - name: "myapp_{nodes}"
         nodes: "{nodes}"
         gpus: 4                # drop this line for a CPU-only application
         time: "01:00:00"       # replaces the time of default_conf
         modules:
           - "some-module"      # include one that puts mpirun on PATH
   ```

2. Refill the copy with `./install.sh`.
3. Write a jobs file with `config: myapp_{nodes}`, as in [Write the jobs file](campaigns.md), and run its dry run, as in [Check the file](campaigns.md#check-the-file). The output has `Would generate myapp_2 / <tag>`.
4. In the benchmark folder, read the lines Slurm will get. A good result includes `#SBATCH --gres=gpu:4`.

   ```bash
   grep SBATCH SbatchMan/configs/<cluster>/myapp_2.sh
   ```

Every `nodes` value a job uses must be in the `nodes` list under `variables`.

## Another cluster

The installer reads `configs/leonardo.yaml` and `site/leonardo.env` by name, plus your `site/local.env`, and writes `.local/configs.leonardo.yaml`. A file named `configs/<cluster>.yaml` is not read. For another Slurm cluster, keep these names and change what is inside the files.

1. Add the settings of your cluster to `site/local.env`. The name takes letters, digits, `_`, `.` and `-`.

   ```bash
   SBATCHMAN_CLUSTER_NAME="mycluster"
   SLURM_PARTITION="mypartition"
   SLURM_QOS="myqos"
   ```

2. In `configs/leonardo.yaml`, rename the block `leonardo:` to the same name and change the lines listed here.
3. Run `./install.sh`, then `source env.sh`. A good result is the line `OK sbatchman launch --dry-run on benchmarks/blink/smoke.yaml (submits nothing)`.

The block name and `SBATCHMAN_CLUSTER_NAME` must be equal. If they differ, SbatchMan stops with `No configurations found for cluster`. The dashboard profile name and the `name` of the `[[clusters]]` block in `remotes-config.toml` are labels: the dashboard reads the first `.local/configs.*.yaml` whatever the profile is called, and `sbatchman fetch` takes its folders from `fetch_dirs`. Using the cluster name for both keeps one name to remember.

Lines that are Leonardo's and need your cluster's values:

- The `modules` of `crab_run_{nodes}`: use modules your cluster has, with one that puts `mpirun` on `PATH`.
- The `env` entries `CRAB_IB_DEVICES`, `UCX_IB_SL` and `NCCL_IB_SL` are Leonardo network settings: replace or delete them. `CRAB_SYSTEM` is the label recorded with the results: rename it.
- `time` and `tasks_per_node` in `default_conf`: check them against your site's limits.
- The name `crab_run_{nodes}` and the `nodes` list: `benchmarks/blink/*.yaml` use that name with 2, 4, 8 and 16 nodes. Keep both, or edit the jobs files.
- The module line of [Register Blink](launch.md#register-blink): at that prompt type your cluster's modules, not the Leonardo line.

The installer does not do these for another cluster:

- It fills the four tokens and leaves the block name, `modules`, `env`, `time` and `tasks_per_node` as they are.
- It checks the account with `sacctmgr` (when it is on `PATH`) and nothing else the file holds. A wrong partition, QOS or module shows only when a job is submitted or runs. When the lookup stops the run because your account is not listed, fix the name with `--account`, or pass `--skip-account-check` if the lookup is wrong for your site ([Reference](reference.md#installsh)).
- It registers no benchmark binary: `crab setup` does that on each cluster.
- Its self-check submits no job. The [smoke test](launch.md#launch-the-smoke-test) shows that jobs start.
- It serves one cluster for each checkout: it reads those file names and no others.
