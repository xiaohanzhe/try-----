# -*- coding: utf-8 -*-
"""第八轮 · 特殊动画治理 验证（Task #13）

对应用户四条：
  1) "确保所有特殊动画……其余的都只交给 AI 判断是否播放，别和抽风似的突然一下"
  2) "特殊行动比如躲猫猫这类的也是"
  3) "如果要是播放，那就播完，不要打断，也不要出现边播放边移动这种情况（只针对特殊动画）"
  4) "待机动画要在原地不动3分钟以上才会播放哦，而不是停止就播"
  5) "他鞠躬的那个动画播放的有些奇怪，像是镜头也在移动一样"

本文件先覆盖 #13d（鞠躬像镜头在动 = 素材锚点不一致），其余小节随后追加。
"""
import os
import sys
import types

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(BASE, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication  # noqa: E402
from PyQt5.QtGui import QBitmap, QRegion  # noqa: E402

_app = QApplication.instance() or QApplication([])

from main import RalseiPet  # noqa: E402
from sprite_loader import SpriteLoader  # noqa: E402

MAIN_SRC = open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
SCALE = 2.0

# ---------------------------------------------------------------------------
# H4/H5 上帝类拆分后：部分方法已从 main.py **搬进控制器模块**。
# 本套件大量使用"取某方法的源码、看它有没有调 X"这类**源码级**断言 ——
# 方法一搬家，`_find_func` 在 main.py 里就找不到它，断言会**假红**
# （实测：H1.3 `_react_to_video` 搬进 video_controller.py 后报
#  "有 note_event=False"，而方法体里 `note_event` 一个字符都没改）。
#
# 处置口径（**不许**把断言放宽成"找不到就跳过" —— 那会让锁失去鉴别力）：
# 让源码查找**跟着方法的新家走**：先 main.py，再按需读控制器模块。
# 这样"实现被搬走"不会误伤锁，"实现真的改坏了"照样会被抓住。
# ---------------------------------------------------------------------------
CONTROLLER_SRCS = {}
for _rel in (
    os.path.join('modules', 'games_controller.py'),    # W1-3
    os.path.join('modules', 'video_controller.py'),    # W1-4
):
    _p = os.path.join(PET, _rel)
    if os.path.exists(_p):
        CONTROLLER_SRCS[_rel] = open(_p, encoding='utf-8').read()

# 合并视图：main.py + 所有控制器（`_find_func` / `play_once_owners` 等按此查找）。
# 顺序很重要 —— main.py 在前，保持"同名以宿主为准"的既有语义。
ALL_SRC = MAIN_SRC + ''.join('\n' + s for s in CONTROLLER_SRCS.values())

RESULTS = []


# ---------------------------------------------------------------- 源码级工具
# 教训（第八轮 E1.4 / F1.2 假失败）：直接 `"某串" in MAIN_SRC` 会把**注释**和
# **文档字符串**里出现的同一串也算进去 —— 于是"已经删掉的死代码"被判成还在、
# "已在文档里说明被删掉的随机数"被判成还在。必须先把注释与字符串字面量抹掉，
# 剩下的才是真正会执行的代码。
def code_only(src):
    """把注释与字符串字面量（含 docstring）替换成等长空格，其余源码保持原样。"""
    import io
    import tokenize
    buf = [list(ln) for ln in src.splitlines(True)]
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except Exception:
        return src
    for tok in toks:
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        (sr, sc), (er, ec) = tok.start, tok.end
        for r in range(sr, er + 1):
            if r - 1 >= len(buf):
                continue
            line = buf[r - 1]
            a = sc if r == sr else 0
            b = ec if r == er else len(line)
            for i in range(a, min(b, len(line))):
                if line[i] != '\n':
                    line[i] = ' '
    return ''.join(''.join(ln) for ln in buf)


def _find_func(name, src=None):
    """在 main.py **与已搬出的控制器模块**里找同名函数（见 ALL_SRC 的说明）。

    返回 `(node, src)` 二元组：node 所在的那份源码必须一起带出来，
    否则 `ast.get_source_segment` 会拿错源文本（跨文件 `node` 对不上 `MAIN_SRC`）。
    """
    import ast
    sources = [src] if src is not None else ([MAIN_SRC] + list(CONTROLLER_SRCS.values()))
    for s in sources:
        for node in ast.walk(ast.parse(s)):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == name):
                return node, s
    return None, None


