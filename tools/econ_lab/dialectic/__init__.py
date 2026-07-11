"""WP-L3-2 GRILL-ME route dialectic gate package (ADR-ECON-007
`adr/ADR-ECON-007-route-market-loop-remedy.md` Decision 5; design doc
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L3.6 "路线辩证门").

Sinks the meta-process TuringOS itself is built with (multiple heterogeneous
proposals + adversarial critique + a synthesizing judge) into a product mechanism:
before a route is committed to, a `route_portfolio.v1` of >=3 candidate routes is
produced, each carrying predicted failure modes, a cheap probe design, an exit
criterion, and a provenanced prior estimate -- never a single committed route.

Deliberately outside `tools/econ_lab/monitor/` and `tools/econ_lab/depthk/`
(file-partition discipline, mirroring `depthk/route_market.py`'s own "does not
import/read/modify Lane A territory" precedent): this package only ever
*read-only imports* `monitor.termination.assert_report_has_no_bzone_leak` (the
Decision-3 blacklist function named in this WP's own brief) -- it never writes to,
nor re-derives any formula from, `monitor/` or `depthk/`.

Every artifact this package produces is `proposal_only: true` (hard, never a caller
override) -- nothing here ever advances an `accepted_head`; any "accept/proceed"
decision continues to flow only through the pre-existing human-signature authority
path this package does not implement (this WP's own red line).
"""
