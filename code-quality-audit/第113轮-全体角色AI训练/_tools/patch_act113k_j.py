# -*- coding: utf-8 -*-
"""第113轮k-j：否定**不许跨句**。

实测：
    输入「我不累，出去逛逛」
    旧（修 i）：`出去` 被前面 3 个字的 `不累，` 里的 `不` 否掉 ⇒ 退回命中更靠后的 `逛`
                ⇒ 结果虽然是 play，但**命中的词错了**（应为 `出去`）。
    再坏一点的情形：「我不想吃饭，去看戏」⇒ `吃饭` 被否（对），
                「去看戏」里的词如果也落在 3 字窗口内就会被误否。

★ 修法：窗口内一旦出现**断句符**立即停手 —— 一口话里的否定不跨逗号。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE = os.path.join(PET, 'modules', 'npc_life.py')
NL = '\r\n'

OLD = """#: 往前看几个字。取 3：`我不太饿` 的 `不` 与 `饿` 隔两个字。
_NEG_WINDOW = 3


def _negated(s, i):
    \"\"\"`s[i:]` 开头的那个词，前面 `_NEG_WINDOW` 个字里有否定词吗？\"\"\"
    if i <= 0:
        return False
    return any(ch in _NEG_HEADS for ch in s[max(0, i - _NEG_WINDOW):i])"""

NEW = """#: 往前看几个字。取 3：`我不太饿` 的 `不` 与 `饿` 隔两个字。
_NEG_WINDOW = 3
#: **断句符**：否定不跨句。
#: ★ 踩过：「我不累，出去逛逛」里 `出去` 距 `不` 是 3 个字、中间还有个逗号，
#:   不切断的话 `出去` 被误否 ⇒ 退回命中更靠后的 `逛`（意思对了，但命中的词错了）；
#:   更坏的情形是后半句真正想说的那个词也被否掉。
_NEG_BREAK = '，。！？；：、,.!?;: \\t\\r\\n…—~（）()「」'


def _negated(s, i):
    \"\"\"`s[i:]` 开头的那个词，**同一口气里**前面有否定词吗？

    ★ 窗口 `_NEG_WINDOW` 个字内、且中间不许夹断句符。
    \"\"\"
    if i <= 0:
        return False
    seg = s[max(0, i - _NEG_WINDOW):i]
    if any(ch in _NEG_BREAK for ch in seg):
        return False
    return any(ch in _NEG_HEADS for ch in seg)"""


def main():
    t = io.open(LIFE, 'r', encoding='utf-8', newline='').read()
    if '_NEG_BREAK' in t:
        print('[SKIP] 已有 _NEG_BREAK')
    else:
        o = OLD.replace('\n', NL)
        if o not in t:
            print('[FAIL] 锚点没命中')
            return 1
        io.open(LIFE, 'w', encoding='utf-8', newline='').write(
            t.replace(o, NEW.replace('\n', NL), 1))
        print('[ OK ] _negated 加断句符')

    import ast
    src = io.open(LIFE, 'r', encoding='utf-8', newline='').read()
    try:
        ast.parse(src)
        print('[ OK ] 语法 PASS')
    except SyntaxError as e:
        print('[FAIL] 语法 %s' % e)
        return 1

    sys.path.insert(0, os.path.join(PET, 'modules'))
    import npc_life as L
    for s, want in (('我不累，出去逛逛', 'play'), ('我不饿', None),
                    ('我饿了', 'eat'), ('没吃饭呢', None), ('别玩了', None),
                    ('咱吃饭去吧', 'eat'), ('我有点累了，歇会儿吧', 'rest'),
                    ('去买点东西', 'work'), ('不累的话出去逛逛', 'play')):
        got = L.detect_activity(s)
        flag = 'OK ' if got[0] == want else 'BAD'
        print('  %s %-14s => %r（期望 %r）' % (flag, s, got[0], want))
    return 0


if __name__ == '__main__':
    sys.exit(main())
