from __future__ import annotations
"""
test_parser.py
--------------
pytest suite for parse_gate_sequence() in gate_parser.py.
"""

import pytest

from gate_library import VARIANT_A_GATE_LIBRARY, VARIANT_B_GATE_LIBRARY
from gate_parser import GateParseError, parse_gate_sequence

# All 9 valid gate names, in library order.
ALL_GATES = list(VARIANT_A_GATE_LIBRARY.keys())

# ============================================================================
# Library integrity (no parser logic here, just data checks)
# ============================================================================

def test_library_keys_match_between_variants():
    """Both variants expose exactly the same gate names."""
    assert VARIANT_A_GATE_LIBRARY.keys() == VARIANT_B_GATE_LIBRARY.keys()


def test_library_has_exactly_nine_gates():
    expected = {"NOT1", "NOT2", "NOT12", "HAD", "PHAD",
                "CNOT12", "CNOT21", "CNOTB12", "CNOTB21"}
    assert set(VARIANT_A_GATE_LIBRARY.keys()) == expected


def test_library_does_not_contain_reserved_names():
    for name in ("PPS", "OBSPOP", "INIT"):
        assert name not in VARIANT_A_GATE_LIBRARY
        assert name not in VARIANT_B_GATE_LIBRARY


# ============================================================================
# Table-driven happy-path tests (one row per spec example)
# ============================================================================

@pytest.mark.parametrize("text, expected", [
    ("NOT1",                        ["NOT1"]),
    ("NOT1, HAD, CNOT12",           ["NOT1", "HAD", "CNOT12"]),
    ("{NOT1, HAD}",                 ["NOT1", "HAD"]),
    ("[NOT1, HAD]",                 ["NOT1", "HAD"]),
    (" not 1 ,\n cnot 12 ",        ["NOT1", "CNOT12"]),
    ("NOT1, NOT2",                  ["NOT1", "NOT2"]),    # must NOT become NOT12
    ("NOT1, NOT1, HAD",             ["NOT1", "NOT1", "HAD"]),
])
def test_happy_path_spec_examples(text, expected):
    assert parse_gate_sequence(text) == expected


# ============================================================================
# Each of the 9 gates parses to itself when given alone
# ============================================================================

@pytest.mark.parametrize("gate", ALL_GATES)
def test_single_gate_roundtrip(gate):
    assert parse_gate_sequence(gate) == [gate]


# ============================================================================
# All 9 gates in one sequence
# ============================================================================

def test_all_nine_gates_in_order():
    text = ", ".join(ALL_GATES)
    assert parse_gate_sequence(text) == ALL_GATES


def test_all_nine_gates_reversed():
    rev = list(reversed(ALL_GATES))
    text = ", ".join(rev)
    assert parse_gate_sequence(text) == rev


def test_all_nine_gates_sorted_order():
    srt = sorted(ALL_GATES)
    text = ", ".join(srt)
    assert parse_gate_sequence(text) == srt


# ============================================================================
# Duplicates are preserved
# ============================================================================

def test_duplicates_preserved():
    result = parse_gate_sequence("NOT1, NOT1, HAD, NOT1")
    assert result == ["NOT1", "NOT1", "HAD", "NOT1"]


# ============================================================================
# Long sequence keeps length and order
# ============================================================================

def test_long_sequence_length_and_order():
    gates_200 = (ALL_GATES * 23)[:200]   # 200 entries cycling through the 9
    text = ", ".join(gates_200)
    result = parse_gate_sequence(text)
    assert result == gates_200
    assert len(result) == 200


# ============================================================================
# Whitespace normalisation
# ============================================================================

@pytest.mark.parametrize("text, expected", [
    ("NOT1\t,\tHAD",            ["NOT1", "HAD"]),        # tabs around comma
    ("NOT1\n,\nHAD",            ["NOT1", "HAD"]),        # newlines around comma
    ("\t NOT1 \t",              ["NOT1"]),                # tabs around token
    ("  NOT1  ,  HAD  ",       ["NOT1", "HAD"]),         # spaces around tokens
])
def test_whitespace_around_tokens(text, expected):
    assert parse_gate_sequence(text) == expected


# ============================================================================
# Case normalisation
# ============================================================================

@pytest.mark.parametrize("text, expected", [
    ("not1",         ["NOT1"]),
    ("Not1",         ["NOT1"]),
    ("had",          ["HAD"]),
    ("cNot12",       ["CNOT12"]),
    ("cnot 12",      ["CNOT12"]),   # internal space + lowercase
    ("NOT 1",        ["NOT1"]),     # internal space, uppercase letters
    ("Cnot 21",      ["CNOT21"]),
])
def test_case_and_internal_space_normalisation(text, expected):
    assert parse_gate_sequence(text) == expected


# ============================================================================
# Empty / whitespace-only input  (spec: must raise)
# ============================================================================

@pytest.mark.parametrize("text", [
    "",
    " ",
    "\t",
    "\n",
    "   \t\n  ",
])
def test_empty_input_raises(text):
    with pytest.raises(GateParseError):
        parse_gate_sequence(text)


def test_empty_input_not_str_raises():
    for bad in (None, 42, [], {}):
        with pytest.raises(GateParseError):
            parse_gate_sequence(bad)


