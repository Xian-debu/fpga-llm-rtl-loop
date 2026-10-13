module fifo_var(
    input clk,
    input rst_n,
    input wr_en,
    input [7:0] din,
    input rd_en,
    output [7:0] dout,
    output full,
    output empty,
    output almost_full,
    output almost_empty
);

reg [7:0] mem [0:7];
reg [2:0] rd_ptr;
reg [2:0] wr_ptr;
reg [3:0] cnt;
integer i;

assign dout = mem[rd_ptr];
assign full = (cnt == 4'd8);
assign empty = (cnt == 4'd0);
assign almost_full = (cnt >= 4'd6);
assign almost_empty = (cnt <= 4'd2);

always @(posedge clk) begin
    if (!rst_n) begin
        for (i = 0; i < 8; i = i + 1) begin
            mem[i] <= 8'd0;
        end
        rd_ptr <= 3'd0;
        wr_ptr <= 3'd0;
        cnt <= 4'd0;
    end else begin
        if (wr_en && !full) begin
            mem[wr_ptr] <= din;
            wr_ptr <= wr_ptr + 1'b1;
            if (rd_en && !empty) begin
                rd_ptr <= rd_ptr + 1'b1;
            end else begin
                cnt <= cnt + 1'b1;
            end
        end else if (rd_en && !empty) begin
            rd_ptr <= rd_ptr + 1'b1;
            cnt <= cnt - 1'b1;
        end
    end
end

endmodule
