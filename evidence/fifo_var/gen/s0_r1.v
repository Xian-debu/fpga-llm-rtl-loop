module fifo_var (
  input wire clk,
  input wire rst_n,
  input wire wr_en,
  input wire [7:0] din,
  input wire rd_en,
  output wire [7:0] dout,
  output wire full,
  output wire empty,
  output wire almost_full,
  output wire almost_empty
);

  reg [7:0] mem [0:7];
  reg [2:0] wr_ptr;
  reg [2:0] rd_ptr;
  reg [3:0] cnt;

  integer i;

  assign dout = mem[rd_ptr];
  assign full = (cnt == 4'd8);
  assign empty = (cnt == 4'd0);
  assign almost_full = (cnt >= 4'd6);
  assign almost_empty = (cnt <= 4'd2);

  always @(posedge clk) begin
    if (!rst_n) begin
      for (i = 0; i < 8; i = i + 1)
        mem[i] <= 8'd0;
      wr_ptr <= 3'd0;
      rd_ptr <= 3'd0;
      cnt <= 4'd0;
    end else begin
      if (wr_en && !full) begin
        mem[wr_ptr] <= din;
        wr_ptr <= wr_ptr + 1'b1;
      end

      if (rd_en && !empty) begin
        rd_ptr <= rd_ptr + 1'b1;
      end

      if (wr_en && !full && rd_en && !empty) begin
        cnt <= cnt;
      end else if (wr_en && !full) begin
        cnt <= cnt + 1'b1;
      end else if (rd_en && !empty) begin
        cnt <= cnt - 1'b1;
      end else begin
        cnt <= cnt;
      end
    end
  end

endmodule
