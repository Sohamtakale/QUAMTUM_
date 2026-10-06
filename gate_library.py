from __future__ import annotations
"""
gate_library.py
---------------
Static library of Bruker NMR pulse-program fragments.

Two hardware variants are stored:
  VARIANT_A  -  1H on f2/pl2, 13C on f1/pl1
  VARIANT_B  -  1H on f1/pl1, 13C on f2/pl2

Per variant:
  HEADER          - fixed preamble (includes, parameters, loop start)
  PREP            - PPS state-preparation block (single block, not a gate)
  GATE_LIBRARY    - dict mapping gate-name -> verbatim pulse-code block
  READOUT_PULSE   - dict with OBSPOP and INIT blocks
  FOOTER          - fixed tail (readout, exit, phase tables, comments)

Nothing is parsed or generated here - this file is pure data.
"""

# ---------------------------------------------------------------------------
# VARIANT A
#   Channel mapping:  1H  -> f2, pl2
#                     13C -> f1, pl1
# ---------------------------------------------------------------------------

VARIANT_A_HEADER: str = """\
#include <Avance.incl>
#include <Grad.incl>

"acqt0=-p1*2/3.1416"
"d2=1/(4*cnst1)" ; 1/4J free evolution


1 ze
2 30m
  d1
"""

# PPS state-preparation block (Variant A).
# Separated from GATE_LIBRARY because it is always the first block and
# is not a quantum gate.
VARIANT_A_PREP: str = """\
;;----------PPS--Based on PRA 85 022109 (2012)-------------------------
(p2 pl2 ph0):f2  ;15 deg x-pulse on 1H
d2
d2
(p3 pl2 ph3):f2  ;75 deg ybar-pulse on 1H

100u UNBLKGRAD ; gradient
p31:gp2
100u BLKGRAD
"""

# Gate library (Variant A).
# Keys  : gate names as they appear in the #define/#ifdef flags.
# Values: verbatim lines between #ifdef <GATE> and #endif.
#         #ifdef / #endif wrappers are NOT included.
VARIANT_A_GATE_LIBRARY: dict[str, str] = {

    "NOT1": """\
(p4 pl2 ph3):f2 ;180 deg y-pulse on 1h
""",

    "NOT2": """\
(p14 pl1 ph1):f1 ;180 deg y-pulse on 13C
""",

    "NOT12": """\
(p4 pl2 ph1):f2 (p14 pl1 ph1):f1 ;180 deg y-pulse on 1h and 13C
""",

    "HAD": """\
(p1 pl2 ph1):f2 (p11 pl1 ph1):f1 ; 90y on 1H and 13C
(p4 pl2 ph0):f2 (p14 pl1 ph0):f1 ; 180x on 1H and 13C
""",

    # NOTE (interpretation): pl1 appears on :f2 (1H channel in this variant)
    # and pl2 on :f1 (13C channel). This looks like pl1/pl2 may be swapped
    # relative to the HAD and CNOT blocks; copied verbatim from the source.
    "PHAD": """\
(p1 pl1 ph3):f2 (p11 pl2 ph3):f1 ; 90y-bar on 1H and 13C
""",

    "CNOT12": """\
;cnot12 control bit 1
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p11 pl1 ph1):f1 ; 90Sy (13C)
d2
d2
(p1 pl2 ph1):f2 ; 90Iy (1H)
(p1 pl2 ph0):f2 ; 90Ix (1H)
(p1 pl2 ph3):f2 (p11 pl1 ph3):f1 ;90Yb on spin I,S (1H, 13C)
(p11 pl1 ph0):f1 ; 90Sx (13C)
""",

    "CNOT21": """\
;cnot21 with control-bit state 1
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p1 pl2 ph1):f2 ; 90Iy (1H)
d2
d2
(p11 pl1 ph1):f1 ; 90Sy (13C)
(p11 pl1 ph0):f1 ;90Sx (13C)
(p1 pl2 ph3):f2 (p11 pl1 ph3):f1 ;90Iyb (1H) 90Syb (13C)
(p1 pl2 ph0):f2 ; 90Ix (1H)
""",

    "CNOTB12": """\
;cnot12 control bit 0
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p11 pl1 ph1):f1 ; 90Sy (13C)
d2
d2
(p1 pl2 ph1):f2 ; 90Iy (1H)
(p1 pl2 ph0):f2 ; 90Ix (1H)
(p1 pl2 ph3):f2 (p11 pl1 ph3):f1 ;90Yb on spin I,S (1H, 13C)
(p11 pl1 ph2):f1 ; 90Sx (1H)
""",

    "CNOTB21": """\
;cnot21 with control-bit state 0
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p1 pl2 ph1):f2 ; 90Iy (1H)
d2
d2
(p11 pl1 ph1):f1 ; 90Sy (13C)
(p11 pl1 ph0):f1 ; 90Sx (13C)
(p1 pl2 ph3):f2 (p11 pl1 ph3):f1 ;90Yb on spin I,S (1H, 13C)
(p1 pl2 ph2):f2 ; 90Ix (1H)
""",
}

# Readout-pulse blocks (Variant A).
# These follow the gate blocks and precede the readout loop.
VARIANT_A_READOUT_PULSE: dict[str, str] = {

    "OBSPOP": """\
  100u UNBLKGRAD ; gradient
  p31:gp3
  100u BLKGRAD
(p11 pl1 ph1):f1 ; observation 90 pulse
""",

    "INIT": """\
(p11 pl1 ph1):f1 ; observation 90 pulse
""",
}

