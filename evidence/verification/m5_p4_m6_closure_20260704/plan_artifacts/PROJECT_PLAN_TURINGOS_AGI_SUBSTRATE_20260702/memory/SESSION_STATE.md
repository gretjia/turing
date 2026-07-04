Purpose: the exact position of the most recent working session, so a fresh orchestrator resumes in minutes (playbook §7.2-§7.3). This file is a SNAPSHOT, not history: overwrite it wholesale at each checkpoint. History lives in `PROGRESS_TRACKER.md` (session log) and ground-truth evidence. On any conflict, the tracker overrides this file, and disk artifacts override both.

---

## Snapshot (overwrite everything below this line at each checkpoint)

- **Session:** 1 (Codex execution session)
- **Timestamp:** 2026-07-04T05:20:00Z
- **Checkpoint reason:** M6.G HCI-A projection module-gate roll-up completed at implementer ceiling. The next least-human step is M6.G exact-SHA GitHub packetization for M5.P4 custody-separated external audit, while existing M1.G/M2.TC5/G and M5.G external-audit packets remain pending external certificates.

### Position

- **Current wave:** W4/W5 execution frontier.
- **Active module/phase/atom:** M5.P4 remains IN_PROGRESS as a standing custody-separated closure queue. M3.G/M4.G are EXTERNALLY_VERIFIED; M1.G and M2.TC5/G have a GitHub packet but are not externally verified; M6.G is ADDRESSED with a local M5.P4 handoff but is not yet packet-published or externally verified. M5.G is ADDRESSED with a GitHub audit packet but is not externally verified; M5.P3 is EXTERNALLY_VERIFIED; FCE.ENTRY/RUN remain unavailable until module/external prerequisites are satisfied.
- **Last completed work:** M6.G module-gate roll-up assembled `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_ARTIFACT_ROLLUP.json` sha256 `3dd8d223d891e8f373d1a82c570afac7e76fdf4efc92ce5b4e6356bab4f60c8e`, drift checklist sha256 `bd169f2eee12b2ea4dc4cc6d7d2b52f7378afee1def3c26c2df976b7aa4b9dec`, gate verdict sha256 `a0dcee840a21a1b7f74e74e016a26098d62413fad2ac6950ade3969f52a295d3`, M5.P4 handoff sha256 `6751ba004630a5ebb6979ea940a08ac5b8a89905863da4e4c2fee3cc1fc98048`, and manifest sha256 `32f6a222c77c97f4dd402124b0eca52c50db2a82a0c99005070ba4cf7350b15e`.

### In-flight atoms

| Atom | State | Next action |
|------|-------|-------------|
| M5.P4 | IN_PROGRESS | M3.G/M4.G queue jobs are EXTERNALLY_VERIFIED via Grok PASS. Submit packet root `evidence/verification/m5_p4_m1_m2_closure_20260704` at commit `e2a77772a98b5511bd90077bd8e95bf9d3b9505b` for M1.G and M2.TC5/G external audit; build/publish an exact-SHA M6.G packet from handoff `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_M5_P4_HANDOFF_PACKET.json` sha256 `6751ba004630a5ebb6979ea940a08ac5b8a89905863da4e4c2fee3cc1fc98048`. |
| M5.G | ADDRESSED | Submit the GitHub packet root `evidence/verification/m5_g_module_gate_20260704` at commit `fbb722086602a61a181f8617a5d77a7e80d5524a` to a custody-separated auditor if M5.G external verification is required before FCE.ENTRY. |
| M6.P3 | ADDRESSED | Static no-write gates are pushed at commit `7192f12a55ef0e834e24d68e8e6f3550cc55026e`; keep them in M6.P5 hci-gates CI. |
| M6.P4 | ADDRESSED | Dynamic head-conservation and read-only-FS gates are pushed at commit `e2944cd512794e0f5cd677dc444ba3dd36119d41`; retained by M6.P5 hci-gates. |
| M6.P5 | ADDRESSED | Projection-integrity auditor, provenance manifest, `--json`/render-fidelity support, worker-leakage grep, repo-committed `hci-gates`, and GitHub Actions `hci-gates` job are pushed at commit `0fd16d1abede372fa8514824ef98a4405e780a86`; feeds the completed M6.G roll-up. |
| M6.G | ADDRESSED | Local roll-up, drift checklist, GateVerdict, manifest, and M5.P4 handoff are present and verified. Next action: packet-publish M6.G for custody-separated M5.P4 audit; do not claim EXTERNALLY_VERIFIED until an external certificate returns. |
| FCE.ENTRY / FCE.RUN | BLOCKED | Entry depends on remaining module gates and external criteria; RUN requires its own custody-separated external audit path. |

