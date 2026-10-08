# -*- coding: utf-8 -*-
u"""第97轮回归锁：两处「用户视角可感知」的修复不许静默回退。

用户三条真机观察里的 ①/③ 落到了**两处真缺陷**（用户原话：
「那个坠落的触发逻辑不对吧，还有，那并没有窗口他也会判定我们移动了窗口然后摔倒，
对了，他站起来不需要揉眼睛，OK？」）。

锁什么
======

【A 段】`handle_jump` 的"穿透检查"**不许再把桌面层当障碍**
    `ralsei_pet/src/main.py` 的 `handle_jump` 里有一段"跳跃路径是否穿过楼板"的检查：

        all_floors = self.floor_manager.get_all_floors()   # = floors + [desktop_floor]
        for floor in all_floors:
            if self._floor_identity_key(floor) in (cur_fid, tgt_fid):
                continue
            if floor['rect'].intersects(current_rect):
                self.start_falling()          # ← 判"穿透"，取消跳跃并强制坠落
                return

    而 `floor_manager.get_all_floors()` **总是**把桌面层算进去，且
    `desktop_floor['rect']` 恒等于**整个虚拟屏幕**（`update_floors`）。
    排除条件只有"起点/终点"，桌面层的 key 是 `'desktop'` ⇒ **只有起点或终点本身
    是桌面时才被排除**。

    ⇒ **起点与终点都是窗口**时（例如站在窗口 A 上跳到更高的窗口 B —— 这正是
      `get_jump_destinations` 给出的**真实候选**），桌面层留在循环里，而宠物矩形
      恒在屏幕内 ⇒ `intersects` **恒为 True** ⇒ 起跳第一帧就被判"穿透"并
      `start_falling()` **强制摔下来**。
    用户视角 = "跳一半掉下来 / 坠落的触发逻辑不对"。

    取证：`_tools/probe97b_pierce.py`（真实 FloorManager 复算该循环）。

【B 段】摔后恢复**不许再播 `fall_back_rub`（揉眼/啜泣）**
    `handle_fall` 的 `dazed`（晕乎）阶段原来切 `fall_back_rub`。该素材的**原始
    语义**是「**坐在地上啜泣**」（仓库根 `要求:80`：使用条件为"触发轻微悲伤事件、
    角色处于坐在地上状态"），拿它当"摔后恢复"会把"呻吟"演成"啜泣+揉眼"。
    用户口径（第97轮）：**"他站起来不需要揉眼睛"**。
    修 = 改切 `fall_back`（`animations.json:545-547`，"地上状态动画"，5 帧）。

段一览
------
  A 前置锚点
    A1 两个目标函数都能抽到真源码（非凭印象）
  A2 ★★★ `handle_jump`（**剥注释后**）确实含桌面层排除
    A3 行为级：起点/终点都是窗口时，**不**命中桌面层（真实 FloorManager 复算）
    A4 负控制（恢复式变异）：去掉该排除 ⇒ A3 必须翻面（命中桌面层）
  B `handle_fall` 的晕乎阶段改播 `fall_back`
    B1 ★★★ `handle_fall`（**剥注释后**）不再出现 `fall_back_rub`
    B2 行为级：真跑 `trigger_splat` + `handle_fall`，晕乎阶段切的是 `fall_back`
    B3 负控制：`fall_back` 素材缺失时不崩，且**也不会**回落到 `fall_back_rub`
  C 判据自身体检
    C1 恒真防护：本文件判据里**没有** `check(..., True)` 形态
    C2 成功标记打印点唯一（供 G2 计数）
    C3 被测文件在盘
    C4 剥注释链自证（原文含 fall_back_rub，剥注释后必须不含）
    C5 ★★★ 成功标记字面量只能是打印模板（防 G2 计数**自匹配**）

★ 本套件零网络 / 零外部盘；Qt 走 offscreen（G2 注入 QT_QPA_PLATFORM）。
"""
import ast
import io
import os
import re
import sys
import textwrap
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
PET_DIR = os.path.join(ROOT, 'ralsei_pet')
SELF_PY = os.path.abspath(__file__)

