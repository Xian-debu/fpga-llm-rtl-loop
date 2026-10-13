`timescale 1ns/1ps
// Reference implementation of the synchronous FIFO with flags (spec: spec.md)
module fifo_var_ref (
    input  wire clk,
    input  wire rst_n,
    input  wire wr_en,
    input  wire [7:0] din,
    input  wire rd_en,
    output wire [7:0] dout,
    output wire full,
    output wire empty,
    output wire almost_full,
    output wire almost_empty
);
    reg [7:0] mem [0:7];
    reg [2:0] rd_ptr;
    reg [2:0] wr_ptr;
    reg [3:0] cnt;
    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            rd_ptr <= 3'd0;
            wr_ptr <= 3'd0;
            cnt    <= 4'd0;
            for (i = 0; i < 8; i = i + 1)
                mem[i] <= 8'd0;
        end else begin
            if (wr_en && !full)
                mem[wr_ptr] <= din;
            if (wr_en && !full)
                wr_ptr <= wr_ptr + 3'd1;
            if (rd_en && !empty)
                rd_ptr <= rd_ptr + 3'd1;
            if (wr_en && !full && !(rd_en && !empty))
                cnt <= cnt + 4'd1;
            else if (rd_en && !empty && !(wr_en && !full))
                cnt <= cnt - 4'd1;
        end
    end

    assign dout        = mem[rd_ptr];
    assign full        = (cnt == 4'd8);
    assign empty       = (cnt == 4'd0);
    assign almost_full = (cnt >= 4'd6);
    assign almost_empty = (cnt <= 4'd2);
endmodule