//! `hardware_manifest.v1` — HW-SW-007. Declares what this device IS and what
//! measurements BootGate (Phase 5) expects. Vendor/model/route strings are
//! DATA, never matched in code (Phase-0 dossier Q11).

use serde::Deserialize;
use std::collections::BTreeMap;

pub const MANIFEST_SCHEMA_VERSION: &str = "hardware_manifest.v1";

/// Errors raised by [`HardwareManifest::validate`]. Every forbidden shape
/// maps to a distinct variant so tests can bind the precise reject reason.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ManifestError {
    /// `schema_version` did not match [`MANIFEST_SCHEMA_VERSION`].
    BadSchemaVersion { found: String },
    /// A load-bearing string value contained a non-ASCII character.
    NonAsciiKey { field: &'static str },
    /// A `*_sha256` measurement was not exactly 64 lowercase hex characters.
    BadDigestFormat { field: &'static str },
    /// A required top-level table was absent.
    MissingSection { name: &'static str },
    /// The document was not valid TOML at all.
    Parse(String),
}

impl std::fmt::Display for ManifestError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ManifestError::BadSchemaVersion { found } => write!(
                f,
                "unknown schema_version {found:?}, expected {MANIFEST_SCHEMA_VERSION:?}"
            ),
            ManifestError::NonAsciiKey { field } => {
                write!(f, "non-ASCII load-bearing value at {field}")
            }
            ManifestError::BadDigestFormat { field } => {
                write!(f, "{field} must be 64 lowercase hex characters")
            }
            ManifestError::MissingSection { name } => write!(f, "missing section [{name}]"),
            ManifestError::Parse(m) => write!(f, "hardware_manifest.toml parse: {m}"),
        }
    }
}

impl std::error::Error for ManifestError {}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Tpm {
    pub present: bool,
    pub version: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Tee {
    pub kind: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Device {
    pub id: String,
    pub platform: String,
    pub tpm: Tpm,
    pub tee: Tee,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Measurements {
    pub constitution_sha256: String,
    pub schema_pack_sha256: String,
    pub predicate_pack_sha256: String,
    pub runtime_binary_sha256: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Signing {
    pub route: String,
    pub key_id: String,
    pub algorithm: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PcrBaseline {
    pub bank: String,
    #[serde(default)]
    pub pcrs: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HardwareManifest {
    pub schema_version: String,
    #[serde(default)]
    pub device: Option<Device>,
    #[serde(default)]
    pub measurements: Option<Measurements>,
    #[serde(default)]
    pub signing: Option<Signing>,
    #[serde(default)]
    pub pcr_baseline: Option<PcrBaseline>,
}

fn is_lower_hex64(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

impl HardwareManifest {
    /// Parse raw TOML. Sections are optional at this layer so
    /// [`Self::validate`] can report a precise [`ManifestError::MissingSection`]
    /// instead of a generic parse failure.
    pub fn parse(text: &str) -> Result<Self, ManifestError> {
        toml::from_str(text).map_err(|e| ManifestError::Parse(e.to_string()))
    }

    /// `schema_version` recognized, all required sections present, all
    /// `*_sha256` measurements well-formed lowercase hex-64, all load-bearing
    /// string values ASCII.
    pub fn validate(&self) -> Result<(), ManifestError> {
        if self.schema_version != MANIFEST_SCHEMA_VERSION {
            return Err(ManifestError::BadSchemaVersion {
                found: self.schema_version.clone(),
            });
        }

        let device = self
            .device
            .as_ref()
            .ok_or(ManifestError::MissingSection { name: "device" })?;
        let measurements = self
            .measurements
            .as_ref()
            .ok_or(ManifestError::MissingSection { name: "measurements" })?;
        let signing = self
            .signing
            .as_ref()
            .ok_or(ManifestError::MissingSection { name: "signing" })?;
        self.pcr_baseline
            .as_ref()
            .ok_or(ManifestError::MissingSection { name: "pcr_baseline" })?;

        let ascii_fields: [(&'static str, &str); 7] = [
            ("device.id", &device.id),
            ("device.platform", &device.platform),
            ("device.tpm.version", &device.tpm.version),
            ("device.tee.kind", &device.tee.kind),
            ("signing.route", &signing.route),
            ("signing.key_id", &signing.key_id),
            ("signing.algorithm", &signing.algorithm),
        ];
        for (field, value) in ascii_fields {
            if !value.is_ascii() {
                return Err(ManifestError::NonAsciiKey { field });
            }
        }

        let digest_fields: [(&'static str, &str); 4] = [
            ("measurements.constitution_sha256", &measurements.constitution_sha256),
            ("measurements.schema_pack_sha256", &measurements.schema_pack_sha256),
            ("measurements.predicate_pack_sha256", &measurements.predicate_pack_sha256),
            ("measurements.runtime_binary_sha256", &measurements.runtime_binary_sha256),
        ];
        for (field, digest) in digest_fields {
            if !is_lower_hex64(digest) {
                return Err(ManifestError::BadDigestFormat { field });
            }
        }

        Ok(())
    }
}
