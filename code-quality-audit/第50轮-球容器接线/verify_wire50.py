# -*- coding: utf-8 -*-
"""第50轮回归锁：光世界「扭蛋球」容器**接线** —— 从规则到像素的最后一跳。

为什么单开一套（而不是并进 npc_round49）
----------------------------------------
第49轮锁的是**规则层**（球能不能进 / 能不能脱 / 画几层）。
本轮锁的是**接线层**：第44轮的教训是「函数写对了但产品用不上」是本项目最贵的坑
（记忆铁律 §4）—— 规则全对、球却没人画，回归锁必须能抓到。
所以本套件专盯四件事：

  1. `scene_render` 产出的**四层指令**（顺序 / 帧号 / 素材名 / 滤镜载荷）；
  2. `scene_render.split_bubble_layers` 的**分流**（后层留给画布、前层留给 overlay）；
  3. `scene_canvas` 的**消费**（真把后层画成像素、角色层只叠塑料滤镜）；
  4. `main.py` 的**装配**（谁建 overlay / 谁 raise_ / 谁把 bubbles 传进 plan_frame / 谁建交互入口）。

判据纪律（沿用本项目既有教训）
* ✅ 能上 AST 就上 AST；断言**结构/行为**，不断赋值。
* ✅ 需要「不能报红」的地方必须有**正/负控制成对**。
* ✅ 锚定原作帧号时**读仓库内 GML 逐字产物**（第49轮证据，随仓库走）。
* ⛔ 不写 `check(cid, True, ...)` 这种"看着在守其实没守"的恒真判据。

用法:
    C:\\Python311\\python.exe verify_wire50.py            # 跑（cwd 建议=仓库根）
    （`--update` 由 run_all.py 的合并模式处理，本脚本不解释参数）

⚠️ 涉及 QPixmap / QWidget ⇒ 必须 offscreen（run_all.py 里注册为 offscreen=True）。
"""
import ast
import io
import os
import re
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
BUBBLE_DIR = os.path.join(PET, 'assets', 'bubble')
# 第49轮的 GML 逐字产物（随仓库走，不是"用后即删"的临时区）
GML49 = os.path.join(ROOT, 'code-quality-audit', '第49轮-NPC与球容器',
                     '_evidence', 'gml')

# ★ 裸进程脚本读 QPixmap 前必须先建 QApplication（记忆铁律）
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

sys.path.insert(0, MODS)

FAILS = []
PASSES = []


def check(cid, ok, msg):
    # ⚠️ 必须打印 `[PASS]` **字面量**：run_all.py:425 按 `[PASS]`/`[OK]` 计数，
    #    写成 "  PASS  msg" ⇒ PASS 恒 0（记忆铁律）。
    tag = '[PASS]' if ok else '[FAIL]'
    print('%s %-5s %s' % (tag, cid, msg))
    (PASSES if ok else FAILS).append(cid)


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


# ================================================================ A 零依赖 + 常量同源
ALLOWED_TOP = {'logging'}


def _imports(path):
    """→ (顶层模块名集合, 函数内 import 列表)。

    ⚠️ 判据坑（第49轮首跑踩到）：模块级降级写法
        try: from logger_utils import get_logger
        except ImportError: ...
    在 AST 上的父节点是 `Try` 而不是 `Module` ⇒ 按"Module 直接子节点"判会误报。
    正确判据 = **按"是否位于函数体内"来分**。
    """
    tree = ast.parse(rd(path))
    tops = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            tops.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            tops.add((node.module or '').split('.')[0])
        elif isinstance(node, ast.Try):     # 模块级 try/except 的降级 import 算顶层
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    tops.update(a.name.split('.')[0] for a in sub.names)
                elif isinstance(sub, ast.ImportFrom):
                    tops.add((sub.module or '').split('.')[0])
    inner = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = []
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Import):
                    names.extend(a.name.split('.')[0] for a in sub.names)
                elif isinstance(sub, ast.ImportFrom):
                    names.append((sub.module or '').split('.')[0])
            if names:
                inner[fn.name] = names
    return tops, inner


_r_top, _r_inner = _imports(os.path.join(MODS, 'scene_render.py'))
check('A1', _r_top <= ALLOWED_TOP,
      'scene_render 顶层 import ⊆ %s（实得 %s）—— 纯数据层不许 import 项目内模块/Qt'
      % (sorted(ALLOWED_TOP), sorted(_r_top)))