def test_empty_after_bracket_unwrap_raises():
    with pytest.raises(GateParseError):
        parse_gate_sequence("{}")
    with pytest.raises(GateParseError):
        parse_gate_sequence("[]")
    with pytest.raises(GateParseError):
        parse_gate_sequence("{   }")


# ============================================================================
# Empty-entry errors  (trailing / double commas)
# ============================================================================

@pytest.mark.parametrize("text", [
    "NOT1,",
    ",NOT1",
    "NOT1,,HAD",
    "NOT1,,,HAD",
])
def test_empty_entry_raises(text):
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence(text)
    assert any("empty entry" in e for e in exc_info.value.errors)


# ============================================================================
# Invalid format errors
# ============================================================================

def test_invalid_format_not1_space_2():
    """'NOT 1 2' has trailing digits after a valid-looking token."""
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("NOT 1 2")
    assert any("not a valid gate format" in e for e in exc_info.value.errors)


def test_missing_comma_hint():
    """'NOT1 HAD CNOT12' – all gates but space-separated, not comma-separated."""
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("NOT1 HAD CNOT12")
    assert any("missing comma" in e for e in exc_info.value.errors)


def test_only_digits_hint():
    """'1, 3, 5' – tokens are only digits."""
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("1, 3, 5")
    errs = exc_info.value.errors
    assert len(errs) == 3
    assert all("use gate names" in e for e in errs)


# ============================================================================
# Unknown gate with close-match suggestion
# ============================================================================

def test_unknown_gate_cx12_suggests_cnot12():
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("CX12")
    assert any("CNOT12" in e for e in exc_info.value.errors)


def test_close_match_suggestion_present():
    """CNOT13 is very close to CNOT12 – suggestion should appear."""
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("CNOT13")
    errs = " ".join(exc_info.value.errors)
    assert "did you mean" in errs


# ============================================================================
# Reserved names (PPS, OBSPOP, INIT, EQSUP)
# ============================================================================

@pytest.mark.parametrize("name", ["PPS", "OBSPOP", "INIT", "EQSUP"])
def test_reserved_names_are_rejected(name):
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence(name)
    assert any("not a gate" in e for e in exc_info.value.errors)


# ============================================================================
# Multiple errors collected – never stop at first
# ============================================================================

def test_multiple_errors_collected():
    """'NOT1, XYZ, HAD, FOO' – XYZ and FOO are both bad; HAD is fine."""
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("NOT1, XYZ, HAD, FOO")
    errs = exc_info.value.errors
    assert len(errs) == 2       # exactly XYZ and FOO
    combined = " ".join(errs)
    assert "XYZ" in combined
    assert "FOO" in combined


def test_mixed_sequence_raises_and_does_not_return():
    """A sequence with one valid and one invalid gate must raise, not return."""
    with pytest.raises(GateParseError):
        result = parse_gate_sequence("NOT1, BADGATE99")
    # If we reach here without an exception the test already failed above.


def test_errors_list_has_correct_count():
    """Three bad tokens => errors list has exactly 3 entries."""
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("XYZ, ABC, DEF")
    assert len(exc_info.value.errors) == 3


# ============================================================================
# GateParseError structure
# ============================================================================

def test_gate_parse_error_errors_is_list():
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("BAD1")
    assert isinstance(exc_info.value.errors, list)


def test_gate_parse_error_message_joins_errors():
    with pytest.raises(GateParseError) as exc_info:
        parse_gate_sequence("XYZ, ABC")
    exc = exc_info.value
    assert str(exc) == "\n".join(exc.errors)


# ============================================================================
# Determinism – same input, same output
# ============================================================================

def test_same_input_gives_identical_output():
    text = "NOT1, HAD, CNOT12, NOT2"
    assert parse_gate_sequence(text) == parse_gate_sequence(text)


def test_same_error_input_gives_identical_errors():
    text = "XYZ, ABC"
    with pytest.raises(GateParseError) as e1:
        parse_gate_sequence(text)
    with pytest.raises(GateParseError) as e2:
        parse_gate_sequence(text)
    assert e1.value.errors == e2.value.errors


# ============================================================================
# Bracket unwrapping edge cases
# ============================================================================

@pytest.mark.parametrize("text, expected", [
    ("{NOT1}",              ["NOT1"]),
    ("[NOT1]",              ["NOT1"]),
    ("{NOT1, HAD}",         ["NOT1", "HAD"]),
    ("[NOT1, HAD]",         ["NOT1", "HAD"]),
    ("{ NOT1 , HAD }",     ["NOT1", "HAD"]),
])
def test_bracket_unwrapping(text, expected):
    assert parse_gate_sequence(text) == expected


def test_nested_brackets_not_double_unwrapped():
    """Only one layer of brackets is removed. {{NOT1}} should fail."""
    with pytest.raises(GateParseError):
        parse_gate_sequence("{{NOT1}}")


def test_mismatched_brackets_not_stripped():
    """'{NOT1]' – mismatched, so not stripped; 'NOT1]' then fails format."""
    with pytest.raises(GateParseError):
        parse_gate_sequence("{NOT1]")
