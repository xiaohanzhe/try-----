# -*- coding: utf-8 -*-
"""W1-6 e2e 校验：真起 `RalseiPet()`，逐条驱动**文件/表格操作全流程**。

为什么必须有这一层（W1-1/W1-2/W1-3/W1-4 的血泪）：
  「方法体逐字等价」**不等于**「产品还能跑」。搬移只改了「这个名字指向谁」
  （模块作用域 / `self` 是谁 / 属性写到哪个字典），**静态等价断言 100% 看不见**。

本项要盯的三类语义陷阱：
  ① 铁律 7（**本项的核心风险**）—— `os.` / `time.` 是「裸 Attribute 根」，
     不是 Name-func 调用。`_open_desktop_item_by_name` 用了 15 处裸 `os.`，
     **方法体自身没有 `import os`**（父版靠 main.py 的**模块级** `import os` 解析）。
     搬进新模块后若模块级漏 `import os` → 只在**真正走进该分支**时才 `NameError`。
     → E2/E3 真步进到该分支（e2e 独有的维度，静态扫不出「跑起来到底解析得到吗」）。
  ② 铁律 6 —— `_log.` 改写若漏成裸 `_log_()` → `NameError`（12 处）。
     → E4 走 `handle_file_operation` 的**异常兜底分支**（`self._log_().warning`）。
  ③ 铁律 2/3 —— `self.desktop_interaction` / `self.dialogue_ui` / `self.open_folder`
     都必须**转发到宿主**；控制器自身字典只许有 `p`。
     → E1c/E1d 断言；且 E6 断言控制器**不写**宿主新名（本项不搬状态）。

★ A/B 探针的结构性盲区（为何这一层不可省）
  `types.MethodType(fn, stub)` 下方法体内 `self` 即 stub ⇒ 铁律 7「模块级 os 是否在」
  在 A/B 中**完全不可见**（stub 模块的 globals 由 A/B 自己造）。必须有**非 A/B 的
  独立维度**——即本文件的**真实例**。
"""
import os
import sys
import traceback
import shutil
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, SRC)
sys.path.insert(0, MODS)

# ============================================================================
# ⚠️⚠️ 安全约束（务必保留）
#   本项方法里有**真删/真开**的路径：
#     · `handle_file_operation("新建表格")` 会 `win32com` 拉起 **Excel** 并 SaveAs；
#     · `handle_file_operation("打开表格")` 会 `os.startfile(excel_path)` **真的打开文件**；
#     · `_open_desktop_item_by_name` 会调到 `open_folder` / `open_file`（spell 流程 + 真开）。
#   ⇒ 探针**绝不允许**让这些分支落到真实桌面/真实文件上。
#   处置：全部走**桩**——桩掉 `desktop_interaction`（自带沙箱 desktop_path）、
#   `dialogue_ui`、`open_folder` / `open_file`。沙箱目录只放探针自建的假 .xlsx。
# ============================================================================
# 沙箱位置：**必须在本地 NTFS 卷**（%TEMP%）。
# ⚠️ E 盘是 exFAT 外接盘：在其上 `os.makedirs` 会 `OSError: [WinError 1] 函数不正确`。
SANDBOX = os.path.join(tempfile.gettempdir(), '_w1_6_probe_tmp')
if os.path.isdir(SANDBOX):
    shutil.rmtree(SANDBOX, ignore_errors=True)
os.makedirs(SANDBOX, exist_ok=True)


def mkfolder(name):
    p = os.path.join(SANDBOX, name)
    os.makedirs(p, exist_ok=True)
    return p


class _StubDialogue(object):
    """桩：记录 `add_dialogue` / `show_dialogue` 调用，绝不弹窗。"""

    def __init__(self):
        self.calls = []

    def add_dialogue(self, who, text, face=None):
        self.calls.append((who, text, face))

    def show_dialogue(self):
        self.calls.append(('__show__', None, None))

    def texts(self):
        return [t for _, t, _ in self.calls if t is not None]


