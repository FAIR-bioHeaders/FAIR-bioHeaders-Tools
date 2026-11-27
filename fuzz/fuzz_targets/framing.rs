#![no_main]
use fair_bioheaders_tools::framing::{Framer, Kind};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    for kind in [Kind::Fasta, Kind::Gfa, Kind::Gff3] {
        let split = data.first().map_or(1, |b| (*b as usize % 7) + 1);
        let mut framer = Framer::new(kind, 4096, 64);
        let mut sink = |_part: fair_bioheaders_tools::framing::Part<'_>| {};
        for chunk in data.chunks(split) {
            if framer.push(Some(chunk), &mut sink).is_err() {
                break;
            }
        }
        let _ = framer.push(None, &mut sink);
    }
});
