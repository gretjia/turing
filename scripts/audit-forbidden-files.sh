#!/usr/bin/env bash
# HW-SW-003 C2 — forbidden-file guard.
#
# Rejects any path (staged or explicitly named) that touches the
# constitution's authority tree, the constitution file itself, or the
# pinned progress tracker. Fails closed: exit 0 only means "clean".
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: audit-forbidden-files.sh --staged
       audit-forbidden-files.sh --check PATH

Forbidden set (matched anywhere in the path string):
  **/00_authority/**
  *constitution_root_law.md*
  PROGRESS_TRACKER.md (pinned docs)

  --staged      exit 0 if nothing currently staged for commit matches the
                forbidden set; exit 1 (listing offenders) otherwise
  --check PATH  exit 0 if PATH does not match the forbidden set; exit 1 if
                it does (no filesystem access required — string match only)
  -h, --help    show this help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

fail() {
  echo "FAIL: $1"
  exit 1
}

matches_forbidden() {
  case "$1" in
    *00_authority*) return 0 ;;
    *constitution_root_law.md*) return 0 ;;
    *PROGRESS_TRACKER.md*) return 0 ;;
    *) return 1 ;;
  esac
}

MODE=""
CHECK_PATH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --staged)
      MODE="staged"
      shift
      ;;
    --check)
      [ $# -ge 2 ] || { usage >&2; exit 2; }
      MODE="check"
      CHECK_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

[ -n "$MODE" ] || { usage >&2; exit 2; }

if [ "$MODE" = "check" ]; then
  if matches_forbidden "$CHECK_PATH"; then
    fail "forbidden path: $CHECK_PATH"
  fi
  echo "PASS: not a forbidden path: $CHECK_PATH"
  exit 0
fi

# --staged
mapfile -t staged < <(git -C "$REPO_ROOT" diff --cached --name-only --diff-filter=ACMR)
bad=()
for f in "${staged[@]}"; do
  if matches_forbidden "$f"; then
    bad+=("$f")
  fi
done

if [ "${#bad[@]}" -gt 0 ]; then
  fail "forbidden staged path(s): ${bad[*]}"
fi
echo "PASS: no forbidden paths staged"
