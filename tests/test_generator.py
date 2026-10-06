from __future__ import annotations
"""
test_generator.py
-----------------
Pytest test suite for generator.py.

Covers:
  - Output structure (HEADER start, FOOTER end, exactly once each)
  - Single gate and all 9 gates verbatim
  - Block ordering and order sensitivity
  - Repeated gates and large sequences (100 gates)
  - Setup once (prep directly after header, readout before footer, never unrequested)
  - Absence of #ifdef, #endif, #define
  - Phase definitions and d2 parameter line
  - Channel mapping (Variant A: NOT1 on :f2; Variant B: NOT1 on :f1)
  - Validation errors (empty list, unknown gates, bad variant, bad readout)
  - CLI execution and error handling with tmp_path and subprocess
  - Determinism (byte-identical outputs)
  - Regression testing against original_variant_A.txt and original_variant_B.txt
"""

import subprocess
import sys
from pathlib import Path

import pytest

from gate_library import (
    VARIANT_A_HEADER,
    VARIANT_A_PREP,
    VARIANT_A_GATE_LIBRARY,
    VARIANT_A_READOUT_PULSE,
    VARIANT_A_FOOTER,
    VARIANT_B_HEADER,
    VARIANT_B_PREP,
    VARIANT_B_GATE_LIBRARY,
    VARIANT_B_READOUT_PULSE,
    VARIANT_B_FOOTER,
)
from generator import (
    generate_pulse_program,
    strip_provenance,
    PROVENANCE_MARKER,
)

GENERATOR = Path(__file__).resolve().parent.parent / "src" / "generator.py"

ALL_GATES_A = list(VARIANT_A_GATE_LIBRARY.keys())
ALL_GATES_B = list(VARIANT_B_GATE_LIBRARY.keys())


# ===========================================================================
# 1. Structure: starts with HEADER, ends with FOOTER, each appears once
# ===========================================================================

@pytest.mark.parametrize("variant,header,footer", [
    ("A", VARIANT_A_HEADER, VARIANT_A_FOOTER),
    ("B", VARIANT_B_HEADER, VARIANT_B_FOOTER),
    ("a", VARIANT_A_HEADER, VARIANT_A_FOOTER),
    ("b", VARIANT_B_HEADER, VARIANT_B_FOOTER),
])
def test_structure_header_footer(variant: str, header: str, footer: str):
    prog = generate_pulse_program(["NOT1", "HAD"], variant=variant)
    assert prog.startswith(PROVENANCE_MARKER)
    assert strip_provenance(prog).startswith(header)
    assert prog.endswith(footer)
    assert prog.count(header) == 1
    assert prog.count(footer) == 1


# ===========================================================================
# 2. Single gate, and all 9 gates once each: every gate block appears verbatim
# ===========================================================================

@pytest.mark.parametrize("gate_name", ALL_GATES_A)
def test_single_gate_verbatim_variant_a(gate_name: str):
    prog = generate_pulse_program([gate_name], variant="A")
    expected_block = VARIANT_A_GATE_LIBRARY[gate_name]
    assert expected_block in prog


@pytest.mark.parametrize("gate_name", ALL_GATES_B)
def test_single_gate_verbatim_variant_b(gate_name: str):
    prog = generate_pulse_program([gate_name], variant="B")
    expected_block = VARIANT_B_GATE_LIBRARY[gate_name]
    assert expected_block in prog


def test_all_nine_gates_verbatim_variant_a():
    prog = generate_pulse_program(ALL_GATES_A, variant="A")
    for g in ALL_GATES_A:
        block = VARIANT_A_GATE_LIBRARY[g]
        assert block in prog
        assert prog.count(block) == 1


def test_all_nine_gates_verbatim_variant_b():
    prog = generate_pulse_program(ALL_GATES_B, variant="B")
    for g in ALL_GATES_B:
        block = VARIANT_B_GATE_LIBRARY[g]
        assert block in prog
        assert prog.count(block) == 1


