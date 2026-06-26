//! `turingos.jcs.v1` — restricted RFC 8785 canonical codec + `turingos.semantic_digest.v1`.
//!
//! Faithful Rust port of the independent oracle `pack/12_tools/jcs_v5_3_1.py`
//! (`jcs_restricted`, `json_pointer_get`, `json_pointer_delete`, `apply_canonical_sort`,
//! `strip_excluded`, `semantic_digest`). Byte-for-byte digest equality with that
//! reference is the SG-10 cross-implementation property.
//!
//! ## Profile (restricted RFC 8785)
//! - UTF-8, no BOM, no trailing newline.
//! - Object keys sorted bytewise (ASCII-only keys ⇒ bytewise == codepoint).
//! - Separators `,` and `:` with NO whitespace.
//! - Integers only — NO IEEE-754 floats / non-integer / exponent numbers.
//! - String VALUES emitted as raw UTF-8 (non-ASCII allowed); minimal JSON escaping
//!   for `"`, `\`, and control characters (matches Python `json.dumps(ensure_ascii=False)`).
//! - SHA-256 lowercase hex.
//!
//! ## Forbidden values (rejected, never silently accepted)
//! duplicate object keys; non-integer/float/exponent numbers; non-ASCII object KEY;
//! leading BOM / trailing newline; a `head_set_after` key in any payload; a new
//! self-digest-shaped field outside the closed inventory (closed-world reject).

use std::collections::BTreeMap;
use std::fmt;

use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde_json::Value;
use sha2::{Digest, Sha256};

/// Errors raised by the codec. Every forbidden value maps to a distinct variant so
/// tests can bind the precise reject reason.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum JcsError {
    /// A duplicate object key was seen during the strict parse.
    DuplicateKey(String),
    /// A number was not an exact integer (fractional, exponent, NaN/Inf, or out of i128/u128 range).
    NonIntegerNumber(String),
    /// An object key contained a non-ASCII or control character (load-bearing keys must be printable ASCII).
    NonAsciiKey(String),
    /// Input carried a leading UTF-8 BOM, a trailing newline, or other forbidden framing whitespace.
    Framing(String),
    /// The raw bytes were not valid JSON under the strict grammar.
    Malformed(String),
    /// A JSON Pointer did not resolve (never a silent no-op).
    PointerUnresolved(String),
    /// A canonical_sort target was not an array, or a node/edge element was not an object.
    CanonicalSort(String),
    /// A forbidden payload field (e.g. `head_set_after`) was present.
    ForbiddenPayloadField(String),
    /// A self-digest-shaped field (`*_digest` / `*_hash`) absent from the closed inventory.
    UnknownSelfDigestField(String),
}

impl fmt::Display for JcsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            JcsError::DuplicateKey(k) => write!(f, "turingos.jcs.v1: duplicate object key {k:?}"),
            JcsError::NonIntegerNumber(n) => {
                write!(
                    f,
                    "turingos.jcs.v1: non-integer/float/exponent number {n:?}"
                )
            }
            JcsError::NonAsciiKey(k) => {
                write!(f, "turingos.jcs.v1: non-ASCII load-bearing key {k:?}")
            }
            JcsError::Framing(m) => write!(f, "turingos.jcs.v1: framing violation: {m}"),
            JcsError::Malformed(m) => write!(f, "turingos.jcs.v1: malformed JSON: {m}"),
            JcsError::PointerUnresolved(p) => {
                write!(f, "turingos.jcs.v1: pointer did not resolve: {p}")
            }
            JcsError::CanonicalSort(m) => write!(f, "turingos.jcs.v1: canonical_sort: {m}"),
            JcsError::ForbiddenPayloadField(k) => {
                write!(f, "turingos.jcs.v1: forbidden payload field {k:?}")
            }
            JcsError::UnknownSelfDigestField(k) => {
                write!(
                    f,
                    "turingos.jcs.v1: unknown self-digest field {k:?} (closed-world reject)"
                )
            }
        }
    }
}

