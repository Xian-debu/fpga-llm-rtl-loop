"""cocotb tests for module `uart_tx` (fpga-llm-rtl-loop spec, 8N1 baud-tick driven)."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

BAUD_PERIOD = 5  # one baud_tick pulse every 5 clocks


async def reset(dut):
    dut.rst_n.value = 0
    dut.data_in.value = 0
    dut.tx_start.value = 0
    dut.baud_tick.value = 0
    await Timer(30, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")


async def send_frame(dut, data):
    """Drive one full UART frame with deterministic baud_tick pulses.
    Returns the sampled tx bits: [data0..data7, stop, post_stop].
    """
    dut.data_in.value = data
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0
    await Timer(1, units="ns")
    assert int(dut.tx.value) == 0, "start bit should be low"
    assert int(dut.tx_busy.value) == 1, "busy should assert after tx_start"

    bits = []
    for _ in range(10):
        for _ in range(BAUD_PERIOD):
            await RisingEdge(dut.clk)
        dut.baud_tick.value = 1
        await RisingEdge(dut.clk)   # design advances on this edge
        await Timer(1, units="ns")
        bits.append(int(dut.tx.value))
        dut.baud_tick.value = 0
    return bits


def decode(bits):
    """bits[0..7]=data LSB first, bits[8]=stop, bits[9]=post-stop."""
    data = 0
    for i in range(8):
        data |= (bits[i] << i)
    return data, bits[8]


@cocotb.test()
async def test_uart_tx_single_byte(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    bits = await send_frame(dut, 0x5A)   # 0101_1010
    data, stop = decode(bits)
    assert data == 0x5A, f"expected 0x5A, got 0x{data:02X}; bits={bits}"
    assert stop == 1, "stop bit should be high"
    # post-stop: busy deasserts, tx stays high
    assert bits[9] == 1, "tx should stay high after stop"
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert int(dut.tx_busy.value) == 0, "busy should deassert after frame"
    assert int(dut.tx.value) == 1, "tx should be idle high"
    dut._log.info("single byte 0x5A OK")


@cocotb.test()
async def test_uart_tx_two_bytes(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    bits = await send_frame(dut, 0xA3)
    data, _ = decode(bits)
    assert data == 0xA3, f"byte1 expected 0xA3, got 0x{data:02X}"

    # wait until idle
    for _ in range(20):
        await RisingEdge(dut.clk)
        if int(dut.tx_busy.value) == 0:
            break
    assert int(dut.tx_busy.value) == 0

    bits = await send_frame(dut, 0x00)
    data, stop = decode(bits)
    assert data == 0x00, f"byte2 expected 0x00, got 0x{data:02X}"
    assert stop == 1
    dut._log.info("two bytes OK")


@cocotb.test()
async def test_uart_tx_ignores_start_during_busy(dut):
    """tx_start during transmission must be ignored (frame content unchanged)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    dut.data_in.value = 0x3C
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0

    # mid-frame: assert tx_start with different data
    for _ in range(3 * BAUD_PERIOD):
        await RisingEdge(dut.clk)
    dut.data_in.value = 0xFF
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0

    # drain the frame
    bits = []
    for _ in range(10):
        for _ in range(BAUD_PERIOD):
            await RisingEdge(dut.clk)
        dut.baud_tick.value = 1
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        bits.append(int(dut.tx.value))
        dut.baud_tick.value = 0
    data, _ = decode(bits)
    assert data == 0x3C, f"frame corrupted by tx_start during busy: got 0x{data:02X}"
    dut._log.info("tx_start ignored during busy OK")


@cocotb.test()
async def test_uart_tx_reset_mid_frame(dut):
    """Reset during a frame: tx=1, tx_busy=0 immediately."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    dut.data_in.value = 0x55
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0

    for _ in range(2 * BAUD_PERIOD):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await Timer(5, units="ns")
    assert int(dut.tx.value) == 1, "tx should be idle high after reset"
    assert int(dut.tx_busy.value) == 0, "busy should be 0 after reset"
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    dut._log.info("reset mid-frame OK")