# Agent Economy Runtime Handoff

Status: generated private-local qualification handoff.

## Head Evidence

- tape_tip: mu:379179ede423a704251f1b8cbbcc792cdb5a1e2d5fdc0146cd8b80cedceaa398
- authorization_head: null
- accepted_head: mu:715540582923297095fda491b8e1c8b20d267ea1bb4c90824cfe911c7eefdb6b

## Projection Evidence

- market projection hash: sha256:b8530aabc6f28de2d0c6276dfcd4e0aafad1f1ed9670ebcdbcb2f24d2ca1365e
- wallet projection hash: sha256:829db7d6d2995a04a5c6824b9cecdd78257639240bc67d121a3f1604a098dd1a
- PPUT projection hash: sha256:dea7a1f755e46c6c2ba4b9516c0a1d01cd62066274d1db4863f95a3bc576f40a
- disposable projection hash: sha256:190e94d7940a03ab9383d70b3b5acdfd436851717b3ea6e90902c5a92cb550e5

## Replay And Audit Commands

```bash
cargo test --workspace
bash demo/demo_agent_economy_e2e.sh
bash demo/demo_rescue_agent_economy.sh
scripts/install-local.sh --prefix /tmp/turingos-local --profile debug
turing approval preview --approval-id ap_preview --authority-epoch 1 --action capsule_approve --subject wc_latest --risk P2 --evidence-digest sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --signature-route none
turing approval sign --key-id operator-local-key --approval-id ap_sign --authority-epoch 1 --action capsule_approve --subject wc_latest --risk P2 --evidence-digest sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb --signature-route os-keyring
turing replay --verify
turing market replay --verify
turing pput replay --verify
turing audit invariants
turing audit market
turing audit pput
turingd --check
turing-execd --check
turing-marketd --check
turing-pputd --check
turing-viewd --check
turing-mcp --check
turingd --serve --socket /tmp/turingd.sock
```

## Known Risks

- Generated evidence is from a temporary private-local qualification Tape.
- `turingd` has Unix socket JSON-RPC health/read-only heads, configured `--micro-git` head
  reads, goal submission, capsule dispatch approval/rejection, preserve-only append,
  predicate-routed candidate verify/write with an expanded CandidateAccepted predicate pack
  covering capsule/macro/worker/scope/budget/provenance/replay, minimal OS-keyring atom
  authorization, read-only ApprovalCard preview/sign UX, and read-only persistent project status.
  hardware-future route fails closed until a real hardware backend is wired.
- `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, and `turing-viewd` have
  minimal sidecar RPCs for grant authorization, fake worker dispatch, resource manifests, shadow
  budget suggestion, prompt shielding, disposable projection building, and read-only project
  status. `turing-viewd` also supports derived project-scoped projection snapshot write with
  `can_write_truth=false`; `turing-marketd` supports derived project-scoped market projection
  snapshot write with `price_not_truth=true`; `turing-pputd` supports hidden project-scoped
  PPUT projection snapshot write with `hidden_from_worker_prompt=true` and
  `raw_formula_exposed=false`. All sidecar snapshot writes are derived-only and cannot own truth.
