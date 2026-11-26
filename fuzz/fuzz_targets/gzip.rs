#![no_main]
use fair_bioheaders_tools::gzip::Decoder;
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let mut decoder = Decoder::new();
    let mut total = 0usize;
    let mut sink = |piece: &[u8]| -> Result<(), ()> {
        total += piece.len();
        if total > 1 << 24 { Err(()) } else { Ok(()) }
    };
    if decoder.push(data, &mut sink).is_ok() {
        let _ = decoder.finish();
    }
});
