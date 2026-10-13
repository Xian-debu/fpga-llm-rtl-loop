#!/usr/bin/env python3
"""
run_loop.py —— fpga-llm-rtl-loop：配置驱动的 LLM RTL 生成闭环
（E5 chipflow_loop.py 的本地化移植：provider 可切换、API key 不再硬编码、形式验证改等价证明）

流水线：spec → LLM 生成 → verible lint → iverilog 编译 + cocotb 金模型 →（通过后）
        yosys 综合统计 → SymbiYosys 形式等价验证（mode bmc 有界等价，属性式包装/输出级 miter，超时回退 bmc）→ 错误回灌 → 重复 N 轮。

ds 侧运行；验证/综合/形式验证经 wsl.exe 桥在 ub24 执行。

用法:
  python3 run_loop.py <run.json>           # 跑单个配置（断点续跑）
  python3 run_loop.py --all <configs目录>  # 顺序跑目录下所有 run_*.json

路径可移植性：run.json 里的 ds 侧路径可用 {ROOT} 占位符表示仓库根目录
（脚本根据自身位置自动推导），例如 "{ROOT}/specs/pwm/spec.md"。

run.json 字段:
  {
    "name": "pwm",                     # 实验名
    "module": "pwm",                   # 生成设计的顶层模块名（提取/验证/综合/形式验证都用它）
    "ref_module": "pwm_ref",           # 参考实现的顶层模块名（ref.v 内）
    "spec": "{ROOT}/specs/pwm/spec.md",   # 规格文档（ds 侧路径）
    "ref":  "{ROOT}/specs/pwm/ref.v",     # 参考实现（ds 侧路径，用于算 cell 数）
    "verify_cmd": "bash /opt/asic/work/chipflow/fpga_llm_rtl_loop/pwm/verify.sh {V}",
    "formal_sby": "... mode bmc ...",           # SymbiYosys .sby 模板（{V}/{M} 占位）
    "formal_sby_fallback": "... mode bmc ...",   # 可选：bmc 超时后的有界等价回退模板
    "api_base": "https://maas-api.unisound.com/v1/chat/completions",
    "model": "u2-flash",
    "api_key_env": "UNI_API_KEY",
    "samples": 4, "max_rounds": 4,
    "out": "{ROOT}/evidence/pwm"
  }

provider 切换入口（环境变量优先于 run.json，无需改配置）:
  LLM_API_BASE / LLM_MODEL / LLM_API_KEY
  例：LLM_API_BASE=https://api.deepseek.com/v1/chat/completions LLM_MODEL=deepseek-v4-flash \
      LLM_API_KEY=$DEEPSEEK_API_KEY python3 run_loop.py configs/run_pwm.json
"""
import json, os, re, subprocess, sys, time, glob, shutil

WSL = "/mnt/c/Windows/System32/wsl.exe"
CREDS = os.path.expanduser("~/.dsh/.credentials.yaml")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _expand(obj):
    """递归把字符串中的 {ROOT} 占位符替换为仓库根目录路径。"""
    if isinstance(obj, str):
        return obj.replace("{ROOT}", ROOT)
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    return obj


def get_key(env):
    """key 来源优先级：环境变量 LLM_API_KEY > api_key_env 环境变量 > ~/.dsh/.credentials.yaml。

    credentials.yaml 支持两种格式：
      旧格式：UNI_API_KEY: sk-xxx（顶层平铺）
      当前格式：refs.UNI_API_KEY: sk-xxx（嵌套 refs: 映射，实际文件为此结构）
    """
    key = os.environ.get("LLM_API_KEY") or os.environ.get(env)
    if not key and os.path.exists(CREDS):
        text = open(CREDS, encoding="utf-8").read()
        # 匹配顶层平铺（UNI_API_KEY:）或 refs: 嵌套下的缩进行（  UNI_API_KEY:）
        m = re.search(rf"^\s*{env}:\s*(\S+)", text, re.M)
        if m:
            key = m.group(1)
    return key


