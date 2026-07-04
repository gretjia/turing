#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: lineage_scrub.sh <submission_bundle_dir>" >&2
  exit 2
fi

bundle="$1"
if [[ ! -d "$bundle" ]]; then
  echo "LINEAGE_CONTAMINATION:bundle_missing:$bundle"
  exit 1
fi

status=0

scan() {
  local reason="$1"
  local pattern="$2"
  local hits
  hits="$(grep -RInE "$pattern" "$bundle" 2>/dev/null || true)"
  if [[ -n "$hits" ]]; then
    status=1
    while IFS= read -r line; do
      [[ -n "$line" ]] && echo "LINEAGE_CONTAMINATION:$reason:$line"
    done <<<"$hits"
  fi
}

# Heuristic only. The verifier prompt still instructs the auditor to treat any
# implementer-history narrative as contamination even if this grep misses it.
scan "implementer_narrative" '\bwe (did|ran|fixed)\b|\bas (i|we) (implemented|mentioned)\b'
scan "session_id" '\bsession [0-9a-f-]{8,}\b'
scan "subagent_reference" '\bsubagent\b|\bsub-agent\b'

if [[ "$status" -ne 0 ]]; then
  exit "$status"
fi

echo "LINEAGE_CLEAN"
