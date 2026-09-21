# -*- coding: utf-8 -*-
"""第26轮 G1：确认 4 个死代码候选 + 活链路对照组的引用点。

输出自己写 UTF-8（避免 PS 捕获原生 stdout 的 GBK 有损解码）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "code-quality-audit", "架构改造-H4H5"))
import scan_zero_refs as S  # noqa: E402

OUT = os.path.join(HERE, "_evidence", "G1_zero_refs.txt")

NAMES = [
    # 4 个死代码候选
    "check_dragged_file", "react_to_file_deletion", "follow_file", "react_to_file_emotionally",
    # 活链路对照组（应当有引用点）
    "delete_file", "rename_file", "open_file", "open_folder",
    "check_video_windows", "check_game_windows", "react_to_game", "watch_video",
    "interact_with_file", "interact_with_folder",
    "check_file_content", "check_text_content", "check_image_content",
]

hits, defined, parse_fail = S.scan(sorted(set(NAMES)))

lines = []
lines.append("第26轮 G1 零引用筛查（AST 口径，非字符串匹配）")
lines.append("生成脚本：code-quality-audit/第二十六轮/_run_g1_zero_refs.py")
lines.append("扫描根  ：%s" % os.path.relpath(ROOT, ROOT))
lines.append("跳过目录：%s" % ", ".join(sorted(S.SKIP_DIRS)))
lines.append("")

lines.append("=" * 74)
lines.append("### A. 死代码候选（预期：有定义 + 零引用）")
for n in ["check_dragged_file", "react_to_file_deletion", "follow_file", "react_to_file_emotionally"]:
    pts = hits.get(n, [])
    has_def = n in defined
    if not has_def:
        lines.append("  %-38s [已移除] 全仓库无定义" % n)
        continue
    # 定义点本身也算 Attribute/Name? 不算 —— def 语句是 FunctionDef，不是 Name 引用。
    lines.append("  %-38s 有定义=True  引用点 %d" % (n, len(pts)))
    if not pts:
        lines.append("      → 零引用（死代码候选成立）")
    else:
        agg = {}
        for rel, ln, kind in pts:
            agg.setdefault(rel, []).append((ln, kind))
        for rel in sorted(agg):
            ls = sorted(set(x[0] for x in agg[rel]))
            lines.append("      %s  L%s" % (rel, ", ".join(str(x) for x in ls[:12])))
lines.append("")

lines.append("=" * 74)
lines.append("### B. 活链路对照组（预期：引用点 >= 1）")
for n in ["delete_file", "rename_file", "open_file", "open_folder",
          "check_video_windows", "check_game_windows", "react_to_game", "watch_video",
          "interact_with_file", "interact_with_folder",
          "check_file_content", "check_text_content", "check_image_content"]:
    pts = hits.get(n, [])
    has_def = n in defined
    status = "有定义" if has_def else "[已移除]"
    lines.append("  %-38s %s  引用点 %d" % (n, status, len(pts)))
    if pts:
        agg = {}
        for rel, ln, kind in pts:
            agg.setdefault(rel, []).append(ln)
        for rel in sorted(agg):
            ls = sorted(set(agg[rel]))
            shown = ", ".join(str(x) for x in ls[:8])
            more = "" if len(ls) <= 8 else " …(+%d)" % (len(ls) - 8)
            lines.append("      %s  L%s%s" % (rel, shown, more))
lines.append("")

if parse_fail:
    lines.append("=== 解析失败（未纳入统计）===")
    for p in parse_fail:
        lines.append("  " + os.path.relpath(p, ROOT))

outdir = os.path.dirname(OUT)
if not os.path.isdir(outdir):
    os.makedirs(outdir)
with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
sys.stdout.write("wrote %s (%d names, %d parse_fail)\n" % (OUT, len(NAMES), len(parse_fail)))
