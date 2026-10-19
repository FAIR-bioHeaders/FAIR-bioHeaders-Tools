import base64
import gzip
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema.exceptions import ValidationError

from fhr import SCHEMA, fhr
from fhr.cli import checksum, combine, strip_header

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


@pytest.mark.parametrize(
    "kind", ["json", "yaml", "fasta", "gfa", "microdata", "jsonld"]
)
def test_round_trip(metadata, kind):
    metadata.update(
        assemblySoftware=[
            {
                "name": 'tool <x> & "quoted"',
                "version": "1.0",
                "commandLineOption": ["--threads", "2"],
            }
        ],
        assemblyProtocol="https://example.org/protocol",
        seqcol_id="A" * 32,
        vitalStats={"N90": 10, "gcContent": 42.5},
        relatedLink=[],
        funding="",
    )
    original = fhr(**metadata)
    loaded = fhr()
    getattr(loaded, "input_" + kind)(getattr(original, "output_" + kind)())
    assert loaded.__dict__ == metadata
    loaded.fhr_validate()


def test_minimal_and_optional_fields(metadata):
    minimal = {key: metadata[key] for key in SCHEMA["required"]}
    instance = fhr(**minimal)
    instance.fhr_validate()
    for kind in ("json", "yaml", "fasta", "gfa", "microdata"):
        loaded = fhr()
        getattr(loaded, "input_" + kind)(getattr(instance, "output_" + kind)())
        assert loaded.__dict__ == minimal
    other = fhr()
    other.input_json(instance.output_json())
    other.genome = "other"
    assert instance.genome != other.genome


@pytest.mark.parametrize(
    "field,value",
    [
        ("dateCreated", "2026-02-30"),
        ("seqcol_id", "invalid"),
        ("seqcol_id", "A" * 32 + "\n"),
        ("relatedLink", ["not a URI"]),
        ("vitalStats", {"gcContent": 101}),
        ("assemblySoftware", [{"version": "1"}]),
    ],
)
def test_validation_rejects_invalid_fields(metadata, field, value):
    metadata[field] = value
    with pytest.raises(ValidationError):
        fhr(**metadata).fhr_validate()


def test_legacy_software_and_yaml_dates(metadata):
    metadata["assemblySoftware"] = "HiFiASM"
    data = fhr(**metadata)
    data.fhr_validate()
    text = data.output_yaml().replace(
        "dateCreated: '2022-03-21'", "dateCreated: 2022-03-21"
    )
    loaded = fhr()
    loaded.input_yaml(text)
    assert loaded.dateCreated == "2022-03-21"
    loaded.fhr_validate()


@pytest.mark.parametrize(
    "kind,body",
    [
        ("fasta", b"; ordinary comment\r\n>ctg\r\nACGT\r\n"),
        ("gfa", b"# ordinary comment\r\nH\tVN:Z:1.0\r\nS\tctg\tACGT\r\n"),
    ],
)
def test_combine_strip_and_checksum_preserve_bytes(metadata, kind, body):
    original = deepcopy(metadata)
    combined = combine(fhr(**metadata), body, kind)
    assert strip_header(combined, kind) == body
    assert metadata == original
    loaded = fhr()
    getattr(loaded, "input_" + kind)(combined)
    assert checksum(combined, kind) == loaded.checksum
    prefix = b";~" if kind == "fasta" else b"#~"
    covered = b"".join(
        line
        for line in combined.splitlines(keepends=True)
        if not line.startswith(prefix + b"checksum:")
    )
    expected = base64.b64encode(hashlib.new("sha512_256", covered).digest()).decode()
    assert expected == loaded.checksum
    assert checksum(combined.replace(b"ACGT", b"ACGA"), kind) != expected
    assert (
        checksum(combined.replace(b"genome: ", b"genome: changed "), kind) != expected
    )
    assert strip_header(combine(loaded, combined, kind), kind) == body


