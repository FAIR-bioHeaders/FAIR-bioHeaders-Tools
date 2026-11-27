// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Compile tests/c/smoke.c against include/fhcore.h, link the static
//! library, run it (Cargo-driven; Tools#208 section 3).

use std::path::PathBuf;
use std::process::Command;

#[test]
fn c_caller_compiles_links_and_runs() {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    // The uplifted static library lives in target/<profile>/, an ancestor of
    // the test executable in every Cargo build-directory layout.
    let exe = std::env::current_exe().unwrap();
    let lib = exe
        .ancestors()
        .map(|dir| dir.join("libfhcore.a"))
        .find(|candidate| candidate.exists())
        .unwrap_or_else(|| exe.join("libfhcore.a"));
    assert!(
        lib.exists(),
        "static library not built at {}",
        lib.display()
    );
    let out = std::env::temp_dir().join(format!("fhcore-smoke-{}", std::process::id()));
    let compiler = std::env::var("CC").unwrap_or_else(|_| "cc".into());
    let status = Command::new(compiler)
        .arg("-std=c99")
        .arg("-Wall")
        .arg("-Werror")
        .arg("-I")
        .arg(manifest.join("include"))
        .arg(manifest.join("tests/c/smoke.c"))
        .arg(&lib)
        .args(["-lpthread", "-ldl", "-lm"])
        .arg("-o")
        .arg(&out)
        .status()
        .expect("run the C compiler");
    assert!(status.success(), "C compile/link failed");
    let run = Command::new(&out).output().unwrap();
    let _ = std::fs::remove_file(&out);
    assert!(run.status.success(), "smoke exited {:?}", run.status.code());
    assert_eq!(String::from_utf8_lossy(&run.stdout).trim(), "YAML.syntax");
}
