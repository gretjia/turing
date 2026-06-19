# BLOCKED — credentialed / human-gated steps (skip-and-log)

> Per CLAUDE.md: a step needing human credentials/decision is written here and **skipped**; the build
> continues with everything else buildable. BLOCKED stays BLOCKED until a human unblocks it.
> None of these is a Goal-Amendment; each is a credentialed gate.

| ID | Stage / spike | What is blocked | Credential / decision needed | Status |
|----|---------------|-----------------|------------------------------|--------|
| BLK-1 | Stage 2 / S-6 (QB-2) | Real ≥2 subscription Worker adapters (Claude Code + Codex/OpenCode) authenticated dispatch | Operator native login to ≥2 Worker CLIs (no credential bundling) | OPEN |
| BLK-2 | Stage 2 / S-5 | GitHub PR/CI MacroAdapter credentialed round-trip on a disposable repo | GitHub token w/ repo scope + `gh` authenticated; disposable repo authorization | OPEN |
| BLK-3 | Stage 3 | Dogfood against operator's real project | Depends on BLK-1 + BLK-2; a real GoalState + real repo | OPEN |
| BLK-4 | 1.x (not 1.0) | OS-keyring / hardware real signing backend | Keyring secrets | OPEN (out of 1.0 scope; seam only) |

**Single human input to unblock the credentialed path:** authorize the credentialed Worker (≥2 CLI logins) + the disposable-GitHub (token + repo) batch; confirm merge stays human-confirmed. Everything before Stage 2 is buildable now with the fake/manual Worker.
