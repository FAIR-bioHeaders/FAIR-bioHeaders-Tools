// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The diagnostic registry (Tools#207 section 2): rules come from the pinned
//! specification, and codes are append-only against the committed snapshot.

mod corpus;

use fair_bioheaders_tools::diagnostics::REGISTRY;
use serde_json::{Value as Json, json};

#[test]
fn registry_rules_exist_in_the_pinned_specification() {
    let Some(root) = corpus::locate(&corpus::C_SOURCE) else {
        return;
    };
    let manifest = corpus::manifest(&root, &corpus::C_SOURCE);
    let rules = manifest["rules"].as_object().unwrap();
    for entry in REGISTRY {
        if let Some(rule) = entry.rule {
            // C1 is defined by the FHT terms (TERMS.md), not the manifest table.
            assert!(
                rule == "C1" || rules.contains_key(rule),
                "{}: rule {rule} is not in the pinned manifest",
                entry.code
            );
        }
    }
    let terms = std::fs::read_to_string(root.join("docs/TERMS.md")).unwrap_or_default();
    assert!(
        terms.contains("C1"),
        "C1 must be defined in the pinned docs/TERMS.md"
    );
}

fn snapshot() -> Json {
    let entries: Vec<Json> = REGISTRY
        .iter()
        .map(|e| json!({"code": e.code, "rule": e.rule, "layer": e.layer.as_str(), "severity": e.severity.as_str()}))
        .collect();
    json!({"registryVersion": 1, "codes": entries})
}

#[test]
fn codes_are_append_only() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("diagnostics.snapshot.json");
    let committed: Json =
        serde_json::from_str(&std::fs::read_to_string(&path).expect("committed snapshot")).unwrap();
    let current = snapshot();
    for old in committed["codes"].as_array().unwrap() {
        let found = current["codes"]
            .as_array()
            .unwrap()
            .iter()
            .find(|c| c["code"] == old["code"]);
        assert_eq!(
            found,
            Some(old),
            "code {} was removed or changed; codes are append-only",
            old["code"]
        );
    }
    if std::env::var("FH_UPDATE_SNAPSHOT").as_deref() == Ok("1") {
        std::fs::write(
            &path,
            serde_json::to_string_pretty(&current).unwrap() + "\n",
        )
        .unwrap();
    }
}
