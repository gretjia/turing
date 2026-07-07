# AUDITOR_RUNBOOK - M5.P3 First External Audit

You are auditing the first M5.P3 external exact-SHA packet. Use only:

1. A fresh clone of `https://github.com/gretjia/turing`.
2. The branch or commit supplied with the audit request.
3. The packet at `evidence/verification/m5_p3_first_external_audit_20260704`.
4. This runbook, `REEXECUTION.md`, `PACKET_MANIFEST.json`, and `MANIFEST.sha256`.
5. The M5 status vocabulary: `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `ADDRESSED`, `EXTERNALLY_VERIFIED`; implementer work is capped at `ADDRESSED`.

Do not use implementation chat, local plan directories, agent memory summaries, or uncommitted files.

This packet does not grant SHIPPED, RELEASED, RATIFIED, M2 enablement, or release eligibility. A PASS certificate for M5.P3 supports the G6 external-audit prerequisite only.

## Custody Requirements

Your certificate or FAIL artifact must truthfully record evidence for all six custody booleans:

| boolean | required evidence |
|---|---|
| `fresh_clone` | Record the `git clone` command, checkout command, and resulting `git rev-parse HEAD`. |
| `no_shared_conversation_state` | Start the audit session from this packet and the audit request only; this means no shared conversation state and no imported implementer summaries. |
| `no_implementer_transcript` | Confirm no implementation transcript or local agent memory was used. |
| `own_credentials` | Use your own credentials as the verifier/operator. Do not reveal secrets. |
| `cross_family_or_human` | M5.P3 is tier E1: use `external_human_operator` unless the owner explicitly records a stricter accepted channel. |
| `own_custody_output` | Store the certificate or FAIL artifact in verifier custody first and anchor its sha256 before any in-repo mirror lands. |

## Procedure

1. Clone and checkout the supplied commit.
2. Set `PACKET=evidence/verification/m5_p3_first_external_audit_20260704`.
3. Run the digest-depth commands in `REEXECUTION.md` and record literal exit codes.
4. Compute your verdict before opening `evidence/EXTERNAL_AUDITOR_PROMPT.md` or any historical EXPECTED_VERDICT text.
5. Inspect `CLAIM_BOUNDARY.json`, `evidence/CLAIM_BOUNDARY.json`, `official_harness_qualification.json`, and `official_harness_qualification_audit.json`.
6. Confirm full-score, leaderboard-equivalence, repo-local-evaluator-official, SHIPPED, RELEASED, RATIFIED, M2-enablement, and release-eligibility claims are absent or forbidden.
7. If any file in the packet or clone must be modified to continue, abort and emit a FAIL/finding artifact. Never patch the packet in place.
8. Emit either a `turingos.closure_certificate.v1` PASS/FAIL JSON or a machine-readable FAIL artifact.

## Required Answer Shape

Return JSON with:

- `schema_id: turingos.closure_certificate.v1`
- `subject.gate_id: M5.P3`
- `subject.repo_url: https://github.com/gretjia/turing`
- `subject.branch: goal/mini-swe-bench-grok-worker`
- `subject.packet_root: evidence/verification/m5_p3_first_external_audit_20260704`
- `subject.packet_sha256` from `PACKET_MANIFEST.json`
- `verifier.kind: external_human_operator` for tier E1, unless owner records a stronger accepted channel
- all six `verifier.custody` booleans set truthfully
- `verification.commands_run[]` with literal commands and exit codes
- `verification.digest_manifest_result: PASS|FAIL`
- `verification.gate_predicate_result: PASS|FAIL`
- `verdict: PASS|FAIL`
- `status_semantics.implementer_ceiling_was: ADDRESSED`
- `status_semantics.does_not_grant` including `SHIPPED`, `RELEASED`, `RATIFIED`, `M2 enablement`, `release eligibility`, `OG-10/genesis signature`, and `constitution-byte change`

If the verdict is FAIL, include machine-readable `reasons[]` and a repair route. Do not write `CLOSED`.
