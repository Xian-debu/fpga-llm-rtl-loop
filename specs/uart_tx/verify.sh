#!/usr/bin/env bash
# verify.sh —— uart_tx 规格的 iverilog 编译 + cocotb 金模型验证。
set -e
DESIGN=$1
MODULE=uart_tx
WORK=/var/tmp/cf_uart_tx_work
rm -rf "$WORK"; mkdir -p "$WORK"
cp "$DESIGN" "$WORK/design.v"
cp "$(dirname "$0")/tb.py" "$WORK/tb.py"
cd "$WORK"

iverilog -g2012 -s "$MODULE" -o sim.out design.v 2>compile.log || {
    echo "COMPILE-FAIL"; head -20 compile.log; exit 1; }

export PATH=/opt/asic/venv/bin:$PATH
export MODULE=tb TOPLEVEL="$MODULE" SIM=icarus VERILOG_SOURCES="$WORK/design.v"
make -f "$(cocotb-config --makefiles)/Makefile.sim" >cocotb.log 2>&1 || {
    echo "TEST-FAIL"; tail -40 cocotb.log; exit 1; }

grep -E "TESTS=.*PASS=.*FAIL=" cocotb.log | tail -1
echo "TEST-SUMMARY"
grep -q "FAIL=0" cocotb.log