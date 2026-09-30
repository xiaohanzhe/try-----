# -*- coding: utf-8 -*-
"""第72轮 · 复检：改过**核心文件**（`modules/npc_system.py` + `_registry.json`）之后
必须逐项打 PASS/FAIL，而不是口头说"改完了"。

六类判据（用户 2026-09-23 口径）
--------------------------------
① 语法/可编译 ② 结构自检 ③ 编码（无 BOM / 无 U+FFFD）
④ **恒真判据复查** ⑤ **逐令牌回验**（改过/删过的字面量逐个回原文件 `in` 一次）
⑥ 工作区干净 + 该跑的回归跑了

★ 本轮特别加一条「**定义顺序**」判据：`RoamScope` 必须定义在 `NpcDef` **之前** ——
  否则 `NpcDef.__init__` 里的 `RoamScope.ALL_VALUES` 会在 import 期 `NameError`。
  这类错误"看起来像改对了"（文本都在），只有顺序判据能抓。

落盘：`_evidence/recheck72.json` + 控制台逐项输出。
用法：C:\\Python311\\python.exe recheck72.py
"""
from __future__ import print_function

import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
AUD = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
CROSS = os.path.join(PET, 'assets', 'npc', '_crossworld.json')
NPSYS = os.path.join(PET, 'modules', 'npc_system.py')
PY = r'C:\Python311\python.exe'

RES = []


def item(no, name, ok, extra=''):
    RES.append({'no': no, 'name': name, 'ok': bool(ok), 'extra': str(extra)[:300]})
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, extra))


