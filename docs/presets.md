# Configs file

The configs file tells SbatchMan what to ask Slurm for: partition, time limit, modules and environment of each job. The umbrella ships one for Leonardo. SbatchMan reads more (a `scheduler` in each config, `per_cluster` and `map` variables, the `pbs` and `local` schedulers). The tables here cover what a Slurm config of the umbrella uses.

The template is `configs/leonardo.yaml`. `./install.sh` fills its tokens and writes the copy `.local/configs.leonardo.yaml`, which every jobs file loads with `configs: ../../.local/configs.leonardo.yaml`. Edit the template, never the filled copy: the next install overwrites the copy. After each edit, refill the copy on the cluster. A good result ends with `install.sh: all checks passed`.

```bash
./install.sh
```

The template is a tracked file. You need not commit your edit: the installer reads the working copy. A plain `git pull` stops with an error that starts `error: Your local changes` when the update changes this file, and goes ahead when it does not. When it stops, run `git stash`, then `git pull`, then `git stash pop`, then `./install.sh`. If the pull changed the same lines, `git stash pop` reports a conflict and keeps the stash: fix the file by hand. If you did commit the edit, a plain `git pull` stops with a recent git, with `Need to specify how to reconcile divergent branches`, once the update has new commits: run `git config pull.rebase false` once (it means merge instead of rebase), then `git pull`, and fix the file by hand if it reports a conflict.

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

The installer reads `configs/leonardo.yaml` and `site/leonardo.env` by name, plus your `site/local.env`, and writes `.local/configs.leonardo.yaml`. A file named `configs/<cluster>.yaml` is not read. For another Slurm cluster, keep these names, `leonardo` included, and change what is inside the files.

Run these steps on the cluster login node, in the umbrella clone there. Never run a bare `./install.sh` on your laptop: it installs the cluster role, writes `site/local.env` and `.local/configs.leonardo.yaml`, and rewrites `env.sh` (the line that sets `CRAB_WEB_PORT` goes, `SBATCHMAN_CLUSTER_NAME` is added). On a laptop run `./install.sh --role laptop`, which writes `env.sh` back.

1. Create `site/local.env` (the clone has none, and Git ignores it) and put the settings of your cluster in it. If an earlier `./install.sh --account` made the file, edit its lines. The name takes letters, digits, `_`, `.` and `-`.

   ```bash
   SBATCHMAN_CLUSTER_NAME="mycluster"
   SLURM_ACCOUNT="myaccount"
   SLURM_PARTITION="mypartition"
   SLURM_QOS="myqos"
   ```

   `SLURM_ACCOUNT` is your Slurm account. `./install.sh --account NAME` gives the same and saves the name in `site/local.env`. With neither, the installer asks for the account. With no terminal to ask in, it stops with exit status 2.

