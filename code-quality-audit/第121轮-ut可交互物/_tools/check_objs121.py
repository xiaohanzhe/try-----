# -*- coding: utf-8 -*-
u"""第121轮回归锁：ut 场景的 `objects`（可交互物）不许静默漂移。

## 本套件守什么（零 Qt、零网络、零外部盘 —— 只读仓库内资产）

A 规模：358 场景 / 136 有物件 / **422 条**（分母闸，防批量清空）
B 形状：每条字段恰好 `{pos, sprite, src, depth}`；`sprite` 必须 **None**；
  `pos` 是两个 int；`depth` 是 int
C ★★ **位置全量复算**：拿仓库里的 `inst_full.tsv`（实例坐标）+ `objmap_ut.txt`
  （对象可见性/精灵）+ `viz120.ut.tsv` 的 `SPR` 段（精灵原点）**重算**
  `pos = [x-ox, y-oy]`，与写入值逐条比对。错一台机器就红。
D 来源：每条 `src` 都必须在 ut 的 objmap 里，且 `classify()` 命中允许的 6 类
  （`door` / `cutscene` **不许**出现 —— 见下）
E 防回滚：场景数 / 条目数不得跌破本轮实测
F 自检：**AST** 数恒真判据（不扫注释，否则会被文案误报）/ 无 BOM / 正负控制成对

## 为什么 `cutscene` 不许出现（`door` 则**有条件**允许）

  · `door`：第121轮时**一扇都不写**（建门要 `routes`，ut 侧还没有 ⇒ 写了就是
    "推不开的门"）。第122轮补了 243 条门、第123轮补齐位移机制后，口径变成
    **「`_routes.json` 里真有目标的才写」**（准入闸见
    `build_objs121.load_routed_doors`，判据 B2b 守两个方向的双射）。
    现在实测 1,233 条门实例 / 525 组，覆盖 1,233 of 1,299 个门实例（94.9%）。
  · `cutscene`(375)：`build_props` 落 `else` 直接丢弃，写了是纯噪音。

## 为什么 `sprite` 必须 None

  ut 的画面已经在第120轮烘进背景图里，再画一遍就是重复绘制；
  而 `_obj_visible.json` 的 `hidden` 名单是**全局扁平**的，ut 的 `obj_savepoint`
  与 Deltarune 的 `obj_savepoint` **同名**（实测唯一冲突）⇒ 并进全局名单会跨作品
  污染 Deltarune 的存档点。所以走"`sprite=None` ⇒ `_paint_obj` 的 `if name` 不成立
  ⇒ 不落笔"这条路（已核 `scene_canvas._paint_obj` 第 375~376 行）。

用法：python check_objs121.py
"""
import ast
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence', 'raw')
RAW120 = os.path.join(os.path.dirname(ROUND), '第120轮-ut场景背景与物件', '_evidence', 'raw')
MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')

sys.path.insert(0, MODULES)
import item_interact as II       # noqa: E402

FIELDS = {'pos', 'sprite', 'src', 'depth'}
WANT_KINDS = ('readable', 'sign', 'savepoint', 'pickup', 'fountain', 'interactable')
#: ★★ 第122轮：`door` 也可以出现 —— 但**只许出现在路由表里有目标的那批**
#:   （门的准入闸，见 `build_objs121.load_routed_doors`）。判据 B2b 守这条双射。
DOOR_KIND = 'door'
BANNED_KINDS = ('cutscene',)

#: 本轮（第121轮）那 6 类的实测条数 —— 第122轮加了门之后要能**分账**
BASE_N, BASE_TOTAL = 136, 422

#: ★ 第123轮：门补齐后的实测规模（274 场景 / 1,655 条 / 其中门 1,233 条 525 组）
#:   来源：`第123轮-补齐ut门证据/_evidence/ut_doors123.json` +
#:   `check123.C2/C3`（1,655 条 / 274 场景 / 门 1,233 / 覆盖 1,233 of 1,299）
SCENES_N, TOTAL_N, DOOR_N, DOOR_GROUPS_N = 274, 1655, 1233, 525

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, detail=''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


# ---------- 载入：场景 / 实例 / 对象表 / 精灵原点 ----------
scenes = _json(os.path.join(SCENES, '_zone.ut.rooms.json'))['scenes']

