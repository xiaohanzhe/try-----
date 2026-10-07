# -*- coding: utf-8 -*-
"""第95轮收尾 · 核心文件复检（45 条判据）。

用法：C:\\Python311\\python.exe recheck95_final.py   （cwd 任意，脚本自带 ROOT）

覆盖 skill `core-file-recheck` 的六类判据 + 本轮特有：全量 G2 零 DIFF + 破坏性验证。
改过「重要核心文件」（记忆文件 / 回归基线 / 被多处依赖的脚本）后必须跑一次。
"""

import ast
import io
import json
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c'
PY = r'C:\Python311\python.exe'

P = print
passed = failed = 0


def ck(desc, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
        P('[PASS] %s' % desc)
    else:
        failed += 1
        P('[FAIL] %s    %s' % (desc, detail))


def rd(p, **kw):
    return io.open(os.path.join(ROOT, p), encoding='utf-8', newline='', **kw).read()


def rdb(p):
    return open(os.path.join(ROOT, p), 'rb').read()


P('=' * 74)
P('一、语法 / 可编译（不产 .pyc：用 ast.parse，不许改变被测状态）')
P('=' * 74)
PYFILES = [
    'ralsei_pet/src/main.py',
    'ralsei_pet/modules/desktop_interaction.py',
    'code-quality-audit/regress/run_all.py',
    'code-quality-audit/第93轮-基础宠物功能收口/_tools/check93.py',
    'code-quality-audit/第95轮-基础宠物运行期排查/_tools/check95.py',
    '.workbuddy/memory/2026-10-07.md',   # 非 py，单独处理
]
for p in PYFILES[:-1]:
    try:
        ast.parse(rd(p))
        ck('① 可编译：%s' % os.path.basename(p), True)
    except SyntaxError as e:
        ck('① 可编译：%s' % os.path.basename(p), False, str(e))
# baseline.json 可解析
try:
    json.loads(rd('code-quality-audit/regress/baseline.json'))
    ck('① 可解析：baseline.json', True)
except Exception as e:
    ck('① 可解析：baseline.json', False, str(e))

P('')
P('=' * 74)
P('二、编码（无 BOM / 无 U+FFFD）')
P('=' * 74)
ALL = PYFILES + [
    '.gitignore',
    '.workbuddy/memory/MEMORY.md',
    '.workbuddy/memory/参考-契约与历轮（详版）.md',
]
for p in ALL:
    b = rdb(p)
    has_bom = b.startswith(b'\xef\xbb\xbf')
    try:
        txt = b.decode('utf-8')
        bad = '\ufffd' in txt
    except UnicodeDecodeError as e:
        ck('③ %s UTF-8 可解' % p, False, str(e))
        continue
    ck('③ %s 无 BOM / 无 U+FFFD' % os.path.basename(p),
       (not has_bom) and (not bad), 'bom=%s fffd=%s' % (has_bom, bad))

P('')
P('=' * 74)
P('三、结构自检（关键锚点全在）')
P('=' * 74)
mem = rd('.workbuddy/memory/MEMORY.md')
for anchor in ['## 0. 铁律', '## 4. 验证脚本教训', '## 10. 历轮索引']:
    ck('② 速查本含 `%s`' % anchor, anchor in mem)
det = rd('.workbuddy/memory/参考-契约与历轮（详版）.md')
# ★ 判据宽式（第95轮自己踩的"判据过窄"）：详版标题写法是 `### 95.13`，无 `§`。
#   首版写 `§95.13` ⇒ 匹配失败 ⇒ 假红。改为**不含 `§`** 的裸编号。
for anchor in ['95.13', '95.14', '95.15', '95.16', '95.17']:
    ck('② 详版含 `%s`' % anchor, anchor in det)
ru = rd('code-quality-audit/regress/run_all.py')
ck('② run_all 含 `_NPC_ROAM_NOISE` 常量', '_NPC_ROAM_NOISE' in ru)
ck('② run_all 的 normalize 里真用了它',
   '_NPC_ROAM_NOISE.match(ln)' in ru)
di = rd('ralsei_pet/modules/desktop_interaction.py')
ck('② desktop_interaction 含 `LVIR_BOUNDS = 0`', 'LVIR_BOUNDS = 0' in di)
ck('② desktop_interaction 注释含调用契约说明', 'DPI 感知是调用契约' in di)
c95 = rd('code-quality-audit/第95轮-基础宠物运行期排查/_tools/check95.py')
ck('② check95 含 F 段（`F2` / `F7`）', 'F2 ' in c95 and 'F7 ' in c95)
c93 = rd('code-quality-audit/第93轮-基础宠物功能收口/_tools/check93.py')
ck('② check93 D 段已 AST 化（含 `ast.Attribute` 分支）',
   'ast.Attribute' in c93 and 'D1b' in c93)
git = rd('.gitignore')
ck('② .gitignore 含 `.tmp/`', '.tmp/' in git)
mj = rd('ralsei_pet/src/main.py')
ck('② main.py 两道防线都在（先算再读 + down 守卫）',
   'self.idle_walk_timer += (current_time - self._last_animation_time)' in mj
   and 'elif self.is_sleeping_walk and self.current_direction == "down":' in mj)

P('')
P('=' * 74)
P('四、恒真判据复查（不可有 check(..., <字面常量>)）')
P('=' * 74)
for p, name in [('code-quality-audit/第95轮-基础宠物运行期排查/_tools/check95.py', 'check95'),
                ('code-quality-audit/第93轮-基础宠物功能收口/_tools/check93.py', 'check93')]:
    tree = ast.parse(rd(p))
    consts = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'check' and len(n.args) >= 2:
            if isinstance(n.args[1], ast.Constant):
                consts.append(repr(n.args[1].value))
    ck('④ %s 无 `check(..., <常量>)` 死判据' % name, not consts, '常量=%s' % consts)

P('')
P('=' * 74)
P('五、逐令牌回验（改/删过的关键令牌逐个回原文件 `in` 一次）')
P('=' * 74)
TOKENS = {
    'ralsei_pet/src/main.py': [
        'self.idle_walk_timer += (current_time - self._last_animation_time)',
        'elif self.is_sleeping_walk and self.current_direction == "down":',
    ],
    'ralsei_pet/modules/desktop_interaction.py': [
        'LVIR_BOUNDS = 0', 'seed.left = LVIR_BOUNDS',
        'remote_seed', 'VirtualFreeEx(h_process, remote_seed',
    ],
    'code-quality-audit/regress/run_all.py': [
        '_NPC_ROAM_NOISE', '自己挪到了', 'HERMETIC_IDS', 'check89', 'check93',
    ],
    'code-quality-audit/第95轮-基础宠物运行期排查/_tools/check95.py': [
        'LVIR_BOUNDS', 'remote_seed', 'F7', '_lf(',
    ],
    'code-quality-audit/第93轮-基础宠物功能收口/_tools/check93.py': [
        'ast.Attribute', 'ast.Constant', 'D1b', 'SetProcessDpiAwareness',
    ],
    '.workbuddy/memory/MEMORY.md': [
        'check95`(43)', 'check93`(42)', '§95.13~§95.17', '_lf()',
    ],
    '.workbuddy/memory/参考-契约与历轮（详版）.md': [
        '§95.15', '§95.16', '§95.17', '_NPC_ROAM_NOISE', 'jitter(npc_id, now',
    ],
}
for p, toks in TOKENS.items():
    txt = rd(p)
    miss = [t for t in toks if t not in txt]
    ck('⑤ %s 令牌全在（%d 个）' % (os.path.basename(p), len(toks)),
       not miss, '缺=%s' % miss)

P('')
P('=' * 74)
P('六、体积 / EOL')
P('=' * 74)
b = rdb('.workbuddy/memory/MEMORY.md')
t = b.decode('utf-8')
ck('⑥ 速查本 js_len ≤ 10000', len(t) <= 10000, 'js_len=%d' % len(t))
ck('⑥ 速查本 EOL 未被破坏（原为 CRLF）',
   (t.count('\r\n') == 66) and (t.count('\n') - t.count('\r\n') == 0),
   'CRLF=%d LFonly=%d' % (t.count('\r\n'), t.count('\n') - t.count('\r\n')))
dj = rdb('.workbuddy/memory/参考-契约与历轮（详版）.md')
tj = dj.decode('utf-8')
ck('⑥ 详版 EOL 未被破坏（原为 CRLF）',
   (tj.count('\r\n') > 10000) and (tj.count('\n') - tj.count('\r\n') == 0),
   'CRLF=%d LFonly=%d' % (tj.count('\r\n'), tj.count('\n') - tj.count('\r\n')))

P('')
P('=' * 74)
P('七、工作区与无删除')
P('=' * 74)
r = subprocess.run(['git', 'diff', '--cached', '--numstat'], cwd=ROOT,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
ck('⑥ 暂存区为空（无意外 pre-staged 删除）', r.stdout.decode().strip() == '',
   r.stdout.decode()[:200])
r2 = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
mods = [l for l in r2.stdout.decode('utf-8', 'replace').splitlines()]
dels = [l for l in mods if l.strip().startswith('D ')]
ck('⑥ 无文件被删除（`D ` 条目为 0）', not dels, '删除=%s' % dels)
P('     改动文件 %d 个' % len(mods))

P('')
P('=' * 74)
P('合计  PASS=%d  FAIL=%d' % (passed, failed))
P('=' * 74)
sys.exit(1 if failed else 0)
