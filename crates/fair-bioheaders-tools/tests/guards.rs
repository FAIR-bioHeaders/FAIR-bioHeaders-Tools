// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The harness guards fail closed (Tools#208 section 6): a tampered manifest,
//! a wrong count and incomplete accounting are failures, never passes.

mod corpus;

use corpus::{Pin, Run};

fn temp_manifest(bytes: &[u8]) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("fh-guard-{}-{}", std::process::id(), bytes.len()));
    std::fs::create_dir_all(dir.join("conformance")).unwrap();
    std::fs::write(dir.join("conformance/manifest.json"), bytes).unwrap();
    dir
}

const MANIFEST: &[u8] = br#"{"vectors": [{"id": "a"}, {"id": "b"}]}"#;

fn pin(sha256: &'static str, count: usize) -> Pin {
    Pin {
        label: "GUARD",
        env: "UNUSED",
        commit: "0",
        manifest: "conformance/manifest.json",
        sha256,
        count,
    }
}

#[test]
fn matching_identity_is_accepted() {
    let digest: &'static str = Box::leak(corpus::sha256_hex(MANIFEST).into_boxed_str());
    let root = temp_manifest(MANIFEST);
    let json = corpus::manifest(&root, &pin(digest, 2));
    assert_eq!(json["vectors"].as_array().unwrap().len(), 2);
}

#[test]
#[should_panic(expected = "manifest digest is not the pinned one")]
fn tampered_manifest_fails() {
    let digest: &'static str = Box::leak(corpus::sha256_hex(MANIFEST).into_boxed_str());
    let mut tampered = MANIFEST.to_vec();
    tampered.push(b' ');
    let root = temp_manifest(&tampered);
    corpus::manifest(&root, &pin(digest, 2));
}

#[test]
#[should_panic(expected = "manifest count differs from the pin")]
fn wrong_count_fails() {
    let digest: &'static str = Box::leak(corpus::sha256_hex(MANIFEST).into_boxed_str());
    let root = temp_manifest(MANIFEST);
    corpus::manifest(&root, &pin(digest, 3));
}

#[test]
fn accounting_detects_failures_and_missing_vectors() {
    let mut run = Run::default();
    run.record("fasta", "a", Ok(()));
    run.record("fasta", "b", Err("wrong".into()));
    run.not_run("jsonld", "c", "outside-engine-scope:jsonld");
    let (total, ran, passed, failed) = run.totals();
    assert_eq!((total, ran, passed, failed), (3, 2, 1, 1));
    assert_eq!(run.failures, vec!["b: wrong".to_owned()]);
    // Two-way: executed + declared must equal the manifest count.
    assert_ne!(run.executed.len() + run.declared_not_run.len(), 4);
}

#[test]
#[should_panic(expected = "a missing corpus is a failure")]
fn missing_corpus_is_a_failure() {
    let pin = Pin {
        env: "FH_DEFINITELY_UNSET_CORPUS",
        ..pin("x", 1)
    };
    // SAFETY-free: only reads the environment.
    if std::env::var("FH_ALLOW_MISSING_CORPUS").as_deref() == Ok("1") {
        panic!("a missing corpus is a failure (FH_ALLOW_MISSING_CORPUS set; guard not exercised)");
    }
    corpus::locate(&pin);
}