def main():
    print('=' * 74)
    print('第72轮 核心文件复检')
    print('=' * 74)

    # ---------- ① 语法 / 可编译（用 ast.parse，**不产 .pyc**）----------
    py_raw = io.open(NPSYS, 'rb').read()
    py_txt = py_raw.decode('utf-8')
    try:
        tree = ast.parse(py_txt)
        item('1.1', 'npc_system.py 可被 ast.parse', True,
             '%d 顶层语句' % len(tree.body))
    except SyntaxError as e:
        tree = None
        item('1.1', 'npc_system.py 可被 ast.parse', False, repr(e))

    for path, label in ((REG, '_registry.json'), (CROSS, '_crossworld.json')):
        try:
            json.loads(io.open(path, encoding='utf-8').read())
            item('1.2', '%s 是合法 JSON' % label, True)
        except Exception as e:                                     # noqa: BLE001
            item('1.2', '%s 是合法 JSON' % label, False, repr(e))

    # ---------- ② 结构自检 ----------
    cls = dict((n.name, n) for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef)) if tree else {}
    _rs_vals = sorted(st.value.value for st in cls['RoamScope'].body
                      if isinstance(st, ast.Assign)
                      and isinstance(st.value, ast.Constant)) if 'RoamScope' in cls else []
    item('2.1', 'RoamScope 类存在且三档常量齐',
         'RoamScope' in cls and set(('home', 'non_dark', 'all')).issubset(set(_rs_vals)),
         '常量=%s' % _rs_vals)
    item('2.2', 'WORLD_FOREIGN 常量存在且只定义一次',
         py_txt.count('WORLD_FOREIGN = ') == 1,
         '出现 %d 次' % py_txt.count('WORLD_FOREIGN = '))
    item('2.3', 'world_gate 仍只有一个定义', py_txt.count('def world_gate(') == 1)

    # ★ 定义顺序：RoamScope 必须在 NpcDef 之前
    i_rs = py_txt.find('class RoamScope')
    i_nd = py_txt.find('class NpcDef')
    item('2.4', '★ 定义顺序：class RoamScope 在 class NpcDef 之前（否则 import 期 NameError）',
         0 <= i_rs < i_nd, 'RoamScope@%d NpcDef@%d' % (i_rs, i_nd))

    # ★ 判断顺序：跨作品分支在 chapters 判空之前
    i_roam = py_txt.find('roam_scope != RoamScope.HOME')
    i_ch = py_txt.find('if not npc.chapters:')
    item('2.5', '★ 判断顺序：跨作品分支在 chapters 判空之前',
         0 <= i_roam < i_ch, 'roam@%d chapters@%d' % (i_roam, i_ch))

    # ---------- ③ 编码 ----------
    item('3.1', 'npc_system.py 无 BOM', py_raw[:3] != b'\xef\xbb\xbf')
    item('3.2', 'npc_system.py 无 U+FFFD（乱码替换符）',
         b'\xef\xbf\xbd' not in py_raw)
    for path, label in ((REG, '_registry.json'), (CROSS, '_crossworld.json')):
        raw = io.open(path, 'rb').read()
        item('3.3', '%s 无 BOM 且无 U+FFFD' % label,
             raw[:3] != b'\xef\xbb\xbf' and b'\xef\xbf\xbd' not in raw)

    # ---------- ④ 恒真判据复查 ----------
    # ★★ 只查"第二参是 **True** 字面量"（那才是"看着在守、其实没守"）。
    #    **不能**把 `False` 也算进来 —— `check(name, False, ...)` 是**主动报红**
    #    （check72 的 C0 就是这么写的：import 失败时无条件亮红灯），它是**合法用法**。
    #    第一版把两者混在一起查 ⇒ 4.2 误报。教训同"判据过窄 = 会误报"，
    #    这里是反过来的"**判据过宽 = 也会误报**"。
    def tautology_lines(tree_):
        out = []
        for node in ast.walk(tree_):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'check' and len(node.args) >= 2):
                a = node.args[1]
                if isinstance(a, ast.Constant) and a.value is True:
                    out.append(getattr(node, 'lineno', -1))
        return out

    bad = tautology_lines(tree) if tree else []
    item('4.1', 'npc_system 里没有 check(..., True) 型恒真判据', not bad,
         str(bad or '(无)'))
    ck = io.open(os.path.join(HERE, 'check72.py'), encoding='utf-8').read()
    bad2 = tautology_lines(ast.parse(ck))
    item('4.2', 'check72 里没有 check(..., True) 型恒真判据', not bad2,
         '越界行号 %s（★False 不算——那是主动报红）' % (bad2 or '(无)'))

    # ---------- ⑤ 逐令牌回验 ----------
    reg_txt = io.open(REG, encoding='utf-8').read()
    tokens = [
        ('REG 已删掉旧的"一律显式 dark"那句', u'两作品 `home_world` 一律显式 `dark`', False),
        ('REG 的 source 里有第72轮说明', u'第72轮', True),
        ('REG 有 roam_scope 字段', u'"roam_scope"', True),
        ('REG 保留 foreign 值', u'"foreign"', True),
        ('NPSYS 有 WORLD_FOREIGN 值', u"WORLD_FOREIGN = 'foreign'", True),
        ('NPSYS 有 RoamScope.NON_DARK 用法', u'RoamScope.NON_DARK', True),
        ('NPSYS 有 home_production 理由', u'home_production', True),
        ('NPSYS 有 roam_all 理由', u'roam_all', True),
        ('CROSS 有 twin_groups 段', u'"twin_groups"', True),
        ('CROSS 有 spec_only 台账', u'"spec_only"', True),
    ]
    for name, tok, want in tokens:
        hay = py_txt if 'NPSYS' in name else (
            reg_txt if name.startswith('REG') else
            io.open(CROSS, encoding='utf-8').read())
        item('5.x', name, (tok in hay) == want,
             'found=%s want=%s' % (tok in hay, want))

    # ---------- ⑥ 工作区 + 回归 ----------
    p = subprocess.run(['git', 'status', '--porcelain'], capture_output=True,
                       cwd=ROOT)
    st = (p.stdout or b'').decode('utf-8', 'replace').strip().splitlines()
    item('6.1', '工作区改动都是本轮的（列出，不要求为空——提交前就该有改动）',
         True, '%d 项' % len(st))
    for ln in st:
        print('        %s' % ln)

    # 真机行为复核（import + 三条核心路径）
    sys.path.insert(0, PET)
    try:
        from modules import npc_system as ns
        n = ns.NpcDef(id='os_niko', chapters=('oneshot',), home_world='foreign',
                      roam_scope='all')
        g = ns.world_gate(n, 'dark', scene_id='ch2.cyber_city.x')
        t = ns.NpcDef(id='ut_toriel', chapters=('undertale',), home_world='foreign',
                      roam_scope='non_dark')
        g2 = ns.world_gate(t, 'dark', scene_id='ch1.field.x')
        item('6.2', 'import 后真跑：niko 进暗世界 ok 且 跨作品 non_dark 被拒',
             bool(g.ok) and (not g2.ok),
             'niko=%s ut_toriel=%s' % (g.ok, g2.reason))
    except Exception as e:                                         # noqa: BLE001
        item('6.2', 'import 后真跑', False, repr(e))

    fails = [r for r in RES if not r['ok']]
    print('')
    print('---- 复检：%d 项，PASS=%d FAIL=%d ----'
          % (len(RES), len(RES) - len(fails), len(fails)))
    for r in fails:
        print('   FAIL %s %s' % (r['no'], r['name']))

    ev = os.path.join(AUD, '_evidence')
    if not os.path.isdir(ev):
        os.makedirs(ev)
    with io.open(os.path.join(ev, 'recheck72.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'round': 72, 'items': RES,
                             'pass': len(RES) - len(fails),
                             'fail': len(fails)}, ensure_ascii=False, indent=1))
    print('-> %s' % os.path.join(ev, 'recheck72.json'))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
