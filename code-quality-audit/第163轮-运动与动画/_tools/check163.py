# -*- coding: utf-8 -*-
u"""第163轮回归锁：**动画落点（脚底不飘）**。

## 为什么有这一轮

用户口径：「尤其是**运动类和动画类**那一部分」。本套件只管动画类的第一条，
即"角色在屏幕上到底站在哪里"。

### 量出来的事实（两次探针，第一次是错的）

| 支 | 口径 | 跨动画脚底跨度 | 帧间最大抖动 | 结论 |
|---|---|---|---|---|
| `probe163_feet.py`（**作废**） | `窗口顶 + 原始 bbox 底×scale`，**假设帧在窗口内左上对齐** | 30.0 px | `act` 17.5 px | 漏了 AlignCenter 居中项与锚点项 |
| `probe163_round2.py`（第一版，**也作废**） | 走产品 `_compose_anchored_sprite` 合成后量 | 0.0 px | 0.0 px | **恒真判据**：`convertToFormat(4)` = `Format_RGB32`（无 alpha）⇒ 每张图都"全不透明"，函数恒返回整张画布 |
| `probe163_round2.py`（修正后） | 同上，`Format_ARGB32` | **10.0 px** | `act` **10.0** / `run_up` 8.0 / `fall_back` 7.0 / `land` 6.0 / `spell` 5.0 / `sit` 5.0 | 真偏差 |

抓出第二版恒真的是 `probe163_bbox_selfcheck.py` 的 **6 项正负控制**
（全透明→None、小方块→精确 bbox、顶部 2 行→底=2、底部 2 行→底=20、
左侧 1 列→(0,0,1,20)、下移 4px→底跟着变 4px）。修前 6 项**全 FAIL**，修后 6/6 PASS。

### 根因（解析式，不是猜）

`_compose_anchored_sprite` 第98轮的垂直口径是"本体**中心**对齐画布中心"：

    本体下沿在画布内的位置 = ch/2 + 本体高×s/2
    ⇒ 距画布底的空隙   = (ch − 本体高×s)/2     ← 只取决于本体高

于是"本体变矮多少，脚底就抬高它的一半"。代入 `act` 的实测空隙 `[1,2,9,10,9]`
反解出本体高 `38→37→25→24` ⇒ **蹲下 14px、脚抬高 10px**。
跨动画那 10px 同理（`idle`/`neutral` 悬空 4px、`sit_rest` 5px，多数贴底）。

再叠一层：第162轮 `anchored_resize_xy` 保的是**画布底边**，而画布底边
≠ 本体脚底 ⇒ "保底边"没能保住脚底。

### 改法与效果

垂直落位从"本体中心对齐画布中心"改成"**本体下沿对齐画布底沿**"
（水平仍保中心 —— 那是第98轮专治 `act` 爱心撑宽 20px 横跳的成果，不动）。
新增 `_anim_anchor_bottom()` + `_anim_bottom_cache`，与锚点表同一次
`_alpha_row_bits` 循环算出，不重复扫像素；拿不到本体时退回旧中心口径。

改后实测：跨动画 **10.0 → 1.0 px**、帧间 **10.0 → 1.0 px**（只剩 `int()` 取整的 1px）。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | 用**已知答案的合成帧**（本体高 40/25/24，模拟站立/半蹲/蹲下）走产品 `_compose_anchored_sprite`：每帧本体下沿必须贴在画布底沿；跨"动画"脚底跨度 ≤1px |
| B | 接线：垂直落位引用 `_anim_anchor_bottom`；两处合成调用点都还在；拿不到本体时**不崩且不跳走** |
| C | 自检：产品文件无 BOM 全 LF · 不碰外部盘 · 只用 `check()` |
| D | 现状记录（**不作红**）：`sit_rest` 单帧 ⇒ 窝着时零动画。这是待裁定项，见 report163 |

★ 为什么用**合成帧**而不是真素材：真素材要 `RalseiPet()` 构造（约 31 秒，
`import main` 本身只要 0.6 秒 —— 旧记忆里"import 要 31 秒"是错的，慢在构造）。
合成帧能给出**已知答案**，判据才只考一件事；真素材那 34 个动画的实测在
`probe163_round2.py` 里留档。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
# ★ 变异测试（`mutate163.py`）要把 main.py 的**副本**喂给本套件，绝不改产品文件：
#   `CQ_SRC_DIR` 指向临时目录时，import 与 AST 都读那份副本。
_SRC_DIR = os.environ.get('CQ_SRC_DIR') or os.path.join(PET, 'src')
MAIN = os.path.join(_SRC_DIR, 'main.py')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_n_pass = 0
_n_fail = 0
_failed = []


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def read_src(path):
    """按字节读，保持原换行（条款 §11）。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


