// Formal equivalence wrapper: fifo_var_ref (golden) vs fifo_var (generated).
module equiv_wrap (input clk);
    reg rst_n = 1'b0;
    always @(posedge clk) rst_n <= 1'b1;

    reg wr_en;
    reg [7:0] din;
    reg rd_en;
    wire [7:0] dout_ref,  dout_impl;
    wire       full_ref,  full_impl;
    wire       empty_ref, empty_impl;
    wire       af_ref,    af_impl;
    wire       ae_ref,    ae_impl;

    fifo_var_ref u_ref (
        .clk          (clk),
        .rst_n       (rst_n),
        .wr_en       (wr_en),
        .din         (din),
        .rd_en       (rd_en),
        .dout        (dout_ref),
        .full        (full_ref),
        .empty       (empty_ref),
        .almost_full (af_ref),
        .almost_empty(ae_ref)
    );

    fifo_var u_impl (
        .clk          (clk),
        .rst_n       (rst_n),
        .wr_en       (wr_en),
        .din         (din),
        .rd_en       (rd_en),
        .dout        (dout_impl),
        .full        (full_impl),
        .empty       (empty_impl),
        .almost_full (af_impl),
        .almost_empty(ae_impl)
    );

    always @(posedge clk) begin
        if (rst_n) begin
            // dout is 0 when the FIFO is empty (memory cleared on reset)
            if (!empty_ref) assert (dout_ref == dout_impl);
            assert (full_ref == full_impl);
            assert (empty_ref == empty_impl);
            assert (af_ref == af_impl);
            assert (ae_ref == ae_impl);
        end
    end
endmodule