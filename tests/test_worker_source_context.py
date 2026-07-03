from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools/bench/materialize_worker_source_context.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("worker_source_context", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_materializes_context_and_apply_snapshot_from_candidate_paths(tmp_path):
    tool = load_tool()
    root = tmp_path / "campaign"
    task_id = "org__repo-1"
    safe_dir = root / "shards/S00/ipqc/S00-W00/worker_safe_tasks" / task_id
    task_dir = root / "shards/S00/tasks" / task_id
    safe_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (safe_dir / "task_packet.json").write_text(
        json.dumps(
            {
                "instance_id": task_id,
                "repo": "org/repo",
                "base_commit": "abc123",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (safe_dir / "worker_capsule.md").write_text("# capsule\n", encoding="utf-8")
    (root / "shards/S00/ipqc/S00-W00/worker_safe_tasks/worker_safe_tasks_report.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "tasks": [
                    {
                        "instance_id": task_id,
                        "worker_capsule_path": str((safe_dir / "worker_capsule.md").relative_to(root)),
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "candidate.patch").write_text(
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n",
        encoding="utf-8",
    )
    source_cache = tmp_path / "source_cache"
    source_file = source_cache / "org__repo/abc123/pkg/mod.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("old\n", encoding="utf-8")

    report = tool.materialize(
        root=root,
        shard="S00",
        window="S00-W00",
        source_cache_dir=source_cache,
    )

    assert report["status"] == "PASS"
    context_path = safe_dir / "source_context.md"
    snapshot_path = root / "shards/S00/ipqc/S00-W00/source_snapshots" / task_id / "pkg/mod.py"
    assert "pkg/mod.py" in context_path.read_text(encoding="utf-8")
    assert snapshot_path.read_text(encoding="utf-8") == "old\n"
    assert report["tasks"][0]["source_context_sha256"].startswith("sha256:")
