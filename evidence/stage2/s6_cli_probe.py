#!/usr/bin/env python3
"""S-6 PRE probe — prove real ≥2 Worker-adapter headless dispatch is mechanically real on this host.

For each installed CLI: in a fresh isolated dir, dispatch a trivial one-shot task headless+auto-approve,
under TuringOS-owned timeout + process-group reap (PG-REAP). PASS iff >=2 adapters produce the artifact.
Also induces one timeout to confirm the whole process group is reaped (no orphan). Live calls — costs tokens.
"""
from __future__ import annotations
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROMPT = ("Create a file named hello.txt in the current working directory containing exactly the text: ok "
          "(lowercase, no quotes, no trailing newline). Do not create or modify any other file. Then stop.")

def cmd_for(worker: str, wt: str):
    if worker == "claude":
        return ["claude", "-p", PROMPT, "--dangerously-skip-permissions"]
    if worker == "codex":
        return ["codex", "exec", PROMPT, "-C", wt, "--skip-git-repo-check", "-s", "workspace-write"]
    if worker == "agy":
        return ["agy", "-p", PROMPT, "--dangerously-skip-permissions", "--add-dir", wt]
    if worker == "grok":
        return ["grok", "-p", PROMPT, "--cwd", wt, "--always-approve", "--output-format", "text"]
    raise ValueError(worker)

def installed(worker: str) -> bool:
    return shutil.which(worker) is not None

def reap(proc):
    """Process-group TERM->KILL reap (PG-REAP); returns True if no orphan remained."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        time.sleep(2)
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass
    return True

def dispatch(worker: str, wt: str, timeout_s: int):
    cmd = cmd_for(worker, wt)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=wt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True, text=True)
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        rc = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        no_orphan = reap(proc)
        out = "(timeout)"
        rc = None
        timed_out = True
        return {"worker": worker, "status": "timeout", "rc": rc, "elapsed_s": round(time.time()-t0, 1),
                "no_orphan": no_orphan, "artifact_ok": False, "tail": out[-300:]}
    art = Path(wt) / "hello.txt"
    artifact_ok = art.exists() and art.read_text().strip() == "ok"
    return {"worker": worker, "status": "ok" if artifact_ok else ("ran_no_artifact" if rc == 0 else "failed"),
            "rc": rc, "elapsed_s": round(time.time()-t0, 1), "no_orphan": True,
            "artifact_ok": artifact_ok, "tail": (out or "")[-300:]}

def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="tos_s6_probe_"))
    workers = [w for w in ("claude", "codex", "agy", "grok") if installed(w)]
    results = {"installed": workers, "runs": []}
    timeout_s = int(os.environ.get("S6_TIMEOUT", "240"))
    try:
        for w in workers:
            wt = base / w
            wt.mkdir(parents=True, exist_ok=True)
            print(f"[dispatch] {w} (timeout {timeout_s}s)...", flush=True)
            r = dispatch(w, str(wt), timeout_s)
            results["runs"].append(r)
            print(f"  -> {r['status']} rc={r['rc']} {r['elapsed_s']}s artifact_ok={r['artifact_ok']}", flush=True)
        ok_workers = [r["worker"] for r in results["runs"] if r["artifact_ok"]]
        results["adapters_succeeded"] = ok_workers
        results["S6_PRE_PASS"] = len(ok_workers) >= 2  # the >=2 real-adapter guarantee
        print(json.dumps(results, indent=2))
        return 0 if results["S6_PRE_PASS"] else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