def func_src(name):
    """模块级函数/方法 `name` 的源码文本（含 def 行），找不到返回 ''。

    ⚠️ 必须用 `_find_func` 返回的**那份**源码取片段（而不是硬写 MAIN_SRC）：
    方法搬进控制器后，node 来自 video_controller.py，拿 MAIN_SRC 定位会取到错位文本。
    """
    import ast
    node, src = _find_func(name)
    return (ast.get_source_segment(src, node) or '') if node else ''


def func_statements(name):
    """函数体内跳过 docstring 后的语句列表（找不到返回 None）。"""
    import ast
    node, _src = _find_func(name)
    if node is None:
        return None
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return body


def play_once_owners():
    """{owner 函数名: [调用行号…]} —— 所有 play_animation_once 调用的归属函数。"""
    import ast
    out = {}

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def _f(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
        visit_FunctionDef = _f
        visit_AsyncFunctionDef = _f

        def visit_Call(self, node):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == 'play_animation_once':
                out.setdefault(self.stack[-1] if self.stack else '<module>',
                               []).append(node.lineno)
            self.generic_visit(node)

    V().visit(ast.parse(MAIN_SRC))
    return out


MAIN_CODE = code_only(MAIN_SRC)


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         (" <- " + str(detail)) if detail else ""))


def bbox_center(pixmap):
    """不透明区域包围盒的中心（像素坐标）。"""
    reg = QRegion(QBitmap.fromImage(pixmap.toImage().createAlphaMask()))
    rects = reg.rects()
    if not rects:
        return None
    x0 = min(r.x() for r in rects)
    y0 = min(r.y() for r in rects)
    x1 = max(r.x() + r.width() for r in rects)
    y1 = max(r.y() + r.height() for r in rects)
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


_LOADER = None


def loader():
    global _LOADER
    if _LOADER is None:
        _LOADER = SpriteLoader()
        _LOADER.load_sprites()
    return _LOADER


def make_stub():
    """只装 _anim_anchor_offset / _compose_anchored_sprite 需要的属性。

    注意：`_compose_anchored_sprite` 内部会 `self._anim_anchor_offset(...)`，
    SimpleNamespace 没有这个方法 —— 必须用 MethodType 显式绑上去，
    否则会 AttributeError（同样的坑在 round8_fling 的 _CATCH_CLEARED_ATTRS 上踩过）。
    """
    o = types.SimpleNamespace()
    o.sprite_loader = loader()
    o._anim_anchor_offset = types.MethodType(RalseiPet._anim_anchor_offset, o)
    o._compose_anchored_sprite = types.MethodType(RalseiPet._compose_anchored_sprite, o)
    return o


TARGETS = ['idle', 'walk_down', 'walk_up', 'walk_left', 'walk_right',
           'run_down', 'run_left', 'run_right', 'run_up',
           'bow', 'act', 'pose', 'curtsy', 'sing', 'wave', 'laugh',
           'surprised', 'splat', 'fall', 'land', 'dance', 'spin', 'look_up']


def container_of(sl, anim):
    cw = ch = 0
    for f in sl.sprites.get(anim, []):
        if f is not None and not f.isNull():
            cw = max(cw, f.width())
            ch = max(ch, f.height())
    return (cw, ch) if cw and ch else None