### Repo State At Checkpoint

- `/home/zephryj/turingos_backup/work/turing`: branch `hci/operator-console-v1-rebased`, pushed to origin at `0fd16d1abede372fa8514824ef98a4405e780a86`; `evidence/verification/` is visible as untracked only because this branch is based before the M5 packet commits and must not be added to the HCI rescue branch.
- Plan tree contains updated M5.P3/M5.P4 pass records, M5.G roll-up artifacts, M5.G GitHub packet record, M5.P4 remaining-queue packet record, M6.P1 acceptance artifacts, M6.P2/M6.P3/M6.P4/M6.P5 result artifacts, M6.G roll-up/handoff artifacts, tracker updates, and refreshed session state.
- Workspace-root `AGENTS.md` instruction says `TOP_ALIGNMENT_PROJECT_BOOK.md` is the top alignment file for TuringOS work under this directory, but not human-ratified, OG-10 signed, or M2-enabling by existence alone.

### Key M5.P3 Artifacts

- GitHub audit target: `https://github.com/gretjia/turing`, branch `goal/mini-swe-bench-grok-worker`, audited commit `5383e6919590d84fafc46b07e52af1c282dfdc75`.
- Packet root: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p3_first_external_audit_20260704`.
- Packet digest: `sha256:6442d1e1773b3f4385e75767c22dfff6469984dbf0ceff2a90f7c56a99b0618c`.
- External PASS certificate mirror: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p3_first_external_audit_20260704_external_pass/M5_P3_GROK_PASS_CERTIFICATE.json` sha256 `8be75cf0f62c217bc9dd8eccbdc0b0f1e1337ee98e88c04e8fda60edf232e7cf`.
- Certificate mirror commit: `/home/zephryj/turingos_backup/work/turing` `072673ad38734f7e2b33ac7198ae6438b669abe4`.
- Plan pass record: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5_P3_FIRST_AUDIT_PASS_RECORD.json` sha256 `747a2a14eeaeb88c7627f052e1aeaec9603f2227c96d82297a93bfc0d05a9a75`.
- Packet record: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5_P3_FIRST_AUDIT_PACKET_RECORD.json` sha256 `a84208046b002eb5182037b4c2359ca07d79a021b5d5a8d7c17ee951ebfa19c7`.

### Key M5.P4 Artifacts

- External PASS certificate mirror: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p4_module_closure_20260704_r2_external_pass/M5_P4_GROK_PASS_CERTIFICATE.json` sha256 `00d9c6a7594fafe1b4c38046110046aed3dc8337b68e62606c40584498896a4f`.
- Plan pass record: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5_P4_MODULE_CLOSURE_PASS_RECORD.json` sha256 `ed361b58dbac0b8e47244b31dd30d4ef603c47da02d81611624ea5f5b9f89465`.
- Remaining-queue GitHub packet: repo `https://github.com/gretjia/turing`, branch `goal/mini-swe-bench-grok-worker`, commit `e2a77772a98b5511bd90077bd8e95bf9d3b9505b`, root `evidence/verification/m5_p4_m1_m2_closure_20260704`.
- Remaining-queue packet JSON: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p4_m1_m2_closure_20260704/PACKET.json` sha256 `06e83aedff8de953c4f436fd95c9d359e37da963fe175eb712105f30fd6a1f15`.
- Remaining-queue packet manifest: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p4_m1_m2_closure_20260704/PACKET_MANIFEST.sha256` sha256 `ae1c9aa91dbaf38a4e21e1a711611a8a795700eee84c6cae6d2739dab75ed344`.
- Remaining-queue source map: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p4_m1_m2_closure_20260704/SOURCE_MAP.json` sha256 `be4ee490d7fdaae97bd420ec197ec0607c7e907c6a180f71d836dab55e9429d6`.
- Remaining-queue repo artifacts: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p4_m1_m2_closure_20260704/REPO_ARTIFACTS.json` sha256 `79d34db813fb4809419b6eb329b61ccc0146d078956b8f77699f6194ba06259b`.
- Remaining-queue auditor prompt template: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_p4_m1_m2_closure_20260704/AUDITOR_PROMPT_TEMPLATE.md` sha256 `090c5a9c1496662c9f9af75a46848c51c697c0b4a3af435ca8b4237b7f60c2c8`.
- Remaining-queue plan packet record: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5_P4_REMAINING_QUEUE_PACKET_RECORD.json` sha256 `304cb610b58eb8b6c05fc6a2c8b03ca4ff325bfae36fa2c9c315524bbacd638a`.

### Key M5.G Artifacts

