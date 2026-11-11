# Templates

This folder holds `jobs-template.yaml`, a SbatchMan jobs file for one app run by CRAB. Every key
has a comment that says what it does and what to change, and the CRAB JSON it writes is embedded
in the `preprocess` script, with a comment block that describes each JSON key.

To use it:

1. Copy it into a benchmark folder, for example `benchmarks/<app>/`, and rename it.
2. Edit the lines marked `Change:` (the node counts, the tag, the wrapper `path` and its `args`).
3. Check it from that folder with `sbatchman launch -f <file>.yaml --dry-run`.

As shipped it runs the Blink all-to-all on 2 nodes and passes `crab validate` unedited, so the
shape is a safe reference for your own app. `tests/test_templates.py` keeps it valid.

The folder is a stub for partners: nothing reads it, and deleting it breaks nothing.
