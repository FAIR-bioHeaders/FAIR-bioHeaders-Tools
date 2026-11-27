// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Component throughput on one file: read, SHA-512/256 alone, framing alone,
//! and the full verify. `cargo run --release --example throughput -- FILE`.

use fair_bioheaders_tools::framing::{Framer, Kind, Part};
use fair_bioheaders_tools::{Container, Engine, Operation};
use sha2::{Digest, Sha512_256};
use std::io::Read;
use std::time::Instant;

fn chunks(path: &str, mut f: impl FnMut(&[u8])) -> f64 {
    let start = Instant::now();
    let mut file = std::fs::File::open(path).unwrap();
    let mut buffer = vec![0u8; 1 << 20];
    loop {
        let n = file.read(&mut buffer).unwrap();
        if n == 0 {
            break;
        }
        f(&buffer[..n]);
    }
    start.elapsed().as_secs_f64()
}

fn main() {
    let path = std::env::args().nth(1).expect("FILE");
    let size = std::fs::metadata(&path).unwrap().len() as f64 / 1048576.0;
    let report =
        |name: &str, secs: f64| println!("{name:<12} {secs:6.2} s  {:7.0} MiB/s", size / secs);
    report("read", chunks(&path, |_| {}));
    let mut hasher = Sha512_256::new();
    report("sha512_256", chunks(&path, |c| hasher.update(c)));
    let mut framer = Framer::new(Kind::Fasta, 1 << 20, 10_000);
    let mut sink = |_p: Part<'_>| {};
    report(
        "framing",
        chunks(&path, |c| framer.push(Some(c), &mut sink).unwrap()),
    );
    let engine = Engine::new().unwrap();
    let start = Instant::now();
    let r = engine
        .verify_path(
            Operation::Verify,
            Container::Fasta,
            std::path::Path::new(&path),
        )
        .unwrap();
    report("verify", start.elapsed().as_secs_f64());
    assert!(r.is_valid());
}