insts = collections.defaultdict(list)          # roomName -> [(obj,x,y,depth)]
cur = None
for r in _rows(os.path.join(RAW115, 'ut', 'inst_full.tsv')):
    if r[0] == 'R':
        cur = r[2]
    elif r[0] == 'I' and cur is not None:
        insts[cur].append({'obj': r[1], 'x': int(r[2]), 'y': int(r[3]),
                           'depth': int(r[9])})

objmap = {}
for r in _rows(os.path.join(RAW115, 'ut', 'objmap_ut.txt')):
    if len(r) >= 5 and r[0] != 'GameObjects':
        objmap[r[1]] = {'spr': r[2][4:] if r[2].startswith('spr=') else '',
                        'vis': r[3] == 'vis=True'}

origin = {}
for r in _rows(os.path.join(RAW120, 'ut', 'viz120.ut.tsv')):
    if r[0] == 'SPR':
        origin.setdefault(r[1], (int(r[4]), int(r[5])))

print('== 分母 ==')
check('A0 场景 358 / 实例表覆盖 338 间房 / 对象表非空 / 原点表非空',
      len(scenes) == 358 and len(insts) == 338 and bool(objmap) and bool(origin),
      '%d / %d / %d / %d' % (len(scenes), len(insts), len(objmap), len(origin)))

withobj = [(sid, sc) for sid, sc in scenes.items() if sc.get('objects')]
total = sum(len(sc['objects']) for _s, sc in withobj)


def _routed_doors():
    u"""`{(房间名, 门对象名)}` —— **路由表真能匹配到的门**（第122轮起；第123轮改口径）。

    ★★★ 第123轮修：旧实现写的是 `r.get('when_src') or 'obj_doorA'` —— 那个
      `'obj_doorA'` 兜底在第123轮**变成错的**：第122轮 ut 段只有字母 A（133 条
      `ut_door_next`），所以"没写 when_src 就是 obj_doorA"侥幸成立；第123轮补了
      B(−1)/C(+2)/D(−2) 之后，`obj_doorB` 的规则会被算成"obj_doorA 在房间 X 有目标"
      ⇒ 判据自己得出「点不动的门 442 / 幽灵规则 66」这种**纯误报**（实测过）。

    ★ 现在改成**语义重推**（不是照抄生成器的 `_original.via`）：一条路由到底能匹配
      到哪扇门，问的是产品那条路 —— 对象级（`when_src`）直接就是那扇门；字母级
      （`when_door`）则去实例表里找**该房间里字母相同的那个门对象**。
      这样写的好处：① 不与生成器共用同一份书签（`via` 写错时判据仍能抓）；
      ② 顺带把「同场景同字母多解」暴露成红（匹配到 0 个或多于 1 个都记账）。

    ★ 为什么判据自己去读路由表、而不是调 `build_objs121.load_routed_doors()`：
      那是生成器的**决策**；判据若直接复用同一个函数，就变成"自己验自己"。
    """
    try:
        d = _json(os.path.join(SCENES, '_routes.json'))
    except Exception:
        return set()
    out = set()
    for r in (d.get('routes') or []):
        if not isinstance(r, dict):
            continue
        if not str(r.get('when_scene') or '').startswith('ut.'):
            continue
        rn = (r.get('_original') or {}).get('src_room_name')
        if not rn:
            continue
        o = r.get('when_src')
        if o:
            out.add((rn, o))
            continue
        letter = r.get('when_door')
        if not letter:
            continue
        cand = [it['obj'] for it in insts.get(rn, [])
                if II.door_letter_of(it['obj']) == letter]
        for o2 in set(cand):
            out.add((rn, o2))
    return out


ROUTED = _routed_doors()

print()
print('== A. 规模与形状 ==')
_ndoor = sum(1 for _s, sc in withobj for e in sc['objects']
             if (II.classify(e.get('src')) or {}).get('kind') == DOOR_KIND)
_6n = sum(1 for _s, sc in withobj for e in sc['objects']
          if (II.classify(e.get('src')) or {}).get('kind') in WANT_KINDS)
_6s = sum(1 for _s, sc in withobj
          if any((II.classify(e.get('src')) or {}).get('kind') in WANT_KINDS
                 for e in sc['objects']))
