# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The binding's native values, errors and ownership (Tools#208 sections 4-5)."""

import base64
import hashlib
import io
import threading
from decimal import Decimal

import fair_bioheaders_tools as fht
import pytest

FHR = """schema: https://w3id.org/fair-bioheaders/fhr/v0.6.0
schemaVersion: '2.1'
genome: Synthetic genome
taxon:
  name: Homo sapiens
  uri: https://identifiers.org/taxonomy:9606
version: '0.0.1'
metadataAuthor:
- name: A
assemblyAuthor:
- name: B
dateCreated: '2022-03-21'
masking: soft-masked
"""

PLACEHOLDER = "checksum: '" + "A" * 43 + "='\n"


def fasta(metadata=FHR, body=b">s\nACGT\n"):
    header = "".join(f";~{line}\n" for line in metadata.splitlines()).encode()
    digest = base64.b64encode(
        hashlib.new("sha512_256", header + body).digest()
    ).decode()
    return header + f";~checksum: {digest}\n".encode() + body


def test_versions_and_provenance():
    engine = fht.Engine()
    assert fht.ABI_VERSION == "0.1"
    assert fht.ENGINE_VERSION
    provenance = engine.provenance
    assert provenance["profile_id"] == "python"
    assert provenance["limits_applied"]["in_memory_decompressed_bytes"] == (
        1 << 30,
        False,
    )


@pytest.mark.parametrize(
    "lexeme,value",
    [
        ("2147483647", 2**31 - 1),
        ("2147483648", 2**31),
        ("3100000000", 3100000000),
        ("9007199254740993", 2**53 + 1),
        ("-9007199254740993", -(2**53 + 1)),
        ("9223372036854775808", 2**63),
        ("18446744073709551616", 2**64),
        ("1000000000000000000000000000000", 10**30),
        ("0x1F", 31),
    ],
)
def test_integers_are_exact_python_ints(lexeme, value):
    report = fht.Engine().validate(
        (FHR + PLACEHOLDER + f"x-n: {lexeme}\n").encode(), container="metadata-yaml"
    )
    assert report.valid, report.first_error()
    assert isinstance(report.metadata["x-n"], int) and not isinstance(
        report.metadata["x-n"], bool
    )
    assert report.metadata["x-n"] == value


def test_decimals_float_by_default_and_decimal_when_exact():
    data = (FHR + PLACEHOLDER + "x-a: 1.10\nx-b: 0.1\n").encode()
    default = fht.Engine().validate(data, container="metadata-yaml")
    assert default.metadata["x-a"] == 1.1 and isinstance(default.metadata["x-a"], float)
    assert default.metadata["x-b"] == 0.1
    exact = fht.Engine(exact_decimals=True).validate(data, container="metadata-yaml")
    assert exact.metadata["x-a"] == Decimal("1.1") and isinstance(
        exact.metadata["x-a"], Decimal
    )


@pytest.mark.parametrize("bad", ["1.8e+308", ".inf", ".nan"])
def test_r13_float_path(bad):
    report = fht.Engine().validate(
        (FHR + PLACEHOLDER + f"x-a: {bad}\n").encode(), container="metadata-yaml"
    )
    assert report.outcome == "invalid"
    assert report.first_error().rule == "R13"


def test_verify_paths_streams_and_file_objects(tmp_path):
    data = fasta()
    path = tmp_path / "x.fhr.fasta"
    path.write_bytes(data)
    engine = fht.Engine()
    for source in (
        data,
        bytearray(data),
        memoryview(data),
        str(path),
        path,
        io.BytesIO(data),
    ):
        report = engine.verify(source, container="fasta")
        assert report.valid, report.first_error()
        assert report.checksum.matches is True
    with engine.stream("verify", container="fasta") as stream:
        for i in range(0, len(data), 5):
            stream.feed(data[i : i + 5])
        assert stream.finish().valid


