from gate_parser import parse_gate_sequence, GateParseError

inputs = [
       "NOT 1 2",
       "NOT1 HAD",
       "not1,,had",
       "NOT1, XYZ, FOO",
       "PPS",
       "not 1, cnot 12",
       "NOT1, NOT2",
       "CX12",
]

for text in inputs:
    print("INPUT:", repr(text))
    try:
        print("  OK:", parse_gate_sequence(text))
    except GateParseError as e:
        print("  ERROR:")
        for line in e.errors:
            print("    ", line)
    print()