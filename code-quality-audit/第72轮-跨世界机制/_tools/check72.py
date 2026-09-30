# -*- coding: utf-8 -*-
"""第72轮 · 常驻锁：跨世界机制（穿行域）不许静默漂移。

为什么值得常驻
--------------
第72轮给 96 位 NPC 加了 `roam_scope`（穿行域），并在 `world_gate` 的暗世界分支
插了一段**顺序敏感**的判断。三样东西都可能被后来的人无声改坏：

  ① **数据**：`_registry.json` 里谁是什么档（niko 是唯一 `all`）；
  ② **代码**：`RoamScope` 三值与 `NpcDef` 的字段接线（`__slots__` / `to_dict` /
     `from_dict` 少一处就"写进去读不出来"）；
  ③ **判断顺序**：跨作品分支**必须排在 `chapters` 判空之前** ——
     顺序反了，跨作品角色会掉进"没有登记任何暗世界"这个**误导性**理由码。

设计纪律（沿用 check71）
------------------------
① **零 Qt、零网络、零存储、零外部盘** ⇒ 可进 G2。
② **正/负控制成对**：每条"放行"都配一条"拒"，每条内核都配一个"改坏了必须报红"。
③ **不自比**：A 段真源 = `_registry.json`（数据面契约）；`_crossworld.json` 只用来对账。
④ **判据名里不许自带 `[PASS]`/`[FAIL]`/`[OK]` 字样**（会污染 run_all 的计数）。
⑤ ★ C 段**真 import 真跑** `world_gate`（不是读字面量）—— 这是本轮唯一能证明
   "产品真的用上了"的一段；其余全是静态检查。
"""
from __future__ import print_function

import collections
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
NPCDIR = os.path.join(PET, 'assets', 'npc')
REG = os.path.join(NPCDIR, '_registry.json')
CROSS = os.path.join(NPCDIR, '_crossworld.json')
NPC_SYSTEM = os.path.join(PET, 'modules', 'npc_system.py')

FAILS = []
NCHECK = 0
XWORK = ('ut', 'hy', 'ot', 'os')
AU_FAMILY = ('ut', 'hy', 'ot')


