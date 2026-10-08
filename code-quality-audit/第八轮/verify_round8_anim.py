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
    """只装锚点合成所需的属性（第98轮起含"逐帧口径"的三个依赖，见函数体注释）。

    注意：`_compose_anchored_sprite` 内部会 `self._anim_anchor_offset(...)`，
    SimpleNamespace 没有这个方法 —— 必须用 MethodType 显式绑上去，
    否则会 AttributeError（同样的坑在 round8_fling 的 _CATCH_CLEARED_ATTRS 上踩过）。
    """
    o = types.SimpleNamespace()
    o.sprite_loader = loader()
    o._anim_anchor_offset = types.MethodType(RalseiPet._anim_anchor_offset, o)
    o._compose_anchored_sprite = types.MethodType(RalseiPet._compose_anchored_sprite, o)
    # ★★ 第98轮补：`_anim_anchor_offset` 已改为"**逐帧**取最大 alpha 连通块"（用户真机
    #   反馈「他在鞠躬那个动画的时候会自身位移」），内部新增三个依赖，
    #   `SimpleNamespace` 上都没有 ⇒ 不加这三行会 `AttributeError`（本套件 D0.2 直接崩，
    #   整份输出退化成 traceback = 静默失去 28 条判据）。
    #     ① `_anim_anchor_offsets`：普通方法（读 `self.sprite_loader`、写 `self._anim_anchor_cache`）
    #        ⇒ 必须 MethodType 绑；
    #     ② `_alpha_row_bits` / `_main_component_bbox`：产品里是 **staticmethod**，
    #        但代码里是 `self._alpha_row_bits(...)` 调的 ⇒ 桩上也得挂同名属性。
    #   ⚠️ 这正是"夹具不保真 = 报假问题"的实例：被测量（锚点值）没问题，是**桩缺零件**。
    o._anim_anchor_offsets = types.MethodType(RalseiPet._anim_anchor_offsets, o)
    o._alpha_row_bits = RalseiPet._alpha_row_bits
    o._main_component_bbox = RalseiPet._main_component_bbox
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


def _body_bbox_of_canvas(o, canvas):
    """一帧**合成后**画布上"角色本体"的包围盒（半开 `(x0,y0,x1,y1)`）。

    用**产品同一套口径**（`_alpha_row_bits` → 最大 alpha 8-连通块），
    而不是 `QRegion` 的"全部不透明像素"——见 `_per_frame_center_dev` 的说明。
    """
    rows = o._alpha_row_bits(canvas)
    return o._main_component_bbox(rows, canvas.width())


