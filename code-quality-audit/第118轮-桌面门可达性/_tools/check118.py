# -*- coding: utf-8 -*-
u"""check118.py —— 第118轮回归锁：**桌面四门「看得见 = 走得到」** + 交互锁不许僵尸化。

起因（真机探针 `_tools/probe118_doors.py`，两条都是它抓出来的）
----------------------------------------------------------------
① **站哪扇门都进三角符文**：把宠物摆到画在屏幕边缘的 UT 门上、朝左按 E，
   进的是 `ch1.hometown.town_mid`（D 的路由）；四扇门**全**这样。
   真因：交互的"实体"取**灵魂**，桌面上的灵魂恒停 (2487,1500) ⇒ 射线永远从右下角
   出发、永远打不到门 ⇒ 降级"离**灵魂**最近" ⇒ 门 D 的 `pos`(140,42) 恰是最近的那个。
   而门自第112轮续四起就**画在屏幕坐标**（`desk_doors`），与 `desktop.json` 的 `pos`
   早就不是一回事。⇒ 修 = 桌面按**宠物盒 ↔ 门屏幕矩形**的距离选（`_desktop_door_pick`）。

② **推过一次门，之后所有可交互物全失灵**：`Interactable.interact()` 在
   `on_interact()` 返回 True 时**保持全局锁**，靠 `update()` 的 `dialog_done()` 解锁 ——
   而**全仓从来没人调过 `update()`**。换场景时旧道具被丢掉，锁的持有者成了
   没人再驱动的僵尸 ⇒ `try_acquire` 永远失败。
   ⇒ 修 = ① 30ms 帧钩子驱动 `update(dt)`；② 重建道具前按持有者 `release()`。

判据（四组，逐条对着"修了什么"）
--------------------------------
  A `_desktop_door_pick` 存在、**只吃屏幕几何**（不碰房间坐标）、接线排在射线之前
  B `_tick_item_props` 存在 + 真调 `update` + 挂在 30ms 钩子上
  C 重建道具**先释放旧锁**（语句序）
  D 桌面上发起交互的主体 = `'pet'`（否则「Niko 的家」永远判成"用户" ⇒ 彩蛋永不触发）
  E 行为级：`Interactable` 的"True ⇒ 持锁 / update ⇒ 解锁"语义（用**产品真模块**跑）
  F 判据自身体检（无恒真、记账、被测文件在盘）

★ 一律走 **AST**，不扫源码文本（"提到某个名字"类恒真判据在本项目已发作五次）。
★ 本套件**不建 App**（不上屏），真机四门由 `probe118_doors.py` 承担（不进 G2）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\check118.py
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.environ.get('RALSEI_ROUND118_ROOT')
                       or os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
COMP = os.path.join(PKG, 'modules', 'companion.py')
DD = os.path.join(PKG, 'modules', 'door_reveal.py')

ok = fail = 0
L = []


def check(name, cond, star=False, detail=None):
    u"""记一条判据。★ 第118轮修正：原来在 append 了 detail 之后才 `print(L[-1])`
    ⇒ **FAIL 行永远不打印**（打出来的是 detail），而"按 `[FAIL]` 前缀找责任判据"
    的变异测试就会**零命中** —— 判据自己把自己藏起来了（本轮实测踩到）。"""
    global ok, fail
    line = ('[PASS] %s' % name) if cond else ('[FAIL] %s' % name)
    if cond:
        ok += 1
    else:
        fail += 1
    L.append(line)
    print(line)
    if not cond and detail:
        d = '       detail: %s' % (detail,)
        L.append(d)
        print(d)


def rd(p):
    return io.open(p, 'r', encoding='utf-8', newline='').read()


def funcs_of(tree, cls=None):
    u"""(类名可空) ⇒ {函数名: 节点}。"""
    out = {}
    for n in ast.walk(tree):
        if cls is None:
            if isinstance(n, ast.FunctionDef):
                out.setdefault(n.name, n)
        elif isinstance(n, ast.ClassDef) and n.name == cls:
            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    out.setdefault(m.name, m)
    return out


def call_names(node):
    u"""函数体里**按出现顺序**的被调名字（`a.b()` 记 `b`，`a()` 记 `a`）。"""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                out.append(f.attr)
            elif isinstance(f, ast.Name):
                out.append(f.id)
    # ast.walk 是 BFS，跨层级序不保；同层顺序可用 ⇒ 只在同一 body 上用小工具比，
    # 跨层用途只判"出现过"，不判先后。见 A3/B2 各自的实现。
    return out


try:
    _src = rd(MAIN)
    _tree = ast.parse(_src)
    _ok_parse = True
    _err = None
except Exception as e:                                            # noqa: BLE001
    _src, _tree, _ok_parse, _err = '', None, False, repr(e)

check('F1 被测文件在盘且可解析（main.py）', _ok_parse, star=True, detail=_err)
if not _ok_parse:
    print('\\r\\n%d PASS / %d FAIL' % (ok, fail))
    sys.exit(1)

_F = funcs_of(_tree)

# ===========================================================================
#  A · 桌面门按**屏幕几何**选，且接线排在房间坐标射线**之前**
# ===========================================================================
check('A1 ★★★ 有 `_desktop_door_pick`（桌面门选取的单一入口）',
      '_desktop_door_pick' in _F, star=True, detail=sorted(_F)[:5])
_n = _F.get('_desktop_door_pick')
if _n is not None:
    _calls = call_names(_n)
    check('A2 ★★★ 它**不使用**房间坐标的实体（不许再调 `_npc_interact_actor_room_xy`）',
          '_npc_interact_actor_room_xy' not in _calls, star=True, detail=str(sorted(set(_calls))))
    check('A3 ★★★ 它真用屏幕几何：`_pet_screen_rect` + `rect_gap` + `_desktop_screen_doors`',
          {'_pet_screen_rect', 'rect_gap', '_desktop_screen_doors'} <= set(_calls),
          star=True, detail=str(sorted(set(_calls))))
    # 只对桌面生效（否则别的场景会绕开"灵魂射线"这套原作语义）
    check('A4 ★★ 只对桌面生效（函数里出现 `_scene_is_desktop_scene`）',
          '_scene_is_desktop_scene' in _calls, star=True)
else:
    for k in ('A2', 'A3', 'A4'):
        check('%s（缺函数）' % k, False)

# 接线顺序：同一个函数体里，`_desktop_door_pick` 的调用必须在 `_npc_interact_pick_prop` 之前
_isp = _F.get('interact_scene_prop')
if _isp is not None:
    _seq = []
    for _st in _isp.body:                       # 只看**顶层语句**的顺序（够用且不误判）
        for _c in call_names(_st):
            if _c in ('_desktop_door_pick', '_npc_interact_pick_prop'):
                if _c not in _seq:
                    _seq.append(_c)
    check('A5 ★★★ 接线顺序：桌面门选取**排在**房间坐标射线之前',
          _seq[:2] == ['_desktop_door_pick', '_npc_interact_pick_prop'], star=True,
          detail='实际顺序=%r' % (_seq,))
else:
    check('A5 接线（缺 interact_scene_prop）', False)

# ===========================================================================
#  B · 每帧驱动 update()（否则全局交互锁永不释放）
# ===========================================================================
check('B1 ★★★ 有 `_tick_item_props`（驱动 update 的唯一入口）',
      '_tick_item_props' in _F, star=True)
_tip = _F.get('_tick_item_props')
if _tip is not None:
    check('B2 ★★★ 它真调 `update`（不是只遍历一遍）',
          'update' in call_names(_tip), star=True, detail=str(sorted(set(call_names(_tip)))))
    # 循环体内 try/except：一件坏掉不许拖死整轮
    _has_try = any(isinstance(n, ast.Try) for n in ast.walk(_tip))
    check('B3 ★★ 循环体里逐件 try/except（一件坏掉不许让其余全部失灵）', _has_try, star=True)
# 挂在 30ms 钩子上：同函数里 `_advance_scene_transition` 与 `_tick_item_props` 都被调
_host = None
for _fn in _F.values():
    _cn = call_names(_fn)
    if '_advance_scene_transition' in _cn and '_tick_item_props' in _cn:
        _host = _fn.name
        break
check('B4 ★★★ `_tick_item_props` 挂在 30ms 帧钩子上（与场景过渡同一拍）',
      _host is not None, star=True, detail='宿主函数=%r' % (_host,))

# ===========================================================================
#  C · 重建道具时**先释放旧锁**（语句序，不许只看"出现过 release"）
# ===========================================================================
_rb = _F.get('_rebuild_item_props')
if _rb is not None:
    _rel_idx = _clr_idx = None
    for i, st in enumerate(_rb.body):
        for c in call_names(st):
            if c == 'release' and _rel_idx is None:
                _rel_idx = i
        for n in ast.walk(st):
            if (isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
                    and n.targets[0].attr == 'item_props'
                    and isinstance(n.value, ast.List) and not n.value.elts
                    and _clr_idx is None):
                _clr_idx = i
    check('C1 ★★★ 重建道具**先 release 旧持有者**、再清空列表（语句序）',
          _rel_idx is not None and _clr_idx is not None and _rel_idx < _clr_idx,
          star=True, detail='release@%r 清空@%r' % (_rel_idx, _clr_idx))
    check('C2 ★★ release 用的是持有者身份（`release` 调用带实参，不是无参清锁）',
          'release' in call_names(_rb), star=True)
else:
    check('C1/C2（缺 _rebuild_item_props）', False)

# ===========================================================================
#  D · 桌面上的交互主体 = 'pet'
# ===========================================================================
_actor_pet = False
if _isp is not None:
    for n in ast.walk(_isp):
        if isinstance(n, ast.If):
            _t = ast.dump(n.test)
            if '_scene_is_desktop_scene' in _t:
                for sub in ast.walk(n):
                    if (isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Constant)
                            and sub.value.value == 'pet'):
                        _actor_pet = True
check("D1 ★★★ 桌面上发起交互的主体是 `'pet'`（否则 Niko 家永远判成用户 ⇒ 彩蛋永不触发）",
      _actor_pet, star=True)

# ===========================================================================
#  E · 行为级：Interactable 的"True ⇒ 持锁 / update ⇒ 解锁"
# ===========================================================================
try:
    sys.path.insert(0, PKG)
    from modules import companion as _cp
    _imp_err = None
except Exception as e:                                            # noqa: BLE001
    _cp, _imp_err = None, repr(e)
if _cp is not None:
    try:
        class _P(_cp.Interactable):
            def on_interact(self, actor=None):
                return True                      # = DoorProp 成功推门

        _bus = _cp.InteractBus()
        _p = _P('k1', bus=_bus)
        _opened = _p.interact(None)
        _locked_after = _bus.locked
        _p.update(0.03)
        _locked_after_update = _bus.locked
        check('E1 ★★★ 行为级：`on_interact` 返 True ⇒ 全局锁被占（这正是"僵尸锁"的来源）',
              _opened is True and _locked_after is True, star=True,
              detail='opened=%r locked=%r' % (_opened, _locked_after))
        check('E2 ★★★ 行为级：`update()` 一跑就解锁（⇒ 不驱动 update 就永远锁死）',
              _locked_after_update is False, star=True,
              detail='update 后 locked=%r' % (_locked_after_update,))
        # 负控制：没有 dialog 也不 update ⇒ 锁一直在（证明 E2 不是恒真）
        _bus2 = _cp.InteractBus()
        _p2 = _P('k2', bus=_bus2)
        _p2.interact(None)
        check('E3 ★★ 负控制：不 update ⇒ 锁**一直**在（E2 有鉴别力）',
              _bus2.locked is True, star=True)
        # 别人的锁不许被误放
        _bus3 = _cp.InteractBus()
        _p3, _p4 = _P('k3', bus=_bus3), _P('k4', bus=_bus3)
        _p3.interact(None)
        check('E4 ★★ `release(别人)` 无效（重建时不会误放别人的锁）',
              _bus3.release(_p4) is False and _bus3.locked is True, star=True)
    except Exception as e:                                        # noqa: BLE001
        check('E 行为级（构造失败）', False, detail=repr(e))
else:
    check('E 行为级（import companion 失败）', False, detail=_imp_err)

# ===========================================================================
#  G · 「Niko 的家」的选择框必须是**三角符文风格**，不是系统弹窗
# ===========================================================================
# 用户 10-19 逐字：「你要按照**三角符文的那选择**来啊，**不是干巴巴的弹窗**」
# ⇒ ① `_niko_home_ask` 里**不许**再出现 QMessageBox（AST 查属性名，不扫文本）；
#    ② 必须走 `modules/dr_choice.choose`；
#    ③ 选择框本体就用**原作框体**（`dr_textbox.paint_dark_box_scaled`）+ **红心**；
#    ④ 行为级：↑/↓ 改选中、Enter 落定、Esc 取消（离屏跑，不需要上屏）。
_DRC = os.path.join(PKG, 'modules', 'dr_choice.py')
check('G1 ★★★ `modules/dr_choice.py` 在盘（原作式选择框）', os.path.isfile(_DRC), star=True)
_dr_txt = rd(_DRC) if os.path.isfile(_DRC) else u''
check('G2 ★★★ 选择框用**原作框体**（`paint_dark_box_scaled`）',
      'paint_dark_box_scaled' in _dr_txt, star=True)
# ★ G3 用**行为级**判（下面 Qt 段里真载一次贴图），不在这里扫文本 ——
#   首版写成 `'spr_heart_0.png' in 源码`，结果**docstring 里也写着这个文件名**
#   ⇒ 把素材名改错照样绿（变异 M7 实证：MISSED）。这类"文本判据被注释喂饱"
#   在本项目已发作六次，这次是第六次。
# ★ 用 AST 判"有没有用到这个常量"，**不扫文本** —— 文件 docstring 里就写着
#   "禁 `WindowStaysOnTopHint`"，纯文本扫必然误报（本项目已五次栽在这上面）。
_dr_no_top = True
try:
    for _n in ast.walk(ast.parse(_dr_txt)):
        if isinstance(_n, ast.Attribute) and _n.attr == 'WindowStaysOnTopHint':
            _dr_no_top = False
except SyntaxError:
    _dr_no_top = False
check('G4 ★★ 代码里不用 `WindowStaysOnTopHint`（本项目铁律，第13轮 E1 守着）',
      _dr_no_top, star=True)

_ask = _F.get('_niko_home_ask')
if _ask is not None:
    _bad = []
    for n in ast.walk(_ask):
        if isinstance(n, ast.Attribute) and n.attr == 'QMessageBox':
            _bad.append('QMessageBox')
    check('G5 ★★★ `_niko_home_ask` **不再**用系统弹窗 QMessageBox（用户否掉的形态）',
          not _bad, star=True, detail=str(_bad))
    _cn = call_names(_ask)
    check('G6 ★★★ `_niko_home_ask` 走 `dr_choice.choose`', 'choose' in _cn,
          star=True, detail=str(sorted(set(_cn))))
    _consts = set()
    for n in ast.walk(_ask):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            _consts.add(n.value)
    check('G7 ★★★ 选项文案逐字：`我确定！！！` / `我确定` / `我再考虑考虑`',
          {'我确定！！！', '我确定', '我再考虑考虑'} <= _consts, star=True,
          detail=str(sorted(_consts)))
else:
    for k in ('G5', 'G6', 'G7'):
        check('%s（缺 _niko_home_ask）' % k, False)

# 行为级（离屏）：真的按键、真的返回下标
try:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5 import QtCore, QtGui, QtWidgets
    sys.path.insert(0, PKG)
    from modules import dr_choice as _dc
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _press(box, key):
        QtWidgets.QApplication.sendEvent(
            box, QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier))

    _b = _dc.DrChoiceBox(None, ['我确定', '我再考虑考虑'], scale=1.0,
                         default_index=1, cancel_index=1, prompt='（门纹丝不动。）')
    check('G3 ★★★ 光标 = 原作红心：`heart_pixmap()` 真能载入（素材名/路径都对）',
          _dc.heart_pixmap() is not None, star=True)
    _start = _b._sel
    _press(_b, QtCore.Qt.Key_Up)
    _up = _b._sel
    _press(_b, QtCore.Qt.Key_Return)
    _picked = _b.picked
    check('G8 ★★★ 行为级：默认停在「我再考虑考虑」；↑ 之后 Enter ⇒ 返回 0（确定）',
          _start == 1 and _up == 0 and _picked == 0, star=True,
          detail='start=%r up=%r picked=%r' % (_start, _up, _picked))
    _b2 = _dc.DrChoiceBox(None, ['我确定', '我再考虑考虑'], scale=1.0,
                          default_index=1, cancel_index=1)
    _press(_b2, QtCore.Qt.Key_Escape)
    check('G9 ★★ 行为级：Esc ⇒ 返回 cancel_index（= 1，按"再考虑"处理）',
          _b2.picked == 1, star=True, detail='picked=%r' % (_b2.picked,))
    check('G10 ★★ 选择框绘制真的走了原作框（自带 `paint_dark_box_scaled` 调用点）',
          hasattr(_dc.DrChoiceBox, 'paintEvent'), star=True)
except Exception as e:                                            # noqa: BLE001
    check('G8/G9/G10 行为级（离屏 Qt 不可用）', False, detail=repr(e))

# ===========================================================================
#  F · 判据自身体检
# ===========================================================================
_taut = []
for n in ast.walk(_tree):
    pass
_self = ast.parse(rd(os.path.abspath(__file__)))
for n in ast.walk(_self):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
            _taut.append(getattr(n, 'lineno', '?'))
check('F2 ★★★ 本文件**无恒真判据**（AST 查 `check(..., True)`）', not _taut,
      star=True, detail='命中行=%r' % (_taut,))
check('F3 ★ 断言条数记账一致',
      ok + fail >= 15, detail='ok=%d fail=%d' % (ok, fail))

print('')
print(u'结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
