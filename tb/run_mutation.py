"""Mutation testing: inject bugs into the RTL and check that the cocotb regression catches each one.

Usage:  python tb/run_mutation.py [--full]
  --full  also run the 327k-vector exhaustive test (slower, strictest)
A mutant is KILLED if the regression fails because of scoreboard mismatches (the desired outcome).
A SURVIVED mutant means a hole in the testbench. ERROR means the mutant did not compile/run.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "alu8.v"
OUT = ROOT / "sim" / "mutants"

# (id, description, old text, new text) -- `old` must occur exactly once in alu8.v
MUTANTS = [
    ("M01", "ADD overflow: sign compare inverted",
     "t = {1'b0, a} + {1'b0, b};\n                r = t[7:0];  c = t[8];\n                v = (a[7] == b[7])",
     "t = {1'b0, a} + {1'b0, b};\n                r = t[7:0];  c = t[8];\n                v = (a[7] != b[7])"),
    ("M02", "ADC overflow flag stuck at 0",
     "t = {1'b0, a} + {1'b0, b} + {8'd0, cin};\n                r = t[7:0];  c = t[8];\n                v = (a[7] == b[7]) && (r[7] != a[7]);",
     "t = {1'b0, a} + {1'b0, b} + {8'd0, cin};\n                r = t[7:0];  c = t[8];\n                v = 1'b0;"),
    ("M03", "SUB overflow: sign compare inverted",
     "t = {1'b0, a} - {1'b0, b};\n                r = t[7:0];  c = t[8];            // borrow\n                v = (a[7] != b[7])",
     "t = {1'b0, a} - {1'b0, b};\n                r = t[7:0];  c = t[8];            // borrow\n                v = (a[7] == b[7])"),
    ("M04", "SUB borrow flag stuck at 0",
     "t = {1'b0, a} - {1'b0, b};\n                r = t[7:0];  c = t[8];            // borrow\n                v = (a[7] != b[7])",
     "t = {1'b0, a} - {1'b0, b};\n                r = t[7:0];  c = 1'b0;            // borrow\n                v = (a[7] != b[7])"),
    ("M05", "INC overflow threshold off by one (7E)", "v = (a == 8'h7F);", "v = (a == 8'h7E);"),
    ("M06", "DEC overflow threshold off by one (81)", "v = (a == 8'h80);", "v = (a == 8'h81);"),
    ("M07", "SHR sign-extends instead of logical shift",
     "r = {1'b0, a[7:1]};  c = a[0];", "r = {a[7], a[7:1]};  c = a[0];"),
    ("M08", "SHL carry takes wrong bit (a[6])",
     "r = {a[6:0], 1'b0};  c = a[7];", "r = {a[6:0], 1'b0};  c = a[6];"),
    ("M09", "zero flag stuck at 0",
     "zero     = illegal ? 1'b0 : (fv == 8'h00);", "zero     = 1'b0;"),
    ("M10", "CMP flags computed from result instead of a-b",
     "fv = (op == OP_CMP) ? t[7:0] : r;", "fv = r;"),
    ("M11", "illegal opcode returns operand A instead of 0",
     "default: illegal = 1'b1;", "default: begin illegal = 1'b1; r = a; end"),
    ("M12", "ADC ignores carry-in",
     "t = {1'b0, a} + {1'b0, b} + {8'd0, cin};", "t = {1'b0, a} + {1'b0, b};"),
    ("M13", "ADD wrongly uses carry-in",
     "t = {1'b0, a} + {1'b0, b};\n                r = t[7:0];  c = t[8];\n                v = (a[7] == b[7])",
     "t = {1'b0, a} + {1'b0, b} + {8'd0, cin};\n                r = t[7:0];  c = t[8];\n                v = (a[7] == b[7])"),
    ("M14", "NAND implemented as AND", "OP_NAND: r = ~(a & b);", "OP_NAND: r = a & b;"),
    ("M15", "CMP result not discarded",
     "r = 8'h00;   c = t[8];", "r = t[7:0];   c = t[8];"),
    ("M16", "XOR implemented as OR", "OP_XOR:  r = a ^ b;", "OP_XOR:  r = a | b;"),
    ("M17", "NOT inverts B instead of A", "OP_NOT:  r = ~a;", "OP_NOT:  r = ~b;"),
    ("M18", "INC adds 2", "t = {1'b0, a} + 9'd1;", "t = {1'b0, a} + 9'd2;"),
    ("M19", "DEC subtracts 2", "t = {1'b0, a} - 9'd1;", "t = {1'b0, a} - 9'd2;"),
    ("M20", "negative flag taken from bit 6",
     "negative = illegal ? 1'b0 : fv[7];", "negative = illegal ? 1'b0 : fv[6];"),
]


def run_regression(rtl: Path, build_dir: Path, full: bool):
    env = dict(os.environ, ALU_SEED="12345", ALU_RANDOM_N="2000")
    env["ALU_SKIP_EXHAUSTIVE"] = "0" if full else "1"
    p = subprocess.run([sys.executable, str(ROOT / "tb" / "run_sim.py"), "--rtl", str(rtl),
                        "--build-dir", str(build_dir)],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    src = RTL.read_text()
    OUT.mkdir(parents=True, exist_ok=True)

    print("Baseline (unmodified RTL) ...", flush=True)
    rc, _ = run_regression(RTL, OUT / "build_base", args.full)
    if rc != 0:
        print("Baseline FAILS - fix the DUT/testbench before mutation testing.")
        return 2
    print("  baseline passes\n")

    rows, survived, errors = [], [], []
    for mid, desc, old, new in MUTANTS:
        if src.count(old) != 1:
            raise SystemExit(f"{mid}: pattern occurs {src.count(old)}x in alu8.v (need exactly 1)")
        mutant = OUT / f"{mid}.v"
        mutant.write_text(src.replace(old, new))
        rc, out = run_regression(mutant, OUT / f"build_{mid}", args.full)
        if rc == 0:
            status = "SURVIVED"; survived.append(mid)
        elif "mismatches in" in out or "MISMATCH" in out or "coverage goals" in out:
            status = "KILLED"
        else:
            status = "ERROR"; errors.append(mid)
        rows.append((mid, desc, status))
        print(f"  {mid}  {status:<9} {desc}", flush=True)

    killed = sum(1 for r in rows if r[2] == "KILLED")
    score = 100.0 * killed / len(rows)
    print(f"\nMutation score: {killed}/{len(rows)} killed ({score:.0f}%)")
    if survived:
        print("SURVIVED (testbench gaps):", ", ".join(survived))
    if errors:
        print("ERROR (mutant did not run properly):", ", ".join(errors))

    report = ROOT / "sim" / "mutation_report.md"
    lines = ["# Mutation report", "", f"Score: **{killed}/{len(rows)} killed ({score:.0f}%)**", "",
             "| ID | Mutation | Result |", "|----|----------|--------|"]
    lines += [f"| {m} | {d} | {s} |" for m, d, s in rows]
    report.write_text("\n".join(lines) + "\n")
    (ROOT / "sim" / "mutation_results.json").write_text(json.dumps(
        {"killed": killed, "total": len(rows), "score": score,
         "mutants": [{"id": m, "desc": d, "status": s} for m, d, s in rows]}, indent=2))
    print(f"Report written to {report}")
    return 0 if killed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
