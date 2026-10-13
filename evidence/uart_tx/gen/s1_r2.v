
module uart_tx(
  input clk, rst_n,
  input [7:0] data_in,
  input tx_start,
  input baud_tick,
  output reg tx,
  output reg tx_busy
);
reg [3:0] state;
reg [7:0] data_shift;
reg [3:0] bit_cnt;
localparam IDLE=0, START=1, DATA=2, STOP=3;

always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
    state <= IDLE;
    tx <= 1'b1;
    tx_busy <= 1'b0;
    data_shift <= 0;
    bit_cnt <= 0;
  end else begin
    case(state)
      IDLE: begin
        tx <= 1'b1;
        tx_busy <= 1'b0;
        if(tx_start) begin
          tx <= 1'b0;
          tx_busy <= 1'b1;
          data_shift <= data_in;
          bit_cnt <= 0;
          state <= START;
        end
      end
      START: begin
        if(baud_tick) begin
          tx <= data_shift[0];
          data_shift <= {data_shift[0], data_shift[7:1]};
          state <= DATA;
        end
      end
      DATA: begin
        if(baud_tick) begin
          if(bit_cnt == 7) begin
            tx <= 1'b1;
            state <= STOP;
          end else begin
            tx <= data_shift[0];
            data_shift <= {data_shift[0], data_shift[7:1]};
            bit_cnt <= bit_cnt + 1;
          end
        end
      end
      STOP: begin
        if(baud_tick) begin
          state <= IDLE;
          tx_busy <= 1'b0;
        end
      end
    endcase
  end
end
endmodule
