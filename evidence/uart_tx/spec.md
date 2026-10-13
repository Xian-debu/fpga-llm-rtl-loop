# UART Transmitter (8N1, baud-tick driven)

Implement module `uart_tx`: a UART transmitter with 8 data bits, 1 start bit and 1 stop bit
(8N1), LSB first. Bit timing is driven by an external `baud_tick` pulse.

Ports:

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | system clock |
| `rst_n` | input | 1 | asynchronous reset, active low |
| `data_in` | input | 8 | byte to transmit |
| `tx_start` | input | 1 | start-transmission pulse (high for one cycle) |
| `baud_tick` | input | 1 | baud-rate clock enable; one high pulse per bit period |
| `tx` | output | 1 | serial output (idle high) |
| `tx_busy` | output | 1 | transmission busy flag |

Behavior (cycle-accurate):

- Idle state: `tx = 1`, `tx_busy = 0`.
- On the rising edge of `clk` where the transmitter is idle and `tx_start = 1` is sampled,
  the transmitter must in that same edge: latch `data_in` into an internal shift register,
  assert `tx_busy = 1`, and drive `tx` low (`tx = 0`, the start bit). Do **not** delay the
  start bit to a later state or wait for `baud_tick` — the start bit begins immediately on
  the `tx_start` sampling edge.
- Transmission sequence: start bit (`tx = 0`, 1 bit period) → 8 data bits LSB first →
  stop bit (`tx = 1`, 1 bit period) → back to idle.
- A bit period is marked by `baud_tick = 1`. On the rising edge of `clk` where
  `baud_tick = 1` while transmitting, the transmitter advances to the next bit: each data
  bit `shift[0]`..`shift[7]` is driven onto `tx` for exactly one bit period, then the stop
  bit (`tx = 1`) for one bit period, then idle (`tx = 1`, `tx_busy = 0`).
- After reset: `tx = 1`, `tx_busy = 0`, all internal state cleared.
- While `tx_busy = 1`, a new `tx_start` is ignored.
- `tx` and `tx_busy` must be register outputs. No latches allowed.

Write synthesizable Verilog-2001 only. Do not use SystemVerilog constructs.