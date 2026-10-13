`timescale 1ns/1ps
// Reference implementation of the UART transmitter (spec: spec.md)
module uart_tx_ref (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] data_in,
    input  wire tx_start,
    input  wire baud_tick,
    output reg  tx,
    output reg  tx_busy
);
    localparam IDLE = 4'd10;
    reg [3:0] bit_cnt;
    reg [7:0] shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx      <= 1'b1;
            tx_busy <= 1'b0;
            bit_cnt <= IDLE;
            shift   <= 8'd0;
        end else begin
            if (bit_cnt == IDLE) begin
                tx      <= 1'b1;
                tx_busy <= 1'b0;
                if (tx_start) begin
                    shift   <= data_in;
                    bit_cnt <= 4'd0;
                    tx      <= 1'b0;   // start bit
                    tx_busy <= 1'b1;
                end
            end else if (baud_tick) begin
                case (bit_cnt)
                    4'd0: begin
                        tx      <= shift[0];
                        bit_cnt <= 4'd1;
                    end
                    4'd1: begin tx <= shift[1]; bit_cnt <= 4'd2; end
                    4'd2: begin tx <= shift[2]; bit_cnt <= 4'd3; end
                    4'd3: begin tx <= shift[3]; bit_cnt <= 4'd4; end
                    4'd4: begin tx <= shift[4]; bit_cnt <= 4'd5; end
                    4'd5: begin tx <= shift[5]; bit_cnt <= 4'd6; end
                    4'd6: begin tx <= shift[6]; bit_cnt <= 4'd7; end
                    4'd7: begin tx <= shift[7]; bit_cnt <= 4'd8; end
                    4'd8: begin
                        tx      <= 1'b1;   // stop bit
                        bit_cnt <= 4'd9;
                    end
                    4'd9: begin
                        bit_cnt <= IDLE;
                        tx_busy <= 1'b0;
                    end
                    default: bit_cnt <= IDLE;
                endcase
            end
        end
    end
endmodule