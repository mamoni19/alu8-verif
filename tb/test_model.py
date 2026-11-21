"""Unit tests for the golden model itself (verify the reference before trusting it)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "model"))

import pytest
from alu_model import alu_model, OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR, OP_NAND, OP_NOT, \
    OP_SHL, OP_SHR, OP_INC, OP_DEC, OP_CMP, OP_ADC, ILLEGAL_OPS


def r(a, b, op, cin=0):
    return alu_model(a, b, op, cin)


def test_add_basic():
    assert r(1, 2, OP_ADD) == (3, 0, 0, 0, 0)


def test_add_carry_and_zero():
    assert r(0xFF, 0x01, OP_ADD) == (0x00, 1, 1, 0, 0)


def test_add_signed_overflow():
    assert r(0x7F, 0x01, OP_ADD) == (0x80, 0, 0, 1, 1)
    assert r(0x80, 0x80, OP_ADD) == (0x00, 1, 1, 0, 1)


def test_adc_uses_cin():
    assert r(1, 2, OP_ADC, cin=1).result == 4
    assert r(0xFF, 0x00, OP_ADC, cin=1) == (0x00, 1, 1, 0, 0)
    assert r(1, 2, OP_ADD, cin=1).result == 3  # ADD ignores cin


def test_sub_borrow_and_overflow():
    assert r(5, 3, OP_SUB) == (2, 0, 0, 0, 0)
    assert r(3, 5, OP_SUB) == (0xFE, 1, 0, 1, 0)
    assert r(0x80, 0x01, OP_SUB) == (0x7F, 0, 0, 0, 1)
    assert r(0x7F, 0xFF, OP_SUB) == (0x80, 1, 0, 1, 1)


def test_logic_ops():
    assert r(0xF0, 0x3C, OP_AND).result == 0x30
    assert r(0xF0, 0x3C, OP_OR).result == 0xFC
    assert r(0xF0, 0x3C, OP_XOR).result == 0xCC
    assert r(0xF0, 0x3C, OP_NAND).result == 0xCF
    assert r(0xF0, 0x00, OP_NOT).result == 0x0F


def test_shifts():
    assert r(0x81, 0, OP_SHL) == (0x02, 1, 0, 0, 0)
    assert r(0x81, 0, OP_SHR) == (0x40, 1, 0, 0, 0)
    assert r(0x80, 0, OP_SHL) == (0x00, 1, 1, 0, 0)


def test_inc_dec():
    assert r(0xFF, 0, OP_INC) == (0x00, 1, 1, 0, 0)
    assert r(0x7F, 0, OP_INC) == (0x80, 0, 0, 1, 1)
    assert r(0x00, 0, OP_DEC) == (0xFF, 1, 0, 1, 0)
    assert r(0x80, 0, OP_DEC) == (0x7F, 0, 0, 0, 1)


def test_cmp_flags_from_difference():
    assert r(5, 5, OP_CMP) == (0, 0, 1, 0, 0)       # equal -> zero
    assert r(3, 5, OP_CMP) == (0, 1, 0, 1, 0)       # a<b -> borrow, negative
    assert r(5, 3, OP_CMP) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("op", ILLEGAL_OPS)
def test_illegal_ops_all_zero(op):
    assert r(0xAA, 0x55, op, 1) == (0, 0, 0, 0, 0)


def test_inputs_are_masked():
    assert r(0x1FF, 0x101, OP_ADD) == r(0xFF, 0x01, OP_ADD)


def test_exhaustive_add_matches_python_ints():
    for a in range(256):
        for b in range(256):
            o = r(a, b, OP_ADD)
            assert o.result == (a + b) & 0xFF
            assert o.carry == int(a + b > 255)
            sa = a - 256 if a & 0x80 else a
            sb = b - 256 if b & 0x80 else b
            assert o.overflow == int(not -128 <= sa + sb <= 127)


def test_exhaustive_sub_matches_python_ints():
    for a in range(256):
        for b in range(256):
            o = r(a, b, OP_SUB)
            assert o.result == (a - b) & 0xFF
            assert o.carry == int(a < b)
            sa = a - 256 if a & 0x80 else a
            sb = b - 256 if b & 0x80 else b
            assert o.overflow == int(not -128 <= sa - sb <= 127)
