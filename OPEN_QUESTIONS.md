# Open questions

Questions that need a decision from Dr. Kale or whoever owns the original pulse
programs, before this tool is used on the spectrometer. Each one is evidence-backed:
the relevant lines are cited, and every quirk listed has been confirmed to exist in the
**original** repo programs, not introduced by this tool.

Verification context: all 24 blocks (9 gates + PPS + OBSPOP + INIT, × 2 variants) are
byte-identical to `original_variant_A.txt` / `original_variant_B.txt`; 147 tests pass.

---

## Answered

### PPS placement — answered by Avik Mitra, WhatsApp, 8:57 PM

> "The pps should be kept in the header as that is the starting point of all the
> quantum algorithms. There is a choice between obspop and init and that is also
> provided by the user. So obspop and init is not included in the footer."

**Status: implemented.**

- **PPS** is now emitted by default, immediately after the header, and is suppressed
  only by an explicit `--no-prep` (kept for calibration/debugging). It was previously
  opt-in via `--prep`, which meant the default output had no state preparation at all —
  a circuit running from thermal equilibrium rather than a pseudo-pure state, failing
  silently. `--prep` is still accepted as a no-op for compatibility.
- **OBSPOP / INIT** already matched the guidance and were unchanged: they live in their
  own `READOUT_PULSE` table, separate from `FOOTER`, and the user chooses with
  `--readout`.

### Still open from that thread

Kanishka asked (9:53 PM): *"I've separated the init and obspop as separate calls to the
lib, will they have to be called as a part of the gates?"* — not yet answered.

Our current behaviour is **no**: `PPS`, `OBSPOP`, `INIT` and `EQSUP` are reserved names
and are rejected if they appear inside a gate sequence —

```
Position 2: 'OBSPOP' is not a gate and cannot be used in a sequence
```

This seems consistent with describing the readout as "a choice provided by the user"
(an option, not a gate), but please confirm. See also Q7 below.

---

## Q1 — Variant A `PHAD`: are `pl1`/`pl2` swapped in the original? **(blocking)**

This is the only quirk we found that likely changes the physics.

