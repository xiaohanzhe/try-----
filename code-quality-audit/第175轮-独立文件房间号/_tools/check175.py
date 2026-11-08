# -*- coding: utf-8 -*-
u"""第175轮判据：`original_room_id` 补进 87 个独立场景文件。

★★★ 本轮判据的"重心"在哪
-------------------------
补一个字段**最容易写出恒真判据**：
    "文件里有 original_room_id" —— 改前也有 1 个（desktop），改后 88 个；
    只要写成 `>= 1` 就永远绿。
所以本轮把重心放在两个**改前/改后有明确差值**的量上：

    ① **自足率**：`SceneState.from_dict(文件)` **不经 `load_scene` 的 entry 回退**
       就能拿到房间号。改前 = 2079 / 2166（2078 分片 + desktop），改后 = **2166 / 2166**。
       负控制：把某文件的字段在内存里抹掉 ⇒ 该场景立刻掉回 None。
    ② **其余一字未改**：87 个文件"除 rid 外"的指纹必须等于改前快照；
       字节增量必须恰好等于新增那一行的 utf-8 长度。

★★ 值从哪来：一律从 `_index.json` 抄同一个数（产品运行时本来就以 index 为准）。
   本轮**不重算、不猜**，所以判据查的是"文件值 == index 值"，不是"文件值合理"。

用法：python check175.py
"""
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SNAP = os.path.join(EV, 'before175.json')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
INDEX = os.path.join(SCENES, '_index.json')
ROOMS = os.path.join(SCENES, '_original_rooms.json')

sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))
from modules import scene_system as SS          # noqa: E402

#: 分母常量（写死 + 判据里独立重算，两边必须相等才会绿）
EXPECT_SCENES = 2166      # index 登记场景数
EXPECT_SOLO = 88          # 独立文件数
EXPECT_ZONE_FILES = 76    # 分片文件数
EXPECT_ZONE_SCENES = 2078 # 分片内场景数
EXPECT_FILLED = 87        # 本轮补的条数
EXPECT_SELF_BEFORE = 2079 # 改前自足数（2078 分片 + desktop）
CHECK_FLOOR = 30

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace',
                              newline='').read())


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def h_rest(d):
    x = {k: v for k, v in d.items() if k != 'original_room_id'}
    return hashlib.sha1(json.dumps(x, sort_keys=True, ensure_ascii=False)
                        .encode('utf-8')).hexdigest()


