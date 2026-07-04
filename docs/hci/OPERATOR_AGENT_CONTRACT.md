# Operator Agent Contract v1

North star:

```text
Humans may speak naturally.
TuringOS acts only through typed commands, predicates, approvals, receipts, and replay.
```

The Operator Agent may classify, explain, propose, and trace turns. It may not
evaluate predicates, move heads, create approval material, run shell, or dispatch
work outside a `typed_command.v1` boundary.

All agent output is advisory. The local implementation ceiling is
`IMPLEMENTER_ADDRESSED` until a real external human signature exists.

Renderer truth source: every human, JSON, TUI, or web renderer must consume
`operator_view_snapshot.v1`. Renderers may format fields. They may not derive new
truth, hide warnings, or change severity order.
