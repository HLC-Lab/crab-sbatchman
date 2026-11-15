#!/usr/bin/env bash
# Installs the umbrella on this machine. Safe to run again: a second run prints the same
# commands and changes no file. Every command is printed before it runs; --dry-run prints
# them and runs nothing.
set -euo pipefail

# The one place that pins SbatchMan (override from the environment).
SBATCHMAN_VERSION="${SBATCHMAN_VERSION:-2.0.4}"

usage() {
    cat <<'EOF'
Usage: ./install.sh [--role cluster|laptop] [--account NAME] [--skip-account-check]
                    [--no-check] [--full-check] [--dry-run] [--offline] [-h|--help]

  --role ROLE      cluster (default): CRAB, SbatchMan and the configs file.
                   laptop: CRAB with the web dashboard and SbatchMan with its plots.
  --account NAME   Slurm account to charge; saved in site/local.env (cluster role). It is
                   resolved and checked first: with sacctmgr on PATH, a name that is not one of
                   your Slurm accounts stops the run before anything is installed.
  --skip-account-check
                   do not look the account up with sacctmgr (the name is still checked for
                   allowed characters).
  --no-check       skip the self-check at the end. The check prints one OK or FAIL line per
                   item (tool versions, commands in the venv, wrappers, every jobs file
                   through 'crab validate' and, for the cluster role, a dry-run launch of
                   the smoke file), then a summary, and exits 1 if any item failed. It
                   submits no Slurm job.
  --full-check     in the self-check, run 'crab validate' on every variable combination of
                   each jobs file (default: the first and the last combination only).
  --dry-run        print every command and file write, run and write nothing.
  --offline        no network: every pip call (also inside 'make core') reads wheels only from
                   the folder $WHEELHOUSE (default: .wheelhouse in this folder). Stops with an
                   error if that folder is missing; fill it with 'pip download -d <folder> ...'.
EOF
}

ROLE=cluster
ACCOUNT_FLAG=""
SKIP_ACCOUNT_CHECK=0
NO_CHECK=0
FULL_CHECK=0
DRY_RUN=0
OFFLINE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --role)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            ROLE="$2"
            shift 2
            ;;
        --account)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            ACCOUNT_FLAG="$2"
            shift 2
            ;;
        --skip-account-check)
            SKIP_ACCOUNT_CHECK=1
            shift
            ;;
        --no-check)
            NO_CHECK=1
            shift
            ;;
        --full-check)
            FULL_CHECK=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --offline)
            OFFLINE=1
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "install.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$ROLE" in
    cluster | laptop) ;;
    *)
        echo "install.sh: unknown role: $ROLE" >&2
        usage >&2
        exit 2
        ;;
esac

