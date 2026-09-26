# -*- coding: utf-8 -*-
"""第50轮收尾复检（六类，逐项 PASS/FAIL 落盘）。

① 可编译（ast.parse，**不产 .pyc** —— 复检不许改变被测状态）
② 报告结构（必需段落全在 / 无粘连）
③ 编码（无 BOM / 无 U+FFFD / 纯 LF）
④ 恒真判据形状扫描（`check(..., True)` / 自比 `X == X`）
⑤ **逐令牌回验**（本轮改/新增的令牌逐个回原文件 in 一次）
⑥ 工作区清单（如实打印，不自动改）

用法: C:\\Python311\\python.exe recheck50.py
"""
import ast
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')

REPORT = os.path.join(ROUND, '第50轮报告-球容器接线.md')
SUITE = os.path.join(ROUND, 'verify_wire50.py')
PROBE = os.path.join(HERE, 'probe_wire50.py')
DISC = os.path.join(HERE, 'disc_wire50.py')
MODS = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
SR = os.path.join(MODS, 'scene_render.py')
SCV = os.path.join(MODS, 'scene_canvas.py')
BS = os.path.join(MODS, 'bubble_system.py')
NS = os.path.join(MODS, 'npc_system.py')
CTL = os.path.join(MODS, 'scene_controller.py')
MAIN = os.path.join(SRC, 'main.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
V49 = os.path.join(ROOT, 'code-quality-audit', '第49轮-NPC与球容器', 'verify_npc49.py')
V44C = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', 'verify_canvas_round44.py')
V44R = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', 'verify_routes_order44.py')
V45 = os.path.join(ROOT, 'code-quality-audit', '第45轮-场景自主寻路', 'verify_pathfind45.py')
MEM = os.path.join(ROOT, '.workbuddy', 'memory')
MEMQ = os.path.join(MEM, 'MEMORY.md')
MEMD = os.path.join(MEM, '参考-契约与历轮（详版）.md')
MEML = os.path.join(MEM, '2026-09-26.md')

PASS, FAIL = [], []


def check(cid, ok, msg):
    print('%s %-4s %s' % ('[PASS]' if ok else '[FAIL]', cid, msg))
    (PASS if ok else FAIL).append(cid)


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def rdb(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


# ---------------------------------------------------------------- ① 可编译
PY_FILES = [SR, SCV, BS, NS, CTL, MAIN, SUITE, PROBE, DISC, V49, V44C, V44R, V45]
bad, seen = [], set()
for p in PY_FILES:
    if p in seen or not os.path.isfile(p):
        continue
    seen.add(p)
    try:
        ast.parse(rd(p))
    except SyntaxError as e:
        bad.append('%s: %s' % (os.path.basename(p), e))
check('1', not bad, '① 可编译：%d 个 .py 全部 ast.parse 通过（失败 %s）' % (len(seen), bad or '无'))

# ---------------------------------------------------------------- ② 报告结构
rep = rd(REPORT) if os.path.isfile(REPORT) else ''
HEADS = ['## 1. 用户口径（逐字，第16项）', '## 2. 结论先行', '## 3. 改动清单',
         '## 4. 关键取证（本轮踩到的真实事实）', '## 5. 回归结果',
         '## 6. 教训（可复用）', '## 7. 缺口 / 未接线（如实登记）', '## 8. 下一步']
miss = [h for h in HEADS if h not in rep]
check('2a', not miss, '② 报告 %d 个必需段全在（缺 %s）' % (len(HEADS), miss or '无'))
h2 = [l for l in rep.splitlines() if l.startswith('## ')]
check('2b', len(h2) == len(HEADS), '② 二级标题恰 %d 个（实得 %d）⇒ 无粘连' % (len(HEADS), len(h2)))
# ⚠️ 判据坑（复检脚本自身，第二次踩）：`rep.count('## ')` **不是**二级标题数 ——
#   `### xxx` 里含 `## ` 子串 ⇒ 15 而非 8，与 2b（`startswith('## ')`）自相矛盾。
#   ⇒ 标题数归 2b 管，2c 只断「表格线 + 分节线」。
check('2c', rep.count('|') > 40 and rep.count('\n---') >= 5,
      '② 报告含对比表（表格线 %d 条）+ 分节线 %d 条'
      % (rep.count('|'), rep.count('\n---')))

# ---------------------------------------------------------------- ③ 编码
TXT = [REPORT, SUITE, PROBE, DISC, SR, SCV, BS, NS, CTL, MAIN,
       V49, V44C, V44R, V45, MEMQ, MEMD, MEML]
bom, fffd, crlf = [], [], []
for p in TXT:
    if not os.path.isfile(p):
        continue
    b = rdb(p)
    if b[:3] == b'\xef\xbb\xbf':
        bom.append(os.path.basename(p))
    if '\ufffd' in b.decode('utf-8', 'replace'):
        fffd.append(os.path.basename(p))
    if b'\r\n' in b:
        crlf.append(os.path.basename(p))
check('3', not bom and not fffd and not crlf,
      '③ 编码：%d 个文本无 BOM（%s）/ 无 U+FFFD（%s）/ 纯 LF（CRLF: %s）'
      % (len(TXT), bom or '0', fffd or '0', crlf or '0'))

# ---------------------------------------------------------------- ④ 恒真判据形状
# ⚠️ 第49轮踩坑：正则扫源码会命中**注释里**的示例 ⇒ 能上 AST 就上 AST。
src = rd(SUITE)
always = []
for node in ast.walk(ast.parse(src)):
    if not isinstance(node, ast.Call):
        continue
    f = node.func
    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)
    if name != 'check' or len(node.args) < 2:
        continue
    a1 = node.args[1]
    if isinstance(a1, ast.Constant) and a1.value is True:
        always.append(node.lineno)
# ⚠️ 判据坑（本轮踩到）：**正则**版自比扫描（`(\bident\b)\s*==\s*\1`）会被
#   `node.name == name` 这种**属性访问**骗到（`.` 处也是词边界 ⇒ 匹配成 `name == name`）
#   ⇒ 3 处假红。正确做法 = **结构比较**：`ast.Compare` 左右两边 `ast.dump` 完全相同才算自比。
selfcmp = []
for node in ast.walk(ast.parse(src)):
    if (isinstance(node, ast.Compare) and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq) and len(node.comparators) == 1
            and ast.dump(node.left) == ast.dump(node.comparators[0])):
        selfcmp.append(node.lineno)