def check(name, cond, extra=''):
    global NCHECK
    NCHECK += 1
    for tok in ('[PASS]', '[FAIL]', '[OK]'):
        if tok in name:
            FAILS.append('判据名字面量污染: %s' % name)
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def read_json(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def source_of(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


REGJ = read_json(REG)
NPCS = REGJ['npcs']
CROSSJ = read_json(CROSS)
SRC = source_of(NPC_SYSTEM)

#: 真源：从注册表推出该有的档位（**不看** `_crossworld.json`）
EXPECT_SCOPE = {}
for _n in NPCS:
    _w = _n['id'].split('_')[0]
    if _n['id'] == 'os_niko':
        EXPECT_SCOPE[_n['id']] = 'all'
    elif _w in XWORK:
        EXPECT_SCOPE[_n['id']] = 'non_dark'
    else:
        EXPECT_SCOPE[_n['id']] = 'home'
XW_IDS = sorted(n['id'] for n in NPCS if n['id'].split('_')[0] in XWORK)
DL_IDS = sorted(n['id'] for n in NPCS if n['id'].split('_')[0] not in XWORK)

# --------------------------------------------------------------------------
print('=' * 74)
print('A 数据面：96 位的穿行域（真源 = 注册表本身）')
print('=' * 74)
check('A1 96 条 NPC **逐条显式**写了 roam_scope（不靠代码兜底）',
      all('roam_scope' in n for n in NPCS),
      '缺 %d 条' % sum(1 for n in NPCS if 'roam_scope' not in n))

_actual = dict((n['id'], n.get('roam_scope')) for n in NPCS)
_diff = [(k, v, _actual.get(k)) for k, v in EXPECT_SCOPE.items()
         if _actual.get(k) != v]
check('A2 每条的档位 == 按「来处 + niko 特例」推出的档位',
      not _diff, str(_diff[:3] or '(全一致)'))

_c = collections.Counter(_actual.values())
check('A3 档位分布 = home 35 / non_dark 60 / all 1',
      _c.get('home') == 35 and _c.get('non_dark') == 60 and _c.get('all') == 1,
      json.dumps(dict(_c), ensure_ascii=False))

# ★ 负控制：把 niko 之外的某位也抬成 all，A3/A4 必须报红
_allids = sorted(k for k, v in _actual.items() if v == 'all')
check('A4 全域通行**只有 Niko 一人**（负控制：多一个就该报红）',
      _allids == ['os_niko'],
      'all = %s' % _allids)
_fake = dict(_actual)
_fake['ut_toriel'] = 'all'
check('A4n 鉴别的确落在"集合相等"上（伪造第二个 all ⇒ 集合不等）',
      sorted(k for k, v in _fake.items() if v == 'all') != ['os_niko'])

_hw_bad = [n['id'] for n in NPCS
           if n['id'] in XW_IDS and n.get('home_world') != 'foreign']
check('A5 跨作品 61 位的 home_world 全是 foreign（不再借用 Deltarune 的 dark）',
      not _hw_bad, str(_hw_bad[:4] or '(全一致)'))

_hw_dl_bad = [n['id'] for n in NPCS
              if n['id'] in DL_IDS and n.get('home_world') not in ('light', 'dark')]
check('A6 Deltarune 侧 35 位的 home_world 仍是 light/dark（没被误改）',
      not _hw_dl_bad, str(_hw_dl_bad[:4] or '(全一致)'))

_dc = CROSSJ['roam']['counts']
check('A7 契约文件的对账数字 == 磁盘注册表实际（不自比）',
      dict(_dc) == {'home': _c.get('home', 0), 'non_dark': _c.get('non_dark', 0),
                    'all': _c.get('all', 0)},
      '%s vs %s' % (json.dumps(_dc, ensure_ascii=False),
                    json.dumps(dict(_c), ensure_ascii=False)))

# --------------------------------------------------------------------------
print('=' * 74)
print('B 代码面：字段接线与判断顺序（AST，不吃注释）')
print('=' * 74)
import ast  # noqa: E402

TREE = ast.parse(SRC)
CLS = dict((n.name, n) for n in ast.walk(TREE) if isinstance(n, ast.ClassDef))
FUN = dict((n.name, n) for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef))

_roam = CLS.get('RoamScope')
_vals = []
if _roam is not None:
    for st in _roam.body:
        if isinstance(st, ast.Assign) and isinstance(st.value, ast.Constant):
            _vals.append(st.value.value)
check('B1 RoamScope 三档常量齐（home / non_dark / all）',
      set(['home', 'non_dark', 'all']).issubset(set(_vals)),
      '常量值 = %s' % sorted(v for v in _vals if isinstance(v, str)))

_slot_names = []
if 'NpcDef' in CLS:
    # ★ 不能取 body[0] —— 类里第一条是 docstring（Constant），不是 __slots__。
    #   本项目第64轮踩过同型的坑（"取了第一条就当常量"）。
    for _st in CLS['NpcDef'].body:
        if (isinstance(_st, ast.Assign) and len(_st.targets) == 1
                and isinstance(_st.targets[0], ast.Name)
                and _st.targets[0].id == '__slots__'):
            _slot_names = [e.value for e in _st.value.elts
                           if isinstance(e, ast.Constant)]
check('B2 NpcDef.__slots__ 含 roam_scope（否则赋值直接 AttributeError）',
      'roam_scope' in _slot_names, 'slots=%d 项' % len(_slot_names))

_methods = dict((f.name, f) for f in CLS['NpcDef'].body
                if isinstance(f, ast.FunctionDef))
_td_src = ast.get_source_segment(SRC, _methods['to_dict'])
_fd_src = ast.get_source_segment(SRC, FUN['npc_from_dict'])
check('B3 to_dict 输出 roam_scope，且 npc_from_dict 读得回来（写进去读不出来 = 假接线）',
      'roam_scope' in (_td_src or '') and 'roam_scope' in (_fd_src or ''))

_wg = FUN['world_gate']
_wg_src = ast.get_source_segment(SRC, _wg) or ''
check('B4 world_gate 里出现 roam_scope（本轮确实改了门控，不是只改数据）',
      'roam_scope' in _wg_src)

# ★ 顺序判据：跨作品分支必须排在 "if not npc.chapters:" 之前
_i_roam = _wg_src.find('roam_scope != RoamScope.HOME')
_i_ch = _wg_src.find('if not npc.chapters:')
check('B5 跨作品分支排在 chapters 判空**之前**（顺序反了会给误导性理由码）',
      0 <= _i_roam < _i_ch, 'roam@%d chapters@%d' % (_i_roam, _i_ch))

# --------------------------------------------------------------------------
print('=' * 74)
print('C 行为面：真 import 真跑 world_gate（本轮唯一能证明"产品用上了"的一段）')
print('=' * 74)
sys.path.insert(0, PET)
try:
    from modules import npc_system as ns
except Exception as e:                                            # noqa: BLE001
    ns = None
    print('!! import 失败：%r' % (e,))


_RAW = dict((n['id'], n) for n in NPCS)


def gate_disk(nid, world, scene_id):
    """按**磁盘注册表**里的真定义判 —— 这条很关键：
    内存构造只能证明"函数写对了"，用真数据才能证明"**这批数据**是对的"。"""
    n = ns.NpcDef(id=nid, name=nid, name_cn=nid,
                  chapters=_RAW[nid].get('chapters') or (),
                  home_world=_RAW[nid].get('home_world'),
                  escape_via_bubble=_RAW[nid].get('escape_via_bubble', False),
                  roam_scope=_RAW[nid].get('roam_scope'))
    return ns.world_gate(n, world, scene_id=scene_id)


if ns is not None:
    _cases = [
        ('C1 跨作品(non_dark) 进 Deltarune **光世界** ⇒ 放行',
         'ut_toriel', 'light', 'ch1.hometown.x', True),
        ('C2 跨作品(non_dark) 进 Deltarune **暗世界** ⇒ 拒',
         'ut_toriel', 'dark', 'ch1.field.x', False),
        ('C3 跨作品(non_dark) 回**自己作品那侧** ⇒ 放行',
         'ut_toriel', 'dark', 'undertale.snowdin.x', True),
        ('C4 Niko(all) 进 Deltarune **暗世界** ⇒ 放行（用户口径的核心一句）',
         'os_niko', 'dark', 'ch2.cyber_city.x', True),
        ('C5 Niko(all) 进光世界 ⇒ 放行',
         'os_niko', 'light', 'ch1.home.x', True),
        ('C6 黄魂 / Outertale 侧同款（不是只对 ut_ 生效）',
         'hy_flowey', 'dark', 'ch1.field.x', False),
    ]
    # C6b 单独验一个 outertale
    for name, nid, world, sid, want in _cases:
        g = gate_disk(nid, world, scene_id=sid)
        check(name, g.ok == want,
              '%s world=%s scene=%s -> ok=%s (%s)'
              % (nid, world, sid, g.ok, g.reason))
    g = gate_disk('ot_sans', 'dark', scene_id='ch1.field.x')
    check('C7 Outertale 侧也受同一条约束（ot_sans 进暗世界 ⇒ 拒）', g.ok is False,
          'ok=%s reason=%s' % (g.ok, g.reason))

    # ★ 零回归：第49/50/56轮的老行为一条都不许变
    _old = [
        ('C8 零回归 · Ralsei 跨章暗世界仍放行', 'ralsei', 'dark', 'ch3.tv_world.x', True),
        ('C9 零回归 · Ralsei 无球进光世界仍被拒', 'ralsei', 'light', 'ch1.hometown.x', False),
        ('C11 零回归 · Lancer 进本作品暗世界仍放行', 'lancer', 'dark', 'ch1.castle_town.x', True),
        ('C12 零回归 · 桌面白名单内仍放行（kris）', 'kris', 'light', 'desktop', True),
    ]
    for name, nid, world, sid, want in _old:
        g = gate_disk(nid, world, scene_id=sid)
        check(name, g.ok == want,
              '%s -> ok=%s (%s)' % (nid, g.ok, g.reason))
    # ★ "别章拒"的用例**从数据推**，不凭印象写死哪一章 —— 本项目踩过
    #   "判据名与事实脱节却照样 PASS"的坑（第64轮 W22：名字说"35 条"、实测 70 条）。
    #   第一版我就是凭印象写 `lancer + ch3`，实测 lancer 的 chapters 里**有 ch3**
    #   ⇒ 报红；错的是期望，不是产品。这里改成算出来。
    _n_ch = set(_RAW['noelle'].get('chapters') or [])
    _miss_ch = [c for c in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5') if c not in _n_ch][0]
    g = gate_disk('noelle', 'dark', scene_id='%s.field.x' % _miss_ch)
    check('C10 零回归 · Noelle 进**没登记过**的那一章仍被拒（用例由数据推出）',
          g.ok is False,
          'noelle 登记=%s ⇒ 试 %s -> ok=%s (%s)'
          % (sorted(_n_ch), _miss_ch, g.ok, g.reason))
    g = gate_disk('ut_toriel', 'light', scene_id='desktop')
    check('C13 桌面闸优先于一切：跨作品角色仍上不了桌面', g.ok is False,
          'reason=%s' % g.reason)

    # ★★ 负控制：把 niko 的档位人为降成 non_dark，C4 必须翻转
    _n = ns.NpcDef(id='os_niko', name_cn='niko', chapters=('oneshot',),
                   home_world='foreign', roam_scope='non_dark')
    g = ns.world_gate(_n, 'dark', scene_id='ch2.cyber_city.x')
    check('C14 负控制：Niko 若被降档为 non_dark，暗世界必须**进不去**'
          '（证明放行真是 scope 给的，不是碰巧）',
          g.ok is False, 'ok=%s reason=%s' % (g.ok, g.reason))
else:
    check('C0 npc_system 可 import（后续行为段的前提）', False, 'import 失败')

# --------------------------------------------------------------------------
print('=' * 74)
print('D 同名角色组（共存 / 相认的身份基础）')
print('=' * 74)
_byname = collections.defaultdict(list)
for n in NPCS:
    _byname[n['name']].append((n['id'], n['id'].split('_')[0] in XWORK))
_expect_groups = sorted(k for k, v in _byname.items()
                        if len(v) >= 2 and any(x[1] for x in v))
_got = CROSSJ['twin_groups']['groups']
_got_names = sorted(g['name'] for g in _got)
check('D1 同名组集合 == 注册表推出的集合（≥2 人且含跨作品）',
      _got_names == _expect_groups, '契约 %s vs 注册表 %s'
      % (_got_names, _expect_groups))

_tor = [g for g in _got if g['name'] == 'Toriel']
_tor = _tor[0] if _tor else {}
check('D2 Toriel 组恰 3 人，且"Deltarune 那位只是同名"被标出来（用户点名的例子）',
      _tor.get('members') == ['ot_toriel', 'toriel', 'ut_toriel']
      and _tor.get('namesake_members') == ['toriel']
      and _tor.get('au_family_members') == ['ot_toriel', 'ut_toriel'],
      'members=%s namesake=%s' % (_tor.get('members'), _tor.get('namesake_members')))

_bad_mem = []
for g in _got:
    if len(g['members']) != len(set(g['members'])):
        _bad_mem.append('%s 有重复' % g['name'])
    for m in g['members']:
        if m not in _RAW:
            _bad_mem.append('%s 里的 %s 不在注册表' % (g['name'], m))
check('D3 每个成员都真实存在于注册表，且组内无重复', not _bad_mem,
      str(_bad_mem[:3] or '(全一致)'))

_au_bad = [g['name'] for g in _got
           if g['has_au'] != (len(g['au_family_members']) >= 2)]
check('D4 has_au 与"组内 AU 家族成员数 ≥2"逐组一致', not _au_bad,
      str(_au_bad[:3] or '(全一致)'))
check('D5 负控制：编造的组名不在表里（防"表格里塞了不存在的人"）',
      'ZzzNoSuchTwin' not in _got_names)

# --------------------------------------------------------------------------
print('=' * 74)
print('E 诚实判据：只准把真接线的写成 wired')
print('=' * 74)
_w = CROSSJ['wiring']
# ★ 第73轮更新：`scene_traits` / `familiarity_seed` / `identity_blind` / `twin_groups`
#   也已接线（自由生活）。本判据**不再写死"只有 roam"** ——
#   写死会把"将来接线"变成"必须报红"，那是判据过窄（本项目踩过：
#   判据名与事实脱节却照样 PASS，以及"判据过窄会漏报"）。
#   改成守**两件不许撒谎的事**：
#     ① 宣布 `wired` 的块，自己 `status` 必须也是 `wired`（台账与正文不许打架）；
#     ② 每一块 `wired` 都必须写明 `used_by`（谁在用它）——
#        "标了 wired 却说不清用在哪"正是「函数写对了 ≠ 产品用上了」的变体。
_wired = set(_w.get('wired') or [])
_tag_mismatch = [k for k in _wired if CROSSJ.get(k, {}).get('status') != 'wired']
check('E1 台账 wired 与正文 status 一致，且至少 roam 在（第73轮起可增长）',
      'roam' in _wired and not _tag_mismatch
      and not [k for k in (_w.get('spec_only') or [])
               if CROSSJ.get(k, {}).get('status') != 'spec_only'],
      'wired=%s 正文不一致=%s' % (sorted(_wired), _tag_mismatch))
check('E1b ★ 每一项 wired 都必须写明 used_by（谁在用），否则"标了 wired 说不清用在哪"',
      all(CROSSJ.get(k, {}).get('used_by') for k in _wired),
      str({k: bool(CROSSJ.get(k, {}).get('used_by')) for k in sorted(_wired)}))
check('E2 接线台账列了 not_yet（不许只说"做完了"）', bool(_w.get('not_yet')),
      '%d 条' % len(_w.get('not_yet') or []))
# 反向：契约里每个 spec_only 的块，自己也要带 status 字段
_missing_status = [k for k in (_w.get('spec_only') or [])
                   if CROSSJ.get(k, {}).get('status') != 'spec_only']
check('E3 每个 spec_only 的块自己带 status 字段且值一致（台账与正文不许打架）',
      not _missing_status, str(_missing_status or '(一致)'))
check('E4 ★ `visitor` 必须仍为 spec_only（跨作品场景面没进 `_index.json`，'
      '不许跟着一起翻绿 —— 翻绿就等于宣称"访客已经能用"）',
      CROSSJ.get('visitor', {}).get('status') == 'spec_only',
      str(CROSSJ.get('visitor', {}).get('status')))

# --------------------------------------------------------------------------
print('=' * 74)
print('F 判据自身体检')
print('=' * 74)
check('F1 判据条数经 check() 记账', NCHECK >= 20, 'NCHECK=%d' % NCHECK)
check('F2 判据名里没有自带的计数标记字样（防污染 run_all 的 PASS 计数）',
      not [f for f in FAILS if f.startswith('判据名字面量污染')])

print('')
print('---- 第72轮 跨世界锁：%d 项判据，FAIL=%d ----' % (NCHECK, len(FAILS)))
if FAILS:
    for f in FAILS:
        print('   FAIL: %s' % f)
sys.exit(0 if not FAILS else 1)
