# -*- coding: utf-8 -*-
"""第56轮 · 核心文件复检（可落盘）

按用户长期口径「调整重要核心文件时一定要记得复检」执行六类判据：
  1 可解析（.py 走 `ast.parse` —— **不用 `py_compile`**：它会落 .pyc，改变被检状态）
  2 结构自检（报告章节全在且无粘连 / `_placement.json` 顶层键 / counts 自洽 /
    站位⊎未安置 == 注册表 / 回归基线 54 套件且登记了本轮新套件）
  3 编码（无 BOM / 无 U+FFFD）
  4 恒真判据复查（本轮改动的判据脚本里不许出现"裸写常量条件"；配正/负控制）
  5 逐令牌回验（本轮**改过/删过**的令牌逐个回**该在**的文件 in 一次；
     ★ 反向：**已经不该在**的旧诊断串必须真消失）
  6 状态干净 + 改动集合 == 预期集合（`git status --porcelain` + numstat 删除量闸）

本轮"重要核心文件" = 回归锁与基线（`run_all.py` / `baseline.json` / `check52c.py`）
                     + 被多处依赖的 `main.py` / `npc_system.py` + 新增的
                     `npc_placement.py` / `_placement.json` + 本报告。

输出：`_evidence/recheck56_result.txt`（固定文件名，不依赖 stdout）。
"""
import ast
import importlib.util
import io
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EVID = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EVID, 'recheck56_result.txt')

P = lambda *a: os.path.join(ROOT, *a)
LINES, PASS, FAIL = [], [], []


def ck(cid, title, ok, detail=''):
    (PASS if ok else FAIL).append(cid)
    LINES.append('  [%s] %-5s %s%s' % ('PASS' if ok else 'FAIL', cid, title,
                                       ('  :: ' + str(detail)) if detail else ''))


