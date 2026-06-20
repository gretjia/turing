# Shipgate 3 — receipt (Stage 3: private local dogfood) + 1.0 RELEASE

**Date:** 2026-06-20 · **Result:** PASS · The loop runs on REAL atoms with REAL workers, human-routed integration.

## Dogfood result (`dogfood_result.json`)
3 real atoms through the full loop, one per real vendor at the **router fast tier**:
| atom | worker | tier | first-try | files_touched | result |
|---|---|---|---|---|---|
| factorial(n) | claude | fast | ✅ | mathx.py | accepted |
| slugify(s) (edge cases) | codex | fast | ✅ | strutil.py | accepted |
| parse_kv(text) (comments/blanks) | agy | fast | ✅ | parsekv.py | accepted |

- **first_attempt_pass_rate = 1.0** (3/3); failure_nodes = 0; all candidates in-scope; acceptance commands
  actually executed and passed (Predicate-gated, not worker-trusted).
- **S-7 on the dogfood tape:** replay rebuilds accepted_head ✅; two replays byte-equal ✅; handoff rebuild equal ✅.
- accepted = 3/3; q_t.active_goal populated; DOGFOOD_PASS = true.

## Empirical answer — "is fast tier good enough?"
Yes for these representative atoms: 100% first-attempt pass at fast tier across three vendors. And critically,
**correctness did not depend on it** — every candidate was gated by the deterministic Predicate (declared
tests + scope + isolation + anchor + replay), so a fast-tier miss would have failed-on-Tape and escalated
(fast→standard) on retry rather than corrupting accepted state.

## 1.0 RELEASE (Shipgate-3 exit criteria, plan §6.4)
1. The loop drove ≥1 real project's atoms through accept (and, in Stage 1, failure) paths on a real Tape. ✅
2. All GATE spikes green on real artifacts: S-1/S-2 (Stage 0), S-3/S-4/S-7 (Stage 1), S-6/S-5 (Stage 2),
   S-7 on the dogfood tape (Stage 3). `MANIFEST.sha256` recorded throughout. ✅
3. Honest scope declaration published (DEFER list as a visible 1.0 limitation register — `MILESTONE_REPORT.md`,
   App D §D.3). ✅
4. None of the seven 临时违宪 anti-patterns present (release audit clean across all stages). ✅
