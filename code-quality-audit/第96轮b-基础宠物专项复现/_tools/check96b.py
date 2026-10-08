# -*- coding: utf-8 -*-
u"""第96轮b 回归锁：基础宠物两处「用户视角可感知」的修复不许静默回退。

锁什么（两处，均经真机取证）
============================

【B 段】`react_to_desktop_element` **不许再直写对话**（口径违规）
    用户 2026-09-19 口径：「所有对话全权交给 AI」。落实在 `speak_event` 的
    docstring 逐字 ——「不给内置台词：说不了就不说话，宁可安静也不甩一句写死的
    台词。这是"全权交给 AI"的口径」。
    但 `main.py` 的 `react_to_desktop_element` 里原来有：
        self.dialogue_ui.add_dialogue("ralsei", reaction['dialogue'], reaction['emotion'])
        self.dialogue_ui.show_dialogue()
    ⇒ 宠物自主漫游靠近桌面图标时会**绕过唯一入口**弹出一句写死的话。
    真机实证（`_tools/probe96b_canned.py`，落 `_evidence/probe96b_canned.txt`）：
      · 修前 A 段：`add_dialogue` 增量 **2**、`speak_event` 增量 **0**（绕过实锤）
        实抓台词：「这是文本文件呢！ 纸做的东西要小心处理哦！」
      · 同一次运行的负控制 B 段：`speak_event(pool=None)` 增量 **0**（口径没坏）
      · 同一次运行的正控制 C 段：`speak_event(pool=[...])` 增量 **2**（入口可用）
    修后：A 段增量 **0**，B/C 两控制不变。

【C 段】`mouseMoveEvent` 的拖拽判定必须是**位检测**，不许等值
    `if event.buttons() == Qt.LeftButton:` 是**等值**比较，而 Qt 的 `buttons()`
    返回**按位或**的组合值 ⇒ 拖拽中再按右键（多键鼠标/触控板/触屏）
    `LeftButton | RightButton != LeftButton` ⇒ 掉进 `else`：
    清 `_is_being_dragged`、删 `_drag_speed`、误触发悬停与抚摸检测。
    用户视角 = **拖到一半突然松脱**。修 = `if event.buttons() & Qt.LeftButton:`。
    ★ 单按左键时 `&` 与 `==` 结果相同 ⇒ **不改变**既有行为（只修组合键场景）。

段一览
------
  A 前置锚点
    A1 两个目标函数都可抽到（真源码，非凭印象）
      A2 `speak_event` 的"不给内置台词"口径**仍在**（这条口径本身不能被误删）
  B `react_to_desktop_element` 不再直写对话
    B1 ★★★ 函数体内**零** `dialogue_ui.add_dialogue/show_dialogue`（AST 调用名）
    B2 ★★★ 函数体内**零** `show_dialogue`（AST）
    B3 负控制（**恢复式变异**）：把那两行加回去 ⇒ B1/B2 必须翻面
    B4 观察**仍在上报**：`_note_desktop_observation` 真被调用（修复没有把功能关掉）
    B5 `reaction['emotion']` 仍被 `add_emotion` 真消费（没顺手删错）
  C 拖拽判定走位检测
    C1 ★★★ `mouseMoveEvent` 里出现 `buttons() & Qt.LeftButton`
    C2 ★★★ `mouseMoveEvent` 里**不再有** `buttons() == Qt.LeftButton`
    C3 负控制（**恢复式变异**）：换回 `==` ⇒ C1/C2 必须翻面
    C4 ★ 全文件**没有第二处** `buttons() == Qt.LeftButton`（同类清干净）
  D 判据自身体检
    D1 恒真防护：本套件判据里**没有** `check(..., True)` 形态
    D2 标记打印点 == 1（供 G2 计数）
    D3 被测文件在盘

★ 本套件**零 UI / 不需要显示器 / 零网络 / 零外部盘**：只读源码 + AST。
"""
import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

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
    """按名字抽**整个函数**的源码段（含 def 头）。找不到返 None。"""
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = MAIN_TEXT.split('\n')
            return '\n'.join(lines[node.lineno - 1: node.end_lineno])
    return None


