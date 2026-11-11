# Register a benchmark

Register a benchmark so that jobs find its binary through a receipt. A receipt is a small file that records where the binary lives on this cluster and which modules it needs. Run the commands in a shell where you ran `source env.sh`.

## Register a supported benchmark

Use this for Blink, Quantum ESPRESSO, or any other benchmark that `crab setup` offers.

```bash
crab setup
```

1. Choose "Install or configure a supported benchmark".
2. Tick the suites you need, then pick a strategy for each benchmark.

The wizard asks which compiler and MPI modules to load. For a binary that is already built, it also asks for its path. Type the `module load` line your site needs at the module prompt: CRAB saves it in the receipt, so jobs load the same modules.

Check the result:

```bash
crab list-benchmarks
```

The output lists each registered benchmark with its type:

```text
Installed benchmarks (1):
  blink  (source)
```

## Register a new benchmark

You need the application's binary on the cluster and a real output of one run of it. A wrapper tells CRAB how to read that output.

1. Create the wrapper.

   ```bash
   crab wrappers new myapp
   ```

   This creates `myapp/myapp.py`, a README and a passing example in the first folder of `CRAB_PATH_WRAPPERS`. After `source env.sh` that folder is `crab-wrappers/`. Add `--local` to keep the wrapper private and untracked.

2. Write the parser against a real sample.

   Edit `metadata` and `read_data()` in `myapp.py`. List each measured value in `metadata`, with its unit and `"conv": True` for values CRAB repeats a run until they converge. `read_data()` returns one dict per sample and raises when the output is not what you expect.

   In the wrapper's `samples/` folder, replace the example case with a folder that holds:

   - `stdout.txt`: the real output of your application.
   - `expected.json`: the rows the parser must return for it.
   - `case.json`: the wrapper file name and the application's arguments.

   Then run the test:

   ```bash
   crab wrappers test myapp --strict
   ```

   The last line counts one passed case per sample:

   ```text
   1 ok, 0 failed
   ```

3. Register the binary with a receipt.

   ```bash
   crab receipts set myapp --binary /path/to/myapp --pre-run "module load openmpi"
   ```

   The first argument is the `benchmark_id` of the wrapper, which `crab wrappers new` sets to the app name. Repeat `--pre-run` for each command to run before every launch. Add `--launcher srun` or `--launcher mpirun` to override the launcher of your preset. A binary on `PATH` that the wrapper names in `executable` needs no receipt.

4. Check the wrapper and the receipt.

   ```bash
   crab wrappers list
   ```

   The wrapper's line ends with the binary the jobs will use:

   ```text
   myapp/myapp.py                           binary receipt: /path/to/myapp
   ```

   `binary missing` means no receipt, `binary` key or `PATH` entry matches. Then run `crab list-benchmarks`: it lists `myapp  (binary)`.

To share the wrapper, send the wrapper folder with the real sample as a pull request to [crab-wrappers](https://github.com/HLC-Lab/crab-wrappers). The wrapper contract is in [Writing a wrapper](../CRAB/docs/extending/wrappers.md).

### Apps built with different module stacks

When two apps with different module stacks share one job, the second app inherits the first one's module variables. Start its `--pre-run` list with `module purge`:

```bash
crab receipts set myapp --binary /path/to/myapp --pre-run "module purge" --pre-run "module load openmpi"
```

The symptom of a missing `module purge` is `symbol lookup error` in the app's log. [Apps built with different module stacks](../CRAB/docs/using/sbatchman-integration.md#apps-built-with-different-module-stacks) explains the cause.

Next: [Write a campaign](campaigns.md).
