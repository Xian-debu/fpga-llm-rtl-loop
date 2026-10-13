// Formal equivalence wrapper: pwm_ref (golden) vs pwm (generated).
// Driven clock; internal reset release. Inputs are free variables (SBY).
module equiv_wrap (input clk);
    reg rst_n = 1'b0;
    always @(posedge clk) rst_n <= 1'b1;

    reg [7:0] duty;
    reg pwm_en;
    wire pwm_out_ref;
    wire pwm_out_impl;

    pwm_ref u_ref (
        .clk     (clk),
        .rst_n   (rst_n),
        .duty    (duty),
        .pwm_en  (pwm_en),
        .pwm_out (pwm_out_ref)
    );

    pwm u_impl (
        .clk     (clk),
        .rst_n   (rst_n),
        .duty    (duty),
        .pwm_en  (pwm_en),
        .pwm_out (pwm_out_impl)
    );

    always @(posedge clk) begin
        if (rst_n)
            assert (pwm_out_ref === pwm_out_impl);
    end
endmodule