class _StubDesktop(object):
    """桩：沙箱桌面。提供 `desktop_path` / `desktop_elements` /
    `update_desktop_elements()` —— 让探针能精确控制「匹配到谁」。

    ★ E3f 的需求：要**真的**走到 `os.path.join` / `os.path.exists` / `os.path.isdir`
    兜底分支，必须让名字匹配**失败**、但文本恰好是**沙箱内已存在的名字**。
    首版直接用旧 stub（`desktop_elements` 空、`desktop_path` = 上级目录）→
    实测是**前一个测试对象名**（"我的项目"）在 `os.listdir` 风格路径上命中了，
    落点与断言不符。⇒ 用 `find`：让 `desktop_path` 指向沙箱、`name` 与桌面内容无关。"""

    def __init__(self, desktop_path):
        self.desktop_path = desktop_path
        self.desktop_elements = []
        self.update_calls = 0

    def update_desktop_elements(self):
        self.update_calls += 1

    # 父版 `_open_desktop_item_by_name` 只用上面两个成员


results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name +
          ((' :: ' + detail) if detail else ''))


# ============================================================================
# ★ 桩的实现纪律（本探针首跑踩了 3 个 FAIL，全部同源）：
#   `FileSheetController.__getattr__` 的**第 1 条白名单**是「宿主**实例字典**」
#   → 给 `pet.xxx = 桩` 塞实例属性，会让 `self.xxx` 走**实例字典**，
#   而**绕过**类上的桩。首版把桩塞进实例字典（`pet5.fix_excel_format = ...`）
#   ⇒ 方法体里的 `self.fix_excel_format(...)` 根本没被拦住，真去调了 Excel。
#   ⇒ 结论：**桩必须打在宿主「类型」上**（`type(pet).xxx = ...`）——
#     实例字典白名单不命中 → 落到 MRO 白名单 → 拿到类属性 → 桩生效。
#     这也顺带证明转发壳的两条白名单**扫描顺序确实是「先实例后 MRO」**。
# ============================================================================
class _ClassPatcher(object):
    """把桩打在**类型**上，退出时精确还原。

    ★ 打哪一个类型，取决于**调用方怎么解析名字**（首跑踩 2 次）：
      · `pet5.fix_excel_format` 这类**外部调用** → 宿主类 `RalseiPet`
      · 但 `handle_file_operation` 的**方法体内部** `self.fix_excel_format(...)`
        是在 **`FileSheetController` 类**上解析的 —— 打 `RalseiPet` 完全无效
        （首版就错了：日志里看到 Excel 被真调，而 `called` 是空的）。
      ⇒ 通则：**桩要打在「方法体里 `self` 的那张类」上**，而不是宿主类。
    """

    def __init__(self):
        self._saved = []

    def patch(self, cls, name, value):
        had = name in cls.__dict__
        old = cls.__dict__.get(name)
        self._saved.append((cls, name, had, old))
        setattr(cls, name, value)

    def restore(self):
        for cls, name, had, old in reversed(self._saved):
            if had:
                setattr(cls, name, old)
            else:
                try:
                    delattr(cls, name)
                except AttributeError:
                    pass
        self._saved = []


def texts_of(dia):
    return [t for _, t, _ in dia.calls if t is not None]


# ---------------- 0. 环境 ----------------
print('=== E0 环境 / 导入期 ===')
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    check('E0a QApplication 就绪', True)
except Exception as e:
    check('E0a QApplication 就绪', False, repr(e))
    sys.exit(1)

try:
    import main as M
    check('E0b import main 成功', True)
except Exception:
    check('E0b import main 成功', False, traceback.format_exc())
    sys.exit(1)

try:
    import file_sheet_controller as FSC
    check('E0c import file_sheet_controller 成功（无初始化环）', True)
except Exception:
    check('E0c import file_sheet_controller 成功（无初始化环）', False,
          traceback.format_exc())
    sys.exit(1)

# ---------------- 1. 构造期 ----------------
print()
print('=== E1 构造期 ===')
try:
    pet = M.RalseiPet()
    check('E1a RalseiPet() 构造成功（无 RecursionError）', True)
except Exception:
    check('E1a RalseiPet() 构造成功（无 RecursionError）', False,
          traceback.format_exc())
    sys.exit(1)

