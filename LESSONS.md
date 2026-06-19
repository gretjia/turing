# LESSONS — abstract rules learned during the build

> One rule per gate failure (the Broadcast+Shield discipline applied to the build itself). Keep rules
> ABSTRACT (a FailureClass → rule), not raw logs. Inject only the relevant rule into the next module.

## Stage 0
- **L0-1 (codec/determinism):** For ASCII-only keys, Python `json.dumps(sort_keys=True, separators=(',',':'),
  ensure_ascii=True)` yields the same key order as RFC 8785 (UTF-16 code-unit order). The real `codec.py`
  MUST still implement full JCS number/string rules + the ascii-key/no-float guards — the spike shortcut is
  valid ONLY because keys are ASCII. *Why:* avoids a false sense that naive json==JCS in general.
- **L0-2 (refs):** `accepted_head` advances ONLY on SOVEREIGN_ACCEPT + Predicate PASS; never on commit
  success alone. The spike asserted advance only for ADVANCE events — the real kernel must additionally gate
  on `predicate_pass`. *Why:* prevents 临时违宪 #3 (predicate bypass).

## Foundation
- **LF-1 (tape, from audit FAIL→rework):** an ADVANCE (SOVEREIGN_ACCEPT) append MUST require
  `predicate_pass is True`; a failed accept is emitted as a `FailureNode`, never as a non-advancing
  SOVEREIGN_ACCEPT. *Why:* keeps "SOVEREIGN_ACCEPT on tape ⟺ accepted_head advanced", so replay rebuilds
  `accepted_head` Tape-only with no stored pass-flag. *How to apply:* every later module that emits an accept
  event passes `predicate_pass=True` only after a real Predicate PASS; otherwise emit FailureNode.
- **LF-2 (replay):** replay must recompute every `content_digest` and re-derive `head_effect` from the
  registry — never trust the envelope's carried values, never read a projection/sqlite. *How to apply:*
  the loop's reduce/panorama are derived views; the conservation test `view == derive_from_tape(tape)` holds.
- **LF-3 (build harness):** dependency-layered Workflow (barrier between layers) + frozen INTERFACES.md
  glossary made parallel module builds merge cleanly (eval "glossary beats swarm merge"). Adversarial audit
  caught the one real defect (tape). *How to apply:* keep INTERFACES.md the single source of API truth; never
  let an implementer change a frozen signature unilaterally.
