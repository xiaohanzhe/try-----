# -*- coding: utf-8 -*-
u"""第120轮回归锁：UT 场景的**背景烘图**接线（空壳房间终于有画面了）。

## 一句话结论

ut 的 `game.droid` 是 **GMS2** 结构：房间内容不在 `room.Backgrounds` / `room.Tiles`
（那些是 GMS1.4 的旧槽位 —— 之前所有脚本一直读它们，所以 UT 这边**永远是空**，
`objects` 0 条 / `bg` 全 null 就是这么来的），而在 `room.Layers` 里：
背景层 + 6.9 万块 legacy tile + 1.4 万个对象实例。

`bake120.py` 按 depth 顺序把它们烘成一张房间图；`apply120.py` 按**房间名**接进场景 `bg`。

## 本套件守什么（零 Qt、零网络，只读仓库内资产）

A 接线正确性：场景名 ↔ 图名 ↔ 来源标记，三者必须彼此对得上（错位即红）
B 尺寸自洽：图尺寸 == 该房间在原作里的 w×h（对 ut 的 ROOM 表）
C 覆盖与来源：338 间用 UT 自己的图；**另 20 间如实留空** —— 它们的名字
  只在 outertale 的房间表里（UT 的 game.droid 里 0 命中），不是 UT 的房间
D 无孤儿图：`bg/ut_*.png` 每一张都被引用
E 防回滚分母闸：接线数 / 图数 / 总字节 不得跌破本轮实测值
F 自检：无恒真判据（AST 判，不扫注释）/ 无 BOM / 正负控制成对

## ★ 为什么有 20 间是空的（本轮改过一版，必须写清楚）

第一版把外传 outertale 的同名烘图接给了这 20 间。事后取证（同一份 TSV）：

    ut  game.droid ROOM = 338
    ot  game.droid ROOM = 358 = UT 的 338 间（全含） + 20 间 outertale 独有

⇒ outertale 是"UT 全量 + 自带 20 间"的结构。那 20 个名字
（`room_steamworks_*` / `room_newhome_*` / `room_of_bog` / `coming_soon` …）
**不在 UT 里**，它们是第 77 轮从跨作品大图迁入时混进 ut 章的。
给它们贴外传像素 = 拿外传美术冒充原作画面 ⇒ 已撤线（`revert120_ot.py`），
`bg: null` + `bg_source: "none"`。归属哪一章见报告 §120.6，本轮不动。

⚠️ `_zone.outertale.*.json` 那 244 个场景**本轮不动**：它们的 `original_room_id`
是本项目自编号（见该文件 note），与本轮那份 game.droid 的房间名实测 **0/244** 命中
⇒ 没有对照表就不接线，如实登记在报告 §120.6。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROUND, '_evidence')
BG = os.path.join(SCENES, 'bg')

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, (('    ' + detail) if detail else '')))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, (('    ' + detail) if detail else '')))


def _read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


def _rows(p):
    for ln in _read(p).split('\n'):
        if ln:
            yield ln.split('\t')


def _room_table(game):
    u"""`viz120.<game>.tsv` 的 ROOM 段 → {房间名: (idx, w, h)}。"""
    out = {}
    for r in _rows(os.path.join(EV, 'raw', game, 'viz120.%s.tsv' % game)):
        if r[0] == 'ROOM':
            out[r[2]] = (int(r[1]), int(r[3]), int(r[4]))
    return out


# ---------- 载入 ----------
zone = _json(os.path.join(SCENES, '_zone.ut.rooms.json'))
scenes = zone.get('scenes') or {}
UT = _room_table('ut')
OT = _room_table('outertale')

PREFIX_SRC = {'ut_': 'room.bake120.ut', 'outertale_': 'room.bake120.ot'}

with_bg = [(sid, sc) for sid, sc in scenes.items()
           if isinstance(sc, dict) and sc.get('bg')]
no_bg = [(sid, sc) for sid, sc in scenes.items()
         if isinstance(sc, dict) and not sc.get('bg')]

print('== 分母 ==')
check('A0 场景总数 358', len(scenes) == 358, str(len(scenes)))
# ★ 第120轮修正版：从"358 间全部有 bg"改成"338 有 / 20 如实留空"。
#   不是放宽 —— 撤线的那 20 间**根本不是 UT 的房间**（见模块 docstring），
#   判据的真正守点由 A0b + A0c 两条合成，比原来那一条更严。
_alien = [sid for sid, sc in scenes.items()
          if isinstance(sc, dict) and sc.get('name') not in UT]
check('A0b 338 间有 bg、20 间留空，且留空的正是"名字不在 UT 房间表里"的那批',
      len(with_bg) == 338 and len(no_bg) == 20
      and sorted(sid for sid, _sc in no_bg) == sorted(_alien),
      '有 %d / 无 %d / 名不在 UT 表 %d' % (len(with_bg), len(no_bg), len(_alien)))
check('A0c 有 bg 的那 338 间，名字**全部**在 UT 自己的房间表里（只给真 UT 房间上图）',
      all(sc.get('name') in UT for _sid, sc in with_bg)
      and len(set(sc['name'] for _sid, sc in with_bg)) == 338,
      '不在表里 %r' % [sc['name'] for _s, sc in with_bg if sc.get('name') not in UT][:5])
check('B2 ROOM 表：ut 338 间 / outertale 358 间',
      len(UT) == 338 and len(OT) == 358, '%d / %d' % (len(UT), len(OT)))

# ---------- A 接线正确性 ----------
bad_name, bad_src, missing = [], [], []
n_ut = n_ot = 0
for sid, sc in with_bg:
    bg = sc['bg']
    room = sc.get('name')
    if bg.startswith('bg/ut_'):
        pref = 'ut_'
    elif bg.startswith('bg/outertale_'):
        # ★ 撤线后**不许再出现**：外传美术冒充 UT 画面＝编造。
        #   留这条是为了"谁哪天又接回去"能当场报红（有鉴别力，不是死代码）。
        bad_name.append((sid, bg, '<外传前缀，UT 章不许用>'))
        continue
    else:
        bad_name.append((sid, bg, '<未知前缀>'))
        continue
    want = 'bg/%s%s.png' % (pref, room)
    if bg != want:
        bad_name.append((sid, bg, want))
    if sc.get('bg_source') != PREFIX_SRC[pref]:
        bad_src.append((sid, bg, sc.get('bg_source')))
    if pref == 'ut_':
        n_ut += 1
    else:
        n_ot += 1
    p = os.path.join(SCENES, bg)
    if not (os.path.isfile(p) and os.path.getsize(p) > 0):
        missing.append(bg)

check('A1 每条 bg 都等于 `bg/<前缀><场景名>.png`（不错位）', not bad_name,
      repr(bad_name[:3]))
check('A2 bg_source 与前缀一一对应', not bad_src, repr(bad_src[:3]))
check('A3 每条 bg 指向的文件都存在且非空', not missing, repr(missing[:5]))
check('A4 分账：338 张 ut_，0 张 outertale_（外传图已撤线）',
      (n_ut, n_ot) == (338, 0), '%d / %d' % (n_ut, n_ot))

# ---------- B 尺寸自洽 ----------
nomatch_ut = [sc['name'] for sid, sc in with_bg
              if sc['bg'].startswith('bg/ut_') and sc['name'] not in UT]
check('B1 ut_ 那批的房间名全在 ut 的 ROOM 表里', not nomatch_ut, repr(nomatch_ut[:5]))
# ★ 原 B1b 是「outertale_ 那批的名字全在 outertale 表里」——
#   撤线后 `with_bg` 里已无外传条目 ⇒ 对空集成立 ⇒ **恒真**（正是本项目最忌的形状）。
#   改成对**撤线的那 20 间**做实质断言：它们的名字必须 "∈OT 且 ∉UT"，
#   一个都不能例外（例外就意味着"撤错了"或"UT 其实有这间房"）。
_alien_names = [sc.get('name') for _sid, sc in no_bg]
_alien_bad = [n for n in _alien_names if not (n in OT and n not in UT)]
check('B1b 留空的 20 间，名字必须"在 outertale 表里、且不在 UT 表里"（撤线理由成立）',
      len(_alien_names) == 20 and not _alien_bad,
      '共 %d；不成立 %r' % (len(_alien_names), _alien_bad[:5]))

try:
    from PIL import Image
    import random
    random.seed(120)
    size_bad = []
    for sid, sc in random.sample(with_bg, 14):
        p = os.path.join(SCENES, sc['bg'])
        w, h = Image.open(p).size
        tab = UT if sc['bg'].startswith('bg/ut_') else OT
        _i, rw, rh = tab[sc['name']]
        if (w, h) != (rw, rh):
            size_bad.append((sc['name'], (w, h), (rw, rh)))
    check('B3 抽样 14 张：图尺寸 == 原作房间 w×h', not size_bad, repr(size_bad[:3]))

    # 内容闸：不是一张纯色空图。
    # ⚠️ 白名单只收**实测确认本来就空**的房间：开场文字/图片是对象自绘的，
    #    按纪律我们**不模拟自绘**（见 bake120 的 custom 过滤）⇒ 烘出来就是纯黑。
    BLANK = {'room_start', 'room_introstory', 'room_introimage', 'room_intromenu',
             'room_emptyblack', 'room_emptywhite', 'room_nothingness',
             'room_empty', 'room_flowey_regret', 'room_friendtest',
             'room_bringitinguys', 'room_of_dog', 'room_goodbyeasriel',
             'room_undertale', 'room_afinaltest', 'room_quizholder',
             'room_asrieltest', 'room_asrielmemory'}
    blank, tested = [], 0
    for sid, sc in with_bg:
        if sc['name'] in BLANK:
            continue
        tested += 1
        if tested > 40:
            break
        im = Image.open(os.path.join(SCENES, sc['bg'])).convert('RGB')
        ncol = len(set(im.resize((32, 32)).getdata()))
        if ncol <= 2:
            blank.append((sc['name'], ncol))
    check('B4 抽 40 张非纯色：颜色种类 > 2（真画了东西）', not blank, repr(blank[:5]))
except ImportError:                                   # pragma: no cover
    check('B3/B4 需要 PIL 才能验尺寸与内容', False, 'PIL 未安装')

# ---------- C 覆盖与来源（防"贴错房" / 防"该有图却没图"）----------
# C1（第一版）问的是"那 20 间是不是只在 outertale 里" —— 撤线后这个问法
# 只剩 B1b 在守。这里改成守**撤线结果本身**：这 20 间必须真的是空，
# 且**必须**显式写 `bg_source: "none"`（不许留个"看着像接了"的残留）。


def _c1_ok(sc):
    u"""留空口径：bg 为 null 且 bg_source 显式 none。"""
    return sc.get('bg') is None and sc.get('bg_source') == 'none'


def _c2_ok(sc):
    u"""UT 自己的房间不许留空。"""
    return sc.get('name') not in UT


check('C1 留空的 20 间：`bg` 必须为 null 且 `bg_source` 必须显式 == "none"',
      len(no_bg) == 20 and all(_c1_ok(sc) for _sid, sc in no_bg),
      '不合格 %r' % [(sid, sc.get('bg'), sc.get('bg_source'))
                  for sid, sc in no_bg if not _c1_ok(sc)][:3])

# C2 反向守：不许把"UT 自己的房间"漏成 none（该有图却没图 = 静默丢画面）。
#    两条合起来才是全称：UT 房 ⇒ 有图；非 UT 房 ⇒ 留空。任一方向破了都报红。
check('C2 不许有"名字在 UT 表里却留空"的场景（该有图却没图 = 静默丢画面）',
      not [sid for sid, sc in no_bg if not _c2_ok(sc)],
      repr([sid for sid, sc in no_bg if not _c2_ok(sc)][:5]))

# 负控制：把同一对判据喂给**合成样本**，四种组合各验一次（不是恒真）。
check('C3 负控制：C1/C2 的判据对合成样本各方向都有鉴别力',
      _c1_ok({'bg': None, 'bg_source': 'none'}) is True
      and _c1_ok({'bg': None, 'bg_source': 'room.bake120.ot'}) is False
      and _c1_ok({'bg': 'bg/ut_x.png', 'bg_source': 'none'}) is False
      and _c2_ok({'name': 'room_of_bog'}) is True
      and _c2_ok({'name': 'room_ruins1'}) is False)

# ---------- D 无孤儿图 ----------
refd = set(os.path.basename(sc['bg']) for sid, sc in with_bg)
ondisk_ut = set(f for f in os.listdir(BG) if f.startswith('ut_') and f.endswith('.png'))
ondisk_ot = set(f for f in os.listdir(BG)
                if f.startswith('outertale_') and f.endswith('.png'))
check('D1 没有孤儿图（ut_ 都被引用）',
      not (ondisk_ut | ondisk_ot) - refd,
      repr(sorted((ondisk_ut | ondisk_ot) - refd)[:5]))
check('D2 图数 == 引用数 == 338，且 bg/ 下没有残留的 outertale_*.png',
      len(ondisk_ut) == 338 and len(refd) == 338 and not ondisk_ot,
      '%d / %d / 残留外传图 %d' % (len(ondisk_ut), len(refd), len(ondisk_ot)))

# ---------- E 防回滚 ----------
total_bytes = sum(os.path.getsize(os.path.join(BG, f))
                  for f in (ondisk_ut | ondisk_ot))
check('E1 有 bg 的场景数 == 338（防批量清空；20 间留空是已取证的事实）',
      len(with_bg) == 338, str(len(with_bg)))
check('E2 bg 图总字节 ≥ 2 MB（防批量置空文件）', total_bytes >= 2_000_000,
      str(total_bytes))

# ---------- F 自检 ----------
src = _read(os.path.abspath(__file__))
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
check('F1 没有 `check(x, True)` 这种恒真判据（AST 判，不扫注释）',
      not _true_checks, repr(_true_checks[:5]))
check('F2 资产文件无 BOM（U+FEFF）',
      not _read(os.path.join(SCENES, '_zone.ut.rooms.json')).startswith(u'\ufeff'))


def _name_ok(sc, bg):
    return bg == 'bg/ut_%s.png' % sc.get('name')


check('F3 正/负控制成对：同名通过、邻房名必须报红',
      _name_ok({'name': 'room_start'}, 'bg/ut_room_start.png') is True
      and _name_ok({'name': 'room_start'}, 'bg/ut_room_ruins1.png') is False)
check('F4 负控制：前缀与来源标记的对应关系不是恒真',
      PREFIX_SRC['ut_'] != PREFIX_SRC['outertale_']
      and PREFIX_SRC['outertale_'] == 'room.bake120.ot')

print('---- 共 %d 条：PASS %d / FAIL %d' % (_n_pass + _n_fail, _n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  · ' + d)
sys.exit(1 if _failed else 0)
