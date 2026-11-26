// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Deterministic mutation smoke test (complements the cargo-fuzz targets in
//! fuzz/): mutated corpus files never panic and always produce a report or a
//! call error. `FH_MUTATION_ROUNDS` raises the round count.

use fair_bioheaders_tools::{Container, Engine, Operation};

struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        // xorshift64*
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        self.0.wrapping_mul(0x2545_f491_4f6c_dd1d)
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % n.max(1) as u64) as usize
    }
}

const INTERESTING: &[&[u8]] = &[
    b"\n",
    b"\r",
    b"\r\n",
    b";~",
    b"#~",
    b">",
    b"\x00",
    b"\xff",
    b"&a ",
    b"*a",
    b"!!str ",
    b"<<: ",
    b"---\n",
    b"%YAML 1.2\n",
    b"\x1f\x8b\x08\x00",
    b"[",
    b"{",
    b"\"",
    b"'",
    b"checksum: ",
    b".inf",
    b"1e999",
    b"\xe2\x80\xa8",
    b"\xef\xbb\xbf",
    b"##gff-version 3\n",
    b"##FASTA\n",
];

fn mutate(rng: &mut Rng, input: &[u8]) -> Vec<u8> {
    let mut data = input.to_vec();
    for _ in 0..1 + rng.below(4) {
        let at = rng.below(data.len() + 1);
        match rng.below(5) {
            0 if !data.is_empty() => {
                let i = rng.below(data.len());
                data[i] = rng.next() as u8;
            }
            1 if !data.is_empty() => {
                let end = (at + rng.below(16)).min(data.len());
                data.drain(at.min(end)..end);
            }
            2 => {
                let piece = INTERESTING[rng.below(INTERESTING.len())];
                data.splice(at..at, piece.iter().copied());
            }
            3 if !data.is_empty() => {
                let from = rng.below(data.len());
                let len = rng.below(64).min(data.len() - from);
                let copy = data[from..from + len].to_vec();
                data.splice(at..at, copy);
            }
            _ => data.truncate(at),
        }
    }
    data
}

#[test]
fn mutated_inputs_never_panic() {
    let seeds: Vec<Vec<u8>> = vec![
        b";~schema: https://w3id.org/fair-bioheaders/fhr/v0.6.0\n;~genome: g\n;~checksum: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n>s\nACGT\n".to_vec(),
        b"##gff-version 3\n#~schema: https://w3id.org/fair-bioheaders/fhgff3/v0.6.0\n#~a: [1, {b: 2}]\nchr1\t.\tgene\t1\t2\t.\t+\t.\tID=g\n".to_vec(),
        b"{\"schema\": \"x\", \"a\": [1, 2.5, null, true, {\"b\": \"c\"}]}".to_vec(),
    ];
    let rounds: usize = std::env::var("FH_MUTATION_ROUNDS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(3000);
    let engine = Engine::new().unwrap();
    let containers = [
        Container::Auto,
        Container::Fasta,
        Container::Gfa,
        Container::Gff3,
        Container::MetadataYaml,
        Container::MetadataJson,
    ];
    let mut rng = Rng(0x9e37_79b9_7f4a_7c15);
    for round in 0..rounds {
        let seed = &seeds[round % seeds.len()];
        let input = mutate(&mut rng, seed);
        let container = containers[rng.below(containers.len())];
        let op = if rng.below(2) == 0 {
            Operation::Validate
        } else {
            Operation::Verify
        };
        match engine.verify_bytes(op, container, &input) {
            Ok(_) => {}
            Err(fair_bioheaders_tools::EngineError::Internal { message }) => {
                panic!("internal error on round {round}: {message}\ninput: {input:?}")
            }
            Err(_) => {}
        }
        // Streaming in odd chunk sizes must agree with one-shot reads.
        let mut stream = engine.stream(op, container);
        for chunk in input.chunks(1 + rng.below(9)) {
            stream.feed(chunk).unwrap();
        }
        let streamed = stream.finish().unwrap();
        let whole = engine.verify_bytes(op, container, &input).unwrap();
        assert_eq!(
            streamed.outcome, whole.outcome,
            "round {round}: chunked and one-shot disagree\ninput: {input:?}"
        );
    }
}
