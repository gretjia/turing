//! SG-10 — Canonical codec cross-implementation.
//!
//! Binds the RATIFIED pack oracle data (`pack/03_contracts/semantic_digest_v5_3_1.json`)
//! and asserts that the Rust `turingos.jcs.v1` codec + `semantic_digest` produce
//! byte-identical digests to the independent Python reference (`pack/12_tools/jcs_v5_3_1.py`),
//! and that every forbidden value is REJECTED (returns `Err`) at the codec parse boundary.
//!
//! Anti-Goodhart: the 7 expected digests are LOADED from the pack file (not hardcoded);
//! the negative cases drive the real reject path (`parse_strict` / closed-world check),
//! never `assert!(true)`.
//!
//! Properties mirrored from `pack/12_tools/check_semantic_digest_v5_3_1.py`:
//!   P1 determinism, P2 stability (noise_ops), P3 sensitivity (change_ops),
//!   P_order (permute canonical_sort arrays), P_target (independent payload digest).

use std::path::PathBuf;

use serde_json::{Value, json};
use turing_contracts::jcs::{self, DigestEntry, JcsError};

/// Trusted load of the ratified vectors file. The vectors file is part of the
/// signed pack and contains no duplicate keys, so a plain `serde_json` load is
/// acceptable HERE (the codec-under-test enforces rejections on its OWN parse path).
fn load_spec() -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../pack/03_contracts/semantic_digest_v5_3_1.json");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("cannot read pack vectors at {}: {e}", path.display()));
    serde_json::from_str(&text).expect("pack vectors parse as JSON")
}

/// RFC 6901 token split (mirrors the Python `_tokens`), used by the test's own
/// pointer-set helper for applying noise_ops / change_ops.
fn pointer_tokens(pointer: &str) -> Vec<String> {
    if pointer.is_empty() {
        return Vec::new();
    }
    assert!(
        pointer.starts_with('/'),
        "JSON pointer must start with '/': {pointer}"
    );
    pointer[1..]
        .split('/')
        .map(|t| t.replace("~1", "/").replace("~0", "~"))
        .collect()
}

/// Set the value at `pointer` (RFC 6901), returning a mutated clone. Mirrors the
/// Python `pointer_set` used by the assertion harness for noise/change ops.
fn pointer_set(obj: &Value, pointer: &str, value: Value) -> Value {
    let toks = pointer_tokens(pointer);
    let mut out = obj.clone();
    let mut cur = &mut out;
    for tok in &toks[..toks.len() - 1] {
        cur = match cur {
            Value::Object(m) => m.get_mut(tok).expect("noise/change pointer resolves"),
            Value::Array(a) => a
                .get_mut(tok.parse::<usize>().expect("array index"))
                .expect("array index in range"),
            _ => panic!("cannot descend into scalar at {pointer}"),
        };
    }
    let last = &toks[toks.len() - 1];
    match cur {
        Value::Object(m) => {
            m.insert(last.clone(), value);
        }
        Value::Array(a) => {
            let i = last.parse::<usize>().expect("array index");
            a[i] = value;
        }
        _ => panic!("parent at {pointer} is not a container"),
    }
    out
}

fn json_pointer_get(obj: &Value, pointer: &str) -> Value {
    let toks = pointer_tokens(pointer);
    let mut cur = obj;
    for tok in &toks {
        cur = match cur {
            Value::Object(m) => m.get(tok).expect("pointer resolves (object)"),
            Value::Array(a) => a
                .get(tok.parse::<usize>().expect("array index"))
                .expect("pointer resolves (array)"),
            _ => panic!("cannot descend into scalar at {pointer}"),
        };
    }
    cur.clone()
}

