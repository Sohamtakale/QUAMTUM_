#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# demo.sh - guided walkthrough of the pulse program generator.
#
#   ./demo.sh          step through, pausing for Enter between sections
#   ./demo.sh -q       run straight through with no pauses
#
# Each section prints the command before running it, so the audience can
# follow along. Outputs are written to a temporary directory and cleaned up.
# ---------------------------------------------------------------------------

set -u
cd "$(dirname "$0")"

# --- pick an interpreter that has pytest, fall back to plain python3 --------
PY=""
for cand in /opt/anaconda3/bin/python3.13 python3.13 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then echo "No python3 found." >&2; exit 1; fi

PYTEST_PY="$PY"
if ! "$PY" -c 'import pytest' 2>/dev/null; then
    for cand in /opt/anaconda3/bin/python3.13 python3.13; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import pytest' 2>/dev/null; then
            PYTEST_PY="$cand"; break
        fi
    done
fi

OUT=$(mktemp -d /tmp/ppgen.XXXXXX)
trap 'rm -rf "$OUT"' EXIT

QUIET=0
[ "${1:-}" = "-q" ] && QUIET=1

B=$(tput bold 2>/dev/null || true); N=$(tput sgr0 2>/dev/null || true)
C=$(tput setaf 6 2>/dev/null || true); G=$(tput setaf 2 2>/dev/null || true)

step() {
    echo
    echo "${B}${C}=== $* ===${N}"
    echo
}
pause() {
    [ "$QUIET" -eq 1 ] && return
    printf '%s' "${B}-- Enter to continue --${N}"; read -r _ </dev/tty || true; echo
}
run() {
    echo "${B}\$ $*${N}"
    eval "$@"
}

echo
echo "${B}Arbitrary Gate-Sequence Pulse Program Generator${N}"
echo "Quantuper two-qubit NMR system  -  1H = qubit 1, 13C = qubit 2"
echo "Interpreter: $PY"
pause

step "1. The problem"
cat <<'EOF'
The original pulse programs are single fixed files where #define flags switch
gate blocks on or off:

    ;#define NOT1
    ;#define HAD
    ;#define CNOT12

Two hard limits follow from that:

  * gate ORDER is fixed by the layout of the file, not by the user
  * each gate can run only ONCE

Running a different circuit meant hand-editing the pulse program.
EOF
pause

step "2. Generate a program from a gate list"
run "$PY generator.py 'NOT1, HAD, CNOT12' --variant A --readout OBSPOP -o $OUT/demo1"
echo
echo "Note: PPS state preparation is emitted by default - no flag needed."
echo
echo "${G}Generated $(wc -l < "$OUT/demo1" | tr -d ' ') lines.${N} The gate section:"
echo
awk '/^  d1$/{f=1;next} /^;; Read out$/{f=0} f' "$OUT/demo1" | sed 's/^/    /'
pause

step "3. Order is the user's, not the file's"
echo "Same two gates, opposite order - note which pulse block comes first."
echo
run "$PY generator.py 'NOT1, HAD' -o $OUT/order1"
run "$PY generator.py 'HAD, NOT1' -o $OUT/order2"
echo
echo "Diff of the two generated programs:"
echo
diff "$OUT/order1" "$OUT/order2" | sed 's/^/    /' || true
echo
echo "${G}The original program cannot express this difference at all.${N}"
pause

step "4. Repeated gates"
echo "The #ifdef scheme can emit each gate at most once. We can repeat freely:"
echo
run "$PY generator.py 'NOT1, NOT1, NOT1' -o $OUT/rep"
echo
echo -n "    180 deg 1H pulses emitted: "
echo "${G}$(grep -c '180 deg y-pulse on 1h' "$OUT/rep")${N}"
pause

step "5. Both hardware variants"
echo "The variants differ only in channel assignment."
echo "  Variant A:  1H -> f2/pl2,  13C -> f1/pl1"
echo "  Variant B:  1H -> f1/pl1,  13C -> f2/pl2"
echo
run "$PY generator.py 'NOT1' --variant A -o $OUT/va"
run "$PY generator.py 'NOT1' --variant B -o $OUT/vb"
echo
echo "The NOT1 (1H) pulse line in each:"
echo
printf '    A:  %s\n' "$(grep '180 deg y-pulse on 1h' "$OUT/va")"
printf '    B:  %s\n' "$(grep '180 deg y-pulse on 1h' "$OUT/vb")"
pause

