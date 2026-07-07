# ADR-M1-004 - CostEvent.v2 Worker Identity and Cost Provenance

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
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/schemas.py
    sha256: 506ff301a5dcefe78aed42690bda3e48d6d6eaa6ee256ce6a7ec1c900965c18b
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/worker/cost.py
    sha256: 6d2136681d468693d86d90450bc5e34dba21aebaf02de25d21c78a3755312078
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/worker/adapter.py
    sha256: fc9ede6035889560fefbb0b103e8cc0466f766e3ccac8b7757a842df0b00d6e9
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/worker/cli.py
    sha256: ee7c028ac2abe16379c243e10537069cf8d529aa2f3216e6ebad22803ee869c2
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/worker/fake.py
    sha256: 8ccd0501e1718be8464bb93fdd08d4c74d2c56c0f9cf4cfcd3dbd44a1ba8bea4
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/audit_micro_tape_decision_dag.py
    sha256: 5967e422dc8b93388d56cebfe9ea0108351895896b16188be70cb55edd626eae
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py
    sha256: 2141da7206b380c9f521539194392a81e17b4a9306b32d36e92d524683ad2299
  - path: /home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json
    sha256: e0344ee18471ba306f65544cbca98cb5242bb8702b81f7ae477c585b99bdbe0a
  - path: /home/zephryj/turingos_backup/work/turing/pack/04_registries/price_table_m1c_20260702.json
    sha256: 84f1c8291162cd6ca990a571f4e887c5e96821d658c0a8db402598fcb696db72
  - path: /home/zephryj/turingos_backup/work/turing/crates/turing-pput/src/lib.rs
    sha256: 0a1954f954db4d1cdc300aab061d82fd37b461778d45db6dc69c7b333c030e27
  - path: /home/zephryj/turingos_backup/work/turing/crates/turing-daemons/src/lib.rs
    sha256: 4684e08611a6c9f1d589d9278ae8291e75c210ef19fca3684e53e4b1fa6b8045
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1C_FRESH_CONTEXT_VERIFIER.json
    sha256: 559adb8b6d4bbf30e4e099fa0fc3a6c57db770510426ec2f43ec86f63a165133
status_ceiling: ADDRESSED
```

## Context

RES_M1 found that worker receipts carried only short worker IDs and that cost events used token estimates with no source boundary. A word-count pseudo-estimate cannot support H-VPPUT or worker-uplift claims, and DeepSeek cache-hit/cache-miss tokens must be distinct because they price differently.

The M1c schema must be codec-legal: ASCII keys, no floats, integer micro-USD only, no secrets, and provider receipts stored supervisor-side rather than in worker-visible packets.

## Decision

Adopt `turingos.cost_event.v2` as the forward CostEvent payload schema at the WorkerAdapter seam. The payload binds:

- `receipt_id`, `run_id`, and `capsule_id`.
- required run dimensions: `problem_id`, `split`, `agent_id`, and `branch_id`.
- `worker.adapter_kind`, provider, requested/resolved model IDs, endpoint, request ID, and response digest.
- provider usage integers plus `provider_usage_raw_sha256`; DeepSeek requires both `prompt_cache_hit_tokens` and `prompt_cache_miss_tokens`.
- `cost.cost_source_kind` in `{provider_receipt_inline, provider_usage_api_reconciled, bounded_estimate, fixture}`.
- integer `cost_microusd`, `price_table_digest`, and `bound_kind` when `cost_source_kind` is `bounded_estimate`.

The event registry row for `CostEvent` points to `turingos.cost_event.v2`. `tools/bench/audit_micro_tape_decision_dag.py --require-cost-provenance` fails non-v2 or malformed cost events, missing/unspecified source kinds, unbounded estimates, and `cost_microusd` conservation mismatches. Rust PPUT serializes v2 CostEvents while retaining non-serialized token fields for internal accounting. This ADR addresses the schema and local seam implementation; the M1c phase gate remains blocked until a durable real provider receipt-bearing tape segment exists.

## Consequences

Future strict M1/M3/M4 tapes can distinguish billing-complete receipts from bounded estimates and fixtures. CLI workers that hide usage must be labeled `bounded_estimate`; word-count estimates are forbidden as cost provenance. Native API measured arms should prefer `provider_receipt_inline`.

The pinned price table in this increment is a schema-anchor/fixture table, not a billing-complete current provider price authority. This ADR does not claim a real provider call, billing-complete M1.G, M3 preregistration freeze, external verification, constitution-byte change, OG-10/genesis signature, M2 enablement, CLOSED, RELEASED, RATIFIED, or SHIPPED status.
