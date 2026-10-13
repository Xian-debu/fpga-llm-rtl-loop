#!/usr/bin/env python3
"""
aggregate_evidence.py —— 汇总 fpga-llm-rtl-loop 各规格运行结果，生成证据包。

用法:
  python3 aggregate_evidence.py <evidence根目录> [<output_md>]
    evidence 根目录下每个子目录应含 results.json + reference.json + spec.md + gen/（由 run_loop.py 产出）。

输出:
  - evidence/SUMMARY.md：验收指标表（pass@1/pass@4/avg tokens/每样本轮数/cells/形式验证状态/等价性）
  - evidence/aggregate.json：机器可读汇总
"""
import json, os, sys

PASS = "PASS"


def load_spec(spec_dir):
    rfile = os.path.join(spec_dir, "results.json")
    ref_file = os.path.join(spec_dir, "reference.json")
    if not os.path.exists(rfile):
        return None
    results = json.load(open(rfile, encoding="utf-8"))
    ref = {}
    if os.path.exists(ref_file):
        ref = json.load(open(ref_file, encoding="utf-8"))
    return {"dir": spec_dir, "results": results, "ref": ref}


def sample_row(spec_name, r, ref_cells):
    rounds = r.get("rounds", [])
    passed_round = r.get("passed_round")
    status = r.get("status", "FAIL")
    final_cells = None
    final_area = None
    formal = None
    formal_mode = None
    if status == PASS and rounds:
        for rec in reversed(rounds):
            if rec.get("status") == "PASS":
                final_cells = rec.get("cells")
                final_area = rec.get("area_um2")
                formal = rec.get("formal")
                formal_mode = rec.get("formal_mode")
                break
    # 失败分类：取最后异常状态
    err_type = ""
    if status != PASS:
        last = rounds[-1] if rounds else {}
        st = last.get("status", "")
        if st == "NO-MODULE":
            err_type = "no-module"
        elif st == "COMPILE":
            err_type = "syntax"
        elif st in ("TEST", "TEST-FAIL"):
            err_type = "functional"
        elif st and st.startswith("API-ERR") or st == "NO-KEY":
            err_type = "api"
        else:
            err_type = st.lower() if st else "unknown"
    cells_dev = None
    if final_cells is not None and ref_cells:
        cells_dev = final_cells - ref_cells
    return {
        "sample": r.get("sample"),
        "status": status,
        "passed_round": passed_round,
        "rounds": len(rounds),
        "tokens": r.get("tokens", 0),
        "cells": final_cells,
        "area_um2": final_area,
        "ref_cells": ref_cells,
        "cells_dev": cells_dev,
        "formal": formal,
        "formal_mode": formal_mode,
        "err_type": err_type,
        "file": r.get("file"),
    }


def aggregate(root):
    specs = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d):
            s = load_spec(d)
            if s:
                specs.append((name, s))
    return specs


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "evidence")
    out_md = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "SUMMARY.md")
    root = os.path.abspath(root)
    specs = aggregate(root)
    md = ["# fpga-llm-rtl-loop 运行证据汇总", ""]
    agg = {"specs": {}}
    for spec_name, s in specs:
        results = s["results"]
        ref = s["ref"]
        ref_cells = ref.get("ref_cells")
        rows = [sample_row(spec_name, r, ref_cells) for r in results]
        n = len(rows)
        n_pass = sum(1 for x in rows if x["status"] == PASS)
        p1 = sum(1 for x in rows if x["passed_round"] == 1)
        p4 = sum(1 for x in rows if x["passed_round"] is not None and x["passed_round"] <= 4)
        total_tok = sum(x["tokens"] for x in rows)
        avg_tok = total_tok / n if n else 0
        pass_tok = [x["tokens"] for x in rows if x["status"] == PASS]
        avg_pass_tok = (sum(pass_tok) / len(pass_tok)) if pass_tok else 0
        formal_ok = sum(1 for x in rows if x["status"] == PASS and x["formal"] == "PASS")
        formal_bmc = sum(1 for x in rows if x["status"] == PASS and x["formal"] == "PASS(bmc)")
        md.append(f"## {spec_name}")
        md.append(f"- **pass@1** = {p1}/{n}，**pass@4** = {p4}/{n}，**pass** = {n_pass}/{n}")
        md.append(f"- 平均 tokens/样本 = {avg_tok:.0f}；通过样本平均 = {avg_pass_tok:.0f}；总 tokens = {total_tok}")
        if ref_cells is not None:
            cells_list = [x["cells"] for x in rows if x["cells"] is not None]
            md.append(f"- 参考设计 cells = {ref_cells}；LLM 设计 cells = {sorted(set(cells_list)) if cells_list else 'n/a'}")
        md.append(f"- 通过样本形式验证：prove PASS = {formal_ok}，bmc 回退 PASS = {formal_bmc}，未通过 = "
                  f"{sum(1 for x in rows if x['status']==PASS and x['formal'] not in ('PASS','PASS(bmc)'))}")
        md.append("")
        md.append("| sample | status | round | tokens | cells(dev) | formal | err_type |")
        md.append("|---|---|---|---|---|---|---|")
        for x in rows:
            dev = f"{x['cells_dev']:+d}" if x["cells_dev"] is not None else ""
            md.append(f"| {x['sample']} | {x['status']} | {x['passed_round'] or '-'} | {x['tokens']} "
                      f"| {x['cells']}{dev} | {x['formal'] or '-'} | {x['err_type'] or '-'} |")
        md.append("")
        agg["specs"][spec_name] = {
            "n": n, "pass": n_pass, "pass1": p1, "pass4": p4,
            "avg_tokens": round(avg_tok, 1), "avg_pass_tokens": round(avg_pass_tok, 1),
            "total_tokens": total_tok, "ref_cells": ref_cells,
            "formal_prove_ok": formal_ok, "formal_bmc_ok": formal_bmc,
            "rows": rows,
        }
    md.append("## 总览")
    n_total = sum(v["n"] for v in agg["specs"].values())
    n_pass = sum(v["pass"] for v in agg["specs"].values())
    p1 = sum(v["pass1"] for v in agg["specs"].values())
    p4 = sum(v["pass4"] for v in agg["specs"].values())
    tot = sum(v["total_tokens"] for v in agg["specs"].values())
    md.append(f"- 总样本 {n_total}，pass={n_pass}（pass@1={p1}，pass@4={p4}），总 tokens={tot}")
    md.append(f"- 形式等价：prove PASS={sum(v['formal_prove_ok'] for v in agg['specs'].values())}，"
              f"bmc 回退 PASS={sum(v['formal_bmc_ok'] for v in agg['specs'].values())}")
    md.append("")
    agg_json = os.path.join(os.path.dirname(out_md), "aggregate.json")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(agg_json, "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_md} and {agg_json}")
    print(f"总览: {n_total} 样本 pass={n_pass} pass@1={p1} pass@4={p4} total_tokens={tot}")


if __name__ == "__main__":
    main()