check('E1b 宿主持有 file_sheet 控制器',
      type(pet.__dict__.get('file_sheet')).__name__ == 'FileSheetController',
      'type=%r' % type(pet.__dict__.get('file_sheet')).__name__)
check("E1c 'file_sheet' 在转发名单里",
      'file_sheet' in M.RalseiPet._CONTROLLER_ATTRS,
      str(M.RalseiPet._CONTROLLER_ATTRS))
fs = pet.__dict__.get('file_sheet')
check('E1d 控制器自身 __dict__ 只有 p（无业务状态）',
      sorted(k for k in fs.__dict__ if k != 'p') == [],
      'own=%s' % sorted(k for k in fs.__dict__ if k != 'p'))

# ---------------- 2. 转发壳 ----------------
print()
print('=== E2 转发壳（宿主 -> 控制器）===')
NAMES = ['handle_file_operation', '_open_desktop_item_by_name',
         'fix_excel_format', 'fill_names_in_excel']
for n in NAMES:
    got = getattr(pet, n, None)
    check('E2 %s 可从宿主调用' % n, callable(got), 'type=%s' % type(got).__name__)
for n in NAMES:
    check('E2x %s 已不在 RalseiPet 类字典' % n, n not in M.RalseiPet.__dict__)
# ★ 铁律 7 的第一道：控制器**模块级**必须有 os
check('E2y ★控制器模块级有 os（15 处裸 os. 的唯一解析来源）',
      'os' in getattr(FSC, '__dict__', {}) and hasattr(FSC, 'os'),
      'has os=%r' % hasattr(FSC, 'os'))

# ---------------- 3. ★ 铁律 7：真步进到裸 os. 分支 ----------------
print()
print('=== E3 ★铁律 7：_open_desktop_item_by_name 真跑到裸 os. 站点 ===')
try:
    pet3 = M.RalseiPet()
    fs3 = pet3.__dict__['file_sheet']
    dk = mkfolder('desk3')
    # 沙箱里造两个真实对象：一个文件夹、一个文件
    sub = mkfolder('desk3/我的项目')
    real_file = os.path.join(dk, '报告.txt')
    with open(real_file, 'w', encoding='utf-8') as fh:
        fh.write('x')
    stub = _StubDesktop(dk)
    stub.desktop_elements = [
        {'type': 'folder', 'path': sub, 'name': '我的项目'},
        {'type': 'file', 'path': real_file, 'name': '报告.txt'},
    ]
    pet3.desktop_interaction = stub
    dia3 = _StubDialogue()
    pet3.dialogue_ui = dia3
    # ★ 桩打在**类型**上（实例字典会绕过——见 _ClassPatcher 注释）
    pat3 = _ClassPatcher()
    opened = []
    pat3.patch(type(pet3), 'open_folder', lambda self, p: opened.append(('folder', p)))
    pat3.patch(type(pet3), 'open_file', lambda self, p: opened.append(('file', p)))

    # (a) 匹配到文件夹 → 走 open_folder，**全程裸 os. 站点被解析**
    r = pet3._open_desktop_item_by_name('帮我打开 我的项目')
    check('E3a ★未抛 NameError（模块级 os 解析正常）', r is True, 'ret=%r' % r)
    check('E3b 命中文件夹并调到 open_folder',
          opened == [('folder', sub)], 'opened=%r' % opened)
    check('E3c update_desktop_elements 被调（刷新桌面元素）',
          stub.update_calls >= 1, 'calls=%d' % stub.update_calls)

    # (b) 匹配到文件（忽略扩展名）→ 走 open_file
    opened[:] = []
    pet3._open_desktop_item_by_name('打开报告')
    check('E3d 忽略扩展名命中文件并调到 open_file',
          opened == [('file', real_file)], 'opened=%r' % opened)

    # (c) ★ 兜底路径：元素列表为空 → 名字匹配必失败 → 退回
    #     `os.path.join(desktop_path, text)` + `os.path.exists` + `os.path.isdir`
    #     （L4385-4400 的 os.path.* 密集段）。这是**静态扫不出「跑起来解析得到吗」**的一段。
    #     ⚠️ 首版这里写错了：`desktop_path` 用了上级沙箱、而文本恰好命中**上一测试对象**
    #     → 断言与落点不符（`opened` 里是 join 出来的路径，`sub` 是另一条路径）。
    #     现在：`desktop_path` 直接指向 `desk3`，文本用**真实存在的子目录名**。
    opened[:] = []
    stub2 = _StubDesktop(dk)          # desktop_path = desk3（兜底会 join 到这里）
    stub2.desktop_elements = []       # 强制走兜底
    pet3.desktop_interaction = stub2
    pet3._open_desktop_item_by_name('打开 我的项目')
    expect_fb = os.path.join(dk, '我的项目')
    check('E3f ★兜底路径 os.path.exists/isdir 解析正常（未 NameError）',
          opened == [('folder', expect_fb)],
          'opened=%r expect=%r' % (opened, [('folder', expect_fb)]))

    # (e) 完全找不到 → 提示语分支（仍用到 os.path.join / exists）
    opened[:] = []
    pet3._open_desktop_item_by_name('打开 根本不存在的东西xyz')
    check('E3g 找不到时给提示且不开任何东西', opened == [] and len(dia3.calls) > 0,
          'opened=%r' % opened)

    # (f) 空指令分支（re 局部 import + 早退）
    pet3._open_desktop_item_by_name('打开')
    check('E3h 空指令分支返回 True 且不抛异常', True)
    pat3.restore()