check('A2', not _r_inner,
      'scene_render 无函数内 import（实得 %r）—— 初始化环纪律' % (_r_inner,))

# 常量同源：scene_render（渲染层）与 bubble_system（规则层）刻意写两份，
# 改了一边忘另一边 ⇒ 本判据立刻报红。
import scene_render as R        # noqa: E402
import bubble_system as B       # noqa: E402
import npc_system as N          # noqa: E402

check('A3', R.BUBBLE_SPRITE == B.SPRITE,
      '球精灵名同源（render=%r sys=%r）' % (R.BUBBLE_SPRITE, B.SPRITE))
check('A4', (R.BUBBLE_FRAME_TOP, R.BUBBLE_FRAME_BACK, R.BUBBLE_FRAME_FRONT)
      == (B.FRAME_TOP, B.FRAME_BACK, B.FRAME_FRONT) == (1, 2, 3),
      '三层帧号同源且 = (1,2,3)（实得 %r）'
      % ((R.BUBBLE_FRAME_TOP, R.BUBBLE_FRAME_BACK, R.BUBBLE_FRAME_FRONT),))
check('A5', R.BUBBLE_PREFIX == 'bubble:'
      and R.bubble_sprite_name(2).endswith('_2.png')
      and R.bubble_sprite_name(2).startswith('bubble:'),
      '素材名规则 = `bubble:<spr>_<frame>.png`（实得 %r）' % R.bubble_sprite_name(2))

# ================================================================ B 计划层：四层序
import scene_camera as C        # noqa: E402

cam = C.Camera((640, 480), 0, 2.0)      # ★ border 是**标量**（不是矩形）
cam.follow((0.0, 0.0, 800.0, 240.0), (100.0, 100.0, 140.0, 140.0))
# ⚠️ 判据坑：`scene` 必须是**带属性的对象**（`plan_frame` 用 `getattr(scene,'objects')`）。
#    首版误用 plain dict ⇒ objects 恒取不到 ⇒ B9「球在物件之后」变成恒真/恒假，
#    且 room_border 也永不产出 ⇒ B10 失去鉴别力。用 SimpleNamespace（与冒烟探针同）。
# 带 1 个物件：用于验证「球压在物件之后」（顺序判据）
# 房间比相机宽（800 > 640/scale）⇒ 会产出 room_border，B10 才有意义。
_scene_ord = SimpleNamespace(
    original_room_id=2, chapter_id='ch1', bg=None,
    objects=[{'pos': (100.0, 100.0), 'sprite': 'objs/test', 'depth': 0}])
_geo = {'ch1:2': {'w': 800, 'h': 240, 'name': 'probe'}}

BUBBLES = [{
    'char': 'ralsei', 'ball_xy': (160.0, 120.0), 'char_xy': (160.0, 120.0),
    'scale': 1.6, 'angle': -150.0, 'alpha': 1.0, 'char_size': (100, 100),
    'char_sprite': None, 'char_frame': 0,
    'filter': {'tint': (222, 231, 238), 'alpha': 0.88,
               'rim': 0.18, 'saturate': 0.92},
}]


def _no_size(_name):
    """不提供真实素材尺寸 ⇒ 球退回原作的 62×62（另有用真尺寸的 B8）。"""
    return None


plan = R.plan_frame(_scene_ord, cam, _geo, tick=0, sprite_size=_no_size,
                    bubbles=BUBBLES)
bub = [it for it in plan if it.get('kind') == R.K_BUBBLE]
roles = [it.get('role') for it in bub]
check('B1', len(bub) == 4, '一个球 ⇒ 4 条指令（实得 %d）' % len(bub))
check('B2', roles == [R.BUBBLE_ROLE_BACK, R.BUBBLE_ROLE_CHAR,
                      R.BUBBLE_ROLE_FRONT, R.BUBBLE_ROLE_TOP],
      '★ 四层顺序 = 原作 Draw_0：back→character→front→top（实得 %r）' % (roles,))
check('B3', tuple(roles) == tuple(R.BUBBLE_DRAW_ROLES),
      '顺序常量 BUBBLE_DRAW_ROLES 与产出顺序一致')

names = [it.get('name') for it in bub]
check('B4', names[0].endswith('_2.png') and names[2].endswith('_3.png')
      and names[3].endswith('_1.png'),
      '★ 帧号落位：back=2 / front=3 / top=1（实得 %r）' % (names,))
