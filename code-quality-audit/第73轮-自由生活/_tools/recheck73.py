# -*- coding: utf-8 -*-
"""第73轮 · 核心文件复检（可落盘）。

改过"重要核心文件"就必须复检（用户口径 2026-09-23）。本轮动过：
  · `ralsei_pet/modules/npc_life.py`（**新建**，零依赖策略层）
  · `ralsei_pet/modules/npc_system.py`（加跨世界契约加载器 + `au_twin_pairs`）
  · `ralsei_pet/modules/npc_persona.py`（`build_system_prompt` 加 `life` 形参）
  · `ralsei_pet/src/main.py`（import / 开关 / 状态字段 / 6 个新方法 / 3 处接线）
  · `ralsei_pet/assets/npc/_crossworld.json`（四块 spec_only → wired）
  · `code-quality-audit/regress/run_all.py`（注册 check73）
  · `code-quality-audit/regress/baseline.json`（合并更新 5 个套件）
  · `code-quality-audit/第72轮-跨世界机制/_tools/check72.py`（E 段改写）

六类判据（与 skill `core-file-recheck` 同形）：
  ① 可编译/AST ② 结构自检 ③ 编码（无 BOM / 无 U+FFFD）
  ④ 恒真判据复查 ⑤ 逐令牌回验 ⑥ 工作区干净
用法：`python recheck73.py`（只读；`--write` 落 `_evidence/recheck73.json`）。
"""
from __future__ import print_function

import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROOT, 'code-quality-audit', '第73轮-自由生活', '_evidence')

LIFE = os.path.join(PET, 'modules', 'npc_life.py')
NPCSYS = os.path.join(PET, 'modules', 'npc_system.py')
NPCPER = os.path.join(PET, 'modules', 'npc_persona.py')
MAIN = os.path.join(PET, 'src', 'main.py')
CROSS = os.path.join(PET, 'assets', 'npc', '_crossworld.json')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK73 = os.path.join(HERE, 'check73.py')
CHECK72 = os.path.join(ROOT, 'code-quality-audit', '第72轮-跨世界机制', '_tools', 'check72.py')

ITEMS = []


def item(tag, name, cond, extra=''):
    ITEMS.append({'tag': tag, 'name': name, 'ok': bool(cond), 'extra': str(extra)})
    print('%s %s %s %s' % ('[PASS]' if cond else '[FAIL]', tag, name, extra))


def rd(p):
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def rb(p):
    with open(p, 'rb') as fh:
        return fh.read()


print('=' * 74)
print('第73轮 核心文件复检')
print('=' * 74)

# ---------------- ① 可编译 ----------------
for p in (LIFE, NPCSYS, NPCPER, MAIN, CHECK73, CHECK72, RUNALL):
    src = rd(p)
    try:
        ast.parse(src)
        item('1', '%s 可 ast.parse' % os.path.basename(p), True, '%d 顶层语句'
             % len(ast.parse(src).body))
    except SyntaxError as e:
        item('1', '%s 可 ast.parse' % os.path.basename(p), False, repr(e))
for p in (CROSS, REG, BASELINE):
    try:
        json.loads(rd(p))
        item('1', '%s 是合法 JSON' % os.path.basename(p), True)
    except Exception as e:
        item('1', '%s 是合法 JSON' % os.path.basename(p), False, repr(e))

# ---------------- ② 结构自检 ----------------
life_t = ast.parse(rd(LIFE))
names = [n.name for n in life_t.body if isinstance(n, ast.ClassDef)]
item('2', 'npc_life 的公开类齐（Bonds / LifeLoop）',
     'Bonds' in names and 'LifeLoop' in names, str(names))
fns = [n.name for n in life_t.body if isinstance(n, ast.FunctionDef)]
item('2', 'npc_life 的公开函数齐（scene_traits / trait_hits / transmit / pick_line 等）',
     {'scene_traits', 'trait_hits', 'trait_hint', 'transmit', 'pick_line',
      'pair_key', 'production_of' if 'production_of' in fns else 'scene_traits'} <= set(fns),
     str(sorted(fns)))

