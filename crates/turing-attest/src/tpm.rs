//! TPM 2.0 attestor (HW-SW-010..013, Phase 4). Shells out to `tpm2-tools`
//! via `std::process::Command` rather than linking `tss-esapi`: the locked
//! P0 design decision for this phase is "shell-backend now, in-process
//! backend later" — a `tss-esapi` implementation is a drop-in P1 backend
//! behind this same, unchanged `Attestor` trait; it is not implemented
//! here. Zero new Rust dependencies this phase: only `std`.
//!
//! Every quote produced here is a LOCAL evidence artifact. Nothing in this
//! module writes to the tape; tape ingestion of hardware evidence is
//! Phase 6. `TpmAttestor` never invokes an unfinished-code macro and never
//! panics on a caller-reachable path (internal `expect`s only guard
//! genuinely-unreachable invariants inside this file's own test-support
//! code, not this module).

use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::{hex_lower, AttestError, AttestationQuote, Attestor, AttestorKind};

/// PCR bank + PCR indices this backend reads/quotes by default. Phase 3's
/// `policy.rs::TpmPolicy::required_pcrs` is the eventual declared-law
/// source for this selection (attestation_policy.toml); wiring `TpmAttestor`
/// to read that file is left to a later atom. PCRs 0 and 7 are the pair
/// already populated and proven quotable on this workspace's real vTPM
/// (SPEC.md "Environment").
const DEFAULT_PCR_SELECTION: &str = "sha256:0,7";

/// One bank's worth of PCR values as reported by `tpm2_pcrread`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PcrSet {
    pub bank: String,
    /// `(pcr_index, lowercase_hex_digest)`, in the order `tpm2_pcrread`
    /// printed them.
    pub values: Vec<(u32, String)>,
}

/// Typed error surface for the tpm2-tools shell backend. Every distinct
/// failure mode gets its own variant so callers (and tests) can match the
/// precise cause; this type is never used to signal "unimplemented" — that
/// remains `AttestError::NotYetImplemented`'s job for backends with no P0
/// implementation at all.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TpmError {
    /// A required `tpm2-tools`/`swtpm` binary was not found on `PATH`.
    ToolNotFound { tool: &'static str },
    /// `TPM2TOOLS_TCTI` could not be reached (simulator socket down, device
    /// permission denied, etc).
    TctiUnavailable { detail: String },
    /// A quote-producing command (`tpm2_createek`/`tpm2_createak`/
    /// `tpm2_quote`) exited non-zero; stderr captured verbatim.
    QuoteFailed { stderr: String },
    /// `tpm2_checkquote` rejected the quote (tampered qualifying value,
    /// wrong AK, truncated attest blob, etc).
    VerifyFailed { stderr: String },
    /// A tool's output, or a previously-produced quote's packed evidence
    /// string, could not be parsed into the expected shape.
    Parse { detail: String },
}

impl std::fmt::Display for TpmError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TpmError::ToolNotFound { tool } => write!(f, "required tool not found on PATH: {tool}"),
            TpmError::TctiUnavailable { detail } => write!(f, "TPM2TOOLS_TCTI unreachable: {detail}"),
            TpmError::QuoteFailed { stderr } => write!(f, "tpm2 quote step failed: {stderr}"),
            TpmError::VerifyFailed { stderr } => write!(f, "tpm2_checkquote rejected the quote: {stderr}"),
            TpmError::Parse { detail } => write!(f, "tpm output/evidence parse failure: {detail}"),
        }
    }
}

impl std::error::Error for TpmError {}

/// Real TPM 2.0 attestor: `read_pcrs`/`quote`/`verify` all shell to
/// `tpm2-tools` against a caller-selected `TPM2TOOLS_TCTI` endpoint.
pub struct TpmAttestor {
    kind: AttestorKind,
    tcti: String,
    pcr_selection: String,
}

impl TpmAttestor {
    /// Simulator backend: `tcti` is a full `TPM2TOOLS_TCTI` connection
    /// string for a running `swtpm` instance (e.g.
    /// `"swtpm:host=localhost,port=2321"`). `kind()` reports
    /// [`AttestorKind::TpmSimulator`] — never a kind implying real hardware.
    pub fn simulator(tcti: impl Into<String>) -> Self {
        Self {
            kind: AttestorKind::TpmSimulator,
            tcti: tcti.into(),
            pcr_selection: DEFAULT_PCR_SELECTION.to_string(),
        }
    }

