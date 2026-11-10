#!/usr/bin/env bash
# Installs the umbrella on this machine. Safe to run again: a second run prints the same
# commands and changes no file. Every command is printed before it runs; --dry-run prints
# them and runs nothing.
set -euo pipefail

# The one place that pins SbatchMan (override from the environment).
SBATCHMAN_VERSION="${SBATCHMAN_VERSION:-2.0.4}"

usage() {
    cat <<'EOF'
Usage: ./install.sh [--role cluster|laptop] [--account NAME] [--no-setup] [--dry-run] [-h|--help]

  --role ROLE      cluster (default): CRAB, SbatchMan, the configs file, the setup wizard.
                   laptop: CRAB with the web dashboard and SbatchMan with its plots.
  --account NAME   Slurm account to charge; saved in site/local.env (cluster role).
  --no-setup       skip the interactive 'crab setup' wizard at the end.
  --dry-run        print every command and file write, run and write nothing.
EOF
}

ROLE=cluster
ACCOUNT_FLAG=""
NO_SETUP=0
DRY_RUN=0

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
        --no-setup)
            NO_SETUP=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
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
read_file() {
    local -n target="$1"
    target=""
    if [[ -f "$2" ]]; then
        IFS= read -r -d '' target <"$2" || true
    fi
}

# A cluster Python module exports PYTHONPATH, which breaks the venv's pip.
unset PYTHONPATH PYTHONHOME

# 1. Python 3.10 or newer, before anything is created.
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    found="$(python3 --version 2>&1 || echo 'not found')"
    echo "python3 is ${found}: 3.10 or newer is needed. On a cluster run 'module load python' first, then run install.sh again." >&2
    exit 1
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
if [[ "$ROLE" == cluster ]]; then
    run "$VENV_BIN/pip" install "sbatchman==$SBATCHMAN_VERSION"
else
    run "$VENV_BIN/pip" install -e "$CRAB_DIR[web]"
    run "$VENV_BIN/pip" install "sbatchman[visualization]==$SBATCHMAN_VERSION"
fi

# 6. Cluster only: the Slurm account and the configs file.
if [[ "$ROLE" == cluster ]]; then
    LOCAL_ENV="$ROOT/site/local.env"
    SLURM_ACCOUNT=""
    SLURM_PARTITION=""
    SLURM_QOS=""
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

    if [[ -n "$ACCOUNT_FLAG" ]]; then
        set_account "$ACCOUNT_FLAG"
    fi
    if [[ -z "$SLURM_ACCOUNT" || "$SLURM_ACCOUNT" == "<YOUR_ACCOUNT>" ]]; then
        if [[ -t 0 ]]; then
            read -r -p "Slurm account: " typed
            if [[ ! "$typed" =~ ^[A-Za-z0-9_.-]+$ ]]; then
                echo "install.sh: the account may only contain letters, digits, '_', '.' and '-'" >&2
                exit 2
            fi
            set_account "$typed"
        else
            echo 'no Slurm account: pass --account NAME or create site/local.env with SLURM_ACCOUNT="NAME"' >&2
            exit 2
        fi
    fi

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
        content="${content//"<YOUR_ACCOUNT>"/"$SLURM_ACCOUNT"}"
        content="${content//"<SLURM_PARTITION>"/"$SLURM_PARTITION"}"
        content="${content//"<SLURM_QOS>"/"$SLURM_QOS"}"
        content="${content//"<CRAB_DIR>"/"$CRAB_DIR"}"
        left="$(printf '%s' "$content" | grep -o '<[A-Z_]\+>' | sort -u | tr '\n' ' ' || true)"
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
    if [[ ! -d "$dir/SbatchMan" ]]; then
        run_in "$dir" "$VENV_BIN/sbatchman" init
    fi
done

# 8. The benchmarks wizard, last: it asks questions.
if [[ "$ROLE" == cluster && $NO_SETUP -eq 0 ]]; then
    echo "Next: register the benchmarks you will run (skip with --no-setup)."
    run "$VENV_BIN/crab" setup
fi

if [[ $DRY_RUN -eq 1 ]]; then
    echo "install.sh finished: role $ROLE (dry run, nothing was changed)"
else
    echo "install.sh finished: role $ROLE"
fi