impl std::error::Error for JcsError {}

// ---------------------------------------------------------------------------
// Strict parse: dup-key / float / non-ASCII-key rejecting deserialization.
// ---------------------------------------------------------------------------

/// A value produced by the strict deserializer. Mirrors `serde_json::Value` but is
/// built by a `Visitor` that rejects duplicate keys, non-integer numbers, and
/// non-ASCII object keys at PARSE time (serde_json's default silently keeps the
/// last duplicate key, so we cannot rely on `from_str::<Value>`).
struct StrictValue(Value);

struct StrictVisitor;

impl<'de> Visitor<'de> for StrictVisitor {
    type Value = Value;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a strict turingos.jcs.v1 JSON value")
    }

    fn visit_bool<E>(self, v: bool) -> Result<Value, E> {
        Ok(Value::Bool(v))
    }

    fn visit_i64<E>(self, v: i64) -> Result<Value, E> {
        Ok(Value::Number(v.into()))
    }

    fn visit_i128<E: de::Error>(self, v: i128) -> Result<Value, E> {
        i64::try_from(v)
            .map(|n| Value::Number(n.into()))
            .map_err(|_| de::Error::custom(JcsError::NonIntegerNumber(v.to_string()).to_string()))
    }

    fn visit_u64<E>(self, v: u64) -> Result<Value, E> {
        Ok(Value::Number(v.into()))
    }

    fn visit_u128<E: de::Error>(self, v: u128) -> Result<Value, E> {
        u64::try_from(v)
            .map(|n| Value::Number(n.into()))
            .map_err(|_| de::Error::custom(JcsError::NonIntegerNumber(v.to_string()).to_string()))
    }

    // ANY float (1.5, 1e3, 2.0E2, NaN, ±Inf, -0.0) reaches here under serde_json's
    // default number handling — restricted profile forbids all of them.
    fn visit_f64<E: de::Error>(self, v: f64) -> Result<Value, E> {
        Err(de::Error::custom(
            JcsError::NonIntegerNumber(format!("{v}")).to_string(),
        ))
    }

    fn visit_str<E>(self, v: &str) -> Result<Value, E> {
        Ok(Value::String(v.to_owned()))
    }

    fn visit_string<E>(self, v: String) -> Result<Value, E> {
        Ok(Value::String(v))
    }

    fn visit_none<E>(self) -> Result<Value, E> {
        Ok(Value::Null)
    }

    fn visit_unit<E>(self) -> Result<Value, E> {
        Ok(Value::Null)
    }

    fn visit_seq<A>(self, mut seq: A) -> Result<Value, A::Error>
    where
        A: SeqAccess<'de>,
    {
        let mut out = Vec::new();
        while let Some(StrictValue(v)) = seq.next_element()? {
            out.push(v);
        }
        Ok(Value::Array(out))
    }

    fn visit_map<A>(self, mut map: A) -> Result<Value, A::Error>
    where
        A: MapAccess<'de>,
    {
        // preserve_order is enabled; Map preserves insertion order. We additionally
        // reject duplicate keys and non-ASCII keys here.
        let mut obj = serde_json::Map::new();
        while let Some(key) = map.next_key::<String>()? {
            if !is_printable_ascii_key(&key) {
                return Err(de::Error::custom(
                    JcsError::NonAsciiKey(key.clone()).to_string(),
                ));
            }
            let StrictValue(value) = map.next_value()?;
            if obj.contains_key(&key) {
                return Err(de::Error::custom(JcsError::DuplicateKey(key).to_string()));
            }
            obj.insert(key, value);
        }
        Ok(Value::Object(obj))
    }
}

impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_any(StrictVisitor).map(StrictValue)
    }
}

