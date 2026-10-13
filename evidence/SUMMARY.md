# fpga-llm-rtl-loop 运行证据汇总

## fifo_var
- **pass@1** = 2/3，**pass@4** = 3/3，**pass** = 3/3
- 平均 tokens/样本 = 12244；通过样本平均 = 12244；总 tokens = 36733
- 参考设计 cells = 317；LLM 设计 cells = [317, 321]
- 通过样本形式验证：prove PASS = 3，bmc 回退 PASS = 0，未通过 = 0

| sample | status | round | tokens | cells(dev) | formal | err_type |
|---|---|---|---|---|---|---|
| s0 | PASS | 1 | 3186 | 317+0 | PASS | - |
| s1 | PASS | 3 | 24609 | 321+4 | PASS | - |
| s2 | PASS | 1 | 8938 | 317+0 | PASS | - |

## pwm
- **pass@1** = 3/4，**pass@4** = 4/4，**pass** = 4/4
- 平均 tokens/样本 = 2773；通过样本平均 = 2773；总 tokens = 11091
- 参考设计 cells = 88；LLM 设计 cells = [88]
- 通过样本形式验证：prove PASS = 3，bmc 回退 PASS = 1，未通过 = 0

| sample | status | round | tokens | cells(dev) | formal | err_type |
|---|---|---|---|---|---|---|
| s0 | PASS | 1 | 1795 | 88+0 | PASS | - |
| s1 | PASS | 1 | 1882 | 88+0 | PASS | - |
| s2 | PASS | 1 | 1744 | 88+0 | PASS | - |
| s3 | PASS | 3 | 5670 | 88+0 | PASS(bmc) | - |

## uart_tx
- **pass@1** = 2/3，**pass@4** = 3/3，**pass** = 3/3
- 平均 tokens/样本 = 12263；通过样本平均 = 12263；总 tokens = 36789
- 参考设计 cells = 110；LLM 设计 cells = [184, 191, 209]
- 通过样本形式验证：prove PASS = 3，bmc 回退 PASS = 0，未通过 = 0

| sample | status | round | tokens | cells(dev) | formal | err_type |
|---|---|---|---|---|---|---|
| s0 | PASS | 1 | 8931 | 191+81 | PASS | - |
| s1 | PASS | 2 | 18927 | 209+99 | PASS | - |
| s2 | PASS | 1 | 8931 | 184+74 | PASS | - |

## 总览
- 总样本 10，pass=10（pass@1=7，pass@4=10），总 tokens=84613
- 形式等价：prove PASS=9，bmc 回退 PASS=1
