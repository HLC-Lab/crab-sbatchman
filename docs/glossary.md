# Glossary

The words the docs use for the parts of the setup, in alphabetical order. A link names the page that explains the word.

| Word | Meaning |
|---|---|
| Campaign | A jobs file written for one set of runs ([Write the jobs file](campaigns.md)). It is not the `sbatchman campaign` command, which takes a YAML file of its own kind: `apps:` with a `name`, a `dir` and `steps`, each step naming a `jobs` file in that `dir`. Run it as `sbatchman campaign campaign.yaml -c <cluster>`; `--dry-run` lists the jobs without submitting. It launches each jobs file from its app's `dir`, waits for the jobs to finish and keeps a journal in `./campaign_results`. `sbatchman campaign-tui` opens a terminal screen to monitor and manage campaigns. |
| Cluster profile | The record the dashboard keeps of one cluster: how to reach it and where the umbrella is installed on it. [Connect](connect.md) adds one. |
| Config | A named entry of the configs file: the nodes, modules and GPUs of the jobs that use it. [Add your config](presets.md#add-your-config) adds one. |
| Configs file | The SbatchMan file `.local/configs.leonardo.yaml`, the one name the installer writes, filled from `configs/leonardo.yaml`. [Configs file](presets.md) has its fields. |
| Dashboard | The web app that `crab web` serves on your laptop. It browses the wrappers on the cluster and writes jobs files there. It does not launch jobs or show their state: `sbatchman status` on the cluster does ([Run a benchmark](launch.md)). [Connect](connect.md) sets it up. |
| Fetch | The command `sbatchman fetch`, which copies the result folders from the cluster to your laptop. [Fetch and plot](results.md#fetch-and-plot) runs it. |
| Jobs file | A YAML file in `benchmarks/<benchmark>/` that lists the jobs SbatchMan launches. [Write the jobs file](campaigns.md) writes one. |
| Login node | The cluster machine you reach with ssh. You install the umbrella and launch jobs there, and Slurm runs the jobs on other nodes. [Install on the cluster](install.md#install-on-the-cluster) starts there. |
| Module | A software package that the cluster loads into your shell with `module load`. A config and a receipt list the modules their jobs need. |
| Noise app | An app that runs at the same time as the app you measure, to load the cluster and slow the measured app down. [Change the keys](campaigns.md#change-the-keys) says how to set one up. |
| Receipt | A small file that records where a binary lives on this cluster and which modules it needs. [Register the binary](benchmarks.md#register-the-binary) writes one. |
| SbatchMan project | The `SbatchMan/` folder that `sbatchman init` creates in a benchmark folder. It holds the jobs and their results. |
| Self-check | The last step of `install.sh`: one `OK` or `FAIL` line per item, then a summary. It submits no Slurm job. |
| Slurm account | The account that Slurm charges for your jobs. The installer saves it in `site/local.env`. [Install on the cluster](install.md#install-on-the-cluster) passes it. |
| Smoke test | The first small run: one all-to-all alone on 2 nodes. [Launch the smoke test](launch.md#launch-the-smoke-test) runs it. |
| Tag | The name of a job and of its result folder, set by `tag` in the jobs file. [Change the keys](campaigns.md#change-the-keys) lists it. |
| Umbrella | This repo. It installs CRAB and SbatchMan at matching versions and ships example benchmarks. [Start here](index.md) tells where to begin. |
| Wrapper | A Python file that names an application's binary and turns its output into rows. Every app of a job needs one: CRAB counts the rows as samples and repeats runs until they converge. Shared wrappers are in `crab-wrappers/`, private ones in `local/wrappers/` of the `CRAB` folder. [What a wrapper is](benchmarks.md#what-a-wrapper-is) tells more. |
