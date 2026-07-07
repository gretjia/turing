#!/usr/bin/env bash
# WP6 — F4 泄漏门 (leakage gate)
#
# Source of truth: research/RES_ECON_emergence_toplevel_design_20260707.md §4 (F4 row) / §7
# (WP6 row); ADR-ECON-003 Decision 5 ("Art III.4 的保密通过投影过滤实现"). This gate is
# mechanical (identifier-name grep) and machine-judged; it does not evaluate semantics.
#
# Scan granularity (ADR-ECON-003 Decision 5, granularity amendment 2026-07-07): for .rs
# surface files the leak surface is what can REACH an agent -- string literals (error/
# format/serde-rename text) and struct-field declaration lines (serde serialization
# names) -- comments and code identifiers (type/fn/variant names) are kernel-internal
# and are NOT agent-visible. JSON manifests remain whole-file scans.
#
# It scans the fixed set of agent-visible economy leak surfaces named in the design doc:
#   - daemons failed_predicates return channel
#   - error-message construction sites (Display impls / jsonrpc_error / format! sites)
#   - BudgetSuggestion field carriers (struct + its RPC/event serialization call sites)
#   - tool schema (capability::ToolRequest / CapabilityScope + JSON tool manifests)
#   - tape-read / projection surface (ADR-ECON-003 Decision 5 explicit requirement)
#
# ...for the four forbidden identifier families named in ADR-ECON-003 (Decisions 1/3/4):
#   tau family        : tau, tau_hi, tau_lo, n_anneal, unicode τ
#   lambda family      : lambda, unicode λ
#   floor family        : n_eff_floor, h_lineage_floor
#   bucket-key family   : domain_bucket, scaffold_id, bucket_key
#
# No formula/threshold/key-function name here is invented: every pattern is copied verbatim
# from ADR-ECON-003. If a real F4 surface needs a new identifier added to this list, that is
# an ADR change, not a gate-script judgment call.
#
# This gate is read-only: it never edits crates/turing-economy/src/lib.rs (or anything else
# under scan) -- scanning is not writing.
#
# Fail-closed guarantee: an unscannable surface must never yield PASS. A listed
# SURFACE_FILES entry that is missing, a file the extractor cannot read/decode, or a
# grep error all produce F4_LEAK_NOT_RUN (exit 3) with a message naming the file.
#
# Known extraction limit: when one physical line declares multiple fields and an
# EARLIER field's type is a fn-pointer (e.g. `pub a: fn(u64) -> u64, pub b: u64`),
# the `fn` keyword in the scanned prefix is indistinguishable from a fn-signature
# parameter list, so later fields on that same line are suppressed. Fields on their
# own lines (the normal rustfmt shape) and fn-pointer-typed fields themselves are
# handled correctly.
#
# Usage:
#   gate_f4_econ_leakage.sh              scan the real surfaces under repo root, exit 0/1/3
#   gate_f4_econ_leakage.sh --self-test  bidirectional self-test (clean PASS / seeded FAIL)
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Fixed leak-surface file list (relative to scan root). Any new agent-visible economy
# surface must be added here explicitly by an ADR update -- silent scope drift is itself
# an F4 hole this gate would then fail to cover.
SURFACE_FILES=(
  "crates/turing-daemons/src/lib.rs"       # failed_predicates channel + RPC error text + BudgetSuggestion field carrier
  "crates/turing-predicate/src/lib.rs"     # failed_predicates construction + PredicateError Display
  "crates/turing-qualification/src/lib.rs" # BudgetSuggestion field carrier (second call site)
  "crates/turing-economy/src/lib.rs"       # BudgetSuggestion struct + EconomyError Display (read-only scan)
  "crates/turing-execd/src/lib.rs"         # tool schema (ToolRequest/CapabilityScope) + GrantError Display
  "crates/turing-projection/src/lib.rs"    # tape-read / projection surface (ADR-ECON-003 Decision 5)
)

SURFACE_GLOB_DIRS=(
  "schemas/operator" # tool-schema JSON manifests
)

# Forbidden identifier patterns (POSIX extended regex, case-insensitive), sourced verbatim
# from ADR-ECON-003 Decisions 1 (scaffold_id/domain_bucket), 3 (N_eff_floor/H_lineage_floor)
# and 4 (tau_hi/tau_lo/N_anneal/τ). "lambda"/λ covered per Art III.4/F4 blanket clause.
PATTERNS=(
  'tau_hi'
  'tau_lo'
  'n_anneal'
  '\<tau\>'
  'τ'
  '\<lambda\>'
  'λ'
  'n_eff_floor'
  'h_lineage_floor'
  'domain_bucket'
  'scaffold_id'
  'bucket_key'
)

