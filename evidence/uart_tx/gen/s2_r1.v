
module uart_tx (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    input wire tx_start,
    input wire baud_tick,
    output reg tx,
    output reg tx_busy
);

    localparam IDLE = 2'b00,
               START = 2'b01,
               DATA = 2'b10,
               STOP = 2'b11;

    reg [1:0] state;
    reg [7:0] shift;
    reg [2:0] bit_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            tx <= 1'b1;
            tx_busy <= 1'b0;
            shift <= 8'b0;
            bit_cnt <= 3'd0;
        end else begin
            case (state)
                IDLE: begin
                    if (tx_start) begin
                        state <= START;
                        tx <= 1'b0;
                        tx_busy <= 1'b1;
                        shift <= data_in;
                    end else begin
                        // remain idle, tx and tx_busy already default? Need to set to avoid latches? Since tx and tx_busy are regs assigned in all branches? They hold value if not assigned. But to be safe and match spec, we can set tx<=1'b1, tx_busy<=1'b0 in IDLE. Actually if no tx_start, they should be 1 and 0. If they are already, but after reset they are. But if we don't assign, they hold. That's fine. However, if we came from STOP, we already set busy=0 and tx=1. So IDLE holds. But to avoid inferred latch? Since tx and tx_busy are regs and not assigned in all branches? In always with case, if a reg is not assigned in some branch, it retains value. That's not a latch, it's a register. But to be explicit and avoid warnings, assign defaults at top of case? We can set tx <= 1'b1; tx_busy <= 1'b0; at IDLE branch always. But if tx_start, we override. Let's do that.
                    end
                end
                START: begin
                    // tx_busy stays 1, tx stays 0 unless baud_tick
                    if (baud_tick) begin
                        state <= DATA;
                        tx <= shift[0];
                        shift <= shift >> 1;
                        bit_cnt <= 3'd0;
                    end else begin
                        // hold start bit
                        state <= START;
                        tx <= 1'b0;
                        tx_busy <= 1'b1;
                    end
                end
                DATA: begin
                    if (baud_tick) begin
                        if (bit_cnt == 3'd7) begin
                            state <= STOP;
                            tx <= 1'b1;
                            // shift not needed
                        end else begin
                            state <= DATA;
                            tx <= shift[0];
                            shift <= shift >> 1;
                            bit_cnt <= bit_cnt + 1'b1;
                        end
                    end else begin
                        // hold current data bit
                        state <= DATA;
                        // tx should hold; but to be explicit, we can assign tx <= tx? Not necessary. But if we don't assign, it holds. However, if we assign tx <= shift[0] only on baud_tick, then on non-baud_tick, tx holds. That's fine. But to avoid "incomplete assignment" concerns, we can assign tx <= tx; but that's not needed. Better to not assign and let it hold. But in Verilog, if a reg is not assigned in a branch, it retains value. That's not a latch. So okay.
                    end
                end
                STOP: begin
                    if (baud_tick) begin
                        state <= IDLE;
                        tx <= 1'b1;
                        tx_busy <= 1'b0;
                    end else begin
                        state <= STOP;
                        tx <= 1'b1;
                        tx_busy <= 1'b1;
                    end
                end
                default: begin
                    state <= IDLE;
                    tx <= 1'b1;
                    tx_busy <= 1'b0;
                end
            endcase
        end
    end

endmodule