def _per_frame_center_dev(o, sl, anim):
    """该动画**每一帧**合成后，"角色本体"中心相对**该帧画布中心**的偏差列表。

    返回 `[(frame_index, dx, dy, cw, ch, tol), ...]`（画布像素）。

    ★★ 第98轮：测量单位由"**每个动画的并集包围盒中心**"改为"**每一帧**"。
      为什么必须改：
        · 产品的承诺就是"**每一帧**的本体中心 == 该帧画布中心"（`_anim_anchor_offsets`
          逐帧表 + `_compose_anchored_sprite` 按 `frame_index` 取偏移），
          ⇒ 逐帧测才是这条承诺的**直接**检验；
        · 并集中心会把各帧的噪声叠加（并集端点来自**不同帧**）—— 实测 `run_up`
          逐帧 ≤4px 而并集偏 1.5px，两者都不是"角色跳了"。
        ⚠️ 顺带修掉一处夹具不保真：合成必须显式传 `frame_index`（产品两处渲染分支都传
          `self.current_frame`）。旧口径（整动画一个常量）下漏传看不出差别，
          逐帧口径下 `act` 会差 10.0px。

    ★★ `tol` = **测量链自身**的已知误差，不是被测对象的一部分：
      `scaled()` 用 `SmoothTransformation` 做插值 ⇒ 边缘 alpha 被"抹开"，
      原本与身体**彼此独立**的像素（影子 / 尘土 / 速度线）会和身体**连成一个连通块**
      ⇒ "缩放后本体"比"源帧本体 × 缩放比"更大、更偏。
      实测（`probe98d.py`）：
        `run_down[2]`：源本体 `(0,0,25,27)` → 缩放后 `(0,0,50,62)`（**涨到满格**），
                      `缩放后中心 − 源中心×2 = (0.0, 4.0)`
        `idle`：无粒子 ⇒ `tol = 0.0`
      ⇒ 判据容差取 `tol + 1.0`：**没有插值漂移的帧仍是 1px**（严格），
        有漂移的帧"漂多少容多少"。这不是放宽阈值，是**把量具的误差从读数里扣掉**。
      ⚠️ 兜底：偏移公式本身对不对由 `check98` E5 锁着 —— 那里用**独立**的连通块算法
        （cv2 8-邻域）、在**源帧坐标系**、阈值 1px，不受本处插值噪声影响。
    """
    out = []
    frames = sl.sprites.get(anim) or []
    cont = container_of(sl, anim)
    if not frames or not cont:
        return out
    for _i, pm in enumerate(frames):
        if pm is None or pm.isNull():
            continue
        sp = scaled(pm)
        canvas = o._compose_anchored_sprite(sp, cont, anim, SCALE, _i)
        bb = _body_bbox_of_canvas(o, canvas)
        if bb is None:
            continue
        # 量具误差：缩放插值把"本体"重新定义了多少
        tol = 0.0
        b_src = _body_bbox_of_canvas(o, pm)
        b_sc = _body_bbox_of_canvas(o, sp)
        if b_src is not None and b_sc is not None:
            tol = max(
                abs((b_sc[0] + b_sc[2]) / 2.0 - (b_src[0] + b_src[2]) / 2.0 * SCALE),
                abs((b_sc[1] + b_sc[3]) / 2.0 - (b_src[1] + b_src[3]) / 2.0 * SCALE))
        cw, ch = canvas.width(), canvas.height()
        out.append((_i,
                    (bb[0] + bb[2]) / 2.0 - cw / 2.0,
                    (bb[1] + bb[3]) / 2.0 - ch / 2.0,
                    cw, ch, tol))
    return out


def _d1_scan(o, sl):
    """跑一遍 TARGETS 的**每一帧**，返回 `(最差偏差, 最差位置, 超差列表)`。

    阈值 = `tol + 1.0`（见 `_per_frame_center_dev` 的 tol 说明）。
    抽成函数是为了让**负控制**复用**同一条**判据（而不是另写一份近似品 ——
    那样证明不了原判据有鉴别力）。
    """
    worst = (0.0, '')
    bad = []
    for anim in TARGETS:
        for _i, dx, dy, _cw, _ch, tol in _per_frame_center_dev(o, sl, anim):
            d = max(abs(dx), abs(dy))
            lim = tol + 1.0
            if d > worst[0]:
                worst = (d, '%s[%d] dx=%.1f dy=%.1f tol=%.1f'
                         % (anim, _i, dx, dy, tol))
            if d > lim:
                bad.append('%s[%d]:%.1f>%.1f' % (anim, _i, d, lim))
    return worst, bad


def t_d1_composed_centered():
    """核心：合成后，"该动画**本体**的包围盒中心"必须落在画布中心（±1px）。"""
    o = make_stub()
    sl = loader()
    worst, bad = _d1_scan(o, sl)
    check("D1.1 **每一帧**合成后本体包围盒中心 = 该帧画布中心（≤1px）",
          not bad, "超差=%s 最差=%s" % (bad[:5], worst))
    # ★ 负控制（第98轮补）：把同一批偏移整体推 5px ⇒ 判据必须报红。
    #   为什么必须要：新口径下偏移**定义**就是"本体中心与画布中心之差"，
    #   而合成又按该偏移平移 ⇒ "本体中心 == 画布中心"看上去**像是**恒真。
    #   这条负控制证明它**不是**恒真 —— 真值被改坏会被抓到，而不是静默变绿。
    o2 = make_stub()
    _orig_offs = types.MethodType(RalseiPet._anim_anchor_offsets, o2)

    def _shifted(animation):
        return [(x + 5.0, y) for (x, y) in _orig_offs(animation)]

    o2._anim_anchor_offsets = _shifted
    worst2, bad2 = _d1_scan(o2, sl)
    check("D1.1n 负控制：偏移整体推 5px 后 D1.1 必须报红",
          bool(bad2), "超差=%s 最差=%s" % (bad2[:3], worst2))


