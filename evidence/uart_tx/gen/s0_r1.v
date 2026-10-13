
module uart_tx (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    input wire tx_start,
    input wire baud_tick,
    output reg tx,
    output reg tx_busy
);

localparam [1:0] IDLE=2'b00, START=2'b01, DATA=2'b10, STOP=2'b11;

reg [1:0] state;
reg [7:0] shift;
reg [2:0] bit_cnt;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        state <= IDLE;
        shift <= 8'b0;
        bit_cnt <= 3'b0;
        tx <= 1'b1;
        tx_busy <= 1'b0;
    end else begin
        case (state)
            IDLE: begin
                tx <= 1'b1;
                tx_busy <= 1'b0;
                if (tx_start) begin
                    shift <= data_in;
                    bit_cnt <= 3'b0;
                    state <= START;
                    tx <= 1'b0;
                    tx_busy <= 1'b1;
                end
            end
            START: begin
                if (baud_tick) begin
                    state <= DATA;
                    bit_cnt <= 3'b0;
                    tx <= shift[0];
                    // shift? Should we shift at START->DATA? Need decide.
                    shift <= {1'b0, shift[7:1]}; // maybe yes
                end
            end
            DATA: begin
                if (baud_tick) begin
                    if (bit_cnt == 3'd7) begin
                        state <= STOP;
                        tx <= 1'b1;
                        // no shift needed
                    end else begin
                        bit_cnt <= bit_cnt + 1'b1;
                        tx <= shift[0];
                        shift <= {1'b0, shift[7:1]};
                    end
                end
            end
            STOP: begin
                if (baud_tick) begin
                    state <= IDLE;
                    tx_busy <= 1'b0;
                    tx <= 1'b1;
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
