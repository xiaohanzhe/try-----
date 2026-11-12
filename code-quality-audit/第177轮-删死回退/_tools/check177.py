# -*- coding: utf-8 -*-
u"""第177轮判据：删掉 `load_scene()` 里那条**已死**的 `original_room_id` 回退。

★★★ 本轮判据的重心
-----------------
要删的是一段"**从来没执行过**"的代码。这种删除最容易写出**恒真判据**：
    "源码里没有那段赋值" —— 用文本 `in` 搜当然能搜到/搜不到，
    但真正要证明的是"**删了行为不变**"，而不是"我删掉了那几行"。

所以判据分成三层，越往后越硬：

  ① **自足率**（A 段）：两条来源 2166/2166 **自带** `original_room_id`，
     与 `_index.json` **逐条相等** ⇒ 回退即使存在也无事可做。
  ② **机制已消失**（B 段）：AST 扫 `load_scene` 的**函数体**，
     不许出现 `scene.original_room_id = ...` 赋值、不许出现 `entry.get('original_room_id')`；
     但 `entry.get('chapter_id')` / `('area_id')` **必须还在**（分片定位还要它）。
     ★ 负控制：把同样的扫描器喂给一段**合成源码**，它必须报命中（防扫描器恒空）。
  ③ **行为已改**（C 段）：临时造一个"缺 rid"的场景文件 + 给 `entry` 带 rid ⇒
     `load_scene` 返回的 rid 必须是 **None**（不再猜）。
     ★★★ 这条是本轮**唯一**在删前会红、删后转绿的判据 —— 它就是"这次真的删了"的证据。

★ 为什么不是"随手删干净"：`entry` 参数本身**不能删** —— 分片场景要靠它知道
  去读 `_zone.<章>.<区域>.json`。删错了 2078 个场景会全部加载失败。B3 就是钉这个的。

用法：python check177.py
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
SS_P = os.path.join(PKG, 'modules', 'scene_system.py')
SELF = os.path.abspath(__file__)

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules import scene_system as SS            # noqa: E402
from modules.scene_system import (load_scene, load_zone,  # noqa: E402
                                  zone_filename)

#: ★ 第185轮：`ch1.forest.room_man` 进 zone + `_index.json` ⇒ 两个分母各 +1。只加账、不重算。
EXPECT_INDEX = 2166 + 1       # `_index.json` 登记场景数
EXPECT_SOLO = 88          # 独立文件数（含 desktop）
EXPECT_ZONE = 2078 + 1        # 分片内场景数
SENTINEL = -999999        # 哨兵：如果它还从 entry 取 rid，就会看到这个数
CHECK_FLOOR = 29

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


# ---------------------------------------------------------------------------
# 0. 装配
# ---------------------------------------------------------------------------
#: ★★ `entry` 必须用 `load_index()['scenes']`（**展平 + 注入 chapter_id/area_id** 的那份），
#:   不能用原始 `_index.json` —— 后者只有 `original_room_id`，没有 chapter/area，
#:   `load_scene` 拿到它会定位不到分片（第一版就栽在这：76 片全返回 None）。
_IDX = SS.load_index(SCENES)
REG = (_IDX or {}).get('scenes') or {}

SOLO = sorted(f for f in os.listdir(SCENES)
              if f.endswith('.json') and not f.startswith('_'))
ZONES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.'))
SOLO_RAW = {f: jl(os.path.join(SCENES, f)) for f in SOLO}
ZONE_RAW = {}
for _zf in ZONES:
    ZONE_RAW[_zf] = jl(os.path.join(SCENES, _zf))

print('=' * 70)
print(u'第177轮判据 · 删掉 `load_scene()` 里已死的 `original_room_id` 回退')
print('=' * 70)

# ---------------------------------------------------------------------------
# A 段：自足率（回退"无事可做"的证据）
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'A 段  两条来源都自带 rid（回退无事可做）')
print('=' * 70)

_z_scenes = {}
for _zf, _d in ZONE_RAW.items():
    for _sid, _sc in ((_d or {}).get('scenes') or {}).items():
        _z_scenes[_sid] = _sc

check(u'A0 分母：`_index.json` 登记 %d；独立文件 %d；分片场景 %d；%d + %d == %d'
      % (EXPECT_INDEX, EXPECT_SOLO, EXPECT_ZONE, EXPECT_SOLO, EXPECT_ZONE,
         EXPECT_INDEX),
      len(REG) == EXPECT_INDEX and len(SOLO) == EXPECT_SOLO
      and len(_z_scenes) == EXPECT_ZONE
      and len(SOLO) + len(_z_scenes) == EXPECT_INDEX,
      u'index=%d solo=%d zone=%d' % (len(REG), len(SOLO), len(_z_scenes)))


def _rid(d):
    r = (d or {}).get('original_room_id')
    return r if isinstance(r, int) and not isinstance(r, bool) else None


_a1_miss = [f for f in SOLO if _rid(SOLO_RAW[f]) is None]
check(u'A1 独立文件 %d/%d **自带** int `original_room_id`（一个都不缺）'
      % (EXPECT_SOLO, EXPECT_SOLO),
      not _a1_miss, u'缺 %d: %r' % (len(_a1_miss), _a1_miss[:5]))

_a2_miss = [s for s, d in _z_scenes.items() if _rid(d) is None]
check(u'A2 分片场景 %d/%d **自带** int `original_room_id`'
      % (EXPECT_ZONE, EXPECT_ZONE),
      not _a2_miss, u'缺 %d: %r' % (len(_a2_miss), _a2_miss[:5]))

_a3_bad = []
for f in SOLO:
    sid = SOLO_RAW[f].get('scene_id')
    want = _rid(REG.get(sid))
    if _rid(SOLO_RAW[f]) != want:
        _a3_bad.append((f, _rid(SOLO_RAW[f]), want))
for sid, d in _z_scenes.items():
    want = _rid(REG.get(sid))
    if _rid(d) != want:
        _a3_bad.append((sid, _rid(d), want))
check(u'A3 2166 条**逐条**与 `_index.json` 登记值相等（文件值 == 索引值，不是"值合理"）',
      not _a3_bad,
      u'不符 %d: %r' % (len(_a3_bad), _a3_bad[:3]))

#: ★ 独立于 `load_scene` 的一层：`from_dict` 自己**不许**偷偷填 rid。
#:   （若哪天有人把补值逻辑塞进 `from_dict`，回退"删掉了"也没意义 —— 换个地方又长出来。）
_a4_bad = []
for f in SOLO[:8] + sorted(_z_scenes)[:8]:
    raw = dict(SOLO_RAW.get(f) or _z_scenes.get(f) or {})
    raw.pop('original_room_id', None)
    st = SS.SceneState.from_dict(raw)
    if st is not None and st.original_room_id is not None:
        _a4_bad.append((f, st.original_room_id))
check(u'A4 `SceneState.from_dict` 对**抹掉 rid** 的 raw 返回 `None`（16 条抽样）'
      u'—— 补值逻辑不许换个地方又长出来',
      not _a4_bad, u'偷偷填了 %d: %r' % (len(_a4_bad), _a4_bad[:3]))

# ---------------------------------------------------------------------------
# B 段：机制已消失（AST 扫函数体，不是文本搜）
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'B 段  回退机制已从 `load_scene()` 消失')
print('=' * 70)

_src = io.open(SS_P, encoding='utf-8').read()
_tree = ast.parse(_src)


def _load_scene_node(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'load_scene':
            return n
    return None


NODE = _load_scene_node(_tree)


def _assigns_rid(node):
    u"""函数体里有没有 `scene.original_room_id = ...` 这类赋值。"""
    out = []
    for n in ast.walk(node):
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            if isinstance(t, ast.Attribute) and t.attr == 'original_room_id':
                out.append(getattr(n, 'lineno', -1))
    return out


def _gets_rid_key(node):
    u"""函数体里有没有 `entry.get('original_room_id')` / `xxx['original_room_id']`。"""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'get' and n.args \
                and isinstance(n.args[0], ast.Constant) \
                and n.args[0].value == 'original_room_id':
            out.append(getattr(n, 'lineno', -1))
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and n.slice.value == 'original_room_id':
            out.append(getattr(n, 'lineno', -1))
    return out


check(u'B0 ★ 能定位到 `load_scene` 函数体（找不到就没法做 B 段，必须报红而不是跳过）',
      NODE is not None, u'node=%r' % (NODE is not None,))

_b1 = _assigns_rid(NODE) if NODE is not None else [-1]
check(u'B1 ★★★ `load_scene` 函数体里**没有** `scene.original_room_id = ...` 赋值'
      u'（回退已删；行号=%r）' % (_b1[:5],),
      not _b1, u'仍有赋值 %d 处: %r' % (len(_b1), _b1[:5]))

_b2 = _gets_rid_key(NODE) if NODE is not None else [-1]
check(u'B2 ★★★ `load_scene` 函数体里**没有**读 `entry["original_room_id"]`'
      u'（行号=%r）' % (_b2[:5],),
      not _b2, u'仍有读取 %d 处: %r' % (len(_b2), _b2[:5]))

#: ★★ 但 `entry` 本身**不能删** —— 分片定位靠它。少了这条，"删干净"会把 2078 个
#:   分片场景全弄挂，而 B1/B2 反而更绿（典型的"越删越绿"陷阱）。
_b3 = [n for n in ast.walk(NODE)
       if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
       and n.func.attr == 'get' and n.args
       and isinstance(n.args[0], ast.Constant)
       and n.args[0].value in ('chapter_id', 'area_id')] if NODE is not None else []
check(u'B3 ★★★ `entry` 仍被用于**分片定位**：`entry.get("chapter_id")` / '
      u'`entry.get("area_id")` 各至少一处（%d 处）' % len(_b3),
      len(_b3) >= 2, u'实测 %d 处' % len(_b3))

#: 负控制：扫描器喂给"确实含该赋值/读取"的合成源码，必须报命中
_SYN = ast.parse(u'def load_scene(a, b=None, entry=None):\n'
                 u'    scene = object()\n'
                 u'    scene.original_room_id = entry.get("original_room_id")\n'
                 u'    return scene\n')
_syn = _load_scene_node(_SYN)
check(u'B4 负控制：把 B1/B2 的扫描器喂给一段**含该赋值**的合成源码 ⇒ 必须各报 1 处'
      u'（证明扫描器不恒空）',
      _syn is not None and _assigns_rid(_syn) and _gets_rid_key(_syn),
      u'assign=%r get=%r' % (_assigns_rid(_syn) if _syn else None,
                             _gets_rid_key(_syn) if _syn else None))

#: ★★ `entry` 这个**形参**不能删（B3 钉的是"还在用"，这条钉的是"签名没被改掉"）。
#:   删了形参，`scene_controller` 那处 `entry=...` 会直接 `TypeError`。
_b5_args = [a.arg for a in (NODE.args.args if NODE is not None else [])]
check(u'B5 `load_scene` 的签名里仍有 `entry` 形参（形参=%r）—— 删了它会和调用方对不上'
      % (_b5_args,),
      'entry' in _b5_args and 'scene_dir_path' in _b5_args,
      u'形参=%r' % (_b5_args,))

# ---------------------------------------------------------------------------
# C 段：行为已改（entry 不再参与 rid）
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'C 段  行为：`entry` 不再参与 `original_room_id`')
print('=' * 70)

_c1_bad = []
for f in SOLO:
    sid = SOLO_RAW[f].get('scene_id')
    a = load_scene(sid)
    b = load_scene(sid, entry=REG.get(sid))
    if a is None or b is None or a.original_room_id != b.original_room_id:
        _c1_bad.append((sid, getattr(a, 'original_room_id', 'None'),
                        getattr(b, 'original_room_id', 'None')))
check(u'C1 88 个独立文件：`load_scene(sid)` 与 `load_scene(sid, entry=...)` 的 rid '
      u'**逐条相同**（entry 里的 rid 不再有任何作用）',
      not _c1_bad, u'不同 %d: %r' % (len(_c1_bad), _c1_bad[:3]))

_c2_bad = []
_c2_n = 0
for _zf, _d in ZONE_RAW.items():
    _sc = ((_d or {}).get('scenes') or {})
    if not _sc:
        continue
    sid = sorted(_sc)[0]
    e = dict(REG.get(sid) or {})
    good = load_scene(sid, entry=e)
    e2 = dict(e)
    e2['original_room_id'] = SENTINEL
    bad = load_scene(sid, entry=e2)
    _c2_n += 1
    if good is None or bad is None:
        _c2_bad.append((sid, 'None', 'None'))
    elif bad.original_room_id == SENTINEL or \
            good.original_room_id != bad.original_room_id:
        _c2_bad.append((sid, good.original_room_id, bad.original_room_id))
check(u'C2 分片抽样 %d 片（每片取 1 个场景）：把 `entry` 里的 rid 换成哨兵 %d ⇒ '
      u'场景的 rid **一个都不变成哨兵**、且与正常 entry 逐条相同'
      u'〔说明：文件自足时回退分支本来就进不去（`if ... is None`），'
      u'所以这条在删前也是绿的 —— 真正区分删没删的是 C3/C4〕'
      % (_c2_n, SENTINEL),
      _c2_n >= 60 and not _c2_bad,
      u'片=%d 异常=%d: %r' % (_c2_n, len(_c2_bad), _c2_bad[:3]))

#: ★★★ C3/C4 是本轮**唯一**在删前会红的判据：造一个"缺 rid"的场景 + 给 entry 带 rid。
#:   删前：entry 会把 555 补进去（回退生效）；删后：必须是 None（不再猜）。
_tmp = tempfile.mkdtemp(prefix='cq177_')
try:
    _noid = {'schema_version': SS.SCENE_SCHEMA_VERSION,
             'scene_id': 'tmp.probe.no_rid', 'area_name': u'探针',
             'objects': []}
    _p1 = os.path.join(_tmp, 'tmp.probe.no_rid.json')
    with io.open(_p1, 'w', encoding='utf-8') as f:
        json.dump(_noid, f, ensure_ascii=False)
    _got1 = load_scene('tmp.probe.no_rid', scene_dir_path=_tmp,
                       entry={'chapter_id': 'ch1', 'area_id': 'probe',
                              'original_room_id': 555})
    check(u'C3 ★★★ 独立文件**缺** `original_room_id` + `entry` 里带 555 ⇒ '
          u'`load_scene` 返回的 rid 必须是 **None**（不再用 entry 猜）',
          _got1 is not None and _got1.original_room_id is None,
          u'实得=%r' % (getattr(_got1, 'original_room_id', 'None'),))

    # 分片支路：造一个只含 1 个场景、缺 rid 的 `_zone` 文件
    _zname = zone_filename('ch1', 'probe')
    with io.open(os.path.join(_tmp, _zname), 'w', encoding='utf-8') as f:
        json.dump({'schema_version': SS.SCENE_SCHEMA_VERSION,
                   'scenes': {'tmp.probe.zone_no_rid': {
                       'scene_id': 'tmp.probe.zone_no_rid',
                       'area_name': u'探针', 'objects': []}}},
                  f, ensure_ascii=False)
    _got2 = load_scene('tmp.probe.zone_no_rid', scene_dir_path=_tmp,
                       entry={'chapter_id': 'ch1', 'area_id': 'probe',
                              'original_room_id': 666})
    check(u'C4 ★★★ 分片场景**缺** rid + `entry` 里带 666 ⇒ 同样必须是 **None**'
          u'（两条支路的回退都拆掉了，不是只拆一条）',
          _got2 is not None and _got2.original_room_id is None,
          u'实得=%r' % (getattr(_got2, 'original_room_id', 'None'),))

    #: 负控制：同一个临时目录里放一个**带** rid 的文件 ⇒ 必须读到它
    #: （证明 C3/C4 的 None 不是"读不到文件"造成的假象）
    _yes = dict(_noid)
    _yes['scene_id'] = 'tmp.probe.has_rid'
    _yes['original_room_id'] = 777
    with io.open(os.path.join(_tmp, 'tmp.probe.has_rid.json'), 'w',
                 encoding='utf-8') as f:
        json.dump(_yes, f, ensure_ascii=False)
    _got3 = load_scene('tmp.probe.has_rid', scene_dir_path=_tmp,
                       entry={'chapter_id': 'ch1', 'area_id': 'probe',
                              'original_room_id': 555})
    check(u'C5 负控制：同一份临时数据里放个**带** rid=777 的文件 ⇒ 必须读到 777'
          u'（证明 C3/C4 的 None 不是"文件读不到"造成的假象）',
          _got3 is not None and _got3.original_room_id == 777,
          u'实得=%r' % (getattr(_got3, 'original_room_id', 'None'),))
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
# D 段：语义不变（删的只是"猜 rid"，别的行为一格不许动）
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'D 段  其余语义逐条不变')
print('=' * 70)

_d_solo = [f for f in SOLO
           if load_scene(SOLO_RAW[f].get('scene_id')) is None]
check(u'D1 88 个独立文件**不给 entry** 也全都能加载（向后兼容没被破坏）',
      not _d_solo, u'失败 %d: %r' % (len(_d_solo), _d_solo[:3]))

#: 分片用 `load_zone` 一次一片地取（别在循环里反复读文件）
_z_ok = {}
for _cid, _ch in ((_IDX or {}).get('chapters') or {}).items():
    for _aid in ((_ch or {}).get('areas') or {}):
        _z_ok.update(load_zone(_cid, _aid, SCENES))
_d_miss = [s for s in _z_scenes if s not in _z_ok]
check(u'D2 分片里的 %d 个场景全部能被 `load_zone` 读出（一片不少）'
      % EXPECT_ZONE,
      not _d_miss and len(_z_ok) == EXPECT_ZONE,
      u'读出=%d 缺=%d: %r' % (len(_z_ok), len(_d_miss), _d_miss[:3]))

_tmp2 = tempfile.mkdtemp(prefix='cq177b_')
try:
    #: schema 不符 ⇒ None
    with io.open(os.path.join(_tmp2, 'tmp.bad_schema.json'), 'w',
                 encoding='utf-8') as f:
        json.dump({'schema_version': 999, 'scene_id': 'tmp.bad_schema',
                   'objects': []}, f)
    check(u'D3 schema 版本不符 ⇒ `None`（守卫还在，没被顺手删掉）',
          load_scene('tmp.bad_schema', scene_dir_path=_tmp2) is None)
    #: JSON 坏 ⇒ None
    with io.open(os.path.join(_tmp2, 'tmp.bad_json.json'), 'w',
                 encoding='utf-8') as f:
        f.write(u'{ not json')
    check(u'D4 JSON 坏掉 ⇒ `None`（永不抛）',
          load_scene('tmp.bad_json', scene_dir_path=_tmp2) is None)
    #: 路径穿越拦截
    #: ★★★ 第177轮修：原来只写 `load_scene('a/b') is None` 这类断言 ——
    #:   那些文件**本来就不存在**，守卫删了也一样返回 None ⇒ **恒真判据**
    #:   （变异 M7「删掉遍历守卫」实测 rc=0 全绿，就是被这条骗过去的）。
    #:   现在先**真的造出**一个"穿越一步就能读到"的文件，让"守卫生效"有鉴别力。
    _sneak_dir = os.path.join(_tmp2, 'sub')
    os.makedirs(_sneak_dir, exist_ok=True)
    with io.open(os.path.join(_sneak_dir, 'sneaky.json'), 'w',
                 encoding='utf-8') as f:
        json.dump({'schema_version': SS.SCENE_SCHEMA_VERSION,
                   'scene_id': 'sneaky', 'objects': []}, f)
    check(u'D5a 夹具就位：`sub/sneaky.json` 真实存在（否则 D5b 恒真）',
          os.path.isfile(os.path.join(_sneak_dir, 'sneaky.json')))
    check(u'D5b 场景 id 带分隔符 / `..` ⇒ `None`（路径穿越守卫还在）',
          load_scene('sub/sneaky', scene_dir_path=_tmp2) is None
          and load_scene('../etc/passwd', scene_dir_path=_tmp2) is None
          and load_scene('a/b', scene_dir_path=_tmp2) is None
          and load_scene('..', scene_dir_path=_tmp2) is None,
          u'穿越一步可读=%s'
          % os.path.isfile(os.path.join(_sneak_dir, 'sneaky.json')))
finally:
    shutil.rmtree(_tmp2, ignore_errors=True)

check(u'D6 空 id / None ⇒ `None`（不抛）',
      load_scene(None) is None and load_scene('') is None)

# ---------------------------------------------------------------------------
# E 段：文件与自检
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'E 段  文件与自检（判据也是被测物）')
print('=' * 70)

_b = io.open(SS_P, 'rb').read()
#: ★ 第138/146轮立的规矩：判据只判**断言**，不把"随版本必然漂移"的量打进 extra
#:   （文件体积每改一次 `scene_system.py` 就变 ⇒ 判定没变也会报 DIFF）。
check(u'E1 `scene_system.py` 无 BOM、UTF-8 可解码、`ast.parse` 通过',
      not _b.startswith(b'\xef\xbb\xbf')
      and _b.decode('utf-8') is not None and _tree is not None)

_checks = [n for n in ast.walk(ast.parse(io.open(SELF, encoding='utf-8').read()))
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == 'check']
_const_true = [getattr(c, 'lineno', -1) for c in _checks
               if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
               and bool(c.args[1].value)]
check(u'E2 ★★★ 全部 %d 条 `check(...)` 的第二参**都不是**常量真'
      u'（恒真判据比不写还危险）' % len(_checks),
      len(_checks) > 0 and not _const_true, u'恒真行号=%r' % (_const_true[:5],))

_ok_defs = [n for n in ast.walk(ast.parse(io.open(SELF, encoding='utf-8').read()))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == 'ok']
check(u'E3 单一 harness：本文件只定义 `check(desc, cond, extra)`，没有第二套 `ok(...)`',
      not _ok_defs)

check(u'E4 判据条数下限：AST 数出 >= %d 条（防有人整段删掉）' % CHECK_FLOOR,
      len(_checks) >= CHECK_FLOOR)

_self_src = io.open(SELF, encoding='utf-8').read()
_pat = [('E' + ':' + '\\'), ('h' + 'ttp' + '://'), ('h' + 'ttps' + '://')]
_hit = [p for p in _pat if p in _self_src]
check(u'E5 零外部盘 / 零网络：源码里不出现 E 盘路径或 URL'
      u'（★ 令牌用拼接构造，避免扫描器扫到自己）',
      not _hit, u'命中=%r' % (_hit,))

#: ★★★ 这里踩过"扫描器扫到自己"：把令牌**字面量**写进源码再全文找，那行自己就命中。
#:   ⇒ 令牌用**拼接**构造，源码里（含注释与文案）不出现完整串。
_tok_main = 'Ralsei' + 'Pet('
_tok_imp = 'import ' + 'main'
check(u'E6 不构造真机、不 import 主程序（本轮只碰数据层，不需要显示器）',
      _tok_main not in _self_src and _tok_imp not in _self_src)

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
print('=' * 70)
sys.exit(1 if _n['f'] else 0)