/// Build a `DigestEntry` from a vector's `entry` object in the pack file.
fn entry_from_json(entry: &Value, extra_excluded_from_field: &[String]) -> DigestEntry {
    let target_pointer = entry
        .get("target_pointer")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let self_pointers = entry
        .get("self_pointers")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .map(|v| v.as_str().expect("self_pointer is a string").to_string())
                .collect()
        })
        .unwrap_or_default();
    let canonical_sort = entry
        .get("canonical_sort")
        .and_then(Value::as_array)
        .map(|specs| {
            specs
                .iter()
                .map(|spec| {
                    let array_pointer = spec
                        .get("array_pointer")
                        .and_then(Value::as_str)
                        .expect("canonical_sort.array_pointer")
                        .to_string();
                    let sort_keys = spec
                        .get("sort_keys")
                        .and_then(Value::as_array)
                        .expect("canonical_sort.sort_keys")
                        .iter()
                        .map(|v| v.as_str().expect("sort_key string").to_string())
                        .collect();
                    jcs::CanonicalSort {
                        array_pointer,
                        sort_keys,
                    }
                })
                .collect()
        })
        .unwrap_or_default();

    // Per-vector extra_excluded comes from the entry; some fields (projection/visible_card)
    // also declare it at the digest_field level. The vectors embed it on `entry`.
    let mut extra_excluded: Vec<String> = entry
        .get("extra_excluded_key_names")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .map(|v| v.as_str().expect("extra_excluded string").to_string())
                .collect()
        })
        .unwrap_or_default();
    for k in extra_excluded_from_field {
        if !extra_excluded.contains(k) {
            extra_excluded.push(k.clone());
        }
    }

    DigestEntry {
        target_pointer,
        self_pointers,
        canonical_sort,
        extra_excluded_key_names: extra_excluded,
    }
}

/// The global excluded key set, read from the pack file (not hardcoded).
fn global_excluded(spec: &Value) -> Vec<String> {
    spec["global"]["excluded_key_names"]
        .as_array()
        .expect("global.excluded_key_names array")
        .iter()
        .map(|v| v.as_str().expect("excluded key string").to_string())
        .collect()
}

