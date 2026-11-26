// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The published FHT v0.7.0 lane (C-FHT at 34bbe21a): supplemental L1
//! evidence for the python profile's released FHT 1.0 contract.

mod corpus;

use corpus::{Pin, Run};
use fair_bioheaders_tools::{Container, Engine, Operation, Outcome};

const C_FHT: Pin = Pin {
    label: "C-FHT",
    env: "FH_SPEC_34BBE21A",
    commit: "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b",
    manifest: "conformance/fht-v0.7.0/manifest.json",
    sha256: "238682707a799c274b24388159d392e74c42d16ef96593b49bb483db3f642e3a",
    count: 93,
};

#[test]
fn fht_v070_lane() {
    let Some(root) = corpus::locate(&C_FHT) else {
        return;
    };
    let manifest = corpus::manifest(&root, &C_FHT);
    let base = root.join("conformance/fht-v0.7.0");
    let engine = Engine::new().unwrap();
    let mut run = Run::default();
    for vector in manifest["vectors"].as_array().unwrap() {
        let id = vector["id"].as_str().unwrap();
        // C3 parent identity needs the parent files: a model/parent-link check
        // outside the Phase 1 engine (#207 section 1), declared, never counted.
        if vector["rule"] == "C3" {
            run.not_run("fht-fasta", id, "outside-engine-scope:parent-links");
            continue;
        }
        let result = (|| -> Result<(), String> {
            let bytes = std::fs::read(base.join(vector["file"].as_str().unwrap()))
                .map_err(|e| e.to_string())?;
            let report = engine
                .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
                .map_err(|e| e.to_string())?;
            let valid = vector["expected"] == "valid";
            let ok = if valid {
                report.outcome == Outcome::Valid
            } else {
                report.outcome != Outcome::Valid
            };
            if !ok {
                return Err(format!(
                    "expected {}, got {} [{:?}]",
                    vector["expected"],
                    report.outcome.as_str(),
                    report.first_error().map(|d| (d.code, d.message.clone()))
                ));
            }
            if let Some(stated) = vector.get("checksum").and_then(|c| c.as_str()) {
                if report.checksum.and_then(|c| c.computed).as_deref() != Some(stated) {
                    return Err("checksum differs".into());
                }
            }
            Ok(())
        })();
        run.record("fht-fasta", id, result);
    }
    run.write_receipt(&C_FHT, &engine);
    let (total, ran, passed, failed) = run.totals();
    eprintln!(
        "C-FHT: total {total}, run {ran}, passed {passed}, failed {failed}, not run {}",
        run.declared_not_run.len()
    );
    assert_eq!(total, C_FHT.count);
    assert_eq!(ran + run.declared_not_run.len(), C_FHT.count);
    assert!(
        run.failures.is_empty(),
        "{} failures:\n{}",
        run.failures.len(),
        run.failures.join("\n")
    );
}