def t_d2_position_invariant_across_switch():
    """核心：idle ↔ 其余动作切换时，角色在"窗口坐标系"里的位置必须不变。

    窗口中心在 resize 时被保持，sprite_label 铺满窗口且精灵居中 —— 所以
    "角色相对窗口中心的位置"就等于它在桌面上的实际位置。
    修复前 idle↔bow 差 40px（idle 素材右侧 41px 透明留白导致）。
    """
    o = make_stub()
    sl = loader()
    # ★ 第98轮：改用与 D1.1 相同的**逐帧**扫描（同一个物理量、两条不同角度的断言：
    #   D1.1 守"本体居中"，D2.1 守"跨动画切换时角色在屏幕上不跳"）。
    #   ⚠️ 逐帧口径下两者表达式相同 —— 保留两条是**有意**的（名字与历史结论各自可追溯），
    #      不是为了凑数：第八轮 D2.1 记下的"修复前 idle↔其它差 40px"就是本条的存在理由。
    worst, bad = _d1_scan(o, sl)
    check("D2.1 所有动作的角色屏幕位置都相同（≤1px，修复前 idle↔其它差 40px）",
          not bad, "超差=%s 最差=%s" % (bad[:5], worst))


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
        # ★★ 第60轮：显式关掉"就寝"子系统。
        #    本套件只测动画，而就寝是与动画无关的子系统，**且它的输出依赖挂钟**：
        #    `main.py::_bedtime_tick` 在「23:10 ~ 24:00」这一窗口内必然打一行
        #        [就寝] 今晚（YYYY-MM-DD）窗口 HH:MM~HH:MM 已过，不再补睡
        #    （实测：2026-09-28 23:35 跑 G2，本套件因此由 IDENTICAL 变 DIFF）。
        #    ⇒ 本套件原是一枚"每天 50 分钟的时间炸弹"：白天跑绿、深夜跑红。
        #    这里关掉它，使输出与挂钟无关（`_bedtime_tick` 直接早退，不打日志）。
        #    注：就寝自身"会不会绕过动画来源闸门"的风险不在本套件职责内，
        #        已作为第60轮发现登记，不在此处静默兜住。
        _PET.BEDTIME_ENABLED = False
        # ★★ 第89轮：冻结 NPC 自主挪窝 —— 它同样是与动画无关的子系统，
        #    且输出**逐次都不同**（不是"白天绿深夜红"那种时段炸弹，是**纯随机漂移**）。
        #    根因：`update_movement()` 里有一句 `self._npc_roam_tick(current_time)`，
        #    而 `_npc_roam_tick` 内部经 `npc_intent.jitter()` 使用**连续墙钟**
        #    `time.time()`（精确到微秒）参与哈希 ⇒ 每次跑 NPC 落点都不一样，
        #    打印 `<TS> ... NPC xxx 自己挪到了 <场景>` 一二十行 ⇒ 本套件必然 DIFF。
        #    实测：`ralsei` 一次去 `uty.rooms.rm_intro`、另一次去 `ch4.kris_room.kris_s_room`。
        #    ⚠️ 这是**测试夹具的时间耦合**，不是产品缺陷 —— NPC 生活本就该"每天不同"
        #      （L6「同人同刻不必同行为」），第78/79 轮已用**纯函数级**判据单独锁住它。
        #    ⇒ 处置：把该子系统关掉（`NPC_AUTONOMOUS_TICK = 0` 会让节拍闸始终放行，
        #      所以直接摘掉 `npc_placement`；`_npc_roam_tick` 见 book 为 None 即早退、零日志）。
        #    ⚠️ 代价：本套件从此**看不见**"NPC 挪窝会不会绕过动画来源闸门"。
        #      该风险不在本套件职责内（本套件只测动画治理），已在第89轮登记。
        try:
            _PET._npc_roam_last_tick = float('inf')   # 节拍闸：now - inf < 30 ⇒ 永远早退
        except Exception:
            pass
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


