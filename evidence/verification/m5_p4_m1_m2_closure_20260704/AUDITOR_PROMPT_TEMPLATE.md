# M5.P4 Remaining Module Closure Audit Prompt Template

You are the custody-separated external auditor for TuringOS M5.P4 remaining module closure jobs.

Do not use implementation chat, local plan-directory files, agent memory summaries, or uncommitted local files. Use only the GitHub repository, branch, exact commit SHA supplied by the owner, and files committed under this packet.

## Repository

- Repository: `https://github.com/gretjia/turing`
- Branch: `goal/mini-swe-bench-grok-worker`
- Exact commit: supplied by owner in the surrounding prompt
- Packet root: `evidence/verification/m5_p4_m1_m2_closure_20260704/`

## Audit Scope

Audit M5.P4 module closure queue targets:

- `M1.G`
- `M2.TC5`
- `M2.G`

Do not audit M3.G, M4.G, M5.G, M6.G, FCE.RUN, release eligibility, or SHIPPED status from this packet unless the owner supplies a separate exact-SHA packet for those targets.

## Required Inputs

Start from:

- `evidence/verification/m5_p4_m1_m2_closure_20260704/PACKET.json`
- `evidence/verification/m5_p4_m1_m2_closure_20260704/SOURCE_MAP.json`
- `evidence/verification/m5_p4_m1_m2_closure_20260704/REPO_ARTIFACTS.json`
- `evidence/verification/m5_p4_m1_m2_closure_20260704/PACKET_MANIFEST.sha256`

The packet contains copied plan artifacts under:

- `evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/`

Repo-native artifacts remain at their normal GitHub paths and are listed in `REPO_ARTIFACTS.json`.

## Custody Requirements

You must be able to truthfully set all six custody booleans to true:

- `fresh_clone`
- `no_shared_conversation_state`
- `no_implementer_transcript`
- `own_credentials`
- `cross_family_or_human`
- `own_custody_output`

If any custody boolean is false, return `FAIL`.

## Required Checks

1. Fresh-clone the GitHub repository and checkout the exact owner-supplied commit SHA.
2. Verify `PACKET_MANIFEST.sha256` from inside the packet root:

   ```bash
   cd evidence/verification/m5_p4_m1_m2_closure_20260704
   sha256sum -c PACKET_MANIFEST.sha256
   ```

3. Verify every copied plan artifact in `SOURCE_MAP.json` exists at its `github_path` and matches its `sha256`.
4. Verify every repo-native artifact in `REPO_ARTIFACTS.json` exists at its GitHub path and matches its `sha256`.
5. Run the packet-local M1.G recheck:

   ```bash
   bash evidence/verification/m5_p4_m1_m2_closure_20260704/packet_checks/run_m1_g_recheck.sh
   ```

6. Run the packet-local M2.TC5/M2.G boundary check:

   ```bash
   bash evidence/verification/m5_p4_m1_m2_closure_20260704/packet_checks/run_m2_tc5_boundary_check.sh
   ```

7. For `M2.TC5`, run TC-10 yourself from the clean clone. The implementer-side `TC-10.json` is intentionally `NOT_RUN` with `not_run_is_fail: true`; treating it as PASS is a FAIL.
8. For `M1.G`, decide whether the packet supports only this claim:

   `M1.G is ADDRESSED at the implementer ceiling as a canonical-substrate G2 roll-up, not external verification.`

9. For `M2.TC5/M2.G`, decide whether the clean-clone TC-10 action and M2 boundary support PASS or FAIL. Do not infer Turing-completeness unless TC-10 is actually executed under your custody and its result supports the claim boundary.
10. Check that no target claims release, SHIPPED status, M2 enablement, OG-10/genesis signature, constitution-byte change, or external verification before your certificate.

## Output

Return one JSON object using `ClosureCertificate.v1` shape:

- `schema_id`: `turingos.closure_certificate.v1`
- `subject.gate_id`: `M5.P4`
- `subject.module_targets`: `["M1.G", "M2.TC5", "M2.G"]`
- `subject.repo_url`: `https://github.com/gretjia/turing`
- `subject.branch`: `goal/mini-swe-bench-grok-worker`
- `subject.commit_sha`: exact commit you audited
- `subject.packet_root`: `evidence/verification/m5_p4_m1_m2_closure_20260704`
- `verifier.kind`: `external_human_operator` or `external_cross_family_model`
- `verification.commands_run`: include commands and exit codes, including your TC-10 command/result
- `verification.digest_manifest_result`: `PASS` or `FAIL`
- `verification.gate_predicate_result`: `PASS` or `FAIL`
- `verdict`: `PASS` or `FAIL`

If the verdict is `FAIL`, include machine-readable reasons. Do not repair the packet. Do not infer from implementation chat. Do not grant release or SHIPPED status.