build_pattern() {
  local IFS='|'
  echo "${PATTERNS[*]}"
}

collect_targets() {
  local root="$1"
  local rel f
  for rel in "${SURFACE_FILES[@]}"; do
    [[ -f "$root/$rel" ]] && printf '%s\n' "$root/$rel"
  done
  for rel in "${SURFACE_GLOB_DIRS[@]}"; do
    for f in "$root/$rel"/*.json; do
      [[ -f "$f" ]] && printf '%s\n' "$f"
    done
  done
}

# Extract the agent-reachable text of a Rust source file: string-literal contents and
# struct-field declaration lines, with // and /* */ comments stripped. Deterministic
# character-state-machine; emits "LINENO:text" for grep.
extract_rs_surface() {
  python3 - "$1" <<'PY'
import re, sys
try:
    src = open(sys.argv[1], encoding='utf-8').read()
except OSError as e:
    print(f"extract_rs_surface: cannot read {sys.argv[1]}: {e}", file=sys.stderr)
    sys.exit(4)
except UnicodeDecodeError as e:
    print(f"extract_rs_surface: {sys.argv[1]} is not valid UTF-8: {e}", file=sys.stderr)
    sys.exit(4)
out = {}
def emit(line, text):
    if text.strip():
        out.setdefault(line, []).append(text)
i, line, n = 0, 1, len(src)
state = 'code'          # code | str | rawstr | line_comment | block_comment
code_line = []          # comment-stripped code text of the current line
cur = []                # current string literal
raw_hashes = 0
while i < n:
    c = src[i]
    if c == '\n':
        if state in ('str', 'rawstr'):
            # A newline inside a string literal is literal-content: keep it so a
            # multi-line "ta\nu_hi" is never glued into the single token tau_hi.
            cur.append('\n')
            line += 1
            i += 1
            continue
        if state == 'line_comment':
            state = 'code'
        stripped = ''.join(code_line)
        # Field declarations: at line start or after '{'/',' so single-line structs
        # (`pub struct X { pub tau_hi: u64 }`) emit their field names too. Exclusion
        # keywords are checked only in the text BEFORE the candidate field, so a
        # fn-pointer-typed field (`pub tau: fn(u64) -> u64`) is still emitted while
        # fn-signature parameter lists / let bindings / patterns are not.
        for m in re.finditer(r'(?:^|[{,])(\s*(?:pub(?:\([^)]*\))?\s+)?'
                             r'[A-Za-z_][A-Za-z0-9_]*\s*:\s[^,{}]*)', stripped):
            if re.search(r'\b(fn|let|const|static|impl|use|mod)\b', stripped[:m.start(1)]):
                continue
            emit(line, m.group(1))
        code_line = []
        line += 1
        i += 1
        continue
    if state == 'code':
        if c == '/' and i + 1 < n and src[i+1] == '/':
            state = 'line_comment'; i += 2; continue
        if c == '/' and i + 1 < n and src[i+1] == '*':
            state = 'block_comment'; i += 2; continue
        if c == 'r' and i + 1 < n and src[i+1] in '#"':
            j = i + 1; h = 0
            while j < n and src[j] == '#':
                h += 1; j += 1
            if j < n and src[j] == '"':
                state = 'rawstr'; raw_hashes = h; cur = []; i = j + 1; continue
        if c == '"':
            state = 'str'; cur = []; i += 1; continue
        if c == "'" and i + 2 < n and src[i+1] == '\\':
            i += 2  # char escape like '\n'
            while i < n and src[i] != "'":
                i += 1
            i += 1; continue
        if c == "'" and i + 2 < n and src[i+2] == "'":
            i += 3; continue  # plain char literal
        code_line.append(c); i += 1; continue
    if state == 'str':
        if c == '\\':
            cur.append(src[i:i+2]); i += 2; continue
        if c == '"':
            emit(line, ''.join(cur)); state = 'code'; i += 1; continue
        cur.append(c); i += 1; continue
    if state == 'rawstr':
        if c == '"':
            j = i + 1; h = 0
            while j < n and h < raw_hashes and src[j] == '#':
                h += 1; j += 1
            if h == raw_hashes:
                emit(line, ''.join(cur)); state = 'code'; i = j; continue
        cur.append(c); i += 1; continue
    if state == 'block_comment':
        if c == '*' and i + 1 < n and src[i+1] == '/':
            state = 'code'; i += 2; continue
        i += 1; continue
    i += 1
for ln in sorted(out):
    for t in out[ln]:
        print(f"{ln}:{t}")
PY
}

gate_scan() {
  local root="$1"
  local pattern
  pattern="$(build_pattern)"

  # Fail closed on scope drift: every explicitly listed surface file must exist. A
  # renamed/moved surface file must surface as NOT_RUN, never as a silently smaller
  # scan scope (only the glob dirs may legitimately be empty).
  local rel
  for rel in "${SURFACE_FILES[@]}"; do
    if [[ ! -f "$root/$rel" ]]; then
      echo "F4_LEAK_NOT_RUN missing surface file: $root/$rel (listed in SURFACE_FILES; refusing to scan a silently reduced scope)" >&2
      return 3
    fi
  done

  mapfile -t targets < <(collect_targets "$root")
  if [[ "${#targets[@]}" -eq 0 ]]; then
    echo "F4_LEAK_NOT_RUN no surface files found under $root" >&2
    return 3
  fi

  local hits extracted t rc
  hits="$(mktemp)"
  extracted="$(mktemp)"
  for t in "${targets[@]}"; do
    case "$t" in
      *.rs)
        # Fail closed: an extractor failure means the file was NOT scanned; it must
        # never contribute "zero hits" to a PASS.
        rc=0
        extract_rs_surface "$t" >"$extracted" || rc=$?
        if [[ "$rc" -ne 0 ]]; then
          rm -f "$hits" "$extracted"
          echo "F4_LEAK_NOT_RUN surface extractor failed (exit $rc) on $t; file was not scanned" >&2
          return 3
        fi
        rc=0
        grep -iE "$pattern" "$extracted" >"$extracted.hits" || rc=$?
        if [[ "$rc" -ge 2 ]]; then
          rm -f "$hits" "$extracted" "$extracted.hits"
          echo "F4_LEAK_NOT_RUN grep failed (exit $rc) on extracted surface of $t; file was not scanned" >&2
          return 3
        fi
        sed "s|^|$t:|" "$extracted.hits" >>"$hits"
        rm -f "$extracted.hits"
        ;;
      *)
        rc=0
        grep -HinE "$pattern" "$t" >>"$hits" || rc=$?
        if [[ "$rc" -ge 2 ]]; then
          rm -f "$hits" "$extracted"
          echo "F4_LEAK_NOT_RUN unreadable surface file (grep exit $rc): $t; file was not scanned" >&2
          return 3
        fi
        ;;
    esac
  done

  if [[ -s "$hits" ]]; then
    while IFS= read -r hit; do
      echo "F4_LEAK_FAIL $hit"
    done <"$hits"
    rm -f "$hits" "$extracted"
    return 1
  fi
  rm -f "$hits" "$extracted"
  echo "F4_LEAK_PASS (${#targets[@]} surface files scanned, $(( ${#PATTERNS[@]} )) patterns)"
}