#[test]
fn all_seven_canonical_vectors_match_oracle() {
    let spec = load_spec();
    let glob = global_excluded(&spec);
    let vectors = spec["canonical_vectors"]
        .as_array()
        .expect("canonical_vectors array");
    assert_eq!(vectors.len(), 7, "pack must declare exactly 7 vectors");

    // The digest_field-level extra_excluded_key_names keyed by field name, so a vector
    // whose `entry` omits them still picks them up (matches semantic_digest_v5_3_1.json).
    let mut field_extra: std::collections::BTreeMap<String, Vec<String>> = Default::default();
    for df in spec["digest_fields"].as_array().expect("digest_fields") {
        let field = df["field"].as_str().expect("field name").to_string();
        let extra = df["entry"]
            .get("extra_excluded_key_names")
            .and_then(Value::as_array)
            .map(|a| {
                a.iter()
                    .map(|v| v.as_str().unwrap().to_string())
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        field_extra.insert(field, extra);
    }

    for vec in vectors {
        let name = vec["name"].as_str().expect("vector name");
        let field = vec["field"].as_str().expect("vector field");
        let entry_json = &vec["entry"];
        let field_default_extra = field_extra.get(field).cloned().unwrap_or_default();
        let entry = entry_from_json(entry_json, &field_default_extra);

        let base = &vec["input"];
        let expected = vec["expected_semantic_digest"]
            .as_str()
            .expect("expected_semantic_digest");

        // ---- pinned digest + P1 determinism ----
        let d1 = jcs::semantic_digest(base, &entry, &glob)
            .unwrap_or_else(|e| panic!("[{name}] semantic_digest errored: {e:?}"));
        let d2 = jcs::semantic_digest(base, &entry, &glob).unwrap();
        assert_eq!(d1, d2, "[{name}] P1 determinism (re-run differs)");
        assert_eq!(
            d1, expected,
            "[{name}] pinned digest mismatch vs ratified oracle"
        );

        // ---- P2 stability: noise_ops must NOT move the digest ----
        let mut noised = base.clone();
        for op in vec["noise_ops"].as_array().expect("noise_ops") {
            let ptr = op["pointer"].as_str().expect("noise pointer");
            noised = pointer_set(&noised, ptr, op["value"].clone());
        }
        let dn = jcs::semantic_digest(&noised, &entry, &glob).unwrap();
        assert_eq!(
            dn, d1,
            "[{name}] P2 stability — excluded-field noise moved digest"
        );

        // ---- P3 sensitivity: change_ops MUST move the digest ----
        let mut changed = base.clone();
        for op in vec["change_ops"].as_array().expect("change_ops") {
            let ptr = op["pointer"].as_str().expect("change pointer");
            changed = pointer_set(&changed, ptr, op["value"].clone());
        }
        let dc = jcs::semantic_digest(&changed, &entry, &glob).unwrap();
        assert_ne!(
            dc, d1,
            "[{name}] P3 sensitivity — semantic change did not move digest"
        );

        // ---- P_order: permuting (reversing) each canonical_sort array keeps the digest ----
        for cs in &entry.canonical_sort {
            let arr = json_pointer_get(base, &cs.array_pointer);
            let arr = arr.as_array().expect("canonical_sort target is an array");
            if arr.len() >= 2 {
                let reversed: Vec<Value> = arr.iter().rev().cloned().collect();
                let permuted = pointer_set(base, &cs.array_pointer, Value::Array(reversed));
                let dp = jcs::semantic_digest(&permuted, &entry, &glob).unwrap();
                assert_eq!(
                    dp, d1,
                    "[{name}] P_order — permuting {} moved digest",
                    cs.array_pointer
                );
            }
        }

        // ---- P_target: content_digest/payload_hash == independent sha256(JCS(payload)) ----
        if vec
            .get("independent_equals_target")
            .and_then(Value::as_bool)
            .unwrap_or(false)
        {
            let payload = json_pointer_get(base, &entry.target_pointer);
            let indep_entry = DigestEntry {
                target_pointer: String::new(),
                self_pointers: entry.self_pointers.clone(),
                canonical_sort: entry.canonical_sort.clone(),
                extra_excluded_key_names: entry.extra_excluded_key_names.clone(),
            };
            let indep = jcs::semantic_digest(&payload, &indep_entry, &glob).unwrap();
            assert_eq!(
                indep, d1,
                "[{name}] P_target — digest != independent sha256(JCS(payload))"
            );

            // Direct cross-check at the byte layer: content_digest == payload_hash ==
            // sha256(JCS(payload)). The payload carries a non-semantic `human_summary`
            // (globally excluded), so the load-bearing bytes are the payload with the
            // excluded keys stripped — exactly what the digest mechanism hashes.
            let mut excl: Vec<String> = glob.clone();
            excl.extend(entry.extra_excluded_key_names.iter().cloned());
            let stripped = jcs::strip_excluded(&payload, &excl);
            let raw = jcs::canonicalize(&stripped).unwrap();
            let direct = jcs::sha256_hex(&raw);
            assert_eq!(
                direct, d1,
                "[{name}] P_target — sha256(JCS(payload\\excluded)) mismatch"
            );
        }
    }
}

// ---------------------------------------------------------------------------
// Forbidden-value rejection. Each MUST return Err from the codec parse/closure
// path — never be silently accepted. These drive the REAL reject path.
// ---------------------------------------------------------------------------

#[test]
fn rejects_duplicate_object_keys() {
    // serde_json silently keeps the last dup key; the codec must NOT.
    let raw = r#"{"a":1,"a":2}"#;
    let r = jcs::parse_strict(raw);
    assert!(
        matches!(r, Err(JcsError::DuplicateKey(_))),
        "duplicate key must reject, got {r:?}"
    );

    // Nested duplicate keys must also reject.
    let nested = r#"{"outer":{"k":1,"k":1}}"#;
    assert!(
        matches!(jcs::parse_strict(nested), Err(JcsError::DuplicateKey(_))),
        "nested duplicate key must reject"
    );
}

#[test]
fn rejects_non_integer_float_and_exponent_numbers() {
    // Fractional float.
    assert!(
        matches!(
            jcs::parse_strict(r#"{"n":1.5}"#),
            Err(JcsError::NonIntegerNumber(_))
        ),
        "fractional float must reject"
    );
    // Exponent form (even if integral magnitude) — restricted profile forbids exponents.
    assert!(
        jcs::parse_strict(r#"{"n":1e3}"#).is_err(),
        "exponent number must reject"
    );
    // Negative exponent.
    assert!(
        jcs::parse_strict(r#"{"n":2.0E2}"#).is_err(),
        "decimal+exponent must reject"
    );
    // A bare top-level float likewise.
    assert!(
        jcs::parse_strict("3.14").is_err(),
        "top-level float must reject"
    );
    // Sanity: a plain integer is accepted.
    assert!(
        jcs::parse_strict(r#"{"n":1000}"#).is_ok(),
        "integer must accept"
    );
}

#[test]
fn rejects_non_ascii_object_key() {
    // Non-ASCII load-bearing KEY (value non-ASCII is fine, key is not).
    let raw = r#"{"键":"value"}"#;
    let r = jcs::parse_strict(raw);
    assert!(
        matches!(r, Err(JcsError::NonAsciiKey(_))),
        "non-ASCII object key must reject, got {r:?}"
    );
    // Control-char in key also non-conforming.
    let ctrl = "{\"a\\u0001\":1}";
    assert!(
        jcs::parse_strict(ctrl).is_err(),
        "control char in key must reject"
    );
    // Sanity: non-ASCII VALUE is accepted (emitted raw UTF-8).
    assert!(
        jcs::parse_strict(r#"{"k":"本地化"}"#).is_ok(),
        "non-ASCII string value must accept"
    );
}

#[test]
fn rejects_bom_and_trailing_newline() {
    // UTF-8 BOM prefix.
    let bom = "\u{feff}{\"a\":1}";
    assert!(jcs::parse_strict(bom).is_err(), "leading BOM must reject");
    // Trailing newline.
    assert!(
        jcs::parse_strict("{\"a\":1}\n").is_err(),
        "trailing newline must reject"
    );
}

#[test]
fn rejects_head_set_after_in_payload() {
    // `head_set_after` is forbidden in EVERY payload — an event can never embed its OID.
    let payload = json!({
        "schema_id": "goal_state.v1",
        "goal_id": "g1",
        "head_set_after": {"tape_tip": "mu:dead"}
    });
    let r = jcs::reject_forbidden_payload_fields(&payload);
    assert!(
        matches!(r, Err(JcsError::ForbiddenPayloadField(ref f)) if f == "head_set_after"),
        "head_set_after must reject, got {r:?}"
    );

    // Nested occurrence also rejects.
    let nested = json!({"outer": {"head_set_after": "x"}});
    assert!(
        jcs::reject_forbidden_payload_fields(&nested).is_err(),
        "nested head_set_after must reject"
    );

    // A clean payload passes.
    let clean = json!({"schema_id": "goal_state.v1", "goal_id": "g1"});
    assert!(
        jcs::reject_forbidden_payload_fields(&clean).is_ok(),
        "clean payload must pass"
    );
}

#[test]
fn rejects_phantom_self_digest_field_closed_world() {
    let spec = load_spec();
    // The closed inventory of self-digest field names, derived from the ratified file.
    let known: Vec<String> = spec["digest_fields"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| f["field"].as_str().unwrap().to_string())
        .chain(
            spec["not_self_digest_reference"]["fields"]
                .as_array()
                .unwrap()
                .iter()
                .map(|f| f.as_str().unwrap().to_string()),
        )
        .collect();

    // A new digest-shaped field absent from the closed inventory => closed-world reject.
    let phantom = json!({
        "schema_id": "work_graph.v1",
        "shadow_digest": "deadbeef",
        "nodes": []
    });
    let r = jcs::reject_unknown_self_digest_fields(&phantom, &known);
    assert!(
        matches!(r, Err(JcsError::UnknownSelfDigestField(ref f)) if f == "shadow_digest"),
        "phantom *_digest/*_hash field must reject (closed-world), got {r:?}"
    );

    // A KNOWN digest field is accepted.
    let ok = json!({
        "schema_id": "goal_state.v1",
        "goal_digest": "abc",
        "goal_id": "g"
    });
    assert!(
        jcs::reject_unknown_self_digest_fields(&ok, &known).is_ok(),
        "known digest field must pass closed-world check"
    );
}
