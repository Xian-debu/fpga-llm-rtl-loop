"""cocotb golden-model tests for module `pwm` (fpga-llm-rtl-loop spec)."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

random.seed(20261011)


async def reset(dut):
    dut.rst_n.value = 0
    dut.pwm_en.value = 0
    dut.duty.value = 0
    await Timer(30, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_pwm_vs_golden(dut):
    """Cycle-by-cycle comparison against a Python golden model (cnt/duty_reg)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    cnt = 1        # RTL cnt after reset() 已消费一个上升沿（复位后首拍 cnt=1）
    duty_reg = 0   # sampled duty register
    for cycle in range(3000):
        # periodic input changes
        if cycle % 50 == 0:
            dut.duty.value = random.randint(0, 255)
        if cycle % 300 == 0:
            dut.pwm_en.value = random.randint(0, 1)

        await RisingEdge(dut.clk)
        await Timer(1, units="ns")

        new_cnt = (cnt + 1) % 256
        if cnt == 255:
            duty_reg = int(dut.duty.value)  # sampled at the period boundary
        pwm_en = int(dut.pwm_en.value)
        exp = 1 if (pwm_en and new_cnt < duty_reg) else 0
        act = int(dut.pwm_out.value)
        if exp != act:
            dut._log.error(
                f"cycle={cycle} cnt={new_cnt} duty_reg={duty_reg} "
                f"duty={int(dut.duty.value)} pwm_en={pwm_en} exp={exp} act={act}")
            raise AssertionError(f"pwm_out mismatch at cycle {cycle}")
        cnt = new_cnt
    dut._log.info(f"golden comparison OK: 3000 cycles")


@cocotb.test()
async def test_pwm_duty_ratio(dut):
    """With duty=64 over 5 full periods, high count must be ~256 (64/256 per period)."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    dut.duty.value = 64
    dut.pwm_en.value = 1

    high = 0
    for _ in range(5 * 256):
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        if dut.pwm_out.value == 1:
            high += 1
    # First period after reset has duty_reg=0 (0 high); periods 2..5 give 64 each = 256.
    if not (240 <= high <= 272):
        raise AssertionError(f"duty=64/256: expected ~256 high cycles over 5 periods, got {high}")
    dut._log.info(f"duty ratio OK: high={high} over {5 * 256} cycles")


@cocotb.test()
async def test_pwm_disable(dut):
    """When pwm_en=0, pwm_out must stay 0 regardless of duty."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)
    dut.duty.value = 200
    dut.pwm_en.value = 0
    for _ in range(300):
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        if int(dut.pwm_out.value) != 0:
            raise AssertionError("pwm_out must be 0 when pwm_en=0")
    dut._log.info("pwm disable OK: output stayed 0")