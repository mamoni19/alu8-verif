"""Golden reference model for the 8-bit ALU (written from docs/spec.md, NOT from the RTL)."""
from typing import NamedTuple

MASK = 0xFF

OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR, OP_NAND, OP_NOT = 0, 1, 2, 3, 4, 5, 6
OP_SHL, OP_SHR, OP_INC, OP_DEC, OP_CMP, OP_ADC = 7, 8, 9, 10, 11, 12

LEGAL_OPS = list(range(13))
ILLEGAL_OPS = [13, 14, 15]
OP_NAMES = {
    0: "ADD", 1: "SUB", 2: "AND", 3: "OR", 4: "XOR", 5: "NAND", 6: "NOT",
    7: "SHL", 8: "SHR", 9: "INC", 10: "DEC", 11: "CMP", 12: "ADC",
}


class AluResult(NamedTuple):
    result: int
    carry: int
    zero: int
    negative: int
    overflow: int

    def packed_flags(self) -> int:
        """Pack flags as {carry, zero, negative, overflow} -> 4-bit value (C=bit3 ... V=bit0)."""
        return (self.carry << 3) | (self.zero << 2) | (self.negative << 1) | self.overflow


def _add_overflow(a: int, b: int, r: int) -> int:
    return int(((a ^ r) & (b ^ r) & 0x80) != 0)


def _sub_overflow(a: int, b: int, r: int) -> int:
    return int(((a ^ b) & (a ^ r) & 0x80) != 0)


def alu_model(a: int, b: int, op: int, cin: int = 0) -> AluResult:
    """Return the expected ALU outputs for the given inputs."""
    a &= MASK
    b &= MASK
    op &= 0xF
    cin &= 1

    carry = overflow = 0
    flagged = None  # value used for zero/negative (defaults to result)

    if op == OP_ADD:
        s = a + b
        res, carry, overflow = s & MASK, s >> 8, _add_overflow(a, b, s & MASK)
    elif op == OP_ADC:
        s = a + b + cin
        res, carry, overflow = s & MASK, s >> 8, _add_overflow(a, b, s & MASK)
    elif op == OP_SUB:
        res = (a - b) & MASK
        carry, overflow = int(a < b), _sub_overflow(a, b, res)
    elif op == OP_AND:
        res = a & b
    elif op == OP_OR:
        res = a | b
    elif op == OP_XOR:
        res = a ^ b
    elif op == OP_NAND:
        res = ~(a & b) & MASK
    elif op == OP_NOT:
        res = ~a & MASK
    elif op == OP_SHL:
        res, carry = (a << 1) & MASK, (a >> 7) & 1
    elif op == OP_SHR:
        res, carry = a >> 1, a & 1
    elif op == OP_INC:
        res, carry, overflow = (a + 1) & MASK, int(a == 0xFF), int(a == 0x7F)
    elif op == OP_DEC:
        res, carry, overflow = (a - 1) & MASK, int(a == 0x00), int(a == 0x80)
    elif op == OP_CMP:
        diff = (a - b) & MASK
        res, flagged = 0x00, diff
        carry, overflow = int(a < b), _sub_overflow(a, b, diff)
    else:  # illegal opcode: result 0, ALL flags 0
        return AluResult(0, 0, 0, 0, 0)

    fv = res if flagged is None else flagged
    return AluResult(res, carry, int(fv == 0), (fv >> 7) & 1, overflow)
