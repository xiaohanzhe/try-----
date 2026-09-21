# -*- coding: utf-8 -*-
"""第26轮 P1 处置：删除 main.py 中的零引用死代码。

G1 证据（code-quality-audit/第二十六轮/_evidence/G1_zero_refs.txt）：
  下列 8 个方法**有定义 + 全项目 AST 零引用**，且无字符串/动态派发入口
  （已全仓库 grep `getattr(self, '<name>')` → 无命中）。

删除清单：
  A. follow_file               (L8232-8236)  —— 无拖拽入口，写入的 dragged_file /
                                                is_following_dragged_file 无生产者
  B. react_to_file_deletion    (L8238-8241)  —— delete_file(L8558-8580) 已承担同一职责
  C. check_video_windows       (L8243-8257)  —— W1-4 VideoController 已接管
  D. check_game_windows        (L8259-8273)  —— W1-3 GamesController 已接管
  E. react_to_game             (L8275-8306)  —— 同上
  F. watch_video               (L8308-8332)  —— 同上
  G. react_to_video_content    (L8334-8350)  —— 零引用，且其情绪事件 saw_deltarune_video
                                                在 emotion_system 无分支（静默 no-op）
  H. check_dragged_file        (L8588-8591)  —— 方法体仅 pass

区间 A–G 恰为连续块 L8232–L8350（块间仅隔空行），故按**单区间**删除，
两头各留一个空行 → 折叠为一个空行，类体排版保持 `\\n\\n` 惯例。
H 单独成块删除（连带其后空行 L8592）。

保留（不在本脚本范围）：
  · react_to_file_emotionally (L8205) —— 归 H4「文件反应」专项
  · delete_file / rename_file / open_file / open_folder / is_own_code /
    react_to_vs_code_code / _recover_from_sadness —— 活链路或活链路上游

纪律：newline='' 保 EOL；首行文本唯一性断言；compileall；AST 反查；
      反向归一证明（删→按原序插回 → 逐字节等于原文）。
"""
import ast
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "ralsei_pet", "src", "main.py")
EVID = os.path.join(HERE, "_evidence")

# 每个被删方法的名字（用于 AST 反查与逐项记录）
METHODS = [
    ("follow_file", 8232, 8236),
    ("react_to_file_deletion", 8238, 8241),
    ("check_video_windows", 8243, 8257),
    ("check_game_windows", 8259, 8273),
    ("react_to_game", 8275, 8306),
    ("watch_video", 8308, 8332),
    ("react_to_video_content", 8334, 8350),
    ("check_dragged_file", 8588, 8591),
]

# 实际删除区间（1-based 闭区间）：先删靠后的，避免行号漂移
SPANS = [
    (8588, 8592, "check_dragged_file"),        # 含其后空行
    (8232, 8350, "follow_file..react_to_video_content (连续死代码块)"),
]


def md5_of(b):
    return hashlib.md5(b).hexdigest()


with io.open(TARGET, "rb") as f:
    raw_before = f.read()
md5_before = md5_of(raw_before)

with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
    text = f.read()

eol_crlf = text.count("\r\n")
eol_lone_lf = text.count("\n") - eol_crlf
lines = text.split("\n")

log = []
log.append("第26轮 P1 死代码处置 — 行级手术记录")
log.append("目标：%s" % os.path.relpath(TARGET, ROOT))
log.append("改前 md5：%s   字节 %d   行数 %d" % (md5_before, len(raw_before), len(lines)))
log.append("EOL：CRLF=%d  lone-LF=%d" % (eol_crlf, eol_lone_lf))
log.append("")

# ---- 1. 逐方法首行断言（文本 + 全文件唯一） ----
log.append("### 逐方法首行断言")
ok_all = True
for name, a, b in METHODS:
    first = lines[a - 1]
    exp_prefix = "    def %s(" % name
    if not first.startswith(exp_prefix):
        ok_all = False
        log.append("  !! [%s] L%d 首行不匹配: %r" % (name, a, first))
        continue
    occ = [i + 1 for i, ln in enumerate(lines) if ln.startswith(exp_prefix)]
    log.append("  %-24s L%d–L%d  首行唯一命中=%s  %r" % (
        name, a, b, occ, first.strip()))
    if len(occ) != 1:
        ok_all = False
        log.append("     !! 首行文本出现 %d 次：%s" % (len(occ), occ))