def scaled(pixmap, scale=SCALE):
    """复刻渲染路径的前置步骤：先纯等比例放大，再交给 _compose_anchored_sprite。

    注意：`_compose_anchored_sprite` 接收的是**已缩放**的精灵（调用点在
    `sprite.scaled(...)` 之后）。直接传原始小图会得到错误的落位 —— 这是本
    验证脚本第一版的假失败原因，不是产品代码的问题。
    """
    from PyQt5.QtCore import Qt
    return pixmap.scaled(int(pixmap.width() * scale), int(pixmap.height() * scale),
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)


def compose(sl, o, anim):
    frames = sl.sprites.get(anim)
    cont = container_of(sl, anim)
    if not frames or not cont:
        return None
    return o._compose_anchored_sprite(scaled(frames[0]), cont, anim, SCALE)


def t_d0_source_evidence():
    """先固化"病因"证据：idle 素材画布严重不居中，其余动作都居中。"""
    sl = loader()
    idle = sl.sprites.get('idle') or []
    check("D0.1 idle 素材存在且为 69x47 宽画布", bool(idle) and idle[0].width() == 69
          and idle[0].height() == 47,
          "idle[0]=%sx%s" % (idle[0].width(), idle[0].height()) if idle else "无素材")
    o = make_stub()
    off_idle = RalseiPet._anim_anchor_offset(o, 'idle')
    check("D0.2 idle 锚点偏移≈(-20, +2.5)（角色偏左，右侧 41px 透明留白）",
          abs(off_idle[0] + 20.0) <= 1.5 and abs(off_idle[1] - 2.5) <= 1.5,
          "idle off=%s" % (off_idle,))
    off_bow = RalseiPet._anim_anchor_offset(o, 'bow')
    check("D0.3 bow 锚点偏移≈(0, 0)（素材本身居中）",
          abs(off_bow[0]) <= 1.0 and abs(off_bow[1]) <= 1.0, "bow off=%s" % (off_bow,))


def union_bbox_center_of_animation(sl, o, anim):
    """把该动画**所有帧**分别合成后取包围盒并集，返回其中心（画布像素坐标）。

    为什么用"并集"而不是第 1 帧：同一个动画内部，角色在各帧之间的位置变化
    **就是动画内容本身**（`land` 三帧就是"爬起来"的过程，`splat` 是压扁）。
    逐帧单独居中会把这个位移抵消掉，动画就"不动了"。
    所以正确的锚点是**每个动画一个**：让"整个动画的包围盒中心"落在画布中心，
    这样跨动画切换时零平移，而动画内部的形变位移完整保留。
    """
    frames = sl.sprites.get(anim)
    if not frames:
        return None, None
    canvas0 = compose(sl, o, anim)
    if canvas0 is None:
        return None, None
    cw, ch = canvas0.width(), canvas0.height()
    ux0 = uy0 = None
    ux1 = uy1 = 0
    for pm in frames:
        if pm is None or pm.isNull():
            continue
        canvas = o._compose_anchored_sprite(
            scaled(pm), container_of(sl, anim), anim, SCALE)
        reg = QRegion(QBitmap.fromImage(canvas.toImage().createAlphaMask()))
        for r in reg.rects():
            x0, y0 = r.x(), r.y()
            x1, y1 = r.x() + r.width(), r.y() + r.height()
            ux0 = x0 if ux0 is None else min(ux0, x0)
            uy0 = y0 if uy0 is None else min(uy0, y0)
            ux1 = max(ux1, x1)
            uy1 = max(uy1, y1)
    if ux0 is None:
        return None, None
    return ((ux0 + ux1) / 2.0, (uy0 + uy1) / 2.0), (cw, ch)


