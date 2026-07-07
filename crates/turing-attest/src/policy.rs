//! `attestation_policy.v1` — HW-SW-008. HOW hardware evidence must be
//! verified: PCR selection sets, freshness window, degraded-mode rules. The
//! hash of this file becomes `q_t_quote.quoted.policy_hash`.

use serde::Deserialize;

pub const POLICY_SCHEMA_VERSION: &str = "attestation_policy.v1";

/// Errors raised by [`AttestationPolicy::validate`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PolicyError {
    /// `[policy].schema_version` did not match [`POLICY_SCHEMA_VERSION`].
    BadSchemaVersion { found: String },
    /// A required top-level table was absent.
    MissingSection { name: &'static str },
    /// `[degraded].on_fail` was neither `halt_authorization` nor `deny_boot`.
    BadOnFail { found: String },
    /// `[tee].allow_debug = true` while `[degraded].simulator_allowed = false`
    /// — a debug enclave is never admissible once simulator evidence is
    /// disallowed (strict/real-hardware mode).
    DebugWithoutSimulator,
    /// The document was not valid TOML at all.
    Parse(String),
}

impl std::fmt::Display for PolicyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PolicyError::BadSchemaVersion { found } => write!(
                f,
                "unknown policy.schema_version {found:?}, expected {POLICY_SCHEMA_VERSION:?}"
            ),
            PolicyError::MissingSection { name } => write!(f, "missing section [{name}]"),
            PolicyError::BadOnFail { found } => write!(
                f,
                "degraded.on_fail {found:?} must be halt_authorization or deny_boot"
            ),
            PolicyError::DebugWithoutSimulator => write!(
                f,
                "tee.allow_debug=true requires degraded.simulator_allowed=true (debug enclave never allowed in strict mode)"
            ),
            PolicyError::Parse(m) => write!(f, "attestation_policy.toml parse: {m}"),
        }
    }
}

impl std::error::Error for PolicyError {}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PolicySection {
    pub schema_version: String,
    pub freshness_max_age_s: u64,
    pub nonce_required: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TpmPolicy {
    pub required_pcrs: Vec<u32>,
    pub allowed_banks: Vec<String>,
    pub ak_cert_required: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TeePolicy {
    pub allowed_enclave_measurements: Vec<String>,
    pub allow_debug: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Degraded {
    pub simulator_allowed: bool,
    pub on_fail: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AttestationPolicy {
    #[serde(default)]
    pub policy: Option<PolicySection>,
    #[serde(default)]
    pub tpm: Option<TpmPolicy>,
    #[serde(default)]
    pub tee: Option<TeePolicy>,
    #[serde(default)]
    pub degraded: Option<Degraded>,
}

impl AttestationPolicy {
    pub fn parse(text: &str) -> Result<Self, PolicyError> {
        toml::from_str(text).map_err(|e| PolicyError::Parse(e.to_string()))
    }

    pub fn validate(&self) -> Result<(), PolicyError> {
        let policy = self
            .policy
            .as_ref()
            .ok_or(PolicyError::MissingSection { name: "policy" })?;
        self.tpm.as_ref().ok_or(PolicyError::MissingSection { name: "tpm" })?;
        let tee = self
            .tee
            .as_ref()
            .ok_or(PolicyError::MissingSection { name: "tee" })?;
        let degraded = self
            .degraded
            .as_ref()
            .ok_or(PolicyError::MissingSection { name: "degraded" })?;

        if policy.schema_version != POLICY_SCHEMA_VERSION {
            return Err(PolicyError::BadSchemaVersion {
                found: policy.schema_version.clone(),
            });
        }

        if degraded.on_fail != "halt_authorization" && degraded.on_fail != "deny_boot" {
            return Err(PolicyError::BadOnFail {
                found: degraded.on_fail.clone(),
            });
        }

        if tee.allow_debug && !degraded.simulator_allowed {
            return Err(PolicyError::DebugWithoutSimulator);
        }

        Ok(())
    }
}