check('B5', all(isinstance(n, str) and n.startswith('bubble:')
                for n in (names[0], names[2], names[3])),
      '球层素材名带 `bubble:` 前缀（供 SceneAssetCache 解析到 assets/bubble/）')
check('B6', bub[1].get('name') is None and bub[1].get('char') == 'ralsei',
      '角色层不携带素材名（角色像素由 sprite_label 画）')
check('B7', isinstance(bub[1].get('filter'), dict)
      and tuple(bub[1]['filter'].get('tint')) == (222, 231, 238),
      '角色层携带塑料滤镜载荷（tint=222,231,238）')
check('B8', abs(float(bub[0].get('angle', 0.0)) - (-150.0)) < 1e-6
      and abs(float(bub[1].get('angle', 0.0))) < 1e-9,
      '球层带角度、角色层角度恒 0（角色层不旋转）')

# —— 顺序：球必须**在物件之后**（球压住物件）——
idx_obj = [i for i, it in enumerate(plan) if it.get('kind') == R.K_OBJ]
idx_bub = [i for i, it in enumerate(plan) if it.get('kind') == R.K_BUBBLE]
idx_border = [i for i, it in enumerate(plan) if it.get('kind') == R.K_ROOM_BORDER]
check('B9', idx_obj and idx_bub and min(idx_bub) > max(idx_obj),
      '球指令在物件**之后**（物件 %r / 球 %r）' % (idx_obj, idx_bub))
check('B10', idx_border and min(idx_bub) < min(idx_border),
      '球指令在边框**之前**（边框永远最上；物件 %r / 球 %r / 边框 %r）'
      % (idx_obj, idx_bub, idx_border))

# —— 负控制：没有球 ⇒ 零行为变化 ——
plan0 = R.plan_frame(_scene_ord, cam, _geo, tick=0, sprite_size=_no_size)
check('B11', not [it for it in plan0 if it.get('kind') == R.K_BUBBLE],
      'bubbles 缺省 ⇒ 不产任何球指令（老调用方零行为变化）')
# —— 负控制：非法球项只跳过、绝不抛 ——
plan_bad = R.plan_frame(_scene_ord, cam, _geo, tick=0, sprite_size=_no_size,
                        bubbles=[{'char': 'x'}, 'not-a-dict', None])
check('B12', not [it for it in plan_bad if it.get('kind') == R.K_BUBBLE],
      '非法球项（无坐标/非字典/None）只跳过，绝不抛')

# ================================================================ C 分流
behind, front = R.split_bubble_layers(plan)
check('C1', [it.get('role') for it in behind
             if it.get('kind') == R.K_BUBBLE] == [R.BUBBLE_ROLE_BACK],
      'behind（角色之下）只含球后层 back')
check('C2', [it.get('role') for it in front] == [R.BUBBLE_ROLE_CHAR,
                                                 R.BUBBLE_ROLE_FRONT,
                                                 R.BUBBLE_ROLE_TOP],
      'front（角色之上）= 角色层 + 前层 + 上罩（实得 %r）'
      % ([it.get('role') for it in front],))
# ⚠️ 判据坑（首跑误报）：分流是"稳定分桶"，不是"把前层挪到最后" ——
#    `behind + front` **不等于** plan 的全局序（边框在球之后，却属 behind）。
#    正确不变量：① 无丢失/无重复（多重集相等）；② 各自内部**保相对序**。
_ids_plan = [id(x) for x in plan]
_ids_b = [id(x) for x in behind]
_ids_f = [id(x) for x in front]
check('C3', len(_ids_b) + len(_ids_f) == len(_ids_plan)
      and sorted(_ids_b + _ids_f) == sorted(_ids_plan)
      and _ids_b == [i for i in _ids_plan if i in set(_ids_b)]
      and _ids_f == [i for i in _ids_plan if i in set(_ids_f)],
      '两层 = 原计划（无丢失/无重复，且各自保相对序）'
      'behind=%d front=%d plan=%d' % (len(_ids_b), len(_ids_f), len(_ids_plan)))
_b2, _f2 = R.split_bubble_layers(plan0)
check('C4', _f2 == [] and len(_b2) == len(plan0),
      '无球计划 ⇒ front 为空、behind == 全量（负控制：分流器不凭空造层）')
check('C5', R.split_bubble_layers([]) == ([], [])
      and R.split_bubble_layers(None) == ([], []),
      '空 / None 计划不抛')

# ================================================================ D 画布消费
from PyQt5.QtWidgets import QApplication      # noqa: E402
from PyQt5.QtGui import QColor, QBrush        # noqa: E402
_app = QApplication.instance() or QApplication([])

