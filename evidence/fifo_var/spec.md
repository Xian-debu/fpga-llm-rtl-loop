# Synchronous FIFO with almost_full / almost_empty flags

Implement module `fifo_var`: a synchronous FIFO with depth 8 and 8-bit data width.

Ports:

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | system clock |
| `rst_n` | input | 1 | synchronous reset, active low |
| `wr_en` | input | 1 | write enable |
| `din` | input | 8 | write data |
| `rd_en` | input | 1 | read enable |
| `dout` | output | 8 | read data (contents of the cell pointed by read pointer) |
| `full` | output | 1 | full flag (combinational) |
| `empty` | output | 1 | empty flag (combinational) |
| `almost_full` | output | 1 | almost full: `cnt >= 6` (combinational) |
| `almost_empty` | output | 1 | almost empty: `cnt <= 2` (combinational) |

Behavior:

- Internal 8-deep RAM `mem[0:7]`, read pointer `rd_ptr`, write pointer `wr_ptr`,
  and item counter `cnt` (0~8).
- `rst_n` is a **synchronous reset** (active low): on the rising edge with
  `rst_n=0`, all storage is cleared (`mem[0:7]=0`, `rd_ptr=0`, `wr_ptr=0`, `cnt=0`).
  After reset: `dout=0`, `empty=1`, `full=0`.
- Write: when `wr_en=1 && !full`, on the rising edge store `din` into `mem[wr_ptr]`,
  increment `wr_ptr`, and increment `cnt`.
- Read: when `rd_en=1 && !empty`, on the rising edge increment `rd_ptr` and decrement
  `cnt`. `dout` is a combinational output `mem[rd_ptr]`.
- When both `wr_en && !full` and `rd_en && !empty` hold in the same cycle, `cnt` stays
  unchanged and both pointers advance.
- Write is ignored when full; read is ignored when empty.
- Flags (all combinational): `full = (cnt == 8)`, `empty = (cnt == 0)`,
  `almost_full = (cnt >= 6)`, `almost_empty = (cnt <= 2)`.
- No latches allowed. All state must update on `posedge clk` (synchronous reset).

Write synthesizable Verilog-2001 only. Do not use SystemVerilog constructs.