// Formal equivalence wrapper: uart_tx (generated) vs 内置同步复位金模型。
// 注意：不要用「对称 ref-vs-impl miter」（两个异步复位设计并排比较）——
// smtbmc 会卡死在 step 0（presat 无法收敛，depth 4/10/12/16/48 均超时）。
// 采用属性式包装：DUT（异步复位）+ 层内金模型（同步复位，行为与 ref.v 一致），
// 断言金模型与 DUT 的 tx / tx_busy 逐周期相等。depth 16 约 43s 收敛。
module equiv_wrap (input clk);
    reg rst_n = 1'b0;
    always @(posedge clk) rst_n <= 1'b1;

    reg [7:0] data_in;
    reg tx_start;
    reg baud_tick;

    wire tx_impl, busy_impl;
    uart_tx u_impl (
        .clk      (clk),
        .rst_n    (rst_n),
        .data_in  (data_in),
        .tx_start (tx_start),
        .baud_tick(baud_tick),
        .tx       (tx_impl),
        .tx_busy  (busy_impl)
    );

    // ---- 金模型（行为与 uart_tx_ref 一致；仅用同步复位）----
    localparam IDLE = 4'd10;
    reg [3:0] bit_cnt;
    reg [7:0] shift;
    reg tx_golden;
    reg busy_golden;

    always @(posedge clk) begin
        if (!rst_n) begin
            tx_golden <= 1'b1;
            busy_golden <= 1'b0;
            bit_cnt    <= IDLE;
            shift      <= 8'd0;
        end else begin
            if (bit_cnt == IDLE) begin
                tx_golden  <= 1'b1;
                busy_golden <= 1'b0;
                if (tx_start) begin
                    shift      <= data_in;
                    bit_cnt    <= 4'd0;
                    tx_golden  <= 1'b0;   // start bit
                    busy_golden <= 1'b1;
                end
            end else if (baud_tick) begin
                case (bit_cnt)
                    4'd0: begin tx_golden <= shift[0]; bit_cnt <= 4'd1; end
                    4'd1: begin tx_golden <= shift[1]; bit_cnt <= 4'd2; end
                    4'd2: begin tx_golden <= shift[2]; bit_cnt <= 4'd3; end
                    4'd3: begin tx_golden <= shift[3]; bit_cnt <= 4'd4; end
                    4'd4: begin tx_golden <= shift[4]; bit_cnt <= 4'd5; end
                    4'd5: begin tx_golden <= shift[5]; bit_cnt <= 4'd6; end
                    4'd6: begin tx_golden <= shift[6]; bit_cnt <= 4'd7; end
                    4'd7: begin tx_golden <= shift[7]; bit_cnt <= 4'd8; end
                    4'd8: begin tx_golden <= 1'b1; bit_cnt <= 4'd9; end   // stop bit
                    4'd9: begin bit_cnt <= IDLE; busy_golden <= 1'b0; end
                    default: bit_cnt <= IDLE;
                endcase
            end
        end
    end

    always @(posedge clk) begin
        if (rst_n) begin
            assert (tx_impl === tx_golden);
            assert (busy_impl === busy_golden);
        end
    end
endmodule