- Assembler: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m5_verification/assemble_m5_gate.py` sha256 `a118a937c1aa192a6f606ccf149a39bfba585a94602c186ec8cab8ad242a0b86`.
- Focused test: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m5_verification/tests/test_m5_g_rollup.sh` sha256 `9bd7b447a23864807853807e34e2d0c546bb2279d7b5cd64f0d264b1b510363d`.
- Roll-up: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_ARTIFACT_ROLLUP.json` sha256 `3d9adb750b765778f4f04828457b91fbab619eb3e2991dbd53a13ff2ab7be5e6`.
- Drift checklist: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_DRIFT_CHECKLIST.md` sha256 `560e7636b3601f5b5a9ba4ea19d203162bd576560401d11dbe23c8df1326cad7`.
- Gate verdict: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_GATE_VERDICT.json` sha256 `7cbf6bb5009ab9edfb9373cc7f8fe697f4cc0849c59852146b1e5947e1338942`.
- External hand-off packet: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_EXTERNAL_HANDOFF_PACKET.json` sha256 `b784fc45f119ca2e41d6aa2d38bdc2acd05ad3dff7accb04805058680be1baf4`.
- GitHub audit packet: repo `https://github.com/gretjia/turing`, branch `goal/mini-swe-bench-grok-worker`, commit `fbb722086602a61a181f8617a5d77a7e80d5524a`, root `evidence/verification/m5_g_module_gate_20260704`.
- Packet JSON: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_g_module_gate_20260704/PACKET.json` sha256 `d043bc6e57405c13fd12c4b51c33da7a9f088d15c439e0c41e35560c93d123f1`.
- Packet manifest: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_g_module_gate_20260704/PACKET_MANIFEST.sha256` sha256 `4300993b995f791dff0844d04e3647413fea2fd0b444125d6f1685549c1146cb`.
- Source map: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_g_module_gate_20260704/SOURCE_MAP.json` sha256 `616d269fbb56f2fbd3d0725a5f24c0398e87ebdddf5f3a2e3b82f1976dad06f7`.
- Auditor prompt template: `/home/zephryj/turingos_backup/work/turing/evidence/verification/m5_g_module_gate_20260704/AUDITOR_PROMPT_TEMPLATE.md` sha256 `a887eb10ab68c6afb187b7e33559b84ad84671b375432fce326f6a36a0eaa8e1`.
- Packet record: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_EXTERNAL_PACKET_RECORD.json` sha256 `e199786669dd60040e647c30624c2d654803f126d29cd5ec0c30194309ad24b5`.

### Key M6.P5 Artifacts

- HCI branch: `/home/zephryj/turingos_backup/work/turing`, branch `hci/operator-console-v1-rebased`, pushed commit `0fd16d1abede372fa8514824ef98a4405e780a86`.
- Result: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P5_PROJECTION_INTEGRITY_RESULT.json` sha256 `b95159eb21f2f5961b289c72e2ea3235600ac55521d0add8318338cf5c864879`.
- Artifact manifest: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P5_ARTIFACT_MANIFEST.sha256` sha256 `5d247829380a26bfdc886ce48ef3ff03240d097a5d1e4ce4f564a4d619c5213c`; `sha256sum -c` PASS.
- Projection-integrity verdict: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/m6_p5_hci_gates_20260704/hci_projection_integrity_verdict.json` sha256 `502e80990f50ef8e8dedfc3ee15d7e49ce75efcfebba0657d8552aeddf4c6cce`; checks `shadow_rebuild`, `independent_heads`, `provenance_closure`, `render_fidelity`, and `worker_leakage` all PASS.
- Aggregate hci-gates result: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/m6_p5_hci_gates_20260704/hci_gates_result.json` sha256 `c9a7abf562ba7b017a08ccd2126fae4ea012048a10bf6a97d32eefb99aded14d`; verdict PASS.
- Key repo files: `tools/hci/audit_projection_integrity.py` sha256 `8a7d3153d3cffcdf5ff32462f85a6a4d940f28ef9b435aaaa7e26564c41c2e96`; `schemas/operator/operator_view_snapshot.v1.provenance.json` sha256 `e51287ba978714b2fb14594880e28a9565469b8878e236e29faedd7ec41af838`; `tools/hci/run_hci_gates.sh` sha256 `7b9c28d6016c24422386d272af8d2c09c2cf0fcfeda6885df54840c3233ba520`.

### Key M6.G Artifacts

