# REEXECUTION - FCE.RUN Certification Packet (r11)

Gate: `FCE.RUN`, the Final Certification Evals (FCE) run — the last gate of the
TuringOS AGI-Substrate Convergence program increment (`09_FINAL_CERTIFICATION_EVALS.md`).

This packet documents FCE aggregate run `r11`: 19/19 scenario `PASS`, all
goals G1-G7 `PASS`, `overall: CERTIFICATION_ADDRESSED`, `cert_repo_sha
7e0a0bd0a03be088b2dd7833aae92e210d251188` on branch `fce/integration-20260704`
of `https://github.com/gretjia/turing`.

The evidence root that produced this packet lives outside version control
(`PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/fce_run_probe_20260704_r11`,
a plain directory tree, not a git repository). Only the audited repository
commit (`cert_repo_sha` above) is version-controlled; the packet itself must
be delivered to the auditor out-of-band alongside the exact-SHA checkout
instructions.

## Required Digest-Depth Path

Run these commands against a fresh clone of the repository at the exact
commit supplied with the audit request, plus this packet delivered
out-of-band:

```bash
set -euo pipefail
REPO=/tmp/turing-fce-run-audit
PACKET=/path/to/delivered/FCE_CERTIFICATION_PACKET_20260705   # supplied out-of-band

# 1. Digest closure of the packet itself.
cd "$PACKET"
sha256sum -c MANIFEST.sha256

# 2. Packet-schema self-validation.
cd "$REPO"
python3 tools/release/build_packet.py --validate "$PACKET"

# 3. Confirm the audited commit.
git rev-parse HEAD   # must equal repo_sha in PACKET_MANIFEST.json and repo_head.txt
```

Expected exit codes:

- `sha256sum -c MANIFEST.sha256`: 0
- `python3 tools/release/build_packet.py --validate "$PACKET"`: 0 (`verdict: PASS`)
- `git rev-parse HEAD`: prints `7e0a0bd0a03be088b2dd7833aae92e210d251188`

## Required Verdict-Content Checks

Independently, from the packet's `evidence/FINAL_CERTIFICATION_VERDICT.json`:

- `schema_id` is `turingos.final_certification_verdict.v1`
- `cert_repo_sha` equals `7e0a0bd0a03be088b2dd7833aae92e210d251188`
- `overall` equals `CERTIFICATION_ADDRESSED` (never `CERTIFICATION_PASSED`/`SHIPPED` — those values do not exist in the schema)
- `shipped_eligible` is `false`
- `shipped_blockers` includes `external_audit_pass_on_certification_packet_missing`
- `external_audit.closure_certificate_path` is `null` (no certificate has been issued for this packet yet)
- every entry in `automatic_fail_conditions` is `false`
- all 19 scenarios (`FCE-R1..R5`, `FCE-S1..S6`, `FCE-W1..W3`, `FCE-B1..B5`) report `verdict: PASS`
- `goal_rollup.G1` through `goal_rollup.G7` each report `verdict: PASS` and `threshold_predicate_held: true`

Then, for each of the 19 `evidence/FCE-*/FCE-*_verdict.json` files in the
packet: confirm `verdict: PASS`, `not_run_is_fail: true`, and that
`evidence_sha256` entries are internally consistent (path + digest pairs);
the full underlying scenario evidence trees are not embedded in this packet
and remain in the evidence root cited above for a deeper audit if requested.

Compute your verdict before opening any historical README or session-log
prose describing this run. After you compute the verdict, you may compare it
against that historical text and record any divergence.

## What this packet does not authorize

Do not treat a PASS on this packet's digest closure as a certification of the
program itself. Only a custody-separated, tier-E1 (external human operator)
`ClosureCertificate.v1` PASS on this exact packet closes the FCE.RUN
external-audit prerequisite. Until that certificate exists, `FCE.RUN` remains
`CERTIFICATION_ADDRESSED` and the program remains `shipped_eligible: false`.
