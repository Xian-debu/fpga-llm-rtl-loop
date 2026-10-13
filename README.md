# fpga-llm-rtl-loop

**Config-driven LLM RTL generation & verification loop.** An LLM writes synthesizable Verilog from a spec; the loop lints it, verifies it against cocotb golden tests, runs Yosys synthesis statistics, proves bounded equivalence with SymbiYosys, and feeds failures back to the model — repeat until pass (max 4 rounds).

This is a local, portable, provider-switchable re-implementation of the E5 `chipflow_loop.py` concept, packaged as a reproducible evidence pipeline: every sample produces `spec / RTL / tokens / rounds / cells / formal status`.

| Metric (10 samples, 3 specs) | Result |
|---|---|
| pass@4 | **10/10 (100%)** |
| pass@1 | 7/10 |
| avg tokens per sample | **8,461** |
| formal equivalence (SymbiYosys bmc) | **10/10 DONE(PASS)** (9 prove-mode-free + 1 bmc-fallback) |

Full per-sample breakdown: [`evidence/SUMMARY.md`](evidence/SUMMARY.md).

---

## Pipeline

```
 spec.md ──▶ LLM (UNI u2-flash / any OpenAI-compatible) ──▶ module code
                                                              │
              ┌─────────────────────────────────────────────┘
              ▼
  1. verible lint (non-fatal warnings fed back)
  2. iverilog + cocotb golden-model tests ── fail ──▶ error feedback ─┐
              │ pass                                                 │
  3. yosys synth stats (cells / area)                                │
  4. SymbiYosys mode bmc (bounded equivalence vs ref) ── fail ────────▶┘
              │ pass
              ▼
          sample PASS (round, tokens, cells, formal recorded)
```

Runs on the host (`ds`), while compile / simulation / synthesis / formal verification execute inside a **WSL2 Ubuntu 24.04** (`ub24`) via the `wsl.exe` stdin bridge. Everything is config-driven — no API key is hard-coded anywhere.

## Repository layout

```
├── README.md
├── SKILL.md                 # full operator manual (also usable as a DSH/Claude skill)
├── scripts/
│   ├── run_loop.py          # main loop: config-driven, checkpoint/resume
│   ├── aggregate_evidence.py  # renders evidence/SUMMARY.md + aggregate.json
│   └── sync_ub24_assets.sh    # push spec assets (ref.v/wrapper/tb/verify.sh) into ub24
├── configs/
│   ├── run_pwm.json         # 4 samples
│   ├── run_fifo_var.json    # 3 samples
│   └── run_uart_tx.json       # 3 samples
├── specs/<spec>/            # per-spec: spec.md, ref.v, equiv_wrap.sv, tb.py, verify.sh
│   ├── pwm/
│   ├── fifo_var/
│   └── uart_tx/
└── evidence/<spec>/        # per sample: results.json, reference.json, spec.md, gen/s*_r*.v
```

## Requirements

- **WSL2 Ubuntu 24.04 (`ub24`)** with:
  - `yosys` + `sby` (SymbiYosys 0.68; note: no `mode equivalence`, use `mode bmc`; engine `smtbmc z3` only)
  - `iverilog` (v12+, `-g2012`), `verible-verilog-syntax`, cocotb (`/opt/asic/venv/bin`)
- Host: Python 3 + `curl`
- An LLM API key — default `UNI_API_KEY` (env `LLM_API_KEY` / `UNI_API_KEY`, or `refs.UNI_API_KEY:` under `~/.dsh/.credentials.yaml`)

> Paths inside `configs/*.json` on the host use the `{ROOT}` placeholder (repo root, auto-derived from the script location). The `ub24` asset directory defaults to `/opt/asic/work/chipflow/fpga_llm_rtl_loop/<spec>/` and can be overridden with `UB24_ROOT`.

## Quick start

```bash
# 1. sync verification assets into ub24 (run whenever specs/ changes)
bash scripts/sync_ub24_assets.sh

# 2. export your key (or rely on ~/.dsh/.credentials.yaml)
export UNI_API_KEY=sk-...          # or: export LLM_API_KEY=...

# 3a. run one config
python3 scripts/run_loop.py configs/run_pwm.json

# 3b. run everything sequentially
python3 scripts/run_loop.py --all configs

# 4. render the evidence summary
python3 scripts/aggregate_evidence.py
```

Checkpoint/resume is built in: completed samples in `evidence/<spec>/results.json` are skipped on re-runs.

## Switching the LLM provider

Environment variables override `run.json` — no config edit needed:

```bash
LLM_API_BASE=https://api.deepseek.com/v1/chat/completions \
LLM_MODEL=deepseek-v4-flash \
LLM_API_KEY=$DEEPSEEK_API_KEY \
python3 scripts/run_loop.py configs/run_pwm.json
```

## Adding a new spec

1. Create `specs/<name>/` with:
   - `spec.md` — behavioral spec (the LLM input). **Use synchronous reset** (`always @(posedge clk)` + `if (!rst_n)`); async-reset designs make `smtbmc` hang at step 0.
   - `ref.v` — golden implementation (`module <name>_ref`), cycle-accurate.
   - `tb.py` + `verify.sh` — cocotb golden tests + entry (`MODULE=<name>`).
   - `equiv_wrap.sv` — formal wrapper. For serial/state-machine modules use the **attribute-style wrapper** (DUT + sync-reset golden model, e.g. `specs/uart_tx/equiv_wrap.sv`); a symmetric ref-vs-impl miter with two async-reset designs stalls `smtbmc` at step 0. See `SKILL.md` → 失败处理 for details.
2. Add `configs/run_<name>.json` (copy an existing one; pick `samples`, `max_rounds`, bmc `depth`).
3. `bash scripts/sync_ub24_assets.sh`, then run.

## Results interpretation

- `status=PASS` ⇒ simulation golden tests passed **and** formal result is not FAIL (TIMEOUT is tolerated but recorded).
- `formal_mode`: `bmc` (primary) or `bmc-fallback` (when the primary bmc depth times out and a shorter fallback depth proves it).
- `cells` per round is the Yosys gate count of the LLM design; `reference.json` stores the ref design's cell count for deviation tracking.
- `evidence/SUMMARY.md` aggregates pass@1 / pass@4 / avg tokens / formal counts per spec and overall.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Inspired by the E5 `chipflow_loop.py` experiment (`chipflow-takeover`, 2026-09): an early end-to-end prototype of LLM-written, formally-checked RTL on this machine. This repo is the production-shaped, portable, provider-switchable successor.