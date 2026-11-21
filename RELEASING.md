# Releasing

How the maintainer moves the pinned CRAB and crab-wrappers versions of this repository. Run the steps in order and stop at the first failure.

## Release CRAB and the wrappers

1. In the CRAB repository, on `develop`, set `__version__` in `src/crab/__init__.py` to X.Y.Z and commit it. Run `make verify-full`: it must end with `[verify-full] all green`.
2. Merge `develop` into `sbatchman`. Merge, never rebase.

   ```bash
   git checkout sbatchman && git merge -m 'chore: merge develop into sbatchman' develop
   ```

   A conflict appears only in `src/crab/web/static/`, where asset names carry a hash. Run `npm run build` in `src/crab/webui`, add that folder and commit the merge. Run `make verify-full` on `sbatchman` too.
3. In the crab-wrappers repository, run `CRAB_PATH_WRAPPERS="$PWD" crab wrappers test --strict`. The last line must say `0 failed`.
4. Write the release notes in a file with `Breaking`, `Added`, `Changed` and `Fixed` headings. Create annotated tags from it with `git tag -a <tag> -F notes.md --cleanup=verbatim`, because git drops lines that start with `#` otherwise: `vX.Y.Z` on `develop`, `vX.Y.Z+sbatchman` on `sbatchman`, and `vX.Y.Z` in crab-wrappers.
5. Before any push, scan the commits and the diff of each branch for user names, host names, account names, personal addresses and AI trailers. This command lists trailers:

   ```bash
   git log origin/sbatchman..sbatchman --format=%B | grep -i -E 'co-authored-by|generated with'
   ```

6. Push the branches and tags, then wait until CI is green on every ref.
7. Advance `master`, the default branch of CRAB, to the release commit: `git push origin vX.Y.Z^{commit}:refs/heads/master`.
8. Create a GitHub release from each tag with `gh release create <tag> --verify-tag --notes-file <notes>`, so the latest release shown on each repository is the new one. In CRAB that is `vX.Y.Z`, not the `+sbatchman` one.

## Pin the new versions here

1. Check out the two tags in the submodules, then read the result.

   ```bash
   git -C CRAB fetch --tags && git -C CRAB checkout vX.Y.Z+sbatchman
   git -C crab-wrappers fetch --tags && git -C crab-wrappers checkout vX.Y.Z
   git submodule status
   ```

2. Put the first 8 characters of the new CRAB commit into the pin assertion of `tests/test_layout.py`, and the new tag into the two CRAB links of `docs/benchmarks.md`.
3. Run `pip install pytest pyyaml`, then `python -m pytest -q` from the repository root, without a sandbox. It must end with `passed`.
4. Commit `CRAB`, `crab-wrappers` and `tests/test_layout.py` as `chore: pin CRAB to vX.Y.Z+sbatchman`.
5. Tag that commit `vX.Y.Z` with `git tag -a vX.Y.Z -m 'CRAB vX.Y.Z'`, so the three matching versions have one name, then push the branch and the tag.
6. Wait for the `macos.yml` run that the push starts. If none started, run `gh workflow run macos.yml`.
