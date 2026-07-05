# AUDITOR_RUNBOOK - FCE.RUN Certification Packet (r11)

You are auditing the exact-SHA `FCE.RUN` certification-run packet: the last
gate of the TuringOS AGI-Substrate Convergence program increment. Use only:

1. A fresh clone of `https://github.com/gretjia/turing`.
2. The branch `fce/integration-20260704` (or the exact commit supplied with
   the audit request) — audited commit
   `7e0a0bd0a03be088b2dd7833aae92e210d251188`.
3. This packet, delivered out-of-band (it documents an evidence root that is
   not itself version-controlled).
4. This runbook, `REEXECUTION.md`, `PACKET_MANIFEST.json`, and
   `MANIFEST.sha256`.
5. The M5 status vocabulary: `PLANNED`, `IN_PROGRESS`, `BLOCKED`,
   `ADDRESSED`, `EXTERNALLY_VERIFIED`; implementer work is capped at
   `ADDRESSED`. The FCE schema's own `overall_enum` is restricted to
   `CERTIFICATION_ADDRESSED` and `CERTIFICATION_FAILED` — there is no
   `CERTIFICATION_PASSED`/`SHIPPED` value to self-elevate to.

Do not use implementation chat, local plan directories, agent memory
summaries, or uncommitted files.

This packet does not grant `SHIPPED`, `RELEASED`, `RATIFIED`, `M2 enablement`,
`OG-10/genesis signature`, `constitution-byte change`, or release
eligibility. Per `ADR-M5-005`, only `assert_release_eligible.sh` may produce
`RELEASE_ELIGIBLE.json`, and only after a validating `ClosureCertificate.v1`
exists for this exact packet. A PASS certificate on this packet satisfies the
FCE.RUN external-audit prerequisite only.

## Custody Requirements (ADR-M5-002)

Per `ADR-M5-002`, FCE.RUN is the final certification: tier **E1, a different
human operator**, is required (not tier E2 cross-family model, which is only
acceptable for module closures). Your certificate or FAIL artifact must
truthfully record evidence for all six custody booleans:

| boolean | required evidence |
|---|---|
| `fresh_clone` | Record the `git clone` command, checkout command, and resulting `git rev-parse HEAD`. |
| `no_shared_conversation_state` | Start the audit session from this packet and the audit request only; no shared conversation state, no imported implementer summaries. |
| `no_implementer_transcript` | Confirm no implementation transcript or local agent memory was used. |
| `own_credentials` | Use your own credentials as the verifier/operator. Do not reveal secrets. |
| `cross_family_or_human` | FCE.RUN is tier E1: use `external_human_operator`, a different human than any implementer, unless the owner explicitly records a stricter accepted channel. |
| `own_custody_output` | Store the certificate or FAIL artifact in verifier custody first and anchor its sha256 before any in-repo mirror lands. |

## Procedure

1. Clone and checkout the supplied commit; confirm it equals
   `7e0a0bd0a03be088b2dd7833aae92e210d251188`.
2. Take receipt of this packet directory out-of-band (it is not committed to
   the git repository — the evidence root that produced it is a plain
   directory tree under `PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/`, not
   a git repo).
3. Run the digest-depth commands in `REEXECUTION.md` and record literal exit
   codes.
4. Compute your verdict before opening any historical README or session-log
   prose describing this run.
5. Inspect `CLAIM_BOUNDARY.json`, `evidence/FINAL_CERTIFICATION_VERDICT.json`,
   `evidence/FCE_RUN_MANIFEST.json`, and all 19
   `evidence/FCE-*/FCE-*_verdict.json` files.
6. Confirm `SHIPPED`, `RELEASED`, `RATIFIED`, `M2 enablement`, `release
   eligibility`, `OG-10/genesis signature`, and `constitution-byte change`
   claims are absent throughout the packet.
7. Confirm every `automatic_fail_conditions` entry in
   `FINAL_CERTIFICATION_VERDICT.json` is `false`.
8. If any file in the packet or clone must be modified to continue, abort
   and emit a FAIL/finding artifact. Never patch the packet in place.
9. Emit either a `turingos.closure_certificate.v1` PASS/FAIL JSON or a
   machine-readable FAIL artifact.

## Required Answer Shape

Return JSON with:

- `schema_id: turingos.closure_certificate.v1`
- `subject.gate_id: FCE.RUN`
- `subject.repo_url: https://github.com/gretjia/turing`
- `subject.branch: fce/integration-20260704`
- `subject.commit_sha: 7e0a0bd0a03be088b2dd7833aae92e210d251188`
- `subject.packet_root`: the out-of-band packet path you were given
- `subject.packet_sha256` from `PACKET_MANIFEST.json`
- `verifier.kind: external_human_operator` (tier E1 — required for FCE.RUN, not merely cross-family-model)
- all six `verifier.custody` booleans set truthfully
- `verification.commands_run[]` with literal commands and exit codes
- `verification.digest_manifest_result: PASS|FAIL`
- `verification.gate_predicate_result: PASS|FAIL`
- `verdict: PASS|FAIL`
- `status_semantics.implementer_ceiling_was: ADDRESSED`
- `status_semantics.does_not_grant` including `SHIPPED`, `RELEASED`,
  `RATIFIED`, `M2 enablement`, `release eligibility`, `OG-10/genesis
  signature`, and `constitution-byte change`

If the verdict is FAIL, include machine-readable `reasons[]` and a repair
route. Do not write `CLOSED`.
