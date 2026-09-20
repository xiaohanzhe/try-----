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
    # ⚠️ 本表是**人工维护的线索集**，不是范围定义（分组器 `scan_method_index.py`
    # 是名字前缀启发式，四类偏差都出现过：漏标 / 误纳 / 跨区散布 / 漏标被调方）。
    # 由 W1-6 施工时发现本表已过期（W1-5 组含第六轮已删方法，且 W1-1/W1-2 组
    # 各有 1 个被前缀启发式漏标、施工时人工补入的方法）→ 这里同步补齐，
    # 并由 main() 对"表里有、仓库里没有定义"的名字打 [已移除] 标记，
    # 让过期**自己暴露**，而不是伪装成"0 引用死代码"的假线索。
    "W1-1 spell": [
        "_tick_spell_flow", "_start_open_with_spell", "_spell_interrupted_reason",
        "_cast_spell_then",          # 补：前缀启发式漏标，施工时人工确认
    ],
    "W1-2 hide-seek": [
        "start_hide_and_seek_game", "_hide_move_to_point", "_hide_on_arrive_center",
        "_hide_create_obstacles_after_spell", "_hide_after_hiding_spell",
        "_hide_on_arrive_folder", "_hide_search_tick", "_hide_end_game",
        "_hide_destroy_obstacles", "_hide_report_clicked_folder",
        "_hide_jump_back_to_desktop",
        "_hide_ralsei",              # 补：前缀启发式漏标，施工时人工确认
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
    # W1-5（office 死代码清理）：`check_excel_table_needs` 第六轮已删，
    # 保留名字只为让扫描器打出 [已移除] —— 见本表顶部说明。
    "W1-5 office(old, 方案表里的)": [
        "check_browser_windows", "check_ppt_windows", "check_excel_table_needs",
    ],
    "W1-6 file-sheet": [
        "fix_excel_format", "fill_names_in_excel", "handle_file_operation",
        "_open_desktop_item_by_name",   # 补：索引漏标的第 8 个方法（真 P0 隐患）
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
    """返回 (hits, defined, parse_fail)。

    与旧版的关键差别：**额外收集 defined 集**（全仓库所有 def/class 名）。
    没有它，就无法区分"清单里的名字早已被删（假线索）"与"真有定义但零引用（真死代码）"
    —— 这两者在旧输出里都会显示成"引用点 0"，必须靠人工回查仓库才能分辨。
    """
    hits = {n: [] for n in names}
    defined = set()
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
        # 定义集：模块级 / 类内 / 嵌套都算（ast.walk 全扫）
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in hits:
                hits[node.attr].append((rel, node.lineno, "attr"))
            elif isinstance(node, ast.Name) and node.id in hits:
                hits[node.id].append((rel, node.lineno, "name"))
    return hits, defined, parse_fail


def main():
    argv = sys.argv[1:]
    if argv:
        groups = {"(指定)": argv}
    else:
        groups = WAVE1

    allnames = []
    for ns in groups.values():
        allnames.extend(ns)
    hits, defined, parse_fail = scan(sorted(set(allnames)))

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
            has_def = n in defined
            if not has_def:
                # 清单里有、仓库里没有 → **清单过期**。这不是死代码线索！
                # 显式打标，避免每次 G1 都让人重新确认一遍（W1-6 实测的假线索）。
                lines.append("  %-38s [已移除] 全仓库无定义（静态清单过期，非死代码）" % n)
                continue
            lines.append("  %-38s 引用点 %d" % (n, len(pts)))
            if not pts:
                lines.append("      → 有定义、全项目零引用（可判定为死代码候选）")
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
