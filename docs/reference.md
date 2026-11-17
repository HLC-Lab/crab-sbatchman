# Reference

Look up the options of `install.sh`, what `env.sh` sets, the files of the repo and the words the docs use.

## `install.sh`

```bash
./install.sh [--role cluster|laptop] [--account NAME] [--skip-account-check] [--no-check] [--full-check] [--dry-run] [--offline] [-h|--help]
```

| Flag | Meaning |
|---|---|
| `--role ROLE` | `cluster` (default): CRAB, SbatchMan and the configs file. `laptop`: CRAB with the web dashboard and SbatchMan with its plots. |
| `--account NAME` | Slurm account to charge, saved in `site/local.env` (cluster role). Letters, digits, `_`, `.` and `-`. The installer resolves and checks it first: with `sacctmgr` on `PATH`, a name that is not one of your Slurm accounts stops the run before anything is installed. |
| `--skip-account-check` | Do not look the account up with `sacctmgr`. The name is still checked for allowed characters. |
| `--no-check` | Skip the self-check at the end. The check prints one `OK` or `FAIL` line per item and submits no Slurm job. |
| `--full-check` | In the self-check, run `crab validate` on every variable combination of each jobs file. Without it the check runs the first and the last combination only. |
| `--dry-run` | Print every command and file write, run and write nothing. |
| `--offline` | Use no network: every `pip` call reads wheels only from the folder in the environment variable `WHEELHOUSE` (default `.wheelhouse` in the umbrella folder). The installer stops if that folder is missing. Fill it with `pip download`. |
| `-h`, `--help` | Print the usage and exit. |

The environment variable `SBATCHMAN_VERSION` sets the SbatchMan version to install (default `2.0.4`).

| Exit code | Meaning |
|---|---|
| 0 | Done, and every check passed or was skipped. |
| 1 | An environment problem (Python older than 3.10, CRAB or the template missing, an unfilled token), an account that `sacctmgr` does not list for you, or a failed check. |
| 2 | A bad argument, a bad value, or no Slurm account. |

## Environment

`env.sh` holds no absolute path: it finds its own folder when sourced, in bash and in zsh. What it sets depends on the role.

| Setting | Role | Value |
|---|---|---|
| `PYTHONPATH`, `PYTHONHOME` | both | Unset. |
| Virtual environment | both | `CRAB/.venv`, activated. |
| `CRAB_PATH_WRAPPERS` | both | The `crab-wrappers/` folder of the umbrella. |
| `SBATCHMAN_CLUSTER_NAME` | cluster | The value in the site files, `leonardo` when none sets it. |
| `CRAB_WEB_PORT` | laptop | `8899`, or the value already set in the shell. |

It ends by printing the paths of `crab` and `sbatchman`.

`install.sh` reads both site files at install time, `site/local.env` last, so a variable in `site/local.env` wins.

| File | In git | Holds |
|---|---|---|
| `site/leonardo.env` | yes | `SLURM_ACCOUNT` (the placeholder `<YOUR_ACCOUNT>`), `SLURM_PARTITION` (`boost_usr_prod`), `SLURM_QOS` (`normal`), `SBATCHMAN_CLUSTER_NAME` (`leonardo`). |
| `site/local.env` | no | Your `SLURM_ACCOUNT`, and any variable of `site/leonardo.env` you set again. |

## Files

`no` means a maintainer changes the file, `generated` means `install.sh` or SbatchMan writes it.

| Path | Holds | You can change it |
|---|---|---|
| `install.sh` | The installer. | no |
| `env.sh` | The environment for your role. | generated |
| `benchmarks/` | One folder per benchmark: jobs files, parser, plots. | yes |
| `benchmarks/<benchmark>/SbatchMan/` | The SbatchMan project of the benchmark: records and results. | generated |
| `configs/` | The template of the SbatchMan configs file (`leonardo.yaml`). | yes |
| `site/leonardo.env` | Shared site settings. | no |
| `site/local.env` | Your site settings. | yes |
| `templates/` | Commented template of a jobs file and the CRAB config it writes. | no |
| `docs/` | The documentation pages. | no |
| `tests/` | The checks that keep the installer and the docs true. | no |
| `CRAB/` | The CRAB submodule, pinned. | no |
| `CRAB/.venv/`, `CRAB/wrappers` | The virtual environment and the link to `crab-wrappers/`. | generated |
| `crab-wrappers/` | The wrappers submodule, pinned. | no, except a shared wrapper that goes to the crab-wrappers repository |
| `.local/` | The filled configs file, `.local/configs.leonardo.yaml`. | generated |

## Glossary

| Word | Meaning |
|---|---|
| Wrapper | A Python file that names an application's binary and turns its output into rows. Shared wrappers are in `crab-wrappers/`, private ones in `local/wrappers/` of the `CRAB` folder. |
| Receipt | A small file that records where a binary lives on this cluster and which modules it needs. |
| Jobs file | A YAML file in `benchmarks/<benchmark>/` that lists the jobs SbatchMan launches. |
| Configs file | The SbatchMan file `.local/configs.leonardo.yaml`, filled from `configs/leonardo.yaml`. |
| Config | A named entry of the configs file: the nodes, modules and GPUs of the jobs that use it. |
| Campaign | A jobs file written for one set of runs. It is not the `sbatchman campaign` command, which takes a YAML file of its own kind. |
| SbatchMan project | The `SbatchMan/` folder that `sbatchman init` creates in a benchmark folder. |
| Self-check | The last step of `install.sh`: one `OK` or `FAIL` line per item, then a summary. It submits no Slurm job. |

## Known limits

- Login nodes can rotate. A fetch lands on whichever node answers.
- The Add cluster form checks the host key against `~/.ssh/known_hosts` when Host key is `strict`: connect once with `ssh <login-host>` first. If the login nodes rotate and `strict` refuses the connection, choose `insecure`. It accepts any host key, so use it as a last resort and never with `password` auth.
- `sbatchman visualize` listens on the fixed port 8765.
- The umbrella pins CRAB and the wrappers to commits. `crab update` does not apply: it moves CRAB off the pinned commit.
- A Python virtual environment is not relocatable. After you move the umbrella folder, run `./install.sh` again.