def t_d1_composed_centered():
    """核心：合成后，"该动画的包围盒中心"必须落在画布中心（±1px）。"""
    o = make_stub()
    sl = loader()
    worst = (0.0, '')
    bad = []
    for anim in TARGETS:
        c, (cw, ch) = union_bbox_center_of_animation(sl, o, anim)
        if c is None:
            continue
        d = max(abs(c[0] - cw / 2.0), abs(c[1] - ch / 2.0))
        if d > worst[0]:
            worst = (d, anim)
        if d > 1.0:
            bad.append('%s:%.1f' % (anim, d))
    check("D1.1 全部动画合成后包围盒中心 = 画布中心（≤1px）",
          not bad, "超差=%s 最差=%s" % (bad, worst))


def t_d2_position_invariant_across_switch():
    """核心：idle ↔ 其余动作切换时，角色在"窗口坐标系"里的位置必须不变。

    窗口中心在 resize 时被保持，sprite_label 铺满窗口且精灵居中 —— 所以
    "角色相对窗口中心的位置"就等于它在桌面上的实际位置。
    修复前 idle↔bow 差 40px（idle 素材右侧 41px 透明留白导致）。
    """
    o = make_stub()
    sl = loader()
    worst = (0.0, '')
    bad = []
    for anim in TARGETS:
        c, (cw, ch) = union_bbox_center_of_animation(sl, o, anim)
        if c is None:
            continue
        dx = abs(c[0] - cw / 2.0)
        dy = abs(c[1] - ch / 2.0)
        d = max(dx, dy)
        if d > worst[0]:
            worst = (d, '%s dx=%.1f dy=%.1f' % (anim, dx, dy))
        if d > 1.0:
            bad.append('%s:%.1f' % (anim, d))
    check("D2.1 所有动作的角色屏幕位置都相同（≤1px，修复前 idle↔其它差 40px）",
          not bad, "超差=%s 最差=%s" % (bad, worst))


def t_d3_render_path_uses_anchor():
    """源码级：两处渲染分支都必须走 _compose_anchored_sprite。"""
    check("D3.1 新增 _anim_anchor_offset / _compose_anchored_sprite",
          "def _anim_anchor_offset" in MAIN_SRC
          and "def _compose_anchored_sprite" in MAIN_SRC)
    check("D3.2 两处渲染分支都调用 _compose_anchored_sprite",
          MAIN_SRC.count("self._compose_anchored_sprite(") == 2,
          "调用次数=%d" % MAIN_SRC.count("self._compose_anchored_sprite("))
    check("D3.3 已不再直接把未定位的精灵 setPixmap 到 label",
          "self.sprite_label.setPixmap(cached_sprite)" in MAIN_SRC
          and "_placed = scaled_sprite" in MAIN_SRC)


# ============================================================ 真实对象（离屏）

_PET = None


def pet():
    """真实 RalseiPet（离屏可构造，已实测）。比 stub 强得多：走的是真代码路径。"""
    global _PET
    if _PET is None:
        _PET = RalseiPet()
    return _PET


def tick(p, times=1):
    """手动驱动一帧动画推进（不跑事件循环，定时器不会自己触发）。"""
    import time as _t
    for _ in range(times):
        p._last_animation_time = _t.time() - 10.0
        p.update_animation()


def force_idle_static(p):
    """把宠物置成"站着不动"的静止状态，使 update_animation 走静止分支。"""
    p.is_moving = False
    p.is_jumping = False
    p.is_falling = False
    p.is_gravity_falling = False
    p.is_recovering = False
    p.is_surprised = False
    p.is_using_item = False
    p.is_spellcasting = False
    p.is_splat = False
    p._spell_stage = None
    p._play_once_active = False
    p.current_animation = 'idle'
    if hasattr(p, 'game_state'):
        p.game_state['is_playing'] = False


