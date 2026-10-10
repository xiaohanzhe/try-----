# -*- coding: utf-8 -*-
u"""第104轮回归锁：OneShot 物件的**材质**（`opacity` / `blend_type`）不许漂移。

口径（用户）：
    「**一切根据原作**」/「把原作的世界搬到桌面上，桌面也是一个场景」

本轮做了什么
------------
第103轮把 7,804 个物件接进了场景（栅格 + 锚点定死、切帧、接线），但**只接了
几何**：`opacity`（半透明）与 `blend_type`（加色）这两个**材质**字段还躺在原作
`events_map<N>.json` 里没人消费。本轮把它们接上：

  ① **数据面**：`graphic.opacity`（0..255）⇒ 物件 `alpha = opacity/255`
     （**只写 != 255 的**，34 条）；`graphic.blend_type == 1`（加色）⇒ 物件
     `blend = 1`（389 条）。并集 **399** 条，落在 **65** 个场景 / 6 个分片。
     `blend_type == 2`（减色）在本数据集里**一条都没有** ⇒ 不做、只登记。
  ② **渲染面**：`scene_render.plan_frame` 把 `blend` **透传**进绘制指令
     （只在非 0 时写键 —— 没材质的 7,405 条指令**一字不变**）；
     `scene_canvas._paint_obj` 在 `blend == 1` 时走
     `QPainter.CompositionMode_Plus`。
     ★ 为什么不自己写像素算术：Qt 的 Plus 在**不透明目标**上恰好等于 RMXP 的
     `d = min(255, d + c·a_pixel·opacity)`（A/B 锚点见 B3），且它复用 Qt 的
     合成快路径；自写 per-pixel Python 循环会让每帧多几十毫秒。

★ 本轮**最有说服力的样本**（报告里会引用）：
  · `room 101` 的 `blue_silver`（`src = "invisible silver"`）**opacity = 0** ——
    原作把传送点画成"隐形"的，我们此前**把它画了出来**；
  · `room 210` 的 `blue_npc_prototype`（`src = "invisi-proto"`）同样是 0；
  · `start_lightmaps` 16 条 `opacity=35/155 且 blend=1` = 原作静态光罩；
  · `jars_light`(189) / `tv_light`(54) / `portal_rays`(19) 清一色 `blend=1` 发光体。

判据分四段
----------
 A **数据面**（从 6 个分片**自己数**，不读构建脚本的结论）：计数 · 值域 ·
   键集合 · **正负成对**（没材质的 7,405 条必须既无 `alpha` 也无 `blend`）·
   与 `_evidence/material104.json` 逐条对账
 B **渲染面（真 QPainter，离屏像素）**：`plan_frame` 原样透传 · 「无 blend 的
   指令里**没有** `blend` 键」 · ★★ **加色像素 == RMXP 公式**（且与 SourceOver
   不同） · ★★ **合成模式必须还原**（加色指令之后画的普通物件仍是 SourceOver） ·
   `alpha == 0` 的物件画了等于没画 · 模块分层（`CompositionMode_*` 只许出现在
   `scene_canvas`）
 C **全量接线**：65 个带材质场景逐个真跑 `plan_frame`（条数 + 透传 + 零缺素材）
 D **纪律**：工具在位 · ★★ 零外部依赖（`ni`+`ko` 拼串）· ★★ 无恒真判据（AST）

★ 铁律：成功标记 `[PASS]` 字面量；正/负控制成对；判据名禁自带标记；
  **零 Qt 窗口**（`QT_QPA_PLATFORM=offscreen`）；**零外部盘依赖**
  （原作在 C 盘桌面，回归碰不得 ⇒ 独立验收交给 `verify104.py`，它不进 G2）。
"""
import ast
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 住在 `<轮次>/_tools/` ⇒ 上溯三层才是仓库根（第38轮起的老坑）
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))

sys.path.insert(0, MOD)      # `scene_canvas` / `scene_render` 等模块目录

ALLOWED_KEYS = {'pos', 'sprite', 'tile', 'depth', 'src', 'layer', 'alpha', 'blend'}
N_ALL = 7804
N_ALPHA = 34
N_BLEND = 389
N_UNION = 399
N_A0 = 2