import scene_canvas as SC       # noqa: E402


class FakePainter(object):
    """最小假画笔：**没有** save/rotate ⇒ 顺便覆盖"退化不旋转"分支。"""

    def __init__(self):
        self.calls = []
        self.fills = []

    def fillRect(self, rect, brush=None):
        self.calls.append('fillRect')
        self.fills.append((rect, brush))

    def drawLine(self, *a):
        self.calls.append('drawLine')

    def drawPixmap(self, *a):
        self.calls.append('drawPixmap')

    def drawRect(self, *a):
        self.calls.append('drawRect')

    def setPen(self, *a):
        self.calls.append('setPen')

    def setOpacity(self, *a):
        self.calls.append('setOpacity')


class FakePixmap(object):
    def __init__(self, w=62, h=62, null=False):
        self._w, self._h, self._null = w, h, null

    def isNull(self):
        return self._null

    def width(self):
        return self._w

    def height(self):
        return self._h


class FakeAssets(object):
    def __init__(self, null=False):
        self._null = null

    def get(self, name):
        if not name:
            return None
        return FakePixmap(null=self._null)


pa = FakePainter()
drawn_b = SC.paint_on(pa, behind, FakeAssets(), (640, 480))
check('D1', drawn_b >= 1 and 'drawPixmap' in pa.calls,
      '画布真把球后层画成像素（drawn=%d calls=%s）' % (drawn_b, pa.calls))

pf = FakePainter()
drawn_f = SC.paint_on(pf, front, FakeAssets(), (640, 480))
check('D2', drawn_f == 3 and pf.calls.count('drawPixmap') == 2
      and pf.calls.count('fillRect') == 1,
      'overlay 层：2 张球壳 pixmap + 1 次滤镜 fillRect（drawn=%d calls=%s）'
      % (drawn_f, pf.calls))
check('D3', hasattr(SC, 'BubbleOverlay'),
      'scene_canvas 暴露 BubbleOverlay 控件类（前层要有自己的控件）')

# —— 塑料滤镜：cover = clamp(1 - alpha) ——
_fp = FakePainter()
SC.paint_on(_fp, [bub[1]], FakeAssets(), (640, 480))
_br = _fp.fills[0][1] if _fp.fills else None
_af = _br.color().alphaF() if isinstance(_br, QBrush) else -1.0
check('D4', abs(_af - 0.12) < 0.02,
      '★ 塑料滤镜覆盖强度 = 1 - alpha(0.88) = 0.12（实得 %.3f）' % _af)
# —— 滤镜兜底：tint 非法 ⇒ 用 BUBBLE_TINT_FALLBACK ——
_item_bad_tint = dict(bub[1])
_item_bad_tint['filter'] = {'tint': None, 'alpha': 0.88}
_fp2 = FakePainter()
_ok2 = SC.paint_on(_fp2, [_item_bad_tint], FakeAssets(), (640, 480))
_col2 = _fp2.fills[0][1].color() if _fp2.fills else None
check('D5', _ok2 == 1 and _col2 is not None
      and (_col2.red(), _col2.green(), _col2.blue()) == SC.BUBBLE_TINT_FALLBACK,
      'tint 非法 ⇒ 回退 BUBBLE_TINT_FALLBACK %r' % (SC.BUBBLE_TINT_FALLBACK,))
# —— 角色层**不画**角色像素（只叠滤镜）——
_fp3 = FakePainter()
SC.paint_on(_fp3, [bub[1]], FakeAssets(), (640, 480))
check('D6', 'drawPixmap' not in _fp3.calls and 'fillRect' in _fp3.calls,
      '角色层只叠滤镜、不画 pixmap（角色由 sprite_label 承担）')
# —— 素材缺失 ⇒ 品红描边（不静默空着）——
_fp4 = FakePainter()
_n4 = SC.paint_on(_fp4, [bub[0]], FakeAssets(null=True), (640, 480))
check('D7', _n4 == 1 and 'drawRect' in _fp4.calls,
      '球素材缺失 ⇒ 描边占位并计数（calls=%s）' % (_fp4.calls,))
