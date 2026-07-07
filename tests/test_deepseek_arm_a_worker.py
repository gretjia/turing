from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from turingos import schemas


REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "tools" / "bench" / "run_deepseek_arm_a_worker.py"


def load_worker():
    spec = importlib.util.spec_from_file_location("deepseek_arm_a_worker", WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_extract_unified_diff_from_fenced_model_output():
    worker = load_worker()
    content = """Here is the patch:

```diff
diff --git a/pkg/mod.py b/pkg/mod.py
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -1 +1 @@
-old
+new
```

Done.
"""

    patch = worker.extract_unified_diff(content)

    assert patch.startswith("diff --git a/pkg/mod.py b/pkg/mod.py\n")
    assert "```" not in patch
    assert patch.endswith("\n")


def test_extract_unified_diff_normalizes_blank_hunk_context_lines():
    worker = load_worker()
    content = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1,3 +1,3 @@\n"
        " context\n"
        "\n"
        "-old\n"
        "+new\n"
    )

    patch = worker.extract_unified_diff(content)

    assert "\n \n-old\n+new\n" in patch


def test_extract_unified_diff_strips_standalone_fence_lines():
    worker = load_worker()
    content = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        " ```\n"
    )

    patch = worker.extract_unified_diff(content)

    assert "```" not in patch


def test_normalize_unified_diff_preserves_trailing_blank_context_line():
    worker = load_worker()
    patch = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1,3 +1,3 @@\n"
        " context\n"
        "-old\n"
        "+new\n"
        " \n"
    )

    normalized = worker.normalize_unified_diff(patch)

    assert normalized.endswith("+new\n \n")


def test_worker_request_disables_thinking_and_omits_sampling_knobs():
    worker = load_worker()

    payload = worker.build_worker_request(
        model="deepseek-v4-flash",
        capsule_text="# task\nFix it.",
        max_tokens=4096,
        thinking_type="disabled",
    )

    assert payload["model"] == "deepseek-v4-flash"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["stream"] is False
    assert payload["max_tokens"] == 4096
    assert payload["messages"][1]["content"].startswith("Your first characters must be: diff --git ")
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_worker_request_can_enable_thinking_with_reasoning_effort():
    worker = load_worker()

    payload = worker.build_worker_request(
        model="deepseek-v4-pro",
        capsule_text="# task\nFix it.",
        max_tokens=4096,
        thinking_type="enabled",
        reasoning_effort="high",
    )

    assert payload["model"] == "deepseek-v4-pro"
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_worker_visible_context_appends_source_context_file(tmp_path):
    worker = load_worker()
    capsule = tmp_path / "worker_capsule.md"
    capsule.write_text("# worker capsule\n", encoding="utf-8")
    source_context = tmp_path / "source_context.md"
    source_context.write_text("## Base source context\n```python\nold = 1\n```\n", encoding="utf-8")

    text, metadata = worker.load_worker_visible_context(
        capsule,
        source_context_name="source_context.md",
    )

    assert "# worker capsule" in text
    assert "## Base source context" in text
    assert metadata["source_context_path"] == str(source_context)
    assert metadata["source_context_sha256"].startswith("sha256:")


def test_worker_visible_context_appends_extra_context_file(tmp_path):
    worker = load_worker()
    capsule = tmp_path / "worker_capsule.md"
    capsule.write_text("# worker capsule\n", encoding="utf-8")
    extra_context = tmp_path / "path_hints.md"
    extra_context.write_text("Available source paths:\n- pkg/mod.py\n", encoding="utf-8")

    text, metadata = worker.load_worker_visible_context(
        capsule,
        extra_context_file=extra_context,
    )

    assert "# worker capsule" in text
    assert "Available source paths" in text
    assert metadata["extra_context_path"] == str(extra_context)
    assert metadata["extra_context_sha256"].startswith("sha256:")


def test_resolve_extra_context_file_prefers_instance_context_root(tmp_path):
    worker = load_worker()
    fallback = tmp_path / "fallback.md"
    fallback.write_text("fallback\n", encoding="utf-8")
    instance_context = tmp_path / "contexts/repo__task-1/extra_context.md"
    instance_context.parent.mkdir(parents=True)
    instance_context.write_text("instance-specific\n", encoding="utf-8")

    selected = worker.resolve_extra_context_file(
        instance_id="repo__task-1",
        extra_context_file=fallback,
        extra_context_root=tmp_path / "contexts",
    )
    fallback_selected = worker.resolve_extra_context_file(
        instance_id="repo__task-2",
        extra_context_file=fallback,
        extra_context_root=tmp_path / "contexts",
    )

    assert selected == instance_context
    assert fallback_selected == fallback


