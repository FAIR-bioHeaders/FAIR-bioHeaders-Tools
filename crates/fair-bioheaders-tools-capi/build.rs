// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

fn main() {
    // SONAME libfhcore.so.<ABI major> (Tools#210 addendum 2).
    let target = std::env::var("TARGET").unwrap_or_default();
    if target.contains("linux") || target.contains("freebsd") {
        println!("cargo:rustc-cdylib-link-arg=-Wl,-soname,libfhcore.so.0");
    }
    println!("cargo:rerun-if-changed=build.rs");
}