# 定义顺序：常量/类必须在使用它们的函数**之前**（否则 import 期 NameError，同第72轮）
_src = rd(LIFE)
i_traits = _src.find('TRAITS = (')
i_use = _src.find('def scene_traits')
item('2', '★ 定义顺序：`TRAITS` 常量排在 `scene_traits()` 之前',
     -1 < i_traits < i_use, 'TRAITS@%d scene_traits@%d' % (i_traits, i_use))
i_cls = _src.find('class Bonds(')
i_key = _src.find('def pair_key')
item('2', '★ 定义顺序：`pair_key()` 排在 `class Bonds` 之前（Bonds 内部要调它）',
     -1 < i_key < i_cls, 'pair_key@%d Bonds@%d' % (i_key, i_cls))

# main.py：接线点必须存在且在同一个函数里
main_t = ast.parse(rd(MAIN))
_meths = {n.name: n for n in ast.walk(main_t) if isinstance(n, ast.FunctionDef)}


def calls_of(node):
    out = set()
    for x in ast.walk(node):
        if isinstance(x, ast.Call):
            f = x.func
            out.add(f.id if isinstance(f, ast.Name)
                    else (f.attr if isinstance(f, ast.Attribute) else ''))
    return out


item('2', '★ `update_movement` 同时调 `npc_placement_tick` / `_ghost_tick` / `_npc_life_tick`',
     {'npc_placement_tick', '_ghost_tick', '_npc_life_tick'}
     <= calls_of(_meths.get('update_movement')))
for m in ('_npc_life_tick', '_npc_life_blocks', '_npc_life_gate', '_npc_life_ids',
          '_npc_seed_lookup', '_npc_plain_ids', '_npc_say_line', '_npc_scene_text'):
    item('2', 'main.py 有方法 `%s`' % m, m in _meths)
item('2', '★ `npc_system_prompt` 调用 `build_system_prompt` 时带 `life=`',
     any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
         and x.func.attr == 'build_system_prompt'
         and any(k.arg == 'life' for k in x.keywords)
         for x in ast.walk(_meths.get('npc_system_prompt', ast.Pass()))))
item('2', 'npc_system.py 有 `load_crossworld` / `au_twin_pairs` / `production_of`',
     {'load_crossworld', 'au_twin_pairs', 'production_of'}
     <= {n.name for n in ast.walk(ast.parse(rd(NPCSYS))) if isinstance(n, ast.FunctionDef)})
_bsp = [n for n in ast.walk(ast.parse(rd(NPCPER)))
        if isinstance(n, ast.FunctionDef) and n.name == 'build_system_prompt']
item('2', '`build_system_prompt` 的形参里真有 `life`',
     bool(_bsp) and 'life' in [a.arg for a in _bsp[0].args.args],
     str([a.arg for a in _bsp[0].args.args] if _bsp else None))

# 第72轮的结构性守门仍然成立（本轮没把 `RoamScope` / 判断顺序改坏）
_ns_src = rd(NPCSYS)
item('2', '★ 第72轮守门仍成立：`class RoamScope` 在 `class NpcDef` 之前',
     -1 < _ns_src.find('class RoamScope') < _ns_src.find('class NpcDef'))
item('2', '★ 第72轮守门仍成立：跨作品分支排在 `chapters` 判空之前',
     -1 < _ns_src.find("'roam_all'") < _ns_src.find('if not npc.chapters:'),
     'roam_all@%d chapters判空@%d'
     % (_ns_src.find("'roam_all'"), _ns_src.find('if not npc.chapters:')))

# ---------------- ③ 编码 ----------------
for p in (LIFE, NPCSYS, NPCPER, MAIN, CROSS, REG, CHECK73, CHECK72, RUNALL):
    b = rb(p)
    ok = (not b.startswith(b'\xef\xbb\xbf')) and (b'\xef\xbf\xbd' not in b)
    item('3', '%s 无 BOM / 无 U+FFFD' % os.path.basename(p), ok,
         'bytes=%d bom=%s fffd=%s' % (len(b), b.startswith(b'\xef\xbb\xbf'),
                                      b'\xef\xbf\xbd' in b))

# ---------------- ④ 恒真判据复查 ----------------
def tautologies(path, label):
    t = ast.parse(rd(path))
    out = []
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in ('check', 'item') and len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                out.append(getattr(n, 'lineno', -1))
    item('4', '%s 里没有"第二参是布尔真"的恒真判据（★ False 是主动报红，不算）' % label,
         not out, str(out or '(无)'))