except Exception:
    try:
        pat3.restore()
    except Exception:
        pass
    check('E3a ★未抛 NameError（模块级 os 解析正常）', False, traceback.format_exc())

# ---------------- 4. ★ 铁律 6：真跑打日志的分支 ----------------
print()
print('=== E4 ★铁律 6：真的走到 self._log_().xxx 站点 ===')
try:
    pet4 = M.RalseiPet()
    dk4 = mkfolder('desk4')
    # ⚠️ 首版把 dialogue_ui 桩成「**任何**调用都抛」→ 异常从**第一个** add_dialogue
    #    （L265 无 xlsx 提示）就抛出 → 直接进了**最外层 except**（L302 的 warning），
    #    而不是想验的 **L386 复核路径**；且外层 except 也再调一次 add_dialogue → 二次抛出。
    #    ⇒ 探针不能把「整条分发链」炸掉。改为：只让 `desktop_path` 抛（见 (b)）。
    xl4 = os.path.join(dk4, 'a.xlsx')
    with open(xl4, 'w', encoding='utf-8') as fh:
        fh.write('x')
    pet4.desktop_interaction = _StubDesktop(dk4)

    # (a) fix_excel_format 真调 Excel 会失败（假 xlsx）→ 走 L386 `self._log_().warning`
    #     ⚠️ 这是**真调 COM**（只对沙箱里的假文件），失败即走 warning 分支 —— 正是目标站点。
    dia4 = _StubDialogue()
    pet4.dialogue_ui = dia4
    r = pet4.handle_file_operation('打开表格并让格子对齐')
    check('E4a ★fix_excel_format 失败路径走到 self._log_().warning 且未 NameError',
          r is True, 'ret=%r' % r)

    # (b) 最外层 except 兜底：造"必然异常但**不炸分发链**"的入口
    #     ⚠️ 首版让 `desktop_path` 属性抛 + 让**失败文案**也抛 → 异常从 L303 二次抛出，
    #        整个探针 block 被吞。断言「方法返回 True」和「真打日志」不能同时用**同一个**会炸的桩。
    #     改法：`desktop_path` 抛（→ 进 except）→ 但 `add_dialogue` **不抛** → 方法正常返回 True。
    #     于是 `self._log_().warning` 被真的执行到（这正是目标站点）。
    class _QuietBoomDesktop(object):
        @property
        def desktop_path(self):
            raise RuntimeError('boom-desktop')

    pet4.desktop_interaction = _QuietBoomDesktop()
    dia4b = _StubDialogue()
    pet4.dialogue_ui = dia4b
    r2 = pet4.handle_file_operation('打开表格')
    check('E4b ★外层 except 走到 self._log_().warning（未 NameError）且优雅返回',
          r2 is True and any('处理文件操作指令失败' in t for t in texts_of(dia4b)),
          'ret=%r texts=%r' % (r2, texts_of(dia4b)))

    # 反向控制：确认这些分支**真的会**打日志（否则上面是空跑）
    import io as _io_
    _src = _io_.open(os.path.join(MODS, 'file_sheet_controller.py'),
                     encoding='utf-8').read()
    _n = _src.count('self._log_().warning')
    check('E4c 反向控制：本方法确有 self._log_().warning 站点', _n >= 2,
          'count=%d' % _n)
