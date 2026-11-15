# Releasing

How the maintainer moves the pinned CRAB and crab-wrappers versions of this repository. Run the steps in order and stop at the first failure.

## Release CRAB and the wrappers

1. In the CRAB repository, on `develop`, set `__version__` in `src/crab/__init__.py` to X.Y.Z and commit it. Run `make verify-full`: it must end with `[verify-full] all green`.
2. Merge `develop` into `sbatchman`. Merge, never rebase.

   ```bash
   git checkout sbatchman && git merge --no-edit develop
   ```

   A conflict appears only in `src/crab/web/static/`, where asset names carry a hash. Run `npm run build` in `src/crab/webui`, add that folder and commit the merge. Run `make verify-full` on `sbatchman` too.
3. In the crab-wrappers repository, run `CRAB_PATH_WRAPPERS="$PWD" crab wrappers test --strict`. The last line must say `0 failed`.
4. Create annotated tags with plain release notes: `vX.Y.Z` on `develop`, `vX.Y.Z+sbatchman` on `sbatchman`, and `vX.Y.Z` in crab-wrappers.
5. Before any push, scan the commits and the diff of each branch for user names, host names, account names, personal addresses and AI trailers. This command lists trailers:

   ```bash
   git log origin/sbatchman..sbatchman --format=%B | grep -i -E 'co-authored-by|generated with'
   ```

6. Push the branches and tags, then wait until CI is green on every ref.

## Pin the new versions here

1. Check out the two tags in the submodules, then read the result.

   ```bash
   git -C CRAB fetch --tags && git -C CRAB checkout vX.Y.Z+sbatchman
   git -C crab-wrappers fetch --tags && git -C crab-wrappers checkout vX.Y.Z
   git submodule status
   ```

2. Put the first 8 characters of the new CRAB commit into the pin assertion of `tests/test_layout.py`.
3. Run `python -m pytest -q` from the repository root, without a sandbox. It must end with `passed`.
4. Commit `CRAB`, `crab-wrappers` and `tests/test_layout.py` as `chore: pin CRAB to vX.Y.Z+sbatchman`, then push.
5. Wait for the `macos.yml` run that the push starts. If none started, run `gh workflow run macos.yml`.
