//! Approval cards and signing backend contracts.
//!
//! Approval bytes are sovereignty-bearing, so every consumer must sign, display-hash,
//! gate, and replay the same canonical payload bytes. Localized display copy is
//! deliberately outside that signed payload.

use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Mutex, OnceLock};

use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use rand_core::OsRng;
use serde::{Deserialize, Serialize};
use turing_contracts::jcs::{self, JcsError};

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

pub const APPROVAL_PAYLOAD_SCHEMA_ID: &str = "approval_payload.v2";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SignatureRoute {
    None,
    OsKeyring,
    LocalFileDev,
    InMemoryTest,
    HardwareFuture,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovalPayload {
    pub schema_id: String,
    pub approval_id: String,
    pub authority_epoch: u64,
    pub action: String,
    pub subject_id: String,
    pub evidence_digests: Vec<String>,
    pub risk_class: String,
    pub signature_route: SignatureRoute,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisplayCopy {
    pub title_zh: String,
    pub body_en: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApprovalCard {
    payload: ApprovalPayload,
    display_copy: DisplayCopy,
}

impl ApprovalCard {
    #[must_use]
    pub fn new(payload: ApprovalPayload, display_copy: DisplayCopy) -> Self {
        ApprovalCard {
            payload,
            display_copy,
        }
    }

    #[must_use]
    pub fn payload(&self) -> &ApprovalPayload {
        &self.payload
    }

    #[must_use]
    pub fn display_copy(&self) -> &DisplayCopy {
        &self.display_copy
    }

    #[must_use]
    pub fn with_display_copy(&self, display_copy: DisplayCopy) -> Self {
        ApprovalCard {
            payload: self.payload.clone(),
            display_copy,
        }
    }

    pub fn canonical_bytes(&self) -> Result<Vec<u8>, ApprovalError> {
        if self.payload.schema_id != APPROVAL_PAYLOAD_SCHEMA_ID {
            return Err(ApprovalError::InvalidSchemaId(
                self.payload.schema_id.clone(),
            ));
        }
        for digest in &self.payload.evidence_digests {
            validate_digest(digest)?;
        }
        let value = serde_json::to_value(&self.payload)
            .expect("ApprovalPayload serializes to JSON infallibly");
        Ok(jcs::canonicalize(&value)?)
    }

    pub fn byte_surfaces(&self) -> Result<ApprovalByteSurfaces, ApprovalError> {
        let canonical_bytes = self.canonical_bytes()?;
        let visible_card_hash = digest(&canonical_bytes);
        Ok(ApprovalByteSurfaces {
            visible_card_hash,
            visible_card_hash_bytes: canonical_bytes.clone(),
            signed_bytes: canonical_bytes.clone(),
            gate_replay_bytes: canonical_bytes.clone(),
            canonical_bytes,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApprovalByteSurfaces {
    pub canonical_bytes: Vec<u8>,
    pub visible_card_hash_bytes: Vec<u8>,
    pub signed_bytes: Vec<u8>,
    pub gate_replay_bytes: Vec<u8>,
    pub visible_card_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignatureEnvelope {
    pub schema_id: String,
    pub key_id: String,
    pub authority_epoch: u64,
    pub signature_route: SignatureRoute,
    pub public_key_fingerprint: String,
    pub verifying_key: String,
    pub signed_payload_hash: String,
    pub signature: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuthorityKeyRecord {
    pub schema_id: String,
    pub key_id: String,
    pub authority_epoch: u64,
    pub signature_route: SignatureRoute,
    pub public_key_fingerprint: String,
    pub verifying_key: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct AuthorityKeySet {
    records: BTreeMap<String, AuthorityKeyRecord>,
}

impl AuthorityKeySet {
    #[must_use]
    pub fn from_record(record: AuthorityKeyRecord) -> Self {
        let mut set = AuthorityKeySet::default();
        set.insert(record);
        set
    }

    pub fn insert(&mut self, record: AuthorityKeyRecord) {
        self.records.insert(
            authority_key_lookup_key(
                &record.key_id,
                record.authority_epoch,
                record.signature_route,
            ),
            record,
        );
    }

    fn get(
        &self,
        key_id: &str,
        authority_epoch: u64,
        signature_route: SignatureRoute,
    ) -> Option<&AuthorityKeyRecord> {
        self.records.get(&authority_key_lookup_key(
            key_id,
            authority_epoch,
            signature_route,
        ))
    }
}

pub trait SigningBackend {
    fn key_id(&self) -> &str;
    fn route(&self) -> SignatureRoute;

    fn exports_plaintext_key(&self) -> bool {
        false
    }

    fn sign(&self, card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError>;

    fn authority_key_record(
        &self,
        authority_epoch: u64,
    ) -> Result<AuthorityKeyRecord, SigningError>;

    fn verify(
        &self,
        card: &ApprovalCard,
        signature: &SignatureEnvelope,
        trusted_keys: &AuthorityKeySet,
    ) -> Result<(), SigningError>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OsKeyringSigningBackend {
    key_id: String,
    provider: OsKeyringProvider,
}

impl OsKeyringSigningBackend {
    #[must_use]
    pub fn new(key_id: impl Into<String>) -> Self {
        OsKeyringSigningBackend {
            key_id: key_id.into(),
            provider: OsKeyringProvider::Platform,
        }
    }

    fn load_or_create_signing_key(&self) -> Result<SigningKey, SigningError> {
        match self.provider {
            OsKeyringProvider::Platform => self.load_or_create_platform_key(),
        }
    }

    fn load_or_create_platform_key(&self) -> Result<SigningKey, SigningError> {
        match secret_tool_lookup(&self.key_id)? {
            Some(seed_hex) => decode_signing_key_hex(&seed_hex).map_err(|message| {
                SigningError::OsKeyringUnavailable {
                    provider: "secret-tool",
                    message,
                }
            }),
            None => {
                let mut rng = OsRng;
                let signing_key = SigningKey::generate(&mut rng);
                let seed_hex = hex::encode(signing_key.to_bytes());
                secret_tool_store(&self.key_id, &seed_hex)?;
                Ok(signing_key)
            }
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum OsKeyringProvider {
    Platform,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InMemoryTestSigningBackend {
    key_id: String,
    can_sign: bool,
}

impl InMemoryTestSigningBackend {
    #[must_use]
    pub fn new(key_id: impl Into<String>) -> Self {
        InMemoryTestSigningBackend {
            key_id: key_id.into(),
            can_sign: true,
        }
    }

    #[must_use]
    pub fn verifier(key_id: impl Into<String>) -> Self {
        InMemoryTestSigningBackend {
            key_id: key_id.into(),
            can_sign: false,
        }
    }

    fn signing_key(&self) -> Result<SigningKey, SigningError> {
        if self.can_sign {
            Ok(in_memory_test_key(&self.key_id))
        } else {
            Err(SigningError::TestSigningKeyUnavailable {
                key_id: self.key_id.clone(),
            })
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalFileSigningBackend {
    key_id: String,
    key_store_dir: Option<PathBuf>,
}

impl LocalFileSigningBackend {
    #[must_use]
    pub fn new(key_id: impl Into<String>) -> Self {
        LocalFileSigningBackend {
            key_id: key_id.into(),
            key_store_dir: None,
        }
    }

    #[must_use]
    pub fn with_key_store_dir(
        key_id: impl Into<String>,
        key_store_dir: impl Into<PathBuf>,
    ) -> Self {
        LocalFileSigningBackend {
            key_id: key_id.into(),
            key_store_dir: Some(key_store_dir.into()),
        }
    }

    fn key_store_dir(&self) -> PathBuf {
        if let Some(dir) = &self.key_store_dir {
            dir.clone()
        } else if let Some(dir) = std::env::var_os("TURINGOS_APPROVAL_LOCAL_FILE_KEY_DIR") {
            PathBuf::from(dir)
        } else {
            std::env::var_os("HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|| PathBuf::from("."))
                .join(".turingos")
                .join("approval_local_file_keys")
        }
    }

    fn key_store_path(&self) -> PathBuf {
        let name = jcs::sha256_hex(self.key_id.as_bytes());
        self.key_store_dir().join(format!("{name}.json"))
    }

    fn load_or_create_signing_key(&self) -> Result<SigningKey, SigningError> {
        let path = self.key_store_path();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|error| SigningError::KeyStoreUnavailable {
                path: parent.to_path_buf(),
                message: error.to_string(),
            })?;
        }
        if path.exists() {
            match self.load_signing_key(&path) {
                Ok(signing_key) => return Ok(signing_key),
                Err(SigningError::KeyStoreUnavailable { .. })
                | Err(SigningError::KeyMaterialCorrupt { .. }) => {
                    let _ = fs::remove_file(&path);
                }
                Err(error) => return Err(error),
            }
        }
        let mut rng = OsRng;
        let signing_key = SigningKey::generate(&mut rng);
        let record = KeyRecord::from_signing_key(&self.key_id, &signing_key);
        let bytes =
            serde_json::to_vec(&record).map_err(|error| SigningError::KeyStoreUnavailable {
                path: path.clone(),
                message: error.to_string(),
            })?;
        match fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
        {
            Ok(mut file) => {
                file.write_all(&bytes)
                    .map_err(|error| SigningError::KeyStoreUnavailable {
                        path: path.clone(),
                        message: error.to_string(),
                    })?;
                file.flush()
                    .map_err(|error| SigningError::KeyStoreUnavailable {
                        path: path.clone(),
                        message: error.to_string(),
                    })?;
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
                return self.load_signing_key(&path);
            }
            Err(error) => {
                return Err(SigningError::KeyStoreUnavailable {
                    path: path.clone(),
                    message: error.to_string(),
                });
            }
        }
        #[cfg(unix)]
        {
            let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
        }
        Ok(signing_key)
    }

    fn load_signing_key(&self, path: &Path) -> Result<SigningKey, SigningError> {
        let text = fs::read_to_string(path).map_err(|error| SigningError::KeyStoreUnavailable {
            path: path.to_path_buf(),
            message: error.to_string(),
        })?;
        let record: KeyRecord =
            serde_json::from_str(&text).map_err(|error| SigningError::KeyMaterialCorrupt {
                path: path.to_path_buf(),
                message: error.to_string(),
            })?;
        if record.schema_id != "approval_key_record.v1" {
            return Err(SigningError::KeyMaterialCorrupt {
                path: path.to_path_buf(),
                message: format!("unexpected schema_id {:?}", record.schema_id),
            });
        }
        if record.key_id != self.key_id {
            return Err(SigningError::KeyMaterialCorrupt {
                path: path.to_path_buf(),
                message: format!(
                    "stored key_id {:?} does not match backend key_id {:?}",
                    record.key_id, self.key_id
                ),
            });
        }
        let seed = hex::decode(record.signing_key_hex).map_err(|error| {
            SigningError::KeyMaterialCorrupt {
                path: path.to_path_buf(),
                message: error.to_string(),
            }
        })?;
        let seed: [u8; 32] = seed
            .try_into()
            .map_err(|_| SigningError::KeyMaterialCorrupt {
                path: path.to_path_buf(),
                message: "signing key seed must be 32 bytes".to_string(),
            })?;
        Ok(SigningKey::from_bytes(&seed))
    }
}

fn in_memory_test_keyring() -> &'static Mutex<BTreeMap<String, SigningKey>> {
    static KEYRING: OnceLock<Mutex<BTreeMap<String, SigningKey>>> = OnceLock::new();
    KEYRING.get_or_init(|| Mutex::new(BTreeMap::new()))
}

fn in_memory_test_key(key_id: &str) -> SigningKey {
    let mut keyring = in_memory_test_keyring()
        .lock()
        .expect("in-memory test keyring mutex poisoned");
    keyring
        .entry(key_id.to_string())
        .or_insert_with(|| {
            let mut rng = OsRng;
            SigningKey::generate(&mut rng)
        })
        .clone()
}

fn secret_tool_lookup(key_id: &str) -> Result<Option<String>, SigningError> {
    let output = Command::new("secret-tool")
        .args(["lookup", "service", "turingos-approval", "key_id", key_id])
        .output()
        .map_err(|error| SigningError::OsKeyringUnavailable {
            provider: "secret-tool",
            message: error.to_string(),
        })?;
    if output.status.success() {
        let seed_hex = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if seed_hex.is_empty() {
            Ok(None)
        } else {
            Ok(Some(seed_hex))
        }
    } else {
        Ok(None)
    }
}

fn secret_tool_store(key_id: &str, seed_hex: &str) -> Result<(), SigningError> {
    let mut child = Command::new("secret-tool")
        .args([
            "store",
            "--label",
            &format!("TuringOS approval key {key_id}"),
            "service",
            "turingos-approval",
            "key_id",
            key_id,
        ])
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|error| SigningError::OsKeyringUnavailable {
            provider: "secret-tool",
            message: error.to_string(),
        })?;
    {
        let stdin = child
            .stdin
            .as_mut()
            .ok_or_else(|| SigningError::OsKeyringUnavailable {
                provider: "secret-tool",
                message: "secret-tool stdin unavailable".to_string(),
            })?;
        stdin.write_all(seed_hex.as_bytes()).map_err(|error| {
            SigningError::OsKeyringUnavailable {
                provider: "secret-tool",
                message: error.to_string(),
            }
        })?;
    }
    let status = child
        .wait()
        .map_err(|error| SigningError::OsKeyringUnavailable {
            provider: "secret-tool",
            message: error.to_string(),
        })?;
    if status.success() {
        Ok(())
    } else {
        Err(SigningError::OsKeyringUnavailable {
            provider: "secret-tool",
            message: format!("secret-tool store exited with {status}"),
        })
    }
}

fn decode_signing_key_hex(seed_hex: &str) -> Result<SigningKey, String> {
    let seed = hex::decode(seed_hex.trim()).map_err(|error| error.to_string())?;
    let seed: [u8; 32] = seed
        .try_into()
        .map_err(|_| "signing key seed must be 32 bytes".to_string())?;
    Ok(SigningKey::from_bytes(&seed))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct KeyRecord {
    schema_id: String,
    key_id: String,
    signing_key_hex: String,
}

impl KeyRecord {
    fn from_signing_key(key_id: &str, signing_key: &SigningKey) -> Self {
        KeyRecord {
            schema_id: "approval_key_record.v1".to_string(),
            key_id: key_id.to_string(),
            signing_key_hex: hex::encode(signing_key.to_bytes()),
        }
    }
}

impl SigningBackend for OsKeyringSigningBackend {
    fn key_id(&self) -> &str {
        &self.key_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::OsKeyring
    }

    fn sign(&self, card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        if card.payload.signature_route != SignatureRoute::OsKeyring {
            return Err(SigningError::RouteMismatch {
                expected: card.payload.signature_route,
                observed: SignatureRoute::OsKeyring,
            });
        }
        let bytes = card.canonical_bytes()?;
        let signing_key = self.load_or_create_signing_key()?;
        let signature = signing_key.sign(&bytes);
        Ok(signature_envelope(
            &self.key_id,
            card.payload.authority_epoch,
            SignatureRoute::OsKeyring,
            &bytes,
            &signing_key,
            &signature,
        ))
    }

    fn authority_key_record(
        &self,
        authority_epoch: u64,
    ) -> Result<AuthorityKeyRecord, SigningError> {
        let signing_key = self.load_or_create_signing_key()?;
        Ok(authority_key_record(
            &self.key_id,
            authority_epoch,
            SignatureRoute::OsKeyring,
            &signing_key,
        ))
    }

    fn verify(
        &self,
        card: &ApprovalCard,
        signature: &SignatureEnvelope,
        trusted_keys: &AuthorityKeySet,
    ) -> Result<(), SigningError> {
        verify_signature_with_authority_keys(card, signature, trusted_keys, &self.key_id)
    }
}

impl SigningBackend for InMemoryTestSigningBackend {
    fn key_id(&self) -> &str {
        &self.key_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::InMemoryTest
    }

    fn sign(&self, card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        if card.payload.signature_route != SignatureRoute::InMemoryTest {
            return Err(SigningError::RouteMismatch {
                expected: card.payload.signature_route,
                observed: SignatureRoute::InMemoryTest,
            });
        }
        let bytes = card.canonical_bytes()?;
        let signing_key = self.signing_key()?;
        let signature = signing_key.sign(&bytes);
        Ok(signature_envelope(
            &self.key_id,
            card.payload.authority_epoch,
            SignatureRoute::InMemoryTest,
            &bytes,
            &signing_key,
            &signature,
        ))
    }

    fn authority_key_record(
        &self,
        authority_epoch: u64,
    ) -> Result<AuthorityKeyRecord, SigningError> {
        let signing_key = self.signing_key()?;
        Ok(authority_key_record(
            &self.key_id,
            authority_epoch,
            SignatureRoute::InMemoryTest,
            &signing_key,
        ))
    }

    fn verify(
        &self,
        card: &ApprovalCard,
        signature: &SignatureEnvelope,
        trusted_keys: &AuthorityKeySet,
    ) -> Result<(), SigningError> {
        verify_signature_with_authority_keys(card, signature, trusted_keys, &self.key_id)
    }
}

impl SigningBackend for LocalFileSigningBackend {
    fn key_id(&self) -> &str {
        &self.key_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::LocalFileDev
    }

    fn exports_plaintext_key(&self) -> bool {
        true
    }

    fn sign(&self, card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        if card.payload.signature_route != SignatureRoute::LocalFileDev {
            return Err(SigningError::RouteMismatch {
                expected: card.payload.signature_route,
                observed: SignatureRoute::LocalFileDev,
            });
        }
        let bytes = card.canonical_bytes()?;
        let signing_key = self.load_or_create_signing_key()?;
        let signature = signing_key.sign(&bytes);
        Ok(signature_envelope(
            &self.key_id,
            card.payload.authority_epoch,
            SignatureRoute::LocalFileDev,
            &bytes,
            &signing_key,
            &signature,
        ))
    }

    fn authority_key_record(
        &self,
        authority_epoch: u64,
    ) -> Result<AuthorityKeyRecord, SigningError> {
        let signing_key = self.load_or_create_signing_key()?;
        Ok(authority_key_record(
            &self.key_id,
            authority_epoch,
            SignatureRoute::LocalFileDev,
            &signing_key,
        ))
    }

    fn verify(
        &self,
        card: &ApprovalCard,
        signature: &SignatureEnvelope,
        trusted_keys: &AuthorityKeySet,
    ) -> Result<(), SigningError> {
        verify_signature_with_authority_keys(card, signature, trusted_keys, &self.key_id)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HardwareSigningBackend {
    slot_id: String,
}

impl HardwareSigningBackend {
    #[must_use]
    pub fn slot(slot_id: impl Into<String>) -> Self {
        HardwareSigningBackend {
            slot_id: slot_id.into(),
        }
    }
}

impl SigningBackend for HardwareSigningBackend {
    fn key_id(&self) -> &str {
        &self.slot_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::HardwareFuture
    }

    fn sign(&self, _card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }

    fn authority_key_record(
        &self,
        _authority_epoch: u64,
    ) -> Result<AuthorityKeyRecord, SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }

    fn verify(
        &self,
        _card: &ApprovalCard,
        _signature: &SignatureEnvelope,
        _trusted_keys: &AuthorityKeySet,
    ) -> Result<(), SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApprovalError {
    InvalidSchemaId(String),
    InvalidDigest(String),
    Canonicalization(String),
}

impl std::fmt::Display for ApprovalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ApprovalError::InvalidSchemaId(schema_id) => {
                write!(
                    f,
                    "approval payload schema_id must be {APPROVAL_PAYLOAD_SCHEMA_ID:?}, got {schema_id:?}"
                )
            }
            ApprovalError::InvalidDigest(digest) => write!(f, "invalid digest {digest:?}"),
            ApprovalError::Canonicalization(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for ApprovalError {}

impl From<JcsError> for ApprovalError {
    fn from(value: JcsError) -> Self {
        ApprovalError::Canonicalization(value.to_string())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SigningError {
    Approval(ApprovalError),
    RouteMismatch {
        expected: SignatureRoute,
        observed: SignatureRoute,
    },
    KeyStoreUnavailable {
        path: PathBuf,
        message: String,
    },
    KeyMaterialCorrupt {
        path: PathBuf,
        message: String,
    },
    OsKeyringUnavailable {
        provider: &'static str,
        message: String,
    },
    SignatureInvalidEncoding(String),
    SignatureVerificationFailed {
        key_id: String,
    },
    AuthorityKeyNotTrusted {
        key_id: String,
        authority_epoch: u64,
        signature_route: SignatureRoute,
    },
    TestSigningKeyUnavailable {
        key_id: String,
    },
    HardwareBackendUnavailable {
        slot_id: String,
    },
}

impl std::fmt::Display for SigningError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SigningError::Approval(error) => write!(f, "{error}"),
            SigningError::RouteMismatch { expected, observed } => {
                write!(
                    f,
                    "signature route mismatch: expected {expected:?}, observed {observed:?}"
                )
            }
            SigningError::KeyStoreUnavailable { path, message } => {
                write!(f, "approval key store {path:?} unavailable: {message}")
            }
            SigningError::KeyMaterialCorrupt { path, message } => {
                write!(f, "approval key store {path:?} is corrupt: {message}")
            }
            SigningError::OsKeyringUnavailable { provider, message } => {
                write!(f, "OS keyring provider {provider} unavailable: {message}")
            }
            SigningError::SignatureInvalidEncoding(message) => {
                write!(f, "invalid signature encoding: {message}")
            }
            SigningError::SignatureVerificationFailed { key_id } => {
                write!(f, "signature verification failed for key_id {key_id:?}")
            }
            SigningError::AuthorityKeyNotTrusted {
                key_id,
                authority_epoch,
                signature_route,
            } => write!(
                f,
                "authority key is not trusted for key_id {key_id:?}, authority_epoch {authority_epoch}, route {signature_route:?}"
            ),
            SigningError::TestSigningKeyUnavailable { key_id } => {
                write!(f, "in-memory test signing key {key_id:?} is verifier-only")
            }
            SigningError::HardwareBackendUnavailable { slot_id } => {
                write!(
                    f,
                    "hardware signing backend slot {slot_id:?} is reserved but unavailable"
                )
            }
        }
    }
}

impl std::error::Error for SigningError {}

impl From<ApprovalError> for SigningError {
    fn from(value: ApprovalError) -> Self {
        SigningError::Approval(value)
    }
}

fn digest(bytes: &[u8]) -> String {
    format!("sha256:{}", jcs::sha256_hex(bytes))
}

fn authority_key_lookup_key(
    key_id: &str,
    authority_epoch: u64,
    signature_route: SignatureRoute,
) -> String {
    format!("{key_id}\n{authority_epoch}\n{signature_route:?}")
}

fn authority_key_record(
    key_id: &str,
    authority_epoch: u64,
    signature_route: SignatureRoute,
    signing_key: &SigningKey,
) -> AuthorityKeyRecord {
    let verifying_key = signing_key.verifying_key();
    AuthorityKeyRecord {
        schema_id: "authority_key_record.v1".to_string(),
        key_id: key_id.to_string(),
        authority_epoch,
        signature_route,
        public_key_fingerprint: public_key_fingerprint(&verifying_key),
        verifying_key: encode_verifying_key(&verifying_key),
    }
}

fn signature_envelope(
    key_id: &str,
    authority_epoch: u64,
    signature_route: SignatureRoute,
    signed_bytes: &[u8],
    signing_key: &SigningKey,
    signature: &Signature,
) -> SignatureEnvelope {
    let verifying_key = signing_key.verifying_key();
    SignatureEnvelope {
        schema_id: "approval_signature.v1".to_string(),
        key_id: key_id.to_string(),
        authority_epoch,
        signature_route,
        public_key_fingerprint: public_key_fingerprint(&verifying_key),
        verifying_key: encode_verifying_key(&verifying_key),
        signed_payload_hash: digest(signed_bytes),
        signature: encode_signature(signature),
    }
}

pub fn verify_signature_with_authority_keys(
    card: &ApprovalCard,
    signature: &SignatureEnvelope,
    trusted_keys: &AuthorityKeySet,
    expected_key_id: &str,
) -> Result<(), SigningError> {
    if signature.schema_id != "approval_signature.v1" {
        return Err(SigningError::SignatureVerificationFailed {
            key_id: signature.key_id.clone(),
        });
    }
    if signature.key_id != expected_key_id {
        return Err(SigningError::SignatureVerificationFailed {
            key_id: signature.key_id.clone(),
        });
    }
    if signature.authority_epoch != card.payload().authority_epoch {
        return Err(SigningError::SignatureVerificationFailed {
            key_id: expected_key_id.to_string(),
        });
    }
    if signature.signature_route != card.payload().signature_route {
        return Err(SigningError::RouteMismatch {
            expected: card.payload().signature_route,
            observed: signature.signature_route,
        });
    }
    let bytes = card.canonical_bytes()?;
    if signature.signed_payload_hash != digest(&bytes) {
        return Err(SigningError::SignatureVerificationFailed {
            key_id: expected_key_id.to_string(),
        });
    }
    let Some(record) = trusted_keys.get(
        &signature.key_id,
        signature.authority_epoch,
        signature.signature_route,
    ) else {
        return Err(SigningError::AuthorityKeyNotTrusted {
            key_id: signature.key_id.clone(),
            authority_epoch: signature.authority_epoch,
            signature_route: signature.signature_route,
        });
    };
    if record.schema_id != "authority_key_record.v1"
        || record.key_id != signature.key_id
        || record.authority_epoch != signature.authority_epoch
        || record.signature_route != signature.signature_route
        || record.public_key_fingerprint != signature.public_key_fingerprint
        || record.verifying_key != signature.verifying_key
    {
        return Err(SigningError::SignatureVerificationFailed {
            key_id: expected_key_id.to_string(),
        });
    }
    let verifying_key = decode_verifying_key(&record.verifying_key)?;
    if record.public_key_fingerprint != public_key_fingerprint(&verifying_key) {
        return Err(SigningError::SignatureVerificationFailed {
            key_id: expected_key_id.to_string(),
        });
    }
    let ed25519_signature = decode_signature(&signature.signature)?;
    verifying_key
        .verify(&bytes, &ed25519_signature)
        .map_err(|_| SigningError::SignatureVerificationFailed {
            key_id: expected_key_id.to_string(),
        })
}

fn public_key_fingerprint(verifying_key: &VerifyingKey) -> String {
    digest(&verifying_key.to_bytes())
}

fn encode_verifying_key(verifying_key: &VerifyingKey) -> String {
    format!("ed25519-pub:{}", hex::encode(verifying_key.to_bytes()))
}

fn decode_verifying_key(raw: &str) -> Result<VerifyingKey, SigningError> {
    let hex = raw
        .strip_prefix("ed25519-pub:")
        .ok_or_else(|| SigningError::SignatureInvalidEncoding(raw.to_string()))?;
    let bytes = hex::decode(hex)
        .map_err(|error| SigningError::SignatureInvalidEncoding(error.to_string()))?;
    let bytes: [u8; 32] = bytes.try_into().map_err(|_| {
        SigningError::SignatureInvalidEncoding("verifying key must be 32 bytes".into())
    })?;
    VerifyingKey::from_bytes(&bytes)
        .map_err(|error| SigningError::SignatureInvalidEncoding(error.to_string()))
}

fn encode_signature(signature: &Signature) -> String {
    format!("ed25519:{}", hex::encode(signature.to_bytes()))
}

fn decode_signature(raw: &str) -> Result<Signature, SigningError> {
    let hex = raw
        .strip_prefix("ed25519:")
        .ok_or_else(|| SigningError::SignatureInvalidEncoding(raw.to_string()))?;
    let bytes = hex::decode(hex)
        .map_err(|error| SigningError::SignatureInvalidEncoding(error.to_string()))?;
    let bytes: [u8; 64] = bytes
        .try_into()
        .map_err(|_| SigningError::SignatureInvalidEncoding("signature must be 64 bytes".into()))?;
    Ok(Signature::from_bytes(&bytes))
}

fn validate_digest(value: &str) -> Result<(), ApprovalError> {
    let rest = value
        .strip_prefix("sha256:")
        .ok_or_else(|| ApprovalError::InvalidDigest(value.to_string()))?;
    if rest.len() != 64 || !rest.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(ApprovalError::InvalidDigest(value.to_string()));
    }
    Ok(())
}