/// A printable-ASCII (0x20..=0x7E) object key, mirroring the oracle's key check.
fn is_printable_ascii_key(k: &str) -> bool {
    k.bytes().all(|b| (0x20..=0x7E).contains(&b))
}

/// Parse a JSON string under the restricted `turingos.jcs.v1` grammar, REJECTING:
/// duplicate object keys, non-integer/float/exponent numbers, non-ASCII object keys,
/// a leading BOM, and a trailing newline. (serde_json alone keeps the last duplicate
/// key silently and tolerates a trailing newline — both are caught here.)
pub fn parse_strict(input: &str) -> Result<Value, JcsError> {
    if input.starts_with('\u{feff}') {
        return Err(JcsError::Framing("leading UTF-8 BOM".into()));
    }
    if input.ends_with('\n') || input.ends_with('\r') {
        return Err(JcsError::Framing("trailing newline".into()));
    }
    // serde_json itself rejects leading zeros, NaN, Infinity, and trailing garbage.
    let mut de = serde_json::Deserializer::from_str(input);
    let StrictValue(value) = StrictValue::deserialize(&mut de).map_err(map_serde_err)?;
    de.end().map_err(map_serde_err)?;
    Ok(value)
}

/// Translate a serde_json error back into a `JcsError`. Our `Visitor` embeds the
/// `JcsError` Display text via `de::Error::custom`, so we recover the variant by
/// prefix; anything else is a generic malformed/grammar error.
fn map_serde_err(e: serde_json::Error) -> JcsError {
    let msg = e.to_string();
    if msg.contains("duplicate object key") {
        JcsError::DuplicateKey(extract_quoted(&msg))
    } else if msg.contains("non-integer/float/exponent number") {
        JcsError::NonIntegerNumber(extract_quoted(&msg))
    } else if msg.contains("non-ASCII load-bearing key") {
        JcsError::NonAsciiKey(extract_quoted(&msg))
    } else {
        JcsError::Malformed(msg)
    }
}

fn extract_quoted(msg: &str) -> String {
    // Best-effort recovery of the offending token between the first pair of quotes.
    if let Some(start) = msg.find('"')
        && let Some(rel) = msg[start + 1..].find('"')
    {
        return msg[start + 1..start + 1 + rel].to_string();
    }
    msg.to_string()
}

// ---------------------------------------------------------------------------
// Canonical serialization (jcs_restricted) + SHA-256.
// ---------------------------------------------------------------------------

/// Canonical `turingos.jcs.v1` bytes for `value`: sorted object keys (bytewise),
/// no whitespace, integers only, raw-UTF-8 string values. Errors if the value
/// contains a float or a non-ASCII object key (mirrors the oracle `check`).
pub fn canonicalize(value: &Value) -> Result<Vec<u8>, JcsError> {
    let mut out = Vec::new();
    write_canonical(value, &mut out)?;
    Ok(out)
}

fn write_canonical(value: &Value, out: &mut Vec<u8>) -> Result<(), JcsError> {
    match value {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(true) => out.extend_from_slice(b"true"),
        Value::Bool(false) => out.extend_from_slice(b"false"),
        Value::Number(n) => {
            if n.is_f64() {
                return Err(JcsError::NonIntegerNumber(n.to_string()));
            }
            // i64 / u64 integers render without exponent or fractional part.
            out.extend_from_slice(n.to_string().as_bytes());
        }
        Value::String(s) => write_json_string(s, out),
        Value::Array(items) => {
            out.push(b'[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                write_canonical(item, out)?;
            }
            out.push(b']');
        }
        Value::Object(map) => {
            // Sort keys bytewise; reject non-ASCII keys.
            let mut sorted: BTreeMap<&String, &Value> = BTreeMap::new();
            for (k, v) in map {
                if !is_printable_ascii_key(k) {
                    return Err(JcsError::NonAsciiKey(k.clone()));
                }
                sorted.insert(k, v);
            }
            out.push(b'{');
            for (i, (k, v)) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                write_json_string(k, out);
                out.push(b':');
                write_canonical(v, out)?;
            }
            out.push(b'}');
        }
    }
    Ok(())
}

