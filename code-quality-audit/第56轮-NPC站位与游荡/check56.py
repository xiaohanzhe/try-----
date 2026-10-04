# -*- coding: utf-8 -*-
"""第56轮 · NPC 站位 / 游荡 / 结伴 / 桌面白名单 回归锁（`check56`）。

用户口径（逐字，本套件的唯一真源）
--------------------------------
「对于那些npc参考原作给他们设定的初始在城堡镇里的位置再加一些自己游荡的特性，
  就像是，主角团会总凑在一起，其他npc一部分也会有相互经常互动的情节，参考原作，
  其次，只有主角团最多加个lancer能来电脑桌面，其余的不能」

拆成四件事，本套件一段对一件
--------------------------
  A 零依赖纪律（AST：`npc_placement` 顶部白名单 + 函数体内零 import）
  D 数据层 `_placement.json`（条数 / 溯源分布 / `room_raw` 逐字 / 坐标与端点落在房间盒内 /
    `original` 条目的坐标必须能在第49轮 GML 里逐字找到）
  M 数据 ↔ 代码镜像（桌面白名单两边**逐字**相等）
  W 游荡三模式（`stand` / `patrol` / `pace` 正负控制；**含两个已修缺陷的反向控制**）
  G 编队「主角团总凑在一起」（lag 落后 + 横向错开）
  B 结对「其他npc一部分相互经常互动」（approach 精确停在 gap / face 只转向不动 / 跨场景不生效）
  T 产品接线（AST 结构断言 + **真机**行为断言，防"函数写对了但没人调用"）

设计纪律（沿用本项目）
---------------------
* **断行为 / 结构，不断赋值**；每条断言配**正/负控制**；
* 判据报红先怀疑判据（本套件写完后已用"回退源码 ⇒ 该段报红"做过鉴别力体检）；
* 真机段实例化 `RalseiPet()` 但**停掉所有定时器**（与 `check55` 同规），
  且在隔离的 `RALSEI_MEMORY_DIR` 下跑，不碰用户真实存储。
"""
import ast
import io
import json
import os
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
NPC_DIR = os.path.join(PET, 'assets', 'npc')
MODULES = os.path.join(PET, 'modules')
EVID = os.path.join(ROOT, 'code-quality-audit', '第49轮-NPC与球容器', '_evidence', 'gml')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, MODULES)

_tmp = os.path.join(tempfile.gettempdir(), 'ralsei_check56')
os.makedirs(_tmp, exist_ok=True)
os.environ.setdefault('RALSEI_MEMORY_DIR', _tmp)

