#!/usr/bin/env python3
"""WP-H5: escalation-threshold offline calibration (EXPLORATORY, zero API).

Spec-of-record (no other source authoritative for this script):
  - ADR-ECON-007-route-market-loop-remedy.md, Decision 5: "升级阈值由自有轨迹
    数据离线标定后以 ADR 增补钉死" (this script IS the offline calibration;
    it does not and cannot pin anything -- pinning is a future ADR addendum
    owned by the orchestrator).
  - RES_ROUTE_lockIn_remedy_design_20260710.md §2 L2.5 ("路线 Q 崩塌 ->
    softmax 自动重探;阈值文献无据 ... 用我们已有轨迹内部标定(开放问题->内部
    实验)") and §3 (open question: no literature-validated escalation
    threshold exists; falsified candidate numbers are blacklisted and are
    NOT read, imported, or referenced anywhere in this file).

Ceiling: ADDRESSED. Every number this script produces is tagged
EXPLORATORY in CALIBRATION_REPORT.json. This is a research/analysis
artifact, not a production threshold and not an agent-visible diagnostic
surface; it must not be wired verbatim into any F4-scanned channel.

Zero API / zero worker calls. Reads only already-committed run artifacts
under tools/econ_lab/runs/{stageA_20260707,stageBprime_20260708,
p3e3_20260709,fracflat_20260710,etransfer_20260710}/ -- i.e. exactly the
five run directories named in the WP-H5 task order. "smoke*" sub-arms
inside those directories are single-task smoke checks, not experiment
arms, and are excluded (documented under structure_map.excluded_arms).

=================== DATA STRUCTURE MAPPING (documented per redline) =======
Two committed-artifact generations were found across the 17 real arms
scanned (see --self-test / structure_map in the report for exact counts):

  GEN1_NESTED_DISPATCH (stageA_20260707 all 5 tau arms; stageBprime_20260708
  all 4 arms; p3e3_20260709 all 3 arms; fracflat_20260710 3 non-smoke arms;
  etransfer_20260710/A): verdict.json["tasks"][i] = {instance_id,
  domain_bucket, selected_arm, selected_lineage, dispatches: [ {..,
  settlement_verdict_resolved, worker_result_status, scoring_result:
  {outcome, harness_error_reason}} ]}. Empirically, across all 850 task
  records read by this script, len(dispatches) == 1 always (verified in
  --self-test): each committed task_run is a single terminal dispatch, not
  a multi-turn retry/edit loop. There is therefore NO within-task
  retry/edit-sequence data anywhere in these five runs -- see
  "unavailable" in the report.

  GEN2_FLAT_CREDIT (etransfer_20260710/T only): verdict.json["tasks"][i] =
  {task_index, domain_bucket, dispatch_arm, lineage,
  settlement_verdict_resolved, worker_result_status, scoring_status,
  live_split_verdict: {harness_error_reason}} -- flat, no "dispatches"
  wrapper, has an explicit task_index.

  task_runs/ on-disk generational drift (per-instance file present):
    stageA_20260707      tau_0, tau_inf: task_runs/<lineage>/{candidate.patch,
                          worker_receipt.json} only -- NO settlement.json.
                          tau_0p5/tau_1/tau_2: no task_runs/ dir at all.
    stageBprime_20260708  no task_runs/ dir for any arm.
    p3e3_20260709          task_runs/<instance>/settlement.json present for
                          every instance (mirrors verdict.json task entry,
                          plus an explicit task_index field).
    fracflat_20260710      task_runs/<instance>/settlement.json present
                          (same shape as p3e3).
    etransfer_20260710/A   task_runs/<instance>/settlement.json present.
    etransfer_20260710/T   task_runs/<instance>/depthk_task_record.json
                          (NOT settlement.json -- different filename,
                          same content as the verdict.json task entry).

  Because verdict.json["tasks"] is present and complete for all 17 arms
  (task_runs/ is not), this script reads verdict.json exclusively as the
  single source of truth. This was cross-validated (see --self-test) by
  comparing verdict.json task list order against the explicit task_index
  recorded in task_runs/*/settlement.json (p3e3 R/L/Z, fracflat
  FL/UU/BL) and task_runs/*/depthk_task_record.json (etransfer T): in
  every arm checked, verdict.json's task list order equals ascending
  task_index order, and this order is furthermore identical across all
  arms of the same run (stageA's 5 tau arms share one order; stageBprime's
  4 arms share one order; etransfer A's positional order equals T's
  task_index order). This is the empirical basis for using verdict.json
  list position as the dispatch-sequence proxy (ORDER_PROXY=positional)
  for the arms that carry no explicit task_index field.
=============================================================================

CODING DECISIONS (all EXPLORATORY, all documented in the report itself):
  D1. "Route" = (run_id, arm_label, domain_bucket, arm, lineage) -- i.e. a
      route is scoped to one market instance (one arm_label such as
      "tau_0" or "W"); routes are NOT merged across different market
      configurations, since those are different experimental conditions.
      The per-task instance_id is explicitly excluded from the route key
      (it is present in budget_suggestion.route_id in the raw data but
      that field is a task+route pairing id, not a reusable route id).
  D2. Attempt outcome ∈ {SUCCESS, FAIL, INDETERMINATE}:
        SUCCESS       settlement_verdict_resolved is True
        FAIL          settlement_verdict_resolved is False
        INDETERMINATE settlement_verdict_resolved is None (worker/harness
                       error pre-verdict, e.g. API_ERROR, SKIPPED_NO_PATCH)
      PRIMARY curve treats INDETERMINATE as FAIL (an escalation detector
      operationally never observes a verified success either way -- see
      ADR-ECON-007 Decision 2, detector is external to Q and reasons over
      the same "no confirmed success yet" signal). A ROBUSTNESS variant
      that excludes INDETERMINATE attempts from the sequence entirely is
      also computed and reported side by side so the reader can see
      whether the curve is sensitive to this choice.
  D3. "同一路线连续失败 k 次后最终成功" is measured within one run's own
      task stream for that route: at the position where a route's losing
      streak first reaches length k, we ask whether that route ever
      records a SUCCESS at any later position in the SAME run. This is
      right-censored at the end of each run -- a route whose losing streak
      is still open when the run's committed task list ends is counted as
      "no later success" even though a longer run might have flipped it.
      This censoring bias pushes P(final_success | streak=k) DOWN for
      larger k (fewer future attempts remain to recover in). See
      "limitations" in the report.
  D4. "失败编辑重复签名" (failure edit-signature repetition) is asked for
      literal per-edit signatures, which are UNAVAILABLE (see D_GEN1 above
      -- no multi-turn edit data exists in any of the 5 runs). As a
      documented PROXY, this script instead reports, for each losing
      streak of length >= 2, the rate at which consecutive FAIL/
      INDETERMINATE attempts on the same route repeat an identical
      (worker_result_status, scoring_outcome_or_status,
      harness_error_reason) signature, plus the overall signature
      histogram. This proxy is coarser than a literal edit-diff signature
      and is labeled PROXY_ROUTE_LEVEL, not EDIT_LEVEL, throughout.

Determinism: no wall-clock timestamps, no randomness, no unordered-dict
iteration in the output path (every grouping key is sorted explicitly
before serialization). Running this script twice against an unchanged
checkout must produce a byte-identical CALIBRATION_REPORT.json; this is
checked by `--self-test` (which also runs a small closed-form check of the
streak-checkpoint algorithm) and by running the script twice and diffing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUN_IDS = [
    "stageA_20260707",
    "stageBprime_20260708",
    "p3e3_20260709",
    "fracflat_20260710",
    "etransfer_20260710",
]
K_MAX = 5
MIN_N_FOR_TRUST = 10  # script-internal statistical-trust floor, not a B-区 econ constant
SCHEMA = "econ_lab.escalation_calibration.v1"


# --------------------------------------------------------------------------
# Loading + normalization
# --------------------------------------------------------------------------


def discover_arms(run_root: Path) -> dict[str, list[Path]]:
    """run_id -> sorted list of arm verdict.json paths (excludes *smoke* arms)."""
    out: dict[str, list[Path]] = {}
    for run_id in RUN_IDS:
        run_dir = run_root / run_id
        paths = []
        if run_dir.is_dir():
            for arm_dir in sorted(run_dir.iterdir()):
                if not arm_dir.is_dir():
                    continue
                if "smoke" in arm_dir.name:
                    continue
                vp = arm_dir / "verdict.json"
                if vp.exists():
                    paths.append(vp)
        out[run_id] = paths
    return out


def excluded_arms(run_root: Path) -> list[str]:
    excluded = []
    for run_id in RUN_IDS:
        run_dir = run_root / run_id
        if not run_dir.is_dir():
            continue
        for arm_dir in sorted(run_dir.iterdir()):
            if arm_dir.is_dir() and "smoke" in arm_dir.name:
                excluded.append(f"{run_id}/{arm_dir.name}")
    return excluded


def sha256_of(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def classify_task(task: dict) -> tuple[str, dict]:
    """Return (schema_generation, normalized_fields)."""
    if "dispatches" in task:
        dispatches = task.get("dispatches") or []
        dispatch = dispatches[-1] if dispatches else {}
        sr = dispatch.get("scoring_result") or {}
        norm = {
            "instance_id": task.get("instance_id"),
            "domain_bucket": task.get("domain_bucket"),
            "arm": task.get("selected_arm"),
            "lineage": task.get("selected_lineage"),
            "settlement_verdict_resolved": dispatch.get("settlement_verdict_resolved"),
            "worker_result_status": dispatch.get("worker_result_status"),
            "scoring_outcome_or_status": sr.get("outcome"),
            "harness_error_reason": sr.get("harness_error_reason"),
            "dispatch_count": len(dispatches),
        }
        return "GEN1_NESTED_DISPATCH", norm
    if "dispatch_arm" in task:
        lsv = task.get("live_split_verdict") or {}
        norm = {
            "instance_id": task.get("instance_id"),
            "domain_bucket": task.get("domain_bucket"),
            "arm": task.get("dispatch_arm"),
            "lineage": task.get("lineage"),
            "settlement_verdict_resolved": task.get("settlement_verdict_resolved"),
            "worker_result_status": task.get("worker_result_status"),
            "scoring_outcome_or_status": task.get("scoring_status"),
            "harness_error_reason": lsv.get("harness_error_reason"),
            "dispatch_count": 1,
        }
        return "GEN2_FLAT_CREDIT", norm
    raise ValueError(f"unrecognized task schema, keys={sorted(task.keys())}")


def outcome_of(settlement_verdict_resolved) -> str:
    if settlement_verdict_resolved is True:
        return "SUCCESS"
    if settlement_verdict_resolved is False:
        return "FAIL"
    return "INDETERMINATE"


def load_arm(run_id: str, arm_label: str, verdict_path: Path) -> dict:
    raw = json.loads(verdict_path.read_text(encoding="utf-8"))
    tasks = raw.get("tasks") or []
    records = []
    generations = set()
    multi_dispatch = 0
    for pos, task in enumerate(tasks):
        gen, norm = classify_task(task)
        generations.add(gen)
        if norm["dispatch_count"] > 1:
            multi_dispatch += 1
        outcome = outcome_of(norm["settlement_verdict_resolved"])
        signature = "|".join(
            str(x)
            for x in (
                norm["worker_result_status"],
                norm["scoring_outcome_or_status"],
                norm["harness_error_reason"],
            )
        )
        records.append(
            {
                "run_id": run_id,
                "arm_label": arm_label,
                "order_pos": pos,
                "instance_id": norm["instance_id"],
                "domain_bucket": norm["domain_bucket"],
                "arm": norm["arm"],
                "lineage": norm["lineage"],
                "outcome": outcome,
                "signature": signature,
            }
        )
    return {
        "run_id": run_id,
        "arm_label": arm_label,
        "verdict_sha256": sha256_of(verdict_path),
        "n_tasks": len(records),
        "schema_generations": sorted(generations),
        "multi_dispatch_tasks": multi_dispatch,
        "records": records,
    }


def route_key(rec: dict) -> tuple:
    return (rec["run_id"], rec["arm_label"], rec["domain_bucket"], rec["arm"], rec["lineage"])


def group_routes(records: list[dict]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        groups[route_key(rec)].append(rec)
    for k in groups:
        groups[k].sort(key=lambda r: r["order_pos"])
    return groups


# --------------------------------------------------------------------------
# Escalation checkpoint statistics
# --------------------------------------------------------------------------


def is_fail(outcome: str, *, treat_indeterminate_as_fail: bool) -> bool | None:
    """True=fail attempt, False=success attempt, None=drop from sequence."""
    if outcome == "SUCCESS":
        return False
    if outcome == "FAIL":
        return True
    # INDETERMINATE
    if treat_indeterminate_as_fail:
        return True
    return None  # excluded from the sequence entirely (robustness variant)


def streak_checkpoints(
    route_records: list[dict], *, treat_indeterminate_as_fail: bool
) -> dict[int, tuple[int, int]]:
    """For one ordered route sequence, return {k: (successes_after, checkpoints)}."""
    seq = []
    for rec in route_records:
        v = is_fail(rec["outcome"], treat_indeterminate_as_fail=treat_indeterminate_as_fail)
        if v is None:
            continue
        seq.append(v)  # True = fail attempt at this position, False = success
    counters: dict[int, list[int]] = {k: [0, 0] for k in range(1, K_MAX + 1)}
    streak = 0
    n = len(seq)
    for i, failed in enumerate(seq):
        if failed:
            streak += 1
            if streak <= K_MAX:
                any_success_after = any(not s for s in seq[i + 1 :])
                counters[streak][1] += 1
                if any_success_after:
                    counters[streak][0] += 1
        else:
            streak = 0
    return {k: (v[0], v[1]) for k, v in counters.items()}


def wilson_interval(successes: int, n: int, z: float = 1.959963985) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return (round(max(0.0, lo), 6), round(min(1.0, hi), 6))


def build_curve(
    route_groups: dict[tuple, list[dict]], *, treat_indeterminate_as_fail: bool
) -> dict[str, dict]:
    totals = {k: [0, 0] for k in range(1, K_MAX + 1)}
    contributing_arms: dict[int, set] = {k: set() for k in range(1, K_MAX + 1)}
    for rk in sorted(route_groups.keys()):
        run_id, arm_label = rk[0], rk[1]
        cps = streak_checkpoints(
            route_groups[rk], treat_indeterminate_as_fail=treat_indeterminate_as_fail
        )
        for k, (succ, n) in cps.items():
            totals[k][0] += succ
            totals[k][1] += n
            if n > 0:
                contributing_arms[k].add(f"{run_id}/{arm_label}")
    out = {}
    for k in range(1, K_MAX + 1):
        succ, n = totals[k]
        p = round(succ / n, 6) if n > 0 else None
        out[f"k{k}"] = {
            "streak_len": k,
            "checkpoints_n": n,
            "eventual_success_count": succ,
            "p_final_success_given_streak": p,
            "wilson_95ci": wilson_interval(succ, n) if n > 0 else None,
            "trusted": n >= MIN_N_FOR_TRUST,
            "n_contributing_arms": len(contributing_arms[k]),
            "contributing_arms": sorted(contributing_arms[k]),
        }
    return out


def curve_trend(curve: dict[str, dict], *, min_n: int = MIN_N_FOR_TRUST) -> dict:
    """Classify the shape of a P(final_success|streak=k) curve over its
    trusted (checkpoints_n >= min_n) points only. Returns trend label + the
    points used. min_n is applied directly against checkpoints_n so callers
    can probe alternate trust floors; it is NOT read from the pre-computed
    'trusted' flag on the curve cell (that flag is always MIN_N_FOR_TRUST)."""
    points = []
    for k in range(1, K_MAX + 1):
        cell = curve[f"k{k}"]
        if cell["checkpoints_n"] >= min_n and cell["p_final_success_given_streak"] is not None:
            points.append((k, cell["p_final_success_given_streak"]))
    if len(points) < 2:
        return {"trend": "INSUFFICIENT_TRUSTED_POINTS", "points": points}
    diffs = [b - a for (_, a), (_, b) in zip(points, points[1:])]
    if all(d <= 0 for d in diffs) and any(d < 0 for d in diffs):
        trend = "NON_INCREASING"
    elif all(d == 0 for d in diffs):
        trend = "FLAT"
    elif all(d >= 0 for d in diffs) and any(d > 0 for d in diffs):
        trend = "NON_DECREASING"
    else:
        trend = "NON_MONOTONIC"
    return {"trend": trend, "points": points}


# --------------------------------------------------------------------------
# Failure-signature (PROXY_ROUTE_LEVEL) statistics
# --------------------------------------------------------------------------


def signature_stats(route_groups: dict[tuple, list[dict]]) -> dict:
    histogram: Counter = Counter()
    repeat_pairs = 0
    total_pairs = 0
    for rk in sorted(route_groups.keys()):
        recs = route_groups[rk]
        streak_sigs: list[str] = []
        for rec in recs:
            if rec["outcome"] == "SUCCESS":
                if len(streak_sigs) >= 2:
                    for a, b in zip(streak_sigs, streak_sigs[1:]):
                        total_pairs += 1
                        if a == b:
                            repeat_pairs += 1
                streak_sigs = []
                continue
            histogram[rec["signature"]] += 1
            streak_sigs.append(rec["signature"])
        if len(streak_sigs) >= 2:
            for a, b in zip(streak_sigs, streak_sigs[1:]):
                total_pairs += 1
                if a == b:
                    repeat_pairs += 1
    repeat_rate = round(repeat_pairs / total_pairs, 6) if total_pairs > 0 else None
    return {
        "granularity": "PROXY_ROUTE_LEVEL",
        "note": (
            "literal within-task edit-diff signatures are UNAVAILABLE in all "
            "5 runs (see docstring D_GEN1); this is a coarser route-level "
            "failure-category repeat rate across sequential dispatches of "
            "the same route"
        ),
        "consecutive_same_signature_pairs": repeat_pairs,
        "consecutive_fail_fail_pairs_total": total_pairs,
        "consecutive_repeat_rate": repeat_rate,
        "signature_histogram": dict(sorted(histogram.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


# --------------------------------------------------------------------------
# Threshold suggestion (EXPLORATORY only)
# --------------------------------------------------------------------------


def naive_below_half_rule(curve: dict) -> int | None:
    for k in range(1, K_MAX + 1):
        cell = curve[f"k{k}"]
        if not cell["trusted"]:
            continue
        p = cell["p_final_success_given_streak"]
        if p is not None and p < 0.5:
            return k
    return None


def suggest_threshold(
    merged_curve_primary: dict, by_arm_primary: dict[str, dict]
) -> dict:
    naive_rule = (
        "smallest k in 1..%d, restricted to checkpoints_n >= %d (MIN_N_FOR_TRUST), "
        "at which p_final_success_given_streak < 0.5 on the merged primary "
        "(INDETERMINATE=FAIL) pooled curve" % (K_MAX, MIN_N_FOR_TRUST)
    )
    naive_k = naive_below_half_rule(merged_curve_primary)
    merged_trend = curve_trend(merged_curve_primary)

    per_arm_trend = {arm: curve_trend(c) for arm, c in sorted(by_arm_primary.items())}
    trend_tally = Counter(v["trend"] for v in per_arm_trend.values())

    # elbow-at-k2: among arms with trusted k1 AND k2, does p drop (or stay flat)
    # at the 2nd consecutive failure vs the 1st?
    elbow_k2_drop = 0
    elbow_k2_no_drop = 0
    # looser, directional-only variant: require only checkpoints_n >= 1 at both
    # k1 and k2 (still labeled untrusted -- more arms qualify, less confidence
    # per arm, reported purely so the reader sees the full picture, not a
    # cherry-picked trusted-only subset).
    informal_drop = 0
    informal_no_drop = 0
    for arm, c in sorted(by_arm_primary.items()):
        c1, c2 = c["k1"], c["k2"]
        p1, p2 = c1["p_final_success_given_streak"], c2["p_final_success_given_streak"]
        if c1["checkpoints_n"] >= 1 and c2["checkpoints_n"] >= 1 and p1 is not None and p2 is not None:
            if p2 <= p1:
                informal_drop += 1
            else:
                informal_no_drop += 1
        if c1["trusted"] and c2["trusted"] and p1 is not None and p2 is not None:
            if p2 <= p1:
                elbow_k2_drop += 1
            else:
                elbow_k2_no_drop += 1

    recommendation = (
        "Merged pooled curve trend is %s; per-arm trend tally is %s. "
        "The merged pooled curve mixes market-configuration arms with very "
        "different baseline resolve rates (PER_DOMAIN_BUCKET arms ~0-4%% "
        "single-shot resolve rate vs GLOBAL_CONSTANT etransfer arms ~40-70%%), "
        "and different arms have data at different k (see contributing_arms "
        "per cell) -- an increasing merged curve at higher k is consistent "
        "with composition shift (Simpson's-paradox-style), not with retrying "
        "a failing route becoming more likely to pay off. The per-arm view is "
        "the more trustworthy read: %d/%d arms with a TRUSTED (n>=%d) k1 AND "
        "k2 checkpoint show p(final_success|streak=2) <= p(final_success|streak=1); "
        "loosening to any n>=1 at both (UNTRUSTED, directional only) widens "
        "this to %d/%d arms showing the same drop-or-flat pattern at the 2nd "
        "consecutive failure. Both readings point the same direction (early "
        "elbow around k=2 for the low-baseline PER_DOMAIN_BUCKET arms) but "
        "neither is a substitute for a larger, purpose-built calibration run. "
        "No arm in this dataset has enough trusted (n>=%d) checkpoints beyond "
        "k=3 to say anything about k=4 or k=5."
        % (
            merged_trend["trend"],
            dict(sorted(trend_tally.items())),
            elbow_k2_drop,
            elbow_k2_drop + elbow_k2_no_drop,
            MIN_N_FOR_TRUST,
            informal_drop,
            informal_drop + informal_no_drop,
            MIN_N_FOR_TRUST,
        )
    )

    return {
        "exploratory": True,
        "authoritative": False,
        "naive_merged_rule": {
            "rule": naive_rule,
            "suggested_k": naive_k,
            "status": "K_FOUND" if naive_k is not None else "NO_TRUSTED_K_BELOW_0.5",
            "caveat": (
                "This rule alone is MISLEADING here: the merged curve trend is "
                "%s over its trusted points, so 'first k below 0.5' mostly "
                "reflects the low unconditional base success rate at k=1, not "
                "a genuine decreasing elbow. See per_arm_analysis for the more "
                "defensible read." % merged_trend["trend"]
            ),
        },
        "merged_curve_trend": merged_trend,
        "per_arm_analysis": {
            "trend_tally": dict(sorted(trend_tally.items())),
            "per_arm_trend": per_arm_trend,
            "elbow_at_k2_drop_or_flat_count_TRUSTED": elbow_k2_drop,
            "elbow_at_k2_no_drop_count_TRUSTED": elbow_k2_no_drop,
            "elbow_at_k2_drop_or_flat_count_UNTRUSTED_ANY_N": informal_drop,
            "elbow_at_k2_no_drop_count_UNTRUSTED_ANY_N": informal_no_drop,
        },
        "recommendation_EXPLORATORY": recommendation,
        "caveat": (
            "NOT a production threshold. Per ADR-ECON-007 Decision 5, formal "
            "pinning of any escalation threshold requires an ADR addendum "
            "owned by the orchestrator; this field is input to that process, "
            "not a substitute for it. See also 'limitations.right_censoring' "
            "and 'limitations.small_n' for known biases -- no k beyond 2 is "
            "well-supported by this dataset."
        ),
    }


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


def build_report(run_root: Path) -> dict:
    arm_paths = discover_arms(run_root)
    excluded = excluded_arms(run_root)

    structure_map: dict[str, dict] = {}
    all_records: list[dict] = []
    arm_meta: list[dict] = []

    for run_id in RUN_IDS:
        structure_map[run_id] = {}
        for vp in arm_paths[run_id]:
            arm_label = vp.parent.name
            arm = load_arm(run_id, arm_label, vp)
            all_records.extend(arm["records"])
            arm_meta.append(
                {
                    "run_id": run_id,
                    "arm_label": arm_label,
                    "n_tasks": arm["n_tasks"],
                }
            )
            structure_map[run_id][arm_label] = {
                "verdict_sha256": arm["verdict_sha256"],
                "n_tasks": arm["n_tasks"],
                "schema_generations": arm["schema_generations"],
                "multi_dispatch_tasks": arm["multi_dispatch_tasks"],
                "order_source": "POSITIONAL_LIST_ORDER (cross-validated against "
                "explicit task_index in task_runs/ where available; see docstring)",
            }

    route_groups_all = group_routes(all_records)

    # merged / global curves
    merged_primary = build_curve(route_groups_all, treat_indeterminate_as_fail=True)
    merged_robust = build_curve(route_groups_all, treat_indeterminate_as_fail=False)

    # per-arm curves
    by_arm_primary: dict[str, dict] = {}
    by_arm_robust: dict[str, dict] = {}
    for run_id, arm_label in sorted((m["run_id"], m["arm_label"]) for m in arm_meta):
        key = f"{run_id}/{arm_label}"
        arm_records = [r for r in all_records if r["run_id"] == run_id and r["arm_label"] == arm_label]
        arm_route_groups = group_routes(arm_records)
        by_arm_primary[key] = build_curve(arm_route_groups, treat_indeterminate_as_fail=True)
        by_arm_robust[key] = build_curve(arm_route_groups, treat_indeterminate_as_fail=False)

    sig_stats_merged = signature_stats(route_groups_all)
    sig_stats_by_arm = {}
    for run_id, arm_label in sorted((m["run_id"], m["arm_label"]) for m in arm_meta):
        key = f"{run_id}/{arm_label}"
        arm_records = [r for r in all_records if r["run_id"] == run_id and r["arm_label"] == arm_label]
        sig_stats_by_arm[key] = signature_stats(group_routes(arm_records))

    outcome_counts = Counter(r["outcome"] for r in all_records)
    n_routes = len(route_groups_all)
    n_routes_with_fail = sum(
        1
        for recs in route_groups_all.values()
        if any(r["outcome"] in ("FAIL", "INDETERMINATE") for r in recs)
    )
    n_routes_len_ge2 = sum(1 for recs in route_groups_all.values() if len(recs) >= 2)

    total_multi_dispatch = sum(
        structure_map[run_id][arm]["multi_dispatch_tasks"]
        for run_id in structure_map
        for arm in structure_map[run_id]
    )

    report = {
        "schema": SCHEMA,
        "status_ceiling": "ADDRESSED",
        "exploratory": True,
        "not_agent_visible": True,
        "spec_sources": [
            "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/adr/ADR-ECON-007-route-market-loop-remedy.md#Decision-5",
            "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_ROUTE_lockIn_remedy_design_20260710.md#2-L2.5",
            "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_ROUTE_lockIn_remedy_design_20260710.md#3",
        ],
        "input_runs": RUN_IDS,
        "excluded_arms_smoke": excluded,
        "structure_map": structure_map,
        "totals": {
            "n_arms_scanned": len(arm_meta),
            "n_task_records": len(all_records),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "n_distinct_routes": n_routes,
            "n_routes_with_any_non_success": n_routes_with_fail,
            "n_routes_with_2plus_attempts": n_routes_len_ge2,
            "multi_dispatch_tasks_total": total_multi_dispatch,
        },
        "coding_decisions": [
            "D1: route_key = (run_id, arm_label, domain_bucket, arm, lineage); "
            "routes are never merged across different market-configuration arms "
            "in the 'by_arm' views (only in the 'merged' pooled view).",
            "D2: outcome in {SUCCESS, FAIL, INDETERMINATE} from "
            "settlement_verdict_resolved in {True, False, None}; PRIMARY curve "
            "treats INDETERMINATE as FAIL, ROBUSTNESS curve excludes it from the "
            "attempt sequence.",
            "D3: 'final success' is right-censored at the end of each run's own "
            "committed task list -- see limitations.right_censoring.",
            "D4: failure-signature repetition is PROXY_ROUTE_LEVEL, not literal "
            "within-task edit-diff signatures, which are UNAVAILABLE in all 5 "
            "runs (dispatches list length is 1 for every one of the "
            f"{len(all_records)} task records read; multi_dispatch_tasks_total="
            f"{total_multi_dispatch}).",
        ],
        "unavailable": [
            "within-task retry/edit-sequence detail (all 5 runs, all 17 arms): "
            "every committed task_run is a single terminal dispatch "
            "(dispatch_mode=single_winner, len(dispatches)==1 always in "
            "GEN1_NESTED_DISPATCH; GEN2_FLAT_CREDIT has no dispatches list at "
            "all, one record per task). There is no literal multi-turn "
            "edit/retry trace to mine in any of these runs. This script "
            "therefore measures consecutive-failure streaks at the ROUTE level "
            "across the market's sequential task dispatches, not at the "
            "within-task edit-attempt level. See D3/D4 above.",
            "settlement.json missing for stageA_20260707 (all 5 tau arms; only "
            "tau_0/tau_inf even have a task_runs/ dir, and it holds no "
            "settlement.json) and for stageBprime_20260708 (no task_runs/ dir "
            "at all); outcome data for those 9 arms is sourced from "
            "verdict.json['tasks'][*]['dispatches'] instead (see structure_map).",
        ],
        "escalation_curve": {
            "definition": (
                "P(final_success | route has just reached k consecutive failed "
                "attempts), computed per route (see D1), then pooled (merged) "
                "or reported per market-configuration arm (by_arm)."
            ),
            "primary_indeterminate_as_fail": {
                "merged": merged_primary,
                "by_arm": by_arm_primary,
            },
            "robustness_indeterminate_excluded": {
                "merged": merged_robust,
                "by_arm": by_arm_robust,
            },
        },
        "failure_signature_distribution": {
            "merged": sig_stats_merged,
            "by_arm": sig_stats_by_arm,
        },
        "suggested_threshold_EXPLORATORY": suggest_threshold(merged_primary, by_arm_primary),
        "limitations": {
            "right_censoring": (
                "Each run's task stream is finite (~50 tasks per arm); a "
                "route's losing streak that is still open when the run's "
                "committed task list ends is scored as 'no eventual success' "
                "even though more dispatches (which none of these runs "
                "provide) might have flipped it. This biases "
                "p_final_success_given_streak downward for larger k, where "
                "fewer future attempts remain on average. Interpret k>=3 cells "
                "with checkpoints_n below MIN_N_FOR_TRUST "
                f"({MIN_N_FOR_TRUST}) as directional only, not trusted."
            ),
            "small_n": (
                "850 total task records across 17 arms split into up to "
                "8 domain buckets x 3-4 arms x 4 lineages routes means most "
                "routes receive very few sequential attempts within one run; "
                "high-k cells are frequently NOT_ENOUGH_DATA. See "
                "totals.n_routes_with_2plus_attempts."
            ),
            "falsified_numbers_excluded": (
                "No externally-sourced threshold candidate (e.g. any 'N "
                "failures -> escalate' literature number) was read, imported, "
                "or used anywhere in this script or its output, per the "
                "RES_ROUTE_lockIn_remedy_design_20260710.md blacklist."
            ),
            "route_scope": (
                "Routes are scoped per (run_id, arm_label); the same "
                "(domain_bucket, arm, lineage) route in two different market "
                "configurations (e.g. stageA tau_0 vs tau_inf) is treated as "
                "two independent route histories, never pooled together, "
                "because those arms are different experimental conditions."
            ),
        },
    }
    return report


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------


def self_test() -> int:
    # Hand-computed toy route: F F S F F F S (F=fail, S=success)
    toy = [
        {"outcome": "FAIL"},
        {"outcome": "FAIL"},
        {"outcome": "SUCCESS"},
        {"outcome": "FAIL"},
        {"outcome": "FAIL"},
        {"outcome": "FAIL"},
        {"outcome": "SUCCESS"},
    ]
    cps = streak_checkpoints(toy, treat_indeterminate_as_fail=True)
    # k=1 checkpoints: position0 (streak1, success after? yes -> pos2 S) ;
    #                  position3 (streak1 after reset, success after? yes -> pos6 S)
    assert cps[1] == (2, 2), cps[1]
    # k=2 checkpoints: position1 (streak2, success after? yes pos2) ;
    #                  position4 (streak2, success after? yes pos6)
    assert cps[2] == (2, 2), cps[2]
    # k=3 checkpoints: position5 only (streak3, success after? yes pos6)
    assert cps[3] == (1, 1), cps[3]
    assert cps[4] == (0, 0), cps[4]

    # Toy route with a losing streak open at the end (right-censored -> no success)
    toy2 = [{"outcome": "FAIL"}, {"outcome": "FAIL"}, {"outcome": "FAIL"}]
    cps2 = streak_checkpoints(toy2, treat_indeterminate_as_fail=True)
    assert cps2[1] == (0, 1), cps2[1]
    assert cps2[2] == (0, 1), cps2[2]
    assert cps2[3] == (0, 1), cps2[3]

    # INDETERMINATE handling: primary counts as fail, robustness drops it.
    toy3 = [
        {"outcome": "FAIL"},
        {"outcome": "INDETERMINATE"},
        {"outcome": "SUCCESS"},
    ]
    cps3_primary = streak_checkpoints(toy3, treat_indeterminate_as_fail=True)
    assert cps3_primary[2] == (1, 1), cps3_primary[2]
    cps3_robust = streak_checkpoints(toy3, treat_indeterminate_as_fail=False)
    # INDETERMINATE dropped -> sequence is [FAIL, SUCCESS] -> only k=1 checkpoint
    assert cps3_robust[1] == (1, 1), cps3_robust[1]
    assert cps3_robust[2] == (0, 0), cps3_robust[2]

    # wilson_interval sanity
    lo, hi = wilson_interval(5, 10)
    assert 0.0 <= lo < 0.5 < hi <= 1.0, (lo, hi)
    assert wilson_interval(0, 0) is None

    # classify_task on both schemas
    gen1_task = {
        "instance_id": "x",
        "domain_bucket": "d",
        "selected_arm": "armA",
        "selected_lineage": "kimi",
        "dispatches": [
            {
                "settlement_verdict_resolved": True,
                "worker_result_status": "COMPLETED",
                "scoring_result": {"outcome": "RESOLVED", "harness_error_reason": None},
            }
        ],
    }
    gen, norm = classify_task(gen1_task)
    assert gen == "GEN1_NESTED_DISPATCH"
    assert norm["settlement_verdict_resolved"] is True
    gen2_task = {
        "instance_id": "y",
        "domain_bucket": "global",
        "dispatch_arm": "armB",
        "lineage": "qwen",
        "settlement_verdict_resolved": False,
        "worker_result_status": "COMPLETED",
        "scoring_status": "COMPLETED",
        "live_split_verdict": {"harness_error_reason": "patch_apply_failed"},
    }
    gen2, norm2 = classify_task(gen2_task)
    assert gen2 == "GEN2_FLAT_CREDIT"
    assert norm2["harness_error_reason"] == "patch_apply_failed"

    # curve_trend classification
    def _mk_curve(ps: list[float | None], ns: list[int]) -> dict:
        return {
            f"k{i+1}": {
                "p_final_success_given_streak": p,
                "trusted": n >= MIN_N_FOR_TRUST,
                "checkpoints_n": n,
            }
            for i, (p, n) in enumerate(zip(ps, ns))
        }

    dec_curve = _mk_curve([0.5, 0.3, 0.1, None, None], [20, 15, 12, 0, 0])
    assert curve_trend(dec_curve)["trend"] == "NON_INCREASING"
    inc_curve = _mk_curve([0.1, 0.3, 0.5, None, None], [20, 15, 12, 0, 0])
    assert curve_trend(inc_curve)["trend"] == "NON_DECREASING"
    flat_curve = _mk_curve([0.2, 0.2, 0.2, None, None], [20, 15, 12, 0, 0])
    assert curve_trend(flat_curve)["trend"] == "FLAT"
    zigzag_curve = _mk_curve([0.1, 0.5, 0.1, None, None], [20, 15, 12, 0, 0])
    assert curve_trend(zigzag_curve)["trend"] == "NON_MONOTONIC"
    sparse_curve = _mk_curve([0.1, None, None, None, None], [20, 0, 0, 0, 0])
    assert curve_trend(sparse_curve)["trend"] == "INSUFFICIENT_TRUSTED_POINTS"

    print("self-test OK", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runs",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    report = build_report(args.run_root)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