def test_checksum_line_is_required_and_unique():
    with pytest.raises(ValueError, match="exactly one"):
        checksum(b">ctg\nACGT\n", "fasta")
    with pytest.raises(ValueError, match="exactly one"):
        checksum(b";~checksum: one\n;~checksum: two\n", "fasta")


def test_invalid_inputs():
    with pytest.raises(ValueError):
        fhr().input_yaml("- list")
    with pytest.raises(ValueError):
        fhr().input_fasta(">ctg\nACGT")
    with pytest.raises(ValueError):
        fhr().input_microdata("<html>no metadata</html>")


def command(tmp_path, script, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / script), *map(str, args)],
        cwd=tmp_path,
        capture_output=True,
    )


def test_cli_all_formats_and_sequence_helpers(metadata, tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(metadata))
    for extension in ("yaml", "json", "fasta", "gfa", "html", "jsonld", "jsonld.gz"):
        output = tmp_path / ("output." + extension)
        result = command(tmp_path, "fhr_convert.py", source, output)
        assert result.returncode == 0, result.stderr
        assert command(tmp_path, "fhr_validate.py", output).returncode == 0
    jsonld_text = (tmp_path / "output.jsonld").read_bytes()
    assert gzip.decompress((tmp_path / "output.jsonld.gz").read_bytes()) == jsonld_text
    back = tmp_path / "back.json"
    assert (
        command(
            tmp_path, "fhr_convert.py", tmp_path / "output.jsonld.gz", back
        ).returncode
        == 0
    )
    assert json.loads(back.read_text()) == metadata
    piped = subprocess.run(
        [
            sys.executable,
            str(ROOT / "fhr_convert.py"),
            "--from",
            "jsonld",
            "--to",
            "yaml",
            "-",
            "-",
        ],
        input=jsonld_text,
        capture_output=True,
        cwd=tmp_path,
    )
    assert piped.returncode == 0, piped.stderr
    assert yaml.safe_load(piped.stdout) == metadata
    piped = subprocess.run(
        [
            sys.executable,
            str(ROOT / "fhr_convert.py"),
            "--from",
            "json",
            "--to",
            "jsonld",
            "-",
            "-",
        ],
        input=source.read_bytes(),
        capture_output=True,
        cwd=tmp_path,
    )
    assert piped.stdout == jsonld_text
    for kind, payload in (("fasta", b">ctg\r\nACGT\r\n"), ("gfa", b"S\tctg\tACGT\r\n")):
        sequence = tmp_path / ("sequence." + kind)
        sequence.write_bytes(payload)
        combined = tmp_path / ("combined." + kind)
        result = command(
            tmp_path, f"{kind}/fhr_{kind}_combine.py", source, sequence, "-o", combined
        )
        assert result.returncode == 0, result.stderr
        from_jsonld = tmp_path / ("from-jsonld." + kind)
        result = command(
            tmp_path,
            f"{kind}/fhr_{kind}_combine.py",
            tmp_path / "output.jsonld",
            sequence,
            "-o",
            from_jsonld,
        )
        assert result.returncode == 0, result.stderr
        assert from_jsonld.read_bytes() == combined.read_bytes()
        assert (
            command(tmp_path, f"{kind}/fhr_{kind}_validate.py", combined).returncode
            == 0
        )
        stripped = tmp_path / ("stripped." + kind)
        assert (
            command(
                tmp_path, f"{kind}/fhr_{kind}_strip.py", combined, stripped
            ).returncode
            == 0
        )
        assert stripped.read_bytes() == payload
        assert (
            command(tmp_path, f"{kind}/fhr_{kind}_strip.py", combined).stdout == payload
        )
        combined.write_bytes(combined.read_bytes().replace(b"ACGT", b"ACGA"))
        assert (
            command(tmp_path, f"{kind}/fhr_{kind}_validate.py", combined).returncode
            == 1
        )


def test_cli_errors_do_not_overwrite_output(metadata, tmp_path):
    source = tmp_path / "bad.json"
    source.write_text('{"genome": "missing everything"}')
    output = tmp_path / "output.yaml"
    output.write_text("keep me")
    result = command(tmp_path, "fhr_convert.py", source, output)
    assert result.returncode == 1
    assert output.read_text() == "keep me"


