# REEXECUTION - M5.P3 First External Audit

Gate: M5.P3, first genuinely external exact-SHA audit of the upstream SWE-bench Docker harness qualification packet.

Packet path in GitHub checkout:

`evidence/verification/m5_p3_first_external_audit_20260704`

Source evidence copied into this packet:

`evidence/bench/swe_bench_official_harness_qualification_20260629`

## Required Digest-Depth Path

Run these commands from a fresh clone at the commit supplied with the audit request:

```bash
set -euo pipefail
REPO=/tmp/turing-m5p3-audit
PACKET="$REPO/evidence/verification/m5_p3_first_external_audit_20260704"
cd "$PACKET"
sha256sum -c MANIFEST.sha256
cd "$REPO"
bash tools/release/build_packet.sh --validate "$PACKET"
python3 tools/bench/audit_official_harness_qualification.py \
  --root "$PACKET/evidence" \
  --out /tmp/m5p3_official_harness_qualification_audit.json
```

Expected exit codes:

- `sha256sum -c MANIFEST.sha256`: 0
- `bash tools/release/build_packet.sh --validate "$PACKET"`: 0
- `python3 tools/bench/audit_official_harness_qualification.py ...`: 0

The Python audit output must report `status: PASS`, `official_harness_kind: upstream_swebench_docker`, `phase_f_submitted_count: 20`, `phase_f_completed_count: 20`, `phase_f_resolved_count: 20`, `phase_f_error_count: 0`, and `release_next_phase_g: true`.

Compute your verdict before opening `evidence/EXTERNAL_AUDITOR_PROMPT.md` or any historical EXPECTED_VERDICT text. After you compute the verdict, you may compare it against the historical prompt and record any divergence.

## Optional full 20-task replay path

This path requires Docker and an upstream SWE-bench installation and can take 1-3 hours. Do not run it in the packet directory. Copy packet evidence to scratch space first:

```bash
set -euo pipefail
REPO=/tmp/turing-m5p3-audit
PACKET="$REPO/evidence/verification/m5_p3_first_external_audit_20260704"
SCRATCH=/tmp/turing-m5p3-full-replay
rm -rf "$SCRATCH"
mkdir -p "$SCRATCH"
cp -a "$PACKET/evidence/." "$SCRATCH/"
cd "$SCRATCH"
python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Verified \
  --split test \
  --predictions_path predictions_phase_f_20_repaired.jsonl \
  --max_workers 2 \
  --timeout 1800 \
  --run_id turingos_m5p3_external_full_replay \
  --report_dir phase_f_20_repaired_run
```

Expected full replay result:

- submitted: 20
- completed: 20
- errors: 0
- resolved: 20
- unresolved: 0

If Docker or SWE-bench setup is unavailable, report the full replay path as NOT_RUN and base the digest-depth verdict only on the required path above.
