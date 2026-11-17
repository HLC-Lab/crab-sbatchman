# Contributing

Send each change to the repository that owns the files.

| You want to add or fix | It belongs in | Where |
|---|---|---|
| A wrapper (the parser of a benchmark's output) or its samples | crab-wrappers | `https://github.com/HLC-Lab/crab-wrappers`, pull request with its template |
| A benchmark's jobs files and plots | this repository | `benchmarks/<benchmark>/` |
| The Slurm configuration of a cluster | this repository | `configs/<cluster>.yaml` and `site/<cluster>.env` |
| A bug or feature in `crab` | CRAB | `https://github.com/HLC-Lab/CRAB` |
| A bug in `sbatchman` | SbatchMan | the SbatchMan repository |

## Add a wrapper

Wrappers live in `crab-wrappers/`, a submodule of this repository. Clone `crab-wrappers` on its own, not through this repository.

1. Write the wrapper and add real samples. Scrub the samples of usernames, accounts and host names.
2. Run the wrapper tests from the `crab-wrappers` clone:

    ```bash
    CRAB_PATH_WRAPPERS="$PWD" crab wrappers test --strict
    ```

3. Open the pull request and fill in its template: where the samples come from and the last lines of the test output.

The output ends with `0 failed` when the wrapper is accepted.

## Add a benchmark folder

A benchmark folder holds everything one benchmark needs to run through SbatchMan:

- One jobs file (`*.yaml`) for each campaign.
- `plots.json`, which `sbatchman visualize` reads.
- `parser.py`, a symbolic link to `../parser.py`.
- `README.md`, which names the binary, its modules and the campaigns.

Copy `benchmarks/blink/` and change it. The installer runs `sbatchman init` in every `benchmarks/*/` folder that holds a jobs file, so no other registration is needed. Jobs files point at the cluster file with `configs: ../../.local/configs.leonardo.yaml`.

The tests in `tests/test_benchmarks.py` run `crab validate` on every combination of every jobs file. Add the folder and its jobs files to the lists at the top of that test file.

## Add a configs file

A configs file describes one cluster: the Slurm partition, the quality of service, the modules and the `crab` paths.

1. Copy `configs/leonardo.yaml` to `configs/<cluster>.yaml`.
2. Keep the placeholders `<YOUR_ACCOUNT>`, `<SLURM_PARTITION>`, `<SLURM_QOS>` and `<CRAB_DIR>`. The installer fills them into `.local/`, which git ignores. A token in capitals that is not on this list makes it stop.
3. Copy `site/leonardo.env` to `site/<cluster>.env` and set the partition, the quality of service and the cluster name.

Today `install.sh` reads only `configs/leonardo.yaml` and `site/leonardo.env`. The files for a second cluster are not read until the installer takes the cluster name as a variable.

Never write a real account, user name or host name in a tracked file.

This repository does not use CRAB presets. Cluster settings live in the configs file.

## Run the tests

The tests use stubs and need no cluster. From the repository root:

```bash
pip install -e ./CRAB pytest pyyaml
```

```bash
python -m pytest -q
```

The output ends with `passed`. The submodules must be checked out: run `git submodule update --init` when `CRAB/` or `crab-wrappers/` is empty.

## Change the pinned versions

The submodules point at fixed CRAB and crab-wrappers versions. Do not change them in a pull request. The maintainer updates them, as [RELEASING.md](RELEASING.md) describes.
