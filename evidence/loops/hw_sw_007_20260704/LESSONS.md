# LESSONS — HW-SW-007..009

Two targeted reworks occurred during this loop, each caused by a
gate/predicate check being a literal string/byte match with no semantic
awareness of the surrounding artifact. One rework per cause, as required.

## Rework 1 — `jcs::parse_strict` rejecting a file's ordinary trailing newline

**Cause:** `crates/turing-attest/src/identity.rs` and `qt_quote.rs` both
reuse `turing_contracts::jcs::parse_strict` to reject non-ASCII object keys
(the reuse the CONTEXT/PREDICATE explicitly asked for, instead of
reimplementing the check). `parse_strict` also enforces the
`turingos.jcs.v1` canonical-envelope framing rule that forbids a trailing
newline — correct for canonical tape bytes, but `device_identity.json` and
the `fixtures/q_t_quote.*.json` files are ordinary on-disk JSON files that
end with a newline by convention. The first run of `cargo test -p
turing-attest identity` failed all three tests with
`Parse("turingos.jcs.v1: framing violation: trailing newline")` instead of
the expected outcomes.

**Fix:** both `parse()` functions now call
`jcs::parse_strict(text.trim_end_matches('\n'))` for the structural
non-ASCII-key check only; the actual typed decode
(`serde_json::from_str`) still runs against the untouched `text`. This
keeps the canonical-envelope discipline intact for anything that actually
enters tape while not forcing on-disk fixture/data files to omit their
trailing newline.

**Rule extracted:** when reusing a canonical-envelope-oriented parser
(`turingos.jcs.v1`) against a plain on-disk data/fixture file rather than a
live tape envelope, strip the one on-disk-convention artifact (trailing
newline) before the strict structural check, and let the typed decode see
the original bytes. Recipients: any future crate that reuses
`jcs::parse_strict` against non-tape JSON files (Phase 4+ device
enrollment records, Phase 6 receipt fixtures).

## Rework 2 — doc comments describing the "never panics" contract tripped PREDICATE G's own grep

**Cause:** `lib.rs`, `tpm.rs`, and `tee.rs` originally documented the P0
stub discipline with prose like "never `panic!`/`todo!`/`unimplemented!`".
PREDICATE's Mini-Recovery grep
(`grep -rn 'todo!\|unimplemented!\|panic!' crates/turing-attest/src/`) is a
plain string match with no comment-vs-code distinction, so these
*descriptions* of the constraint were themselves false-positive hits
against the same grep meant to prove the constraint holds in code.

**Fix:** reworded all three doc comments to state the constraint in prose
without the literal macro-with-bang substrings (e.g. "never panics and
never invokes an unfinished-code macro"). Re-ran the grep: clean.

**Rule extracted:** when a crate's own compliance-checking grep pattern
matches macro *names*, never spell those macro names literally (with the
trailing `!`) in that crate's doc comments, even to describe why they are
absent. Recipients: any future crate under a similar "no todo!/panic!/
unimplemented!" grep gate (Phase 4 tpm crate, Phase 7 tee crate, and any
other stub-discipline crate in this roadmap).

No same-cause double failure occurred; no pinned-file diff; no constitution
touch; no Cargo.lock package outside the toml-family allowlist; no panic
path found in `turing-attest`; `SimulatedAttestor` output is unambiguously
marked (`"simulated:"` prefix, asserted by test).