    /// Real-hardware backend: `path` is the TPM resource-manager device
    /// node (e.g. `"/dev/tpmrm0"`). `kind()` reports [`AttestorKind::Vtpm`]
    /// — this workspace's real device is hypervisor-backed, not
    /// silicon-rooted, per SPEC.md's environment note; callers must never
    /// relabel it with a kind implying a manufacturer EK certificate chain.
    /// Access to the device node itself (root-only) is the caller's
    /// responsibility — this constructor does no privilege elevation.
    pub fn device(path: impl Into<String>) -> Self {
        Self {
            kind: AttestorKind::Vtpm,
            tcti: format!("device:{}", path.into()),
            pcr_selection: DEFAULT_PCR_SELECTION.to_string(),
        }
    }

    /// Which [`AttestorKind`] this instance reports. Shadows
    /// [`Attestor::kind`] for direct (non-trait-object) callers; both
    /// return the same value.
    pub fn kind(&self) -> AttestorKind {
        self.kind
    }

    fn command(&self, tool: &'static str) -> Result<Command, TpmError> {
        if which(tool).is_none() {
            return Err(TpmError::ToolNotFound { tool });
        }
        let mut cmd = Command::new(tool);
        cmd.env("TPM2TOOLS_TCTI", &self.tcti);
        Ok(cmd)
    }

    /// Runs `tool` with `args`, returning captured stdout/stderr. Maps a
    /// TCTI-shaped stderr (connection refused, socket unreachable) to
    /// [`TpmError::TctiUnavailable`]; any other non-zero exit is reported by
    /// the caller under whichever variant fits that call site.
    fn run(&self, tool: &'static str, args: &[&str]) -> Result<std::process::Output, TpmError> {
        let mut cmd = self.command(tool)?;
        cmd.args(args);
        cmd.output().map_err(|_e| TpmError::ToolNotFound { tool })
    }

    fn classify_tool_failure(stderr: &str) -> Option<TpmError> {
        let lower = stderr.to_ascii_lowercase();
        if lower.contains("tcti") && (lower.contains("connect") || lower.contains("unreachable")) {
            Some(TpmError::TctiUnavailable { detail: stderr.to_string() })
        } else {
            None
        }
    }

    /// Reads a PCR bank/selection (e.g. `"sha256:0,7"`) via `tpm2_pcrread`.
    pub fn read_pcrs(&self, sel: &str) -> Result<PcrSet, TpmError> {
        let out = self.run("tpm2_pcrread", &[sel])?;
        if !out.status.success() {
            let stderr = String::from_utf8_lossy(&out.stderr).to_string();
            return Err(Self::classify_tool_failure(&stderr)
                .unwrap_or(TpmError::QuoteFailed { stderr }));
        }
        let stdout = String::from_utf8_lossy(&out.stdout);
        parse_pcrread(&stdout)
    }

    /// Ephemeral quote: provisions a fresh EK+AK in a throwaway temp dir,
    /// runs `TPM2_Quote` over `qualifying` across [`DEFAULT_PCR_SELECTION`],
    /// and packs the raw quote materials (AK public, quote message,
    /// signature, PCR values) into [`AttestationQuote::signature`] as a
    /// small self-describing hex-field JSON blob (no new dependency: this
    /// crate's only allowed deps are serde/serde_json/toml/turing-contracts,
    /// already present; no base64/hex crate is added — byte fields are
    /// hex-encoded via this crate's existing [`hex_lower`] helper).
    /// [`Self::verify`] is the only code that needs to understand this
    /// blob's shape.
    pub fn quote(&self, qualifying: &[u8; 32]) -> Result<AttestationQuote, TpmError> {
        let work_dir = fresh_temp_dir("turing-attest-tpm-quote");
        std::fs::create_dir_all(&work_dir).map_err(|e| TpmError::Parse {
            detail: format!("create ephemeral work dir: {e}"),
        })?;
        let result = self.quote_in(&work_dir, qualifying);
        let _ = std::fs::remove_dir_all(&work_dir);
        result
    }