# ---------------------------------------------------------------- #13c 待机 10 分钟
def t_e_idle_needs_3min():
    """用户（第八轮原话）："待机动画要在原地不动3分钟以上才会播放哦，而不是停止就播"。

    ★ 第52轮门限变更：用户改了口径 ——「他待机只会在**静止超过10分钟**后触发」
      ⇒ `IDLE_LOOP_MIN_SECONDS` 由 180.0 抬到 600.0，本夹具的断言与静止时长同步改。
      函数名沿用（改名要动 `run_all.py` 的套件登记，收益不抵风险）。
    """
    p = pet()
    check("E1.1 存在 IDLE_LOOP_MIN_SECONDS=600 且初值为未激活",
          RalseiPet.IDLE_LOOP_MIN_SECONDS == 600.0
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

    # 静止 700 秒（> 600 门限）：待机循环启动，帧会推进
    # ★ 第52轮：门限 180 → 600（用户口径「他待机只会在静止超过10分钟后触发」），
    #   夹具时长必须同步抬到门限之上，否则 E1.3 会红 —— 那不是产品坏，是夹具过期。
    force_idle_static(p)
    p.idle_timer = 700.0
    tick(p, 1)
    frames_long = []
    for _ in range(6):
        tick(p, 1)
        frames_long.append(p.current_frame)
    check("E1.3 静止 700s：待机循环启动且帧会推进",
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
    # ⚠️ detail 里放**任何数字**都会漂：_um 的 len、两个 needle 的 index（序号是
    # 绝对偏移，needle 之前加一行就 +N）——第 25 轮三次迭代全部踩实，其中一次还
    # 因为打"文件名/首行"吃到了别的代码段的怪字符串，把 DIFF 搞得更大。
    # 唯一与代码增长无关、又真的能定位失败的，是**两个 needle 各自的命中与否**：
    #   lock=F  → 移动锁整个没了（或方法被搬走取错片段）
    #   drag=F  → 拖拽保护没了
    #   lock=T drag=T 却仍 FAIL → 两者都在、但顺序反了
    # 顺序这一维由上面的断言本体承担，detail 不必复述。
    check("G1.6 源码级：移动锁在 update_movement 内、且排在拖拽保护之前",
          "_special_anim_locked()" in _um
          and "_is_being_dragged" in _um
          and _um.index("_special_anim_locked()")
          < _um.index("_is_being_dragged"),
          "lock=%s drag=%s" % ("_special_anim_locked()" in _um,
                               "_is_being_dragged" in _um))


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
    # —— 待机（窝着）状态机（第54轮新增）：确定性触发，不是"环境事件驱动的表演"。
    #   `_idle_lounge_tick` 只在"距上次互动 ≥ IDLE_LOUNGE_AFTER_SECONDS(600s)"后走一次
    #   「到窝点 → 播 sit 过渡 → 保持 sit_rest」，与 `wake_up` 同性质。
    #   本闸的本意是拦"看窗口就挥手/随机跳舞"这类抽风式触发（用户第8轮原话），
    #   待机坐下不属于此类；且 `sit`/`sit_rest` 已登记为非特殊姿态动画
    #   （见 main.py `_NON_SPECIAL_ANIM_GROUPS` 的第54轮说明），两边口径一致。
    '_idle_lounge_tick',
    # —— AI 决策 / AI 发起的特殊行动（施法与躲猫猫）
    '_execute_api_action', '_tick_spell_flow', '_cast_spell_then',
    '_hide_move_to_point', '_hide_end_game', '_hide_destroy_obstacles',
    '_hide_report_clicked_folder', '_hide_jump_back_to_desktop',
    '_notify_arrived_if_needed',
    # —— 宠物手势回应（第75轮 B3 新增）：**用户显式交互**的执行层。
    #   第75轮把"部位+手势 → 台词/情绪/动画"的三处重复判定统一到
    #   `modules/pet_interaction.py`，主窗口这边只留一个查表执行函数
    #   `_apply_pet_response(kind)`，由 `mousePressEvent` / `mouseReleaseEvent` /
    #   `mouseMoveEvent` / `mouseDoubleClickEvent` 通过 `_dispatch_pet_event` 调用。
    #   ⇒ 它属于本白名单的第一类（用户显式交互），与 `mousePressEvent` 等**同性质**，
    #     只是多了一层间接；**不是**"环境事件驱动的表演"（本闸要拦的东西）。
    #   ⚠️ 加白名单的前提是"调用链确实源自用户鼠标事件"—— 已由 `check76` 的
    #      C3/C4（三个 handle_* 真用非哨兵实参 + 真调 `_dispatch_pet_event`）锁住。
    '_apply_pet_response',
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
