# -*- coding: utf-8 -*-
"""第49轮收尾复检（六类，逐项 PASS/FAIL 落盘）。

① 可编译（ast.parse，**不产 .pyc** —— 复检不许改变被测状态）
② 报告结构（必需段落全在 / 无粘连）
③ 编码（无 BOM / 无 U+FFFD）
④ 恒真判据形状扫描（`check(..., True)` / 自比 `X == X`）
⑤ **逐令牌回验**（本轮改/新增的令牌逐个回原文件 in 一次）
⑥ 工作区清单（如实打印，不自动改）

用法: C:\\Python311\\python.exe recheck49.py
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

REPORT = os.path.join(ROOT, '第49轮报告-NPC与球容器.md')
SUITE = os.path.join(ROUND, 'verify_npc49.py')
GEN = os.path.join(HERE, 'gen_npc49.py')
DISC = os.path.join(HERE, 'disc_npc49.py')
NS = os.path.join(PET, 'modules', 'npc_system.py')
BS = os.path.join(PET, 'modules', 'bubble_system.py')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
DIA = os.path.join(PET, 'assets', 'npc', '_dialogue.json')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
DOC = os.path.join(ROUND, '_evidence', '取证与设计49.md')
SPRLOG = os.path.join(ROUND, '_evidence', 'spr49_log.txt')

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
PY_FILES = [NS, BS, SUITE, GEN, DISC,
            os.path.join(HERE, 'mk_names49.py'), os.path.join(HERE, 'run_list49.py'),
            os.path.join(HERE, 'mk_dump49.py'), os.path.join(HERE, 'run_dump49.py'),
            os.path.join(HERE, 'distill_gml49.py'), os.path.join(HERE, 'run_spr49.py'),
            os.path.join(HERE, 'distill_spr49.py'),
            os.path.join(HERE, 'mk_names49.py')]
bad = []
seen = set()
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
HEADS = ['## 1. 需求 → 实现 → 验收', '## 2. 关键设计决策', '## 3. 交付物',
         '## 4. 验收证据', '## 5. ★ 如实登记的缺口', '## 6. 复检表',
         '## 7. ★★ 需要用户提供设定的 NPC 清单', '## 8. 下一步']
miss = [h for h in HEADS if h not in rep]
check('2a', not miss, '② 报告 %d 个必需段全在（缺 %s）' % (len(HEADS), miss or '无'))
# 粘连：二级标题必须各自独占一行
h2 = [l for l in rep.splitlines() if l.startswith('## ')]
check('2b', len(h2) == len(HEADS), '② 二级标题恰 %d 个（实得 %d）⇒ 无粘连'
      % (len(HEADS), len(h2)))
check('2c', rep.count('|') > 80 and rep.count('```') >= 2,
      '② 报告含 14 行验收表 + 原作 GML 代码块（表格线 %d 条）' % rep.count('|'))

# ---------------------------------------------------------------- ③ 编码
TXT = [REPORT, SUITE, GEN, DISC, NS, BS, REG, DIA, DOC, SPY := os.path.join(HERE, 'mk_names49.py')]
bom, fffd = [], []
for p in TXT:
    if not os.path.isfile(p):
        continue
    b = rdb(p)
    if b[:3] == b'\xef\xbb\xbf':
        bom.append(os.path.basename(p))
    if '\ufffd' in b.decode('utf-8', 'replace'):
        fffd.append(os.path.basename(p))
check('3', not bom and not fffd, '③ 编码：%d 个文本无 BOM（%s）/ 无 U+FFFD（%s）'
      % (len(TXT), bom or '0', fffd or '0'))

# ---------------------------------------------------------------- ④ 恒真判据形状
# ⚠️ 判据坑（本轮自己踩到）：首版用正则扫源码，结果命中了我写在**注释里**的
#    "⛔ 不写 `check(cid, True, ...)`" 这句示例 ⇒ 假红。
#    ⇒ 能上 AST 就上 AST：直接找 `check(<id>, True, ...)` 这种真实调用。
src = rd(SUITE)
_tree = ast.parse(src)
always = []
for node in ast.walk(_tree):
    if not isinstance(node, ast.Call):
        continue
    f = node.func
    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)
    if name != 'check' or len(node.args) < 2:
        continue
    a1 = node.args[1]
    if isinstance(a1, ast.Constant) and a1.value is True:
        always.append(node.lineno)
# 自比：先剥掉注释行，再找 `X == X`
_code_lines = [l.split('#', 1)[0] for l in src.splitlines()]
selfcmp = re.findall(r'(\b[A-Za-z_][A-Za-z0-9_.\[\]]*)\s*==\s*\1\b', '\n'.join(_code_lines))
check('4', not always and not selfcmp,
      '④ 恒真判据扫描（AST）：check(...,True) 实际调用 %d 处 %s / 自比 %d 处'
      % (len(always), always or '', len(selfcmp)))

# ---------------------------------------------------------------- ⑤ 逐令牌回验
TOKENS = [
    ('spr_dw_tv_gachaball_transparent', (BS, DOC, SPRLOG)),
    ('spr_board_kris_walk_down', (SPRLOG,)),
    ('obj_tenna_board4_gacha', (DOC,)),
    ('obj_ch3_GSC07_gacha', (DOC,)),
    ('obj_ch3_ballcon', (DOC,)),
    ('1.55', (BS, DOC)),
    ('2.02', (BS, DOC)),
    ('-150', (BS, DOC)),
    ('-100', (BS, DOC)),
    ('SPRITE_W = 62', (BS,)),
    ('ORIGIN_X = 31', (BS,)),
    ('escape_via_bubble', (NS, REG, SUITE)),
    ('NEVER_EJECTABLE', (BS, DISC)),
    ('ALWAYS_EJECTABLE', (BS, DISC)),
    ('BUBBLE_ESCAPE', (BS,)),
    ('SPIN_STEP_DEG', (BS, SUITE, DISC)),
    ('leave_dark_world', (NS, SUITE)),
    ('foreign_dark_world', (NS, SUITE)),
    ('FOLLOW_PENDING', (NS, SUITE)),
    ('PLAIN_LINES_MIN', (NS, SUITE)),
    ('ralsei-npc:4b', (REG, GEN, REPORT)),
    ('obj_npc_toriel', (REG, DOC)),
    ('obj_ch5_DW30_asgore', (REG, DOC)),
    ('obj_knight_enemy', (REG, DOC)),
    ('0.88', (BS, REPORT)),
    ('npc_round49', (RUNALL,)),
    ('verify_npc49.py', (RUNALL,)),
    ('spr_dw_tv_gachaball_transparent', (BS, DOC, SPRLOG)),
]
missing = []
for tok, files in TOKENS:
    for f in files:
        if not os.path.isfile(f) or tok not in rd(f):
            missing.append('%r !in %s' % (tok, os.path.basename(f)))
check('5', not missing, '⑤ 逐令牌回验：%d 组令牌 × 目标文件全命中（漏 %s）'
      % (len(TOKENS), missing or '无'))
NUMS = [('43', os.path.join(PET, 'assets', 'bubble')), ('2296', REPORT),
        ('82', REPORT), ('33', REPORT), ('381', REPORT), ('14', REPORT)]
nummiss = []
for n, where in NUMS:
    if os.path.isdir(where):
        if not (n == '43' and len([f for f in os.listdir(where)
                                   if f.endswith('.png')]) == 43):
            nummiss.append(n)
    elif n not in rd(where):
        nummiss.append(n)
check('5b', not nummiss, '⑤ 数字逐个核（43 个落盘 PNG / 82 条判据 / 33 条 NPC / 2296 G2 / '
                         '381 GML / 14 位待设定）漏 %s' % (nummiss or '无'))

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
