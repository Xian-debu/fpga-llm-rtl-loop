module pwm (
    input clk,
    input rst_n,
    input [7:0] duty,
    input pwm_en,
    output pwm_out
);

    reg [7:0] cnt;
    reg [7:0] duty_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 8'd0;
            duty_reg <= 8'd0;
        end else begin
            cnt <= cnt + 1'b1;
            if (cnt == 8'd255)
                duty_reg <= duty;
        end
    end

    assign pwm_out = pwm_en && (cnt < duty_reg);

endmodule