self_test() {
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN

  mkdir -p \
    "$work/crates/turing-daemons/src" \
    "$work/crates/turing-predicate/src" \
    "$work/crates/turing-qualification/src" \
    "$work/crates/turing-economy/src" \
    "$work/crates/turing-execd/src" \
    "$work/crates/turing-projection/src" \
    "$work/schemas/operator"

  cat >"$work/crates/turing-daemons/src/lib.rs" <<'EOF'
pub fn jsonrpc_error(id: i64, code: i32, message: String) -> String {
    format!("{{\"id\":{id},\"error\":{{\"code\":{code},\"message\":\"{message}\"}}}}")
}
pub fn budget_response(route_id: &str, max_tokens: u64) -> String {
    format!("{{\"route_id\":\"{route_id}\",\"max_tokens\":{max_tokens}}}")
}
pub fn failed_predicates_channel(ids: &[String]) -> String {
    format!("{{\"failed_predicates\":{ids:?}}}")
}
EOF
  cp "$work/crates/turing-daemons/src/lib.rs" "$work/crates/turing-predicate/src/lib.rs"
  cp "$work/crates/turing-daemons/src/lib.rs" "$work/crates/turing-qualification/src/lib.rs"
  cp "$work/crates/turing-daemons/src/lib.rs" "$work/crates/turing-economy/src/lib.rs"
  cp "$work/crates/turing-daemons/src/lib.rs" "$work/crates/turing-execd/src/lib.rs"
  cp "$work/crates/turing-daemons/src/lib.rs" "$work/crates/turing-projection/src/lib.rs"
  printf '%s\n' '{"schema_id":"tool_manifest.v1","commands":[]}' \
    >"$work/schemas/operator/tool_manifest.v1.schema.json"

  if ! gate_scan "$work" >/dev/null; then
    echo "F4_LEAK_SELF_TEST_FAIL clean fixture tree was rejected" >&2
    return 1
  fi

  # Granularity check: a comment / code-identifier mention in a .rs surface is kernel-
  # internal, NOT a leak (ADR Decision 5 granularity amendment) -- must still PASS.
  printf '%s\n' \
    '// internal note: anneal schedule tau_hi/tau_lo and n_eff_floor live in B-zone' \
    'pub struct TauQ32Internal(u64);' \
    >>"$work/crates/turing-economy/src/lib.rs"
  if ! gate_scan "$work" >/dev/null; then
    echo "F4_LEAK_SELF_TEST_FAIL comment/identifier mention was wrongly flagged" >&2
    return 1
  fi

  # Fix-3 direction: a string literal spanning physical lines must not be glued into
  # a single forbidden token ("ta\nu_hi" is NOT tau_hi) -- must still PASS.
  printf '%s\n' 'pub const SPLIT: &str = "ta' 'u_hi";' \
    >>"$work/crates/turing-economy/src/lib.rs"
  if ! gate_scan "$work" >/dev/null; then
    echo "F4_LEAK_SELF_TEST_FAIL multi-line string literal was glued into a forbidden token" >&2
    return 1
  fi

  local rc
  # Fix-4 direction: a single-line struct declaration leaking a forbidden field name
  # must FAIL (exit 1).
  cp "$work/crates/turing-execd/src/lib.rs" "$work/execd_lib_backup.rs"
  printf '%s\n' 'pub struct SingleLineCarrier { pub tau_hi: u64 }' \
    >>"$work/crates/turing-execd/src/lib.rs"
  rc=0
  gate_scan "$work" >/dev/null || rc=$?
  if [[ "$rc" -ne 1 ]]; then
    echo "F4_LEAK_SELF_TEST_FAIL single-line struct field leak yielded exit $rc, want FAIL(1)" >&2
    return 1
  fi
  mv "$work/execd_lib_backup.rs" "$work/crates/turing-execd/src/lib.rs"

  # Fix-2 direction: a listed surface file that is missing (renamed away) must be
  # NOT_RUN (exit 3), never PASS.
  mv "$work/crates/turing-projection/src/lib.rs" "$work/crates/turing-projection/src/lib.rs.moved"
  rc=0
  gate_scan "$work" >/dev/null 2>&1 || rc=$?
  if [[ "$rc" -ne 3 ]]; then
    echo "F4_LEAK_SELF_TEST_FAIL missing surface file yielded exit $rc, want NOT_RUN(3)" >&2
    return 1
  fi
  mv "$work/crates/turing-projection/src/lib.rs.moved" "$work/crates/turing-projection/src/lib.rs"

  # Fix-1 direction: an unscannable .rs surface (extractor failure on non-UTF-8
  # bytes) must be NOT_RUN (exit 3), never PASS.
  cp "$work/crates/turing-projection/src/lib.rs" "$work/projection_lib_backup.rs"
  printf '\xff\xfe not utf-8\n' >>"$work/crates/turing-projection/src/lib.rs"
  rc=0
  gate_scan "$work" >/dev/null 2>&1 || rc=$?
  if [[ "$rc" -ne 3 ]]; then
    echo "F4_LEAK_SELF_TEST_FAIL non-UTF-8 surface yielded exit $rc, want NOT_RUN(3)" >&2
    return 1
  fi
  mv "$work/projection_lib_backup.rs" "$work/crates/turing-projection/src/lib.rs"

  # Seed exactly one leak: an error-message construction site starts naming the anneal
  # floor identifier and the temperature identifier together, as a real regression would.
  printf '%s\n' \
    'pub const LEAK: &str = "n_eff_floor breach observed, reanneal to tau_hi";' \
    >>"$work/crates/turing-daemons/src/lib.rs"

  if gate_scan "$work" >/dev/null; then
    echo "F4_LEAK_SELF_TEST_FAIL seeded leak fixture was not detected" >&2
    return 1
  fi

  echo "F4_LEAK_SELF_TEST_PASS"
}

case "${1:-}" in
  --self-test)
    self_test
    ;;
  "" )
    gate_scan "${F4_LEAK_SCAN_ROOT:-$REPO_ROOT}"
    ;;
  * )
    echo "usage: $0 [--self-test]" >&2
    exit 2
    ;;
esac
