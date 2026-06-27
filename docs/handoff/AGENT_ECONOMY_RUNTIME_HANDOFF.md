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
- `turingd` has a minimal Unix socket JSON-RPC health/read-only heads surface; full
  persistent project heads, append routes, predicate routing, and approval APIs remain pending.
- Daemon boundary binaries exist for marketd, pputd, viewd, mcp, and execd, but their
  long-running socket/RPC services remain pending.
- Operator project persistence and installed binary wiring remain pending.