def wsl_run(cmd, stdin_data=None, retries=3, timeout=420):
    r = None
    for _ in range(retries):
        try:
            r = subprocess.run([WSL, "-d", "ub24", "--cd", "/tmp", "--", "bash", "-c", cmd],
                               input=stdin_data, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                return r
        except subprocess.TimeoutExpired:
            pass
        time.sleep(15)
    return r


def call_llm(cfg, messages):
    """调用 OpenAI 兼容 chat/completions。返回 (text, err, total_tokens)。"""
    api_base = (os.environ.get("LLM_API_BASE")
                or cfg.get("api_base", "https://api.deepseek.com/v1/chat/completions"))
    model = os.environ.get("LLM_MODEL") or cfg.get("model", "deepseek-v4-flash")
    key = get_key(cfg.get("api_key_env", "DEEPSEEK_API_KEY"))
    if not key:
        return None, ("NO-KEY: 未找到 API key（设置环境变量 %s 或 LLM_API_KEY）"
                      % cfg.get("api_key_env", "DEEPSEEK_API_KEY")), 0
    payload = {"model": model, "messages": messages, "temperature": 0.85, "max_tokens": 8192}
    for attempt in range(6):
        r = subprocess.run(
            ["curl", "-sS", "--max-time", "300", "-w", "\n__HTTP_%{http_code}__",
             "-H", "Content-Type: application/json", "-H", f"Authorization: Bearer {key}",
             "-d", json.dumps(payload), api_base],
            capture_output=True, text=True, timeout=330)
        out = r.stdout
        m = re.search(r"__HTTP_(\d+)__\s*$", out)
        code = int(m.group(1)) if m else 0
        body = out.split("__HTTP_")[0]
        if code in (429, 500, 502, 503) and attempt < 5:
            time.sleep(min(5 * 2 ** attempt, 60))
            continue
        try:
            d = json.loads(body)
        except Exception:
            return None, f"API-ERR http={code}: {body[:200]}", 0
        if "choices" not in d:
            return None, f"API-ERR http={code}: {json.dumps(d)[:300]}", 0
        msg = d["choices"][0]["message"]
        text = (msg.get("content") or "") + "\n" + (msg.get("reasoning_content") or "")
        return text, None, d.get("usage", {}).get("total_tokens", 0)
    return None, "API-ERR: retries exhausted", 0


def extract_module(text, module):
    """从模型输出提取完整 module 代码块。

    u2-flash 会把推理文本（含 module 片段）放在 content/reasoning_content 开头，
    真实代码在输出末尾。因此：
    1. 若存在 markdown ``` 代码块，取最后一个代码块内、行首锚定的最后一个
       module..endmodule 块；
    2. 否则取文本中行首锚定的最后一个 module..endmodule 块。
    行首锚定（^\\s*module）避免抓到推理文本里句子中间的 "module xxx" 字样。
    """
    if not text:
        return None
    pat = rf"^\s*module\s+{module}\b.*?endmodule"
    fences = list(re.finditer(r"```(?:verilog|systemverilog)?\s*\n?(.*?)```", text, re.S))
    if fences:
        matches = list(re.finditer(pat, fences[-1].group(1), re.M | re.S))
        if matches:
            return matches[-1].group(0)
    matches = list(re.finditer(pat, text, re.M | re.S))
    return matches[-1].group(0) if matches else None


def stage_lint(mod_path, module):
    """verible 语法检查（ub24 原生）。返回 (ok, feedback_lines)。"""
    with open(mod_path, encoding="utf-8") as f:
        r = wsl_run("cat > /tmp/cf_lint.v && verible-verilog-syntax /tmp/cf_lint.v 2>&1 || true",
                    stdin_data=f.read())
    lines = [l for l in (r.stdout + r.stderr).splitlines() if "error" in l.lower()][:10]
    return (len(lines) == 0), lines


def stage_verify(mod_path, verify_cmd):
    """iverilog 编译 + cocotb 金模型。判定契约：输出含 TEST-SUMMARY 且 FAIL=0 → PASS。"""
    cmd = verify_cmd.replace("{V}", "/tmp/cf_design.v")
    with open(mod_path, encoding="utf-8") as f:
        r = wsl_run(f"cat > /tmp/cf_design.v && {cmd}", stdin_data=f.read(), timeout=600)
    out = r.stdout + r.stderr
    if "TEST-SUMMARY" in out and "FAIL=0" in out:
        return "PASS", out
    if "COMPILE-FAIL" in out:
        return "COMPILE", out
    return "TEST", out


def synth_run(module):
    """对 /tmp/cf_design.v 跑 yosys 综合，返回 (area_um2, num_cells)。"""
    ys = (f"read_verilog /tmp/cf_design.v\\nhierarchy -check -top {module}\\n"
          "proc; opt; memory; opt; techmap; opt\\nstat -json\\n")
    r = wsl_run("printf '" + ys + "' > /tmp/cf_synth.ys && "
                "yosys -s /tmp/cf_synth.ys 2>/dev/null", retries=2, timeout=300)
    try:
        out = r.stdout
        i = out.find("\n{") + 1
        if i <= 0:
            i = out.find("{")
        stats, _ = json.JSONDecoder().raw_decode(out[i:])
        d = stats.get("design", {})
        return d.get("area"), d.get("num_cells")
    except Exception:
        return None, None


def stage_synth(mod_path, module):
    with open(mod_path, encoding="utf-8") as f:
        wsl_run("cat > /tmp/cf_design.v", stdin_data=f.read(), retries=2, timeout=120)
    return synth_run(module)


def stage_formal(sby_template, module):
    """SymbiYosys 形式验证。模板 {V}→设计文件、{M}→模块名。
    'DONE (PASS)' → PASS；'failed assertion'/'DONE (FAIL' → FAIL；否则 TIMEOUT（无结论不 gate）。"""
    if not sby_template:
        return "SKIP", ""
    sby = sby_template.replace("{V}", "/tmp/cf_design.v").replace("{M}", module)
    # 多行 .sby 用 stdin 写入（wsl.exe 命令行参数遇真实换行会截断）
    wsl_run("cat > /tmp/cf.sby", stdin_data=sby, retries=1, timeout=60)
    # pkill 单独一次 wsl_run：与 sby 同一条 bash 命令行时，pkill -f 会匹配到
    # 本命令行里的 "sby -f /tmp/cf.sby" 而把自己杀掉（rc=15，formal 从未运行）。
    # 单独调用时 bash 命令行只含括号模式 cf[.]sby，不会被匹配。
    wsl_run("pkill -f 'sby -f /tmp/cf[.]sby' 2>/dev/null; true", retries=1, timeout=30)
    cmd = "cd /tmp && timeout 240 sby -f /tmp/cf.sby 2>&1 | tail -25"
    r = wsl_run(cmd, retries=1, timeout=300)
    out = r.stdout + r.stderr
    # 注意：sby 实际输出是 "DONE (PASS, rc=0)"（PASS 后有逗号），不能匹配 "DONE (PASS)"。
    if "DONE (PASS" in out:
        return "PASS", out
    if "failed assertion" in out or "DONE (FAIL" in out:
        return "FAIL", out
    return "TIMEOUT", out


def feedback_from(out):
    lines = [l for l in out.splitlines()
             if re.search(r"error|Error|AssertionError|FAIL|failed", l)][:14]
    return "\n".join(lines[:12]) if lines else out[-800:]


def run_sample(cfg, sid, model, max_rounds):
    module = cfg["module"]
    outdir = cfg["out"]
    log = {"sample": sid, "model": model, "rounds": [], "tokens": 0, "status": "FAIL"}
    system = ("你是资深数字 IC 设计工程师。只输出可综合 Verilog-2001 代码，"
              "不输出任何解释文字或 markdown 标记。端口名与规格严格一致；"
              "禁止锁存器；组合输出不得悬空。")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"根据以下规格实现模块。只输出完整 Verilog 代码（module {module} ... endmodule）。\n\n规格：\n{cfg['spec']}"}]
    for rnd in range(1, max_rounds + 1):
        t0 = time.time()
        code, err, tok = call_llm(cfg, messages)
        log["tokens"] += tok
        if code is None:
            log["rounds"].append({"r": rnd, "status": err, "tok": tok,
                                  "sec": round(time.time() - t0, 1)})
            continue
        mod = extract_module(code, module)
        if mod is None:
            messages += [{"role": "assistant", "content": code},
                         {"role": "user", "content": f"输出不是完整 module {module} ... endmodule。重新只输出代码。"}]
            log["rounds"].append({"r": rnd, "status": "NO-MODULE", "tok": tok,
                                  "sec": round(time.time() - t0, 1)})
            continue
        path = f"{outdir}/gen/{sid}_r{rnd}.v"
        with open(path, "w", encoding="utf-8") as f:
            f.write(mod + "\n")
        fb_parts = []
        # 1) lint（非致命，warning 计入反馈）
        lok, llines = stage_lint(path, module)
        if not lok:
            fb_parts.append("verible lint 错误:\n" + "\n".join(llines))
        # 2) iverilog 编译 + cocotb 金模型
        status, vout = stage_verify(path, cfg["verify_cmd"])
        rec = {"r": rnd, "status": status, "tok": tok, "sec": round(time.time() - t0, 1),
               "lint": "ok" if lok else "warn"}
        if status != "PASS":
            fb_parts.append("仿真验证失败:\n" + feedback_from(vout))
        else:
            area, cells = stage_synth(path, module)
            rec.update({"area_um2": area, "cells": cells})
            fstatus, fout = stage_formal(cfg.get("formal_sby"), module)
            if fstatus == "TIMEOUT" and cfg.get("formal_sby_fallback"):
                f2, fout2 = stage_formal(cfg["formal_sby_fallback"], module)
                rec["formal"] = ("PASS(bmc)" if f2 == "PASS" else f2)
                rec["formal_mode"] = "bmc-fallback"
                if f2 == "PASS":
                    fstatus = "PASS"
                elif f2 == "FAIL":
                    fstatus = "FAIL"
                    fout = fout2
                else:
                    fstatus = "TIMEOUT"
            else:
                rec["formal"] = fstatus
                rec["formal_mode"] = ("prove" if "mode prove" in cfg.get("formal_sby", "")
                                      else ("bmc" if "mode bmc" in cfg.get("formal_sby", "") else "other"))
            if fstatus == "FAIL":
                fb_parts.append("形式验证失败:\n" + feedback_from(fout))
        log["rounds"].append(rec)
        if status == "PASS" and rec.get("formal", "SKIP") != "FAIL":
            log["status"] = "PASS"
            log["passed_round"] = rnd
            log["file"] = path
            log["formal"] = rec.get("formal")
            log["formal_mode"] = rec.get("formal_mode")
            return log
        fb = ("以下实现未通过验证，修复后重新只输出完整代码：\n" + "\n---\n".join(fb_parts) +
              "\n\n再次提醒：只输出完整 Verilog 代码。")
        messages += [{"role": "assistant", "content": mod}, {"role": "user", "content": fb}]
    return log


