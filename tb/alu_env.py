"""Reusable verification environment for the 8-bit ALU (UVM-lite, Python/cocotb).

Components: Transaction, Driver, Monitor, Scoreboard, coverage sampling, stimulus generators.
"""
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "model"))
from alu_model import (  # noqa: E402
    ILLEGAL_OPS, LEGAL_OPS, OP_NAMES, AluResult, alu_model,
    OP_ADC, OP_ADD, OP_CMP, OP_DEC, OP_INC, OP_SHL, OP_SHR, OP_SUB,
)

CORNERS = [0x00, 0x01, 0x7F, 0x80, 0xFF]


def op_name(op: int) -> str:
    return OP_NAMES.get(op, f"ILLEGAL_{op:X}")


# --------------------------------------------------------------------------- Transaction
@dataclass(frozen=True)
class Transaction:
    a: int
    b: int
    op: int
    cin: int = 0

    def __str__(self) -> str:
        return f"{op_name(self.op)} a=0x{self.a:02X} b=0x{self.b:02X} cin={self.cin}"


# --------------------------------------------------------------------------- Driver
class Driver:
    """Applies a transaction to the DUT inputs and lets the combinational logic settle."""

    def __init__(self, dut):
        self.dut = dut

    async def drive(self, txn: Transaction) -> None:
        self.dut.a.value = txn.a
        self.dut.b.value = txn.b
        self.dut.op.value = txn.op
        self.dut.cin.value = txn.cin
        await Timer(1, "ns")


# --------------------------------------------------------------------------- Monitor
class Monitor:
    """Samples the DUT outputs. Returns None if any output contains X/Z."""

    def __init__(self, dut):
        self.dut = dut

    def sample(self) -> Optional[AluResult]:
        d = self.dut
        sigs = (d.result, d.carry, d.zero, d.negative, d.overflow)
        if not all(s.value.is_resolvable for s in sigs):
            return None
        return AluResult(int(d.result.value), int(d.carry.value), int(d.zero.value),
                         int(d.negative.value), int(d.overflow.value))


# --------------------------------------------------------------------------- Coverage
def corner_class(v: int) -> str:
    return {0x00: "zero", 0x01: "one", 0x7F: "max_signed", 0x80: "min_signed",
            0xFF: "all_ones"}.get(v, "other")


CORNER_BINS = ["zero", "one", "max_signed", "min_signed", "all_ones", "other"]
CARRY_OPS = [OP_ADD, OP_ADC, OP_SUB, OP_CMP, OP_INC, OP_DEC, OP_SHL, OP_SHR]
OVERFLOW_OPS = [OP_ADD, OP_ADC, OP_SUB, OP_CMP, OP_INC, OP_DEC]
FLAG_OPS_HIT = set()  # (op, "carry"|"overflow") with flag == 1 seen


@CoverPoint("alu.op", xf=lambda t, r: t.op, bins=list(range(16)))
@CoverPoint("alu.a_corner", xf=lambda t, r: corner_class(t.a), bins=CORNER_BINS)
@CoverPoint("alu.b_corner", xf=lambda t, r: corner_class(t.b), bins=CORNER_BINS)
@CoverPoint("alu.cin", xf=lambda t, r: t.cin, bins=[0, 1])
@CoverPoint("alu.carry", xf=lambda t, r: r.carry, bins=[0, 1])
@CoverPoint("alu.zero", xf=lambda t, r: r.zero, bins=[0, 1])
@CoverPoint("alu.negative", xf=lambda t, r: r.negative, bins=[0, 1])
@CoverPoint("alu.overflow", xf=lambda t, r: r.overflow, bins=[0, 1])
@CoverCross("alu.op_x_a_x_b", items=["alu.op", "alu.a_corner", "alu.b_corner"])
def sample_coverage(txn: Transaction, exp: AluResult) -> None:
    """Coverage is sampled on EXPECTED values (the DUT is checked separately by the scoreboard)."""
    if exp.carry:
        FLAG_OPS_HIT.add((txn.op, "carry"))
    if exp.overflow:
        FLAG_OPS_HIT.add((txn.op, "overflow"))


def missing_flag_hits() -> List[str]:
    miss = [f"{op_name(o)}:carry" for o in CARRY_OPS if (o, "carry") not in FLAG_OPS_HIT]
    miss += [f"{op_name(o)}:overflow" for o in OVERFLOW_OPS if (o, "overflow") not in FLAG_OPS_HIT]
    return miss