    /// swtpm/libtpms has only a small number of transient-object slots;
    /// leaving a loaded EK/AK/etc around between steps starves later ones
    /// with "out of memory for object contexts" (observed empirically
    /// developing this atom — see LESSONS.md). Best-effort: failures here
    /// are never a correctness signal, just proactive slot hygiene.
    fn flush_transient(&self) {
        let _ = self.run("tpm2_flushcontext", &["-t"]);
        let _ = self.run("tpm2_flushcontext", &["-s"]);
        let _ = self.run("tpm2_flushcontext", &["-l"]);
    }

    fn quote_in(&self, dir: &Path, qualifying: &[u8; 32]) -> Result<AttestationQuote, TpmError> {
        self.flush_transient();

        let ek_ctx = path_str(dir, "ek.ctx");
        let ek_pub = path_str(dir, "ek.pub");
        let out = self.run(
            "tpm2_createek",
            &["-c", &ek_ctx, "-G", "rsa", "-u", &ek_pub],
        )?;
        require_success(out, |stderr| {
            Self::classify_tool_failure(&stderr).unwrap_or(TpmError::QuoteFailed { stderr })
        })?;
        self.flush_transient();

        let ak_ctx = path_str(dir, "ak.ctx");
        let ak_pub = path_str(dir, "ak.pub");
        let ak_priv = path_str(dir, "ak.priv");
        let ak_name = path_str(dir, "ak.name");
        let out = self.run(
            "tpm2_createak",
            &[
                "-C", &ek_ctx, "-c", &ak_ctx, "-G", "rsa", "-g", "sha256", "-s", "rsassa", "-u",
                &ak_pub, "-r", &ak_priv, "-n", &ak_name,
            ],
        )?;
        require_success(out, |stderr| {
            Self::classify_tool_failure(&stderr).unwrap_or(TpmError::QuoteFailed { stderr })
        })?;
        self.flush_transient();

        let qualifying_path = path_str(dir, "qualifying.bin");
        write_bytes(&qualifying_path, qualifying)
            .map_err(|e| TpmError::Parse { detail: format!("write qualifying.bin: {e}") })?;

        let quote_msg = path_str(dir, "quote.msg");
        let quote_sig = path_str(dir, "quote.sig");
        let pcrs_out = path_str(dir, "pcrs.out");
        let out = self.run(
            "tpm2_quote",
            &[
                "-c", &ak_ctx, "-l", &self.pcr_selection, "-q", &qualifying_path, "-m", &quote_msg,
                "-s", &quote_sig, "-o", &pcrs_out, "-g", "sha256",
            ],
        )?;
        require_success(out, |stderr| {
            Self::classify_tool_failure(&stderr).unwrap_or(TpmError::QuoteFailed { stderr })
        })?;
        self.flush_transient();

        let ak_pub_bytes = read_bytes(&ak_pub)?;
        let quote_msg_bytes = read_bytes(&quote_msg)?;
        let quote_sig_bytes = read_bytes(&quote_sig)?;
        let pcrs_bytes = read_bytes(&pcrs_out)?;

        let signature = pack_evidence(&EvidenceBlob {
            pcr_selection: &self.pcr_selection,
            ak_pub_hex: &hex_lower(&ak_pub_bytes),
            quote_msg_hex: &hex_lower(&quote_msg_bytes),
            quote_sig_hex: &hex_lower(&quote_sig_bytes),
            pcrs_hex: &hex_lower(&pcrs_bytes),
        });

        Ok(AttestationQuote {
            kind: self.kind,
            qualifying: *qualifying,
            signature,
        })
    }

