# Connect the laptop to the cluster

The cluster is registered in two places, because two tools use it. The dashboard keeps its own cluster profile: it browses the cluster, writes jobs files there and shows the state of your jobs. SbatchMan reads `remotes-config.toml` and uses it to copy the results to your laptop; the dashboard does not write that file.

Both need the same three values: the address you ssh to, your username there and the port. Replace `<login-host>` with the address and `<your-user>` with the username. Both also need a name for the cluster, a label you choose. The examples use `leonardo`. Install the umbrella on the cluster and on your laptop first, as in [Install](install.md).

Two more placeholders name the umbrella folder, the `crab-sbatchman` folder that `git clone` made. `<umbrella-dir>` is its full path on the cluster. `<laptop-dir>` is its full path on your laptop. To print a full path, run `pwd` inside the folder, on the machine it belongs to. Do not use a relative path: SbatchMan reads a relative local path from the folder where you run the command. A path that starts with `~` is fine.

## Add the cluster in crab web

1. In the umbrella folder (`crab-sbatchman`), run `source env.sh`: the `crab` command lives in its virtual environment. Then start the dashboard on your laptop, not on the cluster, from the shell that holds your ssh agent. It finds the agent through `SSH_AUTH_SOCK`.

   ```bash
   source env.sh
   crab web
   ```

   The command keeps running in that terminal; stop it with Ctrl-C. It prints `[*] CRAB web dashboard → http://127.0.0.1:8899  (Ctrl-C to stop)` and tries to open your browser. If no browser opens, open `http://127.0.0.1:8899` yourself. The dashboard answers only on your own machine, but it has no login: on a computer shared with other people, anyone logged in there could use the cluster connections it holds. Run it on a computer that only you use.

   To check without a browser, run `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8899/` in a second terminal while `crab web` runs. A good result is `200`. This proves only that the dashboard page answers. The API behind it needs the session token of the page you opened, so a `curl` to an address that starts `/api/` answers `auth_required`.

2. Open **Remotes** and press **+ Add cluster**.
3. Fill in the fields.

   | Field | Value |
   |---|---|
   | Name | your cluster name, for example `leonardo` |
   | Transport | `ssh` |
   | Host, User | `<login-host>`, `<your-user>` |
   | Port | `22` |
   | Auth | agent (ssh-agent / cert) |
   | Host key | strict (for rotating login nodes, see [Known limits](reference.md#known-limits)) |
   | Install dir | `<umbrella-dir>` |
   | Crab command | Empty |

   The Name is only a label that the dashboard keeps for this profile. The dashboard also uses it as the name of the profile's folder on your laptop, so use only letters, digits, `.`, `_` and `-`, and not `local`. Nothing on the cluster and nothing in SbatchMan reads it.

4. Press **Save**.
5. Press **Connect** next to the cluster. The dot turns green and the button says **Disconnect**.

![The Add cluster form filled in, before Save](img/add-cluster.png)

If Connect says no SSH key is loaded in your agent, log in the way you do for the cluster, for example with `ssh-add`, in the shell that runs `crab web`. Then start `crab web` again.
Host key `strict` checks your `~/.ssh/known_hosts`. Run `ssh <login-host>` once first, so the file holds the host key.

Do not press **Install CRAB** for this cluster: the umbrella already installed it.
If a profile with that name exists, the form says so under Name and Save stays off: pick another name.

## Add the cluster to SbatchMan

Save this as `remotes-config.toml` in the SbatchMan config folder on your laptop, or add it by hand to the file if it exists. The folder is `~/.config/sbatchman/` on Linux and `~/Library/Application Support/sbatchman/` on macOS. The install does not create the folder. Create it first, then save the file in it. On Linux this makes the folder, or leaves it as it is when it exists. No output is a good result:

```bash
mkdir -p ~/.config/sbatchman
```

On macOS this does the same for the macOS folder. The backslash keeps the space in the name. No output is a good result:

```bash
mkdir -p ~/Library/Application\ Support/sbatchman
```

```toml
[[clusters]]
name = "leonardo"
host = "<login-host>"
port = 22
user = "<your-user>"
```

The `name` here is a label too. If your cluster name is not `leonardo`, replace `leonardo` in this block with it. [Results](results.md#fetch-and-plot) shows the same block. SbatchMan matches the `-c` value against it on its copy commands, such as `sbatchman fetch -c leonardo`, and prints it in the headers of their output. It need not equal the dashboard name. The `SBATCHMAN_CLUSTER_NAME` setting that names the cluster in the configs file on the cluster is a separate matter, described in [Configs file](presets.md#another-cluster).

[Results](results.md#fetch-and-plot) tells you to add `fetch_dirs` lines under this block and a `[global]` section to the same file, and shows the finished file. Keep this block: Results adds no second one.

Next: [Run a benchmark](launch.md).