/// Emit a JSON string with minimal escaping and raw (non-escaped) UTF-8 for
/// non-ASCII code points. Matches Python `json.dumps(s, ensure_ascii=False)`.
fn write_json_string(s: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for ch in s.chars() {
        match ch {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{08}' => out.extend_from_slice(b"\\b"),
            '\u{0c}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) < 0x20 => {
                out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
            }
            c => {
                let mut buf = [0u8; 4];
                out.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
            }
        }
    }
    out.push(b'"');
}

/// Lowercase-hex SHA-256 of `bytes`.
pub fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

// ---------------------------------------------------------------------------
// JSON Pointer helpers (RFC 6901), nested-aware.
// ---------------------------------------------------------------------------

fn pointer_tokens(pointer: &str) -> Result<Vec<String>, JcsError> {
    if pointer.is_empty() {
        return Ok(Vec::new());
    }
    if !pointer.starts_with('/') {
        return Err(JcsError::PointerUnresolved(format!(
            "pointer must start with '/': {pointer}"
        )));
    }
    Ok(pointer[1..]
        .split('/')
        .map(|t| t.replace("~1", "/").replace("~0", "~"))
        .collect())
}

/// Deep-clone the subtree at `pointer` (`""` = whole document). Errors if it does
/// not resolve.
pub fn json_pointer_get(obj: &Value, pointer: &str) -> Result<Value, JcsError> {
    let toks = pointer_tokens(pointer)?;
    let mut cur = obj;
    for tok in &toks {
        cur = descend(cur, tok, pointer)?;
    }
    Ok(cur.clone())
}

fn descend<'a>(cur: &'a Value, tok: &str, pointer: &str) -> Result<&'a Value, JcsError> {
    match cur {
        Value::Object(m) => m
            .get(tok)
            .ok_or_else(|| JcsError::PointerUnresolved(format!("{pointer}: missing key {tok:?}"))),
        Value::Array(a) => {
            let i: usize = tok.parse().map_err(|_| {
                JcsError::PointerUnresolved(format!("{pointer}: bad index {tok:?}"))
            })?;
            a.get(i)
                .ok_or_else(|| JcsError::PointerUnresolved(format!("{pointer}: index {i} OOB")))
        }
        _ => Err(JcsError::PointerUnresolved(format!(
            "{pointer}: cannot descend into scalar"
        ))),
    }
}

/// Return a copy of `obj` with the value at `pointer` removed. A non-resolving
/// pointer raises (never a silent no-op), matching the oracle.
pub fn json_pointer_delete(obj: &Value, pointer: &str) -> Result<Value, JcsError> {
    let toks = pointer_tokens(pointer)?;
    if toks.is_empty() {
        return Err(JcsError::PointerUnresolved(
            "cannot delete the whole document via pointer ''".into(),
        ));
    }
    let mut out = obj.clone();
    {
        let mut cur = &mut out;
        for tok in &toks[..toks.len() - 1] {
            cur = descend_mut(cur, tok, pointer)?;
        }
        let last = &toks[toks.len() - 1];
        match cur {
            Value::Object(m) => {
                if m.shift_remove(last).is_none() {
                    return Err(JcsError::PointerUnresolved(format!(
                        "{pointer}: missing key {last:?}"
                    )));
                }
            }
            Value::Array(a) => {
                let i: usize = last.parse().map_err(|_| {
                    JcsError::PointerUnresolved(format!("{pointer}: bad index {last:?}"))
                })?;
                if i >= a.len() {
                    return Err(JcsError::PointerUnresolved(format!(
                        "{pointer}: index {i} OOB"
                    )));
                }
                a.remove(i);
            }
            _ => {
                return Err(JcsError::PointerUnresolved(format!(
                    "{pointer}: parent is not a container"
                )));
            }
        }
    }
    Ok(out)
}

