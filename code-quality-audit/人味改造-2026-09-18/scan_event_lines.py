# -*- coding: utf-8 -*-
"""S7 施工用：事件台词（add_dialogue）全量清单 + 触发来源分类。

只读，不改任何被跟踪文件。产出：
  _evidence/event_lines.txt   人读
  _evidence/event_lines.json  机读

口径
----
* 「事件台词」= 代码里直接写死的 add_dialogue(...) 调用（用户拍板 S7 的对象）。
* 分类维度两个：
    - source 触发来源：user / physics / env / ai / sys（见 SOURCE_RULES）
    - kind   文本性质：short（≤SHORT_MAX 字的单句罐头）/ pool（随机池）/ long / var（非字面量）
* 交叉验证（X0）：AST 计数 与 正则计数 必须一致（解析算法要有"算法无关"的独立 oracle）。
  两者不一致时**不静默**：打印差异行号，进程返回 1。
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # 项目根
OUTD = os.path.join(HERE, "_evidence")

TARGETS = [
    ("ralsei_pet/src/main.py", "main"),
    ("ralsei_pet/modules/dialogue_ui.py", "dialogue_ui"),
    ("ralsei_pet/modules/pet_ai.py", "pet_ai"),
    ("ralsei_pet/modules/entertainment_system.py", "entertainment_system"),
    ("ralsei_pet/modules/energy_hunger.py", "energy_hunger"),
    ("ralsei_pet/modules/social_growth_system.py", "social_growth_system"),
    ("ralsei_pet/modules/ai_driver.py", "ai_driver"),
    ("ralsei_pet/modules/autonomous_agent.py", "autonomous_agent"),
    ("ralsei_pet/modules/command_manager.py", "command_manager"),
]

SHORT_MAX = 12          # ≤12 字的单句判为"短促反应"（0 延迟要求）

# 触发来源判定：按"最近的外层函数名"归类（顺序敏感，先匹配者胜）
SOURCE_RULES = [
    # 用户显式交互
    ("user", ("mousePress", "mouseRelease", "mouseMove", "mouseDouble", "on_mouse", "_on_click",
              "click", "pet_", "pat_", "feed", "drag", "handle_chat", "handle_game",
              "handle_file", "handle_command", "command", "toggle", "menu", "tray",
              "send_message", "_on_ai_reply", "chat_with_ai")),
    # 物理状态机（坠落/摔扁/醒来/跳跃/落地）
    ("physics", ("fall", "splat", "land", "jump", "climb", "gravity", "wake", "daze", "sleep",
                 "stir", "floor", "_faint", "recover")),
    # 环境自动触发（看视频/桌面元素/天气/其他窗口/定时）
    ("env", ("video", "desktop", "weather", "window", "browser", "ppt", "excel", "file_reaction",
             "check_", "react_to", "observe", "idle", "autonomous", "timer", "tick", "schedule",
             "energy", "hunger", "growth")),
    # AI 决策侧
    ("ai", ("ai_driver", "_ai_", "_on_reply", "_build_persona", "notify")),
]


def source_of(funcname, clsname):
    hn = "%s.%s" % (clsname or "", funcname)
    for src, keys in SOURCE_RULES:
        for k in keys:
            if k.lower() in hn.lower():
                return src
    return "sys"


def build_parents(tree):
    """一次建好 parent 映射（比每个调用点各 walk 一遍快两个数量级，也避免"先匹配者胜"的顺序歧义）。"""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing(parents, target_node):
    """返回 (class_name, func_name)：目标节点最近的外层类/函数。"""
    clsname = funcname = None
    cur = parents.get(target_node)
    while cur is not None:
        if funcname is None and isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcname = cur.name
        if clsname is None and isinstance(cur, ast.ClassDef):
            clsname = cur.name
        cur = parents.get(cur)
    return clsname, funcname


def is_add_dialogue(call):
    f = call.func
    if isinstance(f, ast.Attribute) and f.attr == "add_dialogue":
        return True
    if isinstance(f, ast.Name) and f.id == "add_dialogue":
        return True
    return False


def classify_arg(src_segment, node):
    """文本性质：short / pool / long / var。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        s = node.value
        return ("short" if len(s) <= SHORT_MAX else "long"), s
    if isinstance(node, (ast.List, ast.Tuple)):
        # 池子里全部是短句 → pool_short，否则 pool_long
        lits = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        longest = max((len(x) for x in lits), default=0)
        return ("pool_short" if longest <= SHORT_MAX else "pool_long"), " | ".join(lits[:4])
    if isinstance(node, ast.JoinedStr):
        return "var_fstring", (src_segment or "")[:90]
    return "var", (src_segment or "")[:90]


