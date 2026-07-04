# M6.G Drift-Check Checklist

Scoring rule: `NOT_RUN` counts as `FAIL`; every answer cites an openable artifact path.

| q | question | answer | artifact_path | verdict |
|---|---|---|---|---|
| 1 | Does the deliverable serve one of G1-G7? Which KPI, exactly? | Serves G7: HCI-A ADR accepted, 100% displayed values replayable by automated projection-integrity audit, zero head-moving UI paths by static plus dynamic checks, and the HCI branch is committed. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M6_hci_console.md | PASS |
| 2 | Does it violate any red line in Intent section 5? | No. The roll-up changes no constitution bytes, uses no genesis/OG-10 signature, does not enable M2, does not authorize HCI-B, and does not authorize write-capable console behavior. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/02_EXECUTION_PLAYBOOK.md | PASS |
| 3 | Is every claim backed by an artifact path an independent agent can open? | Yes. The roll-up digest-binds the accepted ADRs, rescue archive, rescue branch evidence, static gates, dynamic gates, projection-integrity gate, and M5.P4 handoff packet. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_ARTIFACT_ROLLUP.json | PASS |
| 4 | Is anything labeled real that is a fixture? Is anything unlabeled? | No. The original rescue archive remains FIXTURE_AND_SELF_RUN, while the current HCI gate results are deterministic implementation evidence on fixture MicroTapes. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/rescue/operator_console_v1/CLAIM_BOUNDARY.json | PASS |
| 5 | Did scope grow beyond the Atom/Phase spec? If yes, cite the decision. | No. This assembles MODULE_M6 section 3 artifacts and prepares the M5.P4 closure handoff; it does not merge HCI to main or add HCI-B behavior. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M6_hci_console.md | PASS |
| 6 | Can the work be replayed or resumed by a fresh agent from tracker plus tape alone? | Yes. Tracker rows cite every phase artifact, while this roll-up binds the artifact list and M6.P5 hci-gates can be rerun from the pushed branch. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/PROGRESS_TRACKER.md | PASS |
| 7 | Does the status honor the ADDRESSED ceiling? | Yes. M6.G is ADDRESSED only; external verification requires the M5.P4 custody-separated closure queue. | /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P5_PROJECTION_INTEGRITY_RESULT.json | PASS |

HCI-A route ADR: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/adr/ADR-M6-001-adopt-hci-a-projection-route.md`.
Dynamic no-write evidence: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P4_DYNAMIC_GATES_RESULT.json`.