fn descend_mut<'a>(
    cur: &'a mut Value,
    tok: &str,
    pointer: &str,
) -> Result<&'a mut Value, JcsError> {
    match cur {
        Value::Object(m) => m
            .get_mut(tok)
            .ok_or_else(|| JcsError::PointerUnresolved(format!("{pointer}: missing key {tok:?}"))),
        Value::Array(a) => {
            let i: usize = tok.parse().map_err(|_| {
                JcsError::PointerUnresolved(format!("{pointer}: bad index {tok:?}"))
            })?;
            let len = a.len();
            a.get_mut(i).ok_or_else(|| {
                JcsError::PointerUnresolved(format!("{pointer}: index {i} OOB (len {len})"))
            })
        }
        _ => Err(JcsError::PointerUnresolved(format!(
            "{pointer}: cannot descend into scalar"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Canonical sort + exclusion + semantic_digest.
// ---------------------------------------------------------------------------

/// One `{array_pointer, sort_keys}` canonical-sort spec.
#[derive(Debug, Clone)]
pub struct CanonicalSort {
    /// JSON Pointer to the array to sort.
    pub array_pointer: String,
    /// Declared human-meaningful primary sort keys (the coarse pre-sort).
    pub sort_keys: Vec<String>,
}

/// A `turingos.semantic_digest.v1` entry: target subtree, self-exclusion pointers,
/// canonical-sort specs, and field-scoped extra excluded key names.
#[derive(Debug, Clone)]
pub struct DigestEntry {
    /// `""` selects the whole object; `/payload` selects the sibling payload subtree.
    pub target_pointer: String,
    /// Pointers deleted before hashing (a self-digest field is always in its own list).
    pub self_pointers: Vec<String>,
    /// Arrays to total-order before canonicalization (order-independent digests).
    pub canonical_sort: Vec<CanonicalSort>,
    /// Field-scoped excluded key names (UNIONed with the global set).
    pub extra_excluded_key_names: Vec<String>,
}

/// Sort each declared array into a TOTAL order: primary by the declared `sort_keys`
/// (each value serialized canonically; absent => `null`), tie-broken on the FULL
/// canonical bytes of each element. The full-byte tie-break makes this a strict
/// total order so duplicate ids / parallel edges cannot reintroduce order-dependence.
/// Applied BEFORE pruning so the sort keys still exist.
pub fn apply_canonical_sort(obj: &Value, specs: &[CanonicalSort]) -> Result<Value, JcsError> {
    let mut out = obj.clone();
    for spec in specs {
        let toks = pointer_tokens(&spec.array_pointer)?;
        if toks.is_empty() {
            return Err(JcsError::CanonicalSort(
                "array_pointer '' is not an array target".into(),
            ));
        }
        // Locate the array (mutable).
        let arr_val = {
            let mut cur = &mut out;
            for tok in &toks {
                cur = descend_mut(cur, tok, &spec.array_pointer)?;
            }
            cur
        };
        let arr = match arr_val {
            Value::Array(a) => a,
            _ => {
                return Err(JcsError::CanonicalSort(format!(
                    "target {} is not an array",
                    spec.array_pointer
                )));
            }
        };
        for item in arr.iter() {
            if !item.is_object() {
                return Err(JcsError::CanonicalSort(format!(
                    "{} contains a non-object element; graph nodes/edges must be objects",
                    spec.array_pointer
                )));
            }
        }
        // Build (primary, full_canonical_bytes) sort key per element.
        let mut decorated: Vec<(Vec<Vec<u8>>, Vec<u8>, Value)> = Vec::with_capacity(arr.len());
        for item in arr.drain(..) {
            let mut primary: Vec<Vec<u8>> = Vec::with_capacity(spec.sort_keys.len());
            for k in &spec.sort_keys {
                let v = item.get(k).cloned().unwrap_or(Value::Null);
                primary.push(canonicalize(&v)?);
            }
            let full = canonicalize(&item)?;
            decorated.push((primary, full, item));
        }
        // (primary, full) is a strict total order; primary leads, full bytes break ties.
        decorated.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
        *arr = decorated.into_iter().map(|(_, _, item)| item).collect();
    }
    Ok(out)
}

/// Recursively drop every dict key whose name is in `excluded`.
pub fn strip_excluded(value: &Value, excluded: &[String]) -> Value {
    match value {
        Value::Object(m) => {
            let mut obj = serde_json::Map::new();
            for (k, v) in m {
                if !excluded.iter().any(|e| e == k) {
                    obj.insert(k.clone(), strip_excluded(v, excluded));
                }
            }
            Value::Object(obj)
        }
        Value::Array(a) => Value::Array(a.iter().map(|v| strip_excluded(v, excluded)).collect()),
        other => other.clone(),
    }
}

/// `turingos.semantic_digest.v1` — the frozen 5-step algorithm:
/// 1. `sub = json_pointer_get(obj, entry.target_pointer)`
/// 2. `sub = apply_canonical_sort(sub, entry.canonical_sort)`
/// 3. delete each `entry.self_pointers` (non-resolving pointer ⇒ Err)
/// 4. drop keys in `global_excluded ∪ entry.extra_excluded_key_names` (recursive)
/// 5. `lowercase_hex(sha256(canonicalize(sub)))`
pub fn semantic_digest(
    obj: &Value,
    entry: &DigestEntry,
    global_excluded: &[String],
) -> Result<String, JcsError> {
    let mut sub = json_pointer_get(obj, &entry.target_pointer)?;
    sub = apply_canonical_sort(&sub, &entry.canonical_sort)?;
    for ptr in &entry.self_pointers {
        sub = json_pointer_delete(&sub, ptr)?;
    }
    let mut excluded: Vec<String> = global_excluded.to_vec();
    excluded.extend(entry.extra_excluded_key_names.iter().cloned());
    sub = strip_excluded(&sub, &excluded);
    Ok(sha256_hex(&canonicalize(&sub)?))
}

// ---------------------------------------------------------------------------
// Closed-world payload guards.
// ---------------------------------------------------------------------------

/// Reject a payload that embeds a forbidden field anywhere (recursively). Today the
/// single forbidden field is `head_set_after` — an event can never embed its own OID.
pub fn reject_forbidden_payload_fields(value: &Value) -> Result<(), JcsError> {
    const FORBIDDEN: &[&str] = &["head_set_after"];
    match value {
        Value::Object(m) => {
            for (k, v) in m {
                if FORBIDDEN.contains(&k.as_str()) {
                    return Err(JcsError::ForbiddenPayloadField(k.clone()));
                }
                reject_forbidden_payload_fields(v)?;
            }
            Ok(())
        }
        Value::Array(a) => {
            for v in a {
                reject_forbidden_payload_fields(v)?;
            }
            Ok(())
        }
        _ => Ok(()),
    }
}

/// Closed-world check: reject any digest-shaped field (`*_digest` / `*_hash`) at the
/// top level of `value` whose name is not in the ratified `known` inventory. A new
/// self-digest field WITHOUT an entry in `semantic_digest_v5_3_1.json` is an SG-81
/// failure (closed-world reject).
pub fn reject_unknown_self_digest_fields(value: &Value, known: &[String]) -> Result<(), JcsError> {
    if let Value::Object(m) = value {
        for k in m.keys() {
            let looks_like_digest = k.ends_with("_digest") || k.ends_with("_hash");
            if looks_like_digest && !known.iter().any(|kn| kn == k) {
                return Err(JcsError::UnknownSelfDigestField(k.clone()));
            }
        }
    }
    Ok(())
}
