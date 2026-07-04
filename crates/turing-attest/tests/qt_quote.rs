//! HW-SW-009 (PREDICATE C3) — `q_t_quote.json` fixture tests.

use std::fs;

use turing_attest::qt_quote::{QtQuote, QtQuoteError, QT_QUOTE_SCHEMA_ID};

fn fixture(name: &str) -> String {
    let path = format!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../fixtures/{}"), name);
    fs::read_to_string(&path).unwrap_or_else(|e| panic!("missing fixture {path}: {e}"))
}

#[test]
fn qt_quote_valid_parses_and_digest_self_consistent() {
    let text = fixture("q_t_quote.valid.json");
    let quote = QtQuote::parse(&text).expect("parse valid q_t_quote fixture");
    quote.validate().expect("valid fixture must validate");
    assert_eq!(quote.schema_id, QT_QUOTE_SCHEMA_ID);
    let recomputed = quote.qualifying_digest().expect("qualifying digest");
    assert_eq!(recomputed, quote.quote.pcr_digest);
}

#[test]
fn qt_quote_invalid_schema_rejected() {
    let text = fixture("q_t_quote.invalid_schema.json");
    let quote = QtQuote::parse(&text).expect("parse invalid_schema fixture");
    match quote.validate() {
        Err(QtQuoteError::BadSchemaId { .. }) => {}
        other => panic!("expected BadSchemaId, got {other:?}"),
    }
}

#[test]
fn qt_quote_invalid_digest_rejected() {
    let text = fixture("q_t_quote.invalid_digest.json");
    let quote = QtQuote::parse(&text).expect("parse invalid_digest fixture");
    match quote.validate() {
        Err(QtQuoteError::DigestMismatch { .. }) => {}
        other => panic!("expected DigestMismatch, got {other:?}"),
    }
}

#[test]
fn qt_quote_invalid_nonascii_rejected() {
    let text = fixture("q_t_quote.invalid_nonascii.json");
    match QtQuote::parse(&text) {
        Err(QtQuoteError::NonAsciiKey(_)) => {}
        other => panic!("expected NonAsciiKey, got {other:?}"),
    }
}
