#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/install-local.sh --prefix <dir> [--profile debug|release] [--no-build]

Installs the private-local TuringOS CLI and daemon binaries into <dir>/bin.
The script only builds and copies executables; it does not write Micro Tape,
move heads, proxy credentials, or start background services.
USAGE
}

prefix=""
profile="release"
build=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      if [[ $# -lt 2 ]]; then
        echo "--prefix requires a directory" >&2
        exit 2
      fi
      prefix="$2"
      shift 2
      ;;
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "--profile requires debug or release" >&2
        exit 2
      fi
      profile="$2"
      shift 2
      ;;
    --no-build)
      build=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown install-local argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$prefix" ]]; then
  echo "--prefix is required" >&2
  usage >&2
  exit 2
fi

if [[ "$profile" != "debug" && "$profile" != "release" ]]; then
  echo "--profile must be debug or release" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
target_root="${CARGO_TARGET_DIR:-$repo_root/target}"

build_args=(build -p turing-cli -p turing-daemons --bins)
if [[ "$profile" == "release" ]]; then
  build_args+=(--release)
fi

if [[ "$build" -eq 1 ]]; then
  cargo "${build_args[@]}"
fi

install_dir="$prefix/bin"
mkdir -p "$install_dir"

binaries=(
  turing
  turingd
  turing-execd
  turing-marketd
  turing-pputd
  turing-viewd
  turing-mcp
)

for binary in "${binaries[@]}"; do
  source_path="$target_root/$profile/$binary"
  if [[ ! -x "$source_path" ]]; then
    echo "missing built binary: $source_path" >&2
    exit 2
  fi
  install -m 0755 "$source_path" "$install_dir/$binary"
  echo "installed $binary -> $install_dir/$binary"
done
