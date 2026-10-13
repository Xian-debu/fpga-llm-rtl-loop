"""cocotb golden-model tests for module `fifo_var` (fpga-llm-rtl-loop spec)."""
import random
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

random.seed(20260908)


async def reset(dut):
    dut.rst_n.value = 0
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.din.value = 0
    await Timer(30, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")


@cocotb.test()
async def test_fifo_vs_golden(dut):
    """Random push/pop against a Python deque golden model, cycle-by-cycle."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    dq = deque()  # contents in FIFO order; dout = dq[0] if non-empty
    for cycle in range(2000):
        full = len(dq) == 8
        empty = len(dq) == 0
        r = random.random()
        if empty:
            wr = 1 if r < 0.7 else 0
            rd = 0
        elif full:
            rd = 1 if r < 0.7 else 0
            wr = 0
        else:
            if r < 0.45:
                wr, rd = 1, 0
            elif r < 0.75:
                wr, rd = 0, 1
            elif r < 0.90:
                wr, rd = 1, 1
            else:
                wr, rd = 0, 0
        din = random.randint(0, 255)
        dut.wr_en.value = wr
        dut.rd_en.value = rd
        dut.din.value = din

        await RisingEdge(dut.clk)
        await Timer(1, units="ns")

        # model transition (same edge)
        if wr and not full:
            dq.append(din)
        if rd and not empty:
            dq.popleft()
        c = len(dq)
        exp_full = 1 if c == 8 else 0
        exp_empty = 1 if c == 0 else 0
        exp_af = 1 if c >= 6 else 0
        exp_ae = 1 if c <= 2 else 0

        act = (int(dut.full.value), int(dut.empty.value),
               int(dut.almost_full.value), int(dut.almost_empty.value))
        exp = (exp_full, exp_empty, exp_af, exp_ae)
        if act != exp:
            dut._log.error(f"cycle={cycle} wr={wr} rd={rd} din={din} cnt={c} "
                            f"exp={exp} act={act}")
            raise AssertionError(f"fifo flag mismatch at cycle {cycle}")
        # dout is 0 when empty (memory cleared on reset); otherwise must equal dq[0]
        if dq and int(dut.dout.value) != dq[0]:
            dut._log.error(f"cycle={cycle} wr={wr} rd={rd} din={din} cnt={c} "
                            f"exp_dout={dq[0]} act_dout={int(dut.dout.value)}")
            raise AssertionError(f"fifo dout mismatch at cycle {cycle}")
    dut._log.info("fifo golden comparison OK: 2000 cycles")


@cocotb.test()
async def test_fifo_fill_and_drain(dut):
    """Directed: fill to full, verify flags, then drain; simultaneous rd+wr keeps count."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    # fill 8 items
    for i in range(8):
        assert int(dut.full.value) == 0, f"full should be 0 before item {i}"
        dut.wr_en.value = 1
        dut.din.value = i
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
    assert int(dut.full.value) == 1, "full should be 1 after 8 writes"
    assert int(dut.almost_full.value) == 1, "almost_full should be 1 at cnt=8"
    dut.wr_en.value = 0

    # write ignored when full
    dut.din.value = 0xEE
    dut.wr_en.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert int(dut.full.value) == 1, "full must stay 1 after write-while-full"
    dut.wr_en.value = 0

    # read 2 items: cnt=6 -> almost_full still 1, almost_empty 0
    for i in range(2):
        dut.rd_en.value = 1
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
    dut.rd_en.value = 0
    assert int(dut.full.value) == 0
    assert int(dut.almost_full.value) == 1, "almost_full should be 1 at cnt=6"
    assert int(dut.almost_empty.value) == 0, "almost_empty should be 0 at cnt=6"

    # read to empty, check almost_empty boundaries
    while int(dut.empty.value) == 0:
        dut.rd_en.value = 1
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
    dut.rd_en.value = 0
    assert int(dut.empty.value) == 1, "empty should be 1 after draining"
    assert int(dut.almost_empty.value) == 1, "almost_empty should be 1 at cnt=0"
    assert int(dut.dout.value) == 0, "dout should be 0 when empty"

    # read ignored when empty
    dut.rd_en.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    dut.rd_en.value = 0
    assert int(dut.empty.value) == 1, "empty must stay 1 after read-while-empty"

    # simultaneous read+write keeps count stable
    dut.wr_en.value = 1
    dut.din.value = 0x77
    dut.rd_en.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    assert int(dut.empty.value) == 0, "after simultaneous rd/wr, fifo not empty"
    dut._log.info("fifo fill/drain/flags OK")