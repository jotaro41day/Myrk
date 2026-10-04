#!/usr/bin/env sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

termux_detected=0
case "${PREFIX:-}" in
    */com.termux/*) termux_detected=1 ;;
esac
if [ -n "${TERMUX_VERSION:-}" ]; then
    termux_detected=1
fi

if [ "${1:-}" = "--prefix" ]; then
    if [ "$#" -ne 2 ]; then
        printf '%s\n' 'usage: ./install.sh [--prefix DIRECTORY]' >&2
        exit 2
    fi
    install_prefix=$2
elif [ "$#" -ne 0 ]; then
    printf '%s\n' 'usage: ./install.sh [--prefix DIRECTORY]' >&2
    exit 2
elif [ -n "${MYRK_PREFIX:-}" ]; then
    install_prefix=$MYRK_PREFIX
else
    if [ "$termux_detected" -eq 1 ] && [ -n "${PREFIX:-}" ]; then
        install_prefix=$PREFIX
    else
        install_prefix=$HOME/.local
    fi
fi

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Myrk needs Python 3 (Termux: pkg install python).' >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    printf '%s\n' 'Myrk needs Python 3.10 or newer.' >&2
    exit 1
fi
if ! command -v clang >/dev/null 2>&1 && ! command -v cc >/dev/null 2>&1; then
    printf '%s\n' 'Myrk needs a C compiler (Termux: pkg install clang).' >&2
    exit 1
fi
if ! command -v install >/dev/null 2>&1; then
    printf '%s\n' 'Myrk needs the install command (Termux: pkg install coreutils).' >&2
    exit 1
fi

case "$install_prefix" in
    /*) ;;
    *) printf '%s\n' 'installation prefix must be an absolute path' >&2; exit 2 ;;
esac

mkdir -p "$install_prefix/bin" "$install_prefix/share/myrk/myrk"
install -m 644 "$repo_dir"/myrk/*.py "$install_prefix/share/myrk/myrk/"
install -m 755 "$repo_dir/bin/myrk" "$install_prefix/bin/myrk"
if [ "$termux_detected" -eq 1 ]; then
    printf 'Detected Termux on %s.\n' "$(uname -m)"
fi
printf 'Installed Myrk at %s/bin/myrk\n' "$install_prefix"
case ":$PATH:" in
    *":$install_prefix/bin:"*) ;;
    *) printf 'Add %s/bin to PATH to use myrk in new shells.\n' "$install_prefix" ;;
esac
