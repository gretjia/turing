#!/usr/bin/env bash
set -euo pipefail
PACKET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKET_ROOT/../../.." && pwd)"
cd "$PACKET_ROOT"
sha256sum -c PACKET_MANIFEST.sha256 >/dev/null
python3 - "$REPO_ROOT" "$PACKET_ROOT" <<'CHECKPY'
import hashlib
import json
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
packet = pathlib.Path(sys.argv[2])

def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

source_map = json.loads((packet / 'SOURCE_MAP.json').read_text(encoding='utf-8'))
for entry in source_map:
    copied = repo / entry['github_path']
    assert copied.exists(), copied
    assert sha(copied) == entry['sha256'], copied

base = packet / 'plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702'
repo_artifacts = packet / 'repo_artifacts'
rollup = json.loads((base / 'evidence/session_20260702/M5G_ARTIFACT_ROLLUP.json').read_text(encoding='utf-8'))
verdict = json.loads((base / 'evidence/session_20260702/M5G_GATE_VERDICT.json').read_text(encoding='utf-8'))
handoff = json.loads((base / 'evidence/session_20260702/M5G_EXTERNAL_HANDOFF_PACKET.json').read_text(encoding='utf-8'))
m5p3 = json.loads((repo_artifacts / 'evidence/verification/m5_p3_first_external_audit_20260704_external_pass/M5_P3_GROK_PASS_CERTIFICATE.json').read_text(encoding='utf-8'))
m5p4 = json.loads((repo_artifacts / 'evidence/verification/m5_p4_module_closure_20260704_r2_external_pass/M5_P4_GROK_PASS_CERTIFICATE.json').read_text(encoding='utf-8'))

assert rollup['schema'] == 'turingos.m5_g_artifact_rollup.v1'
assert rollup['gate_id'] == 'M5.G'
assert rollup['status'] == 'ADDRESSED'
assert rollup['external_pass_artifact_present'] is True
assert rollup['processed_module_closures_cert_or_fail'] is True
assert verdict['schema'] == 'GateVerdict.v1'
assert verdict['gate_id'] == 'M5.G'
assert verdict['status'] == 'ADDRESSED'
assert 'M5.G is not externally verified' in verdict['non_claims']
assert handoff['lineage_excluded'] is True
assert m5p3['schema_id'] == 'turingos.closure_certificate.v1'
assert m5p3['verdict'] == 'PASS'
assert m5p3['subject']['gate_id'] == 'M5.P3'
assert all(m5p3['verifier']['custody'].values())
assert m5p4['schema_id'] == 'turingos.closure_certificate.v1'
assert m5p4['verdict'] == 'PASS'
assert m5p4['subject']['gate_id'] == 'M5.P4'
assert set(m5p4['subject']['module_targets']) == {'M3.G', 'M4.G'}
assert all(m5p4['verifier']['custody'].values())
print('M5_G_PACKET_CHECK_PASS')
CHECKPY
