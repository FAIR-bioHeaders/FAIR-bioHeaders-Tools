// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! FAIR-bioHeaders read/validate/verify engine (Phase 1 of Project 14).
#![forbid(unsafe_code)]

pub mod checksum;
pub mod diagnostics;
pub mod framing;
pub mod gzip;
pub mod json;
pub mod report;
pub mod selection;
pub mod value;
pub mod yaml;

/// Placeholder until the engine module lands.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Container { Auto }