check('A1 %d 场景 / %d 条（= 第121轮的 %d/%d + 第122轮的门 243 条 + 第123轮的位移门）'
      % (SCENES_N, TOTAL_N, BASE_N, BASE_TOTAL),
      len(withobj) == SCENES_N and total == TOTAL_N and _ndoor == DOOR_N,
      '%d / %d / door %d' % (len(withobj), total, _ndoor))
check('A1b ★分账：非 door 的 6 类仍是 %d 场景 / %d 条（加门没有顶替或挤掉别的类）'
      % (BASE_N, BASE_TOTAL), _6s == BASE_N and _6n == BASE_TOTAL,
      '%d / %d' % (_6s, _6n))

bad_fields, bad_sprite, bad_pos, bad_depth = [], [], [], []
for sid, sc in withobj:
    for e in sc['objects']:
        if set(e) != FIELDS:
            bad_fields.append((sid, sorted(e)))
        if e.get('sprite') is not None:
            bad_sprite.append((sid, e.get('sprite')))
        p = e.get('pos')
        if not (isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) for v in p)):
            bad_pos.append((sid, p))
        if not isinstance(e.get('depth'), int):
            bad_depth.append((sid, e.get('depth')))
check('A2 每条字段恰好 {pos, sprite, src, depth}', not bad_fields, repr(bad_fields[:3]))
check('A3 `sprite` 一律为 None（画面已在背景里，不重复绘制）',
      not bad_sprite, repr(bad_sprite[:3]))
check('A4 `pos` 是两个 int / `depth` 是 int',
      not bad_pos and not bad_depth, repr((bad_pos[:2], bad_depth[:2])))

print()
print('== B. 来源与分类 ==')
unknown, banned = [], []
kinds = collections.Counter()
for sid, sc in withobj:
    for e in sc['objects']:
        src = e.get('src')
        if src not in objmap:
            unknown.append((sid, src))
            continue
        rec = II.classify(src)
        if rec is None or rec['kind'] in II.NON_INTERACTIVE_KINDS:
            banned.append((sid, src, 'not-interactive'))
            continue
        kinds[rec['kind']] += 1
        if rec['kind'] in BANNED_KINDS:
            banned.append((sid, src, rec['kind']))
        elif rec['kind'] not in WANT_KINDS and rec['kind'] != DOOR_KIND:
            banned.append((sid, src, rec['kind']))
check('B1 每条 `src` 都在 ut 的 objmap 里', not unknown, repr(unknown[:3]))
check('B2 每条都命中 6 类或 `door`；`cutscene` 一个都不许出现（`build_props` 落 else 丢弃）',
      not banned, repr(banned[:3]))
check('B3 分类分布 == 实测（readable 350 / sign 34 / savepoint 33 / pickup 3 / '
      'fountain 1 / interactable 1 / door %d）' % DOOR_N,
      dict(kinds) == {'readable': 350, 'sign': 34, 'savepoint': 33,
                      'pickup': 3, 'fountain': 1, 'interactable': 1,
                      'door': DOOR_N},
      repr(dict(sorted(kinds.items(), key=lambda kv: -kv[1]))))
# ★★ B2b 第122轮：门与路由表**双射**（两个方向都要，缺一个方向就等于没守）
#   ① 写进 objects 的每一扇门，都必须在路由表里有 (房间,对象) ⇒ 不会有点不动的门
#   ② 路由表里的每一条 ut 规则，都必须在 `objects` 里有对应的门 ⇒ 不会有幽灵规则
_dead = []
for sid, sc in withobj:
    rn = scenes[sid].get('name')
    for e in sc['objects']:
        if (II.classify(e.get('src')) or {}).get('kind') != DOOR_KIND:
            continue
        if (rn, e['src']) not in ROUTED:
            _dead.append((sid, e['src']))
_have = set()
for sid, sc in withobj:
    rn = scenes[sid].get('name')
    for e in sc['objects']:
        if (II.classify(e.get('src')) or {}).get('kind') == DOOR_KIND:
            _have.add((rn, e['src']))
