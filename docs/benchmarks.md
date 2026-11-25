# Wrap and register your benchmark

Wrap an application that CRAB does not support yet, then register its binary. To run Blink or another benchmark that `crab setup` offers, follow [Register Blink](launch.md#register-blink).

You need the application's binary on the cluster and one real output of a run. Run every command on the cluster login node, in a shell where you ran `source env.sh`.

## What a wrapper is

A wrapper is a small Python file that turns the output of your application into numbers. CRAB runs the application, hands its output to the wrapper and stores the numbers it returns. A receipt, written in the last steps, tells CRAB where the binary is. The wrapper and the receipt live on the cluster where the jobs run: the receipt in `local/receipts` of the `CRAB` folder, and the wrapper where the dashboard's wrapper picker finds it.

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
- `read_data()` returns one entry per sample, with a value for every metric and nothing else. It raises when the output is not what you expect, so a bad run fails instead of recording made-up numbers.

[Writing a wrapper](https://github.com/HLC-Lab/CRAB/blob/v1.5.1+sbatchman/docs/extending/wrappers.md#the-contract) holds the full contract, with sweeps over message sizes and correctness checks.

## Test the wrapper

The test runs your wrapper on a saved output, with no job and no binary. In `CRAB/local/wrappers/myapp/samples/example/`, put the real output of your application in `stdout.txt` (for the toy, the sample output), the arguments of the run in the `"args"` of `case.json`, and the rows the wrapper must return in `expected.json`, one entry per sample, each holding a value for every metric. For the toy:

```json
[{"time": 12.5}, {"time": 12.1}, {"time": 12.8}]
```

```bash
crab wrappers test myapp --strict
```

The last line counts one passed case per sample. A good result is `1 ok, 0 failed`.

To share the wrapper, send the wrapper folder with the real sample as a pull request to [crab-wrappers](https://github.com/HLC-Lab/crab-wrappers).

## Register the binary

Record where the binary lives on this cluster. The command refuses a path that does not exist:

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
crab wrappers list
```

The line of `myapp/myapp.py` ends with the binary the jobs will use, here `binary receipt: /path/to/myapp`. `binary missing` means no receipt, `binary` key or `PATH` entry matches. Then run `crab list-benchmarks`: it lists `myapp  (binary)`.

To plot the results of this benchmark later, its folder needs a `parser.py`: [Use the shared parser](plots.md#use-the-shared-parser) gives it.

Next: [Write the jobs file](campaigns.md).
