module pwm (
    input wire clk,
    input wire rst_n,
    input wire [7:0] duty,
    input wire pwm_en,
    output wire pwm_out
);

    reg [7:0] cnt;
    reg [7:0] duty_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 8'd0;
            duty_reg <= 8'd0;
        end else begin
            if (cnt == 8'd255) begin
                duty_reg <= duty;
            end
            cnt <= cnt + 1'b1;
        end
    end

    assign pwm_out = pwm_en && (cnt < duty_reg);

endmodule