step "6. Input validation"
echo "All problems are reported at once, with positions and suggestions."
echo "Nothing is written and the exit code is 1."
echo
for bad in "CX12, FOO" "NOT1 HAD" "not1,,had" "PPS" "1, 3, 5"; do
    echo "${B}\$ $PY generator.py '$bad' -o $OUT/never${N}"
    msg=$("$PY" generator.py "$bad" -o "$OUT/never" 2>&1); rc=$?
    printf '%s\n' "$msg" | sed 's/^/    /'
    echo "    ${B}exit code: $rc${N}"
    echo
done
if [ -e "$OUT/never" ]; then
    echo "    UNEXPECTED: a file was created on error"
else
    echo "    ${G}Confirmed: no output file was created by any of the above.${N}"
fi
echo
echo "A failed run also clears a stale file left by an EARLIER run, so a"
echo "rejected input can never leave a valid-looking program behind:"
echo
run "$PY generator.py 'NOT1, HAD' -o $OUT/circuit"
echo "    -> wrote $(wc -l < "$OUT/circuit" | tr -d ' ') lines"
echo "${B}\$ $PY generator.py 'NOT1, CN' -o $OUT/circuit${N}"
"$PY" generator.py 'NOT1, CN' -o "$OUT/circuit" 2>&1 | sed 's/^/    /'
echo "    file still present: ${G}$([ -e "$OUT/circuit" ] && echo yes || echo no)${N}"
echo
echo "But a file this tool did NOT write is never touched:"
echo
printf 'IMPORTANT DATA\n' > "$OUT/thesis.txt"
echo "${B}\$ $PY generator.py 'NOT1, CN' -o $OUT/thesis.txt${N}"
"$PY" generator.py 'NOT1, CN' -o "$OUT/thesis.txt" 2>&1 | sed 's/^/    /'
echo "    contents: ${G}$(cat "$OUT/thesis.txt")${N}"
pause

step "7. Forgiving input"
echo "Lowercase, spaces inside names, and one outer bracket pair are accepted."
echo
"$PY" - <<'EOF' | sed 's/^/    /'
from gate_parser import parse_gate_sequence
for t in ["NOT1, HAD", "not 1, cnot 12", "{HAD, PHAD}", "  nOt12 ,had  "]:
    print(f"{t!r:24} -> {parse_gate_sequence(t)}")
EOF
echo
echo "But a space is never a separator: 'NOT 1 2' is an error, not NOT12,"
echo "because that would be ambiguous."
pause

step "8. Regression against the original programs"
cat <<'EOF'
The strongest correctness claim: for any subset of gates, the generated
program equals the ORIGINAL repo program with exactly those blocks enabled
(normalising only trailing whitespace and blank lines).

All 24 blocks - 9 gates + PPS + OBSPOP + INIT, across both variants - are
byte-identical to the source files.
EOF
echo
run "$PYTEST_PY -m pytest -q -p no:cacheprovider -p no:asyncio -k regression"
pause

step "9. Full test suite"
run "$PYTEST_PY -m pytest -q -p no:cacheprovider -p no:asyncio"
pause

step "10. Status and what is next"
cat <<'EOF'
Done and verified locally:
  * 154 tests passing (69 parser, 85 generator)
  * all 24 pulse blocks byte-identical to the original programs
  * 72 generated programs pass static structural checks

NOT yet done:
  * nothing has been compiled or run in TopSpin - no spectrometer access
    from this machine, so no claim is made about on-instrument behaviour

Settled since the last review (Avik Mitra, WhatsApp):
  * PPS now emitted by DEFAULT, in the preamble - it is the starting point
    of every quantum algorithm. Previously opt-in, which silently produced
    circuits with no state preparation. --no-prep remains for calibration.
  * OBSPOP/INIT already matched the guidance - user's choice, kept out of
    the footer. No change needed.

Needs a decision from Dr. Kale:
  * Q1 (blocking) variant A PHAD appears to have pl1/pl2 swapped, which
    would give wrong flip angles. Present in the ORIGINAL file; copied
    verbatim rather than silently corrected.
  * Q2 three comment mislabels (13C pulses labelled 1H), text only
  * Q5 whether to annotate gate boundaries in the output
  * Q7 must one of OBSPOP/INIT always be present? We currently allow
    neither, which may be the same silent-wrong-default we just fixed
    for PPS.
EOF
echo
echo "${B}${G}End of demo.${N}"
echo
