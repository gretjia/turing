//! Route + algorithm negotiation for the approval signing path.
//!
//! Negotiation binds a signing route to an explicit algorithm BEFORE signing so
//! a backend can never silently swap the route or downgrade the algorithm. The
//! negotiated algorithm rides OUT-OF-BAND (trusted-key-record identity), never
//! inside the signed `ApprovalPayload`: adding an algorithm field to the
//! payload is a schema-v3 wire break, deferred (see
//! docs/security/key_hierarchy.md). The route itself already rides the signed
//! canonical bytes, so `assert_matches_card` re-checks it against the payload.

use crate::{ApprovalCard, SignatureRoute, SigningBackend, SigningError};

/// Signature algorithm offered on a signing route.
///
/// Constraint: negotiated out-of-band; it MUST NOT enter the signed
/// `ApprovalPayload` bytes (that is a schema-v3 change, deferred).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignatureAlgorithm {
    /// The only algorithm any current backend signs with.
    Ed25519,
    /// Reserved for hardware backends (e.g. YubiKey PIV); no software signer.
    EcdsaP256,
}

/// A route+algorithm pair a backend explicitly agreed to before signing.
///
/// Constraint: produced only by [`negotiate`]; possessing one is the proof that
/// no silent route or algorithm swap occurred.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NegotiatedRoute {
    /// The signing route that was agreed; equals the backend's own route.
    pub route: SignatureRoute,
    /// The algorithm that was agreed; must be in the backend's supported set.
    pub algorithm: SignatureAlgorithm,
}

impl NegotiatedRoute {
    /// Out-of-band identity string binding route to algorithm.
    ///
    /// Constraint: this is the algorithm-identity surface (trusted-key-record
    /// side); it is never serialized into the signed payload.
    #[must_use]
    pub fn identity_field(&self) -> String {
        format!("{:?}+{:?}", self.route, self.algorithm)
    }

    /// Asserts the negotiated route equals the route baked into the card's
    /// signed payload.
    ///
    /// Constraint: the route rides the signed bytes, so a disagreement here is
    /// rejected, never coerced.
    pub fn assert_matches_card(&self, card: &ApprovalCard) -> Result<(), SigningError> {
        let observed = card.payload().signature_route;
        if observed == self.route {
            Ok(())
        } else {
            Err(SigningError::NegotiationIdentityMismatch {
                expected: self.route,
                observed,
            })
        }
    }
}

/// Negotiates a signing route+algorithm against a backend, never swapping.
///
/// Constraint: a `None` route, a backend that does not own `route`, or an
/// unsupported `requested_algorithm` is a hard `Err(RouteAlgorithmUnsupported)`
/// — never a silent downgrade or route change.
///
/// ADVISORY: `sign()` does not require a `NegotiatedRoute`, so this is not yet
/// a runtime control; a `sign_negotiated(&NegotiatedRoute, card)` wrapper is
/// the planned additive close (deferred, see docs/security/key_hierarchy.md).
pub fn negotiate(
    route: SignatureRoute,
    requested_algorithm: SignatureAlgorithm,
    backend: &dyn SigningBackend,
) -> Result<NegotiatedRoute, SigningError> {
    // A `None` route carries no signing authority; never negotiable.
    if route == SignatureRoute::None {
        return Err(SigningError::RouteAlgorithmUnsupported {
            route,
            algorithm: requested_algorithm,
        });
    }
    // The backend must own the requested route; no silent route swap.
    if backend.route() != route {
        return Err(SigningError::RouteAlgorithmUnsupported {
            route,
            algorithm: requested_algorithm,
        });
    }
    // The algorithm must be explicitly supported; no silent downgrade.
    if !backend.supported_algorithms().contains(&requested_algorithm) {
        return Err(SigningError::RouteAlgorithmUnsupported {
            route,
            algorithm: requested_algorithm,
        });
    }
    Ok(NegotiatedRoute {
        route,
        algorithm: requested_algorithm,
    })
}