def run_config(path):
    cfg = _expand(json.load(open(path, encoding="utf-8")))
    module = cfg["module"]
    outdir = cfg["out"]
    os.makedirs(f"{outdir}/gen", exist_ok=True)
    spec_src = cfg.get("spec")
    cfg["spec"] = open(spec_src, encoding="utf-8").read() if spec_src else ""
    shutil.copyfile(spec_src, f"{outdir}/spec.md")
    model = os.environ.get("LLM_MODEL") or cfg.get("model", "deepseek-v4-flash")

    # 参考设计 cell 数（一次性）
    ref_cells, ref_area = None, None
    ref_path = cfg.get("ref")
    if ref_path and os.path.exists(ref_path):
        with open(ref_path, encoding="utf-8") as f:
            wsl_run("cat > /tmp/cf_design.v", stdin_data=f.read(), retries=2, timeout=120)
        ref_area, ref_cells = synth_run(cfg.get("ref_module", module + "_ref"))
        json.dump({"ref_module": cfg.get("ref_module"), "ref_cells": ref_cells,
                   "ref_area_um2": ref_area}, open(f"{outdir}/reference.json", "w"), indent=2)
        print(f"[ref] {cfg.get('ref_module')}: cells={ref_cells} area={ref_area}", flush=True)

    rfile = f"{outdir}/results.json"
    results = []
    done = set()
    if os.path.exists(rfile):
        try:
            results = json.load(open(rfile, encoding="utf-8"))
            done = {r["sample"] for r in results}
        except Exception:
            pass
    for i in range(cfg["samples"]):
        sid = f"s{i}"
        if sid in done:
            print(f"=== {sid} skipped (done)", flush=True)
            continue
        print(f"=== {sid} start {time.strftime('%H:%M:%S')}", flush=True)
        log = run_sample(cfg, sid, model, cfg["max_rounds"])
        results.append(log)
        json.dump(results, open(rfile, "w"), indent=2)
        print(f"    {sid}: status={log['status']} passed_round={log.get('passed_round')} "
              f"tokens={log['tokens']} cells={[r.get('cells') for r in log['rounds']]} "
              f"formal={[r.get('formal') for r in log['rounds']]}", flush=True)
    n = max(len(results), 1)
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    p1 = sum(1 for r in results if r.get("passed_round") == 1)
    p4 = sum(1 for r in results if r.get("passed_round") is not None and r["passed_round"] <= 4)
    avg_tok = sum(r["tokens"] for r in results) / n
    print(f"=== DONE[{cfg.get('name')}]: pass={n_pass}/{len(results)} pass@1={p1}/{len(results)} "
          f"pass@4={p4}/{len(results)} avg_tokens={avg_tok:.0f} "
          f"total_tokens={sum(r['tokens'] for r in results)}", flush=True)


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--all":
        cfgdir = sys.argv[2]
        for path in sorted(glob.glob(f"{cfgdir}/run_*.json")):
            print(f"\n########## {path} ##########", flush=True)
            run_config(path)
    elif len(sys.argv) == 2:
        run_config(sys.argv[1])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()