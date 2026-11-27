// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! L1 conformance (Tools#208 section 2): the frozen v0.6.0 suite and the
//! pinned current suite, decided only against the specification manifests.

mod corpus;

use corpus::{C_FROZEN, C_HIST, C_SOURCE, OUTSIDE_ENGINE, Pin, Run};
use fair_bioheaders_tools::Engine;
use serde_json::Value as Json;
use std::collections::BTreeMap;

/// A retired historical expectation: (historical expected, rule, the
/// SHA-256 of the historical bytes the crosswalk retires).
type Retired = BTreeMap<String, (String, String, String)>;

/// Retired historical expectations from the pinned crosswalk (C-HIST).
fn crosswalk() -> Retired {
    let root = corpus::locate(&C_HIST).expect("crosswalk checkout");
    let json = corpus::manifest(&root, &C_HIST);
    json["cases"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| {
            (
                c["id"].as_str().unwrap().to_owned(),
                (
                    c["expected"].as_str().unwrap().to_owned(),
                    c["rule"].as_str().unwrap_or_default().to_owned(),
                    c["oldSha256"].as_str().unwrap_or_default().to_owned(),
                ),
            )
        })
        .collect()
}

fn run_suite(
    pin: &Pin,
    expected_run: usize,
    expected_not_run: usize,
    retired: Option<&Retired>,
) -> Run {
    let Some(root) = corpus::locate(pin) else {
        return Run::default();
    };
    let manifest = corpus::manifest(&root, pin);
    let engine = Engine::new().expect("engine");
    let mut run = Run::default();
    for vector in manifest["vectors"].as_array().unwrap() {
        let id = vector["id"].as_str().unwrap();
        let format = vector["format"].as_str().unwrap();
        if OUTSIDE_ENGINE.contains(&format) {
            run.not_run(format, id, &format!("outside-engine-scope:{format}"));
            continue;
        }
        let result = corpus::check_vector(&engine, &root, vector).map(|_| ());
        // A retired historical expectation counts as superseded only when the
        // pinned crosswalk retires exactly this id and these bytes for R4 and
        // the engine rejects them under R4; anything else is a failure.
        if let (Err(_), Some(retired)) = (&result, retired) {
            if let Some((expected, rule, old_sha256)) = retired.get(id) {
                let bytes = std::fs::read(
                    root.join("conformance")
                        .join(vector["file"].as_str().unwrap()),
                )
                .unwrap();
                let container = corpus::container_for(format).unwrap();
                let report = engine
                    .verify_bytes(fair_bioheaders_tools::Operation::Verify, container, &bytes)
                    .unwrap();
                let r4 = report
                    .first_error()
                    .is_some_and(|d| d.code == "R4.non-canonical-checksum");
                let same_bytes = corpus::sha256_hex(&bytes) == *old_sha256;
                if expected == vector["expected"].as_str().unwrap()
                    && rule == "R4"
                    && same_bytes
                    && r4
                {
                    run.superseded(format, id);
                    continue;
                }
            }
        }
        run.record(format, id, result);
    }
    let receipt = run.write_receipt(pin, &engine);
    let (total, ran, passed, failed) = run.totals();
    eprintln!(
        "{}: total {total}, run {ran}, passed {passed}, failed {failed}; receipt {}",
        pin.label,
        receipt.display()
    );
    // Two-way accounting: every manifest vector is either run or declared NOT_RUN.
    assert_eq!(
        total, pin.count,
        "{}: vectors accounted for differ from the manifest",
        pin.label
    );
    assert_eq!(run.executed.len() + run.declared_not_run.len(), pin.count);
    assert!(ran > 0, "{}: zero vectors executed", pin.label);
    assert_eq!(
        run.declared_not_run.len(),
        expected_not_run,
        "{}: declared NOT_RUN count",
        pin.label
    );
    assert_eq!(ran, expected_run, "{}: executed count", pin.label);
    assert!(
        run.failures.is_empty(),
        "{}: {} failures:\n{}",
        pin.label,
        run.failures.len(),
        run.failures.join("\n")
    );
    assert_eq!(passed + run.superseded.len(), expected_run);
    run
}

/// G1 item 1, decided (option A, specification#296 comment 7206358624): the
/// frozen receipt is exactly 198 passed + 30 superseded-by-crosswalk + 63
/// NOT_RUN. The 30 are the valid vectors with the non-canonical historical
/// parent placeholder; each must be retired by the pinned crosswalk (id,
/// expectation and bytes) and rejected under R4, and the superseded set must
/// equal the crosswalk's valid retirements present in the frozen manifest.
#[test]
fn frozen_v060_suite() {
    let Some(root) = corpus::locate(&C_FROZEN) else {
        return;
    };
    let retired = crosswalk();
    let run = run_suite(&C_FROZEN, 228, 63, Some(&retired));
    let (_, _, passed, _) = run.totals();
    assert_eq!(passed, 198, "frozen passes");
    assert_eq!(run.superseded.len(), 30, "frozen superseded-by-crosswalk");
    let manifest = corpus::manifest(&root, &C_FROZEN);
    let in_manifest: std::collections::BTreeSet<&str> = manifest["vectors"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v["id"].as_str().unwrap())
        .collect();
    let valid_retired: std::collections::BTreeSet<&str> = retired
        .iter()
        .filter(|(id, (expected, _, _))| expected == "valid" && in_manifest.contains(id.as_str()))
        .map(|(id, _)| id.as_str())
        .collect();
    let superseded: std::collections::BTreeSet<&str> =
        run.superseded.iter().map(String::as_str).collect();
    assert_eq!(superseded, valid_retired, "superseded set vs crosswalk");
    let _: Option<Json> = None;
}

/// G1 item 2: all 254 run vectors pass (Clarification Q3).
#[test]
fn current_34bbe21a_suite() {
    let run = run_suite(&C_SOURCE, 254, 65, None);
    assert!(run.superseded.is_empty());
}