# ============================================================ 准备合成素材
from PyQt5.QtWidgets import QApplication                       # noqa: E402
from PyQt5.QtGui import QPixmap, QColor, QPainter, QImage      # noqa: E402
from PyQt5.QtCore import Qt                                    # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv[:1])

sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))
# ★ `PET` 必须在 path 上：`main.py` 里写的是 `from modules.xxx import ...`，
#   而变异副本放在 TEMP 时，main.py 内部按 `__file__` 推算的父目录变成 `%TEMP%`，
#   找不到 `modules` 包（实测 `ModuleNotFoundError: No module named 'modules'`）。
#   这里放产品真实 `PET` ⇒ 只变异 main.py，modules 仍用真的。
sys.path.insert(0, PET)
if os.environ.get('CQ_SRC_DIR'):
    # 变异副本优先（否则 import 到的是产品原文件，变异全成假绿）
    sys.path.insert(0, os.environ['CQ_SRC_DIR'])
# ★ 不许让 import 崩掉整个套件：变异把文件改出语法错时，如果直接抛异常，
#   本套件一行 `[FAIL]` 都打不出来 ⇒ 变异测试误判"全绿"（M5 就是这么漏的）。
try:
    import main as MAIN_MOD                                        # noqa: E402
    _IMPORT_ERR = ''
except Exception as _e:                                            # noqa: BLE001
    MAIN_MOD = None
    _IMPORT_ERR = '%s: %s' % (type(_e).__name__, _e)
    print('  (import main 失败：%s)' % _IMPORT_ERR)

_PET_CLS = getattr(MAIN_MOD, 'RalseiPet', None) if MAIN_MOD is not None else None
COMPOSE = getattr(_PET_CLS, '_compose_anchored_sprite', None)
ANCHOR_BOTTOM = getattr(_PET_CLS, '_anim_anchor_bottom', None)
BBOX = getattr(_PET_CLS, '_main_component_bbox', None)
ROW_BITS = getattr(_PET_CLS, '_alpha_row_bits', None)


def alpha_bbox(pixmap):
    """独立扫 alpha 的包围盒（半开）。**故意不复用产品实现** —— 用来交叉验证。"""
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    raw = bytes(ptr)
    bpl = img.bytesPerLine()
    miny, maxy = h, -1
    minx, maxx = w, -1
    for y in range(h):
        a = raw[y * bpl: y * bpl + w * 4][3::4]
        if not any(a):
            continue
        if y < miny:
            miny = y
        maxy = y
        x0 = w - len(a.lstrip(b'\x00'))
        x1 = len(a.rstrip(b'\x00'))
        if x0 < minx:
            minx = x0
        if x1 > maxx:
            maxx = x1
    if maxx < 0:
        return None
    return (minx, miny, maxx, maxy + 1)


def make_frame(fw, fh, body_h, body_w=8, x=2, body_top=1):
    """造一帧：画布 fw×fh，本体 = body_w×body_h 的不透明块，左上角在 (x, body_top)。"""
    pm = QPixmap(fw, fh)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.fillRect(x, body_top, body_w, body_h, QColor(200, 60, 60, 255))
    p.end()
    return pm