# --------------------------------------------------------------------------- Scoreboard
class Scoreboard:
    """Compares DUT outputs with the golden model and collects mismatches."""

    MAX_LOGGED = 20

    def __init__(self, dut, name: str = "scoreboard"):
        self.log = dut._log
        self.name = name
        self.checked = 0
        self.mismatches: List[str] = []

    def check(self, txn: Transaction, got: Optional[AluResult]) -> bool:
        exp = alu_model(txn.a, txn.b, txn.op, txn.cin)
        sample_coverage(txn, exp)
        self.checked += 1
        if got == exp:
            return True
        msg = f"MISMATCH [{txn}] expected={exp} got={got}"
        self.mismatches.append(msg)
        if len(self.mismatches) <= self.MAX_LOGGED:
            self.log.error(msg)
        return False

    def report(self) -> None:
        self.log.info(f"[{self.name}] checked={self.checked} mismatches={len(self.mismatches)}")
        assert not self.mismatches, (
            f"{len(self.mismatches)} mismatches in {self.checked} checks; first: {self.mismatches[0]}")


class AluEnv:
    """Glue: drive a stream of transactions, sample, and check each one."""

    def __init__(self, dut, name: str = "env"):
        self.dut = dut
        self.driver = Driver(dut)
        self.monitor = Monitor(dut)
        self.scoreboard = Scoreboard(dut, name)

    async def run(self, txns: Iterable[Transaction]) -> None:
        for t in txns:
            await self.driver.drive(t)
            self.scoreboard.check(t, self.monitor.sample())
        self.scoreboard.report()


# --------------------------------------------------------------------------- Generators
def directed_vectors() -> Iterator[Transaction]:
    T = Transaction
    vecs = [
        T(1, 2, 0), T(0xFF, 1, 0), T(0x7F, 1, 0), T(0x80, 0x80, 0), T(0, 0, 0),
        T(5, 3, 1), T(3, 5, 1), T(0x80, 1, 1), T(0x7F, 0xFF, 1), T(0, 0, 1),
        T(0xF0, 0x3C, 2), T(0xF0, 0x3C, 3), T(0xF0, 0x3C, 4), T(0xF0, 0x3C, 5),
        T(0xF0, 0x00, 6), T(0x00, 0x00, 6), T(0xFF, 0x00, 6),
        T(0x81, 0, 7), T(0x80, 0, 7), T(0x01, 0, 7), T(0x81, 0, 8), T(0x01, 0, 8), T(0x80, 0, 8),
        T(0xFF, 0, 9), T(0x7F, 0, 9), T(0x00, 0, 9),
        T(0x00, 0, 10), T(0x80, 0, 10), T(0x01, 0, 10),
        T(5, 5, 11), T(3, 5, 11), T(5, 3, 11), T(0x80, 0x01, 11), T(0x7F, 0xFF, 11),
        T(1, 2, 12, 0), T(1, 2, 12, 1), T(0xFF, 0, 12, 1), T(0x7F, 0, 12, 1), T(0xFF, 0xFF, 12, 1),
    ]
    yield from vecs


def corner_sweep() -> Iterator[Transaction]:
    sweep_vals = CORNERS + [0x55]  # 0x55 represents the 'other' coverage bin
    for op in range(16):
        for a in sweep_vals:
            for b in sweep_vals:
                for cin in (0, 1):
                    yield Transaction(a, b, op, cin)


def illegal_ops(n: int = 300, seed: int = 1) -> Iterator[Transaction]:
    rng = random.Random(seed)
    for _ in range(n):
        yield Transaction(rng.randrange(256), rng.randrange(256), rng.choice(ILLEGAL_OPS), rng.randrange(2))


def exhaustive(ops: Iterable[int] = (OP_ADD, OP_SUB, OP_ADC, OP_CMP)) -> Iterator[Transaction]:
    for op in ops:
        for cin in ((0, 1) if op == OP_ADC else (0,)):
            for a in range(256):
                for b in range(256):
                    yield Transaction(a, b, op, cin)


def get_seed() -> int:
    return int(os.environ.get("ALU_SEED", random.SystemRandom().randrange(1, 2**31)))


def constrained_random(n: int, seed: int, corner_bias: float = 0.3) -> Iterator[Transaction]:
    rng = random.Random(seed)

    def operand() -> int:
        return rng.choice(CORNERS) if rng.random() < corner_bias else rng.randrange(256)

    for _ in range(n):
        yield Transaction(operand(), operand(), rng.randrange(16), rng.randrange(2))
