# Next Contract: Stage16R Real Evaluator Bundles

Required next loop:

1. Do not rewrite existing Stage16R bundles.
2. For each Phase F repair target, run a fresh retry attempt that produces a worker-derived unified diff.
3. Run the batch evaluator with the recorded task manifest and real patch artifact.
4. Import official evaluator evidence into a fresh MicroTape bundle.
5. CandidateAccepted may occur only after official PASS.
6. MarketSettled, RewardDistributed, and final PPUTAccounted remain terminal-basis and preserve-only.
7. Public evidence must include candidate patch, test patch, apply logs, target test logs, command, environment digest, stdout/stderr digests, and bundle SHA.
8. Dataset `patch` / gold patch fields are forbidden as candidate patch sources.

Release rule:

```text
Phase G release remains blocked until audit_phase_f_evaluator_proof reports:
  status: PASS
  official_evaluator_executable_replay: true
  release_next_phase_g: true
```
