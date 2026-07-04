# M5.P4 M6.G Module Closure Audit Prompt Template

You are the custody-separated external auditor for the TuringOS M5.P4 module closure job targeting M6.G.

Do not use implementation chat, local plan-directory files, agent memory summaries, or uncommitted local files. Use only the GitHub repository, branch, exact commit SHA supplied by the owner, and files committed under this packet.

## Repository

- Repository: `https://github.com/gretjia/turing`
- Branch: `hci/operator-console-v1-rebased`
- Exact commit: supplied by owner in the surrounding prompt
- Packet root: `evidence/verification/m5_p4_m6_closure_20260704/`

## Audit Scope

- Target gate: `M6.G`
- Closure service: `M5.P4`
- Certificate schema: `ClosureCertificate.v1`
- Status ceiling before your audit: `ADDRESSED`
- M6.G is not externally verified by this packet. Only your custody-separated PASS certificate can certify the target as `EXTERNALLY_VERIFIED`.

## Required Checks

1. Fresh clone the repository and check out the exact commit supplied by the owner.
2. Run `cd evidence/verification/m5_p4_m6_closure_20260704 && sha256sum -c PACKET_MANIFEST.sha256`.
3. Run `bash evidence/verification/m5_p4_m6_closure_20260704/packet_checks/run_m6_g_rollup_check.sh` from the repository root.
4. Independently verify every `SOURCE_MAP.json` entry points to an existing copied packet artifact with a matching sha256.
5. Independently verify every `REPO_ARTIFACTS.json` entry points to an existing repository file at the checked-out commit with a matching sha256.
6. Confirm `M6G_GATE_VERDICT.json` is `GateVerdict.v1`, `gate_id: M6.G`, `status: ADDRESSED`, `status_ceiling: ADDRESSED`, and `not_run_is_fail: true`.
7. Confirm the G7 predicates are true: HCI-A ADR accepted, displayed values replayable, zero head-moving paths static and dynamic, and branch committed/archived.
8. Confirm no packet artifact authorizes HCI-B, any write-capable console behavior, SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, or constitution-byte change.

## Certificate Output

Return a single JSON object conforming to `turingos.closure_certificate.v1`.

Use:
- `subject.gate_id`: `M5.P4`
- `subject.module_targets`: [`M6.G`]
- `subject.repo_url`: `https://github.com/gretjia/turing`
- `subject.branch`: `hci/operator-console-v1-rebased`
- `subject.commit_sha`: the exact commit you checked out
- `subject.packet_root`: `evidence/verification/m5_p4_m6_closure_20260704`
- `verifier.kind`: `external_human_operator` or `external_cross_family_model`
- all six custody booleans set according to what you actually did

If any required check fails, return `verdict: FAIL` with machine-readable reasons and missing or mismatched paths. Do not repair the packet in place.
