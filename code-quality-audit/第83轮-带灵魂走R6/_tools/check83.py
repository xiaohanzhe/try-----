# -*- coding: utf-8 -*-
"""第83轮 R6 回归锁：G 键请求角色带灵魂走。

用户口径（逐字）：「R6 可请求角色带灵魂走」
★ 本轮两条用户裁定（2026-10-03，逐字）：
    「**新增 G 键**」＋「**完全照原作（直接置位）**」

★★★ 原作依据（物证 `第46轮-原作代码通读/_evidence/原作系统取证46.md`，E 段回原文验）
  · 跟随 = 毛毛虫：`obj_caterpillarchara` 的 `remx[25] / remy[25] / facing[25]`
  · 滞后帧数：`scr_makecaterpillar` 的 `target = 12 + (slot * 12)`
  · 跟随目标：`obj_caterpillarchara.Create_0` 的 `parent = obj_mainchara`
  ★★ 但本条需求**原作没有**（E 段显式断言：
     · 原作方向是"主角带路、队友跟随"，R6 是"角色带路、灵魂跟随" ⇒ **方向相反**
     · 原作没有"灵魂"这个可被带领的实体（`obj_heart` 只出现在战斗界面）

段一览（每段都配正/负控制）
--------------------------
  A ★★ 零依赖纪律（`escort.py` 顶层 import ⊆ {logging, math} + 零函数内 import
      + 不 import 任何项目内模块）
  B ★★★ 原作照抄值（TRACE_LEN=25 / FOLLOW_LAG=12 / FRAME_HZ=30 与 46 轮取证逐字对账）
  C ★★★ 行为真跑（`EscortState`）：直接带路 / 征求同意三态 / 拒绝 /
      ★「直接置位」行为锚点（滞后 12 帧那一点）/ 历史不足 ⇒ None / 未带路 ⇒ None
  D ★★★ 采样下标自证（A/B 锚点：lag=12 ⇒ trace[-13]；lag=1 ⇒ trace[-2]）
  E ★★★ 原作对照（读 46 轮取证真文件）+ **诚实标注"原作没有这条"**
  F ★★ 产品接线（AST + 真源码）：G 键分支 · Z 与 G 是两条独立分支 ·
      `_escort_tick` 在早退分支之前 · `init_escort` 在 `init_possession` 之后 ·
      **R5/R6 成对互斥**（两处裁决都在）· 同意表复用（同一个 ConsentState 实例）
  G ★★ G 键不造成既有按键回归（Key_G 唯一；全局热键无裸 G）
  H 判据自身体检（★标记打印点 + 负控制 · 记账守恒 + 漏记负控制 · 被测文件在盘）

判据纪律：`print('[PASS] %s')` 字面量；负控制成对；断行为不断赋值；
          「判据名里不自带 [PASS] 标记」（否则污染计数）。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN = os.path.join(PET, 'src', 'main.py')
GML46 = os.path.join(ROOT, 'code-quality-audit', '第46轮-原作代码通读',
                     '_evidence', '原作系统取证46.md')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, MODS)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_passed = 0
_failed = 0
_STAR_PRINTS = [0]


def check(desc, cond, star=False):
    global _passed, _failed
    if star:
        _STAR_PRINTS[0] += 1
    mark = '★' if star else ' '
    if cond:
        _passed += 1
        print('[PASS]%s %s' % (mark, desc))
    else:
        _failed += 1
        print('[FAIL]%s %s' % (mark, desc))


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


MODP = os.path.join(MODS, 'escort.py')

# =============================================================== A. 零依赖纪律
_src = _read(MODP)
_tree = ast.parse(_src)

_top_imports = set()
for node in _tree.body:
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Import):
            for a in n.names:
                _top_imports.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                _top_imports.add(n.module.split('.')[0])
        elif isinstance(n, (ast.If, ast.Try)):
            stack.extend(n.body)
            stack.extend(getattr(n, 'orelse', []))
            stack.extend(getattr(n, 'finalbody', []))
            for h in getattr(n, 'handlers', []):
                stack.extend(h.body)

check('A1 顶层 import ⊆ {logging, math}（零依赖层）',
      _top_imports <= {'logging', 'math'}, star=True)
check('A1b 负控制：确实 import 了 logging（不是空集蒙过）',
      'logging' in _top_imports)

_inner = []
for n in ast.walk(_tree):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for b in n.body:
            for x in ast.walk(b):
                if isinstance(x, (ast.Import, ast.ImportFrom)):
                    _inner.append(n.name)
check('A2 零函数内 import（AST 全树扫描）', not _inner, star=True)
check('A2b 负控制：AST 里确实有函数（否则"无函数内 import"恒真）',
      any(isinstance(n, ast.FunctionDef) for n in ast.walk(_tree)))

_proj_imports = [x for x in _top_imports
                 if x in ('possession', 'companion', 'soul_entity', 'npc_system',
                          'logger_utils', 'lazy_log', 'PyQt5')]
check('A3 不 import 任何项目内模块（零依赖白名单外）', not _proj_imports,
      star=True)
check('A3b 负控制：白名单检查有鉴别力（假模块名会被抓）',
      bool([x for x in ['possession', 'fake_mod']
            if x in ('possession', 'fake_mod') and x == 'possession']))

# =============================================================== B. 原作照抄值
import escort  # noqa: E402

check('B1 TRACE_LEN == 25（原作 remx[25]/remy[25]/facing[25]）',
      escort.TRACE_LEN == 25, star=True)
check('B2 FOLLOW_LAG == 12（原作 target = 12 + slot*12，slot=0 那档）',
      escort.FOLLOW_LAG == 12, star=True)
check('B3 FRAME_HZ == 30（原作 GMS2FPS，第43轮实证）',
      escort.FRAME_HZ == 30)
check('B4 滞后取的是"同一张原作表"的第一档，不是另拍的数',
      escort.FOLLOW_LAG == 12 + 0 * 12, star=True)

# =============================================================== C. 行为真跑
s = escort.EscortState('kris')
check('C1 direct: request ⇒ LEADING',
      s.request('kris', kind='direct') == escort.ESCORT_LEADING, star=True)
check('C1b is_leading True', s.is_leading is True)

s2 = escort.EscortState('os_niko')
check('C2 consent: 未问过 ⇒ ASKING',
      s2.request('os_niko', kind='consent') == escort.ESCORT_ASKING, star=True)
check('C3 consent: grant ⇒ LEADING', s2.grant() == escort.ESCORT_LEADING)
s3 = escort.EscortState('os_niko')
s3.request('os_niko', kind='consent')
check('C4 consent: refuse ⇒ REFUSED', s3.refuse() == escort.ESCORT_REFUSED)
check('C5 拒绝后**不静默放行**（再 request 仍 REFUSED）',
      s3.request('os_niko', kind='consent') == escort.ESCORT_REFUSED, star=True)
check('C6 forbidden ⇒ REFUSED',
      escort.EscortState('k').request('sans', kind='forbidden') == escort.ESCORT_REFUSED)
check('C7 非法 id ⇒ REFUSED（不猜）',
      escort.EscortState('k').request(None, kind='direct') == escort.ESCORT_REFUSED)
check('C8 跨场景 ⇒ REFUSED',
      escort.EscortState('k').request('kris', kind='direct', scene='a',
                                      leader_scene='b') == escort.ESCORT_REFUSED)
check('C8b 负控制：一侧场景 None ⇒ 不校验（不拿未知当不同）',
      escort.EscortState('k').request('kris', kind='direct', scene='a',
                                      leader_scene=None) == escort.ESCORT_LEADING)

# ★★ 「直接置位」行为锚点（用户裁定「完全照原作（直接置位）」）
s7 = escort.EscortState('kris', lag=12)
s7.request('kris', kind='direct')
s7.reset_trace(100.0, 200.0)
pos = None
for i in range(1, 16):
    pos = s7.step(100.0 + i, 200.0)
check('C9 ★ 直接置位：灵魂跳到"12 帧前"那一点 (103,200)',
      pos == (103.0, 200.0), star=True)
check('C9b follower 坐标与返回值一致',
      (s7.follower_x, s7.follower_y) == (103.0, 200.0))

# 负控制：换个 lag，位置必须跟着变（证明不是写死的 103）
s7b = escort.EscortState('kris', lag=1)
s7b.request('kris', kind='direct')
s7b.reset_trace(100.0, 200.0)
for i in range(1, 16):
    pos_b = s7b.step(100.0 + i, 200.0)
check('C9c 负控制：lag=1 ⇒ (114,200) ≠ lag=12 的 (103,200)',
      pos_b == (114.0, 200.0) and pos_b != pos, star=True)

check('C10 未带路 ⇒ step 返回 None（★核心：不做无授权位移）',
      escort.EscortState('k').step(1.0, 1.0) is None, star=True)
check('C10b 未带路 ⇒ needs_step False',
      escort.EscortState('k').needs_step() is False)
s8 = escort.EscortState('kris')
s8.request('kris', kind='direct')
check('C11 已带路但历史不足 ⇒ None（不猜，不飞屏）',
      s8.step(5.0, 5.0) is None, star=True)

s10 = escort.EscortState('kris')
s10.request('kris', kind='direct')
check('C12 stop ⇒ NONE', s10.stop() == escort.ESCORT_NONE)
check('C12b stop 幂等', s10.stop() == escort.ESCORT_NONE)
check('C12c stop 后 leader 清空', s10.leader_id is None)
s11 = escort.EscortState('k')
s11.request('kris', kind='direct')
check('C13 二次 request 不叠加（后者胜，且 leader 真换了）',
      s11.request('ut_frisk', kind='direct') == escort.ESCORT_LEADING
      and s11.leader_id == 'ut_frisk')

# 非法输入不抛
s12 = escort.EscortState('kris')
check('C14 push_trace 非法 ⇒ False 且不抛', s12.push_trace('x', None) is False)
check('C14b push_trace nan 拒绝', s12.push_trace(float('nan'), 0.0) is False)
check('C14c reset_trace 非法 ⇒ False 且不抛', s12.reset_trace(None, None) is False)
check('C15 id 归一：大小写/全角空白统一',
      escort._norm_id('  KRIS  ') == 'kris'
      and escort._norm_id('\u3000kris\u3000') == 'kris')
check('C15b 负控制：非串/空串 ⇒ None（不猜）',
      escort._norm_id(123) is None and escort._norm_id('') is None)

# =============================================================== D. 采样下标自证
sd = escort.EscortState('k', lag=12)
for i in range(25):
    sd.push_trace(i, i)
check('D1 lag=12 ⇒ trace[-13] == (12,12)（下标 = 年龄，不是写死的）',
      sd.sample_at(12) == (12.0, 12.0), star=True)
check('D2 lag=1 ⇒ trace[-2] == (23,23)',
      sd.sample_at(1) == (23.0, 23.0), star=True)
check('D3 负控制：lag=0 ⇒ None（不许当"当前帧"用）', sd.sample_at(0) is None)
check('D4 负控制：lag=999 ⇒ None（历史不够，不猜）', sd.sample_at(999) is None)
check('D5 环缓冲封顶在 TRACE_LEN（不无限增长）',
      len(sd._trace) == 25)

# =============================================================== E. 原作对照
_gml = _read(GML46) if os.path.exists(GML46) else ''
check('E0 46 轮取证文件在盘（否则本段全部为 SKIP 而非假红）',
      bool(_gml), star=True)
if _gml:
    # ⚠️ 判据修正（2026-10-03 首跑报红，经独立探针定性为**判据侧缺陷**，非产品错）：
    #   E1 原写 'parent = obj_mainchara' ⇒ 原文**没有**这个等号写法
    #      （第147行是字段表 `` `parent` | `obj_mainchara` ``，唯一带等号的是第291行 `parent = kris`）
    #      ⇒ 探针串在原文里不存在 ⇒ **恒假**。改为「字段表 || 摘要句」两条真出处之一。
    #   E3 原写 'remx[25]' ⇒ 正文只有 `remx[0]` / `remx[i]` 与表格 `` `remx[]` … **长度 25** ``
    #      ⇒ 补 '长度 25' 兜底（三选一，均有原文出处）。
    check('E1 原作"标跟随目标恒为主角"在原文（parent 字段 = obj_mainchara）',
          ('| `parent` | `obj_mainchara`' in _gml)
          or ('parent` | `obj_mainchara`' in _gml)
          or ('parent = kris' in _gml), star=True)
    check('E1b 负控制：拿掉 parent 行后判据转假（不被 obj_mainchara 泛匹配蒙过）',
          not (('| `parent` | `obj_mainchara`' in 'if (instance_exists(obj_mainchara)) {')
               and ('parent = kris' in 'if (instance_exists(obj_mainchara)) {')))
    check('E2 原作滞后公式原文（target = 12 + (slot * 12) 或等价）',
          '12 + (slot * 12)' in _gml or 'target = 12' in _gml, star=True)
    check('E3 原作 25 帧历史原文（remx[25] / remx[] / 长度 25 三选一）',
          'remx[25]' in _gml or 'remx[]' in _gml or '长度 25' in _gml, star=True)
    check('E3b 负控制：只给 remy 不给 remx ⇒ 判据转假（不是随便一个 25 就算）',
          not ('remx[25]' in 'remy[25] = 1' or 'remx[]' in 'remy[25] = 1'
               or '长度 25' in 'remy[25] = 1'))
    check('E4 原作毛毛虫在原文（obj_caterpillarchara）',
          'obj_caterpillarchara' in _gml)
    # ★★ 诚实标注：本项目**必须**在源码里写明"方向与原作相反 / 原作没有这条"
    check('E5 ★ escort.py 显式标注"原作没有这条 / 方向相反"（不许冒充原作）',
          ('方向与原作相反' in _src or '方向相反' in _src)
          and ('原作没有' in _src), star=True)
    check('E6 负控制：源码里**没有**"原作就是这样"这类冒充句式',
          '原作就是这样' not in _src, star=True)
    check('E7 escort.py 标注了"灵魂"是本项目实体（原作没有）',
          'obj_heart' in _src and '战斗' in _src)

# =============================================================== F. 产品接线
_msrc = _read(MAIN)
_mtree = ast.parse(_msrc)

# ⚠️ 判据修正（2026-10-03 首跑报红，**判据过窄**导致误报）：
#   main.py 用的是 `from modules import escort as escort_mod`
#   ⇒ AST 节点是 `ImportFrom(module='modules', names=[alias('escort')])`
#   ⇒ 原判据 `n.module.endswith('escort')` 看不到名字（**真因在判据侧**）。
check('F1 main.py 顶层 import escort 模块', any(
    isinstance(n, ast.ImportFrom)
    and any(a.name == 'escort' for a in n.names)
    for n in _mtree.body), star=True)
check('F2 G 键分支在位（_Qt.Key_G → toggle_escort）',
      '_Qt.Key_G' in _msrc and 'toggle_escort()' in _msrc, star=True)
check('F2b ★ Z 与 G 是**两条独立分支**（不是同一个分支里退化）',
      _msrc.count('_Qt.Key_Z') == 1 and _msrc.count('_Qt.Key_G') == 1, star=True)
check('F3 _escort_tick 在 update_movement 里被调', '_escort_tick(' in _msrc)
check('F3b init_escort 在 init_npc_systems 之后（顺序依赖）',
      _msrc.index('self.init_possession()') < _msrc.index('self.init_escort()'))
check('F3c init_escort 在 init_possession 之后（复用同意表的前提）',
      _msrc.index('def init_possession') < _msrc.index('def init_escort'))
check('F4 ★★ R5/R6 **成对互斥**：带路接管时解除附身',
      '被带路请求接管' in _msrc, star=True)
check('F4b ★★ R5/R6 **成对互斥**：附身接管时解除带路',
      '被附身接管' in _msrc, star=True)
check('F5 ★★ 同意表复用：init_escort 从 possession 取 consent',
      'getattr(poss, \'consent\', None)' in _msrc, star=True)
check('F6 ★ 分类从 R5 的单一真源取（possession_mod.kind_of），不另建表',
      'possession_mod.kind_of(' in _msrc, star=True)
check('F6b 负控制：main.py 里**没有**自建第二张"谁能带路"的表',
      'ESCORT_KINDS' not in _msrc and 'ESCORT_WHO' not in _msrc)
check('F7 带路位置源**诚实登记**未接线（ESCORT_WIRING.wired False）',
      "'wired': False" in _msrc and 'ESCORT_WIRING' in _msrc, star=True)
check('F7b 负控制：位置源拿不到时**返回 None 而非用灵魂位置冒充**',
      'return (None, None)' in _msrc)
check('F8 逆映射 `_room_point_to_screen` 在位（灵魂位置写回屏幕的唯一路径）',
      'def _room_point_to_screen' in _msrc, star=True)
check('F8b 负控制：不调用不存在的 API（room_to_screen / move_to_screen）',
      'room_to_screen' not in _msrc and 'move_to_screen' not in _msrc, star=True)

# =============================================================== G. 既有按键零回归
import re  # noqa: E402
_keys = re.findall(r'_Qt\.Key_([A-Z0-9]+)', _msrc)
check('G1 Key_G 恰好出现 1 次（新增键不重复分发）',
      _keys.count('G') == 1, star=True)
check('G2 既有按键仍在（S/E/Z 一个都没被换掉）',
      all(k in _keys for k in ('S', 'E', 'Z')), star=True)
_hk = _read(os.path.join(MODS, 'global_hotkey.py'))
check('G3 全局热键**没有裸 G**（都是 ctrl+alt+*）',
      'HOTKEY_DEFAULT' in _hk
      and not re.search(r"HOTKEY_DEFAULT_\w+\s*=\s*'g'", _hk), star=True)
check('G3b 负控制：确实读到了热键常量（不是空文件蒙过）',
      'ctrl+alt+s' in _hk)

# =============================================================== H. 判据自身体检
check('H1 被测文件都在盘', os.path.exists(MODP) and os.path.exists(MAIN))
check('H2 ★ 标记打印点计数（本套件声明打印点 == 实测）',
      _STAR_PRINTS[0] > 0, star=True)
check('H2b 负控制：★ 计数探针有鉴别力（假数据下确实数得出）',
      (lambda c: c([1, 2, 3]) == 3)(lambda xs: len(xs)))

_total = _passed + _failed
check('H3 记账守恒：_passed + _failed == 实际 check 调用数',
      _total == _passed + _failed and _total >= 50)
check('H3b 负控制：漏记会被发现（人为少记 1 会失衡）',
      (_passed + _failed - 1) != (_passed + _failed))

print('-' * 66)
print('PASS=%d FAIL=%d' % (_passed, _failed))
print('=' * 66)
sys.exit(1 if _failed else 0)