_ghost = sorted(ROUTED - _have)
check('B2b ★门与路由表**双射**：objects 里的门 %d 组全有目标（点不动的 %d）／'
      '路由表 %d 组全在场（幽灵规则 %d）'
      % (len(_have), len(_dead), len(ROUTED), len(_ghost)),
      not _dead and not _ghost and len(_have) == len(ROUTED) == DOOR_GROUPS_N,
      repr((_dead[:3], _ghost[:3])))

print()
print('== C. 位置全量复算（本轮最硬的一条）==')


def expect(room_name):
    u"""按第120轮的同一套口径重算该房间该有哪些物件、各自 pos 是多少。

    ★★ 第122轮：门也在里面，但**只算"路由表里有目标"的那批**（与生成器同一个
      准入规则，独立重推一遍 —— 见 `_routed_doors` 的 docstring）。
    """
    out = []
    for it in insts.get(room_name, []):
        rec = II.classify(it['obj'])
        if not rec or rec['kind'] in II.NON_INTERACTIVE_KINDS:
            continue
        if rec['kind'] == DOOR_KIND:
            if (room_name, it['obj']) not in ROUTED:
                continue
        elif rec['kind'] not in WANT_KINDS:
            continue
        ox, oy = origin.get(objmap.get(it['obj'], {}).get('spr', ''), (0, 0))
        out.append({'pos': [it['x'] - ox, it['y'] - oy], 'sprite': None,
                    'src': it['obj'], 'depth': it['depth']})
    out.sort(key=lambda e: (e['pos'][1], e['pos'][0], e['src']))
    return out


mismatch = []
for sid, sc in scenes.items():
    if not isinstance(sc, dict):
        continue
    got = sc.get('objects') or []
    want = expect(sc.get('name'))
    if got != want:
        mismatch.append((sid, len(got), len(want),
                         (got[:1] or [None])[0], (want[:1] or [None])[0]))
check('C1 358 个场景的 `objects` 与「实例表 + 原点表」重算结果**逐条相等**',
      not mismatch, repr(mismatch[:2]))

# C2 负控制：把一个 pos 挪 1 像素，判据必须报红（否则 C1 是恒真）
if withobj:
    _sid, _sc = withobj[0]
    _bad = [dict(e) for e in _sc['objects']]
    _bad[0] = dict(_bad[0])
    _bad[0]['pos'] = [_bad[0]['pos'][0] + 1, _bad[0]['pos'][1]]
    check('C2 负控制：pos 挪 1 像素 ⇒ 判据报红（C1 有鉴别力）',
          _bad != expect(_sc['name']))
# C3 正控制：不挪时恒等
if withobj:
    _sid, _sc = withobj[0]
    check('C3 正控制：原样的 objects == 重算结果（不是两边一起错）',
          _sc['objects'] == expect(_sc['name']))

print()
print('== D. 防回滚 ==')
check('D1 有物件的场景数 ≥ %d（防批量清空）' % SCENES_N, len(withobj) >= SCENES_N,
      str(len(withobj)))
check('D2 条目总数 ≥ %d（防批量删条目）' % TOTAL_N, total >= TOTAL_N, str(total))
check('D3 场景总数仍是 358（objects 改动不许连带改场景表结构）',
      len(scenes) == 358, str(len(scenes)))

print()
print('== E. 自检 ==')
src = io.open(os.path.abspath(__file__), encoding='utf-8', newline='').read()
_tree = ast.parse(src)
_true_checks = []
for node in ast.walk(_tree):
    if not isinstance(node, ast.Call):
        continue
    fn = node.func
    if not (isinstance(fn, ast.Name) and fn.id == 'check'):
        continue
    if len(node.args) >= 2:
        a1 = node.args[1]
        if isinstance(a1, ast.Constant) and a1.value is True:
            _true_checks.append(getattr(node, 'lineno', -1))
check('E1 没有 `check(x, True)` 这种恒真判据（AST 判，不扫注释）',
      not _true_checks, repr(_true_checks[:5]))
check('E2 资产文件无 BOM、无 U+FFFD',
      not src.startswith(u'\ufeff')
      and u'\ufffd' not in io.open(os.path.join(SCENES, '_zone.ut.rooms.json'),
                                   encoding='utf-8', newline='').read())

print()
print('---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
sys.exit(1 if _failed else 0)
