
module uart_tx(
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
reg [2:0] bit_cnt;
reg [7:0] shift;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        state <= IDLE;
        tx <= 1'b1;
        tx_busy <= 1'b0;
        bit_cnt <= 3'd0;
        shift <= 8'd0;
    end else begin
        // default assignments? Need be careful. If we assign defaults at top, then override. For example tx <= tx;? We can set defaults:
        tx <= tx;
        tx_busy <= tx_busy;
        state <= state;
        bit_cnt <= bit_cnt;
        shift <= shift;
        case (state)
            IDLE: begin
                tx <= 1'b1;
                tx_busy <= 1'b0;
                if (tx_start) begin
                    tx <= 1'b0;
                    tx_busy <= 1'b1;
                    state <= START;
                    shift <= data_in;
                    bit_cnt <= 3'd0;
                end else begin
                    state <= IDLE;
                end
            end
            START: begin
                tx <= 1'b0;
                tx_busy <= 1'b1;
                if (baud_tick) begin
                    tx <= shift[0];
                    shift <= {1'b0, shift[7:1]};
                    state <= DATA;
                    bit_cnt <= 3'd0;
                end else begin
                    state <= START;
                end
            end
            DATA: begin
                tx <= shift[0];
                tx_busy <= 1'b1;
                if (baud_tick) begin
                    if (bit_cnt == 3'd7) begin
                        tx <= 1'b1;
                        state <= STOP;
                        bit_cnt <= 3'd0;
                    end else begin
                        tx <= shift[0];
                        shift <= {1'b0, shift[7:1]};
                        bit_cnt <= bit_cnt + 1'b1;
                        state <= DATA;
                    end
                end else begin
                    state <= DATA;
                end
            end
            STOP: begin
                tx <= 1'b1;
                tx_busy <= 1'b1;
                if (baud_tick) begin
                    state <= IDLE;
                    tx_busy <= 1'b0;
                    bit_cnt <= 3'd0;
                end else begin
                    state <= STOP;
                end
            end
            default: begin
                state <= IDLE;
                tx <= 1'b1;
                tx_busy <= 1'b0;
                bit_cnt <= 3'd0;
                shift <= 8'd0;
            end
        endcase
    end
end

endmodule
