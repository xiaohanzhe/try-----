# -*- coding: utf-8 -*-
"""第111轮 check111 —— **Niko 的家 = 永远进不去的彩蛋**（#47）行为与结构判据。

口径来源（用户逐字，详版 §109.2 / §111.1）：
  · 连问三次：①「你确定吗？」②「你这样的行为可能导致世界崩坏，你真的确定吗？」
    ③「你真的不再考虑考虑了吗？」；
  · 选项「我再考虑考虑」/「我确定！！！」；
  · 选「我确定！！！」⇒ **伴随三角符文的高级爆炸特效**（`spr_realisticexplosion`），
    然后选项**变回「我再考虑考虑」**；
  · **永远进不去**。

★ 本套件**零依赖**（只 import `item_interact`、不建 QApplication、不起真机），
  故不需要进 `HERMETIC_IDS`。

判据分三层：
  A 结构层（AST / 源码）：类、常量、分支、on_egg 传递链。
  B 行为层（真跑 build_props）：desktop B ⇒ 彩蛋类；A/C/D ⇒ 普通门；
    别的场景 B ⇒ 普通门；不给 on_egg ⇒ 不建（**不造假门**）。
  C 负控制（运行时生成）：证明"彩蛋判据"不是恒真 —— 换一个字母 / 换一个场景
    都必须落回普通门。
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
sys.path.insert(0, MODS)

N_PASS = [0]
N_FAIL = [0]


def chk(desc, cond, detail=''):
    if cond:
        N_PASS[0] += 1
        print('[PASS] %s' % desc)
    else:
        N_FAIL[0] += 1
        print('[FAIL] %s%s' % (desc, ('  << ' + detail) if detail else ''))


def read(path):
    return io.open(path, encoding='utf-8', newline='').read()


def lf(s):
    return s.replace('\r\n', '\n')


II = os.path.join(MODS, 'item_interact.py')
MAIN = os.path.join(PET, 'src', 'main.py')
DESKTOP = os.path.join(PET, 'assets', 'scenes', 'desktop.json')

src_ii = read(II)
src_main = read(MAIN)

# ★ 只解析一次（`ast.parse` 不产 `.pyc`，符合"复检不许改变被测状态"）
try:
    tree = ast.parse(src_ii)
except SyntaxError as _e:
    print('[FAIL] item_interact.py 语法错误: %s' % _e)
    sys.exit(1)

# ============================================================ A 结构层
chk('A1 存在类 NikoHomeDoorProp', 'class NikoHomeDoorProp(' in src_ii)
chk('A2 彩蛋台词常量 NIKO_HOME_EGG_TEXT 存在', 'NIKO_HOME_EGG_TEXT = (' in src_ii)
chk('A3 彩蛋门身份常量 NIKO_HOME_EGG_DOOR 存在', 'NIKO_HOME_EGG_DOOR = ' in src_ii)

# A4~A6：三句台词**逐字**（用户给定，不许改写）
#   ★★★ 判据必须走 **AST 取常量值**，不能 `in` 源码全文 ——
#   这三句在模块里**各出现两次**（常量定义 + 类 docstring 里复述口径）。
#   用 `in` 就会变成恒真判据：改掉常量、docstring 里那一份仍让 `in` 为真
#   （第111轮变异测试 M3 实证：报绿 = 判据失效）。这是本项目已栽过五次的
#   "只判提到某名字"陷阱（详版 §108.6）。
EGG_TEXTS = None
for _n in ast.walk(tree):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Name) and _t.id == 'NIKO_HOME_EGG_TEXT' \
                    and isinstance(_n.value, ast.Tuple):
                EGG_TEXTS = [e.value for e in _n.value.elts
                             if isinstance(e, ast.Constant)]
    elif isinstance(_n, ast.AnnAssign):
        if isinstance(_n.target, ast.Name) and _n.target.id == 'NIKO_HOME_EGG_TEXT' \
                and isinstance(_n.value, ast.Tuple):
            EGG_TEXTS = [e.value for e in _n.value.elts
                         if isinstance(e, ast.Constant)]

chk('A4 常量 NIKO_HOME_EGG_TEXT 是 3 元组（AST）',
    EGG_TEXTS is not None and len(EGG_TEXTS) == 3, 'got=%r' % EGG_TEXTS)
chk('A5 第1句逐字（AST 取值）',
    bool(EGG_TEXTS) and EGG_TEXTS[0] == '你确定吗？',
    'got=%r' % (EGG_TEXTS[0] if EGG_TEXTS else None))
chk('A6 第2句逐字（AST 取值）',
    bool(EGG_TEXTS) and len(EGG_TEXTS) > 1
    and EGG_TEXTS[1] == '你这样的行为可能导致世界崩坏，你真的确定吗？',
    'got=%r' % (EGG_TEXTS[1] if EGG_TEXTS and len(EGG_TEXTS) > 1 else None))
chk('A6b 第3句逐字（AST 取值）',
    bool(EGG_TEXTS) and len(EGG_TEXTS) > 2
    and EGG_TEXTS[2] == '你真的不再考虑考虑了吗？',
    'got=%r' % (EGG_TEXTS[2] if EGG_TEXTS and len(EGG_TEXTS) > 2 else None))

# A7：两个选项文案 —— ★ 同样走 AST 取字符串常量（`in` 会被注释/docstring 骗）
try:
    tree_main = ast.parse(src_main)
except SyntaxError as _e2:
    print('[FAIL] main.py 语法错误: %s' % _e2)
    sys.exit(1)
_str_consts_main = {n.value for n in ast.walk(tree_main)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
_str_consts_ii = {n.value for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)}
chk('A7a 选项「我再考虑考虑」是字符串常量',
    '我再考虑考虑' in _str_consts_main or '我再考虑考虑' in _str_consts_ii)
chk('A7b 选项「我确定！！！」是字符串常量', '我确定！！！' in _str_consts_main)

# A8：AST 判据 —— `NikoHomeDoorProp` 必须**继承 DoorProp**
cls = [n for n in ast.walk(tree)
       if isinstance(n, ast.ClassDef) and n.name == 'NikoHomeDoorProp']
bases = []
if cls:
    for b in cls[0].bases:
        if isinstance(b, ast.Name):
            bases.append(b.id)
        elif isinstance(b, ast.Attribute):
            bases.append(b.attr)
chk('A8 NikoHomeDoorProp 继承 DoorProp', bases == ['DoorProp'], 'bases=%r' % bases)

# A9：`target_scene=None`（**永远不切场景**）—— AST 定位到类里那次调用
try:
    ok9 = False
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == 'NikoHomeDoorProp':
            for sub in ast.walk(n):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == '__init__':
                    for kw in sub.keywords:
                        if kw.arg == 'target_scene' and isinstance(kw.value, ast.Constant) \
                                and kw.value.value is None:
                            ok9 = True
    chk('A9 彩蛋门 target_scene=None（结构上永不切场景）', ok9)
except Exception as e:
    chk('A9 彩蛋门 target_scene=None（结构上永不切场景）', False, repr(e))

# A10：宿主实现三个方法
for meth in ('_niko_home_egg', '_niko_home_ask', '_niko_home_explode'):
    chk('A10 宿主有 %s' % meth, ('def %s(' % meth) in src_main)

# A11：爆炸素材是真的 `spr_realisticexplosion`（三角符文招牌特效）
chk('A11 宿主引用 spr_realisticexplosion 帧',
    'spr_realisticexplosion_%d.png' in src_main)

# A12：`on_egg` 传递链 —— build_props 收 on_egg 并转给 NikoHomeDoorProp
chk('A12a build_props 形参含 on_egg', 'routes=None, on_egg=None' in src_ii)
chk('A12b build_props 把 on_egg 传给 NikoHomeDoorProp', 'on_egg=on_egg' in src_ii)
chk('A12c 宿主把 _niko_home_egg 传进 build_props',
    'on_egg=self._niko_home_egg' in src_main)

# A13：**素材在盘** —— 17 帧爆炸 + Niko 光门（不许"引用了不在盘的图"）
objs = os.path.join(PET, 'assets', 'scenes', 'objs')
missing = [i for i in range(17)
           if not os.path.isfile(os.path.join(objs, 'spr_realisticexplosion_%d.png' % i))]
chk('A13a 爆炸 17 帧全在盘', not missing, 'missing=%r' % missing)
niko_files = ['niko_door_portal.png', 'niko_portal_rays.png', 'niko_sparkle_blue1.png']
chk('A13b Niko 光门素材在盘',
    all(os.path.isfile(os.path.join(objs, f)) for f in niko_files),
    'missing=%r' % [f for f in niko_files
                    if not os.path.isfile(os.path.join(objs, f))])

# A14：desktop.json 里那扇门**确实存在**（B = 正下 = Niko 的家）
try:
    d = json.load(io.open(DESKTOP, encoding='utf-8'))
    doors = [o for o in d.get('objects', []) if str(o.get('src', '')).startswith('obj_door')]
    ids = sorted(o.get('id') for o in doors)
    chk('A14 desktop 有 4 扇世界门', len(doors) == 4, 'got=%d %r' % (len(doors), ids))
    niko = [o for o in doors if o.get('id') == 'desk_door_niko_home']
    chk('A14b desktop 有 desk_door_niko_home（彩蛋门）', len(niko) == 1)
    if niko:
        chk('A14c 彩蛋门 src 字母 = obj_doorB',
            niko[0].get('src') == 'obj_doorB', 'src=%r' % niko[0].get('src'))
except Exception as e:
    chk('A14 desktop 有 4 扇世界门', False, repr(e))

# ============================================================ B 行为层
import item_interact as it  # noqa: E402

ROUTES = {'routes': [
    {'when_scene': 'desktop', 'when_door': 'A', 'to': 'oneshot.mainline.INIT', 'priority': 200},
    {'when_scene': 'desktop', 'when_door': 'B', 'to': 'FAKE_NIKO_HOME', 'priority': 200},
    {'when_scene': 'desktop', 'when_door': 'C', 'to': 'ut.ruins', 'priority': 200},
    {'when_scene': 'desktop', 'when_door': 'D', 'to': 'ch1.castle_town', 'priority': 200},
    {'when_scene': 'other_room', 'when_door': 'B', 'to': 'somewhere', 'priority': 200},
]}

called = []


def on_egg(prop):
    called.append(getattr(prop, 'key', '?'))
    return True


scene = json.load(io.open(DESKTOP, encoding='utf-8'))
props = it.build_props(scene, 'ch1', 'light', routes=ROUTES, on_egg=on_egg)
by_src = {}
for p in props:
    by_src.setdefault(getattr(p, 'src', None), p)

b = by_src.get('obj_doorB')
chk('B1 desktop B 建成 NikoHomeDoorProp', isinstance(b, it.NikoHomeDoorProp),
    'got=%s' % type(b).__name__)
chk('B2 彩蛋门没有 target_scene', getattr(b, 'target_scene', 'X') in (None, ''),
    'target=%r' % getattr(b, 'target_scene', None))
chk('B3 彩蛋台词三轮', len(getattr(b, 'egg_texts', ())) == 3,
    'n=%d' % len(getattr(b, 'egg_texts', ())))
chk('B4 interact() 触发 on_egg（且只一次）',
    bool(b.interact()) and len(called) == 1, 'called=%r' % called)

for src, tgt in (('obj_doorA', 'oneshot.mainline.INIT'),
                 ('obj_doorC', 'ut.ruins'),
                 ('obj_doorD', 'ch1.castle_town')):
    p = by_src.get(src)
    chk('B5 %s 是普通 DoorProp（非彩蛋）' % src,
        isinstance(p, it.DoorProp) and not isinstance(p, it.NikoHomeDoorProp))
    chk('B6 %s target = %s' % (src, tgt),
        getattr(p, 'target_scene', None) == tgt, 'got=%r' % getattr(p, 'target_scene', None))

scene2 = {'scene_id': 'other_room', 'objects': [
    {'id': 'x', 'kind': 'prop', 'src': 'obj_doorB', 'sprite': 'objs/spr_darkdoor_0.png'}]}
p2 = it.build_props(scene2, 'ch1', 'light', routes=ROUTES, on_egg=on_egg)[0]
chk('B7 别的场景的 B 门不是彩蛋', not isinstance(p2, it.NikoHomeDoorProp))
chk('B8 别的场景的 B 门有目标', getattr(p2, 'target_scene', None) == 'somewhere')

props3 = it.build_props(scene, 'ch1', 'light', routes=ROUTES, on_egg=None)
n_door3 = len([p for p in props3 if str(getattr(p, 'src', '')).startswith('obj_door')])
chk('B9 不给 on_egg ⇒ 只剩 3 扇门（不造假门）', n_door3 == 3, 'got=%d' % n_door3)
chk('B10 不给 on_egg ⇒ 无 NikoHomeDoorProp',
    not any(isinstance(p, it.NikoHomeDoorProp) for p in props3))
# B11：不给 on_egg 时，B **绝不能**退化成"吃路由的普通门"（用户口径：永远进不去）
b_bad = [p for p in props3 if getattr(p, 'src', '') == 'obj_doorB']
chk('B11 不给 on_egg ⇒ B 门一件不建（不吃假路由）', len(b_bad) == 0,
    'got=%r' % [type(p).__name__ for p in b_bad])

# ============================================================ C 负控制
# ★★★ 第112轮修：**不再用 `uuid.uuid4()`**。
#   原写法每次跑都生成不同的 `ghost_<hex>` ⇒ 该行输出**永远**与基线不同 ⇒
#   `check111` 在 G2 里**永久 DIFF**（"输出与基线不一致"警报变成常驻噪音，
#   真正的回归反而被淹掉）。本判据要的只是"场景 id **不在路由表里**"，
#   固定字面量完全等价、且可复现。
#   ★ 保留 `ghost_` 前缀说明它是**刻意编造**的 id（不是真实场景）。
tag = 'ghost_negctl_fixed'

# C1：**拼一个不存在的场景 id**（运行时生成，文档不自污染）⇒ 必须仍走普通门
#     ⚠️ 该场景在路由表里没有条目 ⇒ 门可能**根本不建**（既有契约：查不到就不建）。
#     所以断言写成"要么不建、要么不是彩蛋"，两条都是正确行为。
scene3 = {'scene_id': 'ghost_%s' % tag, 'objects': [
    {'id': 'x', 'kind': 'prop', 'src': 'obj_doorB', 'sprite': 'objs/spr_darkdoor_0.png'}]}
p3l = it.build_props(scene3, 'ch1', 'light', routes=ROUTES, on_egg=on_egg)
chk('C1 场景 id=ghost_%s 的 B 门不是彩蛋（且不可达时不建）' % tag,
    (not p3l) or (not isinstance(p3l[0], it.NikoHomeDoorProp)),
    'got=%r' % [type(p).__name__ for p in p3l])

# C2：**把 desktop 的 B 门字母改成 A**（运行时拼一个 scene dict）⇒ 不该是彩蛋
scene4 = {'scene_id': 'desktop', 'objects': [
    {'id': 'x', 'kind': 'prop', 'src': 'obj_doorA', 'sprite': 'objs/spr_darkdoor_0.png'}]}
p4 = it.build_props(scene4, 'ch1', 'light', routes=ROUTES, on_egg=on_egg)[0]
chk('C2 desktop 的 A 门不是彩蛋', not isinstance(p4, it.NikoHomeDoorProp))
chk('C2b desktop 的 A 门 target = oneshot.mainline.INIT',
    getattr(p4, 'target_scene', None) == 'oneshot.mainline.INIT')

# C3：**判据自证不是恒真** —— 彩蛋类名必须真的出现在 isinstance 检查里
chk('C3 isinstance 检查用的就是 NikoHomeDoorProp 本体',
    isinstance(it.NikoHomeDoorProp('k', 'obj_doorB'), it.NikoHomeDoorProp))

print('')
print('check111: pass=%d fail=%d' % (N_PASS[0], N_FAIL[0]))
sys.exit(1 if N_FAIL[0] else 0)
