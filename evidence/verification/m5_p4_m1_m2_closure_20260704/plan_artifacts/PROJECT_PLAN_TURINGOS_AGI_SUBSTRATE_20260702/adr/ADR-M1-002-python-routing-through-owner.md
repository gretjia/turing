# ADR-M1-002 - Python Routing Through Owner

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M1_canonical_substrate.md
    sha256: ab3ffbe4fe1aa4a6e6d421c40b5fa9fd2b285e38c6653cd7412d6766bf8401e6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M1_canonical_substrate_integrity.md
    sha256: 6a33aab542dd00b15b8f567fd379a772a5dd83b1223eae25cfa4dd1fd0e2f664
  - path: /home/zephryj/turingos_backup/work/turing/crates/turing-xcheck/src/main.rs
    sha256: b03d1aeb5134d70c3770a59a6a913c042a6f858caa0a5f5894c74df025bd165f
  - path: /home/zephryj/turingos_backup/work/turing/tools/gates/xcheck_emit.py
    sha256: 688462a581f6257e27ca4e59bca61b66fa36562b479f4b45b2c3a03a48ccfae2
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1A_RUST_TRANSCRIPT.txt
    sha256: 81dab95966ae726880a02c32276d23fe8f655e4230ba5b9c0fb377ced51b73d5
status_ceiling: ADDRESSED
```

## Context

M1e must route Python canonical-byte calls through the owner after M1a has proven byte equality and installed recurrence gates. The plan rejects a PyO3 binding in this increment because it adds packaging and ABI surface area before the daemon append path is stabilized.

## Decision

The routing architecture is a process boundary first, daemon-owned append path second:

- Phase 1: expose a batch-capable `turing jcs` CLI verb backed by `turing-contracts::jcs`; `src/turingos/codec.py` delegates to that process boundary after the M1a xcheck remains green.
- Phase 2: new tape appends go through daemon-owned `event.append_preserve`; Python `Tape` becomes a labeled fixture/legacy compatibility path.

PyO3 is rejected for this increment. Historical tapes are never rewritten as part of routing.

## Consequences

M1a gates protect the migration by failing new canonical-byte implementations before routing is complete. M1e owns the implementation of CLI delegation and daemon append routing.

This ADR records the routing decision only. It does not claim M1e is implemented, Python routing is complete, M1.G/G2 is complete, external verification exists, constitution bytes changed, an OG-10/genesis signature exists, M2 is enabled, or any CLOSED, RELEASED, or RATIFIED status.
