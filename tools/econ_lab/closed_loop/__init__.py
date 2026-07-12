"""WP-L3-3 -- closed-loop integration package (ADR-ECON-007
`adr/ADR-ECON-007-route-market-loop-remedy.md`, all Decisions).

Wires the L3-1 (`iterate.iterate_harness`) and L3-2 (`dialectic.dialectic_gate` +
`dialectic.route_market_bridge`) components -- both already merged, both unmodified by
this WP -- into one closed loop: dialectic gate (real three-role panel) -> route
portfolio -> route-market candidates+priors -> iterate harness per route (organic
`--monitor` semantics) -> on escalation, a Decision-4 falsification report flows back
into the dialectic gate as re-entry evidence -> a revised portfolio -> a second route
-> a final terminal state (success settlement or combination-exhausted final
falsification), always carrying real verifier evidence.

Nature: exploratory closed-loop DRILL (`演练非实验`), never an experiment -- no
statistical claim anywhere in this package's own output. See
`closed_loop_driver.py`'s own module docstring for the full six-checkpoint evidence
map and the real-call budget discipline (<= 15 real LLM/worker calls, strictly
counted).
"""