def make_self(anim_frames, containers, scale, bottom_override=None):
    """假 self：给产品方法一套**假 sprite_loader**，其余全用产品真实方法。

    ★★★ 第一版这里自己写 lambda 冒充 `_anim_anchor_offset/_anim_anchor_bottom`，
      结果 A 段只测到 `_compose_anchored_sprite` 的公式，**产品那两个方法根本没被执行**
      —— `mutate163` 的 M2/M4（把它们改成恒 None / 缓存重名）全都漏守。
      现在改成 `RalseiPet.<method>.__get__(ns)` 绑到假 self 上，走产品真实实现：
      假 sprite_loader 提供 `sprites` 字典，`_alpha_row_bits`/`_main_component_bbox`
      是产品的 staticmethod，缓存字段由产品方法自己建。
    """
    ns = type('FakePet', (), {})()
    ns.sprite_loader = type('FakeLoader', (), {})()
    ns.sprite_loader.sprites = anim_frames
    ns._alpha_row_bits = MAIN_MOD.RalseiPet._alpha_row_bits
    ns._main_component_bbox = MAIN_MOD.RalseiPet._main_component_bbox
    for _name in ('_anim_anchor_offsets', '_anim_anchor_offset', '_anim_anchor_bottom'):
        _fn = getattr(MAIN_MOD.RalseiPet, _name)
        setattr(ns, _name, _fn.__get__(ns))
    if bottom_override is not None:
        ns._anim_anchor_bottom = bottom_override
    ns.scale = scale
    return ns


SCALE = 1.25

# 三个"动画"，本体高度依次变小 = 站立 / 半蹲 / 蹲下（复现 act 的 38→37→25→24）
ANIMS = {
    'stand': [(20, 44, 40), (20, 44, 40), (20, 44, 40)],
    'half':  [(20, 44, 26), (20, 44, 25)],
    'crouch': [(20, 44, 24), (20, 44, 24), (20, 44, 23)],
}
FRAMES = {}
for _a, _spec in ANIMS.items():
    FRAMES[_a] = [make_frame(fw, fh, bh) for (fw, fh, bh) in _spec]
CONT = {_a: (20, 44) for _a in ANIMS}


def compose_all(ns):
    """返回 {anim: [合成后画布, ...]}；**任何一步抛异常就返回 None**（不许让整个
    套件崩掉 —— 崩了就只剩 traceback，`[FAIL]` 一条都不打，变异测试会误判"全绿"）。"""
    out = {}
    try:
        for anim, frames in FRAMES.items():
            lst = []
            for idx, pm in enumerate(frames):
                sw = int(pm.width() * SCALE)
                sh = int(pm.height() * SCALE)
                scaled = pm.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lst.append(COMPOSE(ns, scaled, CONT[anim], anim, SCALE, idx))
            out[anim] = lst
    except Exception as e:      # noqa: BLE001
        print('    (compose_all 抛异常：%s: %s)' % (type(e).__name__, e))
        return None
    return out


def feet_screen(composed, bottom=1000.0):
    """视觉脚底屏幕 y：窗口底固定 bottom（第162轮保底边的不变量）⇒
    脚底 y = bottom − (画布高 − 合成后 alpha 底沿)。"""
    res = []
    for anim, lst in composed.items():
        for pm in lst:
            bb = alpha_bbox(pm)
            res.append(bottom - (pm.height() - bb[3]))
    return res


print('\n' + '=' * 66)
print('A 段  落位行为：脚底必须贴住画布底，跨动画/帧间都不飘')
print('=' * 66)

check(u'A0 产品里有 `_compose_anchored_sprite` 与 `_anim_anchor_bottom`',
      callable(COMPOSE) and callable(ANCHOR_BOTTOM),
      'compose=%s anchor_bottom=%s import_err=%s'
      % (callable(COMPOSE), callable(ANCHOR_BOTTOM), _IMPORT_ERR or '-'))