def rd(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def rdb(path):
    with open(path, 'rb') as fh:
        return fh.read()


# ---- 被检文件清单（本轮动过的）-----------------------------------------
MD_REPORT = P('第56轮报告-NPC站位与游荡.md')
PLACEMENT_JSON = P('ralsei_pet', 'assets', 'npc', '_placement.json')
REGISTRY_JSON = P('ralsei_pet', 'assets', 'npc', '_registry.json')
BASELINE_JSON = P('code-quality-audit', 'regress', 'baseline.json')
RUN_ALL = P('code-quality-audit', 'regress', 'run_all.py')
CHECK56 = P('code-quality-audit', '第56轮-NPC站位与游荡', 'check56.py')
MUTATE56 = P('code-quality-audit', '第56轮-NPC站位与游荡', '_tools', 'mutate56.py')
GEN56 = P('code-quality-audit', '第56轮-NPC站位与游荡', '_tools', 'gen_placement56.py')
CHECK52C = P('code-quality-audit', '第52轮-对话与人味收口', '_tools', 'check52c.py')

PY_FILES = [
    P('ralsei_pet', 'src', 'main.py'),
    P('ralsei_pet', 'modules', 'npc_placement.py'),
    P('ralsei_pet', 'modules', 'npc_system.py'),
    RUN_ALL,
    CHECK56,
    MUTATE56,
    CHECK52C,
]
if os.path.isfile(GEN56):
    PY_FILES.append(GEN56)
# 判据 4 只扫"本轮改过/新增的**判据**脚本"（产品代码里没有 check()）
JUDGE_FILES = [CHECK56, CHECK52C]
JSON_FILES = [PLACEMENT_JSON, REGISTRY_JSON, BASELINE_JSON]
MD_FILES = [MD_REPORT]

LINES.append('=' * 72)
LINES.append('第56轮 · 核心文件复检（recheck56）')
LINES.append('=' * 72)

# ---------------------------------------------------------------- 1 可解析
LINES.append('\n【1】可解析（ast.parse；不用 py_compile，避免落 .pyc）')
_bad, _bad_json = [], []
for f in PY_FILES:
    try:
        ast.parse(rd(f), filename=f)
    except SyntaxError as e:
        _bad.append('%s: %s' % (os.path.basename(f), e))
    except OSError as e:
        _bad.append('%s: 读不到 (%s)' % (os.path.basename(f), e))
ck('1', '全部 %d 个 .py 都能 ast.parse' % len(PY_FILES), not _bad, _bad)
for f in JSON_FILES:
    try:
        json.loads(rd(f))
    except Exception as e:
        _bad_json.append('%s: %s' % (os.path.basename(f), e))
ck('1b', '全部 %d 个 .json 都能解析' % len(JSON_FILES), not _bad_json, _bad_json)

_PL = json.loads(rd(PLACEMENT_JSON))
_REG = json.loads(rd(REGISTRY_JSON))
_BASE = json.loads(rd(BASELINE_JSON))


def _ids_of(node):
    """取一组 id。

    ⚠️ 本文件第一版在这里就崩了：`unplaced` 在本项目里是 **`{id: 说明}` 字典**
      （只为了同时记下"为什么不安置"），却按 `[{id: ...}]` 去取 ⇒ `TypeError`。
      ⇒ 判据脚本自己也要容错，改成"结构变了就报 FAIL，而不是直接抛异常"。
    """
    if isinstance(node, dict):
        return set(node.keys())
    if isinstance(node, list):
        return {e if isinstance(e, str) else e.get('id') for e in node}
    return set()

# ---------------------------------------------------------------- 2 结构
LINES.append('\n【2】结构自检')
if os.path.isfile(MD_REPORT):
    _md = rd(MD_REPORT)
    _need = ['## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.', '## 7.', '## 8.']
    _miss = [s for s in _need if s not in _md]
    ck('2a', '报告章节 1~8 全在', not _miss, '缺 %r' % (_miss,))
    # "粘连"：真毛病是**标题和正文黏在同一行**。⚠️ 判据口径（沿用第55轮修正）：
    #   `#` 必须出现在**行首**，出现在中间才算粘连；否则 `### 2.1` 这种合法三级标题会被误判。
    _glue = [ln[:40] for ln in _md.splitlines()
             if '##' in ln and not ln.lstrip().startswith('#')]
    ck('2b', '报告无章节标题粘连（`#` 必须在行首）', not _glue, _glue[:3])
else:
    ck('2a', '报告章节 1~8 全在', False, '报告文件还不存在')
    ck('2b', '报告无章节标题粘连', False, '报告文件还不存在')

# 2c `_placement.json` 顶层键集合（精确相等：多一个少一个都算结构变了）
_EXPECT_KEYS = {'schema_version', 'note', 'source', 'how_original_works', 'rules',
                'hubs', 'groups', 'bonds', 'placement', 'unplaced', 'desktop',
                'counts'}
ck('2c', '_placement.json 顶层键集合 == 预期',
   set(_PL.keys()) == _EXPECT_KEYS,
   sorted(set(_PL.keys()) ^ _EXPECT_KEYS) or 'ok')

# 2d counts 自洽
_cnt = _PL['counts']
_n_npc = len(_REG['npcs'])
_by = _cnt.get('by_source') or {}
ck('2d', 'counts 自洽：placed+unplaced==注册表(%d)、by_source 求和==placed、'
         'groups/bonds/desktop_allowed 与实体条数一致' % _n_npc,
   _cnt['placed'] + _cnt['unplaced'] == _n_npc
   and sum(_by.values()) == _cnt['placed']
   and _cnt['groups'] == len(_PL['groups'])
   and _cnt['bonds'] == len(_PL['bonds'])
   and _cnt['desktop_allowed'] == len(_PL['desktop']['allowed']),
   'placed=%s unplaced=%s by_source=%s groups=%s bonds=%s allowed=%s'
   % (_cnt['placed'], _cnt['unplaced'], _by, len(_PL['groups']),
      len(_PL['bonds']), len(_PL['desktop']['allowed'])))

# 2e 站位 ⊎ 未安置 == 注册表 id 集合（**精确相等**：既不漏人，也不凭空造人）
_ids_pl = {e['id'] for e in _PL['placement']}
_ids_un = _ids_of(_PL['unplaced'])
_ids_reg = {n['id'] for n in _REG['npcs']}
ck('2e', '站位 ⊎ 未安置 == 注册表 %d 个 id（精确相等）' % _n_npc,
   (_ids_pl | _ids_un) == _ids_reg and not (_ids_pl & _ids_un),
   '缺=%r 多=%r 重叠=%r' % (sorted(_ids_reg - (_ids_pl | _ids_un)),
                          sorted((_ids_pl | _ids_un) - _ids_reg),
                          sorted(_ids_pl & _ids_un)))

# 2f 回归基线：套件数一致且登记了本轮新套件
_suites_base = set((_BASE.get('suites') or {}).keys())
ck('2f', 'baseline.json 里有 %d 个套件且**登记了** npc_place56' % len(_suites_base),
   len(_suites_base) == 54 and 'npc_place56' in _suites_base,
   'n=%d has_npc_place56=%s' % (len(_suites_base), 'npc_place56' in _suites_base))

# 2g run_all.py：SUITES 与基线一一对应；npc_place56 必须进 HERMETIC_IDS
#    （✅ 它会真构造 `RalseiPet()` ⇒ 不登记就会往用户**真实存储**写东西）
try:
    _spec = importlib.util.spec_from_file_location('_ra56', RUN_ALL)
    _ra = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_ra)
    _ids_suite = {s['id'] for s in _ra.SUITES}
    ck('2g', 'run_all.SUITES == 基线套件集合（%d 个）' % len(_ids_suite),
       _ids_suite == _suites_base, sorted(_ids_suite ^ _suites_base)[:6])
    ck('2h', 'npc_place56 已登记进 HERMETIC_IDS（真机会写真实存储 ⇒ 必须隔离）',
       'npc_place56' in _ra.HERMETIC_IDS)
    _herm_missing = sorted(i for i in _ids_suite
                           if i in ('npc_place56', 'soul_round55', 'npc_persona55')
                           and i not in _ra.HERMETIC_IDS)
    ck('2h2', '三个真机套件（npc_place56 / soul_round55 / npc_persona55）都在 HERMETIC_IDS',
       not _herm_missing, _herm_missing)
