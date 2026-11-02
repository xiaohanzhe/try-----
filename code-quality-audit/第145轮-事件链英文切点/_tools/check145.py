# -*- coding: utf-8 -*-
"""第145轮回归锁：事件链（24 字）/ 主动开口（40 字）不认 ASCII `.` —— 英文切在半个单词上。

## 病

`event_speech._SENTENCE_ENDS = u'。！？!?\\n…'` —— **没有 ASCII `.`**。
英文回复 `Well, well, well. What do we have here?` 在这张表里**一个切点都没有**
⇒ 只有末尾那句 `t[:max_chars].rstrip('，,、。！？!?；;：: ')` 硬截 ⇒
`Well, well, well. What d`（后面紧跟 `o we have he`）。

这是第143轮那条病的**另一半**：143 修的是对话链（200 字），
这两条链（24 / 40 字）当时没查 —— 而 24 个**字符**对英文只有大约 4 个单词。

## 实测（77 人 / 5592 条真机回复，`_evidence/lead145.json` + `ab145.json`）

| 链 | 英文切在词中（旧→新） | 中文（旧→新） |
|---|---|---|
| 事件 24 字 | **203 → 135**（−68，占英文 448 条的 15.2%） | 1031 → 959 |
| 开口 40 字 | **184 → 100**（−84） | 239 → 200 |

中文也降了 72 条：模型在中文里也用 `...` 当省略号，切在它后面是**完整**的停顿，
比硬截在汉字中间好。132 条中文输出变化**逐条看过**，全是"切在句末 / 省略号后"。

## 改法（两处，且是"减少重复"）

1. `_SENTENCE_ENDS` 加 `.`；配套 `_sentence_ends()` 过滤：
   `.` 前面已有 ≥ `MIN_FIRST_CHARS` 个字才算句末（挡缩写点 `Mr.` / 开头 `...`），
   后面紧跟数字则一律不算（挡小数点 `3.14`）。
2. `first_sentence` 与 `fit_sentences` 原来**各自抄了一遍**"扫标点 + 吃连续 + 去重"
   —— 合成 `_sentence_ends()` 一处实现（加过滤必须两边一致，否则又成"同一份规则两处算"）。

## 本套件守什么

A 证据面：两份 json 在盘、数字自洽、A/B 两份源码**不同**（否则"有改善"是假的）
B 机制面（AST）：`.` 在常量里 · 两条链**都**调 `_sentence_ends` · 过滤两个分支都在 ·
  **函数体内零处重复扫表**（防回潮）
C 行为面：4 条英文用例 + 2 条中文既有契约 + `fit_sentences` 的"最长完整句群" +
  **两条负控制**（去掉 `.` / 把 MIN 调 0，必须变差 —— 证明 C1 不是恒真）
D 自检
"""
import ast
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
ES_PATH = os.path.join(PET, 'modules', 'event_speech.py')
MAIN = os.path.join(PET, 'src', 'main.py')

sys.path.insert(0, PET)
from modules import event_speech as ES          # noqa: E402

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=u''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _func(tree, name):
    for nd in ast.walk(tree):
        if isinstance(nd, ast.FunctionDef) and nd.name == name:
            return nd
    return None


def _calls(name, fn):
    """`fn` 体内是否有 `name(...)` 调用（不含注释、不吃字符串）。"""
    for nd in ast.walk(fn or ast.Module(body=[], type_ignores=[])):
        if isinstance(nd, ast.Call):
            f = nd.func
            if isinstance(f, ast.Name) and f.id == name:
                return True
    return False


