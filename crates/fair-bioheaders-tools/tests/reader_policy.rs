// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! L1 reader-policy cases (C-POLICY at 34bbe21a; decision 15, research R10):
//! metadata cases are validated, carrier cases verified, and every payload's
//! SHA-256 is checked before it is read.

mod corpus;

use corpus::{C_POLICY, Run};
use fair_bioheaders_tools::{Container, Engine, Operation, Outcome};

#[test]
fn reader_policy_cases() {
    let Some(root) = corpus::locate(&C_POLICY) else {
        return;
    };
    let cases = corpus::manifest(&root, &C_POLICY);
    let base = root.join("conformance/reader-policy");
    let engine = Engine::new().expect("engine");
    let mut run = Run::default();
    for case in cases["cases"].as_array().unwrap() {
        let id = case["id"].as_str().unwrap();
        let format = case["format"].as_str().unwrap();
        let file = case["file"].as_str().unwrap();
        let bytes = std::fs::read(base.join(file)).expect("payload");
        let result = (|| -> Result<(), String> {
            if corpus::sha256_hex(&bytes) != case["sha256"].as_str().unwrap() {
                return Err("payload digest differs from cases.json".into());
            }
            let (op, container) = match case["operation"].as_str().unwrap() {
                "metadata" if file.ends_with(".json") => {
                    (Operation::Validate, Container::MetadataJson)
                }
                "metadata" => (Operation::Validate, Container::MetadataYaml),
                _ => (
                    Operation::Verify,
                    corpus::container_for(format).ok_or("unknown carrier format")?,
                ),
            };
            let report = engine
                .verify_bytes(op, container, &bytes)
                .map_err(|e| format!("engine error: {e}"))?;
            let want = match case["expected"].as_str().unwrap() {
                "valid" => Outcome::Valid,
                "unsupported-version" => Outcome::Unsupported,
                _ => Outcome::Invalid,
            };
            if report.outcome != want {
                let first = report
                    .first_error()
                    .map(|d| format!("{}: {}", d.code, d.message))
                    .unwrap_or_default();
                return Err(format!(
                    "expected {}, got {} [{first}]",
                    want.as_str(),
                    report.outcome.as_str()
                ));
            }
            Ok(())
        })();
        run.record(format, id, result);
    }
    let receipt = run.write_receipt(&C_POLICY, &engine);
    let (total, ran, passed, failed) = run.totals();
    eprintln!(
        "C-POLICY: total {total}, run {ran}, passed {passed}, failed {failed}; receipt {}",
        receipt.display()
    );
    assert_eq!(total, C_POLICY.count);
    assert!(
        run.failures.is_empty(),
        "{} failures:\n{}",
        run.failures.len(),
        run.failures.join("\n")
    );
    assert_eq!(passed, C_POLICY.count);
}