def git(*args):
    out = subprocess.run(['git'] + list(args), cwd=REPO,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return out.returncode, out.stdout.decode('utf-8', 'replace')


# ---------------------------------------------------------------------------
# 0. 装配：index / 盘上场景 / 快照
# ---------------------------------------------------------------------------
idx = jl(INDEX)
IDX_RID, IDX_CH = {}, {}
for cid, ch in ((idx or {}).get('chapters') or {}).items():
    for _aid, ar in ((ch or {}).get('areas') or {}).items():
        for sid, sc in ((ar or {}).get('scenes') or {}).items():
            r = (sc or {}).get('original_room_id')
            if isinstance(r, int) and not isinstance(r, bool):
                IDX_RID[sid] = r
                IDX_CH[sid] = cid

SOLO = sorted(f for f in os.listdir(SCENES)
              if f.endswith('.json') and not f.startswith('_'))
ZONES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.'))
SOLO_RAW = {f: jl(os.path.join(SCENES, f)) for f in SOLO}
ZONE_SC = {}
for zf in ZONES:
    for sid, sc in ((jl(os.path.join(SCENES, zf)) or {}).get('scenes') or {}).items():
        ZONE_SC[sid] = sc

SNAP_D = jl(SNAP) if os.path.isfile(SNAP) else {}

print('=' * 70)
print(u'第175轮判据 · original_room_id 补进独立场景文件')
print('=' * 70)

# ---------------------------------------------------------------------------
# A 段：分母与取证
# ---------------------------------------------------------------------------
check(u'A0 index 登记场景数 == %d（实测 %d）' % (EXPECT_SCENES, len(IDX_RID)),
      len(IDX_RID) == EXPECT_SCENES)

check(u'A1 盘上场景 == index（独立 %d + 分片 %d = %d；index %d）'
      % (len(SOLO), len(ZONE_SC), len(SOLO) + len(ZONE_SC), len(IDX_RID)),
      len(SOLO) == EXPECT_SOLO and len(ZONE_SC) == EXPECT_ZONE_SCENES
      and len(SOLO) + len(ZONE_SC) == len(IDX_RID))

check(u'A2 分片文件数 == %d（实测 %d）' % (EXPECT_ZONE_FILES, len(ZONES)),
      len(ZONES) == EXPECT_ZONE_FILES)

_z_have = sum(1 for sc in ZONE_SC.values()
              if isinstance((sc or {}).get('original_room_id'), int))
check(u'A3 分片 %d 个场景**全部**自带房间号（实测 %d）—— 这是"另一条来源已自足"的对照'
      % (len(ZONE_SC), _z_have), _z_have == len(ZONE_SC))

_desk = SOLO_RAW.get('desktop.json') or {}
check(u'A4 desktop.json 的房间号仍是 -1（桌面不是任何原作房间）',
      _desk.get('original_room_id') == -1, u'实测 %r' % (_desk.get('original_room_id'),))

_solo_ok = [f for f in SOLO if 'original_room_id' in SOLO_RAW[f]]
check(u'A5 独立文件 %d 个**全部**带房间号（实测 %d；改前只有 1 个）'
      % (len(SOLO), len(_solo_ok)), len(_solo_ok) == len(SOLO))

_mis = []
for f in SOLO:
    d = SOLO_RAW[f]
    sid = d.get('scene_id')
    if sid in IDX_RID and d.get('original_room_id') != IDX_RID[sid]:
        _mis.append((f, d.get('original_room_id'), IDX_RID[sid]))
check(u'A6 每个文件的值 == index 同一条登记（不一致 %d 条 %r）' % (len(_mis), _mis[:3]),
      not _mis)

_typ = [(f, repr(SOLO_RAW[f].get('original_room_id'))) for f in SOLO
        if not (isinstance(SOLO_RAW[f].get('original_room_id'), int)
                and not isinstance(SOLO_RAW[f].get('original_room_id'), bool))]
check(u'A7 值类型全是 int（非 bool）（异常 %d 条 %r）' % (len(_typ), _typ[:3]), not _typ)

_order = []
for f in SOLO:
    ks = list(SOLO_RAW[f])
    i = ks.index('area_name') if 'area_name' in ks else -1
    if i < 0 or i + 1 >= len(ks) or ks[i + 1] != 'original_room_id':
        _order.append(f)
check(u'A8 键顺序：`original_room_id` 紧跟 `area_name`（错位 %d 个 %r）'
      % (len(_order), _order[:3]), not _order)

# ---------------------------------------------------------------------------
# B 段：自足性 —— 本轮真正的改变
# ---------------------------------------------------------------------------
_solo_self, _solo_val = [], []
for f in SOLO:
    sid = SOLO_RAW[f].get('scene_id')
    st = SS.SceneState.from_dict(dict(SOLO_RAW[f]))     # ★ 单喂，无 entry
    if st.original_room_id is not None:
        _solo_self.append(f)
        if st.original_room_id == IDX_RID.get(sid):
            _solo_val.append(f)
check(u'B0 独立文件走 `SceneState.from_dict` **不经 entry 回退**也能拿到房间号（%d/%d；改前 1/%d）'
      % (len(_solo_self), len(SOLO), len(SOLO)),
      len(_solo_self) == len(SOLO))
check(u'B1 且拿到的值 == index（%d/%d）' % (len(_solo_val), len(SOLO)),
      len(_solo_val) == len(SOLO))

_self_total = _z_have + len(_solo_self)
check(u'B2 ★ 全盘自足率 %d/%d（改前 %d）：分片 %d + 独立 %d'
      % (_self_total, EXPECT_SCENES, EXPECT_SELF_BEFORE, _z_have, len(_solo_self)),
      _self_total == EXPECT_SCENES)

# ★★ 负控制：内存里抹掉一个文件的字段 ⇒ 立刻掉回 None（证明 B0/B1 不是恒真）
_one = 'ch1.card_castle.card_castle_1f.json'
_raw = dict(SOLO_RAW.get(_one) or {})
_raw.pop('original_room_id', None)
check(u'B3 ★★负控制：把 `%s` 的字段抹掉 ⇒ `from_dict` 得 None（%r）'
      % (_one, SS.SceneState.from_dict(_raw).original_room_id),
      SS.SceneState.from_dict(_raw).original_room_id is None)

_ls_bad = []
for f in SOLO:
    sid = SOLO_RAW[f].get('scene_id')
    st = SS.load_scene(sid, scene_dir_path=SCENES)
    if st is None or st.original_room_id != IDX_RID.get(sid):
        _ls_bad.append((f, None if st is None else st.original_room_id))
check(u'B4 完整路径 `load_scene()` 88 个值全对（错 %d %r）' % (len(_ls_bad), _ls_bad[:3]),
      not _ls_bad)

_eq = []
for f in SOLO:
    sid = SOLO_RAW[f].get('scene_id')
    ent = {'original_room_id': IDX_RID.get(sid), 'chapter_id': SOLO_RAW[f].get('chapter_id'),
           'area_id': SOLO_RAW[f].get('area_id')}
    a = SS.load_scene(sid, scene_dir_path=SCENES)
    b = SS.load_scene(sid, scene_dir_path=SCENES, entry=ent)
    if (a is None or b is None
            or getattr(a, 'original_room_id', 0) != getattr(b, 'original_room_id', -1)):
        _eq.append(f)
check(u'B5 给不给 entry 结果相同（%d 个不一致 %r）—— 文件自足后回退层不再改任何东西'
      % (len(_eq), _eq[:3]), not _eq)

# ---------------------------------------------------------------------------
# C 段：其余一字未改
# ---------------------------------------------------------------------------
check(u'C0 改前快照存在且含 %d 个文件（实测 %d）' % (EXPECT_SOLO, len(SNAP_D)),
      len(SNAP_D) == EXPECT_SOLO, SNAP)

_had = [f for f in SNAP_D if SNAP_D[f].get('had_rid')]
check(u'C1 快照里"改前已有字段"的恰好是 desktop 一个（实测 %r）' % (_had,),
      _had == ['desktop.json'])

_hd, _ln, _by = [], [], []
for f in SOLO:
    s = SNAP_D.get(f)
    if not s:
        _hd.append(f)
        continue
    d = SOLO_RAW[f]
    if h_rest(d) != s.get('h_rest'):
        _hd.append(f)
    # desktop 本轮没被改 ⇒ 行数不变；其余 87 个各加 1 行
    _want_lines = s.get('lines', -99) + (0 if f in _had else 1)
    if rd(os.path.join(SCENES, f)).count('\n') != _want_lines:
        _ln.append(f)
    if f in _had:
        want = s.get('bytes', -1)
    else:
        want = s.get('bytes', -1) + len(u'  "original_room_id": %d,\r\n'
                                        % d.get('original_room_id'))
    if os.path.getsize(os.path.join(SCENES, f)) != want:
        _by.append((f, os.path.getsize(os.path.join(SCENES, f)), want))
check(u'C2 87 个文件「除房间号外」的指纹 == 改前快照（不符 %d %r）' % (len(_hd), _hd[:3]),
      not _hd)
check(u'C3 每个文件行数 == 改前 + 1（不符 %d %r）' % (len(_ln), _ln[:3]), not _ln)
check(u'C4 字节增量恰好等于新增那一行（不符 %d %r）' % (len(_by), _by[:3]), not _by)

_rc, _out = git('-c', 'core.quotepath=false', 'diff', '--name-only', 'HEAD', '--',
                'ralsei_pet/assets/scenes/')
_changed = set(x.strip() for x in _out.splitlines() if x.strip())
_want = set('ralsei_pet/assets/scenes/' + f for f in SOLO if f not in _had)
check(u'C5 ★ git 侧改动面恰好是那 87 个文件（git 说 %d 个；多 %r；少 %r）'
      % (len(_changed), sorted(_changed - _want)[:3], sorted(_want - _changed)[:3]),
      _rc == 0 and _changed == _want)

_rc2, _out2 = git('-c', 'core.quotepath=false', 'diff', '--numstat', 'HEAD', '--',
                  'ralsei_pet/assets/scenes/')
_add = _del = _files = 0
for line in _out2.splitlines():
    p = line.split('\t')
    if len(p) == 3 and p[0].isdigit():
        _add += int(p[0])
        _del += int(p[1])
        _files += 1
check(u'C6 git 统计：%d 文件 +%d 行 -%d 行（必须是 +87 / -0）'
      % (_files, _add, _del), _files == EXPECT_FILLED and _add == EXPECT_FILLED and _del == 0)

_leftover = [f for f in SOLO if f.endswith('.new')]
check(u'C7 没有残留 `.new` 临时件（%r）' % (_leftover,), not _leftover)

# ---------------------------------------------------------------------------
# D 段：值有据、不串行
# ---------------------------------------------------------------------------
_nosrc = [f for f in SOLO if SOLO_RAW[f].get('scene_id') not in IDX_RID]
check(u'D0 88 个文件都能在 index 里找到同一 scene_id（找不到 %r）' % (_nosrc[:3],),
      not _nosrc)

_seen, _dup = {}, []
for sid, r in IDX_RID.items():
    k = (IDX_CH[sid], r)
    if k in _seen:
        _dup.append((k, _seen[k], sid))
    _seen[k] = sid
check(u'D1 同章内房间号唯一（冲突 %d 组 %r）—— 值不会串行'
      % (len(_dup), _dup[:3]), not _dup)

_alias = [(f, SOLO_RAW[f].get('scene_id')) for f in SOLO
          if f != (SOLO_RAW[f].get('scene_id') or '') + '.json']
check(u'D2 文件名 == `<scene_id>.json`（不符 %r）' % (_alias[:3],), not _alias)

_ids = [SOLO_RAW[f].get('scene_id') for f in SOLO]
check(u'D3 88 个 file 的 scene_id 无重复（%d 个唯一）' % len(set(_ids)),
      len(set(_ids)) == len(_ids))

orm = jl(ROOMS)
TAB = {}
for cid, ch in ((orm or {}).get('chapters') or {}).items():
    TAB[cid] = set(r.get('id') for r in ((ch or {}).get('rooms') or [])
                   if isinstance(r, dict))
_hit, _out_tab, _wrong = 0, [], []
for f in SOLO:
    sid = SOLO_RAW[f].get('scene_id')
    if sid not in IDX_RID:
        continue
    ch = IDX_CH[sid]
    if IDX_RID[sid] in TAB.get(ch, set()):
        _hit += 1
    else:
        _out_tab.append((f, ch, IDX_RID[sid]))
check(u'D4 落在「原作剧情房间表」里的必须命中：%d 个命中 / %d 个表外（%r）'
      % (_hit, len(_out_tab), _out_tab[:4]),
      _hit + len(_out_tab) == len(SOLO) and _hit >= 85)

# ★ 表外那几个：值仍必须与 index 一致（不与表冲突，只是表本身不全）
check(u'D5 表外的 %d 个值仍逐条 == index（不编造）' % len(_out_tab),
      all(SOLO_RAW[f].get('original_room_id') == IDX_RID[SOLO_RAW[f]['scene_id']]
          for f, _c, _r in _out_tab))

_crlf = [f for f in SOLO if '\r\n' not in rd(os.path.join(SCENES, f))]
check(u'D6 88 个文件仍是 CRLF（被写成 LF 的 %r）' % (_crlf[:3],), not _crlf)

_bom = [f for f in SOLO if rd(os.path.join(SCENES, f)).startswith(u'\ufeff')]
check(u'D7 没有 BOM（%r）' % (_bom[:3],), not _bom)

# ---------------------------------------------------------------------------
# E 段：自检
# ---------------------------------------------------------------------------
_src = rd(os.path.abspath(__file__))
_tree = ast.parse(_src)

_W = 'check'
_trivial = []
for node in ast.walk(_tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == _W:
        if len(node.args) >= 2:
            a = node.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                _trivial.append(node.lineno)
            if isinstance(a, ast.Name) and a.id == 'True':
                _trivial.append(node.lineno)
check(u'E0 AST 查恒真：没有 `check(..., True)` 这种写死的绿（%r）' % (_trivial,),
      not _trivial)

_d = [_n for _n in ast.walk(_tree) if isinstance(_n, ast.FunctionDef) and _n.name == 'check']
check(u'E1 单一 harness：`check` 只定义 1 次（实测 %d）' % len(_d), len(_d) == 1)

check(u'E2 判据条数 %d >= %d（判据太少等于没锁）' % (_n['p'] + _n['f'], CHECK_FLOOR),
      _n['p'] + _n['f'] >= CHECK_FLOOR, u'（本条自己也算一条）')

_MAIN_IMP = 'import ' + 'main'
_TRUE_APP = 'Ralsei' + 'Pet('
check(u'E3 不构造真机 App：不 import `main`、不出现真机构造调用',
      _MAIN_IMP not in _src and _TRUE_APP not in _src)

_DRV = re.compile('[A-Za-z]' + ':' + r'[\\/]')
_ext = _DRV.findall(_src)
check(u'E4 零外部盘：源码里没有盘符绝对路径字面量（%d 处）' % len(_ext), not _ext,
      u'回归不许依赖外部盘/临时区')

_NET = ['import ' + m for m in ('requests', 'urllib', 'socket', 'http.client')]
_hit_net = [k for k in _NET if k in _src]
check(u'E5 零网络（命中 %r）' % (_hit_net,), not _hit_net)

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'红项：')
    for _b in _bad:
        print(u'  - %s' % _b)
print('=' * 70)
sys.exit(1 if _n['f'] else 0)
