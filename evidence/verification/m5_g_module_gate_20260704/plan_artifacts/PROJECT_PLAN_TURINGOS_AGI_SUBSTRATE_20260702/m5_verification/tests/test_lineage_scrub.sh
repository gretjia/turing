#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LINT="$ROOT/m5_verification/tools/lineage_scrub.sh"
FIXTURE="$ROOT/m5_verification/corpus/lineage_scrub_seeded_bundle"

set +e
out="$("$LINT" "$FIXTURE" 2>&1)"
status=$?
set -e

[[ "$status" -ne 0 ]]
[[ "$out" == *"LINEAGE_CONTAMINATION:implementer_narrative"* ]]
[[ "$out" == *"LINEAGE_CONTAMINATION:session_id"* ]]
[[ "$out" == *"LINEAGE_CONTAMINATION:subagent_reference"* ]]

echo "PASS lineage scrub seeded bundle"