def main():
    src = _read(ES_PATH)
    tree = ast.parse(src)
    ev = json.loads(_read(os.path.join(EV, 'lead145.json')))
    ab = json.loads(_read(os.path.join(EV, 'ab145.json')))

    # ======================================================================
    head(u'A · 证据面（先证明"我量的是真的"）')

    check(u'A1 `lead145.json` 是 77 个文件 / 5592 条回复',
          ev.get('files') == 77 and ev.get('turns') == 5592,
          u'%s / %s' % (ev.get('files'), ev.get('turns')))
    check(u'A2 两份源码 sha1 **不同**（A/B 真的在比两个东西）',
          ab['sha1']['old'] != ab['sha1']['new'])
    a = ab['all']
    check(u'A3 少掉的量确实存在：24 字 1234→1094、40 字 423→300（只许降）',
          a['mid24'] == [1234, 1094] and a['mid40'] == [423, 300],
          u'%s ｜ %s' % (a['mid24'], a['mid40']))
    e = ab['en']
    check(u'A4 英文侧降幅最大：203→135（事件）· 184→100（开口）',
          e['mid24'] == [203, 135] and e['mid40'] == [184, 100],
          u'%s ｜ %s' % (e['mid24'], e['mid40']))
    check(u'A5 中文侧也降了（模型在中文里也用 `...`），但不是主要目标',
          ab['zh']['mid24'][1] < ab['zh']['mid24'][0],
          u'%s' % ab['zh']['mid24'])
    check(u'A6 英文 448 条里"24 字内含 `.`"的有 194 条 —— 这就是 `.` 能救到的上界',
          ev.get('en_dot_in_24') == 194)

    # ======================================================================
    head(u'B · 机制面（AST：`.` 在表里、单一真源、过滤不许少）')

    ends_val = None
    for nd in tree.body:
        if isinstance(nd, ast.Assign) and isinstance(nd.value, ast.Constant):
            for t in nd.targets:
                if isinstance(t, ast.Name) and t.id == '_SENTENCE_ENDS':
                    ends_val = nd.value.value
    check(u'B1 `_SENTENCE_ENDS` 里有 ASCII `.`', isinstance(ends_val, str)
          and '.' in ends_val, u'值=%r' % (ends_val,))
    check(u'B2 `…` 还在（第136轮加的，不许为了加 `.` 把它丢了）',
          isinstance(ends_val, str) and u'\u2026' in ends_val)
    check(u'B3 `,` / `;` **没**被加进来（句内停顿不是句末）',
          isinstance(ends_val, str) and ',' not in ends_val
          and ';' not in ends_val)

    fs = _func(tree, 'first_sentence')
    fit = _func(tree, 'fit_sentences')
    se = _func(tree, '_sentence_ends')
    check(u'B4 `_sentence_ends()` 存在（两条链共用一处实现）', se is not None)
    check(u'B5 `first_sentence` 真调 `_sentence_ends`', _calls('_sentence_ends', fs))
    check(u'B6 `fit_sentences` 真调 `_sentence_ends`', _calls('_sentence_ends', fit))
    # 回潮闸：两个函数体内不许再出现 `in _SENTENCE_ENDS` 这种成员测试
    dup = []
    for nm, fn in ((u'first_sentence', fs), (u'fit_sentences', fit)):
        for nd in ast.walk(fn or ast.Module(body=[], type_ignores=[])):
            if isinstance(nd, ast.Compare) and isinstance(nd.ops[0], ast.In):
                comp = nd.comparators[0]
                if isinstance(comp, ast.Name) and comp.id == '_SENTENCE_ENDS':
                    dup.append(nm)
    check(u'B7 两个函数体内**零处**自己扫 `_SENTENCE_ENDS`（防重复实现回潮）',
          not dup, u'命中 %s' % (u','.join(dup) or u'无'))

    # 过滤规则的两个分支：小数点 / 太短
    # ★★★ 必须**结构判定**，不能 `'isdigit' in seg` / `'MIN_FIRST_CHARS' in seg`：
    #   `_sentence_ends` 的 docstring 里本来就写着这两个名字（解释规则）
    #   ⇒ 字符串判据在"守卫被删掉"时**仍然是绿的**。`mutate145 M6` 就是这么抓出来的：
    #   守卫改成 `if False:`，B9 照样绿 —— 判据只判"提没提到"，等于没守。
    def _has_attr_call(fn, attr):
        for nd in ast.walk(fn):
            if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Attribute) \
                    and nd.func.attr == attr:
                return True
        return False

    def _has_name_in_compare(fn, name):
        for nd in ast.walk(fn):
            if isinstance(nd, ast.Compare):
                for c in nd.comparators:
                    if isinstance(c, ast.Name) and c.id == name:
                        return True
        return False

    check(u'B8 过滤里有小数点守卫（真调用 `.isdigit()`，不是注释里提一句）',
          se is not None and _has_attr_call(se, 'isdigit'))
    check(u'B9 过滤里有"头太短不算"守卫（`MIN_FIRST_CHARS` 真进了比较式）',
          se is not None and _has_name_in_compare(se, 'MIN_FIRST_CHARS'))

    # ======================================================================
    head(u'C · 行为面（真跑；四条英文 + 两条中文既有契约 + 两条负控制）')

    check(u'C1 `Well, well, well. What do we have here.` ⇒ `Well, well, well.`',
          ES.first_sentence(u'Well, well, well. What do we have here.')
          == u'Well, well, well.',
          repr(ES.first_sentence(u'Well, well, well. What do we have here.')))
    check(u'C2 缩写点不许当句末：`Mr. Smith went to town.` ⇒ 整句保留',
          ES.first_sentence(u'Mr. Smith went to town.') == u'Mr. Smith went to town.',
          repr(ES.first_sentence(u'Mr. Smith went to town.')))
    check(u'C3 开头的省略号不许当句末：`...H-H-HERE Y-YOU ARE.` ⇒ 整句保留',
          ES.first_sentence(u'...H-H-HERE Y-YOU ARE.')
          == u'...H-H-HERE Y-YOU ARE.',
          repr(ES.first_sentence(u'...H-H-HERE Y-YOU ARE.')))
    check(u'C4 小数点不算句末（`3.14` 不许切开）',
          u'3.14' in ES.first_sentence(
              u'It costs 3.14 coins. And that is that.'),
          repr(ES.first_sentence(u'It costs 3.14 coins. And that is all.')))
    # 中文既有契约（第135轮 §135.3 两条样本，`s7_event_speech A11` 同款）
    check(u'C5 中文既有契约①：`诶？！好舒服呀。后面还有…` ⇒ 切在 `。`',
          ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。')
          == u'诶？！好舒服呀。')
    check(u'C6 中文既有契约②：`哎呀！别捏我的耳朵！好痒呀！` ⇒ 三连感叹整句保留',
          ES.first_sentence(u'哎呀！别捏我的耳朵！好痒呀！')
          == u'哎呀！别捏我的耳朵！好痒呀！')
    check(u'C7 `fit_sentences` 取"能放下的最长完整句群"（英文）',
          ES.fit_sentences(u'Hello there. How are you today. I am fine thank you.')
          == u'Hello there. How are you today.',
          repr(ES.fit_sentences(
              u'Hello there. How are you today. I am fine thank you.')))
    # ★ 负控制一：把 `.` 从表里拿掉，C1 必须退化成"切在半个单词上"
    keep = ES._SENTENCE_ENDS
    try:
        ES._SENTENCE_ENDS = u'。！？!?\n…'
        bad = ES.first_sentence(u'Well, well, well. What do we have here.')
    finally:
        ES._SENTENCE_ENDS = keep
    check(u'C8 负控制：去掉 `.` ⇒ 立刻退回"切在半个单词上"（证明 C1 不是恒真）',
          bad != u'Well, well, well.' and bad.endswith(u'd'),
          repr(bad))
    # ★ 负控制二：MIN 守卫调 0，`Mr.` 就会被当句末
    mkeep = ES.MIN_FIRST_CHARS
    try:
        ES.MIN_FIRST_CHARS = 0
        bad2 = ES.first_sentence(u'Mr. Smith went to town.')
    finally:
        ES.MIN_FIRST_CHARS = mkeep
    check(u'C9 负控制：把 MIN 调 0 ⇒ `Mr.` 立刻被当句末（证明 C2 不是恒真）',
          bad2 == u'Mr.', repr(bad2))

    # ======================================================================
    head(u'D · 接线面（两条链在 main.py 里都还在用这两个函数）')

    msrc = _read(MAIN)
    check(u'D1 事件反应链仍调 `first_sentence`', u'first_sentence(reply' in msrc)
    check(u'D2 主动开口链仍调 `fit_sentences`', u'fit_sentences(text' in msrc)

    # ======================================================================
    head(u'E · 自检')

    mt = ast.parse(_read(os.path.abspath(__file__)))
    calls = [nd for nd in ast.walk(mt)
             if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
             and nd.func.id == 'check']
    trues = [nd for nd in calls
             if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant)
             and nd.args[1].value is True]
    check(u'E1 没有 `check(描述, True)` 这种恒真判据', not trues,
          u'命中 %d 处' % len(trues))
    marker = '[' + 'PASS]'
    leak = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and marker in sub.value:
                leak.append(1)
    check(u'E2 判据描述里没有那个计数标记的字面量', not leak,
          u'命中 %d 处' % len(leak))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