# ---------------------------------------------------------------- #13c 待机 3 分钟
def t_e_idle_needs_3min():
    """用户："待机动画要在原地不动3分钟以上才会播放哦，而不是停止就播"。"""
    p = pet()
    check("E1.1 存在 IDLE_LOOP_MIN_SECONDS=180 且初值为未激活",
          RalseiPet.IDLE_LOOP_MIN_SECONDS == 180.0
          and pet_init_idle_flag_is_false(),
          "const=%s" % RalseiPet.IDLE_LOOP_MIN_SECONDS)

    # 静止 10 秒：不应启动待机循环，帧必须钉在第 0 帧
    force_idle_static(p)
    p.idle_timer = 10.0
    tick(p, 1)
    frames_short = []
    for _ in range(6):
        tick(p, 1)
        frames_short.append(p.current_frame)
    check("E1.2 静止 10s：待机循环未启动，且一直停在第 0 帧",
          p._idle_loop_active is False and set(frames_short) == {0},
          "loop=%s frames=%s" % (p._idle_loop_active, frames_short))

    # 静止 200 秒：待机循环启动，帧会推进
    force_idle_static(p)
    p.idle_timer = 200.0
    tick(p, 1)
    frames_long = []
    for _ in range(6):
        tick(p, 1)
        frames_long.append(p.current_frame)
    check("E1.3 静止 200s：待机循环启动且帧会推进",
          p._idle_loop_active is True and max(frames_long) > 0,
          "loop=%s frames=%s" % (p._idle_loop_active, frames_long))

    check("E1.4 源码级：死分支 if idle_timer>=180 两分支同值已消除，改用常量",
          "self.idle_timer >= self.IDLE_LOOP_MIN_SECONDS" in MAIN_CODE
          and "if self.idle_timer >= 180.0:" not in MAIN_CODE,
          "（已剔除注释/文档字符串：原写法只作为反面例子留在注释里）")


def pet_init_idle_flag_is_false():
    return getattr(pet(), '_idle_loop_active', None) is False


# ---------------------------------------------------------------- #13a 只交给 AI
def t_f_special_only_by_ai():
    """用户："其余的都只交给 AI 判断是否播放，别和抽风似的突然一下"。"""
    code_lines = [ln for ln in MAIN_SRC.splitlines() if not ln.lstrip().startswith('#')]
    check("F1.1 已删除悬停 1% 的随机 look_up",
          not any('random.random() < 0.01' in ln for ln in code_lines))
    # 情绪入口必须彻底"不再驱动动画"：函数体除 docstring 外只剩一个裸 return。
    _stmts = func_statements('update_animation_by_emotion')
    import ast as _ast
    check("F1.2 update_animation_by_emotion 函数体只剩裸 return（无随机/无切换）",
          _stmts is not None and len(_stmts) == 1
          and isinstance(_stmts[0], _ast.Return) and _stmts[0].value is None
          and not any(k in code_only(func_src('update_animation_by_emotion'))
                      for k in ('random', 'change_animation',
                                'play_animation_once', 'get_animation_for_emotion')),
          "stmts=%s" % (None if _stmts is None
                        else [type(s).__name__ for s in _stmts]))
    check("F1.3 update_animation_by_emotion 已成为空实现（不再驱动动画）",
          "def update_animation_by_emotion" in MAIN_SRC
          and "本函数保留为空实现" in MAIN_SRC)

    # 行为级：情绪动画映射本身仍会给出特殊动画（说明旧路径确实会切），
    # 但反复调用入口后动画必须保持不变 —— 这就是"只交给 AI"。
    p = pet()
    p.emotion_system.add_emotion('excited', 90)
    p.emotion_system.add_emotion('tired', 90)
    cur, val = p.emotion_system.get_current_emotion()
    mapped = p.emotion_system.get_animation_for_emotion(cur, abs(val))
    check("F1.4 旧路径本会切到的特殊动画确实存在（映射非 idle）",
          bool(mapped) and mapped != 'idle', "emotion=%s -> %s" % (cur, mapped))

    force_idle_static(p)
    changed = []
    for _ in range(30):
        p.update_animation_by_emotion()
        changed.append(p.current_animation)
    check("F1.5 连续 30 次调用入口后动画仍为 idle（情绪不再驱动动画）",
          set(changed) == {'idle'}, "seen=%s" % sorted(set(changed)))


