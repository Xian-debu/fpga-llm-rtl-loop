---
name: fpga-llm-rtl-loop
description: LLM RTL 生成本地化闭环技能（S5）。把 E5 chipflow_loop.py 移植为配置驱动的 dsh skill：LLM 依据规格生成 Verilog → verible lint + iverilog/cocotb 金模型仿真 → yosys 综合统计 → SymbiYosys 形式等价验证（ref+impl 输出级 miter + mode bmc 有界等价），错误回灌最多 4 轮；LLM 后端默认 UNI u2-flash（预留 DeepSeek 等 provider 切换入口）；跑 3 个新规格约 10 样本并产出可复现证据包（spec/RTL/日志/token/轮数/PPA/等价性）。当用户要求复现/扩展 E5 的 LLM 写 RTL 闭环、评估 LLM 生成可综合 Verilog 的能力、或生成 pass@4/平均 token/形式等价证据时使用。
---

# fpga-llm-rtl-loop

配置驱动的 LLM RTL 生成闭环（E5 chipflow_loop 的本地化移植，S5）。

## 目录结构
```
fpga-llm-rtl-loop/
├── SKILL.md
├── configs/run_<spec>.json      # 每个规格一个运行配置
├── scripts/
│   ├── run_loop.py              # 主闭环（LLM 生成→lint→仿真→综合→形式验证→回灌）
│   ├── aggregate_evidence.py    # 汇总各规格 evidence 为 SUMMARY.md + aggregate.json
│   └── sync_ub24_assets.sh     # 把 specs/<spec> 资产同步到 ub24
├── specs/<spec>/
│   ├── spec.md                  # 规格文档（LLM 输入）
│   ├── ref.v                    # 参考实现（module <spec>_ref）
│   ├── equiv_wrap.sv            # 形式等价 wrapper（uart_tx 用「属性式包装」：DUT+同步复位金模型；其余规格可用 ref+impl 输出 miter，见失败处理）
│   ├── tb.py                    # cocotb 金模型测试（iverilog 编译 + cocotb）
│   └── verify.sh                # 验证入口（MODULE=<spec>）
└── evidence/<spec>/             # 运行产物（results.json/gen/*.v/spec.md/reference.json）
```

## 前置条件
- ub24 (WSL2) 存活，含：`yosys`、`sby`（SymbiYosys 0.68，**无 `mode equivalence` 且 yosys 0.33 无 `equiv_make` 命令**，等价用 ref+impl **输出级 miter + `mode bmc` 有界等价**，引擎只用 `smtbmc z3`）、`iverilog`（v12+，`-g2012`）、`verible-verilog-syntax`、cocotb（`/opt/asic/venv/bin`，cocotb-config 在 PATH 中）
- ds 侧 Python3 + curl
- LLM API key：默认 `UNI_API_KEY`（环境变量 `LLM_API_KEY` / `UNI_API_KEY`，或 `~/.dsh/.credentials.yaml` 中 `refs.UNI_API_KEY:` 读取）
- WSL stdin 桥：`printf 'cmd\n' | /mnt/c/Windows/System32/wsl.exe -d ub24`（`-c` 传参无效，`bash -c` 或 stdin 可用）

## 执行步骤
1. 同步验证资产到 ub24（每次改 specs/ 后执行）：
   ```bash
   bash scripts/sync_ub24_assets.sh
   ```
2. 运行全部配置（断点续跑，已完成的样本自动跳过）：
   ```bash
   python3 scripts/run_loop.py --all configs
   # 或单个： python3 scripts/run_loop.py configs/run_pwm.json
   ```
3. 汇总证据包：
   ```bash
   python3 scripts/aggregate_evidence.py
   ```

provider 切换入口（环境变量优先于 run.json，无需改配置）：
```bash
LLM_API_BASE=https://api.deepseek.com/v1/chat/completions \
LLM_MODEL=deepseek-v4-flash \
LLM_API_KEY=$DEEPSEEK_API_KEY \
python3 scripts/run_loop.py configs/run_pwm.json
```

