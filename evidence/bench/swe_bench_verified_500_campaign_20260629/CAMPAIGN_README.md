# SWE-bench Verified 500 Campaign Controller

This directory freezes the internal official-harness campaign control plane.
It does not run the 500 tasks and does not claim official leaderboard
equivalence.

Current supervisor state:
- upstream SWE-bench Docker harness identity gate: READY, via Phase F official
  harness qualification at commit d055ae4bd013ff09298ae8af576ebdbcf32a4e8c;
- full Verified 500 manifest freeze: PASS;
- campaign execution: not started;
- next gate: S00 must provide one worker-derived unified-diff prediction per
  shard task before the official harness command can be marked ready.
- S00-W00 worker-safe task packets: materialized for 10/10 tasks from the local
  Verified dataset cache, with dataset gold patches, test patches, hidden test
  labels, and hints removed from worker-visible packets.
- S00-W00 worker-derived candidates: 10/10 audited source-only candidate
  patches exist.
- S00-W01 worker-safe task packets: materialized for 10/10 tasks, with dataset
  gold patches, test patches, hidden test labels, and hints removed from
  worker-visible packets.
- S00-W01 worker-derived candidates: 10/10 audited source-only candidate
  patches exist.
- S00-W02 worker-safe task packets: materialized for 10/10 tasks, with dataset
  gold patches, test patches, hidden test labels, and hints removed from
  worker-visible packets.
- S00-W02 worker-derived candidates: 10/10 audited source-only candidate
  patches exist.
- S00 predictions: 30/50 worker-derived unified-diff predictions assembled.
- S00 execution gate: BLOCKED until `predictions/shard_S00_predictions.jsonl`
  contains 50 worker-derived unified-diff predictions matching the S00 manifest.

Execution policy:
- one-shot 500 run: FORBIDDEN
- execution atom: one instance
- process QC: 10-task IPQC window
- audit atom: 50-task sealed shard
- full campaign: 10 shards x 50 tasks

Current S00 worker-safe packet roots:

```text
shards/S00/ipqc/S00-W00/worker_safe_tasks/
shards/S00/ipqc/S00-W01/worker_safe_tasks/
shards/S00/ipqc/S00-W02/worker_safe_tasks/
```

Current audited S00 candidates:

```text
shards/S00/tasks/django__django-10097/candidate.patch
shards/S00/tasks/django__django-10097/worker_receipt.json
shards/S00/tasks/django__django-10097/worker_candidate_audit.json
shards/S00/tasks/astropy__astropy-12907/
shards/S00/tasks/matplotlib__matplotlib-13989/
shards/S00/tasks/mwaskom__seaborn-3069/
shards/S00/tasks/pallets__flask-5014/
shards/S00/tasks/psf__requests-1142/
shards/S00/tasks/pydata__xarray-2905/
shards/S00/tasks/pylint-dev__pylint-4551/
shards/S00/tasks/pytest-dev__pytest-10051/
shards/S00/tasks/scikit-learn__scikit-learn-10297/
shards/S00/tasks/sphinx-doc__sphinx-10323/
shards/S00/tasks/sympy__sympy-11618/
shards/S00/tasks/astropy__astropy-13033/
shards/S00/tasks/django__django-10554/
shards/S00/tasks/matplotlib__matplotlib-14623/
shards/S00/tasks/mwaskom__seaborn-3187/
shards/S00/tasks/psf__requests-1724/
shards/S00/tasks/pydata__xarray-3095/
shards/S00/tasks/pylint-dev__pylint-4604/
shards/S00/tasks/pytest-dev__pytest-10081/
shards/S00/tasks/scikit-learn__scikit-learn-10844/
shards/S00/tasks/sphinx-doc__sphinx-10435/
shards/S00/tasks/sympy__sympy-12096/
shards/S00/tasks/astropy__astropy-13236/
shards/S00/tasks/django__django-10880/
shards/S00/tasks/matplotlib__matplotlib-20488/
shards/S00/tasks/psf__requests-1766/
shards/S00/tasks/pydata__xarray-3151/
shards/S00/tasks/pylint-dev__pylint-4661/
shards/S00/tasks/pytest-dev__pytest-10356/
```