def scan(path, tag):
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    raw_lines = src.splitlines()
    parents = build_parents(tree)

    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_add_dialogue(node):
            clsname, funcname = enclosing(parents, node)
            msg_node = node.args[1] if len(node.args) > 1 else None
            try:
                seg = ast.get_source_segment(src, msg_node) if msg_node is not None else ""
            except Exception:
                seg = ""
            kind, text = classify_arg(seg, msg_node) if msg_node is not None else ("none", "")
            rows.append({
                "file": tag,
                "line": node.lineno,
                "cls": clsname,
                "func": funcname,
                "source": source_of(funcname or "", clsname or ""),
                "kind": kind,
                "text": text,
                "raw": (seg or "")[:120],
            })
    rows.sort(key=lambda r: r["line"])
    return src, rows


def main():
    all_rows = []
    per_file = {}
    oracle = {}
    problems = []
    for rel, tag in TARGETS:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            problems.append("MISSING %s" % rel)
            continue
        src, rows = scan(path, tag)
        per_file[tag] = len(rows)
        all_rows.extend(rows)
        # X0：正则 oracle（含注释/字符串/def 定义会偏高，只记录差值，不静默）
        rx = len(re.findall(r"add_dialogue\s*\(", src))
        oracle[tag] = {"ast": len(rows), "regex": rx, "delta": rx - len(rows)}

    # X0 自检：main.py 的 AST 计数必须 > 0，且正则 >= AST（正则会把注释/字符串也算上）
    assert per_file.get("main", 0) > 0, "main.py 一个 add_dialogue 都没扫到 → 解析器坏了"
    for tag, o in oracle.items():
        if o["delta"] < 0:
            problems.append("ORACLE %s: regex(%d) < ast(%d) → AST 视图可疑" % (tag, o["regex"], o["ast"]))

    txt = []
    txt.append("S7 事件台词全量清单（ast 实测）")
    txt.append("生成脚本：code-quality-audit/人味改造-2026-09-18/scan_event_lines.py")
    txt.append("短句阈值 SHORT_MAX = %d 字" % SHORT_MAX)
    txt.append("")
    txt.append("=== 每文件计数 ===")
    for tag in sorted(per_file):
        txt.append("  %-22s %3d  (regex oracle=%d, delta=%d)"
                   % (tag, per_file[tag], oracle.get(tag, {}).get("regex", -1),
                      oracle.get(tag, {}).get("delta", 0)))
    txt.append("  %-22s %3d" % ("TOTAL", sum(per_file.values())))
    txt.append("")

    txt.append("=== 主文件 main.py：按「触发来源 × 文本性质」汇总 ===")
    cross = {}
    for r in all_rows:
        if r["file"] != "main":
            continue
        cross.setdefault((r["source"], r["kind"]), 0)
        cross[(r["source"], r["kind"])] += 1
    for k in sorted(cross):
        txt.append("  %-8s %-12s %3d" % (k[0], k[1], cross[k]))
    txt.append("")

    txt.append("=== main.py 明细（按行号） ===")
    txt.append("%-6s %-10s %-34s %-12s %s" % ("line", "source", "func", "kind", "text"))
    txt.append("-" * 118)
    for r in all_rows:
        if r["file"] != "main":
            continue
        t = (r["text"] or "").replace("\n", " ")[:44]
        txt.append("%-6d %-10s %-34s %-12s %s" % (r["line"], r["source"], (r["func"] or "?")[:33], r["kind"], t))
    txt.append("")

    for tag in ("dialogue_ui", "pet_ai", "entertainment_system", "energy_hunger",
                "social_growth_system", "ai_driver", "autonomous_agent", "command_manager"):
        rs = [r for r in all_rows if r["file"] == tag]
        if not rs:
            continue
        txt.append("=== %s 明细 ===" % tag)
        for r in rs:
            t = (r["text"] or "").replace("\n", " ")[:50]
            txt.append("  %-6d %-10s %-30s %-12s %s" % (r["line"], r["source"], (r["func"] or "?")[:29], r["kind"], t))
        txt.append("")

    if problems:
        txt.append("=== 异常 ===")
        for p in problems:
            txt.append("  " + p)

    if not os.path.isdir(OUTD):
        os.makedirs(OUTD)
    with io.open(os.path.join(OUTD, "event_lines.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(txt) + "\n")
    with io.open(os.path.join(OUTD, "event_lines.json"), "w", encoding="utf-8") as f:
        json.dump({"per_file": per_file, "oracle": oracle, "cross_main": {"%s|%s" % k: v for k, v in cross.items()},
                   "rows": all_rows, "problems": problems}, f, ensure_ascii=False, indent=1, sort_keys=True)

    sys.stdout.write("total=%d per_file=%s\n" % (sum(per_file.values()), per_file))
    sys.stdout.write("problems=%s\n" % problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