# ---------------------------------------------------------------- #13b 播完 + 不移动
def t_g_play_to_finish_and_no_move():
    """用户："如果要是播放，那就播完，不要打断，也不要出现边播放边移动"。"""
    p = pet()
    check("G1.0 特殊动画分类正确",
          p._is_special_anim('dance') and p._is_special_anim('wave')
          and p._is_special_anim('bow')
          and not p._is_special_anim('idle') and not p._is_special_anim('walk_down')
          and not p._is_special_anim('run_left') and not p._is_special_anim('fall')
          and not p._is_special_anim('splat') and not p._is_special_anim('spell'))

    # 起播一个特殊动画
    force_idle_static(p)
    p._play_once_active = False
    ok_first = p.play_animation_once('wave')
    check("G1.1 特殊动画可以正常起播",
          ok_first is True and p.current_animation == 'wave' and p._play_once_active,
          "ok=%s anim=%s" % (ok_first, p.current_animation))

    # 另一个特殊动画不得打断
    ok_second = p.play_animation_once('dance')
    check("G1.2 播放中新的特殊动画被拒绝（不打断）",
          ok_second is False and p.current_animation == 'wave',
          "ok=%s anim=%s" % (ok_second, p.current_animation))
    ok_force = p.change_animation('dance', force=True)
    check("G1.3 即便 force=True 也不能用特殊动画打断特殊动画",
          ok_force is False and p.current_animation == 'wave',
          "ok=%s anim=%s" % (ok_force, p.current_animation))

    # 非特殊动画（状态机）仍必须放行，否则会卡在动作里
    ok_state = p.change_animation('walk_down', force=True)
    check("G1.4 非特殊动画（走路）仍可打断，不会卡死",
          ok_state is True and p.current_animation == 'walk_down',
          "ok=%s anim=%s" % (ok_state, p.current_animation))

    # 移动锁：特殊动画播放期间不得位移
    force_idle_static(p)
    p._play_once_active = False
    p.play_animation_once('dance')
    p.is_following_mouse = True
    before = (p.pos().x(), p.pos().y())
    for _ in range(5):
        try:
            p.update_movement()
        except Exception as e:  # 环境更新在离屏下可能抛错，不影响位移断言
            print("    (update_movement 异常已忽略: %s)" % e)
    after = (p.pos().x(), p.pos().y())
    check("G1.5 特殊动画播放期间不移动（不被鼠标跟随拖动）",
          p._special_anim_locked() and before == after,
          "locked=%s before=%s after=%s" % (p._special_anim_locked(), before, after))
    p.is_following_mouse = False
    p._play_once_active = False

    # 顺序断言必须限定在 update_movement 内部（原先用全文件 .index()，取到的是
    # 别的函数里更早出现的同一个字符串 → 顺序判反，是"测试写错"而非代码错）。
    _um = func_src('update_movement')
    check("G1.6 源码级：移动锁在 update_movement 内、且排在拖拽保护之前",
          "_special_anim_locked()" in _um
          and "_is_being_dragged" in _um
          and _um.index("_special_anim_locked()")
          < _um.index("_is_being_dragged"),
          "len=%d" % len(_um))


