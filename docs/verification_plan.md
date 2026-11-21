# Verification Plan: 8-bit ALU

DUT: `rtl/alu8.v` (module `alu8`) | Spec: `docs/spec.md` | Reference: `model/alu_model.py`

## 1. Goals
* Prove the RTL matches the spec for every opcode, every flag and illegal opcodes.
* Build a reusable, self-checking cocotb environment (driver / monitor / scoreboard / coverage).
* Prove the environment is strong by killing injected bugs (mutation testing, Phase 7).

## 2. Features to verify

| ID | Feature | How |
|----|---------|-----|
| F1 | Each of the 13 legal opcodes produces the right `result` | directed + exhaustive + random |
| F2 | `carry` (carry/borrow) correct for ADD/ADC/SUB/CMP/INC/DEC/SHL/SHR | directed + exhaustive |
| F3 | `overflow` (signed) correct for ADD/ADC/SUB/CMP/INC/DEC | corner + exhaustive |
| F4 | `zero` / `negative` computed on the right value (CMP uses `a-b`) | directed + random |
| F5 | `cin` only affects ADC | corner sweep (cin 0/1 on all ops) |
| F6 | Unused operands (`b` for NOT/SHL/SHR/INC/DEC) are ignored | random |
| F7 | Illegal opcodes 13-15 give `result=0` and all flags `0` | directed + sweep |

## 3. Test list (`tb/test_alu.py`)

| Test | Stimulus | Size |
|------|----------|------|
| `test_directed` | hand-picked vectors per opcode | ~50 |
| `test_corner_sweep` | all 16 ops x {00,01,7F,80,FF,55} for A and B x cin 0/1 | 1152 |
| `test_illegal_ops` | opcodes 13-15 with random operands | 300 |
| `test_exhaustive` | every (a,b) for ADD, SUB, ADC (cin 0/1), CMP (~100 s; skip with `ALU_SKIP_EXHAUSTIVE=1`) | ~327k |
| `test_random` | seeded constrained-random (30% corner bias), all ops | 20k (env `ALU_RANDOM_N`) |
| `test_coverage_report` | prints coverage, asserts goals | n/a |

Random tests print their **seed**; re-run with `ALU_SEED=<n>` to reproduce a failure.

## 4. Environment architecture

```
 Generator --> Transaction --> Driver --> [ DUT alu8 ] --> Monitor --> Scoreboard <-- alu_model.py
                                    \                                    |
                                     \------------> Coverage <-----------/
```

## 5. Functional coverage goals (cocotb-coverage)

| Cover item | Bins | Goal |
|------------|------|------|
| `alu.op` | 16 opcodes | 100% |
| `alu.a_corner`, `alu.b_corner` | zero, one, max_signed(7F), min_signed(80), all_ones(FF), other | 100% |
| `alu.cin` | 0, 1 | 100% |
| `alu.op_x_a_x_b` (cross) | 16 x 6 x 6 | 100% |
| `alu.carry/zero/negative/overflow` | each flag seen 0 and 1 | 100% |
| flag-per-op hits | overflow seen for ADD, ADC, SUB, CMP, INC, DEC; carry for ADD, ADC, SUB, CMP, INC, DEC, SHL, SHR | all hit |

## 6. Pass criteria
1. Zero scoreboard mismatches in every test.
2. All coverage goals above reached.
3. (Phase 7) Every injected mutant is detected.

## 7. Risks / notes
* Model and RTL are both written from `spec.md`, but independently, so shared-misreading bugs are only caught by reviewing the spec.
* Borrow convention (carry=1 means `a<b`) is documented in the spec; any change must update both.
* X/Z on DUT outputs is treated as a failure.

## 8. How to run
```powershell
$env:Path += ";C:\iverilog\bin"
.\.venv\Scripts\python tb\run_sim.py                 # full regression
$env:ALU_RANDOM_N=2000; .\.venv\Scripts\python tb\run_sim.py   # quicker
.\.venv\Scripts\python tb\run_sim.py --rtl path\to\mutant.v    # run against another DUT (Phase 7)
```
