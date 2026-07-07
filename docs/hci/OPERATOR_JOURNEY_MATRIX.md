# Operator Journey Matrix v1

| State | Primary Message | Next Action | Allowed Commands | Recovery Path |
| --- | --- | --- | --- | --- |
| NotBooted | no MicroTape heads available | bootstrap through authority path | HELP, VIEW_STATUS | initialize MicroTape |
| Healthy | heads are coherent | inspect or propose | VIEW_STATUS, VIEW_PANOVIEW, EXPLAIN_EVENT, PROPOSE_GOAL | replay if stale |
| NeedsApproval | approval material is required | collect human signature | VIEW_PANOVIEW, EXPLAIN_BLOCKER, APPROVE_CAPSULE, APPROVE_CANDIDATE | use OS-keyring or hardware route |
| PendingExecution | dispatch was requested | wait for receipt | VIEW_STATUS, OBSERVE_CAPSULE | replay receipt path |
| AwaitingReceipt | worker output is not on tape | import receipt | OBSERVE_CAPSULE, EXPLAIN_BLOCKER | append receipt through daemon path |
| EvidenceMissing | required evidence is absent | gather evidence | EXPLAIN_BLOCKER, PROPOSE_CAPSULE | add evidence event |
| Blocked | required gate blocks next action | explain and propose rescue | EXPLAIN_BLOCKER, PROPOSE_CAPSULE | route to proposal |
| Failed | failure node exists | inspect failure | EXPLAIN_EVENT, PROPOSE_CAPSULE | rescue proposal |
| StaleProjection | view is stale | replay | REPLAY_VERIFY, VIEW_STATUS | rebuild snapshot |
| ReplayRequired | replay is required | run replay verify | REPLAY_VERIFY | retry snapshot |
| OutsideGovernanceObserved | external action is outside MicroTape | record observation | OBSERVE_CAPSULE, EXPLAIN_BLOCKER | append observation or failure |
| Unknown | state classifier had no match | ask for help | HELP, VIEW_STATUS | replay and inspect heads |
