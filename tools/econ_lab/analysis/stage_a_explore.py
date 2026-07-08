#!/usr/bin/env python3
"""Stage A (E-price-tau) Phase A' exploratory data-mining pass.

EXPLORATORY — NOT CONFIRMATORY. This script mines already-completed Stage A
run artifacts (tools/econ_lab/runs/stageA_20260707/) for descriptive
patterns (A1-A6 below). It is a read-only, zero-spend pass over existing
JSON files: it makes no worker/API calls, runs no build step, and never
writes into `runs/`. Any hypothesis generated here (learning effects, route
base rates, calibration quality, exploration dividends, etc.) is purely
suggestive and REQUIRES NEW, PREREGISTERED DATA collected under a frozen
protocol (see PREREG_ECON_emergence_experiments_20260707.md and
tools/econ_lab/analysis/stage_a_readout.py, which is the frozen confirmatory
readout for the actual PREREG hypothesis) before it can be treated as
confirmed. Nothing in this file's output should be cited as a confirmatory
result, and p-values reported here (A1's McNemar test) are exploratory,
uncorrected for multiplicity across the 6 pairs, and must not be read as a
preregistered significance test.

ANALYTIC CHOICES (read this before disputing any number in EXPLORE_METRICS.json)
----------------------------------------------------------------------------
0. Tri-state outcome field. `dispatches[0].settlement_verdict_resolved` is
   NOT a plain boolean in the raw data: it is `true` (accept/pass), `false`
   (reject/fail), or `null` ("infra_null" -- the harness never reached a
   verdict, e.g. provider timeout, patch-apply failure before scoring,
   SKIPPED_NO_PATCH). This tri-state matches STAGE_A_READOUT.json's
   `arm_stats[*].infra_null` counts exactly (verified: 6/4/3/4/4 for
   tau_0/0p5/1/2/inf). Convention adopted EVERYWHERE in this script,
   matching STAGE_A_READOUT.json's own `n_settled`/`k_pass`/`rate` fields:
   `null` outcomes are EXCLUDED from every pass-rate numerator/denominator
   (n_settled = count of non-null outcomes only) and reported separately as
   an infra_null count wherever relevant. `null` is never coerced to
   False. This is a data-structure-forced deviation from a literal reading
   of the task spec (which assumed a plain boolean field).
1. Canary. `dispatches[0].live_split_verdict` is itself `null` exactly when
   `settlement_verdict_resolved` is null (verified, 0 mismatches across all
   5 arms x 50 tasks). Canary is therefore only defined when
   live_split_verdict is present; infra-null dispatches are never counted
   as canary occurrences (treated as canary=False for cross-tab purposes,
   since no verdict was ever reached).
2. Processing order. For tau_0 and tau_inf (no task_runs/*/settlement.json
   checkpoints exist), `verdict.json`'s `tasks[]` array order is trusted
   as-is. For tau_0p5/tau_1/tau_2, `task_runs/<instance_id>/settlement.json`
   `task_index` order is cross-checked against `tasks[]` array order; if
   they mismatch the task_index order is used and the mismatch is recorded
   in `meta.order_verification`. As actually run on this dataset, all three
   interior arms' orders matched (order_match=true for all three) -- see
   `meta.order_verification` in the output for the live cross-check result.
3. Half-split convention (used identically in A2/A3/A5): first half =
   floor(n/2) tasks in processing order, remainder (ceil(n/2)) to the
   second half.
4. A1 McNemar pairing. A pair (interior instance, extreme instance) is
   excluded from the 2x2 table if EITHER side's outcome is infra_null
   (cannot classify pass/fail); excluded instance_ids are listed per pair.
   All 5 arms in this dataset happen to share the identical 50-instance
   set, so `only_in_interior`/`only_in_extreme` are empty here, but the
   code does not assume that in general.
5. A1 exact McNemar formulas (implemented from scratch, no scipy): let
   n = b+c, m = min(b,c). Two-sided p = min(1, 2 * sum_{i=0}^{m} C(n,i)*0.5**n).
   One-sided p (testing whether interior beats extreme more often than the
   reverse, i.e. the b>c direction) = sum_{i=0}^{b} C(n,i)*0.5**n if b<c,
   else 1 - sum_{i=0}^{c-1} C(n,i)*0.5**n (standard binomial upper-tail via
   complement of the lower tail up to c-1; empty sum for c=0 is 0, giving
   p=1). If n=0 both p's are reported as null.
   CAVEAT (verified against actual data, not merely theoretical): this
   literal formula is directionally inconsistent with its own stated
   intent. Concretely, for tau_0p5_vs_tau_0, b=6, c=0 -- interior wins
   *all* 6 discordant pairs, the strongest possible evidence for "interior
   beats extreme" -- yet the literal formula (b>=c branch, c-1=-1, empty
   sum=0) evaluates to p_one=1.0, i.e. "no evidence whatsoever," which
   contradicts the data. The standard sign-test one-sided p-value for this
   same b,c would be P(Binomial(n,0.5) >= b) = 1 - sum_{i=0}^{b-1}
   C(n,i)*0.5**n = 0.015625 (strongly significant), matching intuition.
   The literal spec formula is implemented unmodified as the primary
   `p_one_sided_interior_favored` field (per "do not invent alternative
   formulas"), and the standard sign-test P(B>=b) formula is additionally
   reported per pair as
   `p_one_sided_interior_favored_standard_signtest_SUPPLEMENTARY` so this
   discrepancy is visible and usable rather than silently swallowed. This
   is flagged prominently in the final report to the requester as a
   probable spec-formula defect, not a data-quality issue.
6. A2 sliding window / half-rates over a tri-state sequence: a window's or
   half's "rate" is k_pass / n_settled restricted to non-null outcomes in
   that slice; n_settled and n_infra_null are reported alongside so a
   window with fewer than 10 "real" observations is visible, not hidden.
   The second-minus-first-half delta is explicitly labelled
   DESCRIPTIVE_ONLY_NO_SIGNIFICANCE in the JSON keys and must not be read
   as a hypothesis test.
7. A3 entropy/selection counts are computed purely from
   `selected_arm`/`selected_lineage` (route selection), which is fully
   defined for every task regardless of the tri-state outcome, so no
   infra_null handling is needed there.
8. A4 oracle -- literal-spec ambiguity, resolved by reporting BOTH readings.
   The task spec says: "Pool ALL 5 arms' task data together. For each of
   the 12 routes, compute pooled pass rate ... Oracle: for each
   domain_bucket, identify the single route with the highest pooled base
   rate FROM THE TABLE ABOVE." Read completely literally, "the table
   above" is the single GLOBAL 12-row route table (not bucket-scoped), so
   the same best route/rate would be picked for every domain_bucket,
   making the bucket-weighted oracle_upper_bound degenerate to exactly
   `oracle_best_global_route_rate`. This script reports that literal
   reading as the primary `oracle_upper_bound_weighted` /
   `arm_actual_vs_oracle_gap` fields (spec-exact, ties broken by
   lexicographically smallest (scaffold_arm,lineage) tuple). Because a
   bucket-invariant oracle is very likely not the intended analysis, this
   script ALSO computes a bucket-scoped variant (`route_table_by_bucket`,
   `oracle_upper_bound_bucket_scoped_supplementary`,
   `arm_actual_vs_oracle_gap_bucket_scoped_supplementary`) where each
   bucket's best route is chosen from a route table pooled ONLY over that
   bucket's own task-instances (still across all 5 arms), using the same
   tie-break rule. This supplementary metric is clearly namespaced/labeled
   as not literally required by the spec text.
9. A4 route n/k: n_settled/k_pass use the infra_null-excluded convention
   from (0); `n_total_selected_incl_infra_null` is reported alongside per
   route for transparency. Routes never selected anywhere have n=0,k=0,
   rate=null, and are still listed (all 12 always appear).
10. A5 replay (arm-local, per interior arm only). S/N counters are updated
    from a task's own outcome ONLY when that outcome is non-null;
    infra_null tasks leave S/N unchanged (their true outcome was never
    observed, so they carry no price signal) but Q_eff_before is still
    computed and still compared against `final_rate[route]` for THAT task
    (Q_eff_before depends only on prior state, not on this task's own
    unresolved outcome), so infra_null tasks are NOT dropped from the
    calibration-error series. `final_rate[route]` = route's settled S/N at
    the end of the arm's full processing sequence (arm-local ground truth,
    deliberately different from A4's cross-arm pooled rate per the task
    spec). If a route's final N is 0 (every selection of it was
    infra_null) its calibration error is reported as null for that task,
    per the spec's "skip/null if final_rate[route] has N=0" instruction.
11. A5 Spearman rho compares two monotonic-in-S-for-fixed-N transforms of
    the same (S_final, N_final) pair per route (Q_eff = (0.5+S)/(1+N) vs
    raw rate = S/N), restricted to routes with N_final>=1 in that arm. As
    the task spec itself anticipates, this typically yields rho near 1; it
    is reported anyway, unfiltered, exactly as specified. Spearman is
    implemented from scratch (average-rank tie handling), no scipy.
12. A6 minority-pick Q_eff is BUCKET-SCOPED (per (domain_bucket,
    scaffold_arm, lineage), reset per arm), which is a DELIBERATE and
    DIFFERENT scoping from A5's arm-global (route-only, not bucket-split)
    Q_eff. This is an adopted convention per the task spec's own
    instruction to scope A6 by domain_bucket. A "minority pick" requires
    the selected route to have been explored before in that bucket AND at
    least one OTHER already-explored route in that bucket to have strictly
    higher Q_eff_before at that moment; first-ever-in-bucket selections and
    unique-max selections are never minority. Pass-rate-among-minority /
    majority figures use the infra_null-excluded convention from (0);
    infra_null counts within each bucket are reported alongside.
13. A6 discovery events are listed for EVERY (arm, route) that ever achieved
    a first pass in that arm (not only those that happen to be minority
    picks); each entry carries `was_minority_pick` so both readings
    ("all discovery events" vs "discovery events driven by minority picks")
    are derivable from the same list.
14. A6 canary cross-tab: the spec nests this under an "interior arms only"
    heading but its own text explicitly asks for "per-arm matrices" and "a
    pooled-across-all-5-arms matrix" -- read literally, that overrides the
    section-level scope restriction for this one metric, so the canary
    cross-tab is computed over ALL 5 arms (both per-arm and pooled), not
    just the 3 interior arms.

Determinism: no `random`, no wall-clock reads, all dict/set iteration that
feeds output is sorted before use, JSON is written with `sort_keys=True`
and `indent=2` for byte-reproducible reruns.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants / canonical orderings
# ---------------------------------------------------------------------------

ARM_DIRS = ["tau_0", "tau_0p5", "tau_1", "tau_2", "tau_inf"]
INTERIOR = ["tau_0p5", "tau_1", "tau_2"]
EXTREME = ["tau_0", "tau_inf"]

SCAFFOLD_ARMS = ["armA", "armB", "armC"]
LINEAGES_CANON = ["deepseek", "qwen", "glm", "kimi"]  # verdict.json worker_lineages order

# Canonical route ordering: plain lexicographic sort of (scaffold_arm, lineage)
# tuples, per the spec's tie-break rule ("lexicographically smallest
# (scaffold_arm,lineage) tuple"). NOT the same order as LINEAGES_CANON.
ALL_ROUTES = sorted((a, l) for a in SCAFFOLD_ARMS for l in LINEAGES_CANON)


def route_key(a: str, l: str) -> str:
    return f"{a}::{l}"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def repo_base() -> Path:
    script_path = Path(__file__).resolve()
    econ_lab_dir = script_path.parent.parent
    return econ_lab_dir / "runs" / "stageA_20260707"


def load_arm_raw(base: Path, arm: str) -> dict:
    with open(base / arm / "verdict.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_settlement_order(base: Path, arm: str):
    """Return sorted list [(instance_id, task_index), ...] from
    task_runs/*/settlement.json, or None if no such checkpoints exist."""
    task_runs_dir = base / arm / "task_runs"
    if not task_runs_dir.is_dir():
        return None
    entries = []
    for sub in sorted(task_runs_dir.iterdir()):
        sf = sub / "settlement.json"
        if sf.is_file():
            with open(sf, "r", encoding="utf-8") as f:
                s = json.load(f)
            entries.append((s["instance_id"], s["task_index"]))
    if not entries:
        return None
    return sorted(entries, key=lambda e: e[0])


def load_arm_ordered_tasks(base: Path, arm: str):
    """Return (ordered_task_list, note_dict, raw_verdict_dict)."""
    raw = load_arm_raw(base, arm)
    tasks = raw["tasks"]
    tasks_order_ids = [t["instance_id"] for t in tasks]
    settlement_entries = get_settlement_order(base, arm)

    note = {"settlement_json_available": settlement_entries is not None}
    if settlement_entries is None:
        note["order_source"] = (
            "verdict.json tasks[] array order (no settlement.json "
            "checkpoints exist for this arm; trusted as-is per spec)"
        )
        note["order_match"] = None
        return tasks, note, raw

    idx_map = {iid: idx for iid, idx in settlement_entries}
    missing = [iid for iid in tasks_order_ids if iid not in idx_map]
    if missing:
        note["missing_settlement_files_for_instances"] = sorted(missing)
    settlement_true_order = [iid for iid, _ in sorted(idx_map.items(), key=lambda kv: kv[1])]
    match = tasks_order_ids == settlement_true_order
    note["order_match"] = match
    if match:
        note["order_source"] = (
            "verdict.json tasks[] array order (cross-checked against "
            "settlement.json task_index order: MATCH)"
        )
        return tasks, note, raw

    note["order_source"] = (
        "settlement.json task_index order (differs from verdict.json "
        "tasks[] array order; task_index used as ground truth per spec)"
    )
    by_id = {t["instance_id"]: t for t in tasks}
    reordered = [by_id[iid] for iid in settlement_true_order if iid in by_id]
    return reordered, note, raw


def task_outcome(task: dict):
    """True/False/None (None = infra_null)."""
    return task["dispatches"][0].get("settlement_verdict_resolved")


def task_canary(task: dict) -> bool:
    lsv = task["dispatches"][0].get("live_split_verdict")
    if lsv is None:
        return False
    return bool(lsv.get("canary"))


def task_route(task: dict):
    return task["selected_arm"], task["selected_lineage"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def half_split(seq):
    n = len(seq)
    half = n // 2
    return seq[:half], seq[half:]


def settled_stats(outcomes):
    """outcomes: iterable of True/False/None. Returns n_settled/k_pass/n_infra_null/rate."""
    outcomes = list(outcomes)
    settled = [o for o in outcomes if o is not None]
    k = sum(1 for o in settled if o)
    n = len(settled)
    return {
        "n_settled": n,
        "k_pass": k,
        "n_infra_null": len(outcomes) - n,
        "rate": (k / n if n > 0 else None),
    }


def shannon_entropy_bits(counts) -> float | None:
    total = sum(counts)
    if total == 0:
        return None
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


def rank_avg_ties(values):
    n = len(values)
    idx_sorted = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[idx_sorted[j + 1]] == values[idx_sorted[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[idx_sorted[k]] = avg_rank
        i = j + 1
    return ranks


def spearman_rho(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    rx = rank_avg_ties(xs)
    ry = rank_avg_ties(ys)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return cov / math.sqrt(var_x * var_y)


# ---------------------------------------------------------------------------
# A1 -- paired McNemar (interior vs extreme arms)
# ---------------------------------------------------------------------------


def binom_tail(n: int, k: int) -> float:
    """sum_{i=0}^{k} C(n,i) * 0.5**n ; empty sum (k<0) = 0.0"""
    if k < 0:
        return 0.0
    return sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)


def mcnemar_exact(b: int, c: int) -> dict:
    n = b + c
    if n == 0:
        return {
            "n_discordant": 0,
            "p_two_sided": None,
            "p_one_sided_interior_favored": None,
            "p_one_sided_interior_favored_standard_signtest_SUPPLEMENTARY": None,
        }
    m = min(b, c)
    # Two-sided: min(1, 2 * lower tail up to m), per spec.
    p_two = min(1.0, 2.0 * binom_tail(n, m))
    # One-sided, literal spec formula (see ANALYTIC CHOICES #5 for a verified
    # directional-inconsistency caveat on this exact formula).
    if b < c:
        p_one_literal = binom_tail(n, b)
    else:
        p_one_literal = 1.0 - binom_tail(n, c - 1)
    # Standard sign-test one-sided p-value for "interior favored" (b>c
    # direction): P(Binomial(n,0.5) >= b) = 1 - P(<= b-1). Reported as a
    # supplementary field, see ANALYTIC CHOICES #5.
    p_one_standard = 1.0 - binom_tail(n, b - 1)
    return {
        "n_discordant": n,
        "p_two_sided": p_two,
        "p_one_sided_interior_favored": p_one_literal,
        "p_one_sided_interior_favored_standard_signtest_SUPPLEMENTARY": p_one_standard,
    }


def phi_coefficient(a: int, b: int, c: int, d: int):
    denom_sq = (a + b) * (c + d) * (a + c) * (b + d)
    if denom_sq == 0:
        return None
    return (a * d - b * c) / math.sqrt(denom_sq)


def a1_mcnemar(arm_data: dict) -> dict:
    result = {}
    for i_arm in INTERIOR:
        for e_arm in EXTREME:
            i_map = {t["instance_id"]: task_outcome(t) for t in arm_data[i_arm]["tasks"]}
            e_map = {t["instance_id"]: task_outcome(t) for t in arm_data[e_arm]["tasks"]}
            common = sorted(set(i_map) & set(e_map))
            only_i = sorted(set(i_map) - set(e_map))
            only_e = sorted(set(e_map) - set(i_map))

            a = b = c = d = 0
            excluded_infra_null = []
            for iid in common:
                oi, oe = i_map[iid], e_map[iid]
                if oi is None or oe is None:
                    excluded_infra_null.append(iid)
                    continue
                if oi and oe:
                    a += 1
                elif oi and not oe:
                    b += 1
                elif (not oi) and oe:
                    c += 1
                else:
                    d += 1

            key = f"{i_arm}_vs_{e_arm}"
            result[key] = {
                "interior_arm": i_arm,
                "extreme_arm": e_arm,
                "n_instances_common": len(common),
                "only_in_interior": only_i,
                "only_in_extreme": only_e,
                "excluded_infra_null_instances": excluded_infra_null,
                "n_pairs_classified": a + b + c + d,
                "a_both_pass": a,
                "b_interior_pass_extreme_fail": b,
                "c_interior_fail_extreme_pass": c,
                "d_both_fail": d,
                "mcnemar_exact": mcnemar_exact(b, c),
                "phi_matched_pairs": phi_coefficient(a, b, c, d),
            }
    return result


# ---------------------------------------------------------------------------
# A2 -- temporal learning curve
# ---------------------------------------------------------------------------


def a2_learning_curve(arm_data: dict) -> dict:
    per_arm = {}
    for arm in ARM_DIRS:
        outcomes = [task_outcome(t) for t in arm_data[arm]["tasks"]]
        n = len(outcomes)
        first, second = half_split(outcomes)
        first_stats = settled_stats(first)
        second_stats = settled_stats(second)

        window = []
        for i in range(0, max(0, n - 10) + 1):
            window.append(settled_stats(outcomes[i : i + 10]))

        delta = None
        if first_stats["rate"] is not None and second_stats["rate"] is not None:
            delta = second_stats["rate"] - first_stats["rate"]

        per_arm[arm] = {
            "n": n,
            "first_half": first_stats,
            "second_half": second_stats,
            "second_minus_first_delta_DESCRIPTIVE_ONLY_NO_SIGNIFICANCE": delta,
            "sliding_window_10_in_order": window,
        }

    deltas_side_by_side = {
        arm: per_arm[arm]["second_minus_first_delta_DESCRIPTIVE_ONLY_NO_SIGNIFICANCE"]
        for arm in INTERIOR + ["tau_inf"]
    }

    return {
        "per_arm": per_arm,
        "learning_deltas_interior_vs_tau_inf_DESCRIPTIVE_ONLY_NO_SIGNIFICANCE": deltas_side_by_side,
        "note": (
            "second_minus_first deltas are purely descriptive point estimates; "
            "no significance/p-value claim is attached to them anywhere in this file."
        ),
    }


# ---------------------------------------------------------------------------
# A3 -- tau=0 lock-in dissection
# ---------------------------------------------------------------------------


def a3_lockin(arm_data: dict) -> dict:
    per_arm = {}
    for arm in ARM_DIRS:
        routes = [task_route(t) for t in arm_data[arm]["tasks"]]

        def counts_of(seq):
            c = {route_key(a, l): 0 for a, l in ALL_ROUTES}
            for a, l in seq:
                c[route_key(a, l)] += 1
            return c

        counts_whole = counts_of(routes)
        total = len(routes)
        max_count = max(counts_whole.values()) if total else 0
        top1_share = (max_count / total) if total > 0 else None

        first, second = half_split(routes)
        counts_first = counts_of(first)
        counts_second = counts_of(second)

        per_arm[arm] = {
            "selection_counts_by_route": counts_whole,
            "total_selections": total,
            "top1_route_share": top1_share,
            "entropy_bits_whole": shannon_entropy_bits(counts_whole.values()),
            "entropy_bits_first_half": shannon_entropy_bits(counts_first.values()),
            "entropy_bits_second_half": shannon_entropy_bits(counts_second.values()),
        }
    return per_arm


# ---------------------------------------------------------------------------
# A4 -- route base rates and oracle upper bound
# ---------------------------------------------------------------------------


def _best_route_from_table(route_table: dict):
    best_ali, best_rate = None, None
    for a, l in ALL_ROUTES:  # already lexicographically sorted -> deterministic tie-break
        rk = route_key(a, l)
        r = route_table[rk]["rate"]
        if r is None:
            continue
        if best_rate is None or r > best_rate:
            best_rate, best_ali = r, (a, l)
    return best_ali, best_rate


def a4_route_base_rates_and_oracle(arm_data: dict) -> dict:
    route_n = {route_key(a, l): 0 for a, l in ALL_ROUTES}
    route_k = {route_key(a, l): 0 for a, l in ALL_ROUTES}
    route_n_total = {route_key(a, l): 0 for a, l in ALL_ROUTES}
    bucket_weight: dict = {}

    # bucket-scoped (supplementary) tables: bucket -> route -> {n,k}
    bucket_route_n: dict = {}
    bucket_route_k: dict = {}

    for arm in ARM_DIRS:
        for t in arm_data[arm]["tasks"]:
            a, l = task_route(t)
            rk = route_key(a, l)
            bucket = t["domain_bucket"]
            outcome = task_outcome(t)

            route_n_total[rk] += 1
            bucket_weight[bucket] = bucket_weight.get(bucket, 0) + 1
            bucket_route_n.setdefault(bucket, {rk2: 0 for rk2 in route_n})
            bucket_route_k.setdefault(bucket, {rk2: 0 for rk2 in route_n})

            if outcome is None:
                continue
            route_n[rk] += 1
            bucket_route_n[bucket][rk] += 1
            if outcome:
                route_k[rk] += 1
                bucket_route_k[bucket][rk] += 1

    route_table = {
        route_key(a, l): {
            "n_settled": route_n[route_key(a, l)],
            "k_pass": route_k[route_key(a, l)],
            "n_total_selected_incl_infra_null": route_n_total[route_key(a, l)],
            "rate": (
                route_k[route_key(a, l)] / route_n[route_key(a, l)]
                if route_n[route_key(a, l)] > 0
                else None
            ),
        }
        for a, l in ALL_ROUTES
    }

    # --- literal-spec (global-table) oracle: ANALYTIC CHOICE 8 ---
    best_ali, best_rate = _best_route_from_table(route_table)
    per_bucket_oracle_literal = {}
    for bucket in sorted(bucket_weight):
        per_bucket_oracle_literal[bucket] = {
            "oracle_route": route_key(*best_ali) if best_ali else None,
            "oracle_rate": best_rate,
            "bucket_weight_task_instances": bucket_weight[bucket],
        }
    total_weight = sum(bucket_weight.values())
    if total_weight > 0 and best_rate is not None:
        oracle_upper_bound_literal = (
            sum(
                per_bucket_oracle_literal[b]["oracle_rate"]
                * per_bucket_oracle_literal[b]["bucket_weight_task_instances"]
                for b in per_bucket_oracle_literal
            )
            / total_weight
        )
    else:
        oracle_upper_bound_literal = None

    # --- supplementary bucket-scoped oracle: ANALYTIC CHOICE 8 ---
    route_table_by_bucket = {}
    per_bucket_oracle_scoped = {}
    for bucket in sorted(bucket_weight):
        bt = {
            route_key(a, l): {
                "n_settled": bucket_route_n[bucket][route_key(a, l)],
                "k_pass": bucket_route_k[bucket][route_key(a, l)],
                "rate": (
                    bucket_route_k[bucket][route_key(a, l)] / bucket_route_n[bucket][route_key(a, l)]
                    if bucket_route_n[bucket][route_key(a, l)] > 0
                    else None
                ),
            }
            for a, l in ALL_ROUTES
        }
        route_table_by_bucket[bucket] = bt
        b_ali, b_rate = _best_route_from_table(bt)
        per_bucket_oracle_scoped[bucket] = {
            "oracle_route": route_key(*b_ali) if b_ali else None,
            "oracle_rate": b_rate,
            "bucket_weight_task_instances": bucket_weight[bucket],
        }
    if total_weight > 0:
        weighted_terms = [
            per_bucket_oracle_scoped[b]["oracle_rate"] * per_bucket_oracle_scoped[b]["bucket_weight_task_instances"]
            for b in per_bucket_oracle_scoped
            if per_bucket_oracle_scoped[b]["oracle_rate"] is not None
        ]
        weight_terms = [
            per_bucket_oracle_scoped[b]["bucket_weight_task_instances"]
            for b in per_bucket_oracle_scoped
            if per_bucket_oracle_scoped[b]["oracle_rate"] is not None
        ]
        oracle_upper_bound_scoped = (sum(weighted_terms) / sum(weight_terms)) if weight_terms else None
    else:
        oracle_upper_bound_scoped = None

    arm_gaps_literal = {}
    arm_gaps_scoped = {}
    for arm in ARM_DIRS:
        outcomes = [task_outcome(t) for t in arm_data[arm]["tasks"]]
        s = settled_stats(outcomes)
        actual_rate = s["rate"]
        arm_gaps_literal[arm] = {
            "actual_pass_rate": actual_rate,
            "n_settled": s["n_settled"],
            "k_pass": s["k_pass"],
            "gap_actual_minus_oracle": (
                actual_rate - oracle_upper_bound_literal
                if actual_rate is not None and oracle_upper_bound_literal is not None
                else None
            ),
        }
        arm_gaps_scoped[arm] = {
            "actual_pass_rate": actual_rate,
            "n_settled": s["n_settled"],
            "k_pass": s["k_pass"],
            "gap_actual_minus_oracle": (
                actual_rate - oracle_upper_bound_scoped
                if actual_rate is not None and oracle_upper_bound_scoped is not None
                else None
            ),
        }

    return {
        "route_table_pooled_across_all_5_arms": route_table,
        "oracle_best_global_route": route_key(*best_ali) if best_ali else None,
        "oracle_best_global_route_rate": best_rate,
        "per_bucket_oracle_literal_spec": per_bucket_oracle_literal,
        "oracle_upper_bound_weighted": oracle_upper_bound_literal,
        "arm_actual_vs_oracle_gap": arm_gaps_literal,
        "note_degenerate_oracle": (
            "Per a literal reading of the spec text ('the table above'), the oracle "
            "route for every domain_bucket is chosen from the single GLOBAL pooled "
            "12-route table, not a bucket-scoped table; since that table does not "
            "vary by bucket, the same best route/rate is picked for every bucket, "
            "making oracle_upper_bound_weighted mathematically identical to "
            "oracle_best_global_route_rate. See ANALYTIC CHOICES #8 in the module "
            "docstring. A non-degenerate supplementary variant is provided below."
        ),
        "route_table_by_bucket_SUPPLEMENTARY": route_table_by_bucket,
        "per_bucket_oracle_bucket_scoped_SUPPLEMENTARY": per_bucket_oracle_scoped,
        "oracle_upper_bound_bucket_scoped_SUPPLEMENTARY": oracle_upper_bound_scoped,
        "arm_actual_vs_oracle_gap_bucket_scoped_SUPPLEMENTARY": arm_gaps_scoped,
    }


# ---------------------------------------------------------------------------
# A5 -- price discovery / calibration (Hayek check), interior arms only
# ---------------------------------------------------------------------------


def a5_price_discovery(arm_data: dict) -> dict:
    per_arm = {}
    for arm in INTERIOR:
        tasks = arm_data[arm]["tasks"]

        # Pass 1: final settled S/N per route over the whole arm.
        S_final = {route_key(a, l): 0 for a, l in ALL_ROUTES}
        N_final = {route_key(a, l): 0 for a, l in ALL_ROUTES}
        for t in tasks:
            rk = route_key(*task_route(t))
            outcome = task_outcome(t)
            if outcome is None:
                continue
            N_final[rk] += 1
            if outcome:
                S_final[rk] += 1
        final_rate = {rk: (S_final[rk] / N_final[rk] if N_final[rk] > 0 else None) for rk in S_final}

        # Pass 2: replay in processing order.
        S = {rk: 0 for rk in S_final}
        N = {rk: 0 for rk in S_final}
        errors = []
        for idx, t in enumerate(tasks):
            rk = route_key(*task_route(t))
            q_eff_before = (0.5 + S[rk]) / (1 + N[rk])
            fr = final_rate[rk]
            err = abs(q_eff_before - fr) if fr is not None else None
            errors.append(
                {
                    "task_order_index": idx,
                    "route": rk,
                    "q_eff_before": q_eff_before,
                    "final_rate_in_arm": fr,
                    "abs_calibration_error": err,
                }
            )
            outcome = task_outcome(t)
            if outcome is not None:
                if outcome:
                    S[rk] += 1
                N[rk] += 1
            # infra_null (outcome is None): S,N left unchanged -- ANALYTIC CHOICE #10.

        first_e, second_e = half_split(errors)

        def mean_err(seq):
            vals = [e["abs_calibration_error"] for e in seq if e["abs_calibration_error"] is not None]
            return {
                "n": len(vals),
                "n_skipped_null_final_rate": len(seq) - len(vals),
                "mean_abs_calibration_error": (sum(vals) / len(vals) if vals else None),
            }

        routes_with_data = sorted(rk for rk in S_final if N_final[rk] >= 1)
        q_eff_end = [(0.5 + S_final[rk]) / (1 + N_final[rk]) for rk in routes_with_data]
        raw_rate_end = [S_final[rk] / N_final[rk] for rk in routes_with_data]
        rho = spearman_rho(q_eff_end, raw_rate_end)

        per_arm[arm] = {
            "n_tasks": len(tasks),
            "first_half_calibration": mean_err(first_e),
            "second_half_calibration": mean_err(second_e),
            "per_task_detail_in_order": errors,
            "end_of_run_route_table": {
                rk: {
                    "S_final": S_final[rk],
                    "N_final": N_final[rk],
                    "q_eff_end": (0.5 + S_final[rk]) / (1 + N_final[rk]),
                    "raw_rate_end": final_rate[rk],
                }
                for rk in sorted(S_final)
            },
            "spearman_rho_qeff_vs_rawrate": rho,
            "spearman_n_routes_with_data": len(routes_with_data),
            "spearman_note": (
                "Q_eff and raw rate are both monotonic-in-S (for fixed N) functions "
                "of the same (S_final,N_final) pair, so rho near 1 is expected; "
                "reported unfiltered per spec, not skipped."
            ),
        }
    return per_arm


# ---------------------------------------------------------------------------
# A6 -- exploration dividend, discovery events, canary cross-tab
# ---------------------------------------------------------------------------


def a6_exploration_and_canary(arm_data: dict) -> dict:
    # Canary cross-tab: all 5 arms (ANALYTIC CHOICE #14), lineage x scaffold_arm.
    canary_matrix_per_arm = {}
    canary_matrix_pooled = {l: {a: 0 for a in SCAFFOLD_ARMS} for l in LINEAGES_CANON}
    for arm in ARM_DIRS:
        cm = {l: {a: 0 for a in SCAFFOLD_ARMS} for l in LINEAGES_CANON}
        for t in arm_data[arm]["tasks"]:
            if task_canary(t):
                a, l = task_route(t)
                cm[l][a] += 1
                canary_matrix_pooled[l][a] += 1
        canary_matrix_per_arm[arm] = cm

    per_arm_exploration = {}
    discovery_events = []

    for arm in INTERIOR:
        tasks = arm_data[arm]["tasks"]
        # (bucket, route_key) -> [S, N], created lazily on first selection.
        SN: dict = {}

        minority_count = 0
        minority_settled_n = 0
        minority_settled_k = 0
        minority_infra_null = 0
        majority_settled_n = 0
        majority_settled_k = 0
        majority_infra_null = 0
        route_first_pass_seen: set = set()

        for idx, t in enumerate(tasks):
            bucket = t["domain_bucket"]
            rk = route_key(*task_route(t))
            key = (bucket, rk)
            sel_S, sel_N = SN.setdefault(key, [0, 0])
            q_eff_selected = (0.5 + sel_S) / (1 + sel_N)
            was_previously_seen = sel_N >= 1

            is_minority = False
            if was_previously_seen:
                for (b2, rk2), (s2, n2) in SN.items():
                    if b2 != bucket or rk2 == rk:
                        continue
                    if n2 >= 1:
                        q2 = (0.5 + s2) / (1 + n2)
                        if q2 > q_eff_selected:
                            is_minority = True
                            break

            outcome = task_outcome(t)
            if is_minority:
                minority_count += 1
                if outcome is None:
                    minority_infra_null += 1
                else:
                    minority_settled_n += 1
                    if outcome:
                        minority_settled_k += 1
            else:
                if outcome is None:
                    majority_infra_null += 1
                else:
                    majority_settled_n += 1
                    if outcome:
                        majority_settled_k += 1

            if outcome is True and rk not in route_first_pass_seen:
                route_first_pass_seen.add(rk)
                discovery_events.append(
                    {
                        "arm": arm,
                        "route": rk,
                        "instance_id": t["instance_id"],
                        "task_order_index": idx,
                        "was_minority_pick": is_minority,
                    }
                )

            if outcome is not None:
                if outcome:
                    SN[key][0] += 1
                SN[key][1] += 1

        total_sel = len(tasks)
        per_arm_exploration[arm] = {
            "total_selections": total_sel,
            "minority_pick_count": minority_count,
            "minority_pick_share": (minority_count / total_sel if total_sel > 0 else None),
            "minority_pass_rate": {
                "n_settled": minority_settled_n,
                "k_pass": minority_settled_k,
                "n_infra_null": minority_infra_null,
                "rate": (minority_settled_k / minority_settled_n if minority_settled_n > 0 else None),
            },
            "majority_pass_rate": {
                "n_settled": majority_settled_n,
                "k_pass": majority_settled_k,
                "n_infra_null": majority_infra_null,
                "rate": (majority_settled_k / majority_settled_n if majority_settled_n > 0 else None),
            },
            "discovery_event_count_this_arm": sum(1 for e in discovery_events if e["arm"] == arm),
        }

    discovery_events_sorted = sorted(
        discovery_events, key=lambda e: (e["arm"], e["task_order_index"], e["route"])
    )

    return {
        "per_arm_exploration_interior_only": per_arm_exploration,
        "discovery_events": discovery_events_sorted,
        "canary_cross_tab_per_arm_lineage_x_scaffold": canary_matrix_per_arm,
        "canary_cross_tab_pooled_all_5_arms_lineage_x_scaffold": canary_matrix_pooled,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def build_meta(base: Path, arm_data: dict) -> dict:
    descs = {json.dumps(arm_data[arm]["raw"]["arm_descriptors"], sort_keys=True) for arm in ARM_DIRS}
    lineage_tuples = {tuple(arm_data[arm]["raw"]["worker_lineages"]) for arm in ARM_DIRS}
    assert len(descs) == 1, f"arm_descriptors differ across arms: {descs}"
    assert len(lineage_tuples) == 1, f"worker_lineages differ across arms: {lineage_tuples}"

    domain_buckets = sorted(
        {t["domain_bucket"] for arm in ARM_DIRS for t in arm_data[arm]["tasks"]}
    )

    return {
        "data_root": str(base),
        "arms": ARM_DIRS,
        "interior_arms": INTERIOR,
        "extreme_arms": EXTREME,
        "task_count_per_arm": {arm: len(arm_data[arm]["tasks"]) for arm in ARM_DIRS},
        "instance_count_per_arm": {
            arm: len({t["instance_id"] for t in arm_data[arm]["tasks"]}) for arm in ARM_DIRS
        },
        "infra_null_count_per_arm": {
            arm: sum(1 for t in arm_data[arm]["tasks"] if task_outcome(t) is None) for arm in ARM_DIRS
        },
        "order_verification": {arm: arm_data[arm]["note"] for arm in ARM_DIRS},
        "domain_buckets": domain_buckets,
        "n_domain_buckets": len(domain_buckets),
        "arm_descriptors": arm_data["tau_0"]["raw"]["arm_descriptors"],
        "arm_descriptors_consistent_across_arms": True,
        "worker_lineages": arm_data["tau_0"]["raw"]["worker_lineages"],
        "routes_canonical_order": [route_key(a, l) for a, l in ALL_ROUTES],
        "n_routes": len(ALL_ROUTES),
        "settlement_verdict_resolved_semantics": (
            "tri-state: true=pass, false=fail/reject, null=infra_null (harness "
            "never reached a verdict; excluded from all pass-rate denominators "
            "throughout this file -- matches STAGE_A_READOUT.json arm_stats "
            "n_settled/k_pass/rate convention exactly)."
        ),
    }


def main() -> int:
    base = repo_base()

    arm_data = {}
    for arm in ARM_DIRS:
        tasks, note, raw = load_arm_ordered_tasks(base, arm)
        arm_data[arm] = {"tasks": tasks, "note": note, "raw": raw}

    output = {
        "meta": build_meta(base, arm_data),
        "A1": a1_mcnemar(arm_data),
        "A2": a2_learning_curve(arm_data),
        "A3": a3_lockin(arm_data),
        "A4": a4_route_base_rates_and_oracle(arm_data),
        "A5": a5_price_discovery(arm_data),
        "A6": a6_exploration_and_canary(arm_data),
    }

    out_path = base / "EXPLORE_METRICS.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