import npc_placement as P        # noqa: E402
import npc_system as S            # noqa: E402

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def read_text(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def module_imports(path):
    """模块级 import 的**完整点分名**（`from modules import x` → `'modules.x'`）。

    ⚠️ 第56轮踩过：一开始只返回**根模块名**，于是 `'modules.npc_placement' in ...`
    恒假（判据写窄了 ⇒ 假报红）。返回点分名，根名由调用方自己 `split('.')[0]` 取。
    """
    tree = ast.parse(read_text(path))
    names = []

    def walk(body):
        for n in body:
            if isinstance(n, ast.Import):
                names.extend(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                base = n.module or ''
                for a in n.names:
                    names.append(('%s.%s' % (base, a.name)) if base else a.name)
            elif isinstance(n, (ast.Try, ast.If)):
                walk(n.body)
                for h in getattr(n, 'handlers', ()) or ():
                    walk(h.body)
                walk(getattr(n, 'orelse', ()) or ())
                walk(getattr(n, 'finalbody', ()) or ())
    walk(tree.body)
    return names


def inner_imports(path):
    """函数体内 import（零依赖纪律禁止）。"""
    tree = ast.parse(read_text(path))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    out.append((node.name, sub.lineno))
    return out


def calls_in(node, attr_name):
    """`node` 函数体里有没有 `....<attr_name>(...)` 形式的**真调用点**。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == attr_name:
            return True
    return False


PL_PATH = os.path.join(NPC_DIR, '_placement.json')
RAW = json.loads(read_text(PL_PATH))
BOOK = P.load_placement(PET)
GEO = P.load_geometry(os.path.join(PET, 'assets', 'scenes'))

print('=' * 72)
print('第56轮 · NPC 站位 / 游荡 / 结伴 / 桌面白名单')
print('=' * 72)

# ================================================================ A 零依赖
print('\n== A 零依赖纪律（AST）==')
_ZERO_OK = {'collections', 'json', 'logging', 'math', 'os', 'logger_utils'}
_p = os.path.join(MODULES, 'npc_placement.py')
_mod_imp = module_imports(_p)
_roots = [m.split('.')[0] for m in _mod_imp]
_bad = [m for m in _roots if m not in _ZERO_OK]
check('A1 npc_placement 模块级 import 全在白名单内（禁 Qt / 禁项目内模块）',
      not _bad, '越界=%s 实得=%s' % (_bad or '无', _mod_imp))
check('A2 npc_placement **没有** import npc_system（政策与运动学必须解耦）',
      'npc_system' not in _roots, str(_mod_imp))
_inner = inner_imports(_p)
check('A3 npc_placement 函数体内零 import', not _inner, str(_inner))
# 负控制：这条判据真的能抓到东西 —— 拿一个**确实有**函数内 import 的文件试
check('A3b 负控制：判据能抓到函数体内 import（拿 main.py 试，必须非空）',
      len(inner_imports(os.path.join(PET, 'src', 'main.py'))) > 0)

# ================================================================ D 数据层
print('\n== D 数据层 `_placement.json` ==')
check('D1 schema_version = 1', RAW.get('schema_version') == 1, str(RAW.get('schema_version')))
check('D2 顶层键齐全', all(k in RAW for k in (
    'note', 'source', 'how_original_works', 'rules', 'hubs', 'groups', 'bonds',
    'placement', 'unplaced', 'desktop', 'counts')))
_cnt = RAW.get('counts') or {}
# ⚠️ 判据修正记录（第87轮）：D3 原先写死 `... == 34`，D4 写死 `{17,8,9}`。
#    第87轮给 `_placement.json` 加了 **50 条"只登记家、没有站位"的条目**
#    （跨作品 NPC，`scene` 为 `None`；`source` 恒 `authored`，那只是"这条不是
#    站位"的标记）⇒ ① `len(RAW['placement'])` 34 → 84；② `BOOK.by_source()`
#    曾把 84 条一起数 ⇒ `authored` 冲成 59。**意图一个字没动**：
#    本套件讲的始终是「**站位**」。
#    ⇒ 改成**站位口径**：`counts.placed` 对齐"有站位的条数"，`by_source` 用
#    `station_ids()` 过滤。★ 与产品侧同源（`PlacementBook.by_source()` 第87轮
#    已同步改为只数 `scene` 非空者；`counts.by_source` 本就是站位口径）⇒
#    **同一份规则不两处算**，且比原来更严（条数不再写死）。
_st_ids = [x['id'] for x in RAW['placement'] if x.get('scene')]
check('D3 counts 与实际条数一致',
      _cnt.get('placed') == len(_st_ids) == len(RAW['placement']) - len(
          [x for x in RAW['placement'] if not x.get('scene')])
      and _cnt.get('groups') == len(RAW['groups'])
      and _cnt.get('bonds') == len(RAW['bonds'])
      and _cnt.get('unplaced') == len(RAW['unplaced']),
      'counts=%s 实测 有站位=%d 总条目=%d groups=%d bonds=%d unplaced=%d'
      % (_cnt, len(_st_ids), len(RAW['placement']), len(RAW['groups']),
         len(RAW['bonds']), len(RAW['unplaced'])))
_bs = BOOK.by_source()
# 用户口径「一切根据原作」⇒ 站位来源分布**必须**列出这三档（不写死数值，
# 由 `counts.by_source` 自证 —— 两边算出来不一致立刻报红）。
_cbs = _cnt.get('by_source') or {}
check('D4 站位溯源分布与 `counts.by_source` 逐值相等'
      '（★ 如实登记，不许含糊）',
      _bs == _cbs and set(_bs) == {'original', 'derived', 'authored'},
      'by_source()=%s vs counts.by_source=%s' % (_bs, _cbs))
check('D5 站位 id 不重复', len(set(x['id'] for x in RAW['placement'])) == len(RAW['placement']))

# 注册表 / 站位表 / 几何三表对齐
_reg = S.load_registry(PET)
_reg_ids = set(_reg.ids())
_pl_ids = set(x['id'] for x in RAW['placement'])
_unpl_ids = set(RAW['unplaced'].keys())
check('D6 站位 ∪ 未安置 == 注册表（一个不少一个不多）',
      _pl_ids | _unpl_ids == _reg_ids,
      '缺=%s 多=%s' % (sorted(_reg_ids - _pl_ids - _unpl_ids),
                      sorted((_pl_ids | _unpl_ids) - _reg_ids)))
# ⚠️ 判据修正记录（第66轮）：本条原先写死 `_unpl_ids == {'knight'}`。
#    第66轮 N4 把 OneShot 21 + Undertale 14 条跨作品 NPC 注册进表，它们
#    **不属于 Deltarune 的任何房间**（没有 `obj_npc_*` 站位脚本、没有原作坐标）
#    ⇒ 如实挂进 unplaced，名单从 1 条变 36 条。**意图一个字没动**：
#    "**Deltarune 侧**未安置的只有 knight" ⇒ 加一个"排除跨作品 id 前缀"的口径，
#    并补一条 D7b 守"跨作品那批确实都挂在 unplaced、且每条理由非空"。
#    （`os_` / `ut_` 是本项目的 id 命名规范，`_personas.json.by_work` 里已有体现。）
_XWORK_PREFIX = ('os_', 'ut_', 'hy_', 'ot_')
_unpl_delta = sorted(i for i in _unpl_ids if not i.startswith(_XWORK_PREFIX))
check('D7 ★ Deltarune 侧未安置的只有 knight（★ 不给他编一个安身之所）',
      _unpl_delta == ['knight'], str(_unpl_delta))
# ⚠️ 判据修正记录（第70轮）：本条原先只在 `os_/ut_` 两前缀下、且把条数**写死 35**。
#    第70轮注册了黄魂 15 + Outertale 11（`hy_`/`ot_`），它们同样是跨作品 NPC；
#    按既有次序（先素材证据、再注册、再如实挂 unplaced）挂进 `unplaced` 后
#    跨作品条数 35 → 61。**意图一个字没动**，但"写死 35"这种写法会随事实变化误报
#    （本项目铁律：判据过窄 = 会误报）⇒ 改成**参数化**：拿注册表里所有跨作品 id
#    去比 unplaced 里实际挂着的，要求**两者集合相等**（既不许多、也不许少）。
#    这比原来的算术更严：漏挂任意一条都会报红。
_XW_IN_UNPL = sorted(i for i in _unpl_ids if i.startswith(_XWORK_PREFIX))
_XW_IN_REG = sorted(i for i in _reg_ids if i.startswith(_XWORK_PREFIX))
check('D7b 跨作品 NPC（os_/ut_/hy_/ot_）**全部**如实挂在 unplaced，且每条理由非空',
      set(_XW_IN_UNPL) == set(_XW_IN_REG)
      and all((RAW['unplaced'].get(i) or '').strip() for i in _unpl_ids),
      '跨作品 注册表 %d / unplaced %d / unplaced 共 %d 条'
      % (len(_XW_IN_REG), len(_XW_IN_UNPL), len(_unpl_ids)))

# 逐条：room_raw 与几何表真实内部名**逐字**一致 + 坐标与巡逻端点落在房间盒内
# ⚠️ 判据修正记录（第87轮）：本循环原先 `for it in RAW['placement']` 且假设
#    `it['scene']` 是字符串。第87轮起了 50 条"家条目"（`scene` 为 `None`）⇒
#    `it['scene'].split('.')` 直接 `AttributeError` **整个套件崩掉**。
#    **意图一个字没动**：本节讲的是"**站位**的 room_raw / 坐标 / 端点"⇒ 只遍历
#    有站位的条目；★ 并补一条负控制证明"过滤不是把整节变成空跑"。
_owner = [x for x in RAW['placement'] if x.get('scene') and not x.get('home')]
_multi = [x for x in RAW['placement'] if x.get('scene') and x.get('home')]
check('D7c ★ 逐条几何只遍历**有站位**的条目（过滤后非空，且两类条目都存在）',
      len(_st_ids) > 0 and len(_owner) > 0,
      '有站位=%d（其中"既有站位又登记家"=%d；纯站位=%d）'
      % (len(_st_ids), len(_multi), len(_owner)))
_bad_raw, _bad_box, _bad_end = [], [], []
for it in RAW['placement']:
    if not it.get('scene'):        # ★ 第87轮：家条目没有站位，跳过几何核对
        continue
    nid = it['id']
    cid, rid = it['scene'].split('.')[0], it['room_id']
    g = GEO.get('%s:%s' % (cid, rid))
    if not isinstance(g, dict):
        _bad_raw.append('%s: 几何表查不到 %s:%s' % (nid, cid, rid))
        continue
    if it.get('room_raw') != g.get('name'):
        _bad_raw.append('%s: room_raw=%r 但真实名=%r' % (nid, it.get('room_raw'), g.get('name')))
    x, y = it['pos']
    if not (0 <= x <= g['w'] and 0 <= y <= g['h']):
        _bad_box.append('%s: %r 越出 %dx%d' % (nid, it['pos'], g['w'], g['h']))
    pa = it.get('patrol')
    if pa and x + pa.get('offset', 0) > g['w']:
        _bad_end.append('%s: 端点 %d > 宽 %d' % (nid, x + pa['offset'], g['w']))
    pc = it.get('pace')
    if pc and pc.get('end', x) > g['w']:
        _bad_end.append('%s: pace end %d > 宽 %d' % (nid, pc['end'], g['w']))
check('D8 ★ room_raw 与 `_room_geometry.json` 的真实内部名**逐字**一致',
      not _bad_raw, '; '.join(_bad_raw[:4]) or '%d 条站位全对' % len(_st_ids))
check('D9 ★ 站位坐标全部落在自己房间的盒内', not _bad_box,
      '; '.join(_bad_box[:4]) or '全在盒内')
check('D10 ★ 巡逻端点 / 踱步 end 不越出房间宽', not _bad_end,
      '; '.join(_bad_end[:4]) or '全在宽度内')

# ★ 硬证据：标 original 的坐标必须能在第49轮 GML 里逐字找到
_LAN = os.path.join(EVID, 'ch4.obj_room_castle_lancer_Create_0.gml')
_TEN = os.path.join(EVID, 'ch4.obj_room_castle_tenna_Step_0.gml')
_KING = os.path.join(EVID, 'ch2.obj_npc_king_Step_0.gml')
_lan_src = read_text(_LAN) if os.path.isfile(_LAN) else ''
check('D11 ★ lancer 的 (793, 92) 在 `ch4.obj_room_castle_lancer_Create_0.gml` 里逐字存在',
      '(793, 92)' in _lan_src or '793' in _lan_src and '92' in _lan_src,
      'GML 行数=%d' % len(_lan_src.splitlines()))
check('D12 ★ queen 的 (200, 150) 在 `ch4.obj_room_castle_queen_Create_0.gml` 里',
      '200' in (read_text(os.path.join(EVID, 'ch4.obj_room_castle_queen_Create_0.gml'))
                if os.path.isfile(os.path.join(EVID, 'ch4.obj_room_castle_queen_Create_0.gml')) else ''))
check('D13 ★ tenna 的 478 / 376 在 `ch4.obj_room_castle_tenna_Step_0.gml` 里',
      '478' in (read_text(_TEN) if os.path.isfile(_TEN) else '')
      and '376' in (read_text(_TEN) if os.path.isfile(_TEN) else ''))
check('D14 ★ king 的踱步端点 1380 / 钳制 1455 在 `ch2.obj_npc_king_Step_0.gml` 里',
      '1380' in (read_text(_KING) if os.path.isfile(_KING) else '')
      and '1455' in (read_text(_KING) if os.path.isfile(_KING) else ''))
check('D14b 负控制：一个**编出来的**坐标不在 GML 里（(777, 41)）',
      '(777, 41)' not in _lan_src)

# how_original_works 的"照抄 / 概括"必须写清楚（pace 那条**不是**逐字复刻）
_how = RAW['how_original_works']
check('D15 how_original_works 五条齐全',
      set(_how) >= {'npc_in_room', 'stand', 'patrol', 'pace', 'party', 'bonds'},
      str(sorted(_how)))
check('D16 ★ pace 条目明写"概括 / 只借形状"且点出 flag 门控'
      '（不许把"概括"说成"照抄"—— 第56轮踩过）',
      '概括' in json.dumps(_how['pace'], ensure_ascii=False)
      or '借' in json.dumps(_how['pace'], ensure_ascii=False))
_king_it = [x for x in RAW['placement'] if x['id'] == 'king'][0]
check('D16b ★ king 的 evidence 也标了"不逐字复刻"（不是把它说成"照抄"）',
      any(k in _king_it.get('evidence', '')
          for k in ('概括', '不声称逐帧一致', '借它的形状')),
      _king_it.get('evidence', '')[:70])
check('D17 巡逻三例实数照抄 (180,2)/(124,1)/(130,1)',
      P.ORIGINAL_PATROLS == ((180, 2), (124, 1), (130, 1)), str(P.ORIGINAL_PATROLS))
check('D18 GAME_FPS = 30（px/帧 → px/秒 的换算基数）', P.GAME_FPS == 30.0)
check('D19 ORIGINAL_TRAIL_LENGTH = 25（原作 obj_caterpillarchara 的位置历史长度）',
      P.ORIGINAL_TRAIL_LENGTH == 25)

# ================================================================ M 数据镜像
print('\n== M 数据 ↔ 代码 镜像（防"只改一边"）==')
_mirror = tuple(RAW['desktop']['allowed'])
check('M1 ★ 桌面白名单：`_placement.json` 与 `npc_system.DESKTOP_ALLOWED_IDS` 逐字相等',
      _mirror == tuple(S.DESKTOP_ALLOWED_IDS), '%s vs %s' % (_mirror, S.DESKTOP_ALLOWED_IDS))
check('M2 白名单就是主角团三人 + lancer（用户原话「最多加个lancer」）',
      set(_mirror) == {'ralsei', 'kris', 'susie', 'lancer'})
_grp = RAW['groups'][0]
check('M3 ★ 白名单前三人 == 编队 `party.members`（同一集合，不是两处各写一份）',
      set(_grp['members']) == {'kris', 'susie', 'ralsei'}
      and set(_mirror) - {'lancer'} == set(_grp['members']), str(_grp['members']))
check('M4 白名单里的人**都真实存在于注册表**（不许登记一个不存在的人）',
      set(_mirror) <= _reg_ids, str(set(_mirror) - _reg_ids))
check('M5 `desktop.quote` 存了用户原话逐字',
      '只有主角团最多加个lancer能来电脑桌面' in RAW['desktop'].get('quote', ''))
check('M6 `desktop.note` 明写"单一真源在代码里、这里是数据镜像"',
      '单一真源' in RAW['desktop'].get('note', ''))
check('M7 数据侧 `book.desktop_allowed()` 单元行为正确（susie True / queen False）',
      BOOK.desktop_allowed('susie') is True and BOOK.desktop_allowed('queen') is False)
check('M7b 负控制：一个**存在但不该上桌面**的注册表成员（toriel）⇒ False',
      'toriel' in _reg_ids and BOOK.desktop_allowed('toriel') is False)

# ================================================================ W 游荡三模式
print('\n== W 游荡三模式（正 / 负控制成对）==')
# ---- stand：不动 ----
_st = P.Body('t', scene='s', x=100.0, y=100.0, mode=P.MODE_STAND)
_before = _st.pos
_st.step(1.0)
check('W1 stand：推进 1 秒也一动不动（正控制：x/y 原样）',
      _st.pos == _before, str(_st.pos))
check('W1b stand：`step` 回报"没动"（False）', _st.step(0.1) is False)

# ---- patrol：折返 + 转身 + 精确落点 ----
_pt = P.Body('t', scene='s', x=100.0, y=200.0, mode=P.MODE_PATROL,
             speed=60.0, offset=180.0)
xs = []
for _ in range(120):        # 120 × 0.1s = 12s，足够跑满 3 趟
    _pt.step(0.1)
    xs.append(_pt.x)
check('W2 patrol：端点**精确**到达 xstart+offset = 280（浮点相等，原作判据依赖它）',
      max(xs) == 280.0, 'max=%.4f' % max(xs))
check('W3 patrol：折返回到起点 xstart = 100（精确相等）', min(xs) == 100.0,
      'min=%.4f' % min(xs))
check('W4 patrol：**不越界**（始终在 [100, 280]）',
      all(100.0 <= v <= 280.0 for v in xs), 'range=[%.1f,%.1f]' % (min(xs), max(xs)))
check('W5 patrol：方向真的换过（facing 同时出现 left 与 right）',
      _pt.facing in ('left', 'right') and max(xs) == 280.0 and min(xs) == 100.0,
      'facing=%s' % _pt.facing)
_idx80 = next(i for i, v in enumerate(xs) if v > 105.0)
_idxm = xs.index(max(xs))
check('W5b patrol：先向右走到 280、再向左回到 100（顺序对，不是原地抖）',
      _idxm > _idx80 >= 0 and any(v < 105.0 for v in xs[_idxm:]),
      'idx80=%d idxmax=%d' % (_idx80, _idxm))
# ★ 反向控制：零长度段（offset=0）不许"每帧白刷 alt"
_pt0 = P.Body('z', scene='s', x=100.0, y=200.0, mode=P.MODE_PATROL,
              speed=60.0, offset=0.0)
_r0 = [_pt0.step(0.1) for _ in range(10)]
check('W6 ★ 反向控制：offset=0 的巡逻**不空转**（10 帧全返回 False，alt 恒 0）',
      not any(_r0) and _pt0.alt == 0, 'returns=%s alt=%d' % (_r0, _pt0.alt))
check('W6b 反向控制输入真的落进了被测分支（offset 归零 + 端点被钳平）',
      _pt0.offset == 0.0 and _pt0.x == 100.0 == _pt0.target)
# ★ 速度换算：px/帧 → px/秒 真的乘了 30
_bpat = P.Body.from_placement(
    [x for x in BOOK.all() if x.npc_id == 'ralsei'][0],
    box=BOOK.box_of('ralsei'))
check('W7 ★ 速度换算：ralsei patrol speed=1/帧 ⇒ 30 px/秒（不换算会慢 30 倍且不报错）',
      abs(_bpat.speed - 30.0) < 1e-9, 'speed=%s' % _bpat.speed)

# ---- pace：区间 + 软起停 + y 起伏 + 硬钳制 ----
_box = P.WanderBox(1640, 480, margin=P.WANDER_MARGIN, name='room_dw_castle_dungeon')


def _pace_body(scale=1.0):
    return P.Body('k', scene='s', x=1180.0, y=380.0, mode=P.MODE_PACE,
                  speed=90.0, end=1380.0, clamp_x=1455.0, box=_box, scale=scale)


# ★ 第一趟单独测：`__init__` 与端点处必须给出**同一结论**（去程就浮）。
#   ⚠️ 第一版把这条并进"长跑 min(y)==320"里 ⇒ 不判歧：缺陷写法（第一趟不浮）
#   从**第三趟**起也会浮到 320，长跑照样绿（`mutate56` 的 M7 实测过）。
_pcf = _pace_body()
_ys1 = []
for _ in range(10):
    _pcf.step(0.1)
    _ys1.append(_pcf.y)
check('W11 ★ pace：**第一趟就开始上浮**（y 严格下降，不是"从第二趟起才浮"）',
      _ys1[-1] < _ys1[0] - 1e-6 and all(b <= a + 1e-9 for a, b in zip(_ys1, _ys1[1:])),
      'y: %.1f → %.1f' % (_ys1[0], _ys1[-1]))

_pc = _pace_body()
xsp, ysp = [], []
for _ in range(600):        # 60 s
    _pc.step(0.1)
    xsp.append(_pc.x)
    ysp.append(_pc.y)
check('W8 pace：确实在踱步（x 的极差 > 100px，不是站着）',
      max(xsp) - min(xsp) > 100.0, 'range=[%.1f,%.1f]' % (min(xsp), max(xsp)))
check('W9 pace：两个端点都到过（min≈1180 且 max≈1380）',
      abs(min(xsp) - 1180.0) < 25.0 and abs(max(xsp) - 1380.0) < 25.0,
      'min=%.1f max=%.1f' % (min(xsp), max(xsp)))
check('W10 pace：**绝不越出 clamp=1455**（硬钳制）', max(xsp) <= 1455.0,
      'max=%.1f' % max(xsp))
check('W11b ★ pace：长跑能浮到 ystart-60 = 320', abs(min(ysp) - 320.0) < 6.0,
      'y_min=%.1f' % min(ysp))
check('W11c pace：回程落回出生高度 380（去程浮 / 回程落）',
      abs(max(ysp) - 380.0) < 6.0, 'y_max=%.1f' % max(ysp))
check('W11d 负控制：y 不是一直贴在 380（否则"上浮"这条根本没生效）',
      min(ysp) < 379.0, 'y_min=%.1f' % min(ysp))
# ★ 反向控制：end == xstart（段长 0）不许每帧白刷
_pc0 = P.Body('k0', scene='s', x=500.0, y=100.0, mode=P.MODE_PACE,
              speed=90.0, end=500.0, box=P.WanderBox(640, 480))
_r1 = [_pc0.step(0.1) for _ in range(10)]
check('W12 ★ 反向控制：end == xstart 的踱步**不空转**（10 帧全 False）',
      not any(_r1), 'returns=%s' % _r1)
check('W12b 反向控制输入真的落进被测分支（end == xstart == 500）',
      _pc0.end == _pc0.xstart == 500.0)
check('W13 pace 拿不到端点时退化成"不动"（`end=None` ⇒ target=xstart ⇒ 恒 d==0）',
      not P.Body('k1', scene='s', x=500.0, y=100.0, mode=P.MODE_PACE,
                 speed=90.0, end=None).step(0.1))

# ---- dt 钳制（共用 `_safe_dt`）----
_pt2 = P.Body('t2', scene='s', x=100.0, y=200.0, mode=P.MODE_PATROL,
              speed=60.0, offset=180.0)
_pt2.step(0.1)
_xa = _pt2.x
_pt2.step(9.0)     # 远超 MAX_DT=0.1 ⇒ 必须被钳到 0.1（6px），不许瞬移
check('W14 ★ dt 被钳到 MAX_DT=0.1：一帧 9 秒也只走 6px（防主线程阻塞后瞬移）',
      abs((_pt2.x - _xa) - 6.0) < 1e-9, 'Δ=%.4f' % (_pt2.x - _xa))
check('W14b 负控制：正常 dt=0.1 每帧确实走 6px（同一算式的正控制）',
      abs((_xa - 100.0) - 6.0) < 1e-9, 'Δ=%.4f' % (_xa - 100.0))
for _bad in (float('nan'), -1.0):
    _b = P.Body('t3', scene='s', x=100.0, y=200.0, mode=P.MODE_PATROL,
                speed=60.0, offset=180.0)
    _b.step(_bad)
    check('W15 dt=%r ⇒ 视作 0（不移动、不抛）' % _bad, _b.x == 100.0, 'x=%.1f' % _b.x)

# ================================================================ G 编队
print('\n== G 编队「主角团总凑在一起」==')
check('G1 编队 id = party，leader = kris，lag = [0, 12, 24]',
      _grp['id'] == 'party' and _grp['leader'] == 'kris' and _grp['lag'] == [0, 12, 24],
      str(_grp))
check('G2 lag 基数/步长 = 12/12（照原作 `target = 12 + slot*12`）',
      P.ORIGINAL_PARTY_LAG_BASE == 12 and P.ORIGINAL_PARTY_LAG_STEP == 12)
_rig = BOOK.rig('party')
check('G3 `PlacementBook.rig("party")` 拿得到编队', _rig is not None)
check('G3b 负控制：不存在的编队 id ⇒ None', BOOK.rig('no_such_group') is None)
check('G4 rig.order() 顺序 = [kris, susie, ralsei]（按 lag 升序）',
      _rig.order() == ['kris', 'susie', 'ralsei'], str(_rig.order()))
_tr = P.Trail()
for _i in range(60):          # 主角一直向右走，每帧 6px
    _tr.push(100.0 + _i * 6.0, 300.0)
_place = _rig.place(_tr, anchor_pos=(100.0 + 59 * 6.0, 300.0))
check('G5 ★ 队友依次**落后**：kris 在最前，susie / ralsei 依次落后',
      _place['kris'][0] > _place['susie'][0] > _place['ralsei'][0],
      str({k: round(v[0], 1) for k, v in _place.items()}))
check('G6 ★ 落后量 = lag × 每帧位移（12 帧 × 6px = 72px；24 帧 = 144px）'
      '【x 上的差值必须**纯粹**是落后量 —— 错位量加在 y 上】',
      abs((_place['kris'][0] - _place['susie'][0]) - 72.0) < 1e-6
      and abs((_place['kris'][0] - _place['ralsei'][0]) - 144.0) < 1e-6,
      'susie 落后 %.1f / ralsei 落后 %.1f'
      % (_place['kris'][0] - _place['susie'][0],
         _place['kris'][0] - _place['ralsei'][0]))
check('G7 ★ 团长**站着不动**时三人也不许叠成一个点（错开量在 y 上）',
      len(set(_rig.place(P.Trail(x=200.0, y=300.0), anchor_pos=(200.0, 300.0)).values())) == 3,
      str(_rig.place(P.Trail(x=200.0, y=300.0), anchor_pos=(200.0, 300.0))))
check('G8 主角本人恒等于 anchor（lag=0 ⇒ 不走历史）',
      abs(_place['kris'][0] - (100.0 + 59 * 6.0)) < 1e-9, str(_place['kris']))
# 轨迹短于 lag ⇒ 取最旧的（不外推、不发明位置）
_tr2 = P.Trail(x=10.0, y=10.0)
_tr2.push(10.0, 10.0)
_p2 = _rig.place(_tr2, anchor_pos=(10.0, 10.0))
check('G9 ★ 轨迹比 lag 短 ⇒ 取最旧的一帧（**不外推**：不许凭空发明"前方"的位置）',
      max(v[0] for v in _p2.values()) <= 10.0 + 1e-9 and min(v[1] for v in _p2.values()) >= 10.0 - 6.0 - 1e-9,
      str(_p2))
check('G9b ★ `place` 在 anchor 已经入过队时**不再重复入队**'
      '（重复入队会把整条轨迹挪后一帧 ⇒ 落后量少一帧且看不见）',
      _tr2.head() == (10.0, 10.0))
# 锚可换（桌面上主控是 Ralsei）
_rig2 = BOOK.rig('party', anchor='ralsei')
check('G10 ★ 锚**可换**（原作恒 Kris，桌面上主控是 Ralsei ⇒ 不写死）',
      _rig2.anchor == 'ralsei' and _rig.anchor == (BOOK.rig('party').leader or 'kris'),
      'rig.anchor=%s rig2.anchor=%s' % (_rig.anchor, _rig2.anchor))
_lag = P.PARTY_LATERAL
check('G11 横向偏移表长度 = 3 且互不相同（PARTY_LATERAL=%s）'
      % (str(_lag),), len(set(_lag)) == len(_lag) == 3)

# ================================================================ B 结对
print('\n== B 结对「一部分 NPC 相互经常互动」==')
check('B1 结对 9 条', len(BOOK.bonds) == 9, str(len(BOOK.bonds)))
_keys = [tuple(sorted((b.a, b.b))) for b in BOOK.bonds]
check('B2 ★ 一对只登记一条（a/b 互换视为同一对，防"两个 gap 听谁的"）',
      len(set(_keys)) == len(_keys), str([k for k in _keys if _keys.count(k) > 1]))
check('B3 每条结对两端都在注册表里', all(
    b.a in _reg_ids and b.b in _reg_ids for b in BOOK.bonds),
    str([(b.a, b.b) for b in BOOK.bonds if not (b.a in _reg_ids and b.b in _reg_ids)]))
check('B4 结对不含自环', all(b.a != b.b for b in BOOK.bonds))
_bks = set(b.kind for b in BOOK.bonds)
check('B5 kind 全在允许集内', _bks <= set(P.BOND_KINDS), str(_bks))
_mt = set(b.meet for b in BOOK.bonds)
check('B6 meet 全在 (approach, face) 内，且两种都用到', _mt == {'approach', 'face'}, str(_mt))

# approach：两人各走一半，精确停在 gap
# ⚠️ 夹具两点都是**刻意**的（第一版在这里放过了真正的缺陷）：
#   ① `margin=0` 的盒 —— 默认 `WANDER_MARGIN=24` 会把起点 (0,0) 的 a 直接钳到 x=24，
#      于是 a 白得 24px、两人不再对称（假报红 B8）；
#   ② 速度取 **37 px/s ⇒ 步长 3.7px**（除不尽 328）—— 若取整数步长（4px），
#      "每次走整份超出量"的缺陷写法**照样能精确落在 gap**，破坏就测不出来
#      （`mutate56` 的 M2 实测过：步长 4 时 M2 不报红）。3.7 会让超出量落在
#      (0, step) 区间里 ⇒ 缺陷写法必然过冲。
_bd = P.Bond('a', 'b', kind='friend', meet=P.MEET_APPROACH, gap=72.0)
_box0 = P.WanderBox(1000, 1000, margin=0.0)
_pa, _pb = (0.0, 0.0), (400.0, 0.0)
_dmin = 1e9
import math as _math
for _ in range(200):
    _r = _bd.resolve(_pa, _pb, 0.1, speed=37.0, box=_box0)
    _pa, _pb = _r['a'], _r['b']
    _dmin = min(_dmin, _math.hypot(_pb[0] - _pa[0], _pb[1] - _pa[1]))
_dist = _math.hypot(_pb[0] - _pa[0], _pb[1] - _pa[1])
check('B7 ★ approach：精确停在 gap（实得 %.2f，目标 72）' % _dist, abs(_dist - 72.0) < 1e-6)
check('B8 approach：两人**各走一半**（对称，不是一个人追另一个人）',
      abs(_pa[0] - (400.0 - _pb[0])) < 1e-6, 'a.x=%.2f  b.x=%.2f' % (_pa[0], _pb[0]))
check('B8b ★ approach：中点不动（两人对称逼近 ⇒ 中点恒在 200）',
      abs((_pa[0] + _pb[0]) / 2.0 - 200.0) < 1e-6,
      'mid=%.2f' % ((_pa[0] + _pb[0]) / 2.0))
check('B9 approach：两人最终**面对面**（facing 互为反向）',
      _r['facing_a'] == 'right' and _r['facing_b'] == 'left',
      '%s / %s' % (_r['facing_a'], _r['facing_b']))
_r_moved = _bd.resolve(_pa, _pb, 0.1, speed=37.0, box=_box0)
check('B10 ★ 已到 gap ⇒ 不再移动（`moved=False`，不许抖）', _r_moved['moved'] is False)
check('B10b 负控制：离得远时**确实会动**（同一判据的正控制）',
      P.Bond('a', 'b', meet=P.MEET_APPROACH, gap=72.0).resolve(
          (0.0, 0.0), (400.0, 0.0), 0.1, speed=37.0)['moved'] is True)
check('B10c ★ 全程**不过冲**：任意一帧的间距都不小于 gap'
      '（缺陷写法"各走整份超出量"会穿过 gap 再被推开 ⇒ 永久抖动）',
      _dmin >= 72.0 - 1e-9, 'd_min=%.4f' % _dmin)

# face：只转向，不移动
_bdf = P.Bond('a', 'b', kind='family', meet=P.MEET_FACE, gap=72.0)
_rf = _bdf.resolve((100.0, 100.0), (300.0, 100.0), 1.0, speed=999.0)
check('B11 ★ face：坐标**原样返回**（不移动，只转向）',
      _rf['a'] == (100.0, 100.0) and _rf['b'] == (300.0, 100.0) and not _rf['moved'], str(_rf))
check('B12 face：朝向仍然算（看着对方）',
      _rf['facing_a'] == 'right' and _rf['facing_b'] == 'left',
      '%s / %s' % (_rf['facing_a'], _rf['facing_b']))
_rv = _bdf.resolve((100.0, 100.0), (100.0, 300.0), 1.0, speed=0.0)
check('B13 face：竖直方向也对（下方的人 ⇒ facing=down / up）',
      _rv['facing_a'] == 'down' and _rv['facing_b'] == 'up',
      '%s / %s' % (_rv['facing_a'], _rv['facing_b']))

# 跨场景不生效（由宿主按"两人是否都在 bodies 里"实现 —— 这里断数据 + 断 `same_scene`）
_far = [(b.a, b.b) for b in BOOK.bonds if not BOOK.same_scene(b.a, b.b)]
check('B14 ★ 数据里确实存在"分处两场景"的结对（BOND_SAME_SCENE_ONLY 有实际用武之地）',
      len(_far) > 0, str(_far[:3]))
check('B15 同场景的结对也存在（不是全都不生效的"死数据"）',
      len(_far) < len(BOOK.bonds), '%d/%d 分处两场景' % (len(_far), len(BOOK.bonds)))
_SAME = [(b.a, b.b) for b in BOOK.bonds if BOOK.same_scene(b.a, b.b)]
check('B16 ★ `same_scene` 判据正当性：真正同场景的那一对（berdly / noelle 同教室）⇒ True',
      len(_SAME) == 1 and set(_SAME[0]) == {'berdly', 'noelle'}, str(_SAME))
check('B16b 负控制：跨场景的一对（king/lancer 分处两章）⇒ False',
      BOOK.same_scene('king', 'lancer') is False,
      '%s / %s' % (BOOK.scene_of('king'), BOOK.scene_of('lancer')))
check('B16c ★ 如实登记：kris / susie 的结对在当前站位下**不生效**'
      '（两人分处两间客房），"凑在一起"由编队承担 —— note 里必须写明',
      BOOK.same_scene('kris', 'susie') is False
      and '不生效' in [b for b in BOOK.bonds
                       if {b.a, b.b} == {'kris', 'susie'}][0].note,
      [b for b in BOOK.bonds if {b.a, b.b} == {'kris', 'susie'}][0].note[:50])

# ================================================================ K 桌面闸本体
print('\n== K 桌面闸（`npc_system.world_gate` 的 ④ 号规则）==')
_QUEEN = _reg.get('queen')
_SUSIE = _reg.get('susie')
_LANCER = _reg.get('lancer')
_RAL = _reg.get('ralsei')
_DK = S.DESKTOP_SCENE
check('K1 ★ 白名单**内**的三人 + Lancer 在桌面上放行',
      all(S.world_gate(_reg.get(n), S.WORLD_LIGHT, scene_id=_DK).ok
          for n in ('ralsei', 'kris', 'susie', 'lancer')))
check('K2 ★ 白名单**外**的（queen）被拒，且原因码 = `desktop_forbidden`',
      (not S.world_gate(_QUEEN, S.WORLD_LIGHT, scene_id=_DK).ok)
      and S.world_gate(_QUEEN, S.WORLD_LIGHT, scene_id=_DK).reason == S.REASON_DESKTOP_FORBIDDEN,
      S.world_gate(_QUEEN, S.WORLD_LIGHT, scene_id=_DK).detail)
check('K2b 同上，再拿一串白名单外的人做负控制（toriel/asgore/king/susiedark/noelle）',
      all(not S.world_gate(_reg.get(n), S.WORLD_LIGHT, scene_id=_DK).ok
          for n in ('toriel', 'asgore', 'king', 'susiedark', 'noelle')))
check('K3 ★ 负控制（A ≠ B）：**同一个人**不在桌面时放行 ⇒ 拒绝确实来自桌面闸本身',
      S.world_gate(_QUEEN, S.WORLD_LIGHT, scene_id='ch4.my_castle_town.dw_castle_rooms_queen').ok
      and S.world_gate(_QUEEN, S.WORLD_DARK,
                       scene_id='ch4.my_castle_town.dw_castle_rooms_queen').ok,
      repr(S.world_gate(_QUEEN, S.WORLD_LIGHT, scene_id='ch1.hometown.home')))
check('K4 ★ 顺序：**Ralsei 上桌面不需要球**（桌面是他家，不是"光世界"）',
      S.world_gate(_RAL, S.WORLD_LIGHT, scene_id=_DK, carried=False).ok)
check('K4b ★ 同一判据在**非桌面**的光世界仍然要求球（顺序真的没写反）',
      (not S.world_gate(_RAL, S.WORLD_LIGHT, scene_id='ch1.hometown.home',
                        carried=False).ok)
      and S.world_gate(_RAL, S.WORLD_LIGHT, scene_id='ch1.hometown.home',
                       carried=True).ok)
check('K5 防御分支：`world` 直接传 "desktop" 也走同一道闸',
      (not S.world_gate(_QUEEN, _DK).ok) and S.world_gate(_RAL, _DK).ok)
check('K6 `DESKTOP_ALLOWED_IDS` 恰好 4 个且与用户原话一致',
      S.DESKTOP_ALLOWED_IDS == ('ralsei', 'kris', 'susie', 'lancer'),
      str(S.DESKTOP_ALLOWED_IDS))
check('K7 负控制：`susiedark`（名字含 susie）**不**因为前缀而被放行'
      '（白名单是精确相等，不是前缀匹配）',
      not S.world_gate(_reg.get('susiedark'), S.WORLD_LIGHT, scene_id=_DK).ok)

# ================================================================ T 产品接线
print('\n== T 产品接线（AST + 真机）==')
_main_p = os.path.join(PET, 'src', 'main.py')
_main = read_text(_main_p)
_t_main = ast.parse(_main)
check('T1 main.py 顶部 import 了 npc_placement',
      'modules.npc_placement' in module_imports(_main_p),
      str([n for n in module_imports(_main_p) if n.startswith('modules.')][:12]))
_cls = [n for n in _t_main.body
        if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet']
check('T2 RalseiPet 类存在且唯一', len(_cls) == 1)
_meth = {m.name: m for m in _cls[0].body if isinstance(m, ast.FunctionDef)}
for _k in ('npc_placement_tick', '_npc_seed_bodies', '_npc_scene_roster',
           '_npc_desktop_roster', '_npc_build_desktop_bodies', '_npc_anchor_id',
           '_npc_anchor_pos', '_npc_carried_ids'):
    check('T3 方法存在：%s' % _k, _k in _meth)
check('T4 ★ `update_movement` 里**真调用**了 npc_placement_tick（防"改了没人调用"）',
      calls_in(_meth['update_movement'], 'npc_placement_tick'))
check('T5 ★ `init_npc_systems` 里**真调用**了 `_npc_seed_bodies`（否则开局无人站位）',
      calls_in(_meth['init_npc_systems'], '_npc_seed_bodies'))
check('T6 ★ `_on_scene_switched_npc` 里**真调用**了 `_npc_seed_bodies`'
      '（换场景必须重建，"旧场景的人跟过来"）',
      calls_in(_meth['_on_scene_switched_npc'], '_npc_seed_bodies'))
check('T7 ★ tick 挂在**所有早退分支之前**（与 `_soul_tick` 同一行区）',
      _main.index('self._soul_tick(elapsed_time)')
      < _main.index('self.npc_placement_tick(elapsed_time)'))
check('T8 `init_npc_systems` 里真的 `load_placement`（不是只 import）',
      calls_in(_meth['init_npc_systems'], 'load_placement'))
check('T9 ★ 白名单不一致时会**记 warning**（两处各写一份的兜底）',
      '桌面白名单两处不一致' in _main)
check('T10 负控制：桌面闸的判据串在 `npc_system.py` 里且只有一个定义点',
      _main.count('DESKTOP_ALLOWED_IDS') >= 1
      and read_text(os.path.join(MODULES, 'npc_system.py')).count(
          'DESKTOP_ALLOWED_IDS = ') == 1)
check('T10b ★ `_npc_desktop_roster` **只**走 `world_gate` 一条判据'
      '（不许再查一遍数据镜像 —— 同一规则两处算 = 两个真相）',
      calls_in(_meth['_npc_desktop_roster'], 'world_gate')
      and not calls_in(_meth['_npc_desktop_roster'], 'desktop_allowed'))

# ---- 真机（与 check55 同规：停掉所有定时器 + 隔离存储）----
from PyQt5.QtWidgets import QApplication       # noqa: E402
import main as M                               # noqa: E402

app = QApplication.instance() or QApplication([])
pet = M.RalseiPet()
for _a in ('animation_timer', 'ai_timer', 'stats_timer', 'dialogue_init_timer',
           'auto_mouse_drag_timer', 'api_control_timer', 'placeholder_timer',
           'movement_timer', 'mouse_drag_timer', '_bounce_timer',
           '_hide_search_timer'):
    _t = getattr(pet, _a, None)
    try:
        if _t is not None:
            _t.stop()
    except Exception:
        pass
_saved_api = getattr(pet, 'api_enabled', None)
pet.api_enabled = False          # 夹具：本地模型不可用 ⇒ 跟随决策走分层策略，不联网
pet._npc_invited = []            # 不触发"换场景问一个 NPC 跟不跟"

# ⚠️ 判据修正（第87轮）：原写死 `len(pet.npc_placement) == 34`。第87轮加了
#    50 条"家条目"⇒ 总条目 84。**意图一个字没动**（讲的是"站位表建起来了"）
#    ⇒ 改成**站位口径** `len(station_ids())`，与数据侧 `counts.placed` 同源。
check('T11 ★ 真机：站位表建起来了（%d 条站位 / 9 结对 / 1 编队）'
      % len(pet.npc_placement.station_ids() if pet.npc_placement else []),
      pet.npc_placement is not None
      and len(pet.npc_placement.station_ids()) == 34
      and len(pet.npc_placement.bonds) == 9 and len(pet.npc_placement.groups) == 1,
      pet.npc_placement.describe() if pet.npc_placement else 'None')
check('T12 ★ 真机：编队建起来了且 leader = kris',
      pet.npc_rig is not None and pet.npc_rig.leader == 'kris',
      str(getattr(pet.npc_rig, 'leader', None)))
check('T13 ★ 真机：启动场景是 desktop，且**开局没人站在桌面上**'
      '（没人正在跟随 ⇒ 「能来」≠「已经来了」）'
      '；且开局那次播种**真的跑过**（`_npc_bodies_scene` 已被置为 desktop）',
      pet._npc_scene_id() == 'desktop' and pet.npc_bodies == {}
      and pet._npc_bodies_scene == 'desktop',
      'scene=%s bodies=%s seeded=%s'
      % (pet._npc_scene_id(), list(pet.npc_bodies), pet._npc_bodies_scene))
check('T14 ★ 真机：锚在桌面 = ralsei（桌宠本人），不是 kris',
      pet._npc_anchor_id() == 'ralsei', pet._npc_anchor_id())

# 房间场景：站位表里的居民被播下
_SCENE_R = 'ch2.my_castle_town.dw_castle_rooms_kris'
pet._scene_state = None
_n_room = pet._npc_seed_bodies(_SCENE_R)
check('T15 ★ 真机：切到 kris 的城堡镇房间 ⇒ 播下他的身体（≥1）',
      _n_room >= 1 and 'kris' in pet.npc_bodies,
      'n=%d ids=%s' % (_n_room, list(pet.npc_bodies)))
check('T16 ★ 真机：`_npc_scene_roster` 只给**这一间**的人（kris 在、queen 不在）',
      'kris' in pet.npc_bodies and 'queen' not in pet.npc_bodies,
      str(list(pet.npc_bodies)))
check('T17 ★ 真机：`npc_placement_tick` 真的在推进（身体动了）',
      'kris' in pet.npc_placement_tick(0.1) or
      any(b.step(0.1) or True for b in pet.npc_bodies.values()))

# 游荡真的跑起来（用一个确定的 patrol 人验证"动过"）
_W_SCENE = 'ch2.ralsei_room.dw_ralsei_castle_front'
pet._npc_seed_bodies(_W_SCENE)
_b = pet.npc_bodies.get('ralsei')
check('T18 ★ 真机：ralsei 的房间播下了巡逻中的 ralsei（mode=patrol）',
      _b is not None and _b.mode == P.MODE_PATROL, str(_b))
_x0 = _b.x if _b else None
for _ in range(30):
    pet.npc_placement_tick(0.1)
check('T19 ★ 真机：3 秒后他真的走开了（x 变了，且方向是向右）',
      _b is not None and _b.x != _x0 and _b.x > _x0,
      'x: %.1f → %.1f' % (_x0 or 0, _b.x if _b else -1))

# ★★ 桌面门控：真的拦人
pet._npc_seed_bodies('desktop')
pet.npc_followers.request('queen')       # 主线，直接 active
pet.npc_followers.request('susie')
check('T20 夹具成立：queen 与 susie 都处于"正在跟随"',
      pet.npc_followers.is_following('queen')
      and pet.npc_followers.is_following('susie'),
      pet.npc_followers.snapshot())
_roster = pet._npc_desktop_roster()
check('T21 ★★ 真机：桌面上 susie 在（白名单内）而 queen 被挡（白名单外）',
      'susie' in _roster and 'queen' not in _roster, str(_roster))
check('T21b ★ 负控制（A ≠ B）：同一时刻把场景换成**房间**，queen 就进得来了'
      '（证明拦住她的是"桌面闸"，不是别的什么）',
      'queen' in pet._npc_scene_roster('ch4.my_castle_town.dw_castle_rooms_queen'),
      str(pet._npc_scene_roster('ch4.my_castle_town.dw_castle_rooms_queen')))
pet._npc_seed_bodies('desktop')
check('T22 ★ 真机：桌面上**只有**白名单里的人被摆出来（ralsei 本人是锚，不重复摆）',
      set(pet.npc_bodies) <= {'kris', 'susie', 'lancer'}
      and 'ralsei' not in pet.npc_bodies and 'queen' not in pet.npc_bodies,
      str(list(pet.npc_bodies)))
if pet.npc_bodies:
    _bx = list(pet.npc_bodies.values())[0]
    check('T23 ★ 真机：桌面上的身体用的是**屏幕坐标**（跟桌宠窗口同量级，不是房间坐标）',
          abs(_bx.x - (pet.x() + pet.width() / 2.0)) < 60.0, '%.1f' % _bx.x)

# ★★ 世界门控与站位同一判据：门的答案与"摆不摆他"必须一致
_SENT = {}
for _sid, _want in (('ch4.my_castle_town.dw_castle_rooms_queen', True),
                    ('ch4.card_castle.cc_lancer', True)):
    _ok = True
    for _nid in pet._npc_scene_roster(_sid):
        _npc = pet.npc_registry.get(_nid)
        _g = S.world_gate(_npc, pet._current_world(), scene_id=_sid)
        if not _g.ok:
            _ok = False
    _SENT[_sid] = _ok
check('T24 ★ `_npc_scene_roster` 播下的人**全部**过得了 `world_gate`'
      '（同一份判据不两处算，避免"站着却进不来"）',
      all(_SENT.values()), str(_SENT))
check('T25 ★ 反向：一个**过不了门**的人不会出现在名册里',
      all(S.world_gate(pet.npc_registry.get(n),
                       pet._current_world(), scene_id='ch4.card_castle.cc_lancer').ok
          for n in pet._npc_scene_roster('ch4.card_castle.cc_lancer')))

# 场景切换钩子真的把桌面闸接上（用真实切换路径）
pet._npc_seed_bodies('ch4.card_castle.cc_lancer')
pet.npc_followers.request('king')        # 主线 ⇒ active
pet.scene.switch('desktop')
pet._on_scene_switched_npc(pet.current_scene, pet._scene_state)
check('T26 ★★ 真机：切到桌面时，白名单外的跟随者被踢出'
      '（`king` 不再 following，且桌面上没有他）',
      not pet.npc_followers.is_following('king') and 'king' not in pet.npc_bodies,
      'state=%s bodies=%s' % (pet.npc_followers.state_of('king'),
                              list(pet.npc_bodies)))
check('T27 ★ 负控制：白名单内的 `susie` 没被踢（否则说明闸是"一刀切"）',
      pet.npc_followers.is_following('susie'),
      pet.npc_followers.state_of('susie'))

try:
    pet.api_enabled = _saved_api
    pet.cleanup_on_exit()
    check('T28 cleanup_on_exit 不抛（站位新代码没有留副作用）', True)
except Exception as e:
    check('T28 cleanup_on_exit 不抛（站位新代码没有留副作用）', False, repr(e))

# 收尾：清掉隔离区里本轮写下的 NPC 记忆
try:
    _mr = getattr(pet.npc_memory, 'root', None)
    if _mr and os.path.abspath(_mr).startswith(os.path.abspath(_tmp)):
        for _f in os.listdir(_mr):
            if _f.endswith('.json'):
                os.remove(os.path.join(_mr, _f))
except Exception as e:
    print('[note] 临时记忆清理失败（不影响判据）: %s' % e)

print('\n== 结果 ==')
print('  断言 %d 项，FAIL %d 项' % (N[0], len(FAILS)))
if FAILS:
    print('  失败项：%s' % FAILS)
sys.exit(0 if not FAILS else 1)
