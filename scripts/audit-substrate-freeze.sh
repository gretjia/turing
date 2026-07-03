#!/usr/bin/env bash
# HW-SW-003 C1 — substrate freeze audit.
#
# Recomputes sha256 for every file pinned in substrate_freeze_manifest.toml
# (the constitution plus the substrate-critical source files this repo's
# other audits bind to) and fails closed on any mismatch. The constitution
# digest is additionally compared against the value pinned directly in this
# script (mirroring evidence/loops/hw_sw_001_20260703/PREDICATE.md), so a
# tampered manifest alone cannot move the constitution pin.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: audit-substrate-freeze.sh [--manifest PATH]

Verifies every sha256 pinned in substrate_freeze_manifest.toml against the
real file contents:
  - [constitution]: $TURINGOS_WORK_ROOT-relative path; its sha256 must also
    equal the pinned constitutional value.
  - [[files]]: repo-relative paths (crates/... source anchors).

  --manifest PATH   use PATH instead of substrate_freeze_manifest.toml at
                     the repo root (for tests)
  -h, --help        show this help

Manifest changes require a commit message containing `REPIN:` + rationale
(documented in the manifest's own header comment).
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_ROOT="${TURINGOS_WORK_ROOT:-/home/zephryj/turingos_backup/work}"
MANIFEST="$REPO_ROOT/substrate_freeze_manifest.toml"
PINNED_CONSTITUTION_SHA256="a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0"

while [ $# -gt 0 ]; do
  case "$1" in
    --manifest)
      [ $# -ge 2 ] || { usage >&2; exit 2; }
      MANIFEST="$2"
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

fail() {
  echo "FAIL: $1"
  exit 1
}

[ -f "$MANIFEST" ] || fail "manifest not found at $MANIFEST"

extract_kv() {
  # $1 = section anchor regex (e.g. '^\[constitution\]' or '^\[\[files\]\]'),
  # $2 = key name. Prints every value found in that section type, in file order.
  awk -v anchor="$1" -v key="$2" '
    $0 ~ anchor { f = 1; next }
    /^\[/ && $0 !~ anchor { f = 0 }
    f && $0 ~ ("^" key "[[:space:]]*=") {
      line = $0
      sub(/^[a-zA-Z0-9_]+[[:space:]]*=[[:space:]]*"/, "", line)
      sub(/".*$/, "", line)
      print line
    }
  ' "$MANIFEST"
}

# ---- constitution -----------------------------------------------------
constitution_path="$(extract_kv '^\[constitution\]' 'path' | head -n1)"
constitution_sha="$(extract_kv '^\[constitution\]' 'sha256' | head -n1)"

[ -n "$constitution_path" ] || fail "manifest missing [constitution].path"
[ -n "$constitution_sha" ] || fail "manifest missing [constitution].sha256"
[ "$constitution_sha" = "$PINNED_CONSTITUTION_SHA256" ] \
  || fail "manifest constitution sha256 ($constitution_sha) does not match the pinned value ($PINNED_CONSTITUTION_SHA256)"

constitution_full_path="$WORK_ROOT/$constitution_path"
[ -f "$constitution_full_path" ] || fail "constitution file not found at $constitution_full_path"
actual_sha="$(sha256sum "$constitution_full_path" | awk '{print $1}')"
[ "$actual_sha" = "$constitution_sha" ] \
  || fail "constitution sha256 mismatch: manifest=$constitution_sha actual=$actual_sha"
echo "PASS: constitution sha256 pinned and verified ($constitution_sha)"

# ---- pinned source files -----------------------------------------------
mapfile -t FILE_PATHS < <(extract_kv '^\[\[files\]\]' 'path')
mapfile -t FILE_SHAS < <(extract_kv '^\[\[files\]\]' 'sha256')

[ "${#FILE_PATHS[@]}" -gt 0 ] || fail "manifest has no [[files]] entries"
[ "${#FILE_PATHS[@]}" -eq "${#FILE_SHAS[@]}" ] \
  || fail "manifest [[files]] path/sha256 count mismatch (${#FILE_PATHS[@]} paths, ${#FILE_SHAS[@]} sha256s)"

for i in "${!FILE_PATHS[@]}"; do
  p="${FILE_PATHS[$i]}"
  s="${FILE_SHAS[$i]}"
  full="$REPO_ROOT/$p"
  [ -f "$full" ] || fail "pinned file not found: $full"
  actual="$(sha256sum "$full" | awk '{print $1}')"
  [ "$actual" = "$s" ] || fail "sha256 mismatch for $p: manifest=$s actual=$actual"
  echo "PASS: $p sha256 verified ($s)"
done

echo "PASS: audit-substrate-freeze complete (${#FILE_PATHS[@]} pinned files + constitution)"