_n = _passed = _failed = 0


def check(desc, cond, detail=''):
    global _n, _passed, _failed
    _n += 1
    if cond:
        _passed += 1
        print('[PASS] %s' % desc)
    else:
        _failed += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def P(s=''):
    print(s)


def _rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


MAIN_TEXT = _rd(MAIN_PY)
MAIN_TREE = ast.parse(MAIN_TEXT)


def _func_src(name):
    """按名字抽**整个函数**源码（含 def 头）。"""
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = MAIN_TEXT.split('\n')
            return '\n'.join(lines[node.lineno - 1: node.end_lineno])
    return None


def _func_body_src(name):
    """只取**函数体**（去掉 def 头，避免外层缩进干扰）。"""
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = MAIN_TEXT.split('\n')
            first = node.body[0].lineno
            return '\n'.join(lines[first - 1: node.end_lineno])
    return None


def _func_code(name):
    """按名字取函数的**规范化源码**：`ast.unparse(函数节点)`。

    一步到位：去注释 / 保留字符串字面量 / 顶格（不依赖文本切片的缩进）。

    ★★ 为什么不用"切文本 + `textwrap.dedent` + `ast.parse`"（本套件首轮实测
      **两次**静默失效）：方法体的**首条语句若是多行 docstring**，其内容行往往
      缩进不足，`dedent` 的公共前缀被拉低到那些行 ⇒ 去不干净 ⇒ `ast.parse` 报
      `unexpected indent` ⇒ 落进 `except` **静默返回原文**（注释根本没剥）⇒
      "不含某串"的判据把**注释里**的名字当成代码引用 ⇒ 假红。
      直接 unparse AST 节点没有缩进问题。C4 自证这条链有效。
    """
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            try:
                return ast.unparse(node)
            except Exception:
                return ''
    return ''


def _norm(s):
    """归一化：去空白 + 统一引号，用于"某调用形态是否出现"。"""
    return re.sub(r'\s+', '', s or '').replace('"', "'")


P('=' * 78)
P('# 第97轮回归锁：跳跃穿透不再误判桌面层 + 摔后恢复不再揉眼')
P('=' * 78)

# ============================================================ A 前置锚点
P('')
P('--- A 前置锚点')
_hj_src = _func_src('handle_jump')
_hf_src = _func_src('handle_fall')
check('A1 两个目标函数都能抽到真源码（handle_jump / handle_fall）',
      bool(_hj_src) and bool(_hf_src),
      'handle_jump=%s handle_fall=%s' % (bool(_hj_src), bool(_hf_src)))

# ============================================================ A2 源码级
P('')
P('--- A2 handle_jump 的穿透检查排除桌面层（源码级，剥注释）')
_hj_code = _norm(_func_code('handle_jump'))
_need = "floor.get('type')=='desktop'"
check('A2 handle_jump（剥注释后）含 `floor.get(\'type\') == \'desktop\'` 的排除',
      _need in _hj_code,
      '未找到；剥注释后片段长度=%d' % len(_hj_code))

# ============================================================ A3 行为级
P('')
P('--- A3 行为级：起点/终点都是窗口时不再误判桌面层')


def _identity_key(floor):
    """main.py `_floor_identity_key` 的等价复写（staticmethod，无隐藏状态）。"""
    if floor is None:
        return None
    if floor.get('type') == 'desktop':
        return 'desktop'
    return ('window', floor.get('window_hwnd'))


def _pierce_hits(fm, current_floor, jump_target_floor, current_rect,
                 skip_desktop=True):
    """`handle_jump` 穿透循环的等价复算。

    `skip_desktop=True` = **第97轮修复后**的语义（桌面层不参与）；
    `skip_desktop=False` = 修复前（只排除起点/终点）—— 负控制用。
    """
    cur_fid = _identity_key(current_floor)
    tgt_fid = _identity_key(jump_target_floor)
    hits = []
    for floor in fm.get_all_floors():
        if _identity_key(floor) in (cur_fid, tgt_fid):
            continue
        if skip_desktop and floor.get('type') == 'desktop':
            continue
        if floor['rect'].intersects(current_rect):
            hits.append(floor)
    return hits