except Exception as e:                                   # noqa: BLE001
    ck('2g', 'run_all.py 可导入并读出 SUITES', False, repr(e))
    ck('2h', 'npc_place56 在 HERMETIC_IDS', False, '导入失败')
    ck('2h2', '三个真机套件都在 HERMETIC_IDS', False, '导入失败')

# ---------------------------------------------------------------- 3 编码
LINES.append('\n【3】编码（无 BOM / 无 U+FFFD）')
_bom, _rep = [], []
for f in PY_FILES + JSON_FILES + MD_FILES:
    if not os.path.isfile(f):
        continue
    _b = rdb(f)
    if _b.startswith(b'\xef\xbb\xbf'):
        _bom.append(os.path.basename(f))
    try:
        _t = _b.decode('utf-8')
    except UnicodeDecodeError as e:
        _rep.append('%s: 不是合法 UTF-8 (%s)' % (os.path.basename(f), e))
        continue
    if '\ufffd' in _t:
        _rep.append(os.path.basename(f))
ck('3a', '无 BOM', not _bom, _bom)
ck('3b', '无 U+FFFD 且都是合法 UTF-8', not _rep, _rep)

# ---------------------------------------------------------------- 4 恒真判据
LINES.append('\n【4】恒真判据复查（判据脚本里不许把常量当条件）')


def _scan_always(src, fname):
    """找出**裸写**的常量条件（`check(name, True)` 之类）。

    ⚠️ 这条判据自身在第55轮踩过两次坑，两处都保留修正：
      ① 正则直接找 `check(name, True)` —— 会把 `try/except` 里的
         `check(name, True)/check(name, False)` 全判红；可那恰恰是
         「**它到底抛没抛**」这个真判据的合法写法。
      ② 改用 AST 但范围只取到 `except` 那一行 ⇒ **没走进行体**，handler 里那句
         仍被当成"不在 try 里"，照样误报。⇒ 必须用 `node.end_lineno`。
    """
    out = []
    tree = ast.parse(src, filename=fname)
    ranges = [(n.lineno, getattr(n, 'end_lineno', n.lineno))
              for n in ast.walk(tree) if isinstance(n, ast.Try)]
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ('check', 'ok', 'ck') and len(node.args) >= 2):
            continue
        _cond = node.args[1]
        if not (isinstance(_cond, ast.Constant) and isinstance(_cond.value, bool)):
            continue
        _ln = getattr(node, 'lineno', 0)
        if not any(_lo <= _ln <= _hi for _lo, _hi in ranges):
            out.append('%s:%d %s(name, %r) 不在任何 try 里'
                       % (os.path.basename(fname), _ln, node.func.id, _cond.value))
    return out