def _func_body_src(name):
    """只取**函数体**（去掉 def 头），便于扫"本函数内是否调用某 API"。"""
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = MAIN_TEXT.split('\n')
            first = node.body[0].lineno
            return '\n'.join(lines[first - 1: node.end_lineno])
    return None


def _called_names(tree):
    """AST 取函数体里出现的**被调用属性名**集合（剥注释与字符串）。"""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


P('=' * 78)
P('# 第96轮b 回归锁：基础宠物两处用户可见修复')
P('=' * 78)

# ============================================================ A 前置锚点
P('')
P('--- A 前置锚点 ---')
_react_src = _func_src('react_to_desktop_element')
_speak_src = _func_src('speak_event')
_mm_src = _func_src('mouseMoveEvent')

check('A1 两个目标函数都能从真源码抽出（`react_to_desktop_element` / '
      '`mouseMoveEvent` / `speak_event`）',
      _react_src is not None and _mm_src is not None and _speak_src is not None,
      'react=%s mm=%s speak=%s'
      % (_react_src is not None, _mm_src is not None, _speak_src is not None))

check('A2 `speak_event` 的"不给内置台词"口径仍在（口径本身不许被误删）',
      _speak_src is not None and '不给内置台词' in _speak_src,
      '口径串是否命中: %s' % ('不给内置台词' in (_speak_src or '')))

# ============================================================ B 不再直写对话
P('')
P('--- B `react_to_desktop_element` 不许绕过 `speak_event` 直写对话 ---')
_react_body = _func_body_src('react_to_desktop_element') or ''

# ★★★ 判据收窄（首版过宽 ⇒ 假红）：
#   本函数体内**还有一处** `add_dialogue`（`help_messages[file_ext]`），
#   但它被 `if self.SHOW_FILE_HELP_HINTS:` 总控，而该开关第51轮起**默认 False**
#   （`main.py:9561`，注释逐字"用户要求「把他内置的对话去掉」"）⇒ **永不执行**
#   ⇒ 它**不是**本轮要守的那条路径。
#   正确判据 = **开关外**的直写对话必须为零（开关内的既有通道按原样保留）。
#   ★ 教训：这与 95 轮 D1（纯文本扫被注释误伤）是同一句话的两面 ——
#     "判据过宽 = 误报"。**改判据，不改产品**。
_SHOW_GUARD = 'SHOW_FILE_HELP_HINTS'


def _calls_outside_guard(body_src, guard_name):
    """取函数体内**不在** `if self.<guard_name>:` 块里的被调用属性名集合。

    ★ 判据实现教训（首版错了两处，都靠负控制 B3 抓出来 —— 这正是负控制的价值）：
      ① 首版用 `ast.dump(test)` 判断"是否提到 guard"，够用；
      ② 但**收集受保护调用**那段写成了 `ast.Module(body=sub.body if…else…,
         type_ignores=[])`，对非 If 子句会把调用**误算进受保护区** ⇒ B3 变异明明
         插在开关外，却被判成"开关内"⇒ 负控制假红。
      ⇒ 改为**按行号区间**扣除：先取整个函数体的全部调用及其行号，
        再把落在 guard-If 的 `lineno..end_lineno` 区间内的调用扣掉。
    """
    tree = ast.parse('def _f():\n' + body_src)
    all_named = {}      # 调用名 -> [行号]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if nm:
                all_named.setdefault(nm, []).append(node.lineno)
    guarded_spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and guard_name in ast.dump(node.test):
            guarded_spans.append((node.lineno, node.end_lineno))

    def _in_any_span(ln):
        return any(a <= ln <= b for a, b in guarded_spans)

    # ★★ 关键：**按调用点**（而不是按名字）判断，否则同一个名字在开关内/外各出现
    #   一次时会被聚合错（`add_dialogue` 正好就是这种情况：开关外不该有、开关内有）。
    out, guarded, allset = set(), set(), set()
    for nm, lns in all_named.items():
        allset.add(nm)
        for x in lns:
            (guarded if _in_any_span(x) else out).add(nm)
    return out, allset, guarded