if callable(COMPOSE) and callable(ANCHOR_BOTTOM):
    ns = make_self(FRAMES, CONT, SCALE)
    comp = compose_all(ns)

    # A1：每一帧的本体下沿都要落在画布底沿（±1 给 int() 取整）
    worst = -1
    worst_where = '(合成失败)'
    if comp:
        worst = 0
        worst_where = ''
        for anim, lst in comp.items():
            for i, pm in enumerate(lst):
                bb = alpha_bbox(pm)
                gap = pm.height() - bb[3]
                if abs(gap) > worst:
                    worst, worst_where = abs(gap), '%s#%d' % (anim, i)
    check(u'A1 每帧本体下沿贴画布底（|空隙| ≤ 1px）', 0 <= worst <= 1,
          '最大 |空隙| = %d px @ %s' % (worst, worst_where))

    # A2：跨动画 + 帧间的脚底屏幕 y 跨度
    fy = feet_screen(comp) if comp else []
    spread = (max(fy) - min(fy)) if fy else 999.0
    check(u'A2 脚底屏幕 y 跨度 ≤ 1px（跨动画 + 帧间一起算）', 0 <= spread <= 1,
          '实测跨度 = %.1f px（%d 帧）' % (spread, len(fy)))

    # A3 负控制：退回旧中心口径 ⇒ 跨度必须变大（证明 A2 不是恒绿）
    ns_old = make_self(FRAMES, CONT, SCALE, bottom_override=lambda a, i=None: None)
    comp_old = compose_all(ns_old)
    fy_old = feet_screen(comp_old) if comp_old else []
    spread_old = (max(fy_old) - min(fy_old)) if fy_old else -1.0
    check(u'A3 负控制：退回"钉中心"后跨度必须 > 1px（否则 A2 是恒真判据）',
          spread_old > 1.0,
          '旧口径跨度 = %.1f px，新口径 = %.1f px' % (spread_old, spread))

    # A4 无害变异：整体下移 1px（锚点数值 +1）⇒ 跨度不变，不许误报
    #   锚点值从**产品刚建好的缓存**里取（ns._anim_bottom_cache 由产品方法填）
    _bots = getattr(ns, '_anim_bottom_cache', {}) or {}
    ns_shift = make_self(
        FRAMES, CONT, SCALE,
        bottom_override=lambda a, i=None: (_bots.get(a) or [0.0])[i] + 1.0)
    comp_shift = compose_all(ns_shift)
    fy_shift = feet_screen(comp_shift) if comp_shift else []
    spread_shift = (max(fy_shift) - min(fy_shift)) if fy_shift else 999.0
    check(u'A4 无害变异：锚点整体 +1px 后跨度仍 ≤ 1px（判据只看跨度，不看绝对值）',
          0 <= spread_shift <= 1.0,
          '跨度 = %.1f px' % spread_shift)

    # A5 空帧不崩：锚点全是 None 时退回中心口径，且不跳走
    ns_none = make_self(FRAMES, CONT, SCALE, bottom_override=lambda a, i=None: None)
    c2 = compose_all(ns_none)
    ok5 = bool(c2) and all(alpha_bbox(pm) is not None
                          for lst in c2.values() for pm in lst)
    y5 = feet_screen(c2) if c2 else []
    check(u'A5 拿不到本体时退回中心口径：不抛异常、像素不丢、脚底跨度仍 ≤ 12px',
          ok5 and bool(y5) and (max(y5) - min(y5)) <= 12.0,
          '跨度 = %.1f px' % ((max(y5) - min(y5)) if y5 else -1))

print('\n' + '=' * 66)
print('B 段  接线：改动真的进到渲染路径了吗')
print('=' * 66)

try:
    tree = ast.parse(read_src(MAIN))
    _ast_ok = True
    _ast_err = ''
except SyntaxError as e:
    _ast_ok = False
    _ast_err = str(e)
# ★ 必须走 check()：第一版这里只 print('[FAIL] ...') 不计数，
#   于是"变异把 main.py 改出语法错"这种情况套件 returncode 仍是 0 ⇒ mutate 判成漏守。
check(u'B0 main.py 能被 ast 解析（不产 .pyc）', _ast_ok, _ast_err)

if _ast_ok:
    def _find_class(name):
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef) and n.name == name:
                return n
        return None

    cls = _find_class('RalseiPet')
    fn = None
    if cls is not None:
        for n in cls.body:
            if isinstance(n, ast.FunctionDef) and n.name == '_compose_anchored_sprite':
                fn = n
    check(u'B1 `_compose_anchored_sprite` 定义在 RalseiPet 里', fn is not None)

    if fn is not None:
        names = set()
        # ★ 第163轮教训：「判据别绑写法」。垂直落位第一版是直接 `self._anim_anchor_bottom(...)`
        #   （Call），后来为了兼容旧桩（`SimpleNamespace` 没这个方法）改成
        #   `getattr(self, '_anim_anchor_bottom', None)` —— 名字从 **Call** 变成了
        #   **字符串常量**。只收 Call 名的判据当场变成假红。
        #   ⇒ 同时收 Call 名、属性访问名与字符串字面量（AST 天然排除注释，
        #     所以不会因为"注释里提了一句"就假绿）。
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                names.add(n.func.attr)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                names.add(n.func.id)
            elif isinstance(n, ast.Attribute):
                names.add(n.attr)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                # 只收"像标识符"的短串：docstring 也是一整个 Constant，
                # 把它打进 detail 会让一行输出几百字（本套件第一版就这样）。
                if len(n.value) < 64 and ' ' not in n.value and '\n' not in n.value:
                    names.add(n.value)
        _anchor_names = sorted(n for n in names if 'anchor' in n)
        check(u'B2 垂直落位引用了 `_anim_anchor_bottom`',
              '_anim_anchor_bottom' in names,
              '相关名 = %s' % _anchor_names)
        check(u'B3 仍保留 `_anim_anchor_offset`（水平保中心，不许退回）',
              '_anim_anchor_offset' in names,
              '相关名 = %s' % _anchor_names)

        # B4：两处调用点（帧推进分支 / 静止分支）都还在
        n_call = 0
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == '_compose_anchored_sprite':
                n_call += 1
        check(u'B4 `_compose_anchored_sprite` 的调用点仍为 2 处', n_call == 2,
              '实测 %d 处' % n_call)

    # B5：新增缓存字段与旧字段不重名（同表不同键会静默错值）
    check(u'B5 新缓存字段名 `_anim_bottom_cache` 与 `_anim_anchor_cache` 不同',
          '_anim_bottom_cache' in read_src(MAIN)
          and '_anim_anchor_cache' in read_src(MAIN))