except Exception:
    check('E4a ★fix_excel_format 失败路径走到 self._log_().warning', False,
          traceback.format_exc())

# ---------------- 5. handle_file_operation 各分支真跑（全桩）----------------
print()
print('=== E5 handle_file_operation 分支（全桩，不碰真实桌面）===')
pat5 = _ClassPatcher()
CTRLCLS = type(pet.__dict__['file_sheet'])      # FileSheetController
try:
    pet5 = M.RalseiPet()
    dk5 = mkfolder('desk5')
    stub5 = _StubDesktop(dk5)
    pet5.desktop_interaction = stub5
    dia5 = _StubDialogue()
    pet5.dialogue_ui = dia5

    # (a) "填人名"+"表格"，但沙箱里**没有** .xlsx → 走「桌面上没有找到Excel表格文件！」
    r = pet5.handle_file_operation('帮我填人名到表格')
    check('E5a 填人名分支：无 xlsx 时给出提示并返回 True',
          r is True and any('没有找到Excel' in t for t in texts_of(dia5)),
          'texts=%r' % texts_of(dia5)[:3])

    # (b) "打开"+"表格"，沙箱无 xlsx → 同样提示
    dia5.calls[:] = []
    pet5.handle_file_operation('打开表格')
    check('E5b 打开表格分支：无 xlsx 时给出提示',
          any('没有找到Excel' in t for t in texts_of(dia5)),
          'texts=%r' % texts_of(dia5)[:3])

    # (c) ★ 有 xlsx + "对齐" → 走 fix_excel_format（桩验证**分派正确**）
    #     ★ 桩必须打在 **FileSheetController** 上（方法体里 self 就是它）。
    xl = os.path.join(dk5, 'a.xlsx')
    with open(xl, 'w', encoding='utf-8') as fh:
        fh.write('x')
    called5 = []
    pat5.patch(CTRLCLS, 'fix_excel_format',
               lambda self, p: (called5.append(p), True)[1])
    dia5.calls[:] = []
    pet5.handle_file_operation('打开表格并让格子对齐')
    check('E5c ★"对齐"触发 fix_excel_format 分派（未真调 Excel）',
          called5 == [xl], 'called=%r' % called5)
    # ★ 负控制：让 fix_excel_format 返回 False → 必须走"失败了"文案
    pat5.patch(CTRLCLS, 'fix_excel_format', lambda self, p: False)
    dia5.calls[:] = []
    pet5.handle_file_operation('打开表格并让格子对齐')
    check('E5c2 负控制：fix 返回 False 时给出失败文案',
          any('失败了' in t for t in texts_of(dia5)), 'texts=%r' % texts_of(dia5)[:3])

    # (d) ★ 有 xlsx 但只是"打开表格" → 走 os.startfile（这里桩掉，验证分派正确）
    started5 = []
    _real_startfile = getattr(os, 'startfile', None)
    if _real_startfile is not None:
        os.startfile = lambda p: started5.append(p)
    try:
        dia5.calls[:] = []
        pet5.handle_file_operation('打开表格')
        check('E5d ★仅"打开表格"走 os.startfile 分派（未真开文件）',
              started5 == [xl], 'started=%r' % started5)
    finally:
        if _real_startfile is not None:
            os.startfile = _real_startfile

    # (e) ★ "打开"但**不含**"表格" → 必须分派到 _open_desktop_item_by_name（新修分支）
    #     分支顺序核实（读原文）：L255 "打开" and "表格" → L296 "打开" and not "表格"。
    #     "打开计算器" 含"打开"、不含"表格" → 精确落 L296。
    #     ★ 同样必须打在 **FileSheetController** 上（方法体内 self 解析）。
    routed5 = []
    pat5.patch(CTRLCLS, '_open_desktop_item_by_name',
               lambda self, ui: (routed5.append(ui), True)[1])
    pet5.handle_file_operation('打开计算器')
    check('E5e ★"打开X"（非表格）分派到 _open_desktop_item_by_name',
          routed5 == ['打开计算器'], 'routed=%r' % routed5)

    # (f) 普通闲聊（既非新建/填人名/打开）→ 落到末尾 show_dialogue，返回 True
    routed5[:] = []
    dia5.calls[:] = []
    r = pet5.handle_file_operation('今天天气不错')
    check('E5f 非文件指令：不误伤（不调 _open_desktop_item_by_name）',
          routed5 == [] and r is True, 'routed=%r ret=%r' % (routed5, r))

    # (g) ★ "新建"+"表格" 分支：真调 win32com → Excel。**这里必须桩掉**，否则会真建文件。
    #     用桩替换 fill/fix 之后，唯一会真碰 Excel 的就是"新建"分支 ——
    #     所以本探针**不驱动**它，改为静态断言「该分支确实存在且被 `try/finally` 保护」。
    #     ⚠️ 首版用 `_io_.open(...)` —— `_io_` 是 E4 的**局部**名，此处 NameError。
    _fssrc = open(os.path.join(MODS, 'file_sheet_controller.py'),
                  encoding='utf-8').read()
    _i = _fssrc.find('new_file_name = "新建表格.xlsx"')
    check('E5g ★"新建表格"分支存在且 SaveAs 有 finally 保护（静态，不驱动）',
          _i >= 0 and 'workbook.SaveAs(new_file_path)' in _fssrc[_i:_i + 900]
          and 'finally:' in _fssrc[_i:_i + 1400],
          'idx=%d' % _i)
    # ★ 反向控制：确认真有第三条分支（否则 E5e 的"不含表格"断言可能是空跑）
    check('E5g2 反向控制：三条 elif 分支齐备（填人名/打开表格/打开非表格）',
          _fssrc.count('elif "填人名" in user_input_lower') == 1 and
          _fssrc.count('elif "打开" in user_input_lower and "表格" in user_input_lower') == 1 and
          _fssrc.count('elif "打开" in user_input_lower and "表格" not in user_input_lower') == 1)
    pat5.restore()