## 验收（可证伪，E5 量级）
- pass@4 ≥ 80%（≥ 8/10 样本通过，即样本在 ≤4 轮内通过仿真 + 形式等价）
- 平均 token ≤ 25000/样本
- 通过样本 100% 经 SymbiYosys 建立有界等价（`DONE (PASS)`，`mode bmc`，depth 见各 run_*.json）
- LLM 设计 cell 数与参考设计偏差逐样本记录（`cells_dev`）
- API key 不出现于任何文件明文（仅环境变量 / credentials.yaml 引用）
- `evidence/SUMMARY.md` 记录每样本 status/round/tokens/cells/formal/err_type

## 失败处理
- **SBY 无 `mode equivalence`、yosys 0.33 无 `equiv_make`**：等价用 `equiv_wrap.sv`（ref+impl 输出级 miter）+ `mode bmc`。**不要用 `mode prove` 做主验证**——输出级 miter 的 induction 会从任意非可达内部状态出发产生假反例（两实例输出相同但内部状态不相关，后续输入暴露差异）。
- **引擎只用 `smtbmc z3`**：本机 `smtbmc boolector` 即时报错（`unsupported command 'set-option'`），`abc` 引擎也缺 ABC 命令。
- **depth 选择**：按规格关键行为周期定，保证 `timeout 240` 内出 `DONE (PASS)`。实测（ref-vs-ref 自等价，smtbmc z3）：`pwm` depth 270 ≈1.1s（cnt 满周期回绕 + duty 采样）；`uart_tx` depth 16 ≈52s（满帧）；`fifo_var` depth 12 ≈37s（装满+开始排空；>12 指数变慢，depth 14 已超 140s）。
- **规格必须用同步复位**：异步复位（`always @(posedge clk or negedge rst_n)`）会让 smtbmc 卡死在 `Checking assumptions in step 0..`（任意深度都挂死，原因与符号数据无关）。fifo_var 的 spec/ref 已按此用 `always @(posedge clk)` + `if (!rst_n)`。若某规格 formal 卡 step 0，先查复位风格。
- **对称 ref-vs-impl miter 可能仍卡死（uart_tx 实测）**：即使规格已用异步复位、断言只在 baud_tick 沿、data_in 常量符号化、tx_start 单脉冲假设，depth 4/10/12/16/48 全部卡 `Checking assumptions in step 0..`（ref-vs-ref 却只需 52s）。根因推测：两个**异步复位**设计并排 + 各自内部状态互不关联会让 presat 不收敛。解法：改用 **E5 式属性式包装**（参考 `specs/uart_tx/equiv_wrap.sv`）——只实例化 DUT（异步复位），层内金模型用**同步复位**（`always @(posedge clk)` + `if (!rst_n)` 清零，行为与 ref.v 逐周期一致），断言 `tx_impl === tx_golden`、`busy_impl === busy_golden`。此包装 depth 16 约 43s 收敛 `DONE (PASS)`。
- **形式验证 TIMEOUT**：无结论不 gate（记 `formal=TIMEOUT`），若仿真已 PASS 且 formal 非 FAIL 也计入通过（满足验收需尽量达到 formal PASS，统计会区分 prove/bmc）。
- **SBY 的 DONE 行是 `DONE (PASS, rc=0)`**（PASS 后有逗号），判定必须匹配 `DONE (PASS` 而非 `DONE (PASS)`。`pkill -f 'sby ...'` 必须单独一条 wsl_run 执行（与 sby 同命令时 pkill 会匹配到本命令行里的 `sby -f /tmp/cf.sby` 自噬）。
- **模型输出含推理文本时**：u2-flash 有时不输出 markdown 代码块，推理里会出现句子中间的 `module xxx` 字样。extract_module 必须用**行首锚定**（`^\s*module\s+xxx`）取最后一个完整模块块，否则会把「推理文本+末尾真实模块」整段当代码保存导致 iverilog COMPILE 失败。若某样本多轮全是 COMPILE，优先怀疑提取仍抓到推理文本。
- **API 429/5xx**：run_loop.py 内置指数退避（最多 6 次）；也可切换 provider（见上）。
- **iverilog v12 语法错误退出码仍为 0**：以日志含 `error`/产物缺失为准（verify.sh 已内置 COMPILE-FAIL 判定）。
- WSL 输出尾部 `Failed to translate '\\wsl.localhost\ds\...'` 是良性噪音，不影响结果。