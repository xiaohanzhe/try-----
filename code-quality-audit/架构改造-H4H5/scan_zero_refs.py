# -*- coding: utf-8 -*-
"""H4 每项 PR 的"该项专属零引用筛查"（方案 §3 末 / §8 决策 2）。

按 AST 统计名字在**全项目**里的真实引用点（只数语法节点，不做字符串匹配，
避免注释/文档串误命中 —— 见项目"验证脚本教训"）。

用法：
  python scan_zero_refs.py                 # 跑内置 Wave 1 各组
  python scan_zero_refs.py 名字1 名字2 ...   # 只跑指定的名字

产出：_evidence/zero_refs.txt
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUTD = os.path.join(HERE, "_evidence")
OUT = os.path.join(OUTD, "zero_refs.txt")

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".workbuddy", "code-quality-audit"}

# Wave 1 各组的"方法名"，用于一次性筛查（正式施工时按单项再跑一次）
WAVE1 = {
    "W1-1 spell": [
        "_tick_spell_flow", "_start_open_with_spell", "_spell_interrupted_reason",
    ],
    "W1-2 hide-seek": [
        "start_hide_and_seek_game", "_hide_move_to_point", "_hide_on_arrive_center",
        "_hide_create_obstacles_after_spell", "_hide_after_hiding_spell",
        "_hide_on_arrive_folder", "_hide_search_tick", "_hide_end_game",
        "_hide_destroy_obstacles", "_hide_report_clicked_folder",
        "_hide_jump_back_to_desktop",
    ],
    "W1-3 games": [
        "start_rock_paper_scissors", "play_rock_paper_scissors",
        "determine_rock_paper_scissors_winner", "end_rock_paper_scissors",
        "start_guess_number", "play_guess_number", "end_guess_number",
    ],
    "W1-4 video": [
        "check_video_apps", "identify_video_apps", "start_watching_video",
        "stop_watching_video", "suggest_watching_video",
    ],
    "W1-5 office(old, 方案表里的)": [
        "check_browser_windows", "check_ppt_windows", "check_excel_table_needs",
    ],
    "W1-6 file-sheet": [
        "create_person_name_table", "fix_excel_format", "fill_names_in_excel",
        "check_excel_table_needs", "handle_file_operation",
        "check_file_content", "check_text_content", "check_image_content",
    ],
}


def iter_py():
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def scan(names):
    hits = {n: [] for n in names}
    parse_fail = []
    for p in sorted(iter_py()):
        try:
            with io.open(p, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src)
        except Exception:
            parse_fail.append(p)
            continue
        rel = os.path.relpath(p, ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in hits:
                hits[node.attr].append((rel, node.lineno, "attr"))
            elif isinstance(node, ast.Name) and node.id in hits:
                hits[node.id].append((rel, node.lineno, "name"))
    return hits, parse_fail


def main():
    argv = sys.argv[1:]
    if argv:
        groups = {"(指定)": argv}
    else:
        groups = WAVE1

    allnames = []
    for ns in groups.values():
        allnames.extend(ns)
    hits, parse_fail = scan(sorted(set(allnames)))

    lines = []
    lines.append("H4 零引用筛查（AST 口径，非字符串匹配）")
    lines.append("生成脚本：code-quality-audit/架构改造-H4H5/scan_zero_refs.py")
    lines.append("扫描根  ：%s" % os.path.relpath(ROOT, ROOT))
    lines.append("跳过目录：%s" % ", ".join(sorted(SKIP_DIRS)))
    lines.append("")
    for g, ns in groups.items():
        lines.append("=" * 74)
        lines.append("### %s" % g)
        for n in ns:
            pts = hits.get(n, [])
            # 定义点（attr 出现在 def 行 → 不算引用；用 lineno 无法直接判，改看是否有 def）
            defs, refs = [], []
            for rel, ln, kind in pts:
                defs.append((rel, ln, kind))
            lines.append("  %-38s 引用点 %d" % (n, len(pts)))
            if not pts:
                lines.append("      → 全项目零引用（可判定为死代码候选）")
            else:
                agg = {}
                for rel, ln, kind in pts:
                    agg.setdefault(rel, []).append(ln)
                for rel in sorted(agg):
                    ls = sorted(set(agg[rel]))
                    shown = ", ".join(str(x) for x in ls[:12])
                    more = "" if len(ls) <= 12 else " …(+%d)" % (len(ls) - 12)
                    lines.append("      %s  L%s%s" % (rel, shown, more))
        lines.append("")
    if parse_fail:
        lines.append("=== 解析失败（未纳入统计）===")
        for p in parse_fail:
            lines.append("  " + os.path.relpath(p, ROOT))

    if not os.path.isdir(OUTD):
        os.makedirs(OUTD)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    sys.stdout.write("wrote %s\n" % OUT)


main()
