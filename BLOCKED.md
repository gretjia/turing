# BLOCKED — credentialed / human-gated steps

> **2026-06-20 — OPERATOR AUTHORIZATION RECEIVED (standing).** The operator logged in to **4 real Worker
> CLIs** (codex, agy, grok, claude — native login, no credential bundling) + `gh` (gretjia, repo+workflow
> scopes), and authorized: (a) run autonomously to the end of the project; (b) **all GitHub operations without
> further permission**; (c) merge=human-confirmed is satisfied by this standing authorization, recorded on the
> Tape as a HumanSteerInjected merge-authorization event. → **BLK-1, BLK-2, BLK-3 UNBLOCKED.**

| ID | Stage / spike | What was blocked | Status |
|----|---------------|------------------|--------|
| BLK-1 | Stage 2 / S-6 | Real ≥2 subscription Worker adapters | ✅ UNBLOCKED — claude/codex/agy/grok logged in (≥2 satisfied) |
| BLK-2 | Stage 2 / S-5 | GitHub PR/CI MacroAdapter round-trip | ✅ UNBLOCKED — `gh` authed (gretjia, repo+workflow); GitHub ops pre-authorized |
| BLK-3 | Stage 3 | Dogfood against a real repo | ✅ UNBLOCKED — proceed on the proven core |
| BLK-4 | 1.x (NOT 1.0) | OS-keyring / hardware real signing backend | OPEN — out of 1.0 loop-completeness scope (seam only); not required for the milestone |

**Best-practice CLI usage (researched — ADR-0008):** headless one-shot for all adapters (`claude -p`,
`codex exec`, `agy -p`, `grok -p --cwd`), NOT the agent protocol (deferred to 1.x; over-build for a one-shot
capsule→candidate, and harder to PG-reap). merge stays human-confirmed (standing authorization on the Tape).
