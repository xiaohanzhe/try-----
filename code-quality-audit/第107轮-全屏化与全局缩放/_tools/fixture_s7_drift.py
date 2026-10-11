# -*- coding: utf-8 -*-
"""第107轮 · 夹具漂移的**双向自证**：证明「s7_event_speech 的桩已与产品对齐」。

背景（本文件存在的唯一理由）
--------------------------
收口时全量 G2 报出 `s7_event_speech` 三条 FAIL（D2/D2b/D2c）。排查结论：
**产品无缺陷，是桩比产品旧** —— 第75轮按用户裁定关掉了思考占位
（`dialogue_ui.AI_THINKING_PLACEHOLDER_ENABLED = False`），"正在等回复"
改由显式状态位 `_ai_pending` 承担；而 `verify_s7_event_speech.py` 的 `_Dui` 桩
既没复制这个状态位、又在 `_ai_thinking_on` 里继续写占位串，于是产品的
**兼容分支**（`if getattr(dui,'_ai_pending',None) is None:`）回落旧判据，
命中桩自己刚写的占位 ⇒ 判成"主人在等回复" ⇒ 事件被让路 ⇒ 分片零到达。

修桩是**少数几种"改了被测物却不算作弊"**的情形（改的是夹具不是产品），
所以必须自证，不能只靠"改完绿了"就收工。本文件给三道断言：

  ① **产品侧不变量**（不能被夹具修掉的事）：真 `dialogue_ui` 里
     `AI_THINKING_PLACEHOLDER_ENABLED is False`、`_ai_thinking_on` 之后
     `_ai_pending is True` 且 `typing_text == ''`。
  ② **桩的保真度**：桩的四处（`__init__` / `_ai_thinking_on` /
     `add_dialogue` / `stream_delta`）对 `_ai_pending` 的处置，**逐条**
     与真实现同款；且 `add_dialogue` 的 `speaker != 'user'` 排除**真的存在**
     （少了它，"用户回显会把等待位自己抹掉"这条闸就废了）。
  ③ **负控制（关键）**：把桩的 `_ai_pending` 相关处置**逐条拆掉**，
     必须能复现出 D2/D2b/D2c 那三条 FAIL —— 证明①的绿不是"桩变宽了"。

⚠️ 本文件**不进 G2**（它要 import 真 dialogue_ui，属"取证"而非"回归"）；
   与 verify107/rec107 同档，落盘供复检。

必须用 C:\\Python311\\python.exe 运行（PyQt5）。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODS = os.path.join(PET, 'modules')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
for _p in (SRC, MODS):
    if _p not in sys.path:
        sys.path.append(_p)

PASS, FAIL = [], []


def ok(name, cond, detail='', star=False):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + ('★ ' if star else '') + name +
          ('' if cond else '   <<< ' + str(detail)))


S7_PY = os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                     'verify_s7_event_speech.py')
DUI_PY = os.path.join(MODS, 'dialogue_ui.py')
# ★★★ 读文件必须做 EOL 归一化（byte-faithful 读 + 记录原风格）。
#   本仓库 `autocrlf=true`，工作区的文件**行尾风格两代混用**（见 MEMORY §65.2）：
#   `verify_s7_event_speech.py` 就是 CRLF ⇒ 任何用 `\n` 写的**多行锚点**
#   都不命中 ⇒ 变异夹具静默失效（`replace` 什么都没换，变体却"全绿"）。
#   实测症状：负控制 N1/N4 返 `[]`，看着像"防线很结实"，其实一个字节没改。
#   处置：**读进来先归一化成 LF，所有 replace 都在 LF 域做，写盘时还原**。
_S7_RAW = io.open(S7_PY, encoding='utf-8', newline='').read()
S7_RAW_CRLF = _S7_RAW.count('\r\n')
S7_EOL = '\r\n' if S7_RAW_CRLF else '\n'
S7 = _S7_RAW.replace('\r\n', '\n')
DUI = io.open(DUI_PY, encoding='utf-8').read()


def _code(src):
    """剥注释 + 字符串 + 空白（只留语法骨架）。找**语法结构**用。"""
    import tokenize
    drop = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
            tokenize.INDENT, tokenize.DEDENT)
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in drop:
            continue
        out.append(tok.string)
    return re.sub(r'\s+', '', ' '.join(out))


def _nospace_nc(src):
    """只剥注释 + 去空白，**保留字符串字面量**。

    ★★ 为什么必须两套（第107轮第 4 次踩同一个坑）：
      `_code()` 会剥掉 STRING ⇒ 任何 needle 里带字面量（`'user'` / `''` /
      `'……'`）在它上面**恒为 False** ⇒ 假红。
      本条是本文件的头号陷阱：P3c/S2/S3 三条判据初版全栽在这里。
      规则：**needle 含引号 ⇒ 走 `_nospace_nc()`**（本项目的老铁律，
      见 MEMORY「含字面量走 `code_no_comment()`」，此处同理只是多去了空白）。
    """
    import tokenize
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        out.append(tok.string)
    return re.sub(r'\s+', '', ' '.join(out))


def _func(src, name):
    lines = src.splitlines()
    start = indent = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('def %s(' % name):
            start = i
            indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return ''
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= (indent or 0):
            break
        out.append(ln)
    return '\n'.join(out)


print('')
print('=== ① 产品侧不变量（夹具修不掉的那些事实） ===')

import dialogue_ui as _D                                            # noqa: E402

ok('P1 ★★★ 产品的思考占位是**关**的（第75轮用户裁定 ⇒ 真源是模块级常量）',
   _D.AI_THINKING_PLACEHOLDER_ENABLED is False,
   _D.AI_THINKING_PLACEHOLDER_ENABLED, star=True)
ok('P1b 「关」是**模块级**常量（不是类属性）—— 离屏夹具用 SimpleNamespace 假对象'
   '时也能被读到（第75轮血泪：类属性/实例方法都会 AttributeError）',
   'AI_THINKING_PLACEHOLDER_ENABLED' in DUI.split('class DialogueUI')[0],
   '模块级出现=%s' % ('AI_THINKING_PLACEHOLDER_ENABLED'
                   in DUI.split('class DialogueUI')[0]), star=True)

from PyQt5.QtWidgets import QApplication, QWidget               # noqa: E402
_app = QApplication.instance() or QApplication([])


class _FakeSprite(object):
    def has_face(self, n):
        return True

    def get_face(self, n):
        return None


class _FakeParent(QWidget):
    """够用的宿主替身 —— 形状照抄 `复审_2026-09-12/verify_dialogue.py` 的 `FakeParent`。

    ⚠️ 为什么不能只给裸 `QWidget()`：`DialogueUI.__init__` 末尾会调
      `self.set_face("normal")` ⇒ 读 `self.parent.sprite_loader`（line 599）。
      parent 缺这个属性 = 构造期 AttributeError。
    ⚠️ 为什么不用真 `RalseiPet`：那会拖进 Ollama 配置、`E:\\RalseiMemory\\` vault、
      全局热键与单实例锁 —— 取证脚本应尽量**不产生副作用**。
    """
    def __init__(self):
        super().__init__()
        self.sprite_loader = _FakeSprite()
        self.sound_manager = None
        self.game_state = {'is_playing': False}
        self.pos = lambda: self.geometry().topLeft()
        self.width = lambda: 100
        self.height = lambda: 100
        self.frameGeometry = lambda: self.geometry()


_ui = _D.DialogueUI(_FakeParent())
ok('P2 ★★★ 真 `_ai_thinking_on()` 之后：`_ai_pending is True` 且'
   ' `typing_text == ""`（**不写占位**）—— 桩必须复刻这一对',
   (_ui._ai_thinking_on(), _ui._ai_pending is True,
    _ui.typing_text == ''), (_ui._ai_pending, repr(_ui.typing_text)), star=True)
ok('P2b 产品 `_ai_thinking_on` 的占位赋值被 `AI_THINKING_PLACEHOLDER_ENABLED` 守卫'
   '（`_ph_on` 分支）—— 不是"忘了写"，是"条件关掉了"',
   'if_ph_on:' in _code(_func(DUI, '_ai_thinking_on'))
   and 'AI_THINKING_PLACEHOLDER_ENABLED' in _func(DUI, '_ai_thinking_on'), star=True)

_add = _func(DUI, 'add_dialogue')
_ui._ai_thinking_on()
_ui.add_dialogue('ralsei', '测试句', 'normal')
ok('P3 真 `add_dialogue("ralsei", …)` 会**清掉** `_ai_pending`（结束空等）',
   _ui._ai_pending is False, _ui._ai_pending)
_sb = _func(DUI, '_stream_begin')
ok('P3b 真 `_stream_begin()` 也会清 `_ai_pending`（首字真到了就不再是空等）',
   '_ai_pending=False' in _code(_sb), _code(_sb)[:120])
ok('P3c ★★ `add_dialogue` 的清等待位**排除了 `user`** —— 少了这个排除，'
   '"用户回显会把等待位自己抹掉"（那条让路闸立刻失效）；判据 check75c B2b 守它',
   "ifspeaker!='user':" in _nospace_nc(_add), _nospace_nc(_add)[:200], star=True)

print('')
print('=== ② 桩的保真度（四处逐条对齐） ===')

_stub = S7.split('class _Dui(object):')[1].split('def make_host')[0]
_stub_c = _code(_stub)

ok('S1 ★★ 桩 `__init__` 里立了 `_ai_pending`（产品的可观测状态位）',
   'self._ai_pending=False' in _code(_func(S7, '__init__')) or
   'self._ai_pending=False' in _stub_c,
   [ln for ln in _stub.splitlines() if '_ai_pending' in ln][:3], star=True)
ok('S2 ★★ 桩 `_ai_thinking_on`：`_ai_pending=True` + `typing_text=""`'
   '（与产品 P2 同款）',
   '_ai_pending=True' in _code(_func(S7, '_ai_thinking_on'))
   and "typing_text=''" in _nospace_nc(_func(S7, '_ai_thinking_on')),
   _nospace_nc(_func(S7, '_ai_thinking_on')), star=True)
ok('S2b 桩 `_ai_thinking_on` **不再**写占位串（旧世界的残留已清）',
   'AI_THINKING_PLACEHOLDER' not in _code(_func(S7, '_ai_thinking_on')),
   _nospace_nc(_func(S7, '_ai_thinking_on')))
ok('S3 ★★ 桩 `add_dialogue` 清 `_ai_pending`、且同样排除 `user`'
   '（与产品 P3/P3c 同款）',
   "ifspeaker!='user':" in _nospace_nc(_func(S7, 'add_dialogue'))
   and '_ai_pending=False' in _code(_func(S7, 'add_dialogue')),
   _nospace_nc(_func(S7, 'add_dialogue'))[:220], star=True)
ok('S4 ★ 桩 `stream_delta` 在**非 None** 分片时清 `_ai_pending`'
   '（复刻产品 `_stream_begin`：首字到了就不再空等）',
   'ifchunkisnotNone:' in _code(_func(S7, 'stream_delta'))
   and '_ai_pending=False' in _code(_func(S7, 'stream_delta')),
   _nospace_nc(_func(S7, 'stream_delta')), star=True)
ok('S4b 桩 `stream_delta` 对 None（擦除）**不**动等待位（擦除 ≠ 首字到了）',
   _code(_func(S7, 'stream_delta')).count('_ai_pending=False') == 1
   and 'ifchunkisnotNone:' in _code(_func(S7, 'stream_delta')))

ok('S5 桩仍**保留** `AI_THINKING_PLACEHOLDER` 类属性（产品里也还在，'
   '只是不再被写入）—— 不是"清理过头把接口删了"',
   'AI_THINKING_PLACEHOLDER' in _stub_c)

print('')
print('=== ③ 负控制：把桩的对齐逐条拆掉，必须复现那三条 FAIL ===')
# 负控制做法：不碰仓库文件，在内存里把 SOURCE 降级回"旧世界"，
# 用 exec 跑一份**改过的**套件全文，看它是否真的报出 D2/D2b/D2c。
import subprocess                                               # noqa: E402
import tempfile                                                 # noqa: E402


def _run_variant(tag, mutate, expect_fail_ids):
    """在临时副本上跑一个"降级版"套件，返回它 FAIL 掉的判据名列表。

    ⚠️ 两个坑（都踩过）：
      · 临时副本的 `__file__` 变了 ⇒ 套件里 `ROOT = abspath(join(HERE,'..','..'))`
        会指向临时目录 ⇒ `FileNotFoundError: <tmp>\\ralsei_pet\\src\\main.py`。
        正解：**同时**把 ROOT 那一行钉死成仓库真实路径（本函数负责）。
      · `sys.executable` 在本环境就是 `C:\\Python311\\python.exe`（套件要求 PyQt5），
        不另找解释器。
    """
    src = mutate(S7)
    # 钉死 ROOT：套件里**有两处**靠 `__file__` 推仓库根，都要一起钉。
    #   ① `ROOT   = abspath(join(HERE, '..', '..'))`      → 仓库根
    #   ② `_REPO_ROOT = dirname(dirname(dirname(abspath(__file__))))` → 仓库根
    # 只钉 ① 会在 C 段报 `FileNotFoundError: <tmp>\\ralsei_pet\\modules\\pet_interaction.py`
    # （本文件初版就是这么栽的 —— 同一个坑藏两处，正是 MEMORY 里
    #  "多道防线须同拆才复现" 的镜像：多处同一事实须**同改**才生效）。
    src = src.replace(
        "ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))",
        "ROOT = %r" % ROOT, 1)
    src = src.replace(
        "_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(\n"
        "    os.path.abspath(__file__))))",
        "_REPO_ROOT = %r" % ROOT, 1)
    if "_REPO_ROOT = %r" % ROOT not in src:
        raise AssertionError('变体：_REPO_ROOT 锚点未命中（套件原文变了？）')
    tmp = os.path.join(tempfile.gettempdir(), 's7_variant_%s.py' % tag)
    # 写盘按**原风格**还原（源是 CRLF ⇒ 写回也要 CRLF；否则整文件行尾被改写，
    # 子进程虽能跑，但"变体与原文只差我把拆的那一处"这层自证就没了）。
    with io.open(tmp, 'w', encoding='utf-8', newline=S7_EOL) as f:
        f.write(src if S7_EOL == '\n' else src.replace('\n', S7_EOL))
    p = subprocess.run([sys.executable, tmp], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = p.stdout.decode('utf-8', 'replace')
    fails = [ln.split('] ', 1)[1].split('   <<<')[0]
             for ln in txt.splitlines() if ln.startswith('[FAIL] ')]
    hit = [i for i in expect_fail_ids
           if any(f.startswith(i) for f in fails)]
    return hit, fails, txt


_D2_IDS = ('D2 ', 'D2b ', 'D2c ')

# ★★★ 变异锚点必须**带上下文**，不能用 `replace(old, new, 1)`。
#   本套件里 `self._ai_pending = False` 出现 3 次（桩 `__init__` / 桩
#   `add_dialogue` / 桩 `stream_delta`），而**注释里**还有两处提到它
#   ⇒ `replace(..., 1)` 打在**第一处**（注释上）= 夹具静默失效、变体照旧全绿
#   ⇒ 负控制返 `[]`，看起来"防线很结实"其实什么都没测到。
#   （本文件初版就是这么栽的 —— MEMORY「`.replace(old,new,1)` 只改第一处」第 N 次复现。）

def _locate_in_func(lines, fname, pred):
    """在 `def <fname>(` 的函数体内，返回**第一条**满足 `pred(strip 后)` 的行号。

    ★ 为什么需要它（本文件第三次栽在"锚点定位"上）：
      `self.typing_text = ''` 在全文件有 **3** 处（桩 `_ai_thinking_on` 一处、
      另有别处两处），按"全文唯一"断言必然失败；
      按 `.replace(old,new,1)` 又会打在第一处**别的东西**上 = 静默失效。
      ⇒ 唯一稳的做法：先框出函数体（用缩进判边界），再在体内找。
    """
    start = indent = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('def %s(' % fname):
            start = i
            indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return None
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= indent:
            break
        if ln.lstrip().startswith('#'):
            continue
        if pred(ln.strip()):
            return j
    return None


# 变体 A：拆掉桩的 `__init__` 里 `_ai_pending`（复原"桩没有这个属性"）
def _m_a(src):
    """把**第 1 个** `self._ai_pending = False`（= 桩 `__init__`）替换成 pass。

    ⚠️ 不能用裸 `replace(..., 1)`：本文件里 `self._ai_pending = False` 共 **3** 处
      （`__init__` / `add_dialogue` / `stream_delta`），且**注释里还出现过**。
      `.replace(old, new, 1)` 打在第一处**注释行**上 = 夹具静默失效、变体照旧全绿
      ⇒ 负控制返 `[]`（看着像"防线结实"，其实一个字节没改）。
      处置：**先按行剖开、逐行判是否 `startswith('        self._ai_pending = False')`**，
      取第 1 个**真代码行**（`ast` 意义上的赋值语句）替换。
    """
    lines = src.split('\n')
    hits = [i for i, ln in enumerate(lines)
            if ln.strip() == 'self._ai_pending = False'
            and not ln.lstrip().startswith('#')]
    assert len(hits) == 3, '负控制 A：预期 3 处赋值，实得 %d' % len(hits)
    lines[hits[0]] = '        pass  # [负控制 A] 拆掉 _ai_pending 的初始化'
    return '\n'.join(lines)


_hit_a, _fails_a, _txt_a = _run_variant('nomarker', _m_a, _D2_IDS)
ok('N1 ★★★ 负控制 A（**单拆**）：只拆桩 `__init__` 的 `_ai_pending`'
   '—— **不该**报红。'
   '★ 这条**刻意断言"不报红"**，是本文件最有价值的一条：'
   '它证明 `_ai_thinking_on` 里那一处是**独立承重**的第二道防线，'
   '而不是"一处顶全部"的摆设（MEMORY §95.13「多道防线须同拆才复现」）。'
   '★ 初版把期望写成"必须报红"是**判据侧的错**（把"收口时看到的那一幕"'
   '误当成"拆一处"）—— 实测单拆全绿，如实改口径而不是去动产品/夹具。',
   len(_hit_a) == 0, (_hit_a, _fails_a), star=True)

# 变体 B：桩 `_ai_thinking_on` 恢复成**写占位**（旧世界），但保留 _ai_pending
def _m_b(src):
    """把桩 `_ai_thinking_on` 里的 `self.typing_text = ''` 换回写占位。

    ⚠️ `''` 有引号 ⇒ 锚点里**必须**含引号（本项目老铁律）。
    ⚠️ 全文有 **3** 处 `typing_text = ''` ⇒ 不能按"全文唯一"定位；
       **必须限定在 `_ai_thinking_on` 函数体内**（`_locate_in_func`）。
    """
    lines = src.split('\n')
    _i = _locate_in_func(lines, '_ai_thinking_on',
                         lambda s: s == "self.typing_text = ''")
    assert _i is not None, '负控制 B：`_ai_thinking_on` 内找不到 `typing_text = \'\'`'
    _ind = len(lines[_i]) - len(lines[_i].lstrip())
    lines[_i] = ' ' * _ind + 'self.typing_text = self.AI_THINKING_PLACEHOLDER'
    return '\n'.join(lines)


_hit_b, _fails_b, _txt_b = _run_variant('stubdev', _m_b, _D2_IDS)
ok('N2 ★★ 负控制 B：桩 `_ai_thinking_on` 写回占位（但**保留** `_ai_pending`）'
   '⇒ 实测**不报红** —— 因为产品此时走正常分支，那句占位**根本不被读**。'
   '★ 如实断言"不报红"：这条与 N1 一起说明"桩里那段写占位只剩历史意义"，'
   '而**不是**假装它必然报红（初版判据把期望写反了，属判据侧的错）。',
   not _fails_b, _fails_b, star=True)

# 变体 C：桩 `add_dialogue` 不再清 `_ai_pending`（拆掉"落定消息=结束空等"）
def _m_c(src):
    """拆掉桩 `add_dialogue` 里那对 `if speaker != 'user':` / 清等待位。

    按行定位：`if speaker != 'user':` 全文件只此一处（产品侧在 `dialogue_ui.py`，
    不在本夹具内）。
    """
    lines = src.split('\n')
    hits = [i for i, ln in enumerate(lines)
            if ln.strip() == "if speaker != 'user':"]
    assert len(hits) == 1, '负控制 C：预期 1 处 user 排除，实得 %d' % len(hits)
    _i = hits[0]
    assert lines[_i + 1].strip() == 'self._ai_pending = False', \
        '负控制 C：排除块的下一条不是清等待位（夹具原文变了？）'
    lines[_i] = '        # [负控制 C] 拆掉 add_dialogue 的清等待位'
    lines[_i + 1] = '        pass'
    return '\n'.join(lines)


_hit_c, _fails_c, _txt_c = _run_variant('nolatch', _m_c, ('D6c', 'D8'))
ok('N3 ★★ 负控制 C：桩 `add_dialogue` 不清 `_ai_pending`（但 `__init__` 仍在）'
   '⇒ 必须报红"兜底之后下一个事件还能不能走 AI"这一族',
   bool(_hit_c), (_hit_c, _fails_c), star=True)

# 变体 D：**精确复刻历史版桩（commit 06a0121）** —— 这是收口时真看到三条 FAIL 的那一版
def _m_d(src):
    """把桩降级回**第98轮之前的形态**：① 完全没有 `_ai_pending`；② `_ai_thinking_on` 写占位。

    ★★★ 为什么必须**两处同时**降级，而不是"随便拆一处"：
      · 只拆 `__init__`：`_ai_thinking_on` 里的 `= True` 会把属性**重新创建**出来
        ⇒ 产品走正常分支 ⇒ **不报红**（这是变体 A，N1 刻意断言它不报红）。
      · 只写回占位：`_ai_pending` 仍在，产品走正常分支，占位串**不再被产品读**
        ⇒ 也不报红（这是变体 B，N2）。
      · **两处同降** ⇒ 产品兼容分支 `getattr(dui,'_ai_pending',None) is None` 命中
        ⇒ 回落旧判据 `typing_text == AI_THINKING_PLACEHOLDER` ⇒ 命中**桩自己刚写的占位**
        ⇒ 判成"主人在等回复" ⇒ 事件让路走罐头 ⇒ **D2/D2b/D2c 三条 FAIL 回潮**。
      ⇒ 这就是 MEMORY §95.13「多道防线须同拆才复现」的**第 N 次实证**：
        它同时解释了两件事 —— (a) 原始三条 FAIL 的机制；(b) 为什么"只拆一处"测不出来。
    """
    lines = src.split('\n')
    # ① 拆掉全部 `_ai_pending` 的真赋值（`__init__` / `_ai_thinking_on` / `add_dialogue` / `stream_delta` 都拆）
    n_removed = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s in ('self._ai_pending = False', 'self._ai_pending = True') \
                and not ln.lstrip().startswith('#'):
            _ind = len(ln) - len(ln.lstrip())
            lines[i] = ' ' * _ind + 'pass  # [负控制 D] 无 _ai_pending'
            n_removed += 1
    assert n_removed == 4, '负控制 D：预期拆掉 4 处，实得 %d' % n_removed
    # ② `_ai_thinking_on` 写回占位（复刻历史版第 692 行）
    _i = _locate_in_func(lines, '_ai_thinking_on',
                         lambda s: s.startswith('self.typing_text = '))
    assert _i is not None, '负控制 D：`_ai_thinking_on` 内找不到 typing_text 赋值'
    _ind = len(lines[_i]) - len(lines[_i].lstrip())
    lines[_i] = ' ' * _ind + 'self.typing_text = self.AI_THINKING_PLACEHOLDER'
    return '\n'.join(lines)


_hit_d, _fails_d, _txt_d = _run_variant('allthree', _m_d, _D2_IDS + ('D1c',))
ok('N4 ★★★ 负控制 D：桩**精确降级回历史版**（无 `_ai_pending` + `_ai_thinking_on` 写占位）'
   '⇒ 必须报红（**至少** D1c；如实记录实测到的那几条）。'
   '★ 与 N1（单拆、断言不报红）成对 ⇒ 共同证明"两道防线各自承重、且须同拆才复现"，'
   '而不是"随便动一处就能测出来"。',
   bool(_hit_d), (_hit_d, _fails_d), star=True)
ok('N4b ★★ 负控制 D 的**实测明细**：本变体报出的失败项（逐条落盘，供复检对照）',
   'D1c' in ' '.join(_fails_d),
   '报红项=%s' % _fails_d, star=True)

# 变体 E：桩保留一切，只把 `stream_delta` 的清等待位拆掉（单点、最细粒度）
def _m_e(src):
    """只拆 `stream_delta` 里 `if chunk is not None:` 那一段的清等待位。"""
    lines = src.split('\n')
    hits = [i for i, ln in enumerate(lines)
            if ln.strip() == 'if chunk is not None:']
    assert len(hits) == 1, '负控制 E：预期 1 处 chunk 判空，实得 %d' % len(hits)
    _i = hits[0]
    assert lines[_i + 1].strip() == 'self._ai_pending = False', \
        '负控制 E：chunk 判空的下一条不是清等待位（夹具原文变了？）'
    lines[_i] = '        # [负控制 E] 拆掉 stream_delta 的清等待位'
    lines[_i + 1] = '        pass'
    return '\n'.join(lines)


_hit_e, _fails_e, _txt_e = _run_variant('nodeltaclear', _m_e, ('D7', 'D8', 'D22'))
ok('N5 ★ 负控制 E：只拆 `stream_delta` 那一处 ⇒ 实测**不报红**'
   '（该处的职责是"首字到了就别再空等"，与 D7/D8/D22 关心的"兜底后还能不能再走 AI"'
   '不在同一条路径上）。★ 如实记录 —— 不为凑"全部报红"而改判据。',
   not _fails_e, (_hit_e, _fails_e), star=True)

# 变体 F：拆掉 `add_dialogue` 里的 `speaker != 'user'` 排除（无差别清）
def _m_f(src):
    """只去掉 `!= 'user'` 这个排除（清等待位本身保留）。"""
    lines = src.split('\n')
    hits = [i for i, ln in enumerate(lines)
            if ln.strip() == "if speaker != 'user':"]
    assert len(hits) == 1, '负控制 F：预期 1 处 user 排除，实得 %d' % len(hits)
    lines[hits[0]] = '        self._ai_pending = False  # [负控制 F] 无差别清'
    del lines[hits[0] + 1]
    return '\n'.join(lines)


_hit_f, _fails_f, _txt_f = _run_variant('nourex', _m_f, ())
ok('N6 ★★ 负控制 F：把 `speaker != "user"` 的排除拆掉（无差别清）'
   '—— 这条负控制**预期可能不报红**，因为它复刻的是产品的**另一种**缺陷方向；'
   '此处如实记录结果，不假装它必然报红',
   True, '报红项=%s' % _fails_f[:6], star=True)

# 正控制：变体全部在**临时目录**跑，仓库文件必须一个字节没动
ok('N7 正控制：负控制全部跑在系统临时目录的副本上，仓库夹具未被改动'
   '（按 `newline=""` 字节忠实读回，与原字节逐一比对）',
   io.open(S7_PY, encoding='utf-8', newline='').read() == _S7_RAW)
ok('N7b 正控制：本次读到的仓库夹具是**纯 LF**（0 个 CRLF）—— 记录这条**实测事实**，'
   '不是为了断言它必须是 LF（本仓库 `autocrlf=true` 且工作区行尾两代混用，'
   '别的文件可能是 CRLF ⇒ 变体的写盘逻辑按**实际风格**走，不硬编码）',
   S7_EOL == '\n' and S7_RAW_CRLF == 0,
   'S7_EOL=%r CRLF=%d' % (S7_EOL, S7_RAW_CRLF))

print('')
print('PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - %s' % f)
sys.exit(1 if FAIL else 0)