if [[ -n "$ACCOUNT_FLAG" && ! "$ACCOUNT_FLAG" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "install.sh: the account may only contain letters, digits, '_', '.' and '-'" >&2
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CRAB_DIR="$ROOT/CRAB"
VENV_BIN="$CRAB_DIR/.venv/bin"

# sbatchman_installed_version: asks the venv's pip. Sets SBATCHMAN_FOUND (the installed version,
# "" when none) and PIP_SHOW_OUT (pip's output); returns pip's status.
SBATCHMAN_FOUND=""
PIP_SHOW_OUT=""
sbatchman_installed_version() {
    SBATCHMAN_FOUND=""
    if PIP_SHOW_OUT="$("$VENV_BIN/pip" show sbatchman 2>&1)"; then
        SBATCHMAN_FOUND="$(printf '%s\n' "$PIP_SHOW_OUT" | sed -n 's/^Version: *//p' | head -n 1)"
        return 0
    fi
    return 1
}

# Prints the command, then runs it (unless --dry-run).
run() {
    printf '+ %s\n' "$*"
    if [[ $DRY_RUN -eq 0 ]]; then
        "$@"
    fi
}

# Same, with a working directory.
run_in() {
    local dir="$1"
    shift
    printf '+ cd %s && %s\n' "$dir" "$*"
    if [[ $DRY_RUN -eq 0 ]]; then
        (cd "$dir" && "$@")
    fi
}

# write_file PATH CONTENT: prints the write; writes only outside --dry-run.
write_file() {
    local path="$1" content="$2"
    printf '+ write %s\n' "$path"
    if [[ $DRY_RUN -eq 0 ]]; then
        mkdir -p "$(dirname "$path")"
        printf '%s' "$content" >"$path"
    fi
}

# read_file VAR PATH: sets VAR to the file's exact text, trailing newlines kept ("" when missing).
# printf -v instead of a nameref: bash 3.2 (the /bin/bash of macOS) has no 'local -n'. The
# helper's own variable is named so it cannot clash with the caller's VAR.
read_file() {
    local _read_file_text=""
    if [[ -f "$2" ]]; then
        IFS= read -r -d '' _read_file_text <"$2" || true
    fi
    printf -v "$1" '%s' "$_read_file_text"
}

# --offline: no pip call touches the network; wheels come from one local folder. Exported for the
# whole run, so the pip inside 'make core' inherits it. Checked before any install step.
if [[ $OFFLINE -eq 1 ]]; then
    WHEEL_DIR="${WHEELHOUSE:-$ROOT/.wheelhouse}"
    if [[ ! -d "$WHEEL_DIR" ]]; then
        echo "install.sh: --offline needs the wheel folder $WHEEL_DIR (set WHEELHOUSE to use another): fill it on a machine with network using 'pip download -d $WHEEL_DIR <packages>', then copy it here." >&2
        exit 1
    fi
    WHEEL_DIR="$(cd "$WHEEL_DIR" && pwd -P)"
    printf '+ export PIP_NO_INDEX=1 PIP_FIND_LINKS=%s\n' "$WHEEL_DIR"
    export PIP_NO_INDEX=1 PIP_FIND_LINKS="$WHEEL_DIR"
fi

# A cluster Python module exports PYTHONPATH, which breaks the venv's pip.
unset PYTHONPATH PYTHONHOME

# 1. Python 3.10 or newer, before anything is created.
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    found="$(python3 --version 2>&1 || echo 'not found')"
    echo "python3 is ${found}: 3.10 or newer is needed. On a cluster run 'module load python' first. On a Mac install Python 3.10 or newer from python.org or Homebrew and put it first on PATH. Then run install.sh again." >&2
    exit 1
fi

# 1b. Cluster only: the Slurm account, resolved and checked now, so a wrong one stops the run
# within a second and not after the slow steps. Order: --account, then site/local.env (and
# site/*.env), then one question. The account is written to site/local.env only after the check.
if [[ "$ROLE" == cluster ]]; then
    LOCAL_ENV="$ROOT/site/local.env"
    SLURM_ACCOUNT=""
    SLURM_PARTITION=""
    SLURM_QOS=""
    SBATCHMAN_CLUSTER_NAME=""
    # shellcheck source=/dev/null
    [[ -f "$ROOT/site/leonardo.env" ]] && source "$ROOT/site/leonardo.env"
    # shellcheck source=/dev/null
    [[ -f "$LOCAL_ENV" ]] && source "$LOCAL_ENV"

    # set_account NAME: create or replace the one SLURM_ACCOUNT line of site/local.env.
    set_account() {
        local name="$1" old new="" line replaced=0
        read_file old "$LOCAL_ENV"
        while IFS= read -r line || [[ -n "$line" ]]; do
            if [[ "$line" == SLURM_ACCOUNT=* ]]; then
                if [[ $replaced -eq 0 ]]; then
                    new+="SLURM_ACCOUNT=\"$name\""$'\n'
                    replaced=1
                fi
            else
                new+="$line"$'\n'
            fi
        done <<<"${old%$'\n'}"
        if [[ $replaced -eq 0 ]]; then
            new+="SLURM_ACCOUNT=\"$name\""$'\n'
        fi
        # An empty file leaves one blank line from the here-string: start clean.
        if [[ -z "$old" ]]; then
            new="SLURM_ACCOUNT=\"$name\""$'\n'
        fi
        if [[ "$new" != "$old" ]]; then
            write_file "$LOCAL_ENV" "$new"
        fi
        SLURM_ACCOUNT="$name"
    }

    # check_slurm_account NAME: NAME must be one of the user's Slurm associations (one lookup,
    # whole-line match, case-insensitive: Slurm takes the account in any case, and sacctmgr may list
    # it in another case than the one the site prints). No sacctmgr, or a lookup that cannot answer (non-zero
    # exit, empty output: accounting unreachable), is a note and the run goes on; a lookup that
    # answers without NAME stops the run.
    check_slurm_account() {
        local name="$1" user out line want
        if [[ $SKIP_ACCOUNT_CHECK -eq 1 ]]; then
            echo "install.sh: note: the account $name was not checked against Slurm (--skip-account-check)" >&2
            return 0
        fi
        if ! command -v sacctmgr >/dev/null 2>&1; then
            echo "install.sh: note: sacctmgr is not on PATH, so the account $name was not checked against Slurm." >&2
            return 0
        fi
        user="${USER:-$(id -un 2>/dev/null || true)}"
        if [[ -z "$user" ]] || ! out="$(sacctmgr -n -P show assoc user="$user" format=account 2>/dev/null)" || [[ -z "${out//[[:space:]]/}" ]]; then
            echo "install.sh: note: sacctmgr gave no answer, so the account $name was not checked against Slurm." >&2
            return 0
        fi
        want="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"
        while IFS= read -r line || [[ -n "$line" ]]; do
            line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
            [[ "$line" == "$want" ]] && return 0
        done <<<"$out"
        echo "install.sh: the account $name is not among the Slurm accounts of user $user (sacctmgr). Pass the right one with --account NAME, or --skip-account-check to skip this lookup." >&2
        exit 1
    }

    account_new=0
    if [[ -n "$ACCOUNT_FLAG" ]]; then
        SLURM_ACCOUNT="$ACCOUNT_FLAG"
        account_new=1
    elif [[ -z "$SLURM_ACCOUNT" || "$SLURM_ACCOUNT" == "<YOUR_ACCOUNT>" ]]; then
        if [[ -t 0 ]]; then
            read -r -p "Slurm account: " SLURM_ACCOUNT
            account_new=1
        else
            echo 'no Slurm account: pass --account NAME or create site/local.env with SLURM_ACCOUNT="NAME"' >&2
            exit 2
        fi
    fi
    if [[ ! "$SLURM_ACCOUNT" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        echo "install.sh: the account may only contain letters, digits, '_', '.' and '-'" >&2
        exit 2
    fi
    check_slurm_account "$SLURM_ACCOUNT"
    if [[ $account_new -eq 1 ]]; then
        set_account "$SLURM_ACCOUNT"
    fi
fi

# 2. The CRAB checkout.
if [[ ! -e "$CRAB_DIR/Makefile" && -e "$ROOT/.git" ]]; then
    run git -C "$ROOT" submodule update --init
fi
if [[ ! -e "$CRAB_DIR/Makefile" ]]; then
    if [[ $DRY_RUN -eq 1 && -e "$ROOT/.git" ]]; then
        echo "install.sh: note: CRAB/Makefile is not there yet; the submodule update above would fetch it." >&2
    else
        echo "install.sh: CRAB/Makefile is missing. Run 'git submodule update --init' and try again." >&2
        exit 1
    fi
fi

# 3. The wrappers: CRAB/wrappers is a relative link to the submodule.
if [[ -e "$CRAB_DIR/wrappers" || -L "$CRAB_DIR/wrappers" ]]; then
    if [[ ! -L "$CRAB_DIR/wrappers" || "$(readlink "$CRAB_DIR/wrappers")" != "../crab-wrappers" ]]; then
        echo "install.sh: warning: $CRAB_DIR/wrappers is not a link to ../crab-wrappers; leaving it as it is." >&2
    fi
else
    run ln -s ../crab-wrappers "$CRAB_DIR/wrappers"
fi

# 4. CRAB with the web-less core, in CRAB/.venv.
run make -C "$CRAB_DIR" core

# 5. SbatchMan into the same venv.
# Cluster role: pip is not called when the pinned version is already there (never asked on
# --dry-run: the venv may not exist). The laptop role always installs the visualization extra,
# because pip show cannot tell whether the extra's packages are present.
if [[ "$ROLE" == cluster ]]; then
    if [[ $DRY_RUN -eq 0 ]] && sbatchman_installed_version && [[ "$SBATCHMAN_FOUND" == "$SBATCHMAN_VERSION" ]]; then
        echo "sbatchman $SBATCHMAN_VERSION is already installed, skipping pip"
    else
        run "$VENV_BIN/pip" install "sbatchman==$SBATCHMAN_VERSION"
    fi
else
    run "$VENV_BIN/pip" install -e "$CRAB_DIR[web]"
    run "$VENV_BIN/pip" install "sbatchman[visualization]==$SBATCHMAN_VERSION"
fi

# 6. Cluster only: the configs file (the account was resolved and checked in step 1b).
if [[ "$ROLE" == cluster ]]; then
    TEMPLATE="$ROOT/configs/leonardo.yaml"
    TARGET="$ROOT/.local/configs.leonardo.yaml"
    if [[ ! -f "$TEMPLATE" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            echo "install.sh: note: $TEMPLATE is not there yet; the configs file would not be written." >&2
        else
            echo "install.sh: the template $TEMPLATE is missing." >&2
            exit 1
        fi
    else
        shopt -u patsub_replacement 2>/dev/null || true
        read_file content "$TEMPLATE"
        # The tokens sit in variables, not in nested quotes: bash 3.2 would keep those quote
        # characters in the text. The values are used literally (patsub_replacement is off).
        token_account='<YOUR_ACCOUNT>'
        token_partition='<SLURM_PARTITION>'
        token_qos='<SLURM_QOS>'
        token_crab_dir='<CRAB_DIR>'
        content="${content//$token_account/$SLURM_ACCOUNT}"
        content="${content//$token_partition/$SLURM_PARTITION}"
        content="${content//$token_qos/$SLURM_QOS}"
        content="${content//$token_crab_dir/$CRAB_DIR}"
        left="$(printf '%s' "$content" | grep -o -E '<[A-Z_]+>' | sort -u | tr '\n' ' ' || true)"
        if [[ -n "$left" ]]; then
            echo "install.sh: the configs template still has unfilled tokens: $left" >&2
            exit 1
        fi
        read_file current "$TARGET"
        if [[ "$content" != "$current" ]]; then
            write_file "$TARGET" "$content"
        fi
    fi
fi

# 7. One SbatchMan project per benchmark folder.
for dir in "$ROOT"/benchmarks/*/; do
    [[ -d "$dir" ]] || continue
    dir="${dir%/}"
    # Only folders that hold a benchmark file: a stray folder (__pycache__) is not a project.
    compgen -G "$dir/*.yaml" > /dev/null || continue
    if [[ ! -d "$dir/SbatchMan" ]]; then
        run_in "$dir" "$VENV_BIN/sbatchman" init
    fi
done

# 7b. env.sh: what a partner sources in every new shell. It finds its own folder when
# sourced (bash and zsh), so it holds no absolute path and a moved umbrella still works.
env_head="# env.sh, written by install.sh (role $ROLE). Source it: . ./env.sh"$'\n'
IFS= read -r -d '' env_body <<'EOF' || true
_umbrella_env_here="${BASH_SOURCE[0]:-$0}"
UMBRELLA_ROOT="$(cd "$(dirname "$_umbrella_env_here")" && pwd -P)"
unset _umbrella_env_here
unset PYTHONPATH PYTHONHOME
. "$UMBRELLA_ROOT/CRAB/.venv/bin/activate"
export CRAB_PATH_WRAPPERS="$UMBRELLA_ROOT/crab-wrappers"
EOF
if [[ "$ROLE" == cluster ]]; then
    cluster_name="${SBATCHMAN_CLUSTER_NAME:-leonardo}"
    if [[ ! "$cluster_name" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        echo "install.sh: SBATCHMAN_CLUSTER_NAME may only contain letters, digits, '_', '.' and '-'" >&2
        exit 2
    fi
    env_role="export SBATCHMAN_CLUSTER_NAME=\"$cluster_name\""$'\n'
else
    env_role='export CRAB_WEB_PORT="${CRAB_WEB_PORT:-8899}"'$'\n'
fi
env_tail='echo "crab:      $(command -v crab)"'$'\n''echo "sbatchman: $(command -v sbatchman)"'$'\n'
env_content="$env_head$env_body$env_role$env_tail"
read_file env_current "$ROOT/env.sh"
if [[ "$env_content" != "$env_current" ]]; then
    write_file "$ROOT/env.sh" "$env_content"
fi

# 8. The self-check: one OK or FAIL line per check, a summary, exit status 1 if any failed.
# It submits no job: the launch check is a dry run. A failed check does not stop the later ones.
CHECKS_FAILED=0
SMOKE_FILE="smoke.yaml"
SMOKE_DIR="$ROOT/benchmarks/blink"

check_ok() {
    printf 'OK %s\n' "$1"
}

check_fail() {
    printf 'FAIL %s: %s\n' "$1" "$2"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

# one_line TEXT: the text on one line, cut at 300 characters ("(no output)" when empty).
one_line() {
    local text="${1//$'\n'/ }"
    [[ -n "${text// /}" ]] || text="(no output)"
    printf '%s' "${text:0:300}"
}

# Reads a jobs file and writes one JSON file per config.json it would create (every value of
# its variables, the heredoc of each job), the same way tests/test_benchmarks.py does. Prints
# the paths; any problem goes to stderr with exit status 1.
IFS= read -r -d '' EXTRACT_PY <<'PY' || true
import itertools
import json
import re
import sys
from pathlib import Path

import yaml

path, outdir, crab_dir = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
try:
    doc = yaml.safe_load(path.read_text())
except (OSError, yaml.YAMLError) as error:
    sys.exit(f"cannot read it as YAML: {error}")
if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), list) or not doc["jobs"]:
    sys.exit("it has no 'jobs' list")
variables = doc.get("variables") or {}
names = list(variables)
heredoc = re.compile(r"<<'?JSON'?\n(.*?)\nJSON\n", re.DOTALL)
count = 0
for job in doc["jobs"]:
    preprocess = job.get("preprocess", "") if isinstance(job, dict) else ""
    match = heredoc.search(str(preprocess))
    if not match:
        sys.exit("a job has no config.json heredoc (<<JSON ... JSON) in its preprocess")
    for values in itertools.product(*(variables[name] for name in names)):
        text = match.group(1)
        for name, value in zip(names, values):
            text = text.replace("{" + name + "}", str(value))
        text = text.replace("$SBATCHMAN_WD", str(path.parent)).replace("$CRAB_ROOT", crab_dir)
        left = re.findall(r"\{[a-z_]+\}", text)
        if left:
            sys.exit(f"the embedded config still has the unfilled variable {left[0]}")
        try:
            json.loads(text)
        except ValueError as error:
            sys.exit(f"the embedded config is not valid JSON: {error}")
        count += 1
        out = outdir / f"{path.stem}-{count}.json"
        out.write_text(text + "\n")
        print(out)
PY

# check_jobs_file FILE OUTDIR: every config of the jobs file passes `crab validate`.
check_jobs_file() {
    local file="$1" outdir="$2" rel out json count=0 total=0
    local all=() picked=()
    rel="${file#"$ROOT"/}"
    mkdir -p "$outdir"
    if ! out="$("$VENV_BIN/python" -c "$EXTRACT_PY" "$file" "$outdir" "$CRAB_DIR" 2>&1)"; then
        check_fail "jobs file $rel" "$(one_line "$out")"
        return 0
    fi
    while IFS= read -r json; do
        [[ -f "$json" ]] || continue
        all+=("$json")
    done <<<"$out"
    total=${#all[@]}
    if [[ $total -eq 0 ]]; then
        check_fail "jobs file $rel" "no config to validate"
        return 0
    fi
    # Without --full-check only the first and the last combination go through crab validate.
    if [[ $FULL_CHECK -eq 1 || $total -le 2 ]]; then
        picked=("${all[@]}")
    else
        picked=("${all[0]}" "${all[$((total - 1))]}")
    fi
    for json in "${picked[@]}"; do
        count=$((count + 1))
        if ! out="$(CRAB_PATH_WRAPPERS="$ROOT/crab-wrappers" CRAB_ROOT="$CRAB_DIR" "$VENV_BIN/crab" validate "$json" 2>&1)"; then
            check_fail "jobs file $rel" "crab validate: $(one_line "$out")"
            return 0
        fi
    done
    check_ok "jobs file $rel passes crab validate ($count config(s))"
}

# The dry-run launch writes into the SbatchMan project it finds (the configs of the cluster and
# its cache), so it runs in a throw-away copy: the benchmark's real project stays as it is.
CHECK_TMP=""

# Removes the copy: exactly the folder mktemp made, never an empty name.
check_cleanup() {
    if [[ -n "$CHECK_TMP" ]]; then
        rm -rf "$CHECK_TMP"
    fi
    CHECK_TMP=""
}

# dry_run_launch_in_copy: runs `sbatchman init` and `sbatchman launch -f smoke.yaml --dry-run` in a
# temporary copy that holds the smoke jobs file and a link to .local (the jobs file's relative
# "configs:" line still reaches the filled configs file). Sets LAUNCH_OUT to the output and returns
# the status. The copy is removed when the launch ends, fails, or the script is interrupted.
dry_run_launch_in_copy() {
    local copy status=0
    LAUNCH_OUT=""
    trap check_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    if ! CHECK_TMP="$(mktemp -d "${TMPDIR:-/tmp}/crab-umbrella-check.XXXXXX")"; then
        CHECK_TMP=""
        LAUNCH_OUT="cannot create a temporary folder under ${TMPDIR:-/tmp}"
        status=1
    else
        copy="$CHECK_TMP/benchmarks/blink"
        if LAUNCH_OUT="$(
            export PATH="$VENV_BIN:$PATH" SBATCHMAN_CLUSTER_NAME="$cluster_name" CRAB_PATH_WRAPPERS="$ROOT/crab-wrappers"
            {
                mkdir -p "$copy" &&
                    cp "$SMOKE_DIR/$SMOKE_FILE" "$copy/$SMOKE_FILE" &&
                    ln -s "$ROOT/.local" "$CHECK_TMP/.local" &&
                    cd "$copy" &&
                    "$VENV_BIN/sbatchman" init &&
                    "$VENV_BIN/sbatchman" launch -f "$SMOKE_FILE" --dry-run
            } 2>&1
        )"; then
            status=0
        else
            status=1
        fi
    fi
    check_cleanup
    trap - EXIT INT TERM
    return "$status"
}

check_install() {
    local file rel out found resolved tool problem dir workdir n=0
    echo
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "would check: python 3.10 or newer in the venv"
        echo "would check: sbatchman $SBATCHMAN_VERSION installed in the venv"
        echo "would check: crab resolves inside CRAB/.venv/bin"
        echo "would check: sbatchman resolves inside CRAB/.venv/bin"
        echo "would check: the wrappers folders are not empty"
        for file in "$ROOT"/benchmarks/*/*.yaml; do
            [[ -f "$file" ]] || continue
            echo "would check: jobs file ${file#"$ROOT"/} passes crab validate"
        done
        if [[ "$ROLE" == cluster ]]; then
            echo "would check: sbatchman launch --dry-run on benchmarks/blink/$SMOKE_FILE (submits nothing)"
        fi
        return 0
    fi
    echo "Checking the install (no Slurm job is submitted):"

    # a. Python and SbatchMan in the venv.
    if "$VENV_BIN/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        check_ok "python 3.10 or newer in the venv"
    else
        found="$("$VENV_BIN/python" --version 2>&1 || true)"
        check_fail "python in the venv" "CRAB/.venv/bin/python needs 3.10 or newer, found: $(one_line "$found")"
    fi
    if sbatchman_installed_version; then
        found="$SBATCHMAN_FOUND"
        if [[ "$found" == "$SBATCHMAN_VERSION" ]]; then
            check_ok "sbatchman $SBATCHMAN_VERSION installed in the venv"
        else
            check_fail "sbatchman version" "found ${found:-none}, expected $SBATCHMAN_VERSION"
        fi
    else
        check_fail "sbatchman version" "pip show sbatchman failed: $(one_line "$PIP_SHOW_OUT")"
    fi

    # b. The two commands resolve inside the venv once env.sh has put it first on PATH.
    for tool in crab sbatchman; do
        resolved="$(PATH="$VENV_BIN:$PATH" command -v "$tool" || true)"
        if [[ "$resolved" == "$VENV_BIN/$tool" ]]; then
            check_ok "$tool resolves inside CRAB/.venv/bin"
        else
            found="${resolved#"$ROOT"/}"
            check_fail "$tool in the venv" "it resolves to ${found:-nothing}, not CRAB/.venv/bin/$tool"
        fi
    done

    # c. The wrappers: the folder env.sh exports and the link the jobs use.
    problem=""
    for dir in "$ROOT/crab-wrappers" "$CRAB_DIR/wrappers"; do
        if [[ ! -d "$dir" ]]; then
            problem="${dir#"$ROOT"/} is not a folder (run: git submodule update --init)"
        elif ! compgen -G "$dir/*" >/dev/null; then
            problem="${dir#"$ROOT"/} is empty (run: git submodule update --init)"
        fi
        [[ -z "$problem" ]] || break
    done
    if [[ -z "$problem" ]]; then
        check_ok "wrappers folders are not empty"
    else
        check_fail "wrappers folder" "$problem"
    fi

    # d. Every shipped jobs file: its embedded configs pass `crab validate`.
    workdir="$(mktemp -d)"
    for file in "$ROOT"/benchmarks/*/*.yaml; do
        [[ -f "$file" ]] || continue
        n=$((n + 1))
        check_jobs_file "$file" "$workdir/$n"
    done
    rm -rf "$workdir"

    # e. Cluster only: SbatchMan reads the smoke file and lists its jobs; nothing is submitted.
    if [[ "$ROLE" == cluster ]]; then
        if [[ ! -f "$SMOKE_DIR/$SMOKE_FILE" ]]; then
            check_fail "sbatchman launch --dry-run" "benchmarks/blink/$SMOKE_FILE is missing"
        elif dry_run_launch_in_copy; then
            check_ok "sbatchman launch --dry-run on benchmarks/blink/$SMOKE_FILE (submits nothing)"
        else
            check_fail "sbatchman launch --dry-run on benchmarks/blink/$SMOKE_FILE" "$(one_line "$LAUNCH_OUT")"
        fi
    fi

    if [[ $CHECKS_FAILED -eq 0 ]]; then
        echo "install.sh: all checks passed"
    else
        echo "install.sh: $CHECKS_FAILED check(s) failed"
    fi
}

if [[ $NO_CHECK -eq 0 ]]; then
    check_install
fi

if [[ $DRY_RUN -eq 1 ]]; then
    echo "install.sh finished: role $ROLE (dry run, nothing was changed)"
else
    echo "install.sh finished: role $ROLE"
    echo "Next: source env.sh"
fi

# The self-check's verdict: a failed check makes the whole run exit 1.
[[ $CHECKS_FAILED -eq 0 ]] || exit 1