# —— 真素材走 SceneAssetCache：`bubble:` 前缀解析到 assets/bubble/ ——
try:
    _cache = SC.SceneAssetCache()
    _pm_top = _cache.get(R.bubble_sprite_name(R.BUBBLE_FRAME_TOP))
    _pm_back = _cache.get(R.bubble_sprite_name(R.BUBBLE_FRAME_BACK))
    _pm_front = _cache.get(R.bubble_sprite_name(R.BUBBLE_FRAME_FRONT))
    _pm_full = _cache.get(R.bubble_sprite_name(0))
    check('D8', (_pm_full is not None and not _pm_full.isNull()
                 and _pm_full.width() == 62 and _pm_full.height() == 62),
          '真素材：整球 62×62（%r）'
          % ((_pm_full.width(), _pm_full.height()) if _pm_full else None,))
    _dims = {}
    for _tag, _p in (('back', _pm_back), ('front', _pm_front), ('top', _pm_top)):
        _dims[_tag] = (_p.width(), _p.height()) if _p is not None else None
    check('D9', len(set(v for v in _dims.values() if v)) >= 2,
          '★ 三层帧**尺寸不同**（事实，不是猜测）：%r' % (_dims,))
    # 三层各取自己尺寸 ⇒ 出指令时 rect 尺寸各异
    _plan2 = R.plan_frame(_scene_ord, cam, _geo, tick=0,
                          sprite_size=_cache.sprite_size, bubbles=BUBBLES)
    _ball = [it for it in _plan2
             if it.get('kind') == R.K_BUBBLE and it.get('role') != 'character']
    _rd = [(it['rect'][2], it['rect'][3]) for it in _ball]
    check('D10', len(set(_rd)) >= 2,
          '★ 三层各取**自己**尺寸（拿一个尺寸套三层会把球壳拉变形）：%r' % (_rd,))
    _ys = [it['rect'][1] + it['rect'][3] / 2.0 for it in _ball]
    check('D11', max(_ys) - min(_ys) <= 1.0,
          '★ 三层按同一**球心**居中（导出 PNG 无 per-frame offset，故不按 origin 硬对齐）：'
          'centers_y=%r' % (_ys,))
except Exception as e:      # pragma: no cover - 仅当素材损坏
    check('D8', False, '真素材消费异常：%r' % (e,))

# ================================================================ E 球规则表
check('E1', B.grants_foreign_dark(None) is False
      and B.grants_foreign_dark('ralsei') is False
      and B.grants_foreign_dark('kris') is False,
      '★ 球**不给**任何跨暗世界能力（恒 False，含 Ralsei）')
check('E2', B.ejectable('lancer', 'light') is False
      and B.ejectable('lancer', 'dark') is False,
      'Lancer 永远脱不掉（光/暗世界皆然）')
check('E3', B.ejectable('ralsei', 'light') is False
      and B.ejectable('ralsei', 'dark') is True,
      'Ralsei 光世界脱不掉、暗世界可脱（正/负成对）')
check('E4', B.ejectable('kris', 'light') and B.ejectable('kris', 'dark')
      and B.ejectable('susie', 'light') and B.ejectable('susie', 'dark'),
      'Kris / Susie 随时可脱')
check('E5', B.ejectable('toriel', 'dark') is False
      and B.ejectable(None, 'dark') is False,
      '非 CONTAINABLE 角色一律不可脱（含未知 / None）')
check('E6', abs(B.SPIN_STEP_DEG - 90.0) < 1e-9,
      '4 个方向 = 360/4 = 90° 均分（实得 %.1f）' % B.SPIN_STEP_DEG)
check('E7', B.must_stay_inside('ralsei', 'light') is True
      and B.must_stay_inside('ralsei', 'dark') is False
      and B.must_stay_inside('lancer', 'dark') is True,
      '必须留在球里：Ralsei@光=True / Ralsei@暗=False / Lancer=True')

# ================================================================ F 世界门控三规则
_reg = N.load_registry()
_r = _reg.get('ralsei')
_a = _reg.get('toriel')
_g = _reg.get('gerson')     # ★ 只在 ch4 ⇒ 才是真正的"跨章反例"

check('F1', N.world_gate(_r, 'light').reason == N.REASON_LIGHT_NEEDS_BUBBLE
      and N.world_gate(_r, 'light').ok is False,
      '★ Ralsei 无球**不能**去光世界（reason=light_needs_bubble）')
check('F2', bool(N.world_gate(_r, 'light', carried=True)),
      '★ Ralsei 被装进球里**可以**去光世界（正控制）')
check('F3', bool(N.world_gate(_a, 'light')),
      '★ 其他角色去光世界**不需要球**（用户原话"这个不需要他们套上球"）')