# ===========================================================================
# 3. Order: positions follow input order; different orders give different output
# ===========================================================================

def test_gate_ordering_followed():
    sequence = ["CNOT12", "HAD", "NOT1", "PHAD"]
    prog = generate_pulse_program(sequence, variant="A")
    positions = [prog.find(VARIANT_A_GATE_LIBRARY[g]) for g in sequence]
    assert all(pos != -1 for pos in positions)
    assert positions == sorted(positions)


def test_different_gate_order_produces_different_output():
    seq1 = ["HAD", "NOT1"]
    seq2 = ["NOT1", "HAD"]
    prog1 = generate_pulse_program(seq1, variant="A")
    prog2 = generate_pulse_program(seq2, variant="A")

    assert prog1 != prog2
    pos_had_1 = prog1.find(VARIANT_A_GATE_LIBRARY["HAD"])
    pos_not1_1 = prog1.find(VARIANT_A_GATE_LIBRARY["NOT1"])
    assert pos_had_1 < pos_not1_1

    pos_had_2 = prog2.find(VARIANT_A_GATE_LIBRARY["HAD"])
    pos_not1_2 = prog2.find(VARIANT_A_GATE_LIBRARY["NOT1"])
    assert pos_not1_2 < pos_had_2


# ===========================================================================
# 4. Repeated gates: NOT1, NOT1, HAD has 2x NOT1; 100-gate sequence counts
# ===========================================================================

def test_repeated_gates_exact_count():
    seq = ["NOT1", "NOT1", "HAD"]
    prog = generate_pulse_program(seq, variant="A")
    not1_block = VARIANT_A_GATE_LIBRARY["NOT1"]
    had_block = VARIANT_A_GATE_LIBRARY["HAD"]

    assert prog.count(not1_block) == 2
    assert prog.count(had_block) == 1


def test_hundred_gate_sequence():
    pattern = ["NOT1", "HAD", "CNOT12", "NOT2", "PHAD"]
    seq = pattern * 20  # 100 gates total
    assert len(seq) == 100

    prog = generate_pulse_program(seq, variant="A")
    for g in pattern:
        block = VARIANT_A_GATE_LIBRARY[g]
        assert prog.count(block) == 20


# ===========================================================================
# 5. Setup once: prep and readout appear at most once and in correct locations
# ===========================================================================

@pytest.mark.parametrize("variant,header,prep_block", [
    ("A", VARIANT_A_HEADER, VARIANT_A_PREP),
    ("B", VARIANT_B_HEADER, VARIANT_B_PREP),
])
def test_prep_appears_once_directly_after_header(
    variant: str, header: str, prep_block: str
):
    seq = ["NOT1"] * 20
    prog = generate_pulse_program(seq, variant=variant, prep=True)

    assert prog.count(prep_block) == 1
    # Directly after header + blank line, within the pulse code itself
    body = strip_provenance(prog)
    expected_offset = len(header) + len("\n")
    assert body.find(prep_block) == expected_offset


def test_readout_obspop_appears_once_after_gates_before_footer():
    seq = ["NOT1", "HAD"]
    prog = generate_pulse_program(seq, variant="A", readout="OBSPOP")
    obspop_block = VARIANT_A_READOUT_PULSE["OBSPOP"]
    footer = VARIANT_A_FOOTER
    last_gate_pos = prog.find(VARIANT_A_GATE_LIBRARY["HAD"])
    obspop_pos = prog.find(obspop_block)
    footer_pos = prog.find(footer)

    assert prog.count(obspop_block) == 1
    assert last_gate_pos < obspop_pos < footer_pos


def test_readout_init_appears_once_after_gates_before_footer():
    seq = ["NOT1", "HAD"]
    prog = generate_pulse_program(seq, variant="B", readout="INIT")
    init_block = VARIANT_B_READOUT_PULSE["INIT"]
    footer = VARIANT_B_FOOTER
    last_gate_pos = prog.find(VARIANT_B_GATE_LIBRARY["HAD"])
    init_pos = prog.find(init_block)
    footer_pos = prog.find(footer)

    assert prog.count(init_block) == 1
    assert last_gate_pos < init_pos < footer_pos


