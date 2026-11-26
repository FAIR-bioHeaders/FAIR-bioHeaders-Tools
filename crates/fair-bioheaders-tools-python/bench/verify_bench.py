# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Verify throughput and peak memory: pure-Python reader vs the engine
(specs/006 SC-006, SC-007). Not part of acceptance counts.

Generates synthetic FHR FASTA (plain, gzip, BGZF) and GFA files of the given
sizes into a temporary directory, runs ``fhr-fasta-validate`` / ``fhr-gfa-validate``
(the toolkit's verify command) with BIOHEADERS_ENGINE=python and =rust, and
reports the median wall time and peak RSS of N runs each. Files are deleted at
the end.

    python verify_bench.py --gib 2 --gfa-gib 1 --runs 5 [--keep DIR]
"""

import argparse
import base64
import gzip
import hashlib
import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zlib

HEADER = (
    "schema: https://w3id.org/fair-bioheaders/fhr/v0.6.0\n"
    "schemaVersion: '2.1'\n"
    "genome: Synthetic benchmark genome\n"
    "taxon:\n  name: Homo sapiens\n  uri: https://identifiers.org/taxonomy:9606\n"
    "version: '1'\nmetadataAuthor:\n- name: A\nassemblyAuthor:\n- name: B\n"
    "dateCreated: '2026-11-26'\nmasking: soft-masked\n"
)
LINE = (
    b"ACGTTGCAACGTAGCTAGCTAGGATCCGATCGATCGTAGCTAGCTAGCTAGCATCGATCGATCGATGCTAGC" * 2
)[:120] + b"\n"


def write_fasta(path, size, prefix=";~", record=b">chr{n} synthetic\n"):
    lines = "".join(f"{prefix}{line}\n" for line in HEADER.splitlines()).encode()
    digest = hashlib.new("sha512_256")
    digest.update(lines)
    body_size = 0
    with open(path + ".body", "wb") as out:
        n = 0
        while body_size < size:
            chunk = record.replace(b"{n}", str(n).encode()) + LINE * 8192
            out.write(chunk)
            digest.update(chunk)
            body_size += len(chunk)
            n += 1
    checksum = base64.b64encode(digest.digest()).decode()
    with open(path, "wb") as out:
        out.write(lines + f"{prefix}checksum: {checksum}\n".encode())
        with open(path + ".body", "rb") as body:
            shutil.copyfileobj(body, out, 1 << 22)
    os.remove(path + ".body")


def write_gfa(path, size):
    write_fasta(path, size, prefix="#~", record=b"S\ts{n}\t")


def bgzf(src, dst):
    block = 0xFF00
    with open(src, "rb") as inp, open(dst, "wb") as out:
        while True:
            data = inp.read(block)
            if not data:
                break
            deflated = zlib.compressobj(6, zlib.DEFLATED, -15)
            body = deflated.compress(data) + deflated.flush()
            header = bytes([31, 139, 8, 4, 0, 0, 0, 0, 0, 255, 6, 0, 66, 67, 2, 0])
            size = len(header) + 2 + len(body) + 8 - 1
            out.write(header + size.to_bytes(2, "little") + body)
            out.write(
                zlib.crc32(data).to_bytes(4, "little") + len(data).to_bytes(4, "little")
            )
        out.write(
            bytes.fromhex("1f8b08040000000000ff0600424302001b0003000000000000000000")
        )


def run(command, path, engine):
    env = {**os.environ, "BIOHEADERS_ENGINE": engine}
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    start = time.perf_counter()
    result = subprocess.run([command, path], env=env, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if result.returncode != 0:
        raise SystemExit(f"{command} {path} ({engine}) failed: {result.stderr}")
    return elapsed, max(peak, before)


def measure(command, path, engine, runs):
    # ru_maxrss of children is a high-water mark across all children, so each
    # measurement runs in a fresh helper process.
    times, peaks = [], []
    for _ in range(runs):
        helper = subprocess.run(
            [sys.executable, __file__, "--one", command, path, engine],
            capture_output=True,
            text=True,
            check=True,
        )
        t, p = json.loads(helper.stdout)
        times.append(t)
        peaks.append(p)
    return statistics.median(times), max(peaks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gib", type=float, default=2.0)
    parser.add_argument("--gfa-gib", type=float, default=1.0)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--keep")
    parser.add_argument("--one", nargs=3)
    args = parser.parse_args()
    if args.one:
        print(json.dumps(run(*args.one)))
        return
    directory = args.keep or tempfile.mkdtemp(prefix="fh-bench-")
    os.makedirs(directory, exist_ok=True)
    fasta = os.path.join(directory, "bench.fhr.fasta")
    gfa = os.path.join(directory, "bench.fhr.gfa")
    if not os.path.exists(fasta):
        write_fasta(fasta, int(args.gib * 2**30))
        with (
            open(fasta, "rb") as src,
            gzip.open(fasta + ".gz", "wb", compresslevel=6) as dst,
        ):
            shutil.copyfileobj(src, dst, 1 << 22)
        bgzf(fasta, fasta + ".bgz")
        write_gfa(gfa, int(args.gfa_gib * 2**30))
    cases = [
        ("fhr-fasta-validate", fasta, "fasta plain"),
        ("fhr-fasta-validate", fasta + ".gz", "fasta gzip"),
        ("fhr-fasta-validate", fasta + ".bgz", "fasta bgzf"),
        ("fhr-gfa-validate", gfa, "gfa plain"),
    ]
    rows = []
    for command, path, label in cases:
        size = os.path.getsize(path)
        py_time, py_rss = measure(command, path, "python", args.runs)
        rs_time, rs_rss = measure(command, path, "rust", args.runs)
        rows.append(
            {
                "case": label,
                "bytes": size,
                "runs": args.runs,
                "python_median_s": round(py_time, 3),
                "rust_median_s": round(rs_time, 3),
                "ratio_rust_over_python": round(rs_time / py_time, 3),
                "python_peak_rss_mib": round(py_rss / 1024, 1),
                "rust_peak_rss_mib": round(rs_rss / 1024, 1),
            }
        )
        print(json.dumps(rows[-1]), flush=True)
    if not args.keep:
        shutil.rmtree(directory)
    print(
        json.dumps(
            {
                "machine": (
                    os.uname()._asdict()
                    if hasattr(os.uname(), "_asdict")
                    else str(os.uname())
                ),
                "results": rows,
            }
        )
    )


if __name__ == "__main__":
    main()
