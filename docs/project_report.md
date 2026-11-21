# Project Report: 8-bit ALU Verification Framework (Verilog + Python)

## 1. Objective
Design a simple 8-bit ALU in Verilog and build an automated framework in Python that proves it is
correct. The framework generates test inputs, compares the hardware's outputs with an independent
software model, measures how much behaviour was exercised (coverage), and checks that it can catch
bugs deliberately injected into the design (mutation testing).

## 2. Platform and environment
| Item | Detail |
|---|---|
| Operating system | Windows, using PowerShell |
| Editor | VS Code (already installed) |
| Source control / CI | Git, GitHub (`mamoni19/alu8-verif`), GitHub Actions (Ubuntu, Python 3.12) |
| Python | 3.14.2 (already installed; no new Python was needed) |

## 3. What was installed, and why
| Tool | Where | Why it was needed |
|---|---|---|
| **Icarus Verilog 12** (via `winget`) | system-wide, `C:\iverilog` | A **simulator**. Verilog is a hardware description, so it cannot run on its own. Icarus compiles and simulates it. It was the only system-level install. |
| **Python virtual environment** (`.venv`) | inside the project | Keeps the project's packages separate from the global Python so nothing else is affected. |
| **cocotb 2.1** | `.venv` | Lets Python code drive and read the Verilog simulation. This is how the Python testbench talks to the ALU. |
| **cocotb-coverage** | `.venv` | Functional coverage (which operations, operand corners and flag combinations were actually tested). |
| **pytest** | `.venv` | Runs the unit tests of the Python reference model. |
| **pyyaml** | `.venv` | Reads the coverage output when building the HTML report. |
| GTKWave | usually bundled with the Icarus Windows installer | Viewing waveforms (`.vcd`) of the simulation. |

Already present and simply used: VS Code, Python 3.14, Git, `winget`.

**Why not just Python?** The ALU is *hardware* written in Verilog, so it needs a hardware simulator.
**Why not just Verilog?** Verilog testbenches are awkward for exhaustive checks, random stimulus,
coverage and reports, which are easy in Python. Combining both gives the best of each.

## 4. Approach (step by step)
1. **Specification first.** `docs/spec.md` defines the interface, 13 operations (ADD, SUB, AND, OR,
   XOR, NAND, NOT, SHL, SHR, INC, DEC, CMP, ADC), the 4 flags (carry, zero, negative, overflow),
   illegal-opcode behaviour and the borrow convention. Both the design and the model follow this
   one document.
2. **Design (DUT).** `rtl/alu8.v`: a combinational ALU using a 9-bit intermediate value to get
   the carry or borrow.
3. **Golden reference model.** `model/alu_model.py`: a pure-Python version of the spec, written
   independently of the Verilog so a mistake is unlikely to be copied into both. It has its own 15 unit
   tests, including exhaustive ADD and SUB checks against ordinary Python integers.
4. **Quick sanity test.** `tb/tb_smoke.v`: a plain Verilog testbench with 22 hand-checked vectors.
5. **Verification plan.** `docs/verification_plan.md`: features to check, test list, coverage goals
   and pass criteria, written before the testbench.
6. **Testbench (cocotb).** A small layered structure: Transaction -> Driver -> DUT -> Monitor ->
   Scoreboard, with the golden model as the checker and a coverage collector on the side.
7. **Test suite.**

   | Test | Vectors |
   |---|---|
   | Directed | 39 |
   | Corner-value sweep (all ops x edge values x `cin`) | 1,152 |
   | Illegal opcodes | 300 |
   | Exhaustive (ADD, SUB, ADC, CMP: every A and B) | 327,680 |
   | Seeded constrained-random | 20,000 per seed |

   Random seeds are logged so any failure can be reproduced.
8. **Mutation testing.** `tb/run_mutation.py` automatically creates 20 buggy copies of the ALU
   (for example wrong overflow logic, a stuck zero flag, a shift that sign-extends, ADC ignoring
   carry-in) and checks that the regression fails on each one.
9. **Automation and reporting.** `tb/run_all.py` runs every stage and generates `sim/report.html`.
   A GitHub Actions workflow runs the same pipeline on every push.

## 5. Results
| Check | Result |
|---|---|
| Model unit tests | 15/15 passed |
| Verilog smoke test | passed |
| cocotb regression (3 seeds) | 6/6 tests passed on each seed, 0 mismatches |
| Exhaustive test | 327,680 vectors, 0 mismatches |
| Functional coverage | 614/614 bins (100%) |
| Mutation testing | 20/20 injected bugs detected |
| GitHub Actions (Ubuntu) | passing (2 runs) |

## 6. Problems met and how they were solved
- **winget package name.** `iverilog` was not found; the correct ID is `Icarus.Verilog`
  (found with `winget search`).
- **Coverage gap.** The first regression had zero mismatches but failed the coverage goal. One cross
  bin (a mid-value operand pair) was never hit. A mid-value operand (`0x55`) was added to the corner
  sweep, closing the gap deterministically.
- **Results file location.** cocotb wrote `results.xml` into the `tb` folder, so runs overwrote each
  other. Each run now writes its own results and coverage files.
- **`iverilog` not on PATH** in a new terminal. Fixed with `$env:Path += ";C:\iverilog\bin"`,
  and `run_all.py` also does this automatically.
- **GitHub push.** The `gh` CLI was not installed, so the repository was created manually on the
  website, and the first push needed a browser sign-in.

## 7. Limitations
- The ALU is purely combinational. There is no clock, pipeline or timing verification.
- Exhaustive testing covers only ADD, SUB, ADC and CMP. The other operations rely on the corner
  sweep and random tests.
- 20 mutants were chosen by hand. A 100% score shows strength against those bug types, not
  against every possible bug.
- The golden model and the design follow the same spec, so a misreading of the spec itself would not be
  caught by this framework.

## 8. Possible extensions
Parameterised data width (8/16/32 bit), a pipelined ALU variant, SystemVerilog assertions or formal
checks, a results dashboard, and more mutants.

## 9. Where to find everything
Code and docs: https://github.com/mamoni19/alu8-verif. The run commands are in `README.md`.