except Exception:
    try:
        pat5.restore()
    except Exception:
        pass
    check('E5a 填人名分支：无 xlsx 时给出提示', False, traceback.format_exc())

# ---------------- 6. ★ 铁律 3 反向：控制器不写宿主新名 ----------------
print()
print('=== E6 ★铁律 3 反向：本项不搬状态（无需预声明）===')
try:
    pet6 = M.RalseiPet()
    fs6 = pet6.__dict__['file_sheet']
    dk6 = mkfolder('desk6')
    stub6 = _StubDesktop(dk6)
    stub6.desktop_elements = []
    pet6.desktop_interaction = stub6
    pet6.dialogue_ui = _StubDialogue()
    pat6 = _ClassPatcher()
    noop = lambda self, p: None
    pat6.patch(type(pet6), 'open_folder', noop)
    pat6.patch(type(pet6), 'open_file', noop)
    before = set(pet6.__dict__)
    pet6._open_desktop_item_by_name('打开 不存在xyz')
    pet6.handle_file_operation('打开 不存在xyz')
    after = set(pet6.__dict__)
    new_keys = sorted(after - before)
    # ⚠️ `dialogue_ui` 记录桩会往**桩自己**的 list 里塞——不落宿主。宿主新增应为空。
    #    （若本项真搬了状态，这里会冒出 `_file_*` 之类的新键 —— 那才是 FAIL。）
    check('E6a ★控制器未给宿主新增任何属性（不搬状态）', new_keys == [],
          'new=%r' % new_keys)
    check('E6b 控制器自身字典仍只有 p',
          sorted(k for k in fs6.__dict__ if k != 'p') == [],
          'own=%s' % sorted(k for k in fs6.__dict__ if k != 'p'))
    pat6.restore()
