# PWM Generator

Implement module `pwm` with the following ports:

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | system clock |
| `rst_n` | input | 1 | asynchronous reset, active low |
| `duty` | input | 8 | duty cycle configuration (0~255) |
| `pwm_en` | input | 1 | output enable |
| `pwm_out` | output | 1 | PWM output |

Behavior:

- Internal free-running 8-bit counter `cnt`, incremented on every `clk` rising edge.
  Reset clears `cnt` to 0. After reaching 255 it wraps back to 0.
- When `cnt == 8'd255`, sample `duty` into internal register `duty_reg` on the next
  rising edge (duty update takes effect at the period boundary).
- `pwm_out` is a combinational output: `pwm_out = pwm_en && (cnt < duty_reg)`.
- After reset: `cnt = 0`, `duty_reg = 0`, `pwm_out = 0`.
- No latches allowed. All state must update on `posedge clk` or asynchronous reset.

Write synthesizable Verilog-2001 only. Do not use SystemVerilog constructs.