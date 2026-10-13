#!/usr/bin/env bash
# sync_ub24_assets.sh —— 把本技能的 specs/ 验证资产同步到 ub24 的持久目录。
# ub24 侧验证脚本/参考实现/formal wrapper 都在 /opt/asic/work/chipflow/fpga_llm_rtl_loop/<spec>/ 下。
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)/specs"
# ub24 侧目标根目录，可用 UB24_ROOT 环境变量覆盖
DST="${UB24_ROOT:-/opt/asic/work/chipflow/fpga_llm_rtl_loop}"
WSL=/mnt/c/Windows/System32/wsl.exe

for spec_dir in "$SRC"/*/; do
  name="$(basename "$spec_dir")"
  echo "syncing $name -> $DST/$name"
  # shellcheck disable=SC2016
  "$WSL" -d ub24 -- bash -c "mkdir -p '$DST/$name'"
  for f in ref.v equiv_wrap.sv tb.py verify.sh spec.md; do
    if [ -f "$spec_dir/$f" ]; then
      # 经 stdin 写文件（wsl.exe 对多行内容用 -c 传参易截断）
      cat "$spec_dir/$f" | "$WSL" -d ub24 -- bash -c "cat > '$DST/$name/$f'"
    fi
  done
  "$WSL" -d ub24 -- bash -c "chmod +x '$DST/$name/verify.sh' 2>/dev/null || true"
done
echo "OK: assets synced to $DST"