_always = []
for f in JUDGE_FILES:
    _always.extend(_scan_always(rd(f), f))

# ★ 正控制：同一条判据套到"合成的一段裸写"上**必须**报出来（否则这条锁是空转的）
_SYNTH = "check('假装守了一条', True)\n"
_positive = bool(_scan_always(_SYNTH, 'synthetic.py'))
# ★ 负控制：`try/except` 形状**不许**被判红（那是合法写法）
_SYNTH_OK = ("try:\n    f()\n    check('x', True)\n"
             "except Exception:\n    check('x', False)\n")
_negative = not _scan_always(_SYNTH_OK, 'synthetic_ok.py')
ck('4a', '本轮 %d 个判据脚本里没有"裸写"的常量条件' % len(JUDGE_FILES),
   not _always, _always[:4])
ck('4a2', '4a 有鉴别力：合成的裸写必须被抓出（正控制）且 try/except 形状不被误报（负控制）',
   _positive and _negative, 'positive=%r negative=%r' % (_positive, _negative))

# 4b 六条**骨架判据**必须还在（它们是本轮判据的承重墙，删掉就只剩空壳）
_c56 = rd(CHECK56)
_SKELETON = [
    'D14b 负控制：一个**编出来的**坐标不在 GML 里',
    'W6 ★ 反向控制：offset=0 的巡逻**不空转**',
    'G9b ★ `place` 在 anchor 已经入过队时**不再重复入队**',
    'B10c ★ 全程**不过冲**：任意一帧的间距都不小于 gap',
    'K7 负控制：`susiedark`（名字含 susie）**不**因为前缀而被放行',
    'T10b ★ `_npc_desktop_roster` **只**走 `world_gate` 一条判据',
]
_missing = [s for s in _SKELETON if s not in _c56]
ck('4b', 'check56 的 6 条骨架判据（数据溯源 / 零长度 / 不重复入队 / 不过冲 / '
         '前缀不误放行 / 单判据）全在', not _missing, _missing)

# ---------------------------------------------------------------- 5 逐令牌
LINES.append('\n【5】逐令牌回验（改/删过的令牌逐个回原文件 in 一次）')
TOKENS_MAY = [
    # ---- 运动学层（本轮修的六个真缺陷）----
    ('def _facing_between(dx, dy)', P('ralsei_pet', 'modules', 'npc_placement.py'),
     '竖直方向也能定朝向（替掉只吃一轴的 `_facing_for`）'),
    ('    def head(self):', P('ralsei_pet', 'modules', 'npc_placement.py'),
     'Trail 取队首（判"锚点是否已入队"用）'),
    ('if trail.head() != ap:', P('ralsei_pet', 'modules', 'npc_placement.py'),
     '★ 不重复入队（否则队友落后量少一帧）'),
    ('half = min(step, rem * 0.5)', P('ralsei_pet', 'modules', 'npc_placement.py'),
     '★ 结对每人只走一半超出量（否则在 gap 附近永久抖动）'),
    ('self.y_target = (self.ystart - ORIGINAL_PACE_RISE',
     P('ralsei_pet', 'modules', 'npc_placement.py'),
     '★ pace 第一趟就上浮（与 _step_pace 端点处同一判据）'),
    ('BOND_APPROACH_SPEED = 40.0', P('ralsei_pet', 'modules', 'npc_placement.py'),
     '自创量必须显式标注（原作没有"两 NPC 互相凑近"）'),
    # ---- 政策层（需求 ④）----
    ("DESKTOP_ALLOWED_IDS = ('ralsei', 'kris', 'susie', 'lancer')",
     P('ralsei_pet', 'modules', 'npc_system.py'), '桌面白名单 = 代码侧单一真源'),
    ("REASON_DESKTOP_FORBIDDEN = 'desktop_forbidden'",
     P('ralsei_pet', 'modules', 'npc_system.py'), '拒绝原因码'),
    ('def desktop_allowed(npc)', P('ralsei_pet', 'modules', 'npc_system.py'),
     '白名单判定（精确相等，不做前缀匹配）'),
    ('if scene_id == DESKTOP_SCENE or world == DESKTOP_SCENE:',
     P('ralsei_pet', 'modules', 'npc_system.py'),
     '★ 桌面闸：scene_id 与 world 两条路都要认'),
    # ---- 接线层 ----
    ('from modules import npc_placement as npc_placement_mod',
     P('ralsei_pet', 'src', 'main.py'), '模块导入'),
    ('self.npc_placement_tick(elapsed_time)', P('ralsei_pet', 'src', 'main.py'),
     '★ update_movement 里的每帧推进点'),
    ('def npc_placement_tick(self, dt)', P('ralsei_pet', 'src', 'main.py'),
     '推进方法本体'),
    ('def _npc_seed_bodies(self, scene_id=None)', P('ralsei_pet', 'src', 'main.py'),
     '★ 播种（开局 + 每次换场景）'),
    ('def _npc_desktop_roster(self)', P('ralsei_pet', 'src', 'main.py'),
     '桌面名单（只走 world_gate）'),
    ('def _npc_scene_roster(self, scene_id)', P('ralsei_pet', 'src', 'main.py'),
     '房间名单（站位表 ∩ 注册表 ∩ world_gate）'),
    ('def _npc_anchor_id(self)', P('ralsei_pet', 'src', 'main.py'), '编队锚'),
    ('DESKTOP_PARTY_OFFSETS = (0.0, -44.0, 44.0)',
     P('ralsei_pet', 'src', 'main.py'), '桌面上的三人错位量'),
    # ---- 回归锁 ----
    ("'npc_place56'", RUN_ALL, '套件登记进 SUITES / HERMETIC_IDS'),
    # ---- 本轮修的判据诊断（不改断言）----
    ('_CONSTS_FLOOR = 1000', CHECK52C, 'A8c 改成"够不够用"的下限判据'),
    ('"顺序=%s"', CHECK52C, 'A3c/A3d 改报顺序而非绝对偏移'),
]
_tok_fail = []
for _tok, _f, _why in TOKENS_MAY:
    try:
        if _tok not in rd(_f):
            _tok_fail.append('%s 不在 %s（%s）' % (_tok[:44], os.path.basename(_f), _why))
    except OSError as e:
        _tok_fail.append('%s 读不到 (%s)' % (_f, e))