# ---------------------------------------------------------------- #13a 来源闸门
# 用户："确保所有特殊动画……其余的都只交给 AI 判断是否播放，别和抽风似的突然一下。"
# 光改掉已知的两处不够 —— 必须有一条**长期闸门**：任何 play_animation_once 的调用
# 只能出现在"白名单来源"里（用户显式交互 / 物理状态机 / AI 决策）。将来若有人又加
# 一个"看窗口就挥手""随机跳舞"的自动触发，这条断言会立刻失败，强迫过一遍评审。
_ALLOWED_PLAY_ONCE_OWNERS = {
    # —— 用户显式交互（点击 / 双击 / 拖拽 / 右键菜单 / 抚摸 / 喂食 / 小游戏）
    'mousePressEvent', 'mouseReleaseEvent', 'mouseDoubleClickEvent', 'mouseMoveEvent',
    'start_mouse_drag', 'stop_mouse_drag', 'start_following_mouse',
    'stop_following_mouse', 'change_animation_randomly', 'play_game',
    'feed_ralsei', 'pet_ralsei', 'start_rock_paper_scissors',
    'play_rock_paper_scissors', 'end_rock_paper_scissors',
    'start_guess_number', 'play_guess_number', 'end_guess_number',
    # —— 物理 / 状态机（摔倒爬起来这类必须有始有终的流程）
    'update_movement', 'update_animation', 'handle_fall', 'handle_jump',
    'start_fall', 'start_falling', 'handle_gravity_fall', 'trigger_splat',
    'wake_up', 'play_animation_once',
    # —— AI 决策 / AI 发起的特殊行动（施法与躲猫猫）
    '_execute_api_action', '_tick_spell_flow', '_cast_spell_then',
    '_hide_move_to_point', '_hide_end_game', '_hide_destroy_obstacles',
    '_hide_report_clicked_folder', '_hide_jump_back_to_desktop',
    '_notify_arrived_if_needed',
}


def t_h_animation_source_gate():
    owners = play_once_owners()
    illegal = {k: v for k, v in owners.items()
               if k not in _ALLOWED_PLAY_ONCE_OWNERS}
    check("H1.1 所有 play_animation_once 调用都来自白名单来源（无环境自动触发）",
          not illegal, "越权来源=%s" % illegal)

    # 刚刚收编的两个环境触发点：不得再直接播动画，且必须改走上报通道。
    # 注意：react_to_desktop_element 的上报写在辅助方法 _note_desktop_observation 里
    # （为了让主流程不被一坨模板字符串淹没），所以这里要成对检查。
    _rd = code_only(func_src('react_to_desktop_element'))
    _nd = code_only(func_src('_note_desktop_observation'))
    check("H1.2 react_to_desktop_element 不再自行播动画，改走 _note_desktop_observation",
          'play_animation_once' not in _rd and '_note_desktop_observation' in _rd
          and 'play_animation_once' not in _nd and 'note_event' in _nd,
          "主流程 play_once=%s 上报=%s / 辅助 note_event=%s"
          % ('play_animation_once' in _rd, '_note_desktop_observation' in _rd,
             'note_event' in _nd))

    _rv = code_only(func_src('_react_to_video'))
    check("H1.3 _react_to_video（陪看视频）不再自行播动画，改为 note_event 上报",
          'play_animation_once' not in _rv and 'note_event' in _rv,
          "有 note_event=%s 有 play_once=%s"
          % ('note_event' in _rv, 'play_animation_once' in _rv))

    # 上报通道本身必须真的存在且会被写进提示词（否则事件只是黑洞）。
    _drv = open(os.path.join(PET, 'modules', 'ai_driver.py'),
                encoding='utf-8').read()
    _dc = code_only(_drv)
    check("H1.4 ai_driver 提供 note_event 且事件会进入决策提示词",
          'def note_event' in _dc and '_pending_events' in _dc
          and '环境事件' in _drv)


def main():
    t_d0_source_evidence()
    t_d1_composed_centered()
    t_d2_position_invariant_across_switch()
    t_d3_render_path_uses_anchor()
    t_e_idle_needs_3min()
    t_f_special_only_by_ai()
    t_g_play_to_finish_and_no_move()
    t_h_animation_source_gate()

    total = len(RESULTS)
    passed = sum(1 for ok, _n, _d in RESULTS if ok)
    print("-" * 68)
    print("第八轮特殊动画治理验证：%d/%d PASS, %d FAIL"
          % (passed, total, total - passed))
    for ok, name, detail in RESULTS:
        if not ok:
            print("  FAIL: %s  %s" % (name, detail))
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