_N = [0]
_FAIL = []
_APP = None          # Qt 应用单例：必须模块级持有（局部变量被回收会拆掉上下文）


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def jload(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


# ★★ D2 的外部路径特征串：**必须拼出来**，否则检查器自己那几条常量会被自己的
#    AST 扫描扫到 ⇒ 恒假判据（自己报自己）。第103轮已经有同款。
_EXTERNAL = ('ni' + 'ko', 'OneShot' + 'MG', 'OneShot.World' + '.Machine',
             'gamedata' + os.sep + 'maps')

# ---------------------------------------------------------------- 读一次，全用
_MAT = jload(os.path.join(EV, 'material104.json'))
_OBJS = []            # (zone, sid, room, obj)
for _zf in ZONE_FILES:
    _d = jload(os.path.join(SCENES, _zf))
    for _sid, _ent in (_d.get('scenes') or {}).items():
        if not isinstance(_ent, dict):
            continue
        for _o in (_ent.get('objects') or []):
            _OBJS.append((_zf, _sid, _ent.get('original_room_id'), _o))

_A_OBJS = [t for t in _OBJS if 'alpha' in t[3]]
_B_OBJS = [t for t in _OBJS if t[3].get('blend') == 1]
_U_OBJS = [t for t in _OBJS if 'alpha' in t[3] or t[3].get('blend') == 1]
_CLEAN = [t for t in _OBJS if 'alpha' not in t[3] and 'blend' not in t[3]]


# ===========================================================================
# A 数据面
# ===========================================================================
def sec_a():
    print('== A 数据面（从分片自己数，不信构建脚本的结论）==')
    ok(len(_OBJS) == N_ALL,
       'A1 分片侧物件总数 == %d（实际 %d）—— 材质是**加成**在既有 7,804 条上，'
       '不是重写' % (N_ALL, len(_OBJS)))
    ok(len(_A_OBJS) == N_ALPHA and len(_B_OBJS) == N_BLEND
       and len(_U_OBJS) == N_UNION,
       'A2 ★ 材质计数：带 `alpha` %d / 带 `blend=1` %d / 并集 %d（实际 %d/%d/%d）'
       % (N_ALPHA, N_BLEND, N_UNION, len(_A_OBJS), len(_B_OBJS), len(_U_OBJS)))

    a0 = [t for t in _A_OBJS if t[3]['alpha'] == 0.0]
    ok(len(a0) == N_A0 and sorted(t[2] for t in a0) == [101, 210],
       'A3 ★★ `alpha == 0` **恰好 2 条**，且房间 == [101, 210]（实际 %s）—— '
       '这两条是原作**故意隐形**的（`src` 分别叫 `invisible silver` / `invisi-proto`），'
       '此前被我们画了出来' % (sorted((t[2], t[3].get('src')) for t in a0),))

    # ---- A4 值域 ----
    bad_t = [t[3]['alpha'] for t in _A_OBJS
             if not isinstance(t[3]['alpha'], float) or not (0.0 <= t[3]['alpha'] <= 1.0)]
    ok(not bad_t,
       'A4 全部 `alpha` 都是 [0,1] 的 float（越界 %s）' % (bad_t[:3],))

    # ★ 容差 1e-3：`build104` 写 `round(op/255, 6)`，6 位小数带 ~5e-7 误差，
    #   乘 255 放大成 ~1.3e-4。写 1e-6 会报 32 条**假红**（本套件首跑就栽在这）。
    bad_frac = [(t[2], t[3]['alpha']) for t in _A_OBJS
                if abs(t[3]['alpha'] * 255 - round(t[3]['alpha'] * 255)) > 1e-3]
    ok(not bad_frac,
       'A5 ★ `alpha` 都恰好是 `n/255`（n 整数，容差 1e-3；不符 %d %s）—— '
       '证明它**来自原作 `opacity`**，不是谁手调的 0.5 之类'
       % (len(bad_frac), bad_frac[:3]))
    # A5b 负控制：容差不是"放到什么都过"
    ok(abs((220 / 255.0 + 1 / 255.0) * 255 - 221) <= 1e-3
       and abs(0.5 * 255 - round(0.5 * 255)) > 1e-3,
       'A5b 负控制：`221/255` 仍判为整数份，而 `0.5`（=127.5/255）判为**不是** '
       '⇒ A5 的判据有鉴别力')

    # ---- A6 blend 值域 ----
    badb = [(t[2], t[3].get('blend')) for t in _OBJS
            if 'blend' in t[3] and t[3].get('blend') != 1]
    ok(not badb and not [t for t in _OBJS if t[3].get('blend') == 2],
       'A6 ★ `blend` 键**只**以 `1`（加色）出现（异常 %d %s）；且全集里没有 '
       '`blend == 2`（减色）—— 原作本数据集里没有减色，本轮**不做**它、只登记'
       % (len(badb), badb[:3]))

    # ---- A7 键集合 ----
    extra = collections.Counter()
    for _z, _s, _r, o in _OBJS:
        for k in o:
            if k not in ALLOWED_KEYS:
                extra[k] += 1
    ok(not extra,
       'A7 物件键集合 ⊆ %s（越界键 %s）—— 本轮只新增 `alpha`/`blend` 两个键'
       % (sorted(ALLOWED_KEYS), dict(extra)))

    # ---- A8 ★★ 正负成对：没材质的必须"干净" ----
    ok(len(_CLEAN) == N_ALL - N_UNION and
       all(('alpha' not in t[3]) and ('blend' not in t[3]) for t in _CLEAN),
       'A8 ★★ 负控制（正负成对）：`opacity==255 且 blend_type==0` 的物件在产品里'
       '**既无 `alpha` 也无 `blend`** —— 干净条数 %d == %d − %d'
       % (len(_CLEAN), N_ALL, N_UNION))

    # ---- A9 分布 ----
    by_zone = collections.Counter(t[0] for t in _U_OBJS)
    rooms = sorted(set(t[2] for t in _U_OBJS))
    ok(len(by_zone) == 6 and len(rooms) == 65,
       'A9 受影响的 399 条落在 **6** 个分片 / **65** 个房间（实际 %d / %d）'
       % (len(by_zone), len(rooms)))

    # ---- A10 与证据对账 ----
    ok(_MAT['counts'] == dict(objects=N_ALL, alpha=N_ALPHA, blend1=N_BLEND,
                              alpha0=N_A0, union=N_UNION),
       'A10 `_evidence/material104.json` 的五个计数与**独立数出来的**一致（%s）'
       % (_MAT['counts'],))
    # ⚠️ `_U_OBJS` 里"只有 blend 没有 alpha"的占多数 ⇒ 取值必须走 `.get`，
    #   不能假设一定有 `alpha`（首跑就是在这报 `KeyError: 'alpha'` 的）。
    mine = sorted((t[2], t[3].get('src') or '', t[3]['sprite'], tuple(t[3]['tile']),
                   int(round(t[3]['alpha'] * 255)) if 'alpha' in t[3] else 255,
                   int(t[3].get('blend', 0)))
                  for t in _U_OBJS)
    theirs = sorted((it['room'], it['src'] or '', it['sprite'], tuple(it['tile']),
                     it['opacity'], it['blend']) for it in _MAT['items'])
    ok(mine == theirs and len(mine) == N_UNION,
       'A11 ★★ 证据的 %d 条与分片侧**逐条相同**（房间/名字/素材/瓦片/opacity/blend '
       '六元组）—— 证据不是自说自话' % len(theirs))


# ===========================================================================
# B 渲染面（真 QPainter，离屏像素）
# ===========================================================================
def _stub_pixmap(r, g, b, a, n=8):
    from PyQt5.QtGui import QColor, QImage, QPixmap
    img = QImage(n, n, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    for x in range(n):
        for y in range(n):
            img.setPixelColor(x, y, QColor(r, g, b, a))
    return QPixmap.fromImage(img)


class _StubAssets(object):
    def __init__(self, table):
        self.table = table

    def get(self, name):
        return self.table.get(name)


def sec_b():
    print('== B 渲染面（真 QPainter，离屏像素）==')
    from PyQt5.QtGui import QColor, QGuiApplication, QImage, QPainter
    import scene_canvas as SCV
    import scene_render as SR
    global _APP
    _APP = QGuiApplication.instance() or QGuiApplication([])

    # ---- B1/B2 plan_frame 透传 ----
    #   ★ 用**真的** `scene_camera.Camera`（自己造一个"像相机的对象"要补齐
    #     `rect`/`to_view_rect`/`visible_world_rect`/`viewport_size` 一整套协议，
    #     补漏一个就变成"测的是替身而不是产品"）。场景对象则用鸭子类型即可。
    import scene_camera as SCC
    class _Sc(object):
        pass
    sc = _Sc()
    sc.objects = [
        dict(pos=[10, 10], sprite='x.png', tile=[0, 0], depth=100, alpha=0.5,
             blend=1),
        dict(pos=[30, 10], sprite='x.png', tile=[1, 0], depth=100),
        dict(pos=[50, 10], sprite='x.png', tile=[2, 0], depth=100, alpha=0.0),
    ]
    sc.bg = None
    sc.hidden_objects = None
    sc.original_room_id = None
    sc.chapter_id = None

    class _Assets(object):
        def sprite_size(self, name):
            return (8, 8)

    cam = SCC.Camera((64, 64), 0, 1.0)
    cam.follow((0.0, 0.0, 64.0, 64.0), (0.0, 0.0, 64.0, 64.0))
    plan = [it for it in SR.plan_frame(sc, cam, None, tick=0,
                                       sprite_size=_Assets().sprite_size)
            if it['kind'] == SR.K_OBJ]
    ok(len(plan) == 3 and plan[0].get('alpha') == 0.5 and plan[0].get('blend') == 1,
       'B1 ★ `plan_frame` 把 `alpha` 与 `blend` **原样透传**进绘制指令'
       '（3 条指令：alpha=%s / blend=%s）'
       % (plan[0].get('alpha', -1), plan[0].get('blend')))
    ok('blend' not in plan[1] and 'blend' not in plan[2],
       'B2 ★★ 负控制：**没有材质**的物件，指令里**没有 `blend` 键**（也不该有）—— '
       '第 2 条（无材质）键集合 %s。这样 7,405 条旧指令**一字不变**，'
       '不会让"加了一个字段"变成"改了所有指令"'
       % (sorted(plan[1].keys()),))

    # ---- B3 ★★★ 加色像素 == RMXP 公式 ----
    def draw(items, dst, size=8):
        img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        img.fill(dst)
        p = QPainter(img)
        SCV.paint_on(p, items, _StubAssets({'x.png': _stub_pixmap(255, 0, 0, 128)}),
                     view_size=(size, size))
        p.end()
        return img.pixelColor(1, 1)

    base = QColor(128, 128, 128, 255)
    it_plus = dict(kind=SR.K_OBJ, name='x.png', rect=(0, 0, 8, 8), alpha=1.0, blend=1)
    it_norm = dict(kind=SR.K_OBJ, name='x.png', rect=(0, 0, 8, 8), alpha=1.0, blend=0)
    g_plus = draw([it_plus], base)
    g_norm = draw([it_norm], base)
    # RMXP 加色：d = min(255, d + c*a_pixel*opacity)；纯红 a=128 ⇒ 红 +127.5、绿蓝不变
    exp_plus = (min(255, 128 + round(255 * 128 / 255.0)), 128, 128)
    exp_norm = (round(128 * 0.5 + 255 * 0.5), round(128 * 0.5), round(128 * 0.5))
    got_plus = (g_plus.red(), g_plus.green(), g_plus.blue())
    got_norm = (g_norm.red(), g_norm.green(), g_norm.blue())
    ok(max(abs(got_plus[i] - exp_plus[i]) for i in range(3)) <= 1
       and max(abs(got_norm[i] - exp_norm[i]) for i in range(3)) <= 1
       and sum(abs(got_plus[i] - got_norm[i]) for i in range(3)) > 30,
       'B3 ★★★ **加色像素 == RMXP 公式**：纯红(a=128) 叠在灰 128 上 —— '
       '`blend=1` 得 %s（期望 %s = `min(255, d+c·a)`）、`blend=0` 得 %s'
       '（= SourceOver）；两者差 %d 级 ⇒ 这条判据真的在分辨两种合成'
       % (got_plus, exp_plus, got_norm,
          sum(abs(got_plus[i] - got_norm[i]) for i in range(3))))

    # B3b 透明度也进公式：alpha=0.5 的加色物 ⇒ 只加一半
    it_half = dict(kind=SR.K_OBJ, name='x.png', rect=(0, 0, 8, 8), alpha=0.5, blend=1)
    g_half = draw([it_half], base)
    exp_half = (min(255, 128 + round(255 * (128 / 255.0) * 0.5)), 128, 128)
    ok(max(abs(g_half.red() - exp_half[0]) for _ in range(1)) <= 1
       and g_half.red() < g_plus.red(),
       'B3b 加色**乘上 opacity**：`alpha=0.5` 时红通道 %d < `alpha=1.0` 的 %d'
       '（期望 %d）—— 第 39 房间的 `jars_light`（`opacity=220 且 blend=1`）'
       '正是这种组合' % (g_half.red(), g_plus.red(), exp_half[0]))

    # ---- B4 ★★ 合成模式必须还原（否则后续所有物件都被加色） ----
    seq = [it_plus, it_norm]
    img = QImage(20, 8, QImage.Format_ARGB32_Premultiplied)
    img.fill(base)
    p = QPainter(img)
    SCV.paint_on(p, [dict(it_plus, rect=(0, 0, 8, 8)),
                     dict(it_norm, rect=(10, 0, 8, 8))],
                 _StubAssets({'x.png': _stub_pixmap(255, 0, 0, 128)}),
                 view_size=(20, 8))
    p.end()
    after_plus = img.pixelColor(1, 1)
    after_norm = img.pixelColor(11, 1)
    ok((after_plus.red(), after_plus.green(), after_plus.blue()) == got_plus
       and (after_norm.red(), after_norm.green(), after_norm.blue()) == got_norm,
       'B4 ★★ **合成模式被还原**：同一次 `paint_on` 里"加色指令 → 普通指令"之后，'
       '普通物件的像素 %s == 单独画它时的 %s（否则第 1 条加色会把后面所有物件'
       '都染成加色 —— 这是最容易漏的 `setCompositionMode` 还原）'
       % ((after_norm.red(), after_norm.green(), after_norm.blue()), got_norm))

    # ---- B5 ★★ alpha == 0 画了等于没画（原作"隐形"） ----
    it_zero = dict(kind=SR.K_OBJ, name='x.png', rect=(0, 0, 8, 8), alpha=0.0)
    g_zero = draw([it_zero], base)
    ok((g_zero.red(), g_zero.green(), g_zero.blue()) == (base.red(), base.green(),
                                                         base.blue()),
       'B5 ★★ `alpha == 0` 的物件**画了等于没画**（目标像素仍是 %s）—— '
       '房间 101 的 `invisible silver` / 房间 210 的 `invisi-proto` 靠这条'
       '才是"隐形"的' % ((base.red(), base.green(), base.blue()),))

    # ---- B6 模块分层：CompositionMode_* 只许出现在画布壳 ----
    src_cv = io.open(os.path.join(MOD, 'scene_canvas.py'), encoding='utf-8').read()
    src_rd = io.open(os.path.join(MOD, 'scene_render.py'), encoding='utf-8').read()

    def _has_attr(src, attr):
        for node in ast.walk(ast.parse(src)):
            if (isinstance(node, ast.Attribute) and node.attr == attr):
                return True
        return False
    ok(_has_attr(src_cv, 'CompositionMode_Plus'),
       'B6 ★★ `scene_canvas` 里确实用了 `CompositionMode_Plus`（AST 查 `Attribute`，'
       '不做纯文本扫 —— 注释里提一嘴名字不算数）')
    ok(not _has_attr(src_rd, 'CompositionMode_Plus')
       and not _has_attr(src_rd, 'setOpacity'),
       'B7 ★ 分层：`scene_render`（纯数据层）**不许**碰 Qt 合成/透明度 API '
       '—— 它只产指令，落笔全在 `scene_canvas`')
    fake = 'p.setCompositionMode(QPainter.CompositionMode_Plus)\n'
    ok(_has_attr(fake, 'CompositionMode_Plus') and
       not _has_attr('x = 1  # CompositionMode_Plus\n', 'CompositionMode_Plus'),
       'B7b 负控制：B6 的检查器对"代码里真的调了"命中，对"只出现在注释里"不命中')


# ===========================================================================
# C 全量接线
# ===========================================================================
def sec_c():
    print('== C 全量接线（65 个带材质的场景逐个真跑）==')
    import scene_camera as SCC
    import scene_render as SR
    import scene_system as SS
    import scene_canvas as SCV
    from PyQt5.QtGui import QImage, QPainter
    global _APP
    if _APP is None:
        from PyQt5.QtGui import QGuiApplication
        _APP = QGuiApplication.instance() or QGuiApplication([])

    GEO = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']
    ENT = SS.load_index().get('scenes') or {}
    rid2sid = {}
    for _zf in ZONE_FILES:
        for _sid, _e in (jload(os.path.join(SCENES, _zf)).get('scenes') or {}).items():
            if isinstance(_e, dict) and isinstance(_e.get('original_room_id'), int):
                rid2sid.setdefault(_e['original_room_id'], _sid)

    hit = sorted(set(t[1] for t in _U_OBJS))
    bad = []
    n_obj = n_mat = 0
    for sid in hit:
        sc = SS.load_scene(sid, entry=ENT.get(sid))
        if sc is None:
            bad.append((sid, 'load_scene 返回 None'))
            continue
        rid = None
        for _zf in ZONE_FILES:
            _e = (jload(os.path.join(SCENES, _zf)).get('scenes') or {}).get(sid)
            if _e:
                rid = _e.get('original_room_id')
                break
        g = GEO.get('oneshot:%s' % rid)
        if not g:
            bad.append((sid, '无几何'))
            continue
        rw, rh = g['w'], g['h']
        cache = SCV.SceneAssetCache()
        cam = SCC.Camera((rw, rh), 0, 1.0)
        cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
        plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
        objs = [it for it in plan if it['kind'] == SR.K_OBJ]
        if len(objs) != len(sc.objects):
            bad.append((sid, 'K_OBJ %d != 物件 %d' % (len(objs), len(sc.objects))))
        for o, it in zip(sc.objects, objs):
            if (it.get('blend') or 0) != (o.get('blend') or 0):
                bad.append((sid, 'blend 未透传', it.get('blend'), o.get('blend')))
                break
            exp_a = o.get('alpha', 1.0)
            got_a = it.get('alpha', 1.0)
            if abs(float(got_a) - float(exp_a)) > 1e-9:
                bad.append((sid, 'alpha 未透传', got_a, exp_a))
                break
        img = QImage(rw, rh, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        pt = QPainter(img)
        SCV.paint_on(pt, plan, cache, view_size=(rw, rh))
        pt.end()
        n_obj += len(objs)
        n_mat += sum(1 for o in sc.objects if 'alpha' in o or o.get('blend') == 1)
        if cache.missing:
            bad.append((sid, '缺素材', cache.missing[:2]))

    ok(len(hit) == 65 and not bad,
       'C1 ★★★ 带材质的 %d 个场景：`K_OBJ` 条数 == 物件数、`alpha`/`blend` '
       '**逐条透传到绘制指令**、真画布零缺素材（物件 %d / 材质 %d；异常 %s）'
       % (len(hit), n_obj, n_mat, bad[:3]))
    ok(n_mat == N_UNION,
       'C2 ★ 这 65 个场景里带材质的物件合计 %d == %d（不重不漏）'
       % (n_mat, N_UNION))


# ===========================================================================
# D 纪律
# ===========================================================================
def sec_d():
    print('== D 纪律 ==')
    ok(all(os.path.isfile(os.path.join(HERE, t)) for t in
           ('build104.py', 'check104.py', 'verify104.py', 'probe104.py', 'mutate104.py')),
       'D1 本轮五件工具（build / check / verify / probe / mutate）都在盘上')

    src = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    tree = ast.parse(src)
    badstr = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if any(m in v or m in v.lower() for m in _EXTERNAL):
                badstr.append(v[:60])
    ok(not badstr,
       'D2 ★★ 回归套件**零外部依赖**：本文件不含原作绝对路径/游戏目录特征串'
       '（原作在 C 盘桌面，回归碰不得）命中 %s' % (badstr[:2],))

    taut = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'ok' and node.args):
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and a0.value is True:
                taut.append(getattr(node, 'lineno', -1))
    ok(not taut,
       'D3 ★★ **无恒真判据**：本文件所有 `ok(...)` 的首参都不是字面量 `True`'
       '（命中行 %s）' % (taut[:3],))

    fake = ast.parse('ok(True, "x")\nok(n > 0, "y")\n')
    hits = [n for n in ast.walk(fake)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'ok' and n.args
            and isinstance(n.args[0], ast.Constant) and n.args[0].value is True]
    ok(len(hits) == 1,
       'D4 负控制：D3 的检查器对"造出来的恒真"确实命中 1 条（检查器本身不是恒真）')

    ok(_N[0] > 25, 'D5 断言条数 > 25（防"套件只剩几条"）实际 %d' % _N[0])


def main():
    print('第104轮 物件材质（opacity / blend_type）回归锁（%s）'
          % os.path.basename(__file__))
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    print()
    if _FAIL:
        print('[FAIL] 共 %d 条失败（断言 %d）' % (len(_FAIL), _N[0]))
        for f in _FAIL:
            print('   - ' + f)
        return 1
    print('物件材质保真：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