from PyQt5.QtWidgets import QApplication  # noqa: E402
from PyQt5.QtCore import QRect  # noqa: E402

_app = QApplication.instance() or QApplication([])
sys.path.insert(0, os.path.join(PET_DIR, 'modules'))
sys.path.insert(0, os.path.join(PET_DIR, 'src'))
from floor_manager import FloorManager  # noqa: E402

SCREEN = QRect(0, 0, 1920, 1080)
W_A = (1001, QRect(200, 200, 800, 600))
W_B = (1002, QRect(300, 250, 700, 500))    # 压在 A 前面 ⇒ B 更高


def _make_fm(windows):
    fm = FloorManager(parent=None)
    fm.desktop_floor['rect'] = QRect(SCREEN)
    fm.underlying_windows = [
        {'hwnd': h, 'title': 'w%d' % h, 'class_name': 'Notepad',
         'rect': QRect(r), 'z_order': i}
        for i, (h, r) in enumerate(windows)
    ]
    fm._generate_floors()
    return fm


_fm2 = _make_fm([W_B, W_A])
_fA = _fm2.get_floor_by_window(W_A[0])
_fB = _fm2.get_floor_by_window(W_B[0])
# 站在 A 的下边缘（B 的正下方、A 的可见区里）—— "向上跳 B" 的真实起点。
_stand = QRect(500, 760, 36, 76)

# ★ 关键（否则 A3 恒真）：复算时"排不排除桌面层"必须**由产品源码推导**，
#   不能由我硬编码 —— 硬编码等于只测我自己的函数，测不到产品。
_product_skips_desktop = _need in _hj_code
_hits_fixed = _pierce_hits(_fm2, _fA, _fB, _stand,
                           skip_desktop=_product_skips_desktop)
check('A3 窗口A→窗口B（起点终点都不是桌面）⇒ 不命中桌面层'
      '（复算口径取自产品源码：skips_desktop=%s）' % _product_skips_desktop,
      bool(_fA) and bool(_fB) and _product_skips_desktop
      and all(h.get('type') != 'desktop' for h in _hits_fixed),
      'floors=%d A=%s B=%s hits=%s'
      % (len(_fm2.floors), bool(_fA), bool(_fB),
         [h.get('type') for h in _hits_fixed]))

# 可达性：真实 floor_manager 是否真的把"跳 B"作为候选给出
try:
    _cands = [f for f, _p in _fm2.get_jump_destinations(_fA, _stand.topLeft())]
except Exception:
    _cands = []
check('A3b 真实 get_jump_destinations 把"窗口B"作为候选给出（A3 的场景可达）',
      _fB is not None and any(_identity_key(c) == _identity_key(_fB)
                              for c in _cands),
      'cands=%s' % [_identity_key(c) for c in _cands])

# ============================================================ A4 负控制
P('')
P('--- A4 负控制：去掉桌面层排除 ⇒ 必须翻面')
_hits_old = _pierce_hits(_fm2, _fA, _fB, _stand, skip_desktop=False)
check('A4 负控制（恢复式变异）：不排除桌面层时**命中**桌面层 ⇒ A3 的判据非恒真',
      any(h.get('type') == 'desktop' for h in _hits_old),
      'hits=%s' % [h.get('type') for h in _hits_old])

# ============================================================ B1 源码级
P('')
P('--- B1 handle_fall 的晕乎阶段不再用 fall_back_rub（源码级，剥注释）')
_hf_code = _norm(_func_code('handle_fall'))
check('B1 handle_fall（剥注释后）不含 fall_back_rub',
      'fall_back_rub' not in _hf_code,
      '仍出现；片段长度=%d' % len(_hf_code))

check('B1b handle_fall（剥注释后）确实切 fall_back（不是"把动画整个删掉"）',
      "change_animation('fall_back'" in _hf_code,
      '未找到 change_animation(\'fall_back\')')