@pytest.mark.parametrize("variant,prep_block", [
    ("A", VARIANT_A_PREP),
    ("B", VARIANT_B_PREP),
])
def test_prep_is_on_by_default(variant: str, prep_block: str):
    """
    PPS is the starting point of every quantum algorithm on this system, so it
    must be emitted unless explicitly suppressed. Omitting it silently would
    run the circuit from thermal equilibrium instead of a pseudo-pure state.
    """
    prog = generate_pulse_program(["HAD", "CNOT12"], variant=variant)
    assert prog.count(prep_block) == 1


def test_cli_emits_prep_without_any_flag(tmp_path: Path):
    out_file = tmp_path / "default.txt"
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "HAD, CNOT12", "-o", str(out_file)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert VARIANT_A_PREP in out_file.read_text(encoding="utf-8")


def test_cli_no_prep_flag_suppresses_prep(tmp_path: Path):
    out_file = tmp_path / "noprep.txt"
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "HAD, CNOT12", "--no-prep", "-o", str(out_file)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert VARIANT_A_PREP not in out_file.read_text(encoding="utf-8")


def test_prep_and_readout_never_appear_when_not_requested():
    prog = generate_pulse_program(["NOT1", "HAD"], variant="A", prep=False, readout=None)
    assert VARIANT_A_PREP not in prog
    assert VARIANT_A_READOUT_PULSE["OBSPOP"] not in prog
    assert VARIANT_A_READOUT_PULSE["INIT"] not in prog


# ===========================================================================
# 6. Absence of #ifdef, #endif, #define
# ===========================================================================

@pytest.mark.parametrize("variant", ["A", "B"])
@pytest.mark.parametrize("prep", [False, True])
@pytest.mark.parametrize("readout", [None, "OBSPOP", "INIT"])
def test_no_preprocessor_directives_in_output(variant: str, prep: bool, readout: str | None):
    prog = generate_pulse_program(["NOT1", "HAD", "CNOT12"], variant=variant, prep=prep, readout=readout)
    assert "#ifdef" not in prog
    assert "#endif" not in prog
    assert "#define" not in prog
    assert ";#define" not in prog


# ===========================================================================
# 7. Phase definitions (ph0=0 to ph31=0) and d2 line present in every output
# ===========================================================================

@pytest.mark.parametrize("variant", ["A", "B"])
def test_phase_definitions_and_d2_present(variant: str):
    prog = generate_pulse_program(["NOT1"], variant=variant)
    assert '"d2=1/(4*cnst1)" ; 1/4J free evolution' in prog
    assert "ph0=0" in prog
    assert "ph1=1" in prog
    assert "ph2 =2" in prog
    assert "ph3 =3" in prog
    assert "ph31=0" in prog


# ===========================================================================
# 8. Channel mapping: Variant A NOT1 on :f2, Variant B NOT1 on :f1
# ===========================================================================

def test_hardware_channel_mapping():
    prog_a = generate_pulse_program(["NOT1"], variant="A")
    prog_b = generate_pulse_program(["NOT1"], variant="B")

    assert "(p4 pl2 ph3):f2 ;180 deg y-pulse on 1h" in prog_a
    assert "(p4 pl1 ph3):f1 ;180 deg y-pulse on 1h" in prog_b


# ===========================================================================
# 9. Errors: empty list, unknown gate, bad variant, bad readout, CLI behavior
# ===========================================================================

def test_error_empty_gate_list():
    with pytest.raises(ValueError, match="empty"):
        generate_pulse_program([])


def test_error_unknown_gate():
    with pytest.raises(ValueError, match="Unknown gate"):
        generate_pulse_program(["UNKNOWN_GATE"])


def test_error_mixed_valid_and_invalid_gates_lists_all_bad():
    with pytest.raises(ValueError) as exc_info:
        generate_pulse_program(["NOT1", "FOO_GATE", "HAD", "BAR_GATE"])
    msg = str(exc_info.value)
    assert "FOO_GATE" in msg
    assert "BAR_GATE" in msg


