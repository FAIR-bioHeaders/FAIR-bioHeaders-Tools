// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Digest-pinned FAIR-bioHeaders contract bytes, the V1-V7 selection table and
//! consumer support profiles, compiled into the engine (Tools#213).
//!
//! Schema bytes are byte copies of the specification's released (and one
//! historical draft) contracts; `data/bundle.json` records each file's source
//! and SHA-256, which the core crate's tests verify. This crate has no logic.

#![forbid(unsafe_code)]
#![deny(missing_docs)]

/// The bundle manifest (`data/bundle.json`).
pub const BUNDLE_JSON: &str = include_str!("../data/bundle.json");

/// Every bundled schema file, by file name.
pub const SCHEMAS: &[(&str, &[u8])] = &[
    ("fhgff3-1.0.json", include_bytes!("../data/schemas/fhgff3-1.0.json")),
    ("fhgff3-1.1.json", include_bytes!("../data/schemas/fhgff3-1.1.json")),
    ("fhgff3-1.2.json", include_bytes!("../data/schemas/fhgff3-1.2.json")),
    ("fhp-1.0.json", include_bytes!("../data/schemas/fhp-1.0.json")),
    ("fhp-1.1.json", include_bytes!("../data/schemas/fhp-1.1.json")),
    ("fhp-1.2.json", include_bytes!("../data/schemas/fhp-1.2.json")),
    ("fhr-1.json", include_bytes!("../data/schemas/fhr-1.json")),
    ("fhr-2.0.json", include_bytes!("../data/schemas/fhr-2.0.json")),
    ("fhr-2.1.json", include_bytes!("../data/schemas/fhr-2.1.json")),
    ("fht-1.0.json", include_bytes!("../data/schemas/fht-1.0.json")),
    ("fht-draft.json", include_bytes!("../data/schemas/fht-draft.json")),
];

/// Consumer support profiles: `(id, definition JSON)`.
pub const PROFILES: &[(&str, &str)] = &[
    ("python", include_str!("../data/profiles/python.json")),
    ("test-narrow", include_str!("../data/profiles/test-narrow.json")),
];

/// The bytes of the bundled schema `name`.
pub fn schema(name: &str) -> Option<&'static [u8]> {
    SCHEMAS.iter().find(|(n, _)| *n == name).map(|(_, b)| *b)
}

/// The definition of profile `id`.
pub fn profile(id: &str) -> Option<&'static str> {
    PROFILES.iter().find(|(n, _)| *n == id).map(|(_, b)| *b)
}