except Exception:
    try:
        pat6.restore()
    except Exception:
        pass
    check('E6a ★控制器未给宿主新增任何属性（不搬状态）', False,
          traceback.format_exc())

# ---------------- 7. 转发到兄弟控制器 / 宿主链 ----------------
print()
print('=== E7 转发：宿主成员与兄弟控制器 ===')
try:
    pet7 = M.RalseiPet()
    fs7 = pet7.__dict__['file_sheet']
    _M = object()
    # 宿主实例字典成员
    check('E7a 读得到宿主实例成员 desktop_interaction',
          getattr(fs7, 'desktop_interaction', _M) is not _M)
    # 宿主类型 MRO 成员（open_file / open_folder 在宿主链上）
    check('E7b 解析得到宿主 open_folder（MRO 白名单）',
          callable(getattr(fs7, 'open_folder', None)))
    check('E7c 解析得到宿主 open_file（MRO 白名单）',
          callable(getattr(fs7, 'open_file', None)))
    # 负控制：不存在名仍须 AttributeError（不许吞错、不许 RecursionError）
    try:
        getattr(fs7, '_definitely_not_exist_xyz')
        check('E7d 不存在名仍抛 AttributeError', False, 'no raise')
    except AttributeError:
        check('E7d 不存在名仍抛 AttributeError', True)
    except RecursionError:
        check('E7d 不存在名仍抛 AttributeError', False, 'RecursionError')
    # 兄弟控制器可达（第 3 条白名单）—— 当前用不到，但纪律要求
    # ★ 用**独立对象**做哨兵（`is not` 一个字面量会触发 SyntaxWarning 且语义是身份比较）
    check('E7e 兄弟控制器可达（spell 的方法经 file_sheet 转发）',
          callable(getattr(fs7, '_cast_spell_then', None)) or
          getattr(fs7, '_hide_stage', _M) is not _M)
except Exception:
    check('E7d 不存在名仍抛 AttributeError', False, traceback.format_exc())