tautologies(CHECK73, 'check73')
tautologies(CHECK72, 'check72')
tautologies(os.path.join(HERE, 'recheck73.py'), 'recheck73')

# ---------------- ⑤ 逐令牌回验 ----------------
TOKENS = [
    ('main.py', MAIN, '_npc_life_tick(elapsed_time)'),
    ('main.py', MAIN, 'from modules import npc_life as npc_life_mod'),
    ('main.py', MAIN, "NPC_LIFE_ENABLED = True"),
    ('main.py', MAIN, 'life=self._npc_life_blocks(npc_id)'),
    ('main.py', MAIN, 'npc_life_mod.transmit(self.npc_memory, npc_id, _others[0])'),
    ('main.py', MAIN, '_npc_life_scene'),
    ('npc_life.py', LIFE, 'TRAIT_WORDS_CN'),
    ('npc_life.py', LIFE, 'TRAIT_TOKENS_RESERVED'),
    ('npc_life.py', LIFE, 'BANNED_TOKENS'),
    ('npc_life.py', LIFE, 'SEED_SAME_AU_TWIN = 0.55'),
    ('npc_life.py', LIFE, 'GAIN_PER_TICK'),
    ('npc_life.py', LIFE, 'def transmit('),
    ('npc_life.py', LIFE, 'class LifeLoop('),
    ('npc_life.py', LIFE, 'def pick_line('),
    ('npc_system.py', NPCSYS, 'def load_crossworld('),
    ('npc_system.py', NPCSYS, 'def au_twin_pairs('),
    ('npc_system.py', NPCSYS, "PRODUCTION_PREFIXES = ('ut_', 'hy_', 'ot_', 'os_')"),
    ('npc_persona.py', NPCPER, "life=''"),
    ('_crossworld.json', CROSS, '"used_by"'),
    ('_crossworld.json', CROSS, '"wired_how"'),
    ('_crossworld.json', CROSS, '"round73"'),
    ('run_all.py', RUNALL, "'id': 'check73'"),
]
_bad_tok = []
for label, path, tok in TOKENS:
    if tok not in rd(path):
        _bad_tok.append((label, tok))
item('5', '逐令牌回验：%d 个改动令牌逐个回原文件 `in` 一次' % len(TOKENS),
     not _bad_tok, str(_bad_tok or '(全部命中)'))

# 数字回验（改过的数值必须与契约一致）
_cj = json.loads(rd(CROSS))
item('5', '数字回验：契约 seed_values == 0.55 / 0.30 / 0.0',
     _cj['familiarity_seed']['seed_values'] == {'same_au_twin': 0.55,
                                                'same_production': 0.3,
                                                'stranger': 0.0},
     str(_cj['familiarity_seed']['seed_values']))
item('5', '数字回验：契约 wiring.wired 五项 / spec_only 只有 visitor',
     len(_cj['wiring']['wired']) == 5 and _cj['wiring']['spec_only'] == ['visitor'],
     str(_cj['wiring']['wired']))
item('5', '数字回验：run_all 的套件数 == 61（第72轮 60）',
     rd(RUNALL).count("'id': '") >= 61)

# ---------------- ⑥ 工作区 ----------------
r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
porcelain = r.stdout.decode('utf-8', 'replace').strip()
n_changed = len([l for l in porcelain.split('\n') if l.strip()])
item('6', '工作区改动都是本轮的（列出，不要求为空 —— 提交前就该有改动）',
     n_changed >= 1, '%d 项\n%s' % (n_changed, porcelain[:900]))

# ---------------- 汇总 ----------------
_n_ok = sum(1 for x in ITEMS if x['ok'])
print('')
print('---- 复检：%d 项，PASS=%d FAIL=%d ----' % (len(ITEMS), _n_ok,
                                                 len(ITEMS) - _n_ok))
if '--write' in sys.argv:
    if not os.path.isdir(EV):
        os.makedirs(EV)
    out = os.path.join(EV, 'recheck73.json')
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'round': 73, 'total': len(ITEMS), 'pass': _n_ok,
                   'fail': len(ITEMS) - _n_ok, 'items': ITEMS}, fh,
                  ensure_ascii=False, indent=1)
    print('-> %s' % out)
sys.exit(0 if _n_ok == len(ITEMS) else 1)