check('4', not always and not selfcmp,
      '④ 恒真判据扫描（AST）：check(...,True) 实际调用 %d 处 %s / 结构自比 %d 处 %s'
      % (len(always), always or '', len(selfcmp), selfcmp or ''))

# ---------------------------------------------------------------- ⑤ 逐令牌回验
TOKENS = [
    ('REASON_LIGHT_NEEDS_BUBBLE', (NS, SUITE)),
    ('DARK_ONLY_IDS', (NS,)),
    ('light_needs_bubble', (NS, SUITE)),
    ('free_dark_roam', (NS, SUITE)),
    ('light_free', (NS,)),
    ('carried_in_bubble', (NS,)),
    ('grants_foreign_dark', (BS, SUITE)),
    ('SPIN_STEP_DEG', (BS, SUITE)),
    ('NEVER_EJECTABLE', (BS,)),
    ('BUBBLE_FRAME_TOP', (SR, SUITE)),
    ('BUBBLE_FRAME_BACK', (SR, SUITE)),
    ('BUBBLE_FRAME_FRONT', (SR, SUITE)),
    ('BUBBLE_PREFIX', (SR, SUITE)),
    ('BUBBLE_FIT_MARGIN', (SR,)),
    ('BUBBLE_ORIGIN', (SR,)),
    ('BUBBLE_ROLE_CHAR', (SR, SUITE)),
    ('BUBBLE_DRAW_ROLES', (SR, SUITE)),
    ('bubble_sprite_name', (SR, SUITE)),
    ('fit_scale', (SR, MAIN, SUITE)),
    ('_bubble_items', (SR,)),
    ('split_bubble_layers', (SR, MAIN, SUITE)),
    ('BubbleOverlay', (SCV, MAIN, SUITE)),
    ('WA_TransparentForMouseEvents', (SCV, SUITE)),
    ('BUBBLE_TINT_FALLBACK', (SCV, SUITE)),
    ('_paint_bubble_filter', (SCV,)),
    ('_bubble_dir', (SCV,)),
    ('bubble:', (SCV, SR, SUITE)),
    ('SCENE_LAYER_ENABLED', (MAIN, V44C, SUITE)),
    ('_active_bubbles', (MAIN, SUITE)),
    ('_update_bubble_overlay', (MAIN, SUITE)),
    ('toggle_bubble', (MAIN, SUITE)),
    ('_ensure_bubble_field', (MAIN, SUITE)),
    ('_current_world', (MAIN,)),
    ('transfer_world', (MAIN, BS, SUITE)),
    ('bubbles=bubbles', (CTL,)),
    ('bubble_round50', (RUNALL,)),
    ('verify_wire50.py', (RUNALL,)),
]
missing = []
for tok, files in TOKENS:
    for f in files:
        if not os.path.isfile(f) or tok not in rd(f):
            missing.append('%r !in %s' % (tok, os.path.basename(f)))
check('5', not missing, '⑤ 逐令牌回验：%d 组令牌 × 目标文件全命中（漏 %s）'
      % (len(TOKENS), missing or '无'))
# 关键数字逐个核（数字必须落在它该在的文件里）
NUMS = [('2369', REPORT), ('76', REPORT), ('82', REPORT), ('57', REPORT), ('35', REPORT),
        ('12', REPORT), ('47', REPORT), ('0.12', REPORT), ('60×51', REPORT),
        ('_evidence', V44R), ('rooms44', V44R)]
nummiss = []
for n, where in NUMS:
    if not os.path.isfile(where) or n not in rd(where):
        nummiss.append('%s !in %s' % (n, os.path.basename(where)))
check('5b', not nummiss, '⑤ 数字逐个核（G2 2369 / 76 判据 / 82 / 17→ ... / E-盘锁 等）漏 %s'
      % (nummiss or '无'))
# 记忆体积（真判据 = JS 字符数 ≤ 10000）
_m = rd(MEMQ)
js = len(_m.strip().encode('utf-16-le')) // 2
check('5c', js <= 10000, '⑤ 速查本 js_len = %d（限 10000，余 %d）' % (js, 10000 - js))

# ---------------------------------------------------------------- ⑥ 工作区
p = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                   capture_output=True, timeout=120)
lines = [l for l in p.stdout.decode('utf-8', 'replace').splitlines() if l.strip()]
print('      工作区 %d 项：' % len(lines))
for l in lines:
    print('        ', l)
check('6', True, '⑥ 工作区 %d 项 —— 清单已如实打印（提交后须为空）' % len(lines))

print('-' * 72)
print('复检：%d 项，FAIL=%d %s' % (len(PASS) + len(FAIL), len(FAIL), FAIL or ''))
sys.exit(1 if FAIL else 0)