@pytest.mark.parametrize("bad_variant", ["C", "X", "", "123"])
def test_error_bad_variant(bad_variant: str):
    with pytest.raises(ValueError, match="Invalid variant"):
        generate_pulse_program(["NOT1"], variant=bad_variant)


@pytest.mark.parametrize("bad_readout", ["INVALID", "XYZ", ""])
def test_error_bad_readout(bad_readout: str):
    with pytest.raises(ValueError, match="Invalid readout"):
        generate_pulse_program(["NOT1"], readout=bad_readout)


def test_cli_bad_gate_exits_code_1_and_creates_no_file(tmp_path: Path):
    out_file = tmp_path / "should_not_exist.txt"
    cmd = [
        sys.executable,
        str(GENERATOR),
        "NOT1, BADGATE, HAD",
        "-o",
        str(out_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    assert not out_file.exists()
    assert "BADGATE" in res.stderr


def test_cli_bad_gate_does_not_overwrite_existing_file(tmp_path: Path):
    existing = tmp_path / "existing.txt"
    original_content = "SENTINEL CONTENT - DO NOT OVERWRITE\n"
    existing.write_text(original_content, encoding="utf-8")

    cmd = [
        sys.executable,
        str(GENERATOR),
        "NOT1, UNKNOWN_GATE",
        "-o",
        str(existing),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    assert existing.read_text(encoding="utf-8") == original_content


def test_cli_success(tmp_path: Path):
    out_file = tmp_path / "valid_prog.txt"
    cmd = [
        sys.executable,
        str(GENERATOR),
        "NOT1, HAD, CNOT12",
        "--variant",
        "A",
        "--prep",
        "--readout",
        "OBSPOP",
        "-o",
        str(out_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert VARIANT_A_PREP in content
    assert VARIANT_A_READOUT_PULSE["OBSPOP"] in content


# ===========================================================================
# 10. Determinism: identical input gives byte-identical output
# ===========================================================================

def test_determinism():
    run1 = generate_pulse_program(["NOT1", "HAD", "CNOT12"], variant="A", prep=True, readout="OBSPOP")
    run2 = generate_pulse_program(["NOT1", "HAD", "CNOT12"], variant="A", prep=True, readout="OBSPOP")
    assert run1 == run2
    assert run1.encode("utf-8") == run2.encode("utf-8")


# ===========================================================================
# 10b. Provenance header, and stale-output cleanup on failure
# ===========================================================================

def test_provenance_header_identifies_the_command():
    prog = generate_pulse_program(
        ["NOT1", "HAD", "CNOT12"], variant="B", prep=False, readout="INIT"
    )
    assert prog.startswith(PROVENANCE_MARKER)
    assert ";; Gate sequence : NOT1, HAD, CNOT12" in prog
    assert "Variant       : B" in prog
    assert "PPS: no" in prog
    assert "Readout: INIT" in prog


def test_provenance_distinguishes_different_sequences():
    """The whole point: two different commands never leave identical files."""
    a = generate_pulse_program(["NOT1", "HAD"], variant="A")
    b = generate_pulse_program(["HAD", "NOT1"], variant="A")
    assert a.splitlines()[1] != b.splitlines()[1]


def test_strip_provenance_leaves_pulse_code_untouched():
    prog = generate_pulse_program(["NOT1", "HAD"], variant="A", readout="OBSPOP")
    body = strip_provenance(prog)
    assert PROVENANCE_MARKER not in body
    assert body.startswith(VARIANT_A_HEADER)
    # Idempotent, and a no-op on text that has no provenance block.
    assert strip_provenance(body) == body


def test_provenance_does_not_break_determinism():
    a = generate_pulse_program(["NOT1", "HAD"], variant="A", readout="OBSPOP")
    b = generate_pulse_program(["NOT1", "HAD"], variant="A", readout="OBSPOP")
    assert a == b


def test_cli_failure_removes_stale_output_it_wrote(tmp_path: Path):
    """
    A rejected input must not leave a valid-looking program behind from an
    earlier run - that is how the wrong circuit gets loaded on the spectrometer.
    """
    out_file = tmp_path / "circuit.txt"
    ok = subprocess.run(
        [sys.executable, str(GENERATOR), "NOT1, HAD", "-o", str(out_file)],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0 and out_file.exists()

    bad = subprocess.run(
        [sys.executable, str(GENERATOR), "NOT1, BADGATE", "-o", str(out_file)],
        capture_output=True, text=True,
    )
    assert bad.returncode == 1
    assert not out_file.exists(), "stale program left behind after a failed run"
    assert "Removed stale" in bad.stderr


def test_cli_failure_never_deletes_a_file_it_did_not_write(tmp_path: Path):
    """A mistyped -o must not destroy an unrelated file."""
    victim = tmp_path / "thesis.txt"
    content = "IMPORTANT DATA\n"
    victim.write_text(content, encoding="utf-8")

    res = subprocess.run(
        [sys.executable, str(GENERATOR), "NOT1, BADGATE", "-o", str(victim)],
        capture_output=True, text=True,
    )
    assert res.returncode == 1
    assert victim.read_text(encoding="utf-8") == content
    assert "not written by this tool" in res.stderr


def test_cli_failure_with_no_existing_file_is_quiet(tmp_path: Path):
    out_file = tmp_path / "absent.txt"
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "BADGATE", "-o", str(out_file)],
        capture_output=True, text=True,
    )
    assert res.returncode == 1
    assert not out_file.exists()
    assert "Removed stale" not in res.stderr
    assert "not written by this tool" not in res.stderr


# ===========================================================================
# 10c. Batch mode
# ===========================================================================

def _write_batch(tmp_path: Path, body: str) -> Path:
    f = tmp_path / "seqs.txt"
    f.write_text(body, encoding="utf-8")
    return f


def test_batch_compiles_every_sequence(tmp_path: Path):
    batch = _write_batch(tmp_path, "[NOT1]\n[HAD, CNOT12]\nNOT2, PHAD\n")
    outdir = tmp_path / "out"
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "--batch", str(batch), "--outdir", str(outdir)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    names = sorted(p.name for p in outdir.iterdir())
    assert names == ["HAD_CNOT12", "NOT1", "NOT2_PHAD"]
    assert "3/3 sequences compiled" in res.stdout


def test_batch_skips_comments_and_blank_lines(tmp_path: Path):
    batch = _write_batch(
        tmp_path,
        "// a comment\n\n[NOT1]   // trailing comment\n\n   \n[HAD]\n",
    )
    outdir = tmp_path / "out"
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "--batch", str(batch), "--outdir", str(outdir)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    assert sorted(p.name for p in outdir.iterdir()) == ["HAD", "NOT1"]


def test_batch_reports_line_numbers_and_continues(tmp_path: Path):
    batch = _write_batch(tmp_path, "[NOT1]\n[XYZ]\n[HAD]\n")
    outdir = tmp_path / "out"
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "--batch", str(batch), "--outdir", str(outdir)],
        capture_output=True, text=True,
    )
    assert res.returncode == 1
    assert "line 2" in res.stderr
    assert "unknown gate 'XYZ'" in res.stderr
    # the bad line must not stop the good ones
    assert sorted(p.name for p in outdir.iterdir()) == ["HAD", "NOT1"]


def test_batch_deduplicates_filenames(tmp_path: Path):
    batch = _write_batch(tmp_path, "[NOT1]\n[not 1]\n[NOT1]\n")
    outdir = tmp_path / "out"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--batch", str(batch), "--outdir", str(outdir)],
        capture_output=True, text=True,
    )
    assert sorted(p.name for p in outdir.iterdir()) == ["NOT1", "NOT1_2", "NOT1_3"]


def test_batch_output_matches_single_sequence_output(tmp_path: Path):
    """Batch and -o must produce identical programs for the same sequence."""
    batch = _write_batch(tmp_path, "[HAD, CNOT12]\n")
    outdir = tmp_path / "out"
    single = tmp_path / "single"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--batch", str(batch),
         "--outdir", str(outdir), "--variant", "B", "--readout", "INIT"],
        capture_output=True, text=True,
    )
    subprocess.run(
        [sys.executable, str(GENERATOR), "HAD, CNOT12", "-o", str(single),
         "--variant", "B", "--readout", "INIT"],
        capture_output=True, text=True,
    )
    assert (outdir / "HAD_CNOT12").read_text() == single.read_text()


