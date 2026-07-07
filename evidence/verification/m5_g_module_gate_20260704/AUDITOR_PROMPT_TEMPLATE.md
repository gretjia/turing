# M5.G External Auditor Prompt Template

You are auditing only the GitHub packet for M5.G. Do not use implementation chat, local plan directory files, agent memory summaries, or uncommitted local files.

Repository: https://github.com/gretjia/turing
Branch: goal/mini-swe-bench-grok-worker
Packet root: evidence/verification/m5_g_module_gate_20260704
Target gate: M5.G
Certificate schema to return: ClosureCertificate.v1 (`turingos.closure_certificate.v1`)

Required commands from a fresh clone at the submitted commit:

```bash
cd evidence/verification/m5_g_module_gate_20260704
sha256sum -c PACKET_MANIFEST.sha256
cd ../../..
bash evidence/verification/m5_g_module_gate_20260704/packet_checks/run_m5_g_rollup_check.sh
```

Audit questions:

1. Does `PACKET_MANIFEST.sha256` verify every packet file?
2. Do all `SOURCE_MAP.json` entries exist in the GitHub packet and match their sha256 values?
3. Does the M5.G roll-up include the nine MODULE_M5 ship-gate artifact groups, with M5.P3 external PASS and processed M5.P4 M3.G/M4.G certificate-or-FAIL coverage?
4. Does the packet preserve the ADDRESSED ceiling and avoid SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, and constitution-byte-change claims?
5. If you issue PASS, certify only M5.G for this packet root and commit. M5.G is not externally verified by this packet; only your custody-separated certificate can confer that later status.

Return a JSON certificate with verdict PASS or FAIL. FAIL is acceptable and should include machine-readable repair reasons. Do not patch this packet in place.
