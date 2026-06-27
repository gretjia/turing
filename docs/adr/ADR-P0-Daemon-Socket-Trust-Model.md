# ADR: P0 Daemon Socket Trust Model

Status: Accepted for P0 private-local dogfood.

## Decision

P0 Unix-socket daemon ingress is a private-local boundary, not a hostile same-user boundary.

Daemon sockets must be created under an owner-only runtime directory, reject group/world-writable parents, set the socket mode to `0600`, and reject peers whose Unix peer credentials do not match the daemon UID. This protects `turingd`, `turing-execd`, and sidecars from non-owner local users on the same host.

P0 still trusts same-UID local processes. Same-UID clients can connect to the socket after the peer-credential check, so P0 deployments must treat the operator account as the daemon trust domain.

## Consequences

`turingd` remains the only process role that may move sovereign heads, and sidecars still own no truth. The socket check is an ingress guard around that role boundary; it is not a replacement for predicates, approval, replay, or append guards.

P1/P2 hostile-local or multi-user deployments must add nonce-bound signed typed-command envelopes for all head-affecting and authorization-affecting RPC methods before treating same-UID processes as untrusted.