def test_batch_rejects_combination_with_single_mode(tmp_path: Path):
    batch = _write_batch(tmp_path, "[NOT1]\n")
    res = subprocess.run(
        [sys.executable, str(GENERATOR), "NOT1", "--batch", str(batch)],
        capture_output=True, text=True,
    )
    assert res.returncode != 0
    assert "cannot be combined" in res.stderr


# ===========================================================================
# 11. Regression against original_variant_A.txt and original_variant_B.txt
# ===========================================================================

def normalize_whitespace(text: str) -> str:
    """
    Strip trailing spaces from each line and collapse consecutive blank lines.

    Deliberately does NOT touch comment text. Comment bodies are part of the
    verbatim pulse code, so rewriting ';  foo' to '; foo' here would hide a
    gate block that had drifted from the original file.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    result: list[str] = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                result.append("")
                prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result).strip()


def process_original_pulse_program(path: str | Path, active_defines: set[str]) -> str:
    """
    Read an original pulse program template, include only the active #ifdef blocks
    in file order, drop ;#define and #ifdef/#endif lines, and normalize whitespace.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    first_ifdef = min(i for i, l in enumerate(lines) if l.strip().startswith("#ifdef"))
    last_endif = max(i for i, l in enumerate(lines) if l.strip().startswith("#endif"))

    header_lines = [l for l in lines[:first_ifdef] if not l.strip().startswith(";#define")]
    footer_lines = lines[last_endif + 1:]

    body_lines: list[str] = []
    current_macro: str | None = None
    macro_lines: list[str] = []

    for line in lines[first_ifdef : last_endif + 1]:
        s = line.strip()
        if s.startswith("#ifdef"):
            current_macro = s.split()[1]
            macro_lines = []
        elif s.startswith("#endif"):
            if current_macro in active_defines:
                body_lines.extend(macro_lines)
            current_macro = None
            macro_lines = []
        else:
            if current_macro is not None:
                macro_lines.append(line)

    full_text = "".join(header_lines) + "\n" + "".join(body_lines) + "".join(footer_lines)
    return normalize_whitespace(full_text)


@pytest.mark.parametrize("variant", ["A", "B"])
@pytest.mark.parametrize("prep,gates,readout", [
    (False, ["NOT1"], None),
    (False, ["HAD", "CNOT12"], None),
    (True, ["NOT1", "NOT2", "NOT12", "HAD", "PHAD", "CNOT12", "CNOT21", "CNOTB12", "CNOTB21"], "OBSPOP"),
    (True, ["CNOT12", "CNOT21"], "INIT"),
    (False, ["NOT1", "HAD", "PHAD"], "OBSPOP"),
    (True, ["NOT1", "NOT2"], None),
])
def test_regression_against_original(variant: str, prep: bool, gates: list[str], readout: str | None):
    orig_path = Path(__file__).parent / "reference" / f"original_variant_{variant}.txt"
    assert orig_path.exists(), f"Original file {orig_path} must exist"

    active_macros = set(gates)
    if prep:
        active_macros.add("PPS")
    if readout:
        active_macros.add(readout)

    expected_text = process_original_pulse_program(orig_path, active_macros)
    generated_text = normalize_whitespace(
        strip_provenance(
            generate_pulse_program(gates, variant=variant, prep=prep, readout=readout)
        )
    )

    assert generated_text == expected_text
