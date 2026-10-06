from __future__ import annotations
"""
gate_parser.py
---------
Parses a comma-separated list of NMR gate names into a validated,
normalised list of strings.

Public API
----------
  GateParseError   – raised when any validation rule is violated
  parse_gate_sequence(text) -> list[str]
"""

import re
import difflib

from gate_library import VARIANT_A_GATE_LIBRARY

class GateParseError(ValueError):
    """
    Raised when parse_gate_sequence() finds one or more problems.

    Attributes
    ----------
    errors : list[str]
        Every individual problem, one string per bad token.
    The exception message is all problems joined with newlines.
    """

    def __init__(self, *args, errors: list[str] | None = None):
        # GateParseError("msg") also lands in errors[0], for consistency.
        if errors is not None:
            self.errors: list[str] = errors
        elif args:
            self.errors = [str(args[0])]
        else:
            self.errors = []
        super().__init__("\n".join(self.errors))


# Derived from the library, never hardcoded: adding a gate there is enough.
_VALID_GATES: frozenset[str] = frozenset(VARIANT_A_GATE_LIBRARY.keys())

# Names that exist in the library namespace but are NOT sequence gates.
_RESERVED: frozenset[str] = frozenset({"PPS", "OBSPOP", "INIT", "EQSUP"})

# Letters, then optional whitespace and digits. Digits are optional because
# HAD and PHAD have none. Used with .fullmatch(), so ^/$ would be redundant.
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:\s*\d+)?")


def parse_gate_sequence(text: str) -> list[str]:
    """
    Parse and validate a comma-separated gate sequence.

    Parameters
    ----------
    text : str
        Raw user input, e.g. ``"NOT1, HAD, cnot 12"``.

    Returns
    -------
    list[str]
        Normalised gate names in input order (uppercase, no spaces,
        duplicates preserved).

    Raises
    ------
    GateParseError
        If *any* rule is violated.  All violations are collected before
        raising; ``exc.errors`` holds one string per problem.
    """

    # The only early exit; every other problem is collected, not raised.
    _EMPTY_MSG = "Empty input: provide at least one gate, e.g. 'NOT1, HAD'"

    if not isinstance(text, str) or not text.strip():
        raise GateParseError(_EMPTY_MSG)

    text = text.strip()

    # Unwrap one matching outer {} or [] so "{NOT1, HAD}" is accepted.
    if (text.startswith("{") and text.endswith("}")) or \
       (text.startswith("[") and text.endswith("]")):
        text = text[1:-1].strip()

    if not text:
        raise GateParseError(_EMPTY_MSG)

    # Commas only, never whitespace: splitting on spaces would make
    # "NOT 1 2" ambiguous between "NOT1, 2" and "NOT12".
    raw_tokens: list[str] = text.split(",")

    errors: list[str] = []
    normalised: list[str] = []

    for position, raw in enumerate(raw_tokens, start=1):
        token = raw.strip()

        if token == "":
            errors.append(
                f"Position {position}: empty entry (extra comma?)"
            )
            continue

        if not _TOKEN_RE.fullmatch(token):
            parts = token.split()
            if len(parts) > 1 and all(
                re.fullmatch(r"[A-Za-z]+(?:\s*\d+)?", p) for p in parts
            ):
                # Every part looks like a gate name on its own.
                hint = " (missing comma between gates?)"
            elif re.fullmatch(r"\d+", token):
                hint = " (use gate names, not numbers)"
            else:
                hint = ""

            errors.append(
                f"Position {position}: '{token}' is not a valid gate format{hint}"
            )
            continue

        # "cnot 12" -> "CNOT12", "NOT 1" -> "NOT1"
        name = re.sub(r"\s+", "", token).upper()

        if name in _RESERVED:
            errors.append(
                f"Position {position}: '{name}' is not a gate and cannot be "
                f"used in a sequence"
            )
            continue

        if name not in _VALID_GATES:
            close = difflib.get_close_matches(
                name, _VALID_GATES, n=1, cutoff=0.5
            )
            suggestion = f" - did you mean '{close[0]}'?" if close else ""
            errors.append(
                f"Position {position}: unknown gate '{name}'{suggestion}"
            )
            continue

        normalised.append(name)

    # Never return a partial list: one error invalidates the whole sequence.
    if errors:
        raise GateParseError(*errors[:1], errors=errors)

    return normalised