# ============================================================ B2 行为级
P('')
P('--- B2 行为级：真跑 trigger_splat + handle_fall，晕乎阶段切 fall_back')


class _SplatStub:
    """从"刚落地"开始的极简桩：只提供 `trigger_splat` / `handle_fall` 用到的面。"""

    def __init__(self, reason, present=('splat', 'splat_mad', 'fall_back',
                                        'fall_back_rub', 'land', 'pose', 'idle')):
        self._present = tuple(present)
        self.sprite_loader = types.SimpleNamespace(
            sprites={k: 1 for k in self._present})
        self.is_splat = False
        self.splat_start_time = 0.0
        self.is_moving = True
        self.is_falling = False
        self.is_gravity_falling = True
        self.is_recovering = False
        self.recovery_duration = 0.0
        self.recovery_max_duration = 1.5
        self.fall_duration = 0.0
        self.fall_start_time = 0.0
        self.max_fall_duration = 3.0
        self._fall_reason = reason
        self.anims = []
        self.msgs = []
        self.events = []
        self.sound_manager = types.SimpleNamespace(play_splat=lambda: None)
        self.dialogue_ui = types.SimpleNamespace(
            add_dialogue=lambda who, text, mood=None: self.msgs.append(text),
            show_dialogue=lambda: None)
        self.emotion_system = types.SimpleNamespace(
            react_to_event=lambda e, d: self.events.append(e))

    def change_animation(self, name, force=False):
        self.anims.append(name)

    def play_animation_once(self, name, restore_to=None):
        self.anims.append(name)

    def _desktop_floor_y(self):
        return SCREEN.bottom() - 80

    def _clamp_pos_to_desktop(self, x, y):
        return (int(x), int(y))

    def pos(self):
        from PyQt5.QtCore import QPoint
        return QPoint(500, 500)

    def move(self, x, y):
        pass


_RalseiPet = None
try:
    from main import RalseiPet as _RalseiPet  # noqa: E402
except Exception as _e:  # pragma: no cover
    P('  （import main 失败：%s）' % _e)


def _drive_to_dazed(reason, present=None, dt=0.05, limit=40.0):
    pet = _SplatStub(reason) if present is None else _SplatStub(reason, present)
    _RalseiPet.trigger_splat(pet)
    t = 0.0
    while t < limit:
        _RalseiPet.handle_fall(pet, dt, time.time())
        t += dt
        if getattr(pet, '_fall_phase', None) == 'dazed':
            return pet, t
    return pet, None


if _RalseiPet is not None:
    _pet, _t = _drive_to_dazed(None)
    _dazed_anim = _pet.anims[-1] if _pet.anims else None
    check('B2 真跑进入晕乎阶段后，最后切的动画是 fall_back（不是 fall_back_rub）',
          _t is not None and _dazed_anim == 'fall_back',
          'dazed_at=%s last_anim=%s anims=%s' % (_t, _dazed_anim, _pet.anims))

    # ======================================================== B3 负控制
    _pet2, _t2 = _drive_to_dazed(None, present=('splat', 'splat_mad', 'land',
                                               'pose', 'idle'))
    check('B3 负控制：连 fall_back 素材都没有时，不崩、也不会回落到 fall_back_rub',
          _t2 is not None and 'fall_back_rub' not in _pet2.anims,
          'dazed_at=%s anims=%s' % (_t2, _pet2.anims))
else:
    check('B2 真跑进入晕乎阶段后，最后切的动画是 fall_back（不是 fall_back_rub）',
          False, 'import main 失败，跳过')
    check('B3 负控制：连 fall_back 素材都没有时，不崩、也不会回落到 fall_back_rub',
          False, 'import main 失败，跳过')

# ============================================================ C 判据自身体检
P('')
P('--- C 判据自身体检')
_self_src = _rd(SELF_PY)
# C1 恒真防护：本文件里不许出现 `check(<desc>, True)` 这种"看着在守其实没守"
_self_tree = ast.parse(_self_src)
_trivial = 0
for node in ast.walk(_self_tree):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'check' and len(node.args) >= 2):
        if isinstance(node.args[1], ast.Constant) and node.args[1].value is True:
            _trivial += 1
