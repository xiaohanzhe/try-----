# -*- coding: utf-8 -*-
u"""probe118b_inline.py —— 【结论：**已尝试、已撤回**，不是现役实现】。

它证过什么
----------
「把选择框塞进对话气泡那块框里」（原作是一块框，我们当时是两块上下叠）
这条路**技术上做得到**，本探针真机跑通了三件事：
  ① 气泡愿意为选项在框内底部让出空间（`_choice_pad` 占位 80px，输入栏保持 64px）；
  ② 选择框能摆进框内底部（`(1004,1277,552,80)` ⊂ 气泡 `(970,1014,620,377)`）；
  ③ 没有气泡时明确退回独立框（`inline=False`）。

为什么撤回（★ 这是本文件存在的理由）
------------------------------------
同一次真机取证里，**对话框的正文高度开始滚雪球**：`dialogue_content` 129 → 166 → 196。
根因是 `QTextEdit` 的**滚动条反馈环** —— 框变高/变矮会改变 `viewport()` 宽度，
正文重新折行 ⇒ 文档更高 ⇒ 又需要滚动条。而收回预留时，`resize()` 又被布局的
`minimumSizeHint`（当时 330，被撑大的正文/输入栏撑起来）夹住，**回不到 293**。
一句话：为了省掉"两块框之间 10px 的缝"，去动一个**每句话都在用**的动态高度计算，
风险远大于收益 ⇒ 撤回，保留第118轮上半场已验证的"独立框 + 让位气泡"方案。
（改动前的两个文件备份在 `%TEMP%\\inline118_work\\`，供将来真要重做时参考。）

留下的可复用知识
----------------
· 顶层窗口的 `resize()/move()` 在 Windows 上**异步**：调用后立刻读 `frameGeometry()`
  还是旧值（本探针第一版因此差了 84px，正好等于气泡长高量）⇒ 必须延后对位。
· `QDialog` 构造完**不会自己出现**，漏了 `show()` 就会把"没显示"误判成"被压在后面"。
· `hide()/show()` 只是**排队**一次布局激活，紧接着的 `resize()` 会被旧的最小高度夹住。

跑法（仍可复现，用于取证"为什么不做"）
------------------------------------
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118b_inline.py
"""
import ctypes
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
OUT = os.path.join(ROUND, '_evidence', 'inline118')
os.makedirs(OUT, exist_ok=True)

# ---- 沙箱三闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='probe118b_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402
import main as M                                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402


def say(m):
    sys.stdout.write('[inline118] %s\n' % m)
    sys.stdout.flush()


# ★ 现役实现已把 inline 接口撤回 ⇒ 本探针**预期不跑完**。与其抛 AttributeError
#   让人以为坏了，不如把它当"说明书"：直接说明这条改法为什么不做。
try:
    import modules.dr_choice as _DR0                              # noqa: E402
    if not hasattr(_DR0.DrChoiceBox, '_inline_need_h'):
        say('现役 dr_choice **没有** inline 接口（该改法已于第118轮撤回）')
        say('结论：塞进气泡会把 QTextEdit 的滚动条反馈环激活（正文 129→166→196），')
        say('      收回时被布局最小高度夹住 ⇒ 回不到原高。详见本文件头与 §118(f)。')
        raise SystemExit(0)
except SystemExit:
    raise
except Exception as _e:                                            # noqa: BLE001
    say('导入 dr_choice 失败（不影响历史取证结论）: %s' % _e)


def pump(sec):
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.01)


M.check_single_instance()
M.install_crash_guard()
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
pump(1.2)

dlg_ui = window.dialogue_ui
dlg_ui.add_dialogue('ralsei', '前面就是 Niko 的家了……你要现在进去吗？')
dlg_ui.stop_typing()
pump(0.9)

dg0 = dlg_ui.frameGeometry()
say('气泡（预留前） = %r  可见=%s  opacity=%.2f'
    % (dg0, dlg_ui.isVisible(), dlg_ui.windowOpacity()))

import modules.dr_choice as DR                                   # noqa: E402

SCALE = float(window.ui_scale())
say('ui_scale = %.3f' % SCALE)

box = DR.DrChoiceBox(window, [u'我再考虑考虑', u'我确定'], scale=SCALE)
# ★ 必须 show()：QDialog 构造完不会自己出现。第一版探针漏了这一步 ⇒ 截图里
#   只看到气泡、以为"选项层被压在后面"，其实是**根本没显示**（误判）。
box.show()
pump(0.9)

