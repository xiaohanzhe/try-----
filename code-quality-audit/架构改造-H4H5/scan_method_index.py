# -*- coding: utf-8 -*-
"""H4 施工用：main.py 当前真实方法索引（ast，含起止行 / 行数）。

只读，不改任何被跟踪文件。产出：
  _evidence/method_index.txt   人读
  _evidence/method_index.json  机读
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # 项目根
SRC = os.path.join(ROOT, "ralsei_pet", "src", "main.py")
OUTD = os.path.join(HERE, "_evidence")

with io.open(SRC, "r", encoding="utf-8") as f:
    src = f.read()

tree = ast.parse(src)
lines = src.splitlines()
total = len(lines)

cls = None
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "RalseiPet":
        cls = node
        break
assert cls is not None, "RalseiPet 类未找到"

methods = []
for node in cls.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        methods.append({
            "name": node.name,
            "start": node.lineno,
            "end": node.end_lineno,
            "len": node.end_lineno - node.lineno + 1,
            "decorators": [ast.unparse(d) for d in node.decorator_list],
            "args": [a.arg for a in node.args.args],
        })

methods.sort(key=lambda m: m["start"])
total_method_lines = sum(m["len"] for m in methods)

# 归类：按名字前缀给一个粗分组，方便对照方案的 Wave 表
def group_of(name):
    if name.startswith("_spell") or name in ("_start_open_with_spell",):
        return "W1-1 spell"
    if name.startswith("_hide") or name.startswith("start_hide_and_seek") or name.startswith("_hide_"):
        return "W1-2 hide-seek"
    if "rock_paper" in name or "guess" in name or name in ("_game_",):
        return "W1-3 games"
    if name.startswith("video") or "watching_video" in name or "video_app" in name:
        return "W1-4 video"
    if name in ("create_person_name_table", "fix_excel_format", "fill_names_in_excel",
                "handle_file_operation", "check_file_content", "check_text_content",
                "check_image_content"):
        return "W1-6 file-sheet"
    if name in ("get_ralsei_body_part", "mousePressEvent", "mouseMoveEvent",
                "mouseReleaseEvent", "mouseDoubleClickEvent", "update_mouse_drag"):
        return "W2-1 mouse"
    if name in ("update_animation", "change_animation", "play_animation_once",
                "set_animation", "load_animation", "_compose_anchored_sprite"):
        return "W3-1 anim"
    if name in ("update_movement", "randomize_movement_pattern",
                "generate_new_move_target", "init_movement"):
        return "W3-2 move"
    if name in ("start_jump", "handle_jump", "handle_gravity_fall", "handle_fall",
                "start_fall", "check_window_movement", "update_floor", "trigger_splat"):
        return "W3-3 physics"
    return ""

txt = []
txt.append("main.py 方法索引（ast 实测）")
txt.append("生成脚本：code-quality-audit/架构改造-H4H5/scan_method_index.py")
txt.append("源文件：ralsei_pet/src/main.py")
txt.append("")
txt.append("文件总行数        : %d" % total)
txt.append("类                : %s" % cls.name)
txt.append("方法数            : %d" % len(methods))
txt.append("方法体行数合计    : %d" % total_method_lines)
txt.append("")
txt.append("%-6s %-6s %-5s %-12s %s" % ("start", "end", "行数", "分组", "方法名"))
txt.append("-" * 78)
for m in methods:
    txt.append("%-6d %-6d %-5d %-12s %s" % (m["start"], m["end"], m["len"], group_of(m["name"]), m["name"]))
txt.append("")
txt.append("=== 按分组汇总（行数） ===")
agg = {}
for m in methods:
    g = group_of(m["name"])
    if not g:
        continue
    a = agg.setdefault(g, {"n": 0, "lines": 0})
    a["n"] += 1
    a["lines"] += m["len"]
for g in sorted(agg):
    txt.append("%-14s 方法 %3d 个   行数 %5d" % (g, agg[g]["n"], agg[g]["lines"]))

if not os.path.isdir(OUTD):
    os.makedirs(OUTD)
out_txt = os.path.join(OUTD, "method_index.txt")
out_json = os.path.join(OUTD, "method_index.json")
with io.open(out_txt, "w", encoding="utf-8") as f:
    f.write("\n".join(txt))
with io.open(out_json, "w", encoding="utf-8") as f:
    json.dump({
        "source": "ralsei_pet/src/main.py",
        "file_lines": total,
        "class": cls.name,
        "method_count": len(methods),
        "method_body_lines": total_method_lines,
        "methods": methods,
        "group_lines": agg,
    }, f, ensure_ascii=False, indent=1, sort_keys=True)

sys.stdout.write("wrote %s\n" % out_txt)
sys.stdout.write("total=%d methods=%d bodylines=%d\n" % (total, len(methods), total_method_lines))