_react_out, _react_all, _react_guarded = _calls_outside_guard(
    _react_body, _SHOW_GUARD)

check('B0 ★★ 找到受 `SHOW_FILE_HELP_HINTS` 保护的既有通道（默认 False ⇒ 永不执行），'
      '判据只在**开关外**生效',
      _SHOW_GUARD in _react_body and 'add_dialogue' in _react_guarded,
      '开关外调用=%s；受保护调用=%s' % (sorted(_react_out), sorted(_react_guarded)))
check('B0b ★★★ 该开关确实是 `= False`（若被改成 True，B0 的保护前提就不成立）',
      re.search(r'^\s*%s\s*=\s*False\s*$' % _SHOW_GUARD, MAIN_TEXT,
                re.M) is not None,
      '找不到 `%s = False`' % _SHOW_GUARD)

check('B1 ★★★ `react_to_desktop_element` **开关外零** `add_dialogue`（AST 调用名）',
      'add_dialogue' not in _react_out,
      '开关外调用名含 add_dialogue = %s' % ('add_dialogue' in _react_out))
check('B2 ★★★ `react_to_desktop_element` **开关外零** `show_dialogue`（AST 调用名）',
      'show_dialogue' not in _react_out,
      '开关外调用名含 show_dialogue = %s' % ('show_dialogue' in _react_out))

# ---- B3 负控制（恢复式变异）：把**开关外**那两行加回去 ⇒ B1/B2 必须翻面
#   ★ 插入锚点必须**真实存在**（首版锚点串与源码实际缩进不匹配 ⇒ 变异没插入 ⇒ 假红）。
#     这里改成：插在"开关外那段注释"的第一行**之前**，用 `str.replace` 报告是否真的改了。
_ANCHOR = '        # ★★★ 第96轮b 修复（口径违规 · 真机实证）'
_mut_b = _react_body.replace(
    _ANCHOR,
    '        self.dialogue_ui.add_dialogue("ralsei", "X", "y")\n'
    '        self.dialogue_ui.show_dialogue()\n' + _ANCHOR, 1)
_inserted = (_mut_b != _react_body)
_mut_out, _, _ = _calls_outside_guard(_mut_b, _SHOW_GUARD)
check('B3 负控制（恢复式变异）：在**开关外**加回 `add_dialogue`/`show_dialogue` ⇒ '
      'B1/B2 必须翻面（证明判据真有鉴别力）',
      _inserted and 'add_dialogue' in _mut_out and 'show_dialogue' in _mut_out,
      '变异是否真插入=%s；变异体开关外调用名含 add_dialogue=%s show_dialogue=%s'
      % (_inserted, 'add_dialogue' in _mut_out, 'show_dialogue' in _mut_out))

check('B4 观察**仍在上报**：`_note_desktop_observation` 真被调用（没把功能一起关掉）',
      '_note_desktop_observation' in _react_all,
      '实取调用名 = %s' % sorted(_react_all))

check('B5 `reaction[\'emotion\']` 仍被 `add_emotion` 真消费（没顺手删错）',
      'add_emotion' in _react_all and "reaction['emotion']" in _react_body,
      'add_emotion 在调用名里 = %s；reaction[emotion] 在体内 = %s'
      % ('add_emotion' in _react_all, "reaction['emotion']" in _react_body))

# ============================================================ C 拖拽位检测
P('')
P('--- C `mouseMoveEvent` 拖拽判定必须是位检测 ---')
_mm_body = _func_body_src('mouseMoveEvent') or ''


