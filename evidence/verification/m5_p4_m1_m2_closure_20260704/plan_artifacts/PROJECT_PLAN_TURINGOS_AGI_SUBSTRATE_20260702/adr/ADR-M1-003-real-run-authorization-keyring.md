# ADR-M1-003 - Real-Run Authorization via Headless OS Keyring

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M1_canonical_substrate.md
    sha256: ab3ffbe4fe1aa4a6e6d421c40b5fa9fd2b285e38c6653cd7412d6766bf8401e6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M1_canonical_substrate_integrity.md
    sha256: 6a33aab542dd00b15b8f567fd379a772a5dd83b1223eae25cfa4dd1fd0e2f664
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1B_XDG_KEYRING_PROBE_TRANSCRIPT.txt
    sha256: 234e32ad63225990397bacc58ef70e01b01af962a85dfcfdd23b763e7b0c1b38
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py
    sha256: fdc36776a324985c84edea143f7a18c0e357cd98322c85372a71b462ccf933aa
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/evaluate_django_swe_bench_patches.py
    sha256: 28db4fffea917af839a20b1e438e5ef18ba6df4cc8baaf4e62798a0b13168c2c
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1B_REAL_GROK_SMOKE_V2_TRANSCRIPT.txt
    sha256: a3fc03c1fe631d853178e03d7ac358a31e2da7acfd9d46df7771b305596bbadf
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1B_REAL_GROK_OS_KEYRING_SMOKE_V2/substrate_coverage.json
    sha256: f93257df21db2e71eb947315be2e4e614804801d4a0d3cd1bddbfa1f814327ef
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1B_REAL_GROK_PATCH_EVAL_V2_TRANSCRIPT.txt
    sha256: a96747c1a283941fbda21610d95149fe6987e21c6f7fc397d67c957142f9bee6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1B_REAL_GROK_PATCH_EVAL_V2/patch_eval_summary.json
    sha256: 5b3f9db0e93fb43e521bb623973bc12827e30e7eff5160186c37f17a1c2e1a8c
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1B_REAL_GROK_STRICT_AUDIT_V2/micro_tape_decision_dag_audit.json
    sha256: 882bdb449d906f789486837e9bd8b1590cb9eecaaac7b0e98c87a32dfd2f9795
status_ceiling: ADDRESSED
```

## Context

RES_M1 identifies the R9 gap: `authorization_head` had not passed the strict auditor on a real worker run. The production authorization signer is the OS-keyring route through `secret-tool`, so a file-backed local signing pass would not close that gap.

The default user keyring was not unlocked by an arbitrary passphrase during this session. A fresh headless Secret Service collection did work when isolated under a fresh `XDG_DATA_HOME`, while preserving the normal `HOME` required by the Grok CLI. The fresh collection was unlocked under `dbus-run-session` with a 0600 passphrase file outside the repo; the transcripts record only redacted metadata and digests, not secret material.

## Decision

M1b real-run authorization uses:

- `dbus-run-session` with `gnome-keyring-daemon --unlock --components=secrets`.
- Fresh session-scoped `XDG_DATA_HOME` for the keyring collection.
- Normal `HOME` for the Grok CLI worker context.
- `--authorization-mode required --authority-provider os-keyring`.
- Strict MicroTape replay audit requiring authorization head, cost provenance, sandbox provenance, terminal market, and VPPUT.

The real evidence run is `django__django-12039` with worker mode `grok`, model `grok-build`, and an OS-keyring authorization head on tape. The V2 strict audit verdict is PASS with `authorization_head: PASS`, `sandbox_provenance: PASS`, `cost_provenance: PASS`, `vpput_accounting: PASS`, `market_accounting_correctness: PASS`, and no strict findings.

## Consequences

The first non-fixture real worker run now exercises the exact OS-keyring authorization path and exports a replayable MicroTape bundle with three refs, including `refs/turingos/authorization_head`. The run also keeps the M1d sandbox and M1c cost-provenance auditors green for this evidence root, but this ADR does not by itself close M1c's separate real provider receipt requirement.

Passphrases and authorization seed material remain outside repo evidence and are not written to tape. This ADR does not claim M1.G/G2 roll-up, M1c closure, external verification, constitution-byte change, OG-10/genesis signature, M2 enablement, CLOSED, RELEASED, RATIFIED, or SHIPPED status.
