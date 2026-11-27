#![no_main]
use fair_bioheaders_tools::yaml::{YamlLimits, load};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    if let Ok(text) = std::str::from_utf8(data) {
        let limits = YamlLimits { nodes: 2000, depth: 64, scalar_bytes: 1 << 16 };
        let _ = load(text, limits);
        let _ = fair_bioheaders_tools::json::load(text, limits);
    }
});
