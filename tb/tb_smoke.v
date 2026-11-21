// Quick smoke testbench (Phase 2) -- hand-checked vectors, view waves in GTKWave
`timescale 1ns/1ps

module tb_smoke;
    reg  [7:0] a, b;
    reg  [3:0] op;
    reg        cin;
    wire [7:0] result;
    wire       carry, zero, negative, overflow;
    integer    errors = 0;

    alu8 dut (.a(a), .b(b), .op(op), .cin(cin),
              .result(result), .carry(carry), .zero(zero),
              .negative(negative), .overflow(overflow));

    task check(input [7:0] ea, input [7:0] eb, input [3:0] eop, input ecin,
               input [7:0] exp_r, input exp_c, input exp_z, input exp_n, input exp_v);
        begin
            a = ea; b = eb; op = eop; cin = ecin; #1;
            if ({result, carry, zero, negative, overflow} !== {exp_r, exp_c, exp_z, exp_n, exp_v}) begin
                errors = errors + 1;
                $display("FAIL op=%b a=%h b=%h cin=%b -> r=%h c=%b z=%b n=%b v=%b (exp %h %b%b%b%b)",
                         eop, ea, eb, ecin, result, carry, zero, negative, overflow,
                         exp_r, exp_c, exp_z, exp_n, exp_v);
            end
        end
    endtask

    initial begin
        $dumpfile("sim/smoke.vcd");
        $dumpvars(0, tb_smoke);

        //     a     b    op      cin  res   C Z N V
        check(8'h01, 8'h02, 4'b0000, 0, 8'h03, 0,0,0,0);  // ADD
        check(8'hFF, 8'h01, 4'b0000, 0, 8'h00, 1,1,0,0);  // ADD carry+zero
        check(8'h7F, 8'h01, 4'b0000, 0, 8'h80, 0,0,1,1);  // ADD overflow
        check(8'h05, 8'h03, 4'b0001, 0, 8'h02, 0,0,0,0);  // SUB
        check(8'h03, 8'h05, 4'b0001, 0, 8'hFE, 1,0,1,0);  // SUB borrow
        check(8'h80, 8'h01, 4'b0001, 0, 8'h7F, 0,0,0,1);  // SUB overflow
        check(8'hF0, 8'h3C, 4'b0010, 0, 8'h30, 0,0,0,0);  // AND
        check(8'hF0, 8'h3C, 4'b0011, 0, 8'hFC, 0,0,1,0);  // OR
        check(8'hF0, 8'h3C, 4'b0100, 0, 8'hCC, 0,0,1,0);  // XOR
        check(8'hF0, 8'h3C, 4'b0101, 0, 8'hCF, 0,0,1,0);  // NAND
        check(8'hF0, 8'h00, 4'b0110, 0, 8'h0F, 0,0,0,0);  // NOT
        check(8'h81, 8'h00, 4'b0111, 0, 8'h02, 1,0,0,0);  // SHL
        check(8'h81, 8'h00, 4'b1000, 0, 8'h40, 1,0,0,0);  // SHR
        check(8'hFF, 8'h00, 4'b1001, 0, 8'h00, 1,1,0,0);  // INC wrap
        check(8'h7F, 8'h00, 4'b1001, 0, 8'h80, 0,0,1,1);  // INC overflow
        check(8'h00, 8'h00, 4'b1010, 0, 8'hFF, 1,0,1,0);  // DEC borrow
        check(8'h80, 8'h00, 4'b1010, 0, 8'h7F, 0,0,0,1);  // DEC overflow
        check(8'h05, 8'h05, 4'b1011, 0, 8'h00, 0,1,0,0);  // CMP equal
        check(8'h03, 8'h05, 4'b1011, 0, 8'h00, 1,0,1,0);  // CMP a<b
        check(8'h01, 8'h02, 4'b1100, 1, 8'h04, 0,0,0,0);  // ADC with cin
        check(8'hFF, 8'h00, 4'b1100, 1, 8'h00, 1,1,0,0);  // ADC carry
        check(8'hAA, 8'h55, 4'b1111, 1, 8'h00, 0,0,0,0);  // illegal

        if (errors == 0) $display("SMOKE TEST PASSED");
        else             $display("SMOKE TEST FAILED: %0d error(s)", errors);
        $finish;
    end
endmodule