Variant A maps 1H → `f2`/`pl2` and 13C → `f1`/`pl1`. Every block in variant A follows
that mapping **except** `PHAD` ([original_variant_A.txt:55](original_variant_A.txt#L55)):

```
(p1 pl1 ph3):f2 (p11 pl2 ph3):f1 ; 90y-bar on 1H and 13C
    ^^^      ^^      ^^^      ^^
```

- `p1` (the 1H 90° pulse) is sent on `f2` — correct channel — but at power level
  `pl1`, which is the **13C** power level.
- `p11` (the 13C 90° pulse) is sent on `f1` — correct channel — but at `pl2`, the
  **1H** power level.

Compare the adjacent `HAD` block in the same file, which is consistent:
`(p1 pl2 ph1):f2 (p11 pl1 ph1):f1`. And variant B's `PHAD` is consistent with B's
mapping: `(p1 pl1 ph3):f1 (p11 pl2 ph3):f2`.

Pulse *lengths* are right, so each nucleus gets its own duration — but at the other
nucleus's power. Unless `pl1` and `pl2` happen to be calibrated to nearly the same
amplitude, the flip angles will not be 90°.

**Question:** is this a typo in the original variant A program, or is it deliberate
(e.g. a deliberately miscalibrated / scaled pulse)?

**Why we are asking rather than fixing:** design decision #2 is that blocks are copied
verbatim and never edited, so the generated output provably matches the originals. If
this is a typo, correcting it is a one-line change to
[gate_library.py:82](gate_library.py#L82) — but it would then be a deliberate,
documented divergence from the source, and the regression test for `PHAD` would need
updating to expect it. We did not want to make that call for you.

---

## Q2 — Three comment mislabels: fix or keep verbatim?

Text only, after a `;`, so **no effect on execution**. In each case a 13C pulse is
labelled `(1H)`:

| File | Line | Block | Code | Comment says |
|---|---|---|---|---|
| `original_variant_A.txt` | [95](original_variant_A.txt#L95) | `CNOTB12` | `(p11 pl1 ph2):f1` | `; 90Sx (1H)` — `f1` is 13C in variant A |
| `original_variant_B.txt` | [95](original_variant_B.txt#L95) | `CNOTB12` | `(p11 pl2 ph2):f2` | `; 90Sxb (1H)` — `f2` is 13C in variant B |
| `original_variant_B.txt` | [106](original_variant_B.txt#L106) | `CNOTB21` | `(p11 pl2 ph0):f2` | `; 90Sx (1H)` — `f2` is 13C in variant B |

In Jones & Mosca notation the pulse is on spin **S** (13C) in all three cases, which
the `S` in `90Sx` already indicates — so the `(1H)` looks like a copy-paste slip.

**Question:** correct these comments to `(13C)`, or keep them verbatim? Our default is
**keep verbatim** unless you say otherwise.

---

## Q3 — Are the differing gradient recovery delays intentional?

| | Variant A | Variant B |
|---|---|---|
| PPS, after `p31:gp2` | `100u BLKGRAD` | `1000u BLKGRAD` |
| OBSPOP, after `p31:gp3` | `100u BLKGRAD` | `1m BLKGRAD` |

A 10× difference in gradient recovery time. **Question:** does this reflect two
different probes / gradient amplifiers (in which case both are correct and must be
kept), or is one of them stale? Note `1000u` and `1m` are the same duration written two
ways, which hints these were edited at different times.

---

## Q4 — What is `EQSUP`?

The parser reserves `EQSUP` (so it cannot be used as a gate name) but there is no
`EQSUP` block in either source file —
[gate_parser.py:54](gate_parser.py#L54). **Question:** is there an equilibrium-
suppression block in a version of the repo we were not given? If it is simply not
needed, we will drop it from the reserved list.

---

## Q5 — Should the output mark gate boundaries?

Gate blocks are currently concatenated with nothing between them, so a 20-gate program
is a wall of pulse lines with no indication of where each gate starts. Inserting a
comment separator would make spectrometer-side debugging much easier:

```
; ---- gate 3: CNOT12 ----
```

Because it is a comment, TopSpin ignores it entirely. But it *would* mean the generated
file is no longer byte-identical to the original with the same blocks enabled, which is
the property the regression test currently guarantees.

**Question:** add separators (and relax the regression test to ignore inserted comment
lines), or keep byte-identical output? Our recommendation is **add them** behind an
opt-in flag such as `--annotate`, so the default output stays byte-identical and the
regression guarantee is untouched.

---

## Q7 — Must *one* of OBSPOP / INIT always be present?

The guidance says "there is a **choice between** obspop and init", which reads as *pick
one of the two*. Our tool currently allows **neither** — `--readout` defaults to none,
producing a program with no observation pulse at all:

```
$ python3 generator.py "HAD" -o out        # no readout block emitted
```

If one of the two is always required, this is the same class of silent-wrong-default we
just fixed for PPS, and `--readout` should become mandatory (or default to one of them).

**Question:** is "no readout at all" a legitimate option, or must the user always pick
`OBSPOP` or `INIT`? If it must always be one, which is the sensible default?

---

## Q6 — Spectrometer validation: what is the acceptance test?

We cannot run this ourselves (no TopSpin and no spectrometer access from the
development machine — see "TopSpin validation" below). We need someone with instrument
access to confirm:

1. A generated file **compiles** in TopSpin with no errors (`pulsprog` / `ased`).
2. A known circuit gives the expected spectrum — our suggestion for the smallest
   meaningful check is `--prep --readout OBSPOP` with sequence `NOT1`, compared against
   the original program with `PPS`, `NOT1` and `OBSPOP` defined. These should be
   indistinguishable, since the generated file is byte-identical modulo blank lines.
3. A circuit the **original cannot express** behaves sensibly — e.g. `NOT1, NOT1`
   (two 180° pulses on 1H, expected to return to the initial state), which is the
   actual new capability this tool adds.

**Question:** who can run these, and is there a parameter set we should ship or
reference in the README?

---

## TopSpin validation — status

**Not done, and not doable from this machine.** TopSpin is not installed
(checked `/opt`, `/Applications`, Spotlight, and `PATH`), and there is no spectrometer
access, so no claim is made here about whether the output compiles or runs.

What we did instead, as a pre-flight substitute, is a static structural check of **72**
generated programs (both variants × `--prep` on/off × 3 readout settings × 6 sequences
including a 27-gate one). All 72 pass all seven checks:

| Check | Result |
|---|---|
| Balanced parentheses on every pulse line | pass |
| No leftover `#ifdef` / `#endif` / `#define` | pass |
| Every `phN` referenced is defined in the phase table | pass |
| Every jump target (`go=2`, `mc ... to 2`) has a matching label | pass |
| `UNBLKGRAD` / `BLKGRAD` balanced | pass |
| Required skeleton present (`1 ze`, `exit`, `go=2 ph31`, `d2` definition, `Avance.incl`) | pass |
| `d2` defined before first use | pass |

This is a **static lint, not a TopSpin compile.** It cannot catch anything that depends
on the parameter set, probe tuning, hardware limits (e.g. duty cycle on a long
sequence), or pulse calibration. Q1 in particular is exactly the kind of error no
static check can detect.

Parameters the program references but does not define — these must be set in the
dataset before running (note: set **`cnst1`**, the J coupling in Hz; `d2` is computed
by the program as `1/(4*cnst1)`):

```
p1  p2  p3  p4  p11  p14  p31        pulse lengths
pl1  pl2                             power levels
d1  d2  cnst1                        relaxation delay, 1/4J delay, J coupling
gp2  gp3                             gradient programs
```