def test_installed_entry_points_outside_checkout(tmp_path):
    bin_path = Path(sys.executable).parent
    for name in (
        "fhr-convert",
        "fhr-validate",
        "fhr-fasta-combine",
        "fhr-fasta-strip",
        "fhr-fasta-validate",
        "fhr-gfa-combine",
        "fhr-gfa-strip",
        "fhr-gfa-validate",
    ):
        result = subprocess.run(
            [str(bin_path / name), "--version"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "0.8.0"
    result = subprocess.run(
        [str(bin_path / "fhr-validate"), str(ROOT / "examples/minimal.fhr.json")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # JSON-LD from outside the checkout: the bundled context must be installed.
    for source, target in (
        (ROOT / "examples/example.fhr.json", tmp_path / "out.jsonld"),
        (tmp_path / "out.jsonld", tmp_path / "back.json"),
    ):
        result = subprocess.run(
            [str(bin_path / "fhr-convert"), str(source), str(target)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.jsonld").read_bytes() == (
        ROOT / "examples/example.fhr.jsonld"
    ).read_bytes()
    assert json.loads((tmp_path / "back.json").read_text()) == json.loads(
        (ROOT / "examples/example.fhr.json").read_text()
    )


def test_bundled_schema_and_all_examples(metadata):
    assert SCHEMA == json.loads((ROOT / "fhr_schema.json").read_text())
    from fhr.cli import read_metadata

    for path in (ROOT / "examples").iterdir():
        if not path.is_file():  # examples/fhp/ is checked in fhp_test.py.
            continue
        if path.name.endswith(".export.jsonld"):  # one-way: jsonld_export_test.py
            continue
        data = read_metadata(path)
        data.fhr_validate()
        if path.suffix in {".fasta", ".gfa"}:
            kind = "fasta" if path.suffix == ".fasta" else "gfa"
            assert checksum(path.read_bytes(), kind) == data.checksum
        if path.name.startswith("example"):
            original = deepcopy(metadata)
            loaded = deepcopy(data.__dict__)
            original.pop("checksum")
            loaded.pop("checksum")
            assert loaded == original


def test_input_rejects_nonfinite_values_and_nonstring_keys():
    with pytest.raises(ValueError):
        fhr().input_json('{"vitalStats": {"gcContent": NaN}}')
    with pytest.raises(ValueError):
        fhr().input_yaml("vitalStats:\n  1: bad key\n")


def test_microdata_preserves_string_whitespace_and_unicode(metadata):
    metadata["documentation"] = '  α <tag> & "quoted"\nline two  '
    instance = fhr(**metadata)
    loaded = fhr()
    loaded.input_microdata(instance.output_microdata())
    assert loaded.documentation == metadata["documentation"]


def test_microdata_rejects_multiple_roots(metadata):
    instance = fhr(**metadata)
    with pytest.raises(ValueError, match="Multiple"):
        fhr().input_microdata(instance.output_microdata() * 2)


def test_microdata_recognizes_all_void_elements(metadata):
    metadata["documentation"] = "leftright"
    instance = fhr(**metadata)
    html = instance.output_microdata().replace(
        "leftright</span>",
        "left"
        + "".join(
            f"<{tag}>"
            for tag in (
                "area",
                "base",
                "br",
                "col",
                "embed",
                "hr",
                "img",
                "input",
                "link",
                "meta",
                "param",
                "source",
                "track",
                "wbr",
            )
        )
        + "right</span>",
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.documentation == "leftright"


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_sequence_headers_preserve_unicode_line_separators(metadata, kind):
    metadata["documentation"] = "before\u2028middle\u2029after"
    instance = fhr(**metadata)
    header = getattr(instance, "output_" + kind)()
    # YAML reads raw U+2028/U+2029 as line breaks, so they must be escaped.
    assert "\u2028" not in header
    assert "\u2029" not in header
    assert "\\L" in header and "\\P" in header
    loaded = fhr()
    body = ">ctg\nACGT\n" if kind == "fasta" else "S\tctg\tACGT\n"
    getattr(loaded, "input_" + kind)(header + body)
    assert loaded.documentation == metadata["documentation"]


def test_unsupported_hash_reports_runtime_requirement(monkeypatch):
    def unavailable(name):
        raise ValueError("unsupported hash")

    monkeypatch.setattr(hashlib, "new", unavailable)
    with pytest.raises(ValueError, match="Python distribution with OpenSSL"):
        checksum(b";~checksum: placeholder\n>ctg\nACGT\n", "fasta")


def test_nested_checksum_names_stay_covered(metadata):
    # A "checksum:" line that is not the root key stays covered. Since v0.4
    # closes every nested object, multi-line free text is where it can occur.
    metadata["documentation"] = "Assembly notes.\nchecksum: nested-value\n"
    combined = combine(fhr(**metadata), b">ctg\nACGT\n", "fasta")
    assert b"checksum: nested-value" in combined
    assert not combined.count(b";~checksum: nested-value")
    original = checksum(combined, "fasta")
    assert (
        checksum(combined.replace(b"nested-value", b"changed-value"), "fasta")
        != original
    )


def test_root_indentation_for_checksum_line():
    first = b";~ schema: example\n;~ checksum: placeholder\n;~ documentation: |\n;~   checksum: nested\n>ctg\nACGT\n"
    assert checksum(first, "fasta") != checksum(
        first.replace(b"nested", b"changed"), "fasta"
    )


@pytest.mark.parametrize(("kind", "prefix"), [("fasta", b";~"), ("gfa", b"#~")])
def test_checksum_root_indentation_ignores_yaml_markers(kind, prefix):
    content = (
        prefix
        + b"%YAML 1.2\n"
        + prefix
        + b"--- # metadata\n"
        + prefix
        + b" schema: example\n"
        + prefix
        + b" checksum: placeholder\n"
        + b">ctg\nACGT\n"
    )
    digest = checksum(content, kind)
    assert digest != checksum(content.replace(b"ACGT", b"ACGA"), kind)
    assert digest != checksum(content.replace(b"%YAML 1.2", b"%YAML 1.1"), kind)
    assert digest != checksum(
        content.replace(b"--- # metadata", b"--- # changed"), kind
    )


def test_cli_same_path_preserves_input(metadata, tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(metadata))
    original = source.read_bytes()
    result = command(tmp_path, "fhr_convert.py", source, source)
    assert result.returncode == 1
    assert source.read_bytes() == original


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_cli_hardlinked_outputs_preserve_inputs(metadata, tmp_path, kind):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(metadata))
    conversion_link = tmp_path / "conversion.yaml"
    os.link(source, conversion_link)
    original = source.read_bytes()
    result = command(tmp_path, "fhr_convert.py", source, conversion_link)
    assert result.returncode == 1
    assert source.read_bytes() == original
    assert conversion_link.read_bytes() == original

    sequence = tmp_path / ("sequence." + kind)
    sequence.write_bytes(b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n")
    for linked_input in (source, sequence):
        output = tmp_path / f"combined-{linked_input.name}.{kind}"
        os.link(linked_input, output)
        before = linked_input.read_bytes()
        result = command(
            tmp_path,
            f"{kind}/fhr_{kind}_combine.py",
            source,
            sequence,
            "-o",
            output,
        )
        assert result.returncode == 1
        assert linked_input.read_bytes() == before
        assert output.read_bytes() == before

    combined = tmp_path / f"combined.{kind}"
    result = command(
        tmp_path,
        f"{kind}/fhr_{kind}_combine.py",
        source,
        sequence,
        "-o",
        combined,
    )
    assert result.returncode == 0, result.stderr
    strip_link = tmp_path / f"strip-link.{kind}"
    os.link(combined, strip_link)
    before = combined.read_bytes()
    result = command(tmp_path, f"{kind}/fhr_{kind}_strip.py", combined, strip_link)
    assert result.returncode == 1
    assert combined.read_bytes() == before
    assert strip_link.read_bytes() == before


def test_standard_microdata_properties(metadata):
    instance = fhr(**metadata)
    html = instance.output_microdata()
    html = html.replace(
        '<span itemprop="schemaVersion" data-fhr-type="string">2.0</span>',
        '<meta itemprop="schemaVersion" content="2.0">',
    )
    html = html.replace(
        '<span itemprop="assemblyProtocol" data-fhr-type="string">https://example.org/assembly-protocol</span>',
        '<a itemprop="assemblyProtocol" href="https://example.org/assembly-protocol"></a>',
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.__dict__ == metadata


def test_independent_microdata_scope_does_not_leak(metadata):
    html = fhr(**metadata).output_microdata()
    unrelated = (
        '<section itemscope itemtype="https://schema.org/Person">'
        '<div><span itemprop="name">Alice</span></div></section>'
    )
    html = html.replace("</div>", unrelated + "</div>")
    loaded = fhr()
    loaded.input_microdata(html)
    loaded.fhr_validate()
    assert loaded.__dict__ == metadata


@pytest.mark.parametrize("tag", ["data", "meter"])
def test_standard_microdata_machine_values(metadata, tag):
    html = fhr(**metadata).output_microdata()
    date = metadata["dateCreated"]
    html = html.replace(
        f'<span itemprop="dateCreated" data-fhr-type="string">{date}</span>',
        f'<time itemprop="dateCreated" datetime="{date}">Human-readable date</time>',
    )
    version = metadata["schemaVersion"]
    html = html.replace(
        f'<span itemprop="schemaVersion" data-fhr-type="string">{version}</span>',
        f'<{tag} itemprop="schemaVersion" value="{version}">Version one</{tag}>',
    )
    loaded = fhr()
    loaded.input_microdata(html)
    loaded.fhr_validate()
    assert loaded.__dict__ == metadata


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_duplicate_header_keys_are_rejected(metadata, kind):
    prefix = b";~" if kind == "fasta" else b"#~"
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    combined = combine(fhr(**metadata), body, kind)
    repeated = prefix + b"genome: repeated\n" + combined
    with pytest.raises(yaml.YAMLError, match="duplicate key"):
        getattr(fhr(), "input_" + kind)(repeated)
    nested = combined.replace(
        prefix + b"taxon:\n", prefix + b"taxon:\n" + prefix + b"  name: first\n"
    )
    with pytest.raises(yaml.YAMLError, match="duplicate key"):
        getattr(fhr(), "input_" + kind)(nested)


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_header_lines_after_sequence_data_are_rejected(metadata, kind):
    prefix = b";~" if kind == "fasta" else b"#~"
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    combined = combine(fhr(**metadata), body, kind)
    late = combined + prefix + b"documentation: after the sequence\n"
    concatenated = combined + combined
    for content in (late, concatenated):
        with pytest.raises(ValueError, match="after sequence data at line"):
            getattr(fhr(), "input_" + kind)(content)
        with pytest.raises(ValueError, match="after sequence data at line"):
            checksum(content, kind)
        with pytest.raises(ValueError, match="after sequence data at line"):
            strip_header(content, kind)


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_comments_and_blank_lines_may_precede_header_lines(metadata, kind):
    comment = b";" if kind == "fasta" else b"#"
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    combined = combine(fhr(**metadata), body, kind)
    content = comment + b" ordinary comment\n\n" + combined
    loaded = fhr()
    getattr(loaded, "input_" + kind)(content)
    assert loaded.genome == metadata["genome"]
    checksum(content, kind)
    assert strip_header(content, kind) == comment + b" ordinary comment\n\n" + body


def test_duplicate_keys_are_rejected_in_yaml_and_json():
    with pytest.raises(yaml.YAMLError, match="duplicate key"):
        fhr().input_yaml("genome: one\ngenome: two\n")
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        fhr().input_json('{"genome": "one", "genome": "two"}')


@pytest.mark.parametrize(
    "text",
    [
        "a: &a [x, x]\nb: [*a, *a]\n",
        "a: &a {x: 1}\nb: *a\n",
        "base: {genome: x}\n<<: {genome: y}\n",
    ],
)
def test_yaml_anchors_aliases_and_merge_keys_are_rejected(text):
    with pytest.raises(yaml.YAMLError, match="not allowed"):
        fhr().input_yaml(text)


def test_yaml_alias_expansion_is_not_attempted():
    lines = ["a0: &a0 [x, x, x, x, x, x, x, x, x, x]"]
    lines += [
        f"a{i}: &a{i} [" + ", ".join([f"*a{i - 1}"] * 10) + "]" for i in range(1, 9)
    ]
    with pytest.raises(yaml.YAMLError, match="not allowed"):
        fhr().input_fasta("".join(f";~{line}\n" for line in lines))


def _replace_checksum_line(combined, prefix, replacement):
    lines = combined.split(b"\n")
    index = next(
        i for i, line in enumerate(lines) if line.startswith(prefix + b"checksum:")
    )
    value = lines[index].split(b": ", 1)[1]
    lines[index] = replacement(value)
    return b"\n".join(lines)


@pytest.mark.parametrize(
    "replacement",
    [
        lambda value: b";~checksum: >-\n;~  " + value,
        lambda value: b";~checksum: |\n;~  " + value,
        lambda value: b";~checksum:\n;~  " + value,
        lambda value: b';~checksum: "' + value[:-1] + b'\\\n;~="',
        lambda value: b";~checksum: " + value[:22] + b"\n;~  " + value[22:],
    ],
)
def test_checksum_value_must_be_on_its_line(metadata, replacement):
    combined = combine(fhr(**metadata), b">ctg\nACGT\n", "fasta")
    changed = _replace_checksum_line(combined, b";~", replacement)
    with pytest.raises(ValueError, match="single-line scalar"):
        checksum(changed, "fasta")


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
def test_yaml_only_line_breaks_cannot_hide_metadata(metadata, separator):
    # YAML would read text after the separator as an uncovered root property.
    del metadata["voucherSpecimen"]
    combined = combine(fhr(**metadata), b">ctg\nACGT\n", "fasta")
    smuggled = _replace_checksum_line(
        combined,
        b";~",
        lambda value: b";~checksum: "
        + value
        + (separator + "voucherSpecimen: changed").encode("utf-8"),
    )
    with pytest.raises(ValueError, match="U\\+2028"):
        fhr().input_fasta(smuggled)
    with pytest.raises(ValueError, match="U\\+2028"):
        checksum(smuggled, "fasta")


@pytest.mark.parametrize("value", ["a\x85b", "a\u2028b", "a\u2029b"])
def test_yaml_only_line_breaks_round_trip_escaped(metadata, value):
    metadata["documentation"] = value
    for kind in ("yaml", "fasta", "gfa"):
        output = getattr(fhr(**metadata), "output_" + kind)()
        assert not any(char in output for char in "\x85\u2028\u2029")
        loaded = fhr()
        getattr(loaded, "input_" + kind)(output)
        assert loaded.documentation == value


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_sequence_byte_order_mark_is_rejected(metadata, kind):
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    combined = b"\xef\xbb\xbf" + combine(fhr(**metadata), body, kind)
    for action in (
        lambda: getattr(fhr(), "input_" + kind)(combined),
        lambda: checksum(combined, kind),
        lambda: strip_header(combined, kind),
        lambda: combine(fhr(**metadata), b"\xef\xbb\xbf" + body, kind),
    ):
        with pytest.raises(ValueError, match="byte order mark"):
            action()


def test_metadata_byte_order_mark_is_ignored(metadata, tmp_path):
    from fhr.cli import read_metadata

    for name, text in (
        ("bom.json", fhr(**metadata).output_json()),
        ("bom.yaml", fhr(**metadata).output_yaml()),
        ("bom.html", fhr(**metadata).output_microdata()),
    ):
        path = tmp_path / name
        path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
        assert read_metadata(path).__dict__ == metadata
        assert command(tmp_path, "fhr_validate.py", path).returncode == 0


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_non_utf8_sequence_bytes_outside_header(metadata, tmp_path, kind):
    body = b">ctg caf\xe9\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\tCO:Z:\xe9\n"
    combined = tmp_path / ("combined." + kind)
    combined.write_bytes(combine(fhr(**metadata), body, kind))
    result = command(tmp_path, f"{kind}/fhr_{kind}_validate.py", combined)
    assert result.returncode == 0, result.stderr


def test_microdata_implied_end_tags(metadata):
    html = fhr(**metadata).output_microdata()
    html = "<html><body><p>Intro" + html.replace(
        "</div>\n",
        "<p>note<p>second note<ul><li>one<li>two</ul>"
        "<table><tr><td>a<td>b<tr><td>c</table></div>",
    )
    html += "<p>trailing paragraph"
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.__dict__ == metadata


def test_microdata_implied_end_tags_keep_sibling_properties(metadata):
    del metadata["voucherSpecimen"], metadata["funding"]
    html = fhr(**metadata).output_microdata()
    html = html.replace(
        "</div>\n",
        '<p itemprop="voucherSpecimen">voucher<p itemprop="funding">funds</div>',
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.voucherSpecimen == "voucher"
    assert loaded.funding == "funds"


def test_microdata_itemtype_token_list(metadata):
    html = (
        fhr(**metadata)
        .output_microdata()
        .replace('itemtype="', 'itemtype="https://schema.org/Dataset\n ', 1)
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.__dict__ == metadata


def test_microdata_scope_closed_by_ancestor_does_not_leak(metadata):
    html = fhr(**metadata).output_microdata()
    html = (
        "<section>"
        + html.replace("</div>\n", "")
        + "</section><span itemprop='voucherSpecimen'>leak</span>"
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.__dict__ == metadata


def test_microdata_ignores_content_attribute_on_ordinary_elements(metadata):
    html = fhr(**metadata).output_microdata()
    genome = metadata["genome"]
    html = html.replace(
        f'<span itemprop="genome" data-fhr-type="string">{genome}</span>',
        f'<span itemprop="genome" content="other">{genome}</span>',
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.genome == genome


def test_microdata_typed_values_must_match_type(metadata):
    html = (
        fhr(**metadata)
        .output_microdata()
        .replace('data-fhr-type="number">37.5<', 'data-fhr-type="number">[37.5]<')
    )
    with pytest.raises(ValueError, match="not a JSON number"):
        fhr().input_microdata(html)


def test_microdata_uses_first_duplicate_attribute(metadata):
    html = fhr(**metadata).output_microdata()
    html = html.replace(
        '<span itemprop="genome"', '<span itemprop="genome" itemprop="voucherSpecimen"'
    )
    loaded = fhr()
    loaded.input_microdata(html)
    assert loaded.__dict__ == metadata


def test_microdata_unclosed_scope_is_rejected(metadata):
    html = fhr(**metadata).output_microdata().replace("</div>\n", "")
    with pytest.raises(ValueError, match="No complete"):
        fhr().input_microdata(html)


def test_cli_validation_error_is_concise(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text('{"genome": "missing everything"}')
    result = command(tmp_path, "fhr_validate.py", source)
    assert result.returncode == 1
    error = result.stderr.decode()
    assert error.startswith("FHR: schema validation failed at $")
    assert "$schema" not in error and len(error.splitlines()) == 1


@pytest.mark.parametrize("name,start", [("deep.json", ""), ("deep.yaml", "a: ")])
def test_cli_deep_nesting_is_an_error(tmp_path, name, start):
    source = tmp_path / name
    source.write_text(start + "[" * 100000 + "]" * 100000)
    result = command(tmp_path, "fhr_validate.py", source)
    assert result.returncode == 1
    assert result.stderr.decode() == "FHR: metadata is nested too deeply\n"
