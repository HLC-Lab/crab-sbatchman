#!/usr/bin/env bash
# Installs the umbrella on this machine. Safe to run again: a second run prints the same
# commands and changes no file. Every command is printed before it runs; --dry-run prints
# them and runs nothing.
set -euo pipefail

# The one place that pins SbatchMan (override from the environment).
SBATCHMAN_VERSION="${SBATCHMAN_VERSION:-2.0.4}"

usage() {
    cat <<'EOF'
Usage: ./install.sh [--role cluster|laptop] [--account NAME] [--no-setup] [--dry-run]
                    [--login-host HOST] [--user NAME] [--remote-dir PATH] [-h|--help]

  --role ROLE      cluster (default): CRAB, SbatchMan, the configs file, the setup wizard.
                   laptop: CRAB with the web dashboard and SbatchMan with its plots.
  --account NAME   Slurm account to charge; saved in site/local.env (cluster role).
  --no-setup       skip the interactive 'crab setup' wizard at the end.
  --dry-run        print every command and file write, run and write nothing.
  --login-host HOST, --user NAME, --remote-dir PATH
                   laptop only: the cluster's login host, your user there and the umbrella's
                   folder on the cluster. They only fill the help block printed at the end;
                   nothing is saved (site/local.env may hold SITE_LOGIN_HOST, SITE_USER and
                   SITE_REMOTE_DIR instead).
EOF
}

ROLE=cluster
ACCOUNT_FLAG=""
NO_SETUP=0
DRY_RUN=0
LOGIN_HOST_FLAG=""
USER_FLAG=""
REMOTE_DIR_FLAG=""

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
        --login-host)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            LOGIN_HOST_FLAG="$2"
            shift 2
            ;;
        --user)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            USER_FLAG="$2"
            shift 2
            ;;
        --remote-dir)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            REMOTE_DIR_FLAG="$2"
            shift 2
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

if [[ "$ROLE" == cluster && (-n "$LOGIN_HOST_FLAG" || -n "$USER_FLAG" || -n "$REMOTE_DIR_FLAG") ]]; then
    echo "install.sh: --login-host, --user and --remote-dir are for --role laptop" >&2
    usage >&2
    exit 2
fi
if [[ -n "$LOGIN_HOST_FLAG" && ! "$LOGIN_HOST_FLAG" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "install.sh: --login-host may only contain letters, digits, '.' and '-'" >&2
    exit 2
fi
if [[ -n "$USER_FLAG" && ! "$USER_FLAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "install.sh: --user may only contain letters, digits, '.', '_' and '-'" >&2
    exit 2
fi
if [[ -n "$REMOTE_DIR_FLAG" && ! "$REMOTE_DIR_FLAG" =~ ^[A-Za-z0-9._/~-]+$ ]]; then
    echo "install.sh: --remote-dir may only contain letters, digits, '.', '_', '/', '~' and '-'" >&2
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

# 8. The benchmarks wizard, last: it asks questions.
if [[ "$ROLE" == cluster && $NO_SETUP -eq 0 ]]; then
    echo "Next: register the benchmarks you will run (skip with --no-setup)."
    run "$VENV_BIN/crab" setup
fi

if [[ $DRY_RUN -eq 1 ]]; then
    echo "install.sh finished: role $ROLE (dry run, nothing was changed)"
else
    echo "install.sh finished: role $ROLE"
    echo "Next: source env.sh"
fi

# 9. Laptop only: what to type into the dashboard and the sbatchman fetch config. Printed
# only: nothing here is written into the home folder.
if [[ "$ROLE" == laptop ]]; then
    SITE_LOGIN_HOST=""
    SITE_USER=""
    SITE_REMOTE_DIR=""
    SBATCHMAN_CLUSTER_NAME=""
    # shellcheck source=/dev/null
    [[ -f "$ROOT/site/leonardo.env" ]] && source "$ROOT/site/leonardo.env"
    # shellcheck source=/dev/null
    [[ -f "$ROOT/site/local.env" ]] && source "$ROOT/site/local.env"

    cluster_name="${SBATCHMAN_CLUSTER_NAME:-leonardo}"
    login_host="${LOGIN_HOST_FLAG:-${SITE_LOGIN_HOST:-<login-host>}}"
    remote_user="${USER_FLAG:-${SITE_USER:-<your-user>}}"
    remote_dir="${REMOTE_DIR_FLAG:-${SITE_REMOTE_DIR:-<umbrella-folder-on-the-cluster>}}"
    remote_dir="${remote_dir%/}"
    # Values from site/local.env get the same checks as the flags (the placeholders pass).
    if [[ ! "$cluster_name" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        echo "install.sh: SBATCHMAN_CLUSTER_NAME may only contain letters, digits, '_', '.' and '-'" >&2
        exit 2
    fi
    if [[ "$login_host" != "<login-host>" && ! "$login_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
        echo "install.sh: SITE_LOGIN_HOST may only contain letters, digits, '.' and '-'" >&2
        exit 2
    fi
    if [[ "$remote_user" != "<your-user>" && ! "$remote_user" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "install.sh: SITE_USER may only contain letters, digits, '.', '_' and '-'" >&2
        exit 2
    fi
    if [[ "$remote_dir" != "<umbrella-folder-on-the-cluster>" && ! "$remote_dir" =~ ^[A-Za-z0-9._/~-]+$ ]]; then
        echo "install.sh: SITE_REMOTE_DIR may only contain letters, digits, '.', '_', '/', '~' and '-'" >&2
        exit 2
    fi
    # The umbrella's own path goes into TOML basic strings: escape backslash and quote.
    toml_root="${ROOT//\\/\\\\}"
    toml_root="${toml_root//\"/\\\"}"

    benchmark_names=()
    for dir in "$ROOT"/benchmarks/*/; do
        [[ -d "$dir" ]] || continue
        dir="${dir%/}"
        benchmark_names+=("${dir##*/}")
    done

    cat <<EOF

== crab web: add the cluster
In crab web, open Remotes and press "+ Add cluster", then type these values:
  Name: $cluster_name
  Transport: ssh
  Host: $login_host
  User: $remote_user
  Port: 22
  Auth: agent (ssh-agent / cert)
  Host key: insecure (rotating login nodes)
  Install dir: $remote_dir
  Crab command: (leave empty)
  Preset: (leave empty)
Start crab web from the shell that has your ssh agent (the certificate login), because the agent is found through SSH_AUTH_SOCK.
Never press "Install CRAB" for this cluster: the umbrella already installed it, and the button would add a second, separate CRAB.

== sbatchman fetch: results to this laptop
Save this as ~/.config/sbatchman/remotes-config.toml (merge by hand if the file exists):
--- remotes-config.toml ---
[global]
local_base = "$toml_root/benchmarks"
transfer_backend = "rsync"
fetch_excludes = ["scratch"]

[[clusters]]
name = "$cluster_name"
host = "$login_host"
port = 22
user = "$remote_user"
EOF
    for name in ${benchmark_names[@]+"${benchmark_names[@]}"}; do
        cat <<EOF

[[clusters.fetch_dirs]]
remote = "$remote_dir/benchmarks/$name/SbatchMan"
local = "$toml_root/benchmarks/$name/SbatchMan"
EOF
    done
    cat <<EOF
--- end ---

== start the tools
source env.sh
crab web          # dashboard, http://127.0.0.1:8899
cd benchmarks/${benchmark_names[0]:-<benchmark>} && sbatchman fetch && sbatchman visualize   # plots, http://127.0.0.1:8765
EOF
fi