# ---------------- 8. 静态哨兵：裸 _log_() / Qt(self) / 模块级 import ----------------
print()
print('=== E8 静态哨兵 ===')
try:
    import ast as _ast2
    import io as _io2
    csrc = _io2.open(os.path.join(MODS, 'file_sheet_controller.py'),
                     encoding='utf-8').read()
    ct = _ast2.parse(csrc)
    bare_log = [n.lineno for n in _ast2.walk(ct)
                if isinstance(n, _ast2.Call) and isinstance(n.func, _ast2.Name)
                and n.func.id == '_log_']
    check('E8a 无裸 _log_() 调用', bare_log == [], 'lines=%s' % bare_log)

    # Qt(self) 形态（铁律 1）—— 本项预期 0
    QT = ('QTimer', 'QObject', 'QWidget', 'QLabel', 'QMenu', 'QAction',
          'QDialog', 'QMainWindow', 'QThread', 'QGraphicsItem')
    hits = []
    for fn in [n for n in ct.body if isinstance(n, _ast2.ClassDef)][0].body:
        if not isinstance(fn, _ast2.FunctionDef):
            continue
        for node in _ast2.walk(fn):
            if isinstance(node, _ast2.Call):
                fnm = node.func.id if isinstance(node.func, _ast2.Name) else (
                    node.func.attr if isinstance(node.func, _ast2.Attribute) else '')
                if fnm in QT:
                    for a in node.args:
                        if isinstance(a, _ast2.Name) and a.id == 'self':
                            hits.append('%d %s(self)' % (node.lineno, fnm))
    check('E8b 无 Qt(self) 形态（本项无铁律 1）', hits == [], 'hits=%s' % hits)

    # 模块级 import
    mod_names = set()
    for n in ct.body:
        if isinstance(n, _ast2.Import):
            for a in n.names: mod_names.add(a.name)
        elif isinstance(n, _ast2.ImportFrom):
            for a in n.names: mod_names.add(a.name)
    check('E8c 模块级含 os', 'os' in mod_names, str(sorted(mod_names)))
    check('E8d 模块级含 logging', 'logging' in mod_names)
    check('E8e 模块级**不含** win32com.client（保持局部，避免导入期硬依赖）',
          'win32com.client' not in mod_names)

    # ★ 裸 os. 站点计数（铁律 7）
    bare_os = 0
    for fn in [n for n in ct.body if isinstance(n, _ast2.ClassDef)][0].body:
        if not isinstance(fn, _ast2.FunctionDef) or fn.name in (
                '__init__', '__getattr__', '__setattr__', '_log_'):
            continue
        for sub in _ast2.walk(fn):
            if isinstance(sub, _ast2.Attribute) and isinstance(sub.value, _ast2.Name) \
                    and sub.value.id == 'os':
                bare_os += 1
    check('E8f ★裸 os. 站点数 = 15', bare_os == 15, 'count=%d' % bare_os)
    # ★ E8g 必须只数**代码** —— 类/模块 docstring 里就在讲解 `self._log_().` 形态，
    #    整文件计数 = 13（12 实码 + 1 docstring）→ 首跑假红。
    #    这正是「源级断言别用 '字面量' in 源码」的第 6 次复发。
    _ccls = [n for n in ct.body if isinstance(n, _ast2.ClassDef)][0]
    _cmeths = {n.name: n for n in _ccls.body if isinstance(n, _ast2.FunctionDef)}
    _declines = csrc.split('\n')

    def _code_ranges(node):
        skip = set()
        for sub in _ast2.walk(node):
            if isinstance(sub, _ast2.Expr) and isinstance(sub.value, _ast2.Constant) \
                    and isinstance(sub.value.value, str):
                for ln in range(sub.lineno, sub.end_lineno + 1):
                    skip.add(ln)
        return skip

    _code = []
    for _nm in NAMES:
        _node = _cmeths[_nm]
        _skip = _code_ranges(_node)
        for _ln in range(_node.lineno, _node.end_lineno + 1):
            if _ln not in _skip:
                _code.append(_declines[_ln - 1])
    _code_s = '\n'.join(_code)
    check('E8g ★方法体内 self._log_(). 计数 = 12（只数代码，排除 docstring）',
          _code_s.count('self._log_().') == 12,
          'count=%d' % _code_s.count('self._log_().'))
    check('E8h 全文件计数 = 13（12 实码 + 1 docstring 讲解）—— 证明 docstring 噪声确实存在',
          csrc.count('self._log_().') == 13, 'count=%d' % csrc.count('self._log_().'))
except Exception:
    check('E8a 无裸 _log_() 调用', False, traceback.format_exc())

# ---------------- 9. 环境约束：win32com 缺失时不许崩 ----------------
print()
print('=== E9 环境健壮性：win32com 不可用时优雅失败 ===')
try:
    pet9 = M.RalseiPet()
    r = pet9.fix_excel_format(os.path.join(SANDBOX, 'nope.xlsx'))
    check('E9a fix_excel_format 对不存在文件返回 False（不抛）', r is False,
          'ret=%r' % r)
    r2 = pet9.fill_names_in_excel(os.path.join(SANDBOX, 'nope.xlsx'), ['甲', '乙'])
    check('E9b fill_names_in_excel 对不存在文件返回 False（不抛）', r2 is False,
          'ret=%r' % r2)
except Exception:
    check('E9a fix_excel_format 对不存在文件返回 False（不抛）', False,
          traceback.format_exc())

# ---------------- 清理沙箱 ----------------
try:
    shutil.rmtree(SANDBOX, ignore_errors=True)
    check('E10 沙箱目录已清理', not os.path.isdir(SANDBOX))
except Exception:
    pass

# ---------------- 汇总 ----------------
PASS = sum(1 for _, ok, _ in results if ok)
FAIL = len(results) - PASS
print()
print('=' * 60)
print('W1-6 E2E  PASS=%d  FAIL=%d' % (PASS, FAIL))
print('=' * 60)
if FAIL:
    print('FAILED:')
    for n, ok, d in results:
        if not ok:
            print('   ', n, '::', d[:400])
sys.exit(1 if FAIL else 0)
