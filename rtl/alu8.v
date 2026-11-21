// 8-bit combinational ALU -- implements docs/spec.md
`timescale 1ns/1ps

module alu8 (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [3:0] op,
    input  wire       cin,
    output reg  [7:0] result,
    output reg        carry,
    output reg        zero,
    output reg        negative,
    output reg        overflow
);

    localparam [3:0] OP_ADD  = 4'b0000,
                     OP_SUB  = 4'b0001,
                     OP_AND  = 4'b0010,
                     OP_OR   = 4'b0011,
                     OP_XOR  = 4'b0100,
                     OP_NAND = 4'b0101,
                     OP_NOT  = 4'b0110,
                     OP_SHL  = 4'b0111,
                     OP_SHR  = 4'b1000,
                     OP_INC  = 4'b1001,
                     OP_DEC  = 4'b1010,
                     OP_CMP  = 4'b1011,
                     OP_ADC  = 4'b1100;

    reg [8:0] t;        // 9-bit intermediate: bit 8 = carry / borrow
    reg [7:0] r;        // result
    reg [7:0] fv;       // value used for zero / negative flags
    reg       c, v;
    reg       illegal;

    always @(*) begin
        t = 9'd0;  r = 8'd0;  c = 1'b0;  v = 1'b0;  illegal = 1'b0;

        case (op)
            OP_ADD: begin
                t = {1'b0, a} + {1'b0, b};
                r = t[7:0];  c = t[8];
                v = (a[7] == b[7]) && (r[7] != a[7]);
            end
            OP_ADC: begin
                t = {1'b0, a} + {1'b0, b} + {8'd0, cin};
                r = t[7:0];  c = t[8];
                v = (a[7] == b[7]) && (r[7] != a[7]);
            end
            OP_SUB: begin
                t = {1'b0, a} - {1'b0, b};
                r = t[7:0];  c = t[8];            // borrow
                v = (a[7] != b[7]) && (r[7] != a[7]);
            end
            OP_AND:  r = a & b;
            OP_OR:   r = a | b;
            OP_XOR:  r = a ^ b;
            OP_NAND: r = ~(a & b);
            OP_NOT:  r = ~a;
            OP_SHL: begin
                r = {a[6:0], 1'b0};  c = a[7];
            end
            OP_SHR: begin
                r = {1'b0, a[7:1]};  c = a[0];
            end
            OP_INC: begin
                t = {1'b0, a} + 9'd1;
                r = t[7:0];  c = t[8];
                v = (a == 8'h7F);
            end
            OP_DEC: begin
                t = {1'b0, a} - 9'd1;
                r = t[7:0];  c = t[8];            // borrow
                v = (a == 8'h80);
            end
            OP_CMP: begin
                t = {1'b0, a} - {1'b0, b};
                r = 8'h00;   c = t[8];            // result discarded
                v = (a[7] != b[7]) && (t[7] != a[7]);
            end
            default: illegal = 1'b1;
        endcase

        fv = (op == OP_CMP) ? t[7:0] : r;

        result   = r;
        carry    = illegal ? 1'b0 : c;
        overflow = illegal ? 1'b0 : v;
        zero     = illegal ? 1'b0 : (fv == 8'h00);
        negative = illegal ? 1'b0 : fv[7];
    end

endmodule