print('\n' + '=' * 66)
print('C 段  自检')
print('=' * 66)

_raw = open(MAIN, 'rb').read()
check(u'C1 main.py 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
# ★ 第一版照抄了别处的"全 LF"，那是**误报**：main.py 本来就是 CRLF（第162轮实测）。
#   该守的不是"必须 LF"，而是"不许出现混合换行"（混合会把 diff 搅成整片重写）。
# ★★ 输出里**不许回显计数**（第146轮纪律）：`CRLF=19011` 这种一旦改几行就变，
#   于是"改了代码"本身会让判据看起来"不一致"。只在失败时给数。
_n_crlf = _raw.count(b'\r\n')
_n_lone_lf = _raw.count(b'\n') - _n_crlf
check(u'C2 main.py 换行不混合（孤 LF 必须为 0）',
      _n_lone_lf == 0,
      '' if _n_lone_lf == 0 else '孤LF=%d' % _n_lone_lf)

# ★ C3 第一版全文件禁 `E:\\`/`D:\\` 也是**误报**：`E:\RalseiMemory\` 是产品既有的
#   U 盘 vault 设计（第13轮起）。该守的是"**本轮新增的这两个方法**不碰外部盘"，所以按
#   AST 的 lineno/end_lineno 精确切片，只查被改过的那两段。
_src_lines = read_src(MAIN).split('\n')
_seg = ''
for _n in ast.walk(ast.parse(read_src(MAIN))):
    if isinstance(_n, ast.ClassDef) and _n.name == 'RalseiPet':
        for _m in _n.body:
            if isinstance(_m, ast.FunctionDef) and _m.name in (
                    '_compose_anchored_sprite', '_anim_anchor_bottom',
                    '_anim_anchor_offsets'):
                _seg += '\n'.join(_src_lines[_m.lineno - 1:_m.end_lineno]) + '\n'
# 同样不回显切片字数（改一行就变）
check(u'C3 本轮改动的三个方法内不引用外部盘（D:/E:）',
      _seg != '' and 'E:\\' not in _seg and 'D:\\' not in _seg,
      '' if _seg else '切片为空（方法名没找到）')

print('\n' + '=' * 66)
print('D 段  现状记录（不作红，待裁定项见 report163.md）')
print('=' * 66)
print('[INFO] 素材事实（`assets/animations.json`）：idle %d 帧 / sit %d 帧 / sit_rest %d 帧'
      % (5, 4, 1))
print('[INFO] `idle` 5 帧循环的激活门限 = `idle_timer >= 600`（不窝着）或 `_lounge_since`（窝着）；')
print('[INFO]   实测（probe163_round2 D 段）：自然运行 20s，idle_timer 峰值 1.47s、current_frame 恒为 0；')
print('[INFO]   窝着时 `_lounge_since` 非空 ⇒ 落到 `sit_rest`（单帧）⇒ 仍然零动画。')

print('\n' + '=' * 66)
print('PASS=%d  FAIL=%d' % (_n_pass, _n_fail))
if _n_fail:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
    sys.exit(1)
print('[PASS] 第163轮：动画落点（脚底不飘）全部判据通过')