ck('5a', '本轮**新增/保留**的 %d 个令牌逐个回验在位' % len(TOKENS_MAY),
   not _tok_fail, _tok_fail)

# ★ 反向：**已经不该在**的旧诊断串必须真消失（防"以为改了其实没改到"）
TOKENS_GONE = [
    ('"lounge=%d rand=%d"', CHECK52C, 'A3c 的旧绝对偏移诊断'),
    ('"bed=%d sleep=%d"', CHECK52C, 'A3d 的旧绝对偏移诊断'),
    ('"取样数=%d" % len(MAIN_CONSTS)', CHECK52C, 'A8c 的旧字面量总数诊断'),
]
_gone_fail = []
for _tok, _f, _why in TOKENS_GONE:
    try:
        if _tok in rd(_f):
            _gone_fail.append('%s 仍在 %s（%s）' % (_tok, os.path.basename(_f), _why))
    except OSError as e:
        _gone_fail.append('%s 读不到 (%s)' % (_f, e))
ck('5b', '三条**旧的**漂移诊断串已从 check52c.py 消失', not _gone_fail, _gone_fail)

# 5c ★ 报告里的关键数字必须与**实测**一致（否则报告就是一张漂亮但失真的表）
_rep_need = [
    ('original %d / derived %d / authored %d'
     % (_by.get('original'), _by.get('derived'), _by.get('authored')),
     '数据层溯源分布'),
    ('%d 条' % len(_PL['placement']), '站位条数'),
    ('%d 条' % len(_PL['bonds']), '结对条数'),
    ('54 / 54 IDENTICAL', '全量 G2 状态'),
]
_rep_bad = []
if os.path.isfile(MD_REPORT):
    _md2 = rd(MD_REPORT)
    _rep_bad = ['报告缺 %r（%s）' % (s, w) for s, w in _rep_need if s not in _md2]
else:
    _rep_bad = ['报告文件不存在']
ck('5c', '报告里 %d 个关键数字与实测一致（数据/条数/G2 状态）' % len(_rep_need),
   not _rep_bad, _rep_bad)