2. In `configs/leonardo.yaml`, rename the block `leonardo:` to the same name and change the lines listed here.
3. Run `./install.sh`, then `source env.sh`. A good result is the line `OK sbatchman launch --dry-run on benchmarks/blink/smoke.yaml (submits nothing)`.
4. Read the lines Slurm will get, as in step 4 of [Add your config](#add-your-config). In `benchmarks/blink`, run the dry run of [Launch the smoke test](launch.md#launch-the-smoke-test), then run `grep SBATCH SbatchMan/configs/<cluster>/crab_run_2.sh`. A good result holds your partition, account and QOS.

The block name and `SBATCHMAN_CLUSTER_NAME` must be equal. If they differ, SbatchMan stops with `No configurations found for cluster`. The dashboard profile name and the `name` of the `[[clusters]]` block in `remotes-config.toml` are labels: the dashboard reads the first `.local/configs.*.yaml` in the profile's install dir on the cluster, over the connection (the laptop has no `.local/`), whatever the profile is called, and `sbatchman fetch` takes its folders from `fetch_dirs`. Using the cluster name for both keeps one name to remember.

Lines that are Leonardo's and need your cluster's values:

- The `modules` of `crab_run_{nodes}`: use modules your cluster has, with one that puts `mpirun` on `PATH`.
- The `env` entries `CRAB_IB_DEVICES`, `UCX_IB_SL` and `NCCL_IB_SL` are Leonardo network settings: replace or delete them, and delete the comment line `# Leonardo network settings` with them. `CRAB_SYSTEM` is the label recorded with the results: rename it.
- Comments that are true only on Leonardo, counting the lines of the unedited template: replace lines 1 and 2 (one sentence that names Leonardo and CINECA) with two lines, ``# Template of the SbatchMan configs file.`` and ``# Do not edit the filled copy: `./install.sh` fills this file into``, which run on into line 3. In lines 10 and 11 change `site/leonardo.env` to `site/local.env`, which is where your partition and QOS come from. Delete lines 16 and 17 (the one comment that begins `# The cluster block name below` and runs onto the next line), and delete the `boost_qos_dbg` remark at the end of the `qos:` line. Keep the `qos:` line itself.
- `time` and `tasks_per_node` in `default_conf`: check them against your site's limits, as in [Check the limits of your site](#check-the-limits-of-your-site).
- The name `crab_run_{nodes}` and the `nodes` list: `benchmarks/blink/*.yaml` use that name with 2, 4, 8 and 16 nodes. Keep both, or edit the jobs files.
- The module line of [Register Blink](launch.md#register-blink): at that prompt type your cluster's modules, not the Leonardo line.

The installer does not do these for another cluster:

- It fills the four tokens and leaves the block name, `modules`, `env`, `time` and `tasks_per_node` as they are.
- It checks the account with `sacctmgr` (when it is on `PATH`) and nothing else the file holds. Without `sacctmgr` it prints the note `install.sh: note: sacctmgr is not on PATH, so the account myaccount was not checked against Slurm.` and goes on. `install.sh: all checks passed` and the dry run do not check the partition, the QOS, the time limit or the modules: a wrong one shows only when a job is submitted or runs. [Check the limits of your site](#check-the-limits-of-your-site) gives the commands that check them. When the lookup stops the run because your account is not listed, fix the name with `--account`, or pass `--skip-account-check` if the lookup is wrong for your site ([Reference](reference.md#installsh)).
- It registers no benchmark binary: `crab setup` does that on each cluster.
- Its self-check submits no job. The [smoke test](launch.md#launch-the-smoke-test) shows that jobs start.
- It serves one cluster for each checkout: it reads those file names and no others, and `env.sh` names one cluster. A second cluster is a second clone of the umbrella, on that cluster, with its own `site/local.env` and edited template. The laptop keeps one clone for all of them: one dashboard profile for each cluster (its install dir is that cluster's `<umbrella-dir>`), and one `[[clusters]]` block for each in `remotes-config.toml`, each with its own `fetch_dirs`; the `local` folders of two clusters can differ. `sbatchman fetch -c <cluster>` copies one cluster, and `sbatchman fetch` copies all of them.

## Check the limits of your site

`time`, `tasks_per_node`, the partition, the QOS and the modules must fit your site. Your site's documentation has the numbers. These commands print them. Run them on the cluster login node and write your own values in place of `mypartition`, `myqos` and `myaccount`.

1. List the partitions.

   ```bash
   sinfo -o "%P %l %D %c"
   ```

   Each line holds a partition (the default has a `*`), its time limit, its number of nodes and the CPUs of one node. `time` stays within that limit. `tasks_per_node` stays within those CPUs.

2. Read the limits of your partition.

   ```bash
   scontrol show partition mypartition
   ```

   `MaxTime` is the longest `time`, `MaxNodes` the largest `nodes` value, and `AllowQos` and `AllowAccounts` name what the partition takes. `UNLIMITED` and `ALL` mean no limit.

3. Read the QOS limits.

   ```bash
   sacctmgr show qos format=Name,MaxWall,MaxTRESPU
   sacctmgr show assoc user=$USER format=Account,Partition,QOS%60
   ```

   The first command lists each QOS with its longest run time (`MaxWall`) and what one user can hold at once (`MaxTRESPU`). An empty field means no limit. The second lists the QOS names your account can use. A blank QOS there means the account takes its QOS from a parent account, and a value that ends with `+` is cut: raise the `60`.

4. Find the modules. `module avail openmpi` lists the versions of a name. Load your modules by hand, then ask for the three tools `crab setup` needs. A good result is three paths.

   ```bash
   module load gcc openmpi cmake
   command -v mpirun mpicc cmake
   ```

5. Ask Slurm to check the request. It submits no job. Use the `time` and `tasks_per_node` of your configs file, and for `--nodes` the largest node count of your jobs.

   ```bash
   sbatch --test-only --partition=mypartition --qos=myqos --account=myaccount --time=00:30:00 --nodes=2 --ntasks-per-node=4 --wrap=true
   ```

   A good result is a line that starts `sbatch: Job ` and ends with the start time Slurm expects. The job number is not a real job: nothing is queued. On most sites a bad partition, QOS, account, time or node count stops it with a line that starts `sbatch: error:`. A site that does not enforce QOS or account limits at submission can accept a request that only waits in the queue later. Then only the smoke test shows the problem.

The modules of a job load only when it runs, so no command here checks them in the job. The [smoke test](launch.md#launch-the-smoke-test) is the first run that loads them: read the job's `stderr.log` if it fails.