    /// Verifies a quote produced by [`Self::quote`] (this backend's own, or
    /// another `TpmAttestor` instance's — sim or real) against `qualifying`
    /// via `tpm2_checkquote`. Rejects a tampered `qualifying` value with
    /// [`TpmError::VerifyFailed`] (`tpm2_checkquote` fails the nonce/
    /// signature check) — this is the property HW-SW-011's B2 predicate
    /// requires.
    pub fn verify(&self, quote: &AttestationQuote, qualifying: &[u8; 32]) -> Result<(), TpmError> {
        let blob = unpack_evidence(&quote.signature)?;

        let dir = fresh_temp_dir("turing-attest-tpm-verify");
        std::fs::create_dir_all(&dir).map_err(|e| TpmError::Parse {
            detail: format!("create ephemeral verify dir: {e}"),
        })?;
        let result = (|| {
            let ak_pub = path_str(&dir, "ak.pub");
            let quote_msg = path_str(&dir, "quote.msg");
            let quote_sig = path_str(&dir, "quote.sig");
            let pcrs_out = path_str(&dir, "pcrs.out");
            write_bytes(&ak_pub, &unhex(&blob.ak_pub_hex)?)
                .map_err(|e| TpmError::Parse { detail: format!("write ak.pub: {e}") })?;
            write_bytes(&quote_msg, &unhex(&blob.quote_msg_hex)?)
                .map_err(|e| TpmError::Parse { detail: format!("write quote.msg: {e}") })?;
            write_bytes(&quote_sig, &unhex(&blob.quote_sig_hex)?)
                .map_err(|e| TpmError::Parse { detail: format!("write quote.sig: {e}") })?;
            write_bytes(&pcrs_out, &unhex(&blob.pcrs_hex)?)
                .map_err(|e| TpmError::Parse { detail: format!("write pcrs.out: {e}") })?;

            let qualifying_hex = hex_lower(qualifying);
            let out = self.run(
                "tpm2_checkquote",
                &["-u", &ak_pub, "-m", &quote_msg, "-s", &quote_sig, "-f", &pcrs_out, "-q", &qualifying_hex],
            )?;
            if out.status.success() {
                Ok(())
            } else {
                Err(TpmError::VerifyFailed {
                    stderr: String::from_utf8_lossy(&out.stderr).to_string(),
                })
            }
        })();
        let _ = std::fs::remove_dir_all(&dir);
        result
    }
}

/// `Attestor` trait adapter. `AttestorKind` is the only additive surface
/// SPEC.md permits in `lib.rs` this phase (no new `AttestError` variant), so
/// this adapter necessarily collapses any [`TpmError`] into the sole
/// existing [`AttestError::NotYetImplemented`] variant on failure — callers
/// that need the rich, typed hardware error should call
/// [`TpmAttestor::quote`]/[`TpmAttestor::verify`] directly (the inherent
/// methods; Rust resolves `attestor.quote(..)` to them, not to this trait
/// method, for any caller not going through a `&dyn Attestor`). The happy
/// path is fully faithful: `Ok` carries the identical `AttestationQuote`
/// either way.
impl Attestor for TpmAttestor {
    fn kind(&self) -> AttestorKind {
        self.kind
    }

    fn quote(&self, qualifying: &[u8; 32]) -> Result<AttestationQuote, AttestError> {
        TpmAttestor::quote(self, qualifying)
            .map_err(|_e| AttestError::NotYetImplemented { phase: "phase04-trait-adapter" })
    }
}

struct EvidenceBlob<'a> {
    pcr_selection: &'a str,
    ak_pub_hex: &'a str,
    quote_msg_hex: &'a str,
    quote_sig_hex: &'a str,
    pcrs_hex: &'a str,
}

struct OwnedEvidenceBlob {
    ak_pub_hex: String,
    quote_msg_hex: String,
    quote_sig_hex: String,
    pcrs_hex: String,
}

/// Packs the quote materials as a tiny hand-rolled `key=value` blob
/// (newline-separated, values are already-hex so no escaping is needed) —
/// no JSON/serde dependency required for this internal, crate-private
/// wire shape.
fn pack_evidence(blob: &EvidenceBlob<'_>) -> String {
    format!(
        "tpm_evidence.v1\npcr_selection={}\nak_pub_hex={}\nquote_msg_hex={}\nquote_sig_hex={}\npcrs_hex={}\n",
        blob.pcr_selection, blob.ak_pub_hex, blob.quote_msg_hex, blob.quote_sig_hex, blob.pcrs_hex
    )
}