# ⚠️ 判据坑（鉴别力体检抓到）：首版用 'ch5' 测"跨暗世界" —— 但 **Ralsei 登记的章节
#    本来就是全五章** ⇒ 走的是"本属章"分支，`free_dark_roam` 有没有生效**测不出来**
#    （弱判据）。改用**未被任何人登记**的 `ch9`，并与 Toriel（同样登记全五章）成对 ——
#    同一输入、只因身份不同而结果相反 ⇒ 才是真判据。
check('F4', bool(N.world_gate(_r, 'dark', 'ch9.x.y'))
      and not bool(N.world_gate(_a, 'dark', 'ch9.x.y')),
      '★ 只有 Ralsei 能自由跨暗世界（未登记章节 ch9：Ralsei 放行 / Toriel 拒绝）')
check('F5', bool(N.world_gate(_g, 'dark', 'ch4.x.y'))
      and not bool(N.world_gate(_g, 'dark', 'ch3.x.y')),
      '他人暗世界：本属章(ch4)放行 / 异章(ch3)拒绝（正/负成对）')
check('F6', N.world_gate(_g, 'dark', 'ch3.x.y').reason == N.REASON_FOREIGN_DARK,
      '异章拒绝的原因码 = foreign_dark_world（实得 %r）'
      % N.world_gate(_g, 'dark', 'ch3.x.y').reason)
check('F7', N.world_gate(_a, 'nowhere').reason == N.REASON_LEAVE_DARK
      and N.world_gate(_a, 'nowhere').ok is False,
      '未知世界 ⇒ 拒绝（reason=leave_dark_world）')
check('F8', N.world_gate(_a, 'dark').ok is True,
      '暗世界缺 scene_id ⇒ 只按世界判、不做章节判（不猜 ⇒ 放行）')
check('F9', N.free_dark_roam(_r) is True and N.free_dark_roam(_a) is False
      and N.light_needs_bubble(_r) is True
      and N.light_needs_bubble(_a) is False,
      '两条特例只对 Ralsei 成立（其余角色一律 False）')
# ★★ 关键负控制：球**不参与**暗世界判定 ⇒ 其他人 carried=True 走异章**仍拒**
check('F10', N.world_gate(_g, 'dark', 'ch3.x.y', carried=True).reason
      == N.REASON_FOREIGN_DARK,
      '★★ 球不给跨暗世界能力：Gerson carried=True 走异章仍拒（球在暗分支**不被读**）')

# ================================================================ G 接线 AST（main.py）
_main_src = rd(os.path.join(SRC, 'main.py'))
_main_tree = ast.parse(_main_src)