def test_validate_skips_checksum_layer():
    report = fht.Engine().validate(fasta(), container="fasta")
    assert report.valid
    assert report.layers["checksum"].status == "not-run"
    assert report.layers["checksum"].not_run_reason == "not-requested"


def test_diagnostics_carry_codes_rules_and_locations():
    data = fasta(FHR.replace("soft-masked", "maybe"))
    report = fht.Engine().verify(data, container="fasta")
    first = report.first_error()
    assert report.outcome == "invalid"
    assert first.code == "SCHEMA.fhr" and first.layer == "schema"
    assert first.json_pointer == "/masking"
    late = fasta() + b";~late: 1\n"
    report = fht.Engine().verify(late, container="fasta")
    assert report.first_error().rule == "R10"
    assert report.first_error().header_line == 17


def test_unsupported_and_limit_are_distinct_outcomes():
    unsupported = fht.Engine().validate(
        (FHR.replace("v0.6.0", "v9.9.9") + PLACEHOLDER).encode(),
        container="metadata-yaml",
    )
    assert unsupported.outcome == "unsupported"
    assert unsupported.layers["schema"].not_run_reason == "blocked-by:selection"
    limited = fht.Engine(limits={"yaml_nodes": 5}).validate(
        (FHR + PLACEHOLDER).encode(), container="metadata-yaml"
    )
    assert limited.outcome == "limit"
    assert limited.first_error().code == "LIMIT.yaml-nodes"


def test_limits_cannot_be_raised_implicitly():
    with pytest.raises(ValueError):
        fht.Engine(limits={"header_bytes": 2 << 20})
    raised = fht.Engine(raise_limits={"header_bytes": 2 << 20})
    assert raised.provenance["limits_applied"]["header_bytes"] == (2 << 20, True)


def test_profile_errors():
    with pytest.raises(fht.ProfileError):
        fht.Engine("no-such-profile")
    with pytest.raises(fht.ProfileError):
        fht.Engine("test-narrow", draft_lanes=("fht",))


def test_bytes_nul_and_empty_inputs():
    body = b">s\nAC\x00\xffGT\n"
    assert fht.Engine().verify(fasta(body=body), container="fasta").valid
    assert fht.Engine().verify(b"", container="fasta").outcome == "invalid"
    report = fht.Engine().validate(b";~genome: \xff\n>s\n", container="fasta")
    assert report.first_error().rule == "R6"
    nul = fht.Engine().validate(
        (FHR + PLACEHOLDER + 'x-s: "a\\0b"\n').encode(), container="metadata-yaml"
    )
    assert nul.metadata["x-s"] == "a\x00b"


def test_threads_share_one_engine():
    engine = fht.Engine()
    data = fasta()
    results = []

    def work():
        for _ in range(50):
            results.append(engine.verify(data, container="fasta").valid)

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [True] * 200


def test_cancel_from_another_thread():
    engine = fht.Engine()
    stream = engine.stream("verify", container="fasta")
    stream.feed(b";~a: 1\n")
    threading.Thread(target=stream.cancel).start()
    import time

    time.sleep(0.05)
    with pytest.raises(fht.CancelledError):
        stream.feed(b">s\n")
    stream.close()


def test_finished_stream_refuses_use():
    stream = fht.Engine().stream("validate", container="metadata-yaml")
    stream.feed((FHR + PLACEHOLDER).encode())
    stream.finish()
    with pytest.raises(fht.StateError):
        stream.finish()


def test_internal_failures_are_contained():
    from fair_bioheaders_tools import _native

    engine = fht.Engine()
    if _native.FAULT_INJECTION:
        with pytest.raises(fht.InternalError):
            engine._native._test_panic()
        assert engine.verify(
            fasta(), container="fasta"
        ).valid  # interpreter and engine continue
    else:
        # A release wheel must not carry the fault-injection entry point.
        assert not hasattr(engine._native, "_test_panic")