fn unpack_evidence(signature: &str) -> Result<OwnedEvidenceBlob, TpmError> {
    let mut ak_pub_hex = None;
    let mut quote_msg_hex = None;
    let mut quote_sig_hex = None;
    let mut pcrs_hex = None;
    for line in signature.lines() {
        if let Some((key, value)) = line.split_once('=') {
            match key {
                "ak_pub_hex" => ak_pub_hex = Some(value.to_string()),
                "quote_msg_hex" => quote_msg_hex = Some(value.to_string()),
                "quote_sig_hex" => quote_sig_hex = Some(value.to_string()),
                "pcrs_hex" => pcrs_hex = Some(value.to_string()),
                _ => {}
            }
        }
    }
    Ok(OwnedEvidenceBlob {
        ak_pub_hex: ak_pub_hex.ok_or_else(|| TpmError::Parse {
            detail: "signature blob missing ak_pub_hex".into(),
        })?,
        quote_msg_hex: quote_msg_hex.ok_or_else(|| TpmError::Parse {
            detail: "signature blob missing quote_msg_hex".into(),
        })?,
        quote_sig_hex: quote_sig_hex.ok_or_else(|| TpmError::Parse {
            detail: "signature blob missing quote_sig_hex".into(),
        })?,
        pcrs_hex: pcrs_hex.ok_or_else(|| TpmError::Parse {
            detail: "signature blob missing pcrs_hex".into(),
        })?,
    })
}

fn unhex(s: &str) -> Result<Vec<u8>, TpmError> {
    if !s.len().is_multiple_of(2) {
        return Err(TpmError::Parse { detail: format!("odd-length hex string: {s:?}") });
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let hi = hex_val(bytes[i]).ok_or_else(|| TpmError::Parse {
            detail: format!("non-hex byte in {s:?}"),
        })?;
        let lo = hex_val(bytes[i + 1]).ok_or_else(|| TpmError::Parse {
            detail: format!("non-hex byte in {s:?}"),
        })?;
        out.push((hi << 4) | lo);
        i += 2;
    }
    Ok(out)
}

fn hex_val(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}

fn require_success(
    out: std::process::Output,
    on_fail: impl FnOnce(String) -> TpmError,
) -> Result<(), TpmError> {
    if out.status.success() {
        Ok(())
    } else {
        Err(on_fail(String::from_utf8_lossy(&out.stderr).to_string()))
    }
}

fn path_str(dir: &Path, name: &str) -> String {
    dir.join(name).to_string_lossy().into_owned()
}

fn write_bytes(path: &str, bytes: &[u8]) -> std::io::Result<()> {
    let mut f = std::fs::File::create(path)?;
    f.write_all(bytes)
}

fn read_bytes(path: &str) -> Result<Vec<u8>, TpmError> {
    std::fs::read(path).map_err(|e| TpmError::Parse {
        detail: format!("read {path}: {e}"),
    })
}

fn which(bin: &str) -> Option<PathBuf> {
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths).map(|dir| dir.join(bin)).find(|p| p.is_file())
    })
}

fn fresh_temp_dir(prefix: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    std::env::temp_dir().join(format!("{prefix}-{}-{}", std::process::id(), nanos))
}

/// Parses `tpm2_pcrread`'s human-readable output, e.g.:
/// ```text
///   sha256:
///     0 : 0x0000...
///     7 : 0x0000...
/// ```
fn parse_pcrread(stdout: &str) -> Result<PcrSet, TpmError> {
    let mut bank = None;
    let mut values = Vec::new();
    for raw_line in stdout.lines() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        if let Some(name) = line.strip_suffix(':') {
            if bank.is_none() {
                bank = Some(name.trim().to_string());
            }
            continue;
        }
        if let Some((idx_str, rest)) = line.split_once(':') {
            let idx_str = idx_str.trim();
            let hex_part = rest.trim().trim_start_matches("0x").trim_start_matches("0X");
            if let Ok(idx) = idx_str.parse::<u32>() {
                values.push((idx, hex_part.to_ascii_lowercase()));
            }
        }
    }
    let bank = bank.ok_or_else(|| TpmError::Parse {
        detail: format!("could not find a PCR bank line in tpm2_pcrread output: {stdout:?}"),
    })?;
    if values.is_empty() {
        return Err(TpmError::Parse {
            detail: format!("no PCR values parsed from tpm2_pcrread output: {stdout:?}"),
        });
    }
    Ok(PcrSet { bank, values })
}