def _cls(name):
    for node in ast.walk(_main_tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _fn(cls_node, name):
    for node in cls_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _names_in(node):
    """收集节点里出现过的**标识符名**（Name.id / Attribute.attr / 字符串常量）。"""
    got = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            got.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            got.add(sub.attr)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            got.add(sub.value)
    return got


_pet = _cls('RalseiPet')
check('G1', _pet is not None, 'main.py 有 RalseiPet 类')
_imp_names = set()
for node in _main_tree.body:
    if isinstance(node, ast.ImportFrom):
        _imp_names.update(a.asname or a.name for a in node.names)
    elif isinstance(node, ast.Import):
        for a in node.names:
            _imp_names.add(a.asname or a.name.split('.')[0])
check('G2', 'BubbleOverlay' in _imp_names and 'bubble_system_mod' in _imp_names
      and 'scene_render_mod' in _imp_names,
      'main.py 顶层 import 了 BubbleOverlay / bubble_system_mod / scene_render_mod'
      '（实得命中 %r）'
      % (sorted(_imp_names & {'BubbleOverlay', 'bubble_system_mod',
                              'scene_render_mod'}),))

# SCENE_LAYER_ENABLED 是 RalseiPet 的**类属性**且为 True（第18项：贴近原作）
_sle = None
if _pet is not None:
    for node in _pet.body:
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and tg.id == 'SCENE_LAYER_ENABLED':
                    _sle = node.value
check('G3', isinstance(_sle, ast.Constant) and _sle.value is True,
      'SCENE_LAYER_ENABLED 是类属性且 = True（实得 %r）'
      % (getattr(_sle, 'value', None),))

_upd = _fn(_pet, '_update_scene_layer')
_upd_names = _names_in(_upd) if _upd is not None else set()
check('G4', 'split_bubble_layers' in _upd_names and '_update_bubble_overlay' in _upd_names,
      '_update_scene_layer 里真调用了 split_bubble_layers 与 _update_bubble_overlay')
_kw = set()
if _upd is not None:
    for sub in ast.walk(_upd):
        if isinstance(sub, ast.Call):
            for kw in sub.keywords:
                if kw.arg:
                    _kw.add(kw.arg)
check('G5', 'bubbles' in _kw,
      'plan_frame 调用带 `bubbles=` 关键字（实得 kwargs=%r）' % (sorted(_kw),))
check('G6', 'transfer_world' in _upd_names,
      '世界切换时调 fld.transfer_world(...)（回暗世界自动脱下球）')

_bo = _cls('BubbleOverlay')
_ebf = _fn(_pet, '_ensure_bubble_field')
_ebf_names = _names_in(_ebf) if _ebf is not None else set()
check('G7', _bo is None and _ebf is not None,
      'main.py 不**重复定义** BubbleOverlay（真源在 scene_canvas），且存在 '
      '_ensure_bubble_field')
check('G7a', 'BubbleField' in _ebf_names and '__dict__' in _ebf_names,
      '★ 惰性建 BubbleField（放 __dict__ ⇒ 不在 __init__ 里新增构造期依赖）')
_ov = _fn(_pet, '_update_bubble_overlay')
_ov_names = _names_in(_ov) if _ov is not None else set()
check('G8', 'raise_' in _ov_names and 'set_plan' in _ov_names and 'show' in _ov_names,
      '★ _update_bubble_overlay 里 set_plan + show + raise_（保证球壳在角色**之上**）')

_init_ui = _fn(_pet, 'init_ui')
_ui_names = _names_in(_init_ui) if _init_ui is not None else set()
check('G9', 'BubbleOverlay' in _ui_names and 'bubble_overlay' in _ui_names,
      'init_ui 里创建了 self.bubble_overlay（第50轮控件的装配点）')

_tb = _fn(_pet, 'toggle_bubble')
check('G10', _tb is not None, '存在交互入口 toggle_bubble')
_tb_default = None
if _tb is not None:
    for d, v in zip(_tb.args.args, _tb.args.defaults):
        if d.arg == 'char_id':
            _tb_default = v
# ⚠️ 判据坑（首跑误报）：源码是 `char_id=None` 的**哨兵**写法 +
#    函数体内 `cid = char_id or 'ralsei'` 兜底。断言"缺省值 == 'ralsei'"是**过窄判据**。
#    正确判据 = 缺省是 None（"未指定"）**且** 函数体里出现 'ralsei' 兜底（= 真落到 Ralsei）。
_tb_names = _names_in(_tb) if _tb is not None else set()
check('G11', isinstance(_tb_default, ast.Constant) and _tb_default.value is None
      and 'ralsei' in _tb_names,
      '★ toggle_bubble 的 char_id 缺省 = None 哨兵，函数体内兜底为 "ralsei"'
      '（唯一必须靠球的角色）（实得 default=%r / 体内含 ralsei=%s）'
      % (getattr(_tb_default, 'value', None), 'ralsei' in _tb_names))
check('G12', 'equip' in _tb_names and 'unequip' in _tb_names
      and 'ejectable' not in _tb_names and 'must_stay_inside' not in _tb_names,
      '★ toggle_bubble **只转发**（调 equip/unequip），不自己实现规则'
      '（否则规则长出第二份真源）')

_ab = _fn(_pet, '_active_bubbles')
_ab_names = _names_in(_ab) if _ab is not None else set()
check('G13', 'fit_scale' in _ab_names,
      '★ 球的缩放由 fit_scale 从角色显示像素反推（不硬用原作 1.55 ⇒ 不穿模）')
check('G14', 'filters' in _ab_names and 'tick' in _ab_names,
      '_active_bubbles 里取滤镜参数并推进缓动（tick）')

# —— BubbleOverlay 自身的两条自我约束（AST）——
_sc_tree = ast.parse(rd(os.path.join(MODS, 'scene_canvas.py')))


def _cls_in(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


_bo_sc = _cls_in(_sc_tree, 'BubbleOverlay')
_bo_init = None
if _bo_sc is not None:
    for node in _bo_sc.body:
        if isinstance(node, ast.FunctionDef) and node.name == '__init__':
            _bo_init = node
check('G15', _bo_sc is not None and _bo_init is not None,
      'scene_canvas.BubbleOverlay 定义了 __init__')
_bo_names = _names_in(_bo_init) if _bo_init is not None else set()
check('G16', 'WA_TransparentForMouseEvents' in _bo_names,
      '★ BubbleOverlay 设了 WA_TransparentForMouseEvents（不许挡住拖拽/点击）')
check('G17', 'hide' in _bo_names,
      'BubbleOverlay 默认 hide()（真有前层可画时才显示）')
_bo_meth = {n.name for n in (_bo_sc.body if _bo_sc is not None else [])
            if isinstance(n, ast.FunctionDef)}
check('G18', {'set_plan', 'plan', 'paintEvent'} <= _bo_meth,
      'BubbleOverlay 有 set_plan / plan / paintEvent（与 SceneCanvas 同接口）'
      '（实得 %r）' % (sorted(_bo_meth),))

# ================================================================ H 原作锚定 + 恒真自查
# 直接读**仓库内**的 GML 逐字产物（第49轮证据），把帧号钉到原作
_gml = os.path.join(GML49, 'ch3.obj_tenna_board4_gacha_Draw_0.gml')
if os.path.isfile(_gml):
    _draw = rd(_gml)
    _seq = [int(m.group(1)) for m in
            re.finditer(r'spr_dw_tv_gachaball_transparent,\s*(\d+)', _draw)]
    check('H1', _seq == [2, 3, 1],
          '★ 原作 GML 球帧序逐字 = [2,3,1]（实得 %r）' % (_seq,))
    _ic = _draw.find('draw_sprite_ext(actor_sprite')
    _ib = _draw.find('spr_dw_tv_gachaball_transparent, 2')
    _if = _draw.find('spr_dw_tv_gachaball_transparent, 3')
    check('H2', 0 <= _ib < _ic < _if,
          '★ 角色被夹在后层(2)与前层(3)之间 ⇒ 分层遮挡有原作出处（%d<%d<%d）'
          % (_ib, _ic, _if))
    check('H3', tuple(R.BUBBLE_DRAW_ROLES) == (R.BUBBLE_ROLE_BACK,
                                               R.BUBBLE_ROLE_CHAR,
                                               R.BUBBLE_ROLE_FRONT,
                                               R.BUBBLE_ROLE_TOP)
          and [R.BUBBLE_FRAME_BACK, R.BUBBLE_FRAME_FRONT, R.BUBBLE_FRAME_TOP]
          == _seq,
          '渲染层帧号三元组 == 原作逐字序 [2,3,1]')
else:
    check('H1', False, '第49轮 GML 证据缺失：%s' % _gml)

# 负控制：bubble_sprite_name 对不同帧给出**不同**名字（否则"帧号"是摆设）
check('H4', len({R.bubble_sprite_name(f) for f in (0, 1, 2, 3)}) == 4,
      '帧号 0/1/2/3 产出 4 个不同素材名（帧号不是摆设）')

# 恒真自查：三条原因码在本轮**都真的出现过**（不是"写了没走"）
_reasons = {N.world_gate(_r, 'light').reason,
            N.world_gate(_r, 'light', carried=True).reason,
            N.world_gate(_g, 'dark', 'ch3.x.y').reason}
check('H5', {N.REASON_LIGHT_NEEDS_BUBBLE, N.REASON_OK,
             N.REASON_FOREIGN_DARK} <= _reasons,
      '三原因码实测可达（ok / light_needs_bubble / foreign_dark）实得 %r'
      % (sorted(_reasons),))

# 资产在位（查磁盘真 PNG，不信"我写了 N 个"）
_all = sorted(os.listdir(BUBBLE_DIR)) if os.path.isdir(BUBBLE_DIR) else []
_pngs = [f for f in _all if f.lower().endswith('.png')]
_ball = [f for f in _pngs if f.startswith('spr_dw_tv_gachaball_transparent_')]
check('H6', len(_pngs) == len(_all) and len(_pngs) >= 43,
      'assets/bubble 全为真 PNG（%d 个，无杂物 %d 条）'
      % (len(_pngs), len(_all) - len(_pngs)))
check('H7', len(_ball) == 4,
      '主球 transparent 四帧文件齐（实得 %d：%r）' % (len(_ball), _ball))

# ================================================================ 汇总
print('-' * 72)
print('第50轮 回归锁（球容器接线）：PASS=%d FAIL=%d' % (len(PASSES), len(FAILS)))
if FAILS:
    print('FAIL 列表: %s' % (FAILS,))
sys.exit(1 if FAILS else 0)