if not ok_all:
    raise SystemExit("锚校验失败，未做任何改动（见日志）")
log.append("  → 全部通过（8/8）")
log.append("")

# ---- 2. 删除前先记录被删文本（用于反向归一证明） ----
removed = []
for a, b, label in sorted(SPANS, key=lambda t: -t[0]):
    removed.append((a, b, "\n".join(lines[a - 1:b])))
removed.sort(key=lambda t: t[0])

# ---- 3. 执行删除（从后往前） ----
new_lines = list(lines)
for a, b, _label in sorted(SPANS, key=lambda t: -t[0]):
    del new_lines[a - 1:b]
text_after = "\n".join(new_lines)

# ---- 4. 反向归一证明：按原行序插回 → 逐字符等于原文 ----
norm = list(new_lines)
for a, b, content in sorted(removed, key=lambda t: -t[0]):
    prior = sum(bb - aa + 1 for (aa, bb, _c) in removed if aa < a)
    idx = (a - 1) - prior
    norm[idx:idx] = content.split("\n")
if "\n".join(norm) != "\n".join(lines):
    raise SystemExit("反向归一失败：插回后 != 原文")
log.append("### 反向归一证明：通过（删→按原序插回 == 原文，逐字符相等）")
log.append("")

# ---- 5. 写盘 ----
with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
    f.write(text_after)
with io.open(TARGET, "rb") as f:
    raw_after = f.read()
md5_after = md5_of(raw_after)

# ---- 6. 语法/编译校验 ----
try:
    ast.parse(text_after)
    log.append("### AST 解析：OK")
except SyntaxError as e:
    log.append("### AST 解析：失败 %s" % e)
    raise
rc = subprocess.call([sys.executable, "-m", "compileall", "-q",
                      os.path.join(ROOT, "ralsei_pet", "src", "main.py")])
log.append("### compileall 退出码：%d" % rc)

# ---- 7. AST 反查：名字是否仍定义于 main.py ----
tree = ast.parse(text_after)
defined = set()
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        defined.add(node.name)
still = [n for n, _a, _b in METHODS if n in defined]
log.append("### AST 反查（应全部不在 main.py）")
log.append("  仍在：%s" % (", ".join(still) if still else "（无）✓"))

# 反向控制：保留项必须仍在
KEEP = ["react_to_file_emotionally", "delete_file", "rename_file",
        "open_file", "open_folder", "is_own_code", "react_to_vs_code_code",
        "_recover_from_sadness"]
missing_keep = [n for n in KEEP if n not in defined]
log.append("### 反向控制（保留项应仍在）")
log.append("  缺失：%s" % (", ".join(missing_keep) if missing_keep else "（无）✓"))
log.append("")

# ---- 8. 结果 ----
log.append("### 结果")
log.append("  改后 md5：%s   字节 %d   (Δ=%+d)" % (
    md5_after, len(raw_after), len(raw_after) - len(raw_before)))
log.append("  删除行数：%d" % sum(b - a + 1 for a, b, _l in SPANS))
log.append("  改后行数：%d" % (text_after.count("\n") + 1))
log.append("  文件尾字节：%r" % raw_after[-1:])

if not os.path.isdir(EVID):
    os.makedirs(EVID)
with io.open(os.path.join(EVID, "r26_deadcode_surgery.txt"), "w",
             encoding="utf-8", newline="\n") as f:
    f.write("\n".join(log) + "\n")

sys.stdout.write("OK %s -> %s  bytes %d -> %d  compileall=%d\n" % (
    md5_before[:8], md5_after[:8], len(raw_before), len(raw_after), rc))