- Assembler: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m6_hci/assemble_m6_gate.py` sha256 `36bdcd20b1124b782a36d8eb64579813778264d1c047d73bcadd8594f47690f4`.
- Focused test: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m6_hci/tests/test_m6_g_rollup.sh` sha256 `d99600a7f36965afe200f6e282a819cce53e1e55e937753d99dd8cf68cf7e1bf`.
- Roll-up: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_ARTIFACT_ROLLUP.json` sha256 `3dd8d223d891e8f373d1a82c570afac7e76fdf4efc92ce5b4e6356bab4f60c8e`.
- Drift checklist: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_DRIFT_CHECKLIST.md` sha256 `bd169f2eee12b2ea4dc4cc6d7d2b52f7378afee1def3c26c2df976b7aa4b9dec`.
- Gate verdict: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_GATE_VERDICT.json` sha256 `a0dcee840a21a1b7f74e74e016a26098d62413fad2ac6950ade3969f52a295d3`.
- M5.P4 handoff: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_M5_P4_HANDOFF_PACKET.json` sha256 `6751ba004630a5ebb6979ea940a08ac5b8a89905863da4e4c2fee3cc1fc98048`.
- Artifact manifest: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_ARTIFACT_MANIFEST.sha256` sha256 `32f6a222c77c97f4dd402124b0eca52c50db2a82a0c99005070ba4cf7350b15e`; `sha256sum -c` PASS.

### Key M6.P4 Artifacts

- HCI branch: `/home/zephryj/turingos_backup/work/turing`, branch `hci/operator-console-v1-rebased`, pushed commit `e2944cd512794e0f5cd677dc444ba3dd36119d41`.
- Result: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P4_DYNAMIC_GATES_RESULT.json` sha256 `6fc596043ca7b5a5f466f4a680ff83c94047be00099ad4a7d84cdefb1afcedf9`.
- Artifact manifest: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P4_ARTIFACT_MANIFEST.sha256` sha256 `3273b0a6a58e8a9bf9fa9064f9fb98086f85f6b2d03107cb649cea622d7208a5`; `sha256sum -c` PASS.
- Focused head-conservation transcript: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P4_HEAD_CONSERVATION_TEST_TRANSCRIPT.txt` sha256 `511a7be7e13916a35df58c33a0cfbcc3360e4c55af7f9ff8f02e3069c842c30c`.
- Focused read-only-FS transcript: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P4_READONLY_FS_TEST_TRANSCRIPT.txt` sha256 `a7348b31b58ffb2fbdab510da838e2ba13fda7186aa1330a1c768d820b1d9542`.
- Regression transcripts: CLI gates sha256 `99ae31dac06a329bd06c61f09cf9a29a7bcca5eea14b3aaf483849c1fe1b6a07`; package tests sha256 `08854b2924a94d6de67756a99f2478380c82d9e79c8ee169f76bf29e842d3f88`; static no-write gate sha256 `bfba9dd1e8e10bf2da227275a3a73f972cf8ebccae8d4c3ebf05a1f83bed4350`; clippy sha256 `c92508a29848820f033cd2ea015c85dde0953c88b07cc967ce34b7c08f610549`.

### Non-Claims

- M5.P3 is EXTERNALLY_VERIFIED only for the first-audit packet root; it does not grant M5.G, FCE.RUN, SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, OG-10/genesis signature, constitution-byte change, full SWE-bench score, or leaderboard equivalence.
- M5.G is ADDRESSED only; the GitHub packet makes it auditable but is not itself an external certificate and does not grant FCE.RUN or release eligibility.
- M5.P4 external PASS covers only M3.G and M4.G. M1.G and M2.TC5/G have a GitHub packet but no external certificate yet; M6.G has a local handoff but no GitHub packet/certificate yet; FCE.RUN remains outside those packets.
- M6.P1 through M6.G are ADDRESSED at implementer ceiling. This does not authorize HCI-B, any write-capable console behavior, external verification, release eligibility, FCE.RUN, SHIPPED, RELEASED, RATIFIED, M2 enablement, OG-10/genesis signature, or constitution-byte change.
- API secret values are not recorded in plan files, repo evidence, tracker, or this snapshot.

### Resume Checklist

1. Build and publish an exact-SHA GitHub-visible M6.G packet for M5.P4 custody-separated audit. Be careful not to add unrelated `evidence/verification/` content from other branches.
2. Submit the exact-SHA packet for M1.G and M2.TC5/G, plus the new M6.G packet once published, if a custody-separated auditor channel is available.
3. If FCE.ENTRY demands M5.G's declared external verifier class before entry, submit the GitHub packet root `evidence/verification/m5_g_module_gate_20260704` at commit `fbb722086602a61a181f8617a5d77a7e80d5524a` to a custody-separated auditor and record the returned PASS/FAIL without patching in place.
4. Continue least-human-in-loop work on remaining non-owner-blocked gates; halt only on a real owner/external gate or a failing ship gate that cannot be repaired by implementation.
