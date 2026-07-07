# ADR-M1-001 - Single Canonical JCS Owner

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
  - path: /home/zephryj/turingos_backup/work/turing/crates/turing-contracts/src/jcs.rs
    sha256: 762956473a9d6385dc1fb7a3eda71ca4374bc68df6171d7ba5a00e461ab40ad9
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/codec.py
    sha256: 41368869c054f927dee255c8574ae67fe1264013f9d13a4f8924aea59c9fe279
  - path: /home/zephryj/turingos_backup/work/turing/tools/gates/corpus_jcs_extended.jsonl
    sha256: a9c96df869870c992e7895eef81597ebf3273642eae90d970c885766ba66f2eb
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1A_GATE_CLEAN_TRANSCRIPT.txt
    sha256: 139b4996967181d15d6367550415ba7c0c3119020c857cf5c53a9b3a1e21ca66
status_ceiling: ADDRESSED
```

## Context

M1a must end the recurring drift where multiple components silently define canonical JSON bytes. The Rust implementation in `crates/turing-contracts/src/jcs.rs` already owns the restricted `turingos.jcs.v1` profile: strict parse, ASCII object keys, integer-only values, sorted object keys, minimal separators, raw UTF-8 string values, and forbidden payload-field checks.

Python still has `src/turingos/codec.py`. Until M1e routes Python through the owner, it is a derived view and must remain byte-equal to the Rust owner on an extended corpus.

## Decision

Designate `turing-contracts::jcs` as the single canonical-bytes owner for `turingos.jcs.v1`.

`src/turingos/codec.py` is not a second owner. It is a derived compatibility view until M1e routes Python calls through the Rust owner path. Its continued use is allowed only under the M1a xcheck and singleton gates.

## Consequences

New substrate canonical-byte behavior belongs in `turing-contracts::jcs`. Any new Python or tool-side canonical-byte implementation must fail the M1a grep/AST gates unless it is explicitly allowlisted with a bounded migration reason.

This ADR does not claim Python routing is complete, historical tapes are rewritten, M1.G/G2 is complete, external verification exists, constitution bytes changed, an OG-10/genesis signature exists, M2 is enabled, or any CLOSED, RELEASED, or RATIFIED status.
