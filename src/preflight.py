"""
preflight.py
------------
Static structural checks on generated pulse programs.

This is a LINT, not a TopSpin compile. It catches malformed output - unbalanced
parentheses, undefined phases, dangling jump targets, leftover preprocessor
directives. It cannot catch anything depending on the parameter set, probe
tuning, hardware limits or pulse calibration.

    python3 preflight.py
"""
import re
import sys
import itertools

from generator import generate_pulse_program
from gate_library import VARIANT_A_GATE_LIBRARY

GATES = list(VARIANT_A_GATE_LIBRARY)

def check(prog):
    errs = []
    lines = prog.splitlines()
    code = [l.split(';')[0].rstrip() for l in lines]   # strip comments

    # 1. balanced parentheses per line
    for i, l in enumerate(code, 1):
        if l.count('(') != l.count(')'):
            errs.append(f'line {i}: unbalanced parens: {l!r}')

    # 2. no preprocessor directives left
    for i, l in enumerate(code, 1):
        if l.strip().startswith('#') and 'include' not in l:
            errs.append(f'line {i}: stray directive {l.strip()!r}')

    # 3. every phase referenced must be defined in the phase table
    used = set(re.findall(r'\bph\d+\b', ' '.join(code)))
    defined = set(re.findall(r'^(ph\d+)\s*=', prog, re.M))
    for p in sorted(used - defined):
        errs.append(f'phase {p} used but never defined')

    # 4. loop labels: go=2 / mc ... to 2 must have label "2"
    labels = set(re.findall(r'^(\d+)\s+\S', prog, re.M))
    for tgt in re.findall(r'go=(\d+)', prog) + re.findall(r'to\s+(\d+)', prog):
        if tgt not in labels:
            errs.append(f'jump target {tgt} has no matching label')

    # 5. gradient blocks balanced
    unblk, blk = prog.count('UNBLKGRAD'), len(re.findall(r'(?<!UN)BLKGRAD', prog))
    if unblk != blk:
        errs.append(f'UNBLKGRAD({unblk}) != BLKGRAD({blk})')

    # 6. required skeleton
    for req, desc in [(r'^1 ze$', '"1 ze"'), (r'^exit$', '"exit"'),
                      (r'go=2 ph31', 'go=2 ph31'), (r'"d2=1/\(4\*cnst1\)"', 'd2 definition'),
                      (r'#include <Avance.incl>', 'Avance.incl')]:
        if not re.search(req, prog, re.M):
            errs.append(f'missing {desc}')

    # 7. d2 must be defined before first use
    first_use = next((i for i,l in enumerate(code) if re.search(r'^\s*d2\s*$', l)), None)
    defn = next((i for i,l in enumerate(lines) if 'd2=1/(4*cnst1)' in l), None)
    if first_use is not None and defn is not None and defn > first_use:
        errs.append('d2 used before definition')

    return errs

# matrix: both variants x prep x readout x several sequences
seqs = [['NOT1'], GATES, ['NOT1','HAD','CNOT12'], ['CNOT12']*5,
        ['PHAD','PHAD','NOT12'], GATES*3]
total = bad = 0
params = set()
for variant, prep, readout, seq in itertools.product(
        ('A','B'), (False,True), (None,'OBSPOP','INIT'), seqs):
    prog = generate_pulse_program(seq, variant=variant, prep=prep, readout=readout)
    tag = f'{variant} prep={prep:<5} readout={str(readout):<6} n={len(seq)}'
    errs = check(prog)
    params |= set(re.findall(r'\b(p\d+|pl\d+|d\d+|gp\d+|cnst\d+)\b', prog))
    total += 1
    if errs:
        bad += 1
        print(f'FAIL {tag}')
        for e in errs: print('       ', e)

print(f'{total-bad}/{total} generated programs pass all 7 structural checks')
print('\nparameters the program references (must exist in the TopSpin parameter set):')
def key(s):
    m = re.match(r'([a-z]+)(\d+)', s); return (m.group(1), int(m.group(2)))
print('  ' + '  '.join(sorted(params, key=key)))

# Non-zero exit on any failure, so this can gate a commit or a CI run.
sys.exit(1 if bad else 0)
