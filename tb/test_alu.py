"""cocotb tests for the 8-bit ALU. Run via:  python tb/run_sim.py"""
import os
from pathlib import Path

import cocotb
from cocotb_coverage.coverage import coverage_db

from alu_env import (AluEnv, constrained_random, corner_sweep, directed_vectors, exhaustive,
                     get_seed, illegal_ops, missing_flag_hits)


@cocotb.test()
async def test_directed(dut):
    await AluEnv(dut, "directed").run(directed_vectors())


@cocotb.test()
async def test_corner_sweep(dut):
    await AluEnv(dut, "corner_sweep").run(corner_sweep())


@cocotb.test()
async def test_illegal_ops(dut):
    await AluEnv(dut, "illegal_ops").run(illegal_ops())


@cocotb.test()
async def test_exhaustive(dut):
    if os.environ.get("ALU_SKIP_EXHAUSTIVE") == "1":
        dut._log.warning("exhaustive test skipped (ALU_SKIP_EXHAUSTIVE=1)")
        return
    await AluEnv(dut, "exhaustive").run(exhaustive())


@cocotb.test()
async def test_random(dut):
    seed = get_seed()
    n = int(os.environ.get("ALU_RANDOM_N", 20000))
    dut._log.info(f"random test: seed={seed} n={n}  (reproduce with ALU_SEED={seed})")
    await AluEnv(dut, "random").run(constrained_random(n, seed))


@cocotb.test()
async def test_coverage_report(dut):
    """Must run last: prints coverage and enforces the goals from docs/verification_plan.md."""
    coverage_db.report_coverage(dut._log.info, bins=False)
    default_out = str(Path(__file__).resolve().parents[1] / "sim" / "coverage.yml")
    out = os.environ.get("ALU_COVERAGE_OUT", default_out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    coverage_db.export_to_yaml(filename=out)
    dut._log.info(f"coverage exported to {out}")

    low = {k: round(v.cover_percentage, 1) for k, v in coverage_db.items() if v.cover_percentage < 100}
    assert not low, f"coverage goals not met: {low}"
    missing = missing_flag_hits()
    assert not missing, f"flag-per-op hits missing: {missing}"
