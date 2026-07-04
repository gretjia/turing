#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: make_negative_controls.sh <out_dir>" >&2
  exit 2
fi

out="$1"
rm -rf "$out"
mkdir -p "$out/base_fixture_packet/evidence" "$out/base_fixture_packet/tapes" "$out/base_fixture_packet/tools"

repo_sha="9eea210772c526ef50fde339518832aa92aa9f87"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runbook_path="$script_dir/../AUDITOR_RUNBOOK.md"
auditor_path="$script_dir/audit_packet_fixture.py"

write_base_files() {
  local pkt="$1"
  mkdir -p "$pkt/evidence" "$pkt/tapes" "$pkt/tools"
  cat > "$pkt/PACKET_MANIFEST.json" <<JSON
{
  "schema_id": "turingos.release_packet.v1",
  "evidence_class": "FIXTURE",
  "fixture_purpose": "M5.P2 negative-control calibration base packet",
  "gate_id": "M5.P2.FIXTURE",
  "packet_sha256": "sha256:fixture",
  "repo_sha": "$repo_sha",
  "required_artifacts": [
    "PACKET_MANIFEST.json",
    "AUDITOR_RUNBOOK.md",
    "repo_head.txt",
    "REEXECUTION.md",
    "CLAIM_BOUNDARY.json",
    "tools/audit_packet_fixture.py",
    "evidence/receipt_0.json",
    "evidence/gate_verdict.json",
    "evidence/command_transcript.json",
    "evidence/fixture_label.json",
    "tapes/t0.bundle"
  ],
  "implementer_manifest": [
    {
      "operator_label": "codex-orchestrator",
      "model_family": "gpt-5",
      "role": "fixture-builder"
    }
  ]
}
JSON
  printf '%s\n' "$repo_sha" > "$pkt/repo_head.txt"
  cp "$runbook_path" "$pkt/AUDITOR_RUNBOOK.md"
  cp "$auditor_path" "$pkt/tools/audit_packet_fixture.py"
  cat > "$pkt/REEXECUTION.md" <<'MD'
# FIXTURE Reexecution

From the packet root, run `python3 tools/audit_packet_fixture.py .`.
Expected fixture result: PASS for the base packet.
MD
  cat > "$pkt/CLAIM_BOUNDARY.json" <<'JSON'
{
  "schema_id": "CLAIM_BOUNDARY.fixture.v1",
  "evidence_class": "FIXTURE",
  "allowed_claims": ["M5.P2 fixture calibration packet"],
  "forbidden_claims": ["external audit", "release eligibility", "real closure certificate"]
}
JSON
  cat > "$pkt/evidence/receipt_0.json" <<'JSON'
{
  "schema_id": "fixture.receipt.v1",
  "evidence_class": "FIXTURE",
  "receipt_id": "receipt-0"
}
JSON
  cat > "$pkt/evidence/gate_verdict.json" <<'JSON'
{
  "schema_id": "fixture.gate_verdict.v1",
  "evidence_class": "FIXTURE",
  "verdict": "PASS"
}
JSON
  cat > "$pkt/evidence/command_transcript.json" <<'JSON'
{
  "schema_id": "fixture.command_transcript.v1",
  "evidence_class": "FIXTURE",
  "cmd": "fixture gate",
  "exit_code": 0
}
JSON
  cat > "$pkt/evidence/fixture_label.json" <<'JSON'
{
  "schema_id": "fixture.label.v1",
  "evidence_class": "FIXTURE",
  "fixture_probe": true
}
JSON
  printf 'fixture tape bundle\n' > "$pkt/tapes/t0.bundle"
}

write_manifest() {
  local pkt="$1"
  (cd "$pkt" && find . -type f ! -name MANIFEST.sha256 -printf '%P\n' | sort | xargs sha256sum) > "$pkt/MANIFEST.sha256"
}

mutate_json() {
  local path="$1"
  local expression="$2"
  python3 - "$path" "$expression" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expr = sys.argv[2]
data = json.loads(path.read_text())
exec(expr, {"data": data})
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
}

base="$out/base_fixture_packet"
write_base_files "$base"
write_manifest "$base"

cp -R "$base" "$out/NC-1"
printf 'tamper\n' >> "$out/NC-1/tapes/t0.bundle"

cp -R "$base" "$out/NC-2"
mutate_json "$out/NC-2/evidence/command_transcript.json" 'data["exit_code"] = 1'
write_manifest "$out/NC-2"

cp -R "$base" "$out/NC-3"
mutate_json "$out/NC-3/evidence/fixture_label.json" 'data["evidence_class"] = "REAL"'
write_manifest "$out/NC-3"

cp -R "$base" "$out/NC-4"
rm "$out/NC-4/evidence/receipt_0.json"

cp -R "$base" "$out/NC-5"
mutate_json "$out/NC-5/PACKET_MANIFEST.json" 'data["repo_sha"] = "0000000000000000000000000000000000000000"'
write_manifest "$out/NC-5"

cat > "$out/CLAIM_BOUNDARY.json" <<'JSON'
{
  "schema_id": "CLAIM_BOUNDARY.fixture.v1",
  "evidence_class": "FIXTURE",
  "allowed_claims": ["M5.P2 negative-control calibration corpus"],
  "forbidden_claims": ["external audit", "release eligibility", "real closure certificate"],
  "negative_controls": ["NC-1", "NC-2", "NC-3", "NC-4", "NC-5"]
}
JSON

(cd "$out" && find . -type f ! -name corpus_pins.sha256 -printf '%P\n' | sort | xargs sha256sum) > "$out/corpus_pins.sha256"
sort -o "$out/corpus_pins.sha256" "$out/corpus_pins.sha256"

echo "$out"
