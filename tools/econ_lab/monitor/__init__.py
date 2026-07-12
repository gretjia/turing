"""WP-H1 external loop-detection package (ADR-ECON-007 Decision 2; design doc
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.1 rule 1).

Deliberately outside `tools/econ_lab/verifier`'s independent-verifier package: this
module never writes Q, never calls the verifier, and the verifier never imports this
module -- the two stay structurally independent (Decision 2's "检测器信号与经济奖励
解耦").
"""