def test_load_existing_pass_result_summarizes_task_without_provider_call(tmp_path):
    worker = load_worker()
    task_dir = tmp_path / "tasks/repo__task-1"
    task_dir.mkdir(parents=True)
    patch_text = "diff --git a/pkg/mod.py b/pkg/mod.py\n"
    (task_dir / "candidate.patch").write_text(patch_text, encoding="utf-8")
    worker.write_json(
        task_dir / "worker_receipt.json",
        {
            "status": "COMPLETED",
            "model_reported": "deepseek-v4-pro",
            "candidate_patch_sha256": worker.sha256_text(patch_text),
            "cost_event": {"cost": {"cost_microusd": 123}},
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
    )
    worker.write_json(
        task_dir / "worker_candidate_audit.json",
        {"status": "PASS", "problems": []},
    )

    row = worker.load_existing_pass_result(instance_id="repo__task-1", task_dir=task_dir)

    assert row == {
        "instance_id": "repo__task-1",
        "status": "COMPLETED",
        "model_reported": "deepseek-v4-pro",
        "candidate_patch_sha256": worker.sha256_text(patch_text),
        "candidate_patch_bytes": len(patch_text.encode("utf-8")),
        "candidate_audit_status": "PASS",
        "candidate_audit_problems": [],
        "cost_microusd": 123,
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "reused_existing_passing_artifact": True,
    }


def test_main_reuses_existing_passing_artifacts_without_api_key(tmp_path, monkeypatch):
    worker = load_worker()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    root = tmp_path / "campaign"
    capsule = root / "shards/S01/ipqc/S01-W00/worker_safe_tasks/repo__task-1/worker_capsule.md"
    capsule.parent.mkdir(parents=True)
    capsule.write_text("# worker-safe capsule\n", encoding="utf-8")
    worker.write_json(
        root / "shards/S01/ipqc/S01-W00/worker_safe_tasks/worker_safe_tasks_report.json",
        {
            "status": "PASS",
            "tasks": [{"worker_capsule_path": str(capsule.relative_to(root))}],
        },
    )
    task_dir = root / "shards/S01/arms/C/tasks/repo__task-1"
    task_dir.mkdir(parents=True)
    patch_text = "diff --git a/pkg/mod.py b/pkg/mod.py\n"
    (task_dir / "candidate.patch").write_text(patch_text, encoding="utf-8")
    worker.write_json(
        task_dir / "worker_receipt.json",
        {
            "status": "COMPLETED",
            "model_reported": "deepseek-v4-pro",
            "candidate_patch_sha256": worker.sha256_text(patch_text),
            "cost_event": {"cost": {"cost_microusd": 0}},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
    )
    worker.write_json(task_dir / "worker_candidate_audit.json", {"status": "PASS", "problems": []})
    out = root / "summary.json"

    status = worker.main(
        [
            "--root",
            str(root),
            "--shard",
            "S01",
            "--window",
            "S01-W00",
            "--task-dir-root",
            str(root / "shards/S01/arms/C/tasks"),
            "--reuse-existing-passing",
            "--out",
            str(out),
        ]
    )

    summary = json.loads(out.read_text(encoding="utf-8"))
    assert status == 0
    assert summary["status"] == "PASS"
    assert summary["task_count_completed"] == 1
    assert summary["tasks"][0]["reused_existing_passing_artifact"] is True
    assert "missing_env" not in summary


def test_worker_visible_context_can_add_broadcast_section(tmp_path):
    worker = load_worker()
    capsule = tmp_path / "worker_capsule.md"
    capsule.write_text("# worker capsule\n", encoding="utf-8")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "rule_id": "br_format",
                        "failure_class": "PATCH_FORMAT",
                        "guidance": "Return a complete unified diff with hunk headers.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    rules = worker.load_broadcast_rules(rules_file)

    text, metadata = worker.load_worker_visible_context(
        capsule,
        broadcast_rules=rules,
        broadcast_rules_file=rules_file,
        broadcast_section_mode="always",
    )

    assert "# worker capsule" in text
    assert "BEGIN_TURINGOS_BROADCAST_RULES" in text
    assert "PATCH_FORMAT" in text
    assert metadata["broadcast_rule_count"] == 1
    assert metadata["broadcast_rule_ids"] == ["br_format"]
    assert metadata["broadcast_rules_path"] == str(rules_file)


def test_normalize_patch_against_source_recounts_applicable_hunks(tmp_path):
    worker = load_worker()
    source_root = tmp_path / "source"
    source_file = source_root / "pkg/mod.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("old\n", encoding="utf-8")
    patch = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-old\n"
        "+new\n"
    )

    normalized, info = worker.normalize_patch_against_source(patch, source_root)

    assert info["status"] == "RECOUNTED"
    assert normalized.startswith("diff --git a/pkg/mod.py b/pkg/mod.py\n")
    assert "@@ -1 +1 @@" in normalized


def test_worker_result_packet_has_cost_event_and_no_raw_model_text(tmp_path):
    worker = load_worker()
    root = tmp_path / "campaign"
    capsule = root / "shards/S02/ipqc/S02-W00/worker_safe_tasks/repo__task-1/worker_capsule.md"
    capsule.parent.mkdir(parents=True)
    capsule.write_text("# worker-safe capsule\n", encoding="utf-8")
    table = {
        "schema_id": "turingos.m3.price_table.v1",
        "models": [
            {
                "provider": "deepseek",
                "model_id": "deepseek-v4-flash",
                "input_cache_hit_microusd_per_mtok": 2800,
                "input_cache_miss_microusd_per_mtok": 140000,
                "output_microusd_per_mtok": 280000,
            }
        ],
    }
    request_payload = worker.build_worker_request(
        model="deepseek-v4-flash",
        capsule_text=capsule.read_text(encoding="utf-8"),
        max_tokens=256,
        thinking_type="disabled",
    )
    response = {
        "id": "chatcmpl-worker",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "message": {
                    "content": "diff --git a/pkg/mod.py b/pkg/mod.py\n--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1 +1 @@\n-old\n+new\n"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 90,
        },
    }

    packet = worker.build_worker_result_packet(
        root=root,
        shard="S02",
        window="S02-W00",
        instance_id="repo__task-1",
        model_requested="deepseek-v4-flash",
        request_payload=request_payload,
        response=response,
        response_raw=json.dumps(response, sort_keys=True),
        wall_time_ms=25,
        price_table=table,
        source_capsule_path=capsule,
        patch_text=worker.extract_unified_diff(response["choices"][0]["message"]["content"]),
    )

    assert packet["status"] == "COMPLETED"
    assert packet["candidate_source"] == "worker_derived"
    assert packet["submitted_patch_scope"] == "source_only"
    assert "worker-safe" in packet["integrity_statement"]
    assert "raw_model_content" not in json.dumps(packet, sort_keys=True)
    assert response["choices"][0]["message"]["content"] not in json.dumps(packet, sort_keys=True)
    schemas.validate_cost_event_v2(packet["cost_event"])


def test_worker_result_packet_can_stamp_m3_p5_confirmatory_labels(tmp_path):
    worker = load_worker()
    root = tmp_path / "campaign"
    capsule = root / "shards/S01/ipqc/S01-W00/worker_safe_tasks/repo__task-1/worker_capsule.md"
    capsule.parent.mkdir(parents=True)
    capsule.write_text("# worker-safe capsule\n", encoding="utf-8")
    table = {
        "schema_id": "turingos.m3.price_table.v1",
        "models": [
            {
                "provider": "deepseek",
                "model_id": "deepseek-v4-pro",
                "input_cache_hit_microusd_per_mtok": 3500,
                "input_cache_miss_microusd_per_mtok": 420000,
                "output_microusd_per_mtok": 840000,
            }
        ],
    }
    request_payload = worker.build_worker_request(
        model="deepseek-v4-pro",
        capsule_text=capsule.read_text(encoding="utf-8"),
        max_tokens=256,
        thinking_type="enabled",
        reasoning_effort="high",
    )
    response = {
        "id": "chatcmpl-worker",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {
                    "content": "diff --git a/pkg/mod.py b/pkg/mod.py\n--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1 +1 @@\n-old\n+new\n",
                    "reasoning_content": "private reasoning",
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 90,
        },
    }

    packet = worker.build_worker_result_packet(
        root=root,
        shard="S01",
        window="S01-W00",
        instance_id="repo__task-1",
        model_requested="deepseek-v4-pro",
        request_payload=request_payload,
        response=response,
        response_raw=json.dumps(response, sort_keys=True),
        wall_time_ms=25,
        price_table=table,
        source_capsule_path=capsule,
        patch_text=worker.extract_unified_diff(response["choices"][0]["message"]["content"]),
        source_context_metadata={
            "source_context_path": str(capsule.parent / "source_context.md"),
            "source_context_sha256": "sha256:" + "0" * 64,
            "source_context_length_chars": 128,
        },
        experiment_phase="m3-p5",
        run_id_prefix="m3-p5-arm-a",
        split_label="s01-confirmatory",
        agent_id="m3-p5-deepseek-arm-a-worker",
        branch_id="branch:m3-p5",
    )

    assert packet["experiment_phase"] == "m3-p5"
    assert packet["cost_event"]["run_id"] == "m3-p5-arm-a-S01-W00-deepseek-v4-pro"
    assert packet["cost_event"]["split"] == "s01-confirmatory"
    assert packet["cost_event"]["agent_id"] == "m3-p5-deepseek-arm-a-worker"
    assert packet["cost_event"]["branch_id"] == "branch:m3-p5"
    assert "source_context.md" in packet["integrity_statement"]
    assert "private reasoning" not in json.dumps(packet, sort_keys=True)
    schemas.validate_cost_event_v2(packet["cost_event"])


def test_worker_result_packet_can_stamp_loop_arm_metadata(tmp_path):
    worker = load_worker()
    root = tmp_path / "campaign"
    capsule = root / "shards/S01/ipqc/S01-W00/worker_safe_tasks/repo__task-1/worker_capsule.md"
    visible = root / "shards/S01/arms/B_deepseek_loop/capsules/repo__task-1/worker_visible_capsule.md"
    capsule.parent.mkdir(parents=True)
    visible.parent.mkdir(parents=True)
    capsule.write_text("# worker-safe capsule\n", encoding="utf-8")
    visible.write_text("# visible capsule\n", encoding="utf-8")
    table = {
        "schema_id": "turingos.m3.price_table.v1",
        "models": [
            {
                "provider": "deepseek",
                "model_id": "deepseek-v4-pro",
                "input_cache_hit_microusd_per_mtok": 3500,
                "input_cache_miss_microusd_per_mtok": 420000,
                "output_microusd_per_mtok": 840000,
            }
        ],
    }
    request_payload = worker.build_worker_request(
        model="deepseek-v4-pro",
        capsule_text=visible.read_text(encoding="utf-8"),
        max_tokens=256,
        system_role_label="weak SWE-bench worker under the TuringOS loop",
    )
    response = {
        "id": "chatcmpl-worker",
        "model": "deepseek-v4-pro",
        "choices": [{"message": {"content": "diff --git a/pkg/mod.py b/pkg/mod.py\n"}}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 90,
        },
    }

    packet = worker.build_worker_result_packet(
        root=root,
        shard="S01",
        window="S01-W00",
        instance_id="repo__task-1",
        model_requested="deepseek-v4-pro",
        request_payload=request_payload,
        response=response,
        response_raw=json.dumps(response, sort_keys=True),
        wall_time_ms=25,
        price_table=table,
        source_capsule_path=capsule,
        patch_text="diff --git a/pkg/mod.py b/pkg/mod.py\n",
        source_context_metadata={
            "broadcast_section_mode": "always",
            "broadcast_rule_count": 1,
            "broadcast_rule_ids": ["br_format"],
            "broadcast_section_sha256": "sha256:" + "1" * 64,
        },
        experiment_phase="m3-p6",
        run_id_prefix="m3-p6-arm-b",
        split_label="s01-loop-arm-b",
        agent_id="m3-p6-deepseek-loop-worker",
        branch_id="branch:m3-p6:B",
        arm_label="B",
        receipt_schema_id="turingos.m3.deepseek_loop_worker_receipt.v1",
        visible_capsule_path=visible,
        visible_capsule_sha256=worker.sha256_text(visible.read_text(encoding="utf-8")),
    )

    assert packet["schema_id"] == "turingos.m3.deepseek_loop_worker_receipt.v1"
    assert packet["arm_label"] == "B"
    assert packet["visible_capsule_path"] == "shards/S01/arms/B_deepseek_loop/capsules/repo__task-1/worker_visible_capsule.md"
    assert packet["broadcast_rule_ids"] == ["br_format"]
    assert packet["cost_event"]["branch_id"] == "branch:m3-p6:B"
    schemas.validate_cost_event_v2(packet["cost_event"])


def test_loop_run_summary_claim_boundary_uses_requested_arm_and_loop_flags():
    worker = load_worker()

    boundary = worker.build_claim_boundary(
        experiment_phase="m3-p6",
        shard="S01",
        arm_label="B",
        broadcast_section="always",
    )

    assert boundary == {
        "arm": "B",
        "pilot_only": False,
        "confirmatory_s01": False,
        "deepseek_only_source_context_loop": True,
        "has_failure_memory_broadcast": True,
        "no_uplift_result": True,
    }
