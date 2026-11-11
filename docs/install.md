# Install

## Before you start

- A login on a Slurm cluster.
- Python 3.10 or newer. On a cluster this is a module, such as `module load python`.
- git.
- A Slurm account you can charge.

## Install on the cluster

On a login node:

```bash
git clone --recurse-submodules <umbrella-url> <umbrella-dir>
cd <umbrella-dir>
module load python
./install.sh --account <YOUR_ACCOUNT>
source env.sh
```

Replace the placeholders:

- `<umbrella-url>` with the address of this repo.
- `<umbrella-dir>` with the folder the clone creates.
- `<YOUR_ACCOUNT>` with the Slurm account to charge.

The installer saves the account, so later runs need no `--account`. Run `source env.sh` in every new shell. Add `--dry-run` to print the commands without running them.

The install ends with a self-check that submits no job. A pass prints `install.sh: all checks passed`. If a check fails, see [Troubleshooting](troubleshooting.md).

Register the benchmarks you run in [Register a benchmark](benchmarks.md).

## Install on your laptop

Optional: install the umbrella on your laptop, to run the dashboards there.

```bash
git clone --recurse-submodules <umbrella-url> <umbrella-dir>
cd <umbrella-dir>
./install.sh --role laptop
source env.sh
```

`crab web` serves the dashboard on port 8899. `sbatchman visualize` serves the result plots on port 8765.

## Connect your cluster in crab web

1. Start the dashboard from the shell that holds your ssh agent. It finds the agent through `SSH_AUTH_SOCK`.

   ```bash
   crab web
   ```

2. Open **Remotes** and press **+ Add cluster**.
3. Fill in the fields. Replace `<login-host>` with the address you ssh to and `<your-user>` with your username there.

   | Field | Value |
   |---|---|
   | Name | `leonardo` |
   | Transport | `ssh` |
   | Host, User | `<login-host>`, `<your-user>` |
   | Port | `22` |
   | Auth | agent (ssh-agent or certificate) |
   | Host key | insecure (login nodes rotate) |
   | Install dir | The umbrella folder on the cluster |
   | Crab command, Preset | Empty |

Do not press **Install CRAB** for this cluster: the umbrella already installed it.
If a profile with the same name exists, the dashboard saves the new one with a 2 added to the name.

## Update

```bash
git pull
git submodule update --init
./install.sh
```

Do not run `crab update` in the umbrella: it pins CRAB and the wrappers to tested commits.
