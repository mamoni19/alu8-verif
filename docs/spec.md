# 8-bit ALU Specification (single source of truth)

Both `rtl/alu8.v` and `model/alu_model.py` are written from THIS document.

## Interface

| Signal     | Dir | Width | Description                         |
|------------|-----|-------|-------------------------------------|
| `a`        | in  | 8     | Operand A                           |
| `b`        | in  | 8     | Operand B                           |
| `op`       | in  | 4     | Operation select (see table)        |
| `cin`      | in  | 1     | Carry-in (used by ADC only)         |
| `result`   | out | 8     | Operation result                    |
| `carry`    | out | 1     | Carry (ADD/ADC/INC/SHL/SHR) or Borrow (SUB/CMP/DEC) |
| `zero`     | out | 1     | 1 when the 8-bit value being flagged is 0 |
| `negative` | out | 1     | MSB (bit 7) of the value being flagged |
| `overflow` | out | 1     | Signed (two's complement) overflow  |

The ALU is purely **combinational**.

## Opcode table

| `op`   | Name | Result                    | carry            | overflow                          |
|--------|------|---------------------------|------------------|-----------------------------------|
| `0000` | ADD  | `a + b`                   | carry out of bit 7 | `a[7]==b[7] && r[7]!=a[7]`      |
| `0001` | SUB  | `a - b`                   | borrow (`a < b`) | `a[7]!=b[7] && r[7]!=a[7]`        |
| `0010` | AND  | `a & b`                   | 0                | 0                                 |
| `0011` | OR   | `a \| b`                  | 0                | 0                                 |
| `0100` | XOR  | `a ^ b`                   | 0                | 0                                 |
| `0101` | NAND | `~(a & b)`                | 0                | 0                                 |
| `0110` | NOT  | `~a`                      | 0                | 0                                 |
| `0111` | SHL  | `a << 1` (zero fill)      | old `a[7]`       | 0                                 |
| `1000` | SHR  | `a >> 1` (logical)        | old `a[0]`       | 0                                 |
| `1001` | INC  | `a + 1`                   | `a == 0xFF`      | `a == 0x7F`                       |
| `1010` | DEC  | `a - 1`                   | borrow (`a == 0x00`) | `a == 0x80`                   |
| `1011` | CMP  | `0x00` (result discarded) | borrow (`a < b`) | same as SUB                       |
| `1100` | ADC  | `a + b + cin`             | carry out of bit 7 | same rule as ADD                |
| `1101`-`1111` | illegal | `0x00`         | 0                | 0                                 |

## Flag rules

* `zero`     = (flagged value == 0)
* `negative` = flagged value bit 7
* The **flagged value** is `result` for every op, EXCEPT **CMP**, where it is the
  internal difference `a - b` (so `zero` = "a == b", `negative` = sign of the difference).
* **Illegal opcodes** force `result = 0x00` and ALL flags (`carry, zero, negative, overflow`) = 0.
* `cin` is ignored by every op except ADC.
* Operations that do not use `b` (NOT, SHL, SHR, INC, DEC) ignore `b`.

## Conventions

* **Borrow convention:** for SUB/CMP/DEC, `carry = 1` means a borrow occurred (`a < b`).
  This is *not* the inverted-carry convention used by ARM.
* Arithmetic is modulo 256; signed overflow is evaluated on two's-complement interpretation.
