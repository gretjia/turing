# ADR-0008 — Worker CLI invocation: headless one-shot (not the agent protocol)

**Status:** Accepted (Stage 2). **Layer:** 4/5 (ordinary execution + code; per ADR-WORKER-001). **Seam:** `WorkerAdapter`.

## Context
1.0 needs ≥2 real subscription Worker adapters behind one stable seam (S-6), each producing a candidate in an
isolated worktree with an adapter-agnostic receipt, under TuringOS-owned timeout/kill/retry (PG-REAP).
Installed + authenticated CLIs (operator native login, no credential bundling): **claude, codex, agy, grok** (+ `gh`).

Each offers a non-interactive headless mode; grok additionally can run as an agent-protocol/MCP server.

## Decision
**Use headless one-shot mode for ALL adapters** — never the agent protocol in 1.0:
| Worker | Invocation (cwd = isolated worktree) |
|---|---|
| claude | `claude -p "<prompt>" --dangerously-skip-permissions [--output-format json]` |
| codex  | `codex exec "<prompt>" -C <wt> --skip-git-repo-check -s workspace-write [--json]` |
| agy    | `agy -p "<prompt>" --dangerously-skip-permissions [--add-dir <wt>]` |
| grok   | `grok -p "<prompt>" --cwd <wt> --always-approve --output-format plain` (valid: plain\|json\|streaming-json; `text` is INVALID — S-6 probe finding) |

(`--dangerously-skip-permissions` / `--always-approve` / `-s workspace-write` are SAFE here because the cwd is a
throwaway isolated Macro worktree — the candidate is confined and the Predicate re-checks scope/isolation.)

## Why headless one-shot, not agent protocol
1. The WorkerAdapter contract is **one capsule → one candidate** — a one-shot, not a long-lived session.
2. TuringOS owns **timeout/kill/retry + process-group reap**; a one-shot subprocess is cleanly reapable, an
   agent-protocol HTTP daemon is a long-running process that complicates kill/reap and adds a network surface.
3. The plan **defers the Agent Protocol server (HTTP) to 1.x** (App D §D.3) — using it now is over-build.
4. Uniform `-p`/exec shape → one adapter pattern → **adapter-agnostic receipts** (S-6 requirement).

## Smart dispatch router — model + effort tiering (cost control)
Each CLI defaults to the operator's OWN expensive tier (claude **opus-4.8 xhigh**; codex **gpt-5.5
model_reasoning_effort=high**). Dispatching `-p` unqualified burns tokens and is not the fast-worker strategy.
`src/turingos/dispatch_router.py` picks model+effort PER TASK, **fast by default**, escalating only on
signals (risk_class, allowed_files breadth ≥3/≥5, retry-after-failure). Per-CLI fast-tier levers:
| Worker | fast | deep |
|---|---|---|
| claude | `--model sonnet --effort low` | `--model opus --effort high` |
| codex | `-c model_reasoning_effort=low` | `-c model_reasoning_effort=high` |
| agy | `--model "Gemini 3.5 Flash (Low)"` | `--model "Gemini 3.1 Pro (High)"` |
| grok | `--model grok-composer-2.5-fast --effort low` | `--model grok-build --effort high` |
This is **layer-4 ordinary execution** (dispatch tuning), NOT vendor capability ranking — adapters stay
interchangeable (S-6). `CliWorkerAdapter` injects `dispatch_router.worker_flags(worker, select_tier(capsule))`.

## Consequences
- The WorkerAdapter seam still **admits** the agent protocol additively (1.x) — no rewrite.
- All adapters share a generic `CliWorkerAdapter` (command template + router-driven model/effort + receipt builder).
- No capability ranking; adapters interchangeable at the seam. The router tunes COST/EFFORT, not vendor choice.

## Constitution
Art. IV (dispatch); ADR-WORKER-001 (Worker = PROJECT role; Art. V.1.2 is ArchitectAI, not Worker).