dg1 = dlg_ui.frameGeometry()
og = box.geometry()
need = box._inline_need_h()
bar_g = dlg_ui._input_bar.mapToGlobal(dlg_ui._input_bar.rect().topLeft())
bar_r = dlg_ui._input_bar.rect().translated(bar_g)
say('inline = %s   选择框 = %r' % (box._inline, og))
say('气泡（预留后） = %r   长高 = %d   need_h = %d'
    % (dg1, dg1.height() - dg0.height(), need))
say('输入栏 = %r（高度 %d）  与选项区相交？ %s'
    % (bar_r, bar_r.height(), bar_r.intersects(og)))
say('水平同位？ left %d vs %d   宽度 %d vs %d'
    % (og.left(), dg1.left(), og.width(), dg1.width()))
say('选择区在气泡内？ %s' % (dg1.contains(og)))
for _nm in ('name_label', 'dialogue_content', '_input_bar', '_choice_pad'):
    _w = getattr(dlg_ui, _nm, None)
    if _w is not None:
        _g = _w.geometry().translated(dlg_ui._frame.mapToGlobal(dlg_ui._frame.rect().topLeft()))
        say('  子控件 %-16s = %r  高=%d' % (_nm, _g, _g.height()))

# ---- 1:1 截图（整块气泡：框内文字 + 下方选项，人眼判"是不是一块框"）----
pad = 24
x = dg1.left() - pad
y = dg1.top() - pad
w = dg1.width() + pad * 2
h = dg1.height() + pad * 2
img = app.primaryScreen().grabWindow(0, int(x), int(y), int(w), int(h)).toImage()
img = img.convertToFormat(4)          # Format_RGB32（内存 BGRA）
ptr = img.bits()
ptr.setsize(img.byteCount())
arr = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4)
rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])            # BGR → RGB
p_default = os.path.join(OUT, 'inline_default.png')
Image.fromarray(rgb).save(p_default)
say('截图①（默认选中第一项） = %s  %dx%d' % (p_default, rgb.shape[1], rgb.shape[0]))

# 红心下移一行（走产品自己的按键路径，不是直接改字段）
box.keyPressEvent(type('E', (), {'key': lambda s: 16777235, 'accept': lambda s: None,
                                 'ignore': lambda s: None})())
pump(0.5)
img2 = app.primaryScreen().grabWindow(0, int(x), int(y), int(w), int(h)).toImage()
img2 = img2.convertToFormat(4)
ptr2 = img2.bits()
ptr2.setsize(img2.byteCount())
arr2 = np.frombuffer(ptr2, np.uint8).reshape(img2.height(), img2.width(), 4)
p_moved = os.path.join(OUT, 'inline_moved.png')
Image.fromarray(np.ascontiguousarray(arr2[:, :, :3][:, :, ::-1])).save(p_moved)
say('截图②（红心移到第二项） = %s  _sel=%d' % (p_moved, box._sel))

# ---- 收回：高度必须回到预留前 ----
box._restore_host()
pump(0.7)
dg2 = dlg_ui.frameGeometry()
say('气泡（收回后） = %r   与预留前同高？ %s'
    % (dg2, dg2.height() == dg0.height()))
say('  诊断：minimumSizeHint=%r  sizeHint=%r  pad=%r'
    % (dlg_ui.minimumSizeHint(), dlg_ui.sizeHint(), dlg_ui._choice_pad.geometry()))
say('  extra_h=%r pad_vis=%s pad_h=%d  bar_h=%d bar_vis=%s'
    % (dlg_ui._choice_extra_h, dlg_ui._choice_pad.isVisible(),
       dlg_ui._choice_pad.height(), dlg_ui._input_bar.height(),
       dlg_ui._input_bar.isVisible()))
dc = dlg_ui.dialogue_content
say('  content h=%d min=%d max=%d  doc_h=%d  frame_min=%r  inner_min=%r'
    % (dc.height(), dc.minimumHeight(), dc.maximumHeight(),
       int(dc.document().size().height()), dlg_ui._frame.minimumSizeHint(),
       dlg_ui._frame.layout().minimumSize()))
dlg_ui._recalc_size_to_content()
pump(0.4)
say('  手动 recalc 后 = %r' % dlg_ui.frameGeometry())

# ---- 无气泡 ⇒ 必须走独立框老路 ----
dlg_ui.hide_dialogue()
pump(0.6)
box2 = DR.DrChoiceBox(window, [u'好', u'不好'], scale=SCALE)
pump(0.3)
say('气泡隐藏时 inline = %s（期望 False）几何=%r' % (box2._inline, box2.geometry()))
box2._restore_host()

say('=== 结论 ===  inline=%s  长高=%d  收回同高=%s  无气泡退回=%s'
    % (box._inline, dg1.height() - dg0.height(), dg2.height() == dg0.height(),
       not box2._inline))
pump(0.3)
window.close()
pump(0.2)
os._exit(0)
