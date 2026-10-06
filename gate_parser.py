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

# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------

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
        # Store the error list.  When called as GateParseError("msg") the
        # single positional string also becomes errors[0] for consistency.
        if errors is not None:
            self.errors: list[str] = errors
        elif args:
            self.errors = [str(args[0])]
        else:
            self.errors = []
        super().__init__("\n".join(self.errors))


# ---------------------------------------------------------------------------
# Constants derived from the library (never hardcoded)
# ---------------------------------------------------------------------------

# The set of valid, user-selectable gate names.
_VALID_GATES: frozenset[str] = frozenset(VARIANT_A_GATE_LIBRARY.keys())

# Names that exist in the library namespace but are NOT sequence gates.
_RESERVED: frozenset[str] = frozenset({"PPS", "OBSPOP", "INIT", "EQSUP"})

# Regex a token must satisfy: letters optionally followed by (optional
# whitespace then) digits.  Digits are not required (HAD, PHAD are valid).
# Nothing else – no underscores, no punctuation – is allowed.
# Applied with .fullmatch(), so the whole token must match; explicit ^/$
# anchors would be redundant.
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:\s*\d+)?")


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Rule 1 – type and emptiness check
    # ------------------------------------------------------------------
    # If text is not a str, or is empty or whitespace-only, raise
    # immediately with a fixed message.  This is the only early-exit
    # before full collection of errors.
    _EMPTY_MSG = "Empty input: provide at least one gate, e.g. 'NOT1, HAD'"

    if not isinstance(text, str) or not text.strip():
        raise GateParseError(_EMPTY_MSG)

    # ------------------------------------------------------------------
    # Rule 2 – strip, optional bracket unwrapping, strip again
    # ------------------------------------------------------------------
    # Strip outer whitespace.
    text = text.strip()

    # If the whole string is wrapped in one matching {} or [], remove that
    # single pair and strip again.
    if (text.startswith("{") and text.endswith("}")) or \
       (text.startswith("[") and text.endswith("]")):
        text = text[1:-1].strip()

    # After unwrapping, the content might be empty.
    if not text:
        raise GateParseError(_EMPTY_MSG)

    # ------------------------------------------------------------------
    # Rule 3 – split on commas ONLY
    # ------------------------------------------------------------------
    # str.split(",") splits only on commas, preserving all other
    # whitespace inside each token.
    raw_tokens: list[str] = text.split(",")

    # ------------------------------------------------------------------
    # Rules 4 & 5 – validate each token, collect errors
    # ------------------------------------------------------------------
    errors: list[str] = []
    normalised: list[str] = []

    for position, raw in enumerate(raw_tokens, start=1):
        # Rule 4a – strip leading/trailing whitespace from this token.
        token = raw.strip()

        # Rule 4b – empty token (extra comma).
        if token == "":
            errors.append(
                f"Position {position}: empty entry (extra comma?)"
            )
            continue

        # Rule 4c – must fully match ^[A-Za-z]+(?:\s*\d+)?$.
        if not _TOKEN_RE.fullmatch(token):
            # Build hint for the error message.
            parts = token.split()
            if len(parts) > 1 and all(
                re.fullmatch(r"[A-Za-z]+(?:\s*\d+)?", p) for p in parts
            ):
                # Multiple whitespace-separated parts that each look like a
                # gate name or partial name => likely missing commas.
                hint = " (missing comma between gates?)"
            elif re.fullmatch(r"\d+", token):
                # Token is only digits.
                hint = " (use gate names, not numbers)"
            else:
                hint = ""

            errors.append(
                f"Position {position}: '{token}' is not a valid gate format{hint}"
            )
            continue

        # Normalise: remove any internal space, uppercase everything.
        # e.g. "cnot 12" -> "CNOT12", "NOT 1" -> "NOT1"
        name = re.sub(r"\s+", "", token).upper()

        # Rule 5 – validate the normalised name.
        if name in _RESERVED:
            errors.append(
                f"Position {position}: '{name}' is not a gate and cannot be "
                f"used in a sequence"
            )
            continue

        if name not in _VALID_GATES:
            # Look for close matches to suggest a correction.
            close = difflib.get_close_matches(
                name, _VALID_GATES, n=1, cutoff=0.5
            )
            suggestion = f" - did you mean '{close[0]}'?" if close else ""
            errors.append(
                f"Position {position}: unknown gate '{name}'{suggestion}"
            )
            continue

        # Token is valid; add normalised name to the result list.
        normalised.append(name)

    # ------------------------------------------------------------------
    # Final decision – raise if any errors, otherwise return
    # ------------------------------------------------------------------
    # Never return a partial list.  If there are any errors, raise a
    # single GateParseError that contains every problem.
    if errors:
        raise GateParseError(*errors[:1], errors=errors)

    return normalised
