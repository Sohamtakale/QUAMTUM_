# Pulse code library

Every file here is raw Bruker pulse code, loaded verbatim by `src/gate_library.py`.
**You do not need to know Python to correct a pulse** — edit the `.txt` file and the
next generated program picks it up.

```
variant_A/            1H on f2/pl2, 13C on f1/pl1
variant_B/            1H on f1/pl1, 13C on f2/pl2
  header.txt          includes, acqt0, d2 definition, "1 ze", "2 30m", d1
  prep.txt            PPS state preparation (PRA 85 022109)
  footer.txt          go=2 ph31, mc loop, exit, phase table, parameter notes
  gates/NAME.txt      one file per gate; the filename is the gate name
  readout/NAME.txt    OBSPOP and INIT
```

## Rules

**Each file holds exactly the lines that sat between `#ifdef <NAME>` and `#endif` in
the original program.** No `#ifdef`/`#endif` wrappers, nothing reformatted, nothing
renumbered. The generator concatenates these files in the order the user asks for.

**Keep the trailing newline.** Blocks are pasted back to back, so a file without one
would run its last pulse into the next block's first.

**Do not mix variants.** A program must take every block from one directory. `pl1`
and `pl2` mean opposite nuclei in `variant_A` and `variant_B`, so a mixed program
addresses the same qubit on two different channels — it compiles cleanly and runs the
wrong experiment.

**Adding a gate** means dropping `NEWGATE.txt` into *both* `variant_A/gates/` and
`variant_B/gates/`. Nothing else needs changing: the parser, the generator and the
test suite all derive their gate list from these directories.

## Verifying a change

```bash
pytest -q                 # 160 tests, incl. regression against the originals
python3 src/preflight.py  # structural checks on 72 generated programs
```

The regression tests compare generated output against
`tests/reference/original_variant_*.txt`. They will fail if you edit a block here, which
is intentional — it forces a deliberate decision to diverge from the source programs.
If the divergence is wanted, update the reference file in the same commit and say why.

## Known quirk

`variant_A/gates/PHAD.txt` applies `pl1` on `:f2` and `pl2` on `:f1`, the opposite of
every other block in that variant, which would give wrong flip angles. This is present
in the original program and is reproduced rather than corrected. `variant_B`'s `PHAD`
is consistent. Do not "fix" this without confirming the intent with Dr. Kale first.