check('C1 恒真防护：本套件判据里没有 check(..., True) 形态',
      _trivial == 0, 'trivial_checks=%d' % _trivial)

# C2 标记打印点唯一。
# ★ 用 AST 数**真实 print 调用**（实参是 `'[PASS] %s' % desc` 这种 BinOp），
#   绝不 `str.count` —— 本文件 docstring 与 C2 自身的字符串里也含这个子串，
#   用字符串计数会**自匹配**（改前实测 count=3 假红）。
_mark = 0
for _node in ast.walk(_self_tree):
    if (isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name)
            and _node.func.id == 'print' and _node.args):
        _a0 = _node.args[0]
        if (isinstance(_a0, ast.BinOp) and isinstance(_a0.op, ast.Mod)
                and isinstance(_a0.left, ast.Constant)
                and _a0.left.value == '[PASS] %s'):
            _mark += 1
check('C2 成功标记的打印点只出现 1 次（供 G2 计数）',
      _mark == 1, 'count=%d' % _mark)

check('C3 被测文件在盘', os.path.exists(MAIN_PY), MAIN_PY)

# C4 ★★ 判据的判据：`_func_code` 真的在剥注释。
#   首轮实测"切文本 + dedent + ast.parse"**两次静默失效**（方法体首条语句若为
#   多行 docstring，其内容行缩进不足 ⇒ 公共前缀被拉低 ⇒ parse 报
#   unexpected indent ⇒ except 静默返回**原文**）⇒ B1 把**注释里**的
#   `fall_back_rub` 当成代码引用 ⇒ 假红。
#   这里用**真实源码**自证：`handle_fall` 的原文（切文本）里含 `fall_back_rub`
#   （只在注释里），剥注释后必须没有。两者不对称 ⇒ 剥注释链是坏的。
_hf_raw = _func_body_src('handle_fall') or ''
_hf_code_c4 = _func_code('handle_fall')
check('C4 `_func_code` 真在剥注释（原文含 fall_back_rub，剥注释后必须不含）',
      'fall_back_rub' in _hf_raw and 'fall_back_rub' not in _hf_code_c4,
      'raw_has=%s code_has=%s' % ('fall_back_rub' in _hf_raw,
                                  'fall_back_rub' in _hf_code_c4))

# C5 ★★★ 防 G2 计数**自匹配**（第 97 轮 C2 首版真踩，是同一个坑的第三次发作：
#   95D1 → 96bC4 → 97C2-G2 计数）。
#   G2 的计数是 `re.findall(r'\[PASS\]|\[\s*OK\s*\]', stdout)` —— 纯粹**数文本
#   出现次数**。任何 desc/文案里回显成功标记字面量，该行就被数成 2 次 ⇒
#   套件判据数虚高（实测 13 → 14）。
#   ⇒ 全文件含该字面量的**字符串常量**，只允许"恰好等于打印模板"的那一个。
#   ⚠ 本段自己绝不能出现完整字面量：过滤器与被比较值都用**拆写**（`'[PA' +
#   'SS]'`），否则这一行自己就会被扫成 bad ⇒ 恒红（自指陷阱）。
_MARK = '[PA' + 'SS]'
_TMPL = _MARK + ' %s'
_bad_mark_lits = []
for _n3 in ast.walk(_self_tree):
    if (isinstance(_n3, ast.Constant) and isinstance(_n3.value, str)
            and _MARK in _n3.value and _n3.value != _TMPL):
        _bad_mark_lits.append(_n3.value)
check('C5 成功标记字面量只能是打印模板（防 G2 计数自匹配）',
      not _bad_mark_lits, 'bad=%r' % (_bad_mark_lits,))

# ---------------------------------------------------------------- 汇总
P('')
P('=' * 78)
P('第97轮回归锁：PASS=%d FAIL=%d 合计=%d' % (_passed, _failed, _n))
P('=' * 78)

sys.exit(1 if _failed else 0)
