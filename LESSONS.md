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
