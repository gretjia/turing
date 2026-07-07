# M5 Auditor Runbook

Evidence class: REAL_DETERMINISTIC_PROTOCOL. This runbook is executable protocol text for M5-class packet audits. It does not itself issue a ClosureCertificate.

## Inputs

You need exactly the packet directory and its packet digest from the owner channel. Do not use implementer summaries, chat history, session notes, or out-of-packet explanations.

## Custody Evidence

Record evidence for each ClosureCertificate custody boolean:

| boolean | evidence instruction |
|---|---|
| `fresh_clone` | Create the working copy only from the packet's repo material in a directory that has not hosted implementer work; record the clone command and resulting HEAD. |
| `no_shared_conversation_state` | Start the verifier session from this runbook, the packet, the gate spec, the drift checklist, the status vocabulary, and the constitution pointer only. |
| `no_implementer_transcript` | Run lineage scrub over the submitted bundle and record that no implementer narrative, session id, or subagent reference was supplied. |
| `own_credentials` | State the credential class used by the verifier without revealing secrets; it must belong to the verifier or owner-provisioned auditor identity. |
| `cross_family_or_human` | Record verifier kind as `external_human_operator` or `external_cross_family_model` and compare it with the packet implementer manifest. |
| `own_custody_output` | Store the certificate in verifier custody first and record its sha256 through the owner/auditor channel before any in-repo mirror lands. |

## Procedure

0. Confirm the packet directory is the only local input and record `packet_sha256`.
1. Verify packet closure: `sha256sum -c MANIFEST.sha256`. Any mismatch is a FAIL.
2. Verify repository pin: clone the packet repo material, or for M5.P2 fixture packets compare `repo_head.txt` to `PACKET_MANIFEST.json.repo_sha`.
3. Verify every path in `PACKET_MANIFEST.json.required_artifacts` exists exactly once in the packet.
4. Execute `REEXECUTION.md` in order. Record every command and exit code.
5. Compute your verdict before opening any historical `EXPECTED_VERDICT` material.
6. If anything in the packet or clone is modified, abort and report findings only. Do not emit a verdict.
7. If all checks pass, fill `turingos.closure_certificate.v1`, store it in verifier custody, anchor its sha256, and only then send the certificate file.

## M5.P2 Fixture Audit

For the M5.P2 calibration corpus, `m5_verification/tools/audit_packet_fixture.py <packet_dir>` implements the deterministic subset of this runbook. A PASS means the fixture packet reaches certificate handoff. A FAIL reports the machine-readable seeded reason.