VARIANT_A_FOOTER: str = """\

;; Read out
  go=2 ph31
  30m mc #0 to 2 F0(zd)
exit


ph0=0
ph1=1
ph2 =2
ph3 =3
ph31=0



;pl1 : f1 channel - power level for pulse (default)
;p1 : f1 channel -  high power pulse
;d1 : relaxation delay; 1-5 * T1
;ns: 1 * n, total number of scans: NS * TD0



;$Id:$
"""


# ===========================================================================
# VARIANT B
#   Channel mapping:  1H  -> f1, pl1
#                     13C -> f2, pl2
# ===========================================================================

VARIANT_B_HEADER: str = """\
#include <Avance.incl>
#include <Grad.incl>

"acqt0=-p1*2/3.1416"
"d2=1/(4*cnst1)" ; 1/4J free evolution


1 ze
2 30m
  d1
"""

# PPS state-preparation block (Variant B).
# Note: BLKGRAD delay is 1000u here vs 100u in Variant A.
VARIANT_B_PREP: str = """\
;;----------PPS--Based on PRA 85 022109 (2012)-------------------------
(p2 pl1 ph0):f1  ;15 deg x-pulse on 1H
d2
d2
(p3 pl1 ph3):f1  ;75 deg ybar-pulse on 1H

100u UNBLKGRAD ; gradient
p31:gp2
1000u BLKGRAD
"""

# Gate library (Variant B).
VARIANT_B_GATE_LIBRARY: dict[str, str] = {

    "NOT1": """\
(p4 pl1 ph3):f1 ;180 deg y-pulse on 1h
""",

    "NOT2": """\
(p14 pl2 ph1):f2 ;180 deg y-pulse on 13C
""",

    "NOT12": """\
(p4 pl1 ph1):f1 (p14 pl2 ph1):f2 ;180 deg y-pulse on 1h and 13C
""",

    "HAD": """\
(p1 pl1 ph1):f1 (p11 pl2 ph1):f2 ; 90y on 1H and 13C
(p4 pl1 ph0):f1 (p14 pl2 ph0):f2 ; 180x on 1H and 13C
""",

    "PHAD": """\
(p1 pl1 ph3):f1 (p11 pl2 ph3):f2 ; 90y-bar on 1H and 13C
""",

    "CNOT12": """\
;cnot12 with control-bit state 1
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p11 pl2 ph1):f2 ; 90Sy (13C)
d2
d2
(p1 pl1 ph1):f1 ; 90Iy (1H)
(p1 pl1 ph0):f1 ; 90Ix (1H)
(p1 pl1 ph3):f1 (p11 pl2 ph3):f2 ;90Yb on spin I,S (1H, 13C)
(p11 pl2 ph0):f2 ; 90Sx (13C)
""",

    "CNOT21": """\
;cnot21 with control-bit state 1
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p1 pl1 ph1):f1 ; 90Iy (1H)
d2
d2
(p11 pl2 ph1):f2 ; 90Sy (13C)
(p11 pl2 ph0):f2 ;90Sx (13C)
(p1 pl1 ph3):f1 (p11 pl2 ph3):f2 ;90Iyb (1H) 90Syb (13C)
(p1 pl1 ph0):f1 ; 90Ix (1H)
""",

    "CNOTB12": """\
;cnot12 with control-bit state 0
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p11 pl2 ph1):f2 ; 90Sy (13C)
d2
d2
(p1 pl1 ph1):f1 ; 90Iy (1H)
(p1 pl1 ph0):f1 ; 90Ix (1H)
(p1 pl1 ph3):f1 (p11 pl2 ph3):f2 ;90Yb on spin I,S (1H, 13C)
(p11 pl2 ph2):f2 ; 90Sxb (1H)
""",

    "CNOTB21": """\
;cnot21 with control-bit state 0
; quant-ph/9801027 - Jones and Mosca (eqn 14)
; H is spin I and C is spin S
(p1 pl1 ph1):f1 ; 90Iy (1H)
d2
d2
(p11 pl2 ph1):f2 ; 90Sy (13C)
(p11 pl2 ph0):f2 ; 90Sx (1H)
(p1 pl1 ph3):f1 (p11 pl2 ph3):f2 ;90Yb on spin I,S (1H, 13C)
(p1 pl1 ph2):f1 ; 90Ixb (1H)
""",
}

# Readout-pulse blocks (Variant B).
# OBSPOP uses p31:gp3 and 1m BLKGRAD (vs 100u in Variant A).
VARIANT_B_READOUT_PULSE: dict[str, str] = {

    "OBSPOP": """\
  100u UNBLKGRAD ; gradient
   p31:gp3
  1m BLKGRAD
(p1 pl1 ph1):f1 ; observation 90 pulse
""",

    "INIT": """\
(p1 pl1 ph1):f1 ; observation 90 pulse
""",
}

VARIANT_B_FOOTER: str = """\

;; Read out
  go=2 ph31
  30m mc #0 to 2 F0(zd)
exit


ph0=0
ph1=1
ph2 =2
ph3 =3
ph31=0


;pl1 : f1 channel - power level for pulse (default)
;p1 : f1 channel -  high power pulse
;d1 : relaxation delay; 1-5 * T1
;ns: 1 * n, total number of scans: NS * TD0



;$Id:$
"""


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

# Bruker phase-label to integer encoding:
#   0 = x,  1 = y,  2 = -x,  3 = -y
PHASE_TABLE: dict[str, int] = {
    "ph0": 0,
    "ph1": 1,
    "ph2": 2,
    "ph3": 3,
    "ph31": 0,
}
