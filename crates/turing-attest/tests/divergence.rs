//! HW-SW-013 (SPEC D2) — sim/real receipt divergence contract. Compares
//! `evidence/loops/hw_sw_010_20260704/receipt_sim.json` and
//! `receipt_real.json` (both produced by `scripts/attest-tpm.sh`, never by
//! this test) IF both exist: same qualifying data must yield structurally
//! equal quotes modulo signer (AK differs, `kind` differs) — any other
//! structural divergence (e.g. one unverified, differing `pcr_selection`)
//! is a failure, not a shrug. `receipt_real.json` is allowed to be absent
//! in an implementer environment without real-device access; that is a
//! skip-with-note, not a failure.

use std::fs;

use serde_json::Value;

fn evidence_path(name: &str) -> String {
    format!(
        concat!(env!("CARGO_MANIFEST_DIR"), "/../../evidence/loops/hw_sw_010_20260704/{}"),
        name
    )
}

fn load(name: &str) -> Option<Value> {
    let path = evidence_path(name);
    let text = fs::read_to_string(&path).ok()?;
    Some(serde_json::from_str(&text).unwrap_or_else(|e| panic!("{path} is not valid JSON: {e}")))
}

fn require_str<'a>(v: &'a Value, key: &str, receipt: &str) -> &'a str {
    v.get(key)
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{receipt}: missing/non-string field {key:?}: {v:?}"))
}

fn require_bool(v: &Value, key: &str, receipt: &str) -> bool {
    v.get(key)
        .and_then(Value::as_bool)
        .unwrap_or_else(|| panic!("{receipt}: missing/non-bool field {key:?}: {v:?}"))
}

#[test]
fn sim_real_divergence() {
    let Some(sim) = load("receipt_sim.json") else {
        println!("SKIP: receipt_sim.json not found — run ./scripts/attest-tpm.sh --simulator first");
        return;
    };
    let Some(real) = load("receipt_real.json") else {
        println!("SKIP: receipt_real.json absent in this environment (no real-device access) — deferred, non-blocking");
        return;
    };

    // Structural validity + the "verified" contract: both quotes must be
    // self-verified true. An unverified receipt on either side is a
    // failure, never silently accepted.
    assert!(require_bool(&sim, "verified", "receipt_sim.json"), "receipt_sim.json must have verified=true");
    assert!(require_bool(&real, "verified", "receipt_real.json"), "receipt_real.json must have verified=true");

    // Same qualifying data through both backends -> same pcr_selection.
    let sim_sel = require_str(&sim, "pcr_selection", "receipt_sim.json");
    let real_sel = require_str(&real, "pcr_selection", "receipt_real.json");
    assert_eq!(sim_sel, real_sel, "pcr_selection must match structurally between sim and real");

    // Both must carry the same qualifying data — the whole point of the
    // divergence comparison is "identical input, different signer".
    let sim_qual = require_str(&sim, "qualifying_hex", "receipt_sim.json");
    let real_qual = require_str(&real, "qualifying_hex", "receipt_real.json");
    assert_eq!(sim_qual, real_qual, "qualifying_hex must be identical between sim and real receipts");

    // Expected divergence: kind differs (TpmSimulator vs Vtpm).
    let sim_kind = require_str(&sim, "kind", "receipt_sim.json");
    let real_kind = require_str(&real, "kind", "receipt_real.json");
    assert_eq!(sim_kind, "TpmSimulator", "receipt_sim.json kind must be TpmSimulator");
    assert_eq!(real_kind, "Vtpm", "receipt_real.json kind must be Vtpm");
    assert_ne!(sim_kind, real_kind, "sim and real kinds must differ");

    // Expected divergence: AK differs (sim AK != vtpm AK — two distinct
    // ephemeral keys were provisioned in two distinct TPMs).
    let sim_ak = require_str(&sim, "ak_pub_b64", "receipt_sim.json");
    let real_ak = require_str(&real, "ak_pub_b64", "receipt_real.json");
    assert_ne!(sim_ak, real_ak, "sim and real AK public keys must differ (distinct provisioned keys)");

    // Structural presence of the remaining required fields (both sides).
    for (receipt, v) in [("receipt_sim.json", &sim), ("receipt_real.json", &real)] {
        require_str(v, "pcr_digest", receipt);
        require_str(v, "quote_sig_b64", receipt);
        require_str(v, "produced_at", receipt);
    }
}
