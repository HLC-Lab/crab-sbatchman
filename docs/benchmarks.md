# Wrap and register your benchmark

Wrap an application that CRAB does not support yet, then register its binary. To run Blink or another benchmark that `crab setup` offers, follow [Register Blink](launch.md#register-blink).

You need the application's binary on the cluster and one real output of a run. Writing and testing the wrapper works on any machine with the umbrella installed, a laptop included. Registering a binary that exists and every run need the cluster: use the login node. On either machine, run the commands in a shell where you ran `source env.sh`. A wrapper written on a laptop must be copied to `CRAB/local/wrappers/` of the umbrella on the cluster before a job can find it.

## What a wrapper is

A wrapper is a small Python file that turns the output of your application into numbers. CRAB runs the application, hands its output to the wrapper and stores the numbers it returns. A receipt, written in the last steps, tells CRAB where the binary is. The wrapper and the receipt live on the cluster where the jobs run: the receipt in `local/receipts` of the `CRAB` folder, and the wrapper where the dashboard's wrapper picker finds it.

## Get a real output

Skip this when you already have the output of a run. The toy `myapp` in the next section is not a real program: for it, skip this section and use the output shown there.

Otherwise run your binary once and save what it prints. `srun` runs it on a compute node, charged to `<YOUR_ACCOUNT>` like any job, and the job can wait in the queue first. Never run the program directly on the login node. On the login node, load the modules the application needs, then run:

```bash
srun --account=<YOUR_ACCOUNT> --ntasks=1 --time=00:05:00 /path/to/your-app > stdout.txt
```

`--time=00:05:00` stops the program after 5 minutes. Add the `--partition` and `--qos` that your cluster needs, as in your [configs file](presets.md#another-cluster). `--ntasks=1` starts one copy. Use more only for an MPI program: `--ntasks=4` starts 4 copies, and a program that is not MPI then writes the output of all 4 into the one `stdout.txt`. `> stdout.txt` saves what the program prints in the current folder. A good result is a `stdout.txt` that holds the program's output lines.

## Write the wrapper

Create the wrapper from the template:

```bash
crab wrappers new myapp --local
```

This creates `myapp/myapp.py`, a README and a passing example in `local/wrappers/` of the `CRAB` folder. That folder is git-ignored and CRAB searches it first, so a job finds the wrapper as `myapp/myapp.py` and the submodule stays clean. Without `--local`, the wrapper goes to `crab-wrappers/` and shows as untracked content of that submodule in `git status`.

The example is a toy application, `myapp`, that prints one line per iteration:

```text
myapp ranks=4
iteration 1 time_us 12.5
iteration 2 time_us 12.1
iteration 3 time_us 12.8
```

Replace the content of `myapp.py` with this wrapper. For your own application, write the wrapper against a real output.

```python
from crab.wrappers.base import base


class app(base):
    benchmark_id = "myapp"
    metadata = [{"name": "time", "unit": "us", "conv": True}]

    def read_data(self):
        lines = [line for line in self.stdout.splitlines() if line.startswith("iteration")]
        if not lines:
            raise ValueError("no iteration line in the output of myapp")
        return [{"time": float(line.split()[-1])} for line in lines]
```

- `benchmark_id` names the receipt of the binary. `metadata` lists each measured value with its `name` and `unit`. `"conv": True` makes CRAB repeat a run until that value converges.
- `read_data()` returns one entry per iteration line of the output, with a value for every metric and nothing else. It raises when the output is not what you expect, so a bad run fails instead of recording made-up numbers.
- The generated template also sets `executable` and `keys`. This wrapper leaves both out. Without `executable`, the binary comes from the receipt of [Register the binary](#register-the-binary). Without `keys`, every row holds single values, which is what the toy prints.

[Writing a wrapper](https://github.com/HLC-Lab/CRAB/blob/v1.5.1+sbatchman/docs/extending/wrappers.md#the-contract) holds the full contract, with sweeps over message sizes and correctness checks.

## Test the wrapper

The test runs your wrapper on a saved output, with no job and no binary. `crab wrappers new` already made `CRAB/local/wrappers/myapp/samples/example/` with the template's own example in `stdout.txt`, `case.json` and `expected.json`. Replace `stdout.txt` with the real output of your application (for the toy, its four lines), and `expected.json` with the rows the wrapper must return, one entry per iteration line, each holding a value for every metric. In `case.json`, keep `"wrapper"` and put the arguments of the run in `"args"`: the toy takes none, so leave `""` as it is. For the toy, `expected.json` is:

```json
[{"time": 12.5}, {"time": 12.1}, {"time": 12.8}]
```

```bash
crab wrappers test myapp --strict
```

The last line counts sample folders, not the rows inside them. `samples/example/` is one folder, so a good result is `1 ok, 0 failed`, whatever the number of rows.

To share the wrapper, send the wrapper folder with its real sample folder as a pull request to [crab-wrappers](https://github.com/HLC-Lab/crab-wrappers).

## Register the binary

Record where the binary lives on this cluster. Run it on the login node, where the path exists: the command refuses a path that does not exist here. Add `--allow-missing` to record a path that is not there yet, such as a binary you build later. CRAB then saves the path without checking it.

```bash
crab receipts set myapp --binary /path/to/myapp --pre-run "module load openmpi"
```

The first argument is the `benchmark_id` of the wrapper. Repeat `--pre-run` for each command to run before every launch. Add `--launcher srun` or `--launcher mpirun` to override the launcher of your preset. If the binary is on `PATH` when the job runs, add `executable = "myapp"` to the class and skip the receipt. The `modules` of the job's SbatchMan config (see [Add your config](presets.md#add-your-config)) and the `--pre-run` commands both apply: the config's modules load first, then each app's `--pre-run` commands run.

### Apps built with different module stacks

When two apps with different module stacks share one job, the second app inherits the first one's module variables. Start its `--pre-run` list with `module purge`:

```bash
crab receipts set myapp --binary /path/to/myapp --pre-run "module purge" --pre-run "module load openmpi"
```

The symptom of a missing `module purge` is `symbol lookup error` in the app's log. [Apps built with different module stacks](https://github.com/HLC-Lab/CRAB/blob/v1.5.1+sbatchman/docs/using/sbatchman-integration.md#apps-built-with-different-module-stacks) explains the cause.

## Check it

```bash
crab wrappers list | grep myapp
```

The command lists every wrapper, about 80 lines, so `grep` keeps the line of yours. That line, `myapp/myapp.py`, ends with the binary the jobs will use, here `binary receipt: /path/to/myapp`. `binary missing` means no receipt, `binary` key or `PATH` entry matches. Then run `crab list-benchmarks`: it lists `myapp  (binary)`.

Nothing here needs a `parser.py`. To plot the results of this benchmark later, on your laptop, its folder needs one: [Use the shared parser](plots.md#use-the-shared-parser) gives it, and says when to make it.

Next: [Write the jobs file](campaigns.md).
