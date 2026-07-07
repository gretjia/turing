# External Auditor Prompt: Stage16R Real Evaluator Loop

Audit the exact pushed SHA and this evidence root.

Expected scoped verdict:

```text
stage16r_real_evaluator_status: PARTIAL
strict_microtape_replay: PASS
fresh_real_evaluator_bundle_count: 7
official_pass_count: 2
remaining_repair_count: 5
release_phase_f: NO
release_phase_g: NO
safe_to_publish_as_partial_loop_evidence: YES
```

Audit questions:

1. Do all seven fresh bundles exist and match `bundle_sha256s.txt`?
2. Does strict MicroTape audit report PASS while preserving failed progress zero?
3. Do exactly two targets have official PASS and `CandidateAccepted`?
4. Do the five failed targets avoid moving `accepted_head`?
5. Are worker patches worker-derived unified diffs where present?
6. Is this packet clear that Phase F and Phase G remain blocked?
7. Is there any dataset gold patch or official solution text in worker-visible
   prompts or candidate patch sources?
8. Does the correct next loop target only the five remaining repair tasks?
