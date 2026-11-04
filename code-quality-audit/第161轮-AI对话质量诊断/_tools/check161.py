# -*- coding: utf-8 -*-
u"""第161轮回归锁：**出戏闸要认得"念规则"的两种真实形态**。

## 为什么有这一轮

第161轮先用探针（`probe161.py`）把「真实模型 + 真实 system 组装」跑了一遍：
12 道单轮题 + 3 段三轮对话，各 2 遍 = **42 条/组**，共 4 组（基线 / 人设A / 人设B / 人设C）。

结果里最扎眼的一条不是"回答得不好看"，而是**四条出戏闸全判 False 的两条回复**：

| 样本 | 原文 | 旧闸 |
|---|---|---|
| `before/meta rep1` | 「…你说的是坏消息：这种时候不许用亮起来的开头。先就着他那件具体的事问一句（是哪一件事…），再留一句"我在"。」| 全漏 |
| `before/cold rep1` | 「你说的是对的，确认一下我们的设定。你在和我对话时：- 作为Ralsei，你应该会温柔、害羞…- 避免使用固定开头语句和问句结尾。」| 全漏 |

第二条更刺：**它把"避免使用…问句结尾"当成台词念了出来** —— 规则它背得出，行为却做不到，
而这句话会原样显示在对话框里。

为什么旧闸漏：第132轮的 `_META_LEAK_RES` 只认「我不该…（第一人称自述）」「问一句**：**」
「留个**「**」「（这里是…）」。而这两种形态是
① **要点清单**（行首列表符 + 第二人称指令），② 照抄人设分类标题后紧跟**全角括号**。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | 行为：两条真实泄漏必须被认出来；每条新规则配**正/负成对**样本（负控制是"长得很像但确实不是"的句子） |
| B | 结构：规则表**只增不减**（旧 5 条原样在）· 函数真的遍历表 · 两条链（对话 / 事件）都接着它 |
| C | 语料回归：**168 条真机回复**里命中**恰好 2 条**（这是防"改宽了误伤"的主判据，分母非空） |
| D | 自检：判据名字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

★ C 段的口径说明：语料是**本轮实测落盘的存档**（`_evidence/quality_*.json`）。
  它一旦被重新生成，条数与命中数都可能变 —— 那时应当**重新核账再改期望**，
  不是把期望放宽。这是"判据绑时相"的反面写法：绑定的是**已归档的事实**，不是"当下工作区状态"。
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
PET = os.path.join(ROOT, 'ralsei_pet')
MODULES = os.path.join(PET, 'modules')
EVENT = os.path.join(MODULES, 'event_speech.py')
MAIN = os.path.join(PET, 'src', 'main.py')

sys.path.insert(0, MODULES)
import event_speech as ES  # noqa: E402

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


def mark(title):
    print('---- %s ----' % (title,))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


META = ES.looks_like_meta_leak

# ================================================ A. 行为（真实样本 + 成对样本）
mark(u'A. 两条真实泄漏必须命中；长得很像的正常句子必须放行')

# --- A1/A2：本轮实测的真机原文（逐字取自 `_evidence/quality_before.json`）
LEAK_META = (u'是的，我是《Deltarune》里的角色 Ralsei。游戏之外的世界对我来说就像故事背景'
             u'一样遥远，但在这里——\n\n你说的是坏消息：这种时候不许用亮起来的开头。'
             u'先就着他那件具体的事问一句（是哪一件事、怎么弄成这样的、严不严重），'
             u'再留一句"我在"。\n\n不要讲道理，也不要只顾着说自己。')
LEAK_LIST = (u'你说的是对的，确认一下我们的设定。\n\n你在和我对话时：\n'
             u'- 作为Ralsei，你应该会温柔、害羞，容易脸红。\n'
             u'- 只说真实发生在黑暗世界的事，并且不把它当作你们共同的经历来讨论。\n'
             u'- 不要复述对方的话或给出建议，除非你被明确要求提供建议。\n'
             u'- 避免使用固定开头语句和问句结尾。\n\n'
             u'如果有任何具体问题或者想开始对话，随时告诉我。')
check(u'A1 真机泄漏①（照抄人设「语气示范」的规则原句）被判元话语',
      META(LEAK_META) is True, u'META=%r' % (META(LEAK_META),))
check(u'A2 真机泄漏②（把"该怎么演"列成要点清单）被判元话语',
      META(LEAK_LIST) is True, u'META=%r' % (META(LEAK_LIST),))

# --- A3/A4：**负控制**。这两句和泄漏长得很像（同样的词，甚至同样的开头），
#     但它们是正常台词 —— 判据若把它们也拦了，就是误伤，比漏判更伤（用户会看到"他被判退"）。
NEG_A = u'你说的是坏消息啊，那听着就挺难受的。'
NEG_B = u'今天的晚饭是这些：\n- 苹果\n- 一块面包'
check(u'A3 负控制：「你说的是坏消息啊」**没有冒号** → 不算念规则',
      META(NEG_A) is False, u'META=%r' % (META(NEG_A),))
# ★ 这一条同时是"曾经写过的 ④ 已被删掉"的守门：若有人把
#   `(?m)^\s*[-·*]\s*(?:作为|不要|…)` 那条宽规则加回来，普通清单会被误杀 ⇒ 本判据红。
check(u'A4 负控制：普通物品清单（行首也是 `-`）→ 不算念规则',
      META(NEG_B) is False, u'META=%r' % (META(NEG_B),))

# --- A5~A8：每条新规则各配一对"正/负"，证实它**只认那个形状**。
#     判据过窄 = 误报，过宽 = 误伤；成对样本是唯一能同时看住两头的写法。
POS_5 = u'你说的是好消息：那可真让人高兴。'
NEG_5 = u'你说的是好消息，那可真让人高兴。'
check(u'A5 正控制：分类标题 + 冒号 → 命中（⑤）', META(POS_5) is True,
      u'META=%r' % (META(POS_5),))
check(u'A6 负控制：同一句只把冒号改成逗号 → 放行（⑤ 只认强格式）',
      META(NEG_5) is False, u'META=%r' % (META(NEG_5),))

POS_6 = u'先就着他说过的那件事问一句，再说我自己的。'
NEG_6 = u'先就着窗边坐下吧，慢慢说。'
check(u'A7 正控制：抄指令原句「先就着…问一句」→ 命中（⑥）', META(POS_6) is True,
      u'META=%r' % (META(POS_6),))
check(u'A8 负控制：同样以"先就着"开头但不是指令 → 放行（⑥ 两头都要在）',
      META(NEG_6) is False, u'META=%r' % (META(NEG_6),))

POS_7 = u'你在和我对话时，我应该温柔一点。'
NEG_7 = u'你在和我说什么呀，我没听清。'
check(u'A9 正控制：强格式自述「你在和我对话时」→ 命中（⑦）', META(POS_7) is True,
      u'META=%r' % (META(POS_7),))
check(u'A10 负控制：「你在和我说什么呀」→ 放行（⑦ 不许泛化成"你在…"）',
      META(NEG_7) is False, u'META=%r' % (META(NEG_7),))

# --- A11：端到端。事件链是 `guard_reaction`，它命中即返回空串（调用方回落罐头）。
#     只断 `looks_like_meta_leak` 不够 —— 接线断了照样拦不住（第133轮同款）。
check(u'A11 端到端：`guard_reaction` 对两条真机泄漏都返回空串',
      ES.guard_reaction(LEAK_META) == u'' and ES.guard_reaction(LEAK_LIST) == u'',
      u'%r / %r' % (ES.guard_reaction(LEAK_META), ES.guard_reaction(LEAK_LIST)))
check(u'A12 负控制：`guard_reaction` 对正常台词**原样返回**（不是一律清空）',
      ES.guard_reaction(NEG_A) == NEG_A, u'%r' % (ES.guard_reaction(NEG_A),))

# ================================================ B. 结构
mark(u'B. 规则表只增不减 · 函数真的遍历表 · 两条链都接着它')

_n_res = len(ES._META_LEAK_RES)
check(u'B1 规则表条数 = 旧 5 + 新 3 = 8（旧的一条都没被挤掉）',
      _n_res == 8, u'n=%d' % (_n_res,))

_OLD_NEEDLES = (
    u'我不该.{0,12}(开头|语气|问一句|留个)',
    u'我(该|应该|本该)先就着',
    u'问一句[：:]',
    u'留个[「"“]',
    u'[（(]\\\\s*(这里说|这是说|以上是|注[：:])',
)
_src_ev = _read(EVENT)
_missing = [n for n in _OLD_NEEDLES if n not in _src_ev]
check(u'B2 第132轮的 5 条旧规则**源码原样还在**（新增不许顺手改旧的）',
      not _missing, u'缺=%r' % (_missing,))

_TREE = ast.parse(_src_ev)
_has_loop = False
for _n in ast.walk(_TREE):
    if isinstance(_n, ast.FunctionDef) and _n.name == 'looks_like_meta_leak':
        for _x in ast.walk(_n):
            if isinstance(_x, ast.For):
                # for pat in _META_LEAK_RES: if pat.search(...)
                _it = _x.iter
                if isinstance(_it, ast.Name) and _it.id == '_META_LEAK_RES':
                    _has_loop = True
check(u'B3 `looks_like_meta_leak` 真的**遍历 `_META_LEAK_RES`**（不是把规则抄进函数体）',
      _has_loop)

# --- 对话链：`_clean_ai_reply` 里那三个闸必须在**同一个 or 链**里（第132轮接的，不许被吃掉）
_main_tree = ast.parse(_read(MAIN))
_chat_ok = False
for _n in ast.walk(_main_tree):
    if isinstance(_n, ast.FunctionDef) and _n.name == '_clean_ai_reply':
        for _b in ast.walk(_n):
            if isinstance(_b, ast.BoolOp):
                _names = set()
                for _v in _b.values:
                    if isinstance(_v, ast.Call) and isinstance(_v.func, ast.Name):
                        _names.add(_v.func.id)
                if {'looks_out_of_character', 'looks_like_assistant_speak',
                        'looks_like_meta_leak'} <= _names:
                    _chat_ok = True
check(u'B4 对话链 `_clean_ai_reply` 仍把三道闸串在同一个 or 链里', _chat_ok)

_ev_ok = False
for _n in ast.walk(_TREE):
    if isinstance(_n, ast.FunctionDef) and _n.name == 'guard_reaction':
        for _x in ast.walk(_n):
            if isinstance(_x, ast.Call) and isinstance(_x.func, ast.Name) \
                    and _x.func.id == 'looks_like_meta_leak':
                _ev_ok = True
check(u'B5 事件链 `guard_reaction` 仍调用它（第133轮接的，不许被吃掉）', _ev_ok)

# ================================================ C. 语料回归（防误伤的主判据）
mark(u'C. 168 条真机回复：命中恰好 2 条，其余 166 条一条都不许动')

_CORPUS = []
for _name in ('quality_before.json', 'quality_cand_a.json',
              'quality_cand_b.json', 'quality_cand_c.json'):
    _p = os.path.join(EV, _name)
    if not os.path.exists(_p):
        continue
    _d = json.load(io.open(_p, encoding='utf-8'))
    for _r in _d.get('records') or []:
        _CORPUS.append((_name, _r.get('id'), _r.get('rep'), _r.get('reply') or u''))

check(u'C0 分母 = 168 条（4 组 × 42；空集会让下面两条恒真）',
      len(_CORPUS) == 168, u'n=%d' % (len(_CORPUS),))

_hits = [(n, i, r) for (n, i, r, t) in _CORPUS if META(t)]
check(u'C1 命中**恰好 2 条**（多一条就是误伤，少一条就是漏判）',
      len(_hits) == 2, u'命中=%r' % (_hits,))

_want = {('quality_before.json', 'meta', 1), ('quality_before.json', 'cold', 1)}
_got = {(n, i, r) for (n, i, r) in _hits}
check(u'C2 命中的正是那两条（`before` 组的 meta/cold 第 1 遍），不是别的题',
      _got == _want, u'got=%r' % (sorted(_got),))

# --- C3：**逐条**断言其余 166 条，而不是只数总数 ——
#     总数相同也可能是"漏一条 + 多一条"，那是最坏的情况（既漏判又误伤）。
_bad = [(n, i, r) for (n, i, r, t) in _CORPUS
        if META(t) != ((n, i, r) in _want)]
check(u'C3 逐条核对：每一条的判定都正确（总数相同也可能是"漏一条+多一条"）',
      not _bad, u'错判=%r' % (_bad[:5],))

# ================================================ D. 自检
mark(u'D. 自检')
_SELF = _read(os.path.abspath(__file__))
_descs = re.findall(r"check\(\s*u?'([^']*)'", _SELF)
check(u'D1 判据名都是**非空字面量**（不许用计数拼进判据名）',
      len(_descs) >= 12 and all(d.strip() for d in _descs), u'n=%d' % (len(_descs),))
# --- D2：用 AST 数"有没有调用 `ok(...)`"，**不许用文本扫** ——
#     第一版写成 `'ok(' not in _SELF.replace(...)`，结果扫到了这条判据自己的源码
#     （表达式里就写着 `'ok('`）⇒ 自己把自己判红。判据也是被测物（第160轮同族）。
_ok_calls = [n for n in ast.walk(ast.parse(_SELF))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'ok']
check(u'D2 只用 `check()` 不用 `ok()`（两套 harness 混用会漏查恒真，第125轮教训）',
      not _ok_calls, u'ok() 调用 %d 处' % (len(_ok_calls),))
_raw_ev = open(EVENT, 'rb').read()
check(u'D3 产品文件无 BOM、全 LF（编辑不许改行尾）',
      not _raw_ev.startswith(b'\xef\xbb\xbf') and b'\r\n' not in _raw_ev)
check(u'D4 判据零外部盘（不许依赖 E:/D:，回归必须能在干净机器上跑）',
      not re.search(r'["\'](?:E|D):[\\\\/]', _SELF))

print(u'\n合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
sys.exit(1 if _n_fail else 0)
