#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

rust_patterns=(
  ".append("
  ".stage("
  "AppendRequest"
  "re_mint_and_commit"
  "update-ref"
  "#[allow(clippy::disallowed_"
)

all_patterns=(
  "event.append_preserve"
  "approval.authorize_atom"
  "capsule.approve"
  "grant.authorize"
)

scan_file() {
  local file="$1"
  local failures=0
  local pattern

  if [[ "$file" == *.rs ]]; then
    for pattern in "${rust_patterns[@]}"; do
      if grep -nF -- "$pattern" "$file" >/tmp/hci_gate_match.$$ 2>/dev/null; then
        sed "s#^#$file:#" /tmp/hci_gate_match.$$
        failures=1
      fi
    done
  fi

  for pattern in "${all_patterns[@]}"; do
    if grep -nF -- "$pattern" "$file" >/tmp/hci_gate_match.$$ 2>/dev/null; then
      sed "s#^#$file:#" /tmp/hci_gate_match.$$
      failures=1
    fi
  done

  rm -f /tmp/hci_gate_match.$$
  return "$failures"
}

scan_paths() {
  local failures=0
  local path file
  for path in "$@"; do
    if [[ -f "$path" ]]; then
      scan_file "$path" || failures=1
    elif [[ -d "$path" ]]; then
      while IFS= read -r -d '' file; do
        scan_file "$file" || failures=1
      done < <(find "$path" -type f \( -name '*.rs' -o -name '*.py' -o -name '*.md' -o -name '*.json' -o -name '*.toml' \) -print0)
    fi
  done
  return "$failures"
}

operator_main_region() {
  awk '
    /^fn operator_help\(\)/ { in_region=1 }
    /^fn approval_preview\(/ { in_region=0 }
    in_region { print }
  ' "$ROOT/crates/turing-cli/src/main.rs"
}

check_operator_main_region() {
  local tmp
  tmp="$(mktemp)"
  operator_main_region > "$tmp"
  if scan_file "$tmp"; then
    rm -f "$tmp"
    return 0
  fi
  rm -f "$tmp"
  return 1
}

check_dependency_direction() {
  cargo metadata --format-version 1 --no-deps | python3 -c '
import json, sys
metadata = json.load(sys.stdin)
for package in metadata["packages"]:
    if package["name"] == "turing-projection":
        deps = {dep["name"] for dep in package["dependencies"]}
        if "turing-git-tape" in deps:
            print("turing-projection must not depend on turing-git-tape", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
print("turing-projection package not found", file=sys.stderr)
sys.exit(1)
'
}

self_test() {
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/clean" "$tmp/tampered"
  cat > "$tmp/clean/operator.rs" <<'RS'
fn render_only() {
    let writes_truth = false;
    println!("{writes_truth}");
}
RS
  cat > "$tmp/tampered/operator.rs" <<'RS'
fn forbidden(appender: turing_git_tape::append::Append) {
    appender.append(todo!()).unwrap();
}
RS
  scan_paths "$tmp/clean"
  if scan_paths "$tmp/tampered" >/dev/null 2>&1; then
    echo "tampered fixture unexpectedly passed" >&2
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "$tmp"
  echo "HCI_NO_WRITE_SELF_TEST_PASS"
}

main() {
  if [[ "${1:-}" == "--self-test" ]]; then
    self_test
    return
  fi
  if [[ "${1:-}" == "--help" ]]; then
    echo "usage: $0 [--self-test]"
    return
  fi
  if [[ "${1:-}" != "" ]]; then
    echo "unknown argument: $1" >&2
    return 2
  fi

  local failures=0
  scan_paths \
    "$ROOT/crates/turing-projection/src" \
    "$ROOT/src/turingos/operator_agent.py" \
    "$ROOT/docs/hci" \
    "$ROOT/schemas/operator" \
    "$ROOT/scripts/audit_operator_agent.py" \
    "$ROOT/scripts/audit_operator_cli_copy.py" \
    "$ROOT/scripts/lint_hci_copy.py" \
    "$ROOT/scripts/run_operator_simulated_human.py" || failures=1
  check_operator_main_region || failures=1
  check_dependency_direction || failures=3

  if [[ "$failures" -ne 0 ]]; then
    return "$failures"
  fi
  echo "HCI_NO_WRITE_GATE_PASS"
}

main "$@"