def _code_only(src):
    """★★★ 剥掉**注释与字符串字面量**，只留代码。

    为什么必须这么做（第96轮b 实测教训）：
      我在修复处写了注释，逐字引用了旧写法
      ``event.buttons() == Qt.LeftButton``。C4 用裸正则扫全文时**命中的是这句注释**
      ⇒ 假红。这与 95 轮 D1（纯文本扫被注释误伤）**是同一个坑的第二次发作**。
      ⇒ 凡"禁某写法出现"类判据，一律先剥注释/字符串再扫。
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # 片段可能不完整：退化为"只剥行注释"
        return re.sub(r'#[^\n]*', '', src)
    for node in ast.walk(tree):
        # 抹掉文档串与普通字符串常量的**内容**（保留占位，避免拼接成假代码）
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ''
    return ast.unparse(tree) if hasattr(ast, 'unparse') else re.sub(r'#[^\n]*', '', src)


_mm_code = _code_only(_mm_body)
MAIN_CODE = _code_only(MAIN_TEXT)

check('C1 ★★★ `mouseMoveEvent` 用位检测 `buttons() & Qt.LeftButton`（剥注释后）',
      re.search(r'buttons\(\)\s*&\s*Qt\.LeftButton', _mm_code) is not None)
check('C2 ★★★ `mouseMoveEvent` 不再有等值 `buttons() == Qt.LeftButton`（剥注释后）',
      re.search(r'buttons\(\)\s*==\s*Qt\.LeftButton', _mm_code) is None)

# ---- C3 负控制（恢复式变异）：换回 == ⇒ C1/C2 必须翻面
_mut_mm = re.sub(r'buttons\(\)\s*&\s*Qt\.LeftButton',
                 'buttons() == Qt.LeftButton', _mm_code, count=1)
check('C3 负控制（恢复式变异）：换回 `==` ⇒ C1/C2 必须翻面',
      (re.search(r'buttons\(\)\s*==\s*Qt\.LeftButton', _mut_mm) is not None
       and re.search(r'buttons\(\)\s*&\s*Qt\.LeftButton', _mut_mm) is None),
      '变异体：== 命中=%s，& 命中=%s'
      % (re.search(r'buttons\(\)\s*==\s*Qt\.LeftButton', _mut_mm) is not None,
         re.search(r'buttons\(\)\s*&\s*Qt\.LeftButton', _mut_mm) is not None))

# ---- C4 全文件（剥注释/字符串后）没有第二处同类
_all_eq = re.findall(r'buttons\(\)\s*==\s*Qt\.LeftButton', MAIN_CODE)
check('C4 ★ 全文件**没有第二处** `buttons() == Qt.LeftButton`（剥注释后；'
      '同类清干净）',
      len(_all_eq) == 0, '全文件（代码层）命中 %d 处' % len(_all_eq))

# ============================================================ D 判据自身体检
P('')
P('--- D 判据自身体检 ---')
_self = _rd(os.path.abspath(__file__))
_self_code = re.sub(r'u?"""[\s\S]*?"""', '', _self)   # 剥 docstring
_self_code = re.sub(r'^\s*#.*$', '', _self_code, flags=re.M)  # 剥行注释

# ★★★ 自指坑（首版踩过两次）：
#   ① 判据的**描述文本里**写了那个字面量，于是正则扫自己时把**自己的描述**匹配进来
#      ⇒ 恒红；② 用 'che'+'ck(' 拼接时**忘了转义 `(`** ⇒ `re.error: missing )`。
#   ⇒ 现在：用 `re.escape` 拼模式，且描述文本改用中文表述，源码里不存在完整串。
_TRUE_LIT = re.escape('check' + '(')
_hard_true = re.findall(_TRUE_LIT + r'\s*[^,]+,\s*True\s*[,)]', _self_code)
check('D1 ★★★ 本套件**没有**恒真判据（形如「检查名, True」的写法；恒真比不写更危险）',
      len(_hard_true) == 0, '命中 %d 处：%s' % (len(_hard_true), _hard_true[:3]))

_mark = re.findall(r"P\('合计 %d 条判据", _self_code)
check('D2 标记打印点 == 1（G2 靠这条字面量计数）', len(_mark) == 1,
      '命中 %d 处' % len(_mark))
check('D3 被测文件在盘', os.path.isfile(MAIN_PY), MAIN_PY)
check('D3b ★ 产品源码解析出的代码层确实**不含**等值拖拽判定（独立复核 C4 的观察面）',
      re.search(r'buttons\(\)\s*==\s*Qt\.LeftButton', MAIN_CODE) is None)

P('')
P('=' * 78)
P('合计 %d 条判据  PASS=%d  FAIL=%d' % (_n, _passed, _failed))
P('=' * 78)
sys.exit(1 if _failed else 0)
