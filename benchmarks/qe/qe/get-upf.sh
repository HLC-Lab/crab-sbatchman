#!/usr/bin/env bash
# Download the pseudopotential Si.pz-vbc.UPF into this folder.
#
# Why it is not in git: its licence is unclear, so the repo does not ship it (.gitignore lists it).
# Where to run it: on the login node. Compute nodes have no internet, so a job cannot download it.
# Source: https://pseudopotentials.quantum-espresso.org/upf_files/Si.pz-vbc.UPF
# The script checks the sha256 below. A file with another hash is never kept.
#
# Usage: benchmarks/qe/qe/get-upf.sh
set -euo pipefail

URL="https://pseudopotentials.quantum-espresso.org/upf_files/Si.pz-vbc.UPF"
NAME="Si.pz-vbc.UPF"
EXPECTED_SHA256="e8d933754cd51c6bb4b2a809151f89e0647e53d878bab88d26e1b5a5d68d5217"

here="$(cd "$(dirname "$0")" && pwd)"
target="$here/$NAME"
tmp="$here/.$NAME.part"

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d ' ' -f 1
    else
        shasum -a 256 "$1" | cut -d ' ' -f 1
    fi
}

if [ -f "$target" ] && [ "$(sha256_of "$target")" = "$EXPECTED_SHA256" ]; then
    echo "$NAME is already there ($target)"
    exit 0
fi

trap 'rm -f "$tmp"' EXIT
rm -f "$tmp"

echo "downloading $URL"
if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location --max-time 120 --output "$tmp" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget --quiet --timeout=120 --output-document="$tmp" "$URL"
else
    echo "get-upf.sh: neither curl nor wget is installed" >&2
    exit 1
fi

got="$(sha256_of "$tmp")"
if [ "$got" != "$EXPECTED_SHA256" ]; then
    echo "get-upf.sh: wrong sha256 for the download of $NAME, the download was deleted" >&2
    echo "  expected: $EXPECTED_SHA256" >&2
    echo "  got:      $got" >&2
    exit 1
fi

mv "$tmp" "$target"
echo "saved $target (sha256 ok)"