# 5d ★ 记忆压缩的**逐令牌回验**：从速查本移除/改写的令牌必须能在**详版**里找到。
#    （速查本本轮撞上限：用前 9988 / 加完一度 10035 / 压后 9994，上限 10000。）
_MEM_DETAIL = P('.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
_MEM_FAST = P('.workbuddy', 'memory', 'MEMORY.md')
_MEM_TOKENS = [
    ('Q2/Q3 已裁定（50轮）', '从速查本 §11 移除的"已裁定"项原文'),
    ('H4H5／AI 失真／场景 P0／路由', '从速查本 §10 索引移除的"编号→主题"映射原文'),
    ('`dump_rooms.csx` **缺 4 项**', '从速查本 §7 压成指针的「P1 前置」原文'),
    ('objects **仅 37.4% 映射 sprite**、余为**纯逻辑锚点**（`visible=false` 不画）',
     '从速查本 §7 压成指针的「资产与场景文件」原文'),
    ('§51.10-C', 'P1 前置的指针落点'),
    ('§51.10-A', '资产与场景文件的指针落点'),
]
_mem_bad = []
try:
    _det = rd(_MEM_DETAIL)
    for _tok, _why in _MEM_TOKENS:
        if _tok not in _det:
            _mem_bad.append('%r 不在详版（%s）' % (_tok[:36], _why))
except OSError as e:
    _mem_bad.append('详版读不到 (%s)' % (e,))
ck('5d', '记忆压缩的 %d 个"被移除令牌"逐个在详版里找到（逐令牌回验）'
         % len(_MEM_TOKENS), not _mem_bad, _mem_bad)

# 5e ★ 速查本体量必须还在注入上限内（超了会被**砍尾** = 丢掉最新教训）
try:
    _fast_len = len(rd(_MEM_FAST).strip().encode('utf-16-le')) // 2
    ck('5e', '速查本 js_len(%d) <= 10000（注入上限）' % _fast_len, _fast_len <= 10000,
       '余量 %d' % (10000 - _fast_len))
except OSError as e:
    ck('5e', '速查本体量可读', False, repr(e))

# ---------------------------------------------------------------- 6 状态
LINES.append('\n【6】状态干净 + 改动集合')
try:
    _st = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         capture_output=True, text=True, encoding='utf-8',
                         timeout=120)
    _lines = [l for l in _st.stdout.splitlines() if l.strip()]
    _rd = [l for l in _lines if l[:1] in ('R', 'D')]
    ck('6a', '工作区里没有意外的改名/删除记录（R/D 行）', not _rd, _rd[:4])
    if not _lines:
        ck('6a2', '工作区干净（`git status --porcelain` 为空）', True, '(已提交)')
    else:
        LINES.append('  · git status 条目数 = %d（本轮尚未提交，属正常）' % len(_lines))
except Exception as e:                                   # noqa: BLE001
    ck('6a', 'git status 可读', False, repr(e))
try:
    _ns = subprocess.run(['git', 'diff', '--cached', '--numstat'], cwd=ROOT,
                         capture_output=True, text=True, encoding='utf-8',
                         timeout=120)
    _del = 0
    for l in _ns.stdout.splitlines():
        parts = l.split('\t')
        if len(parts) >= 3 and parts[1].isdigit():
            _del += int(parts[1])
    # ⚠️ 走**文件**而不是命令替换：`git add -A` 一旦把"临时文件的删除"也记进来，
    #    这里就是唯一的拦截点（记忆铁律：deletions > 1000 立刻停手）。
    _ns2 = subprocess.run(['git', 'diff', '--numstat'], cwd=ROOT,
                          capture_output=True, text=True, encoding='utf-8',
                          timeout=120)
    for l in _ns2.stdout.splitlines():
        parts = l.split('\t')
        if len(parts) >= 3 and parts[1].isdigit():
            _del += int(parts[1])
    LINES.append('  · 工作区+暂存区删除行数 = %d（守卫阈值 1000）' % _del)
    ck('6b', '删除行数 < 1000', _del < 1000, _del)
except Exception as e:                                   # noqa: BLE001
    LINES.append('  · numstat 读取失败（忽略）: %r' % (e,))

# ---------------------------------------------------------------- 收尾
LINES.append('')
LINES.append('-' * 72)
LINES.append('结果：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    LINES.append('失败项：%r' % (FAIL,))
LINES.append('')

if not os.path.isdir(EVID):
    os.makedirs(EVID)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(LINES) + '\n')
print('\n'.join(LINES))
raise SystemExit(0 if not FAIL else 1)
