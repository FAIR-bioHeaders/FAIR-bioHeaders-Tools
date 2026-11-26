#![no_main]
use fair_bioheaders_tools::{Container, Engine, Operation};
use libfuzzer_sys::fuzz_target;
use std::sync::OnceLock;

static ENGINE: OnceLock<Engine> = OnceLock::new();

fuzz_target!(|data: &[u8]| {
    let engine = ENGINE.get_or_init(|| Engine::new().unwrap());
    for container in [Container::Auto, Container::Fasta, Container::Gff3, Container::MetadataYaml, Container::MetadataJson] {
        // Engine errors are allowed; panics and aborts are not.
        let _ = engine.verify_bytes(Operation::Verify, container, data);
    }
});
