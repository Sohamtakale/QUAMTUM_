from __future__ import annotations
"""
gate_library.py
---------------
Loads the Bruker pulse-program fragments from lib/ into memory.

The pulse code itself lives in plain text files under lib/, not in this
module, so it can be corrected by someone who does not write Python:

    lib/variant_A/header.txt      fixed preamble
    lib/variant_A/prep.txt        PPS state preparation
    lib/variant_A/footer.txt      readout loop, exit, phase table
    lib/variant_A/gates/*.txt     one file per gate
    lib/variant_A/readout/*.txt   OBSPOP, INIT
    lib/variant_B/...             same, other channel mapping

Each file holds exactly the lines that sat between #ifdef <NAME> and #endif
in the original program - no wrappers, nothing reformatted. Editing a file
changes the generated output directly, so keep them verbatim unless you
intend to diverge from the source programs.

Channel mapping:
    VARIANT_A   1H on f2/pl2, 13C on f1/pl1
    VARIANT_B   1H on f1/pl1, 13C on f2/pl2

Known quirk: variant A's PHAD applies pl1 on :f2 and pl2 on :f1, the
opposite of every other block in that variant. It is reproduced from the
original file rather than corrected. See lib/README.md.
"""

from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "lib"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_folder(folder: Path) -> dict[str, str]:
    """Map FILENAME (uppercased, no extension) -> file contents."""
    return {f.stem.upper(): _read(f) for f in sorted(folder.glob("*.txt"))}


def _load_variant(name: str) -> dict[str, object]:
    base = LIB / f"variant_{name}"
    if not base.is_dir():
        raise FileNotFoundError(f"Missing pulse-code directory: {base}")
    return {
        "header": _read(base / "header.txt"),
        "prep": _read(base / "prep.txt"),
        "footer": _read(base / "footer.txt"),
        "gates": _load_folder(base / "gates"),
        "readout": _load_folder(base / "readout"),
    }


_A = _load_variant("A")
_B = _load_variant("B")

VARIANT_A_HEADER: str = _A["header"]
VARIANT_A_PREP: str = _A["prep"]
VARIANT_A_FOOTER: str = _A["footer"]
VARIANT_A_GATE_LIBRARY: dict[str, str] = _A["gates"]
VARIANT_A_READOUT_PULSE: dict[str, str] = _A["readout"]

VARIANT_B_HEADER: str = _B["header"]
VARIANT_B_PREP: str = _B["prep"]
VARIANT_B_FOOTER: str = _B["footer"]
VARIANT_B_GATE_LIBRARY: dict[str, str] = _B["gates"]
VARIANT_B_READOUT_PULSE: dict[str, str] = _B["readout"]

# Bruker phase-label to integer encoding: 0 = x, 1 = y, 2 = -x, 3 = -y
PHASE_TABLE: dict[str, int] = {
    "ph0": 0,
    "ph1": 1,
    "ph2": 2,
    "ph3": 3,
    "ph31": 0,
}
