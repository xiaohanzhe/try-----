# -*- coding: utf-8 -*-
"""第113轮k-i：`detect_activity` 要认**否定**。

问题（本轮自查，属于"人味"线）：
    用户：「我不饿。」
    旧行为：`detect_activity` 命中 `饿` ⇒ 产块 ⇒ 模型很可能接「那要不去家乡那家餐厅？」
—— 用户刚说吃饱了，桌宠还劝他吃饭。这正是「不像人」的典型。

★ 修法：意图词**前面 3 个字**里出现否定词 ⇒ 这个词不算"他要去"。
  窗口取 3 是因为 `我不太饿` 的 `不` 隔了两个字。
★ 只否肯定词命中，**不整句丢弃**：`我不累，出去逛逛` 里 `累` 被否掉之后，
  后面那个 `出去` 仍然该命中 `play` —— 丢掉整句就变成"听不懂话"。
★ 代价（写清楚）：双重否定（`不是不吃`）会被误否。中文里极少，且错的方向是
  **不推荐**（沉默），比乱推荐安全。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE = os.path.join(PET, 'modules', 'npc_life.py')
NL = '\r\n'

CONST_ANCHOR = "def detect_activity(text):"
CONST_ADD = '''#: 意图词前面的**否定词**：出现就说明"他不是要去"。
#: ★ 为什么需要：`我不饿` 里那个 `饿` 会让 NPC 立刻推荐餐厅 —— 用户刚说吃饱，
#:   桌宠还劝他吃饭，这是"不像人"的典型（第113轮k 自查）。
_NEG_HEADS = '不没别甭勿莫'
#: 往前看几个字。取 3：`我不太饿` 的 `不` 与 `饿` 隔两个字。
_NEG_WINDOW = 3


def _negated(s, i):
    """`s[i:]` 开头的那个词，前面 `_NEG_WINDOW` 个字里有否定词吗？"""
    if i <= 0:
        return False
    return any(ch in _NEG_HEADS for ch in s[max(0, i - _NEG_WINDOW):i])


'''

OLD = """    best_kind, best_word, best_at = None, '', len(s) + 1
    for kind in ACTIVITY_KINDS:
        for w in INTENT_WORDS.get(kind, ()):
            i = s.find(w.lower())
            if 0 <= i < best_at:
                best_kind, best_word, best_at = kind, w, i
    return (best_kind, best_word)"""

NEW = """    best_kind, best_word, best_at = None, '', len(s) + 1
    for kind in ACTIVITY_KINDS:
        for w in INTENT_WORDS.get(kind, ()):
            wl = w.lower()
            i = s.find(wl)
            # ★ 同一词可能在一句里出现多次（`我不饿，你想吃点什么`）：被否掉的那次
            #   跳过、继续找下一次，**不能**因为第一处是否定就当整句没提。
            while i >= 0 and _negated(s, i):
                i = s.find(wl, i + 1)
            if 0 <= i < best_at:
                best_kind, best_word, best_at = kind, w, i
    return (best_kind, best_word)"""

DOC_OLD = '''    ★ 多个活动同时命中时取**句子里最先出现**的那个：
      "吃完饭去逛逛" 的第一件事是吃饭。按表顺序取会得到与语序无关的答案，那是错的。
    ★ 空串 / None ⇒ `(None, '')`，不猜。
    """'''
DOC_NEW = '''    ★ 多个活动同时命中时取**句子里最先出现**的那个：
      "吃完饭去逛逛" 的第一件事是吃饭。按表顺序取会得到与语序无关的答案，那是错的。
    ★ 空串 / None ⇒ `(None, '')`，不猜。
    ★★ **否定**要认（`我不饿` / `没吃饭` / `别玩了`）⇒ 那个词不算 —— 否则
      用户刚说吃饱，桌宠就开始推荐餐厅。只否**被否的那一处**，不整句丢弃：
      `我不累，出去逛逛` 里的 `出去` 仍然该命中 `play`。
    """'''


def pat(path, old, new, tag):
    t = io.open(path, 'r', encoding='utf-8', newline='').read()
    if new.replace('\n', NL) in t:
        print('[SKIP] %s' % tag)
        return True
    o = old.replace('\n', NL)
    if o not in t:
        print('[FAIL] %s 锚点没命中' % tag)
        return False
    io.open(path, 'w', encoding='utf-8', newline='').write(
        t.replace(o, new.replace('\n', NL), 1))
    print('[ OK ] %s' % tag)
    return True


def main():
    t = io.open(LIFE, 'r', encoding='utf-8', newline='').read()
    if 'def _negated(' not in t:
        if CONST_ANCHOR not in t:
            print('[FAIL] 常量锚点没命中')
            return 1
        t = t.replace(CONST_ANCHOR, CONST_ADD.replace('\n', NL) + CONST_ANCHOR, 1)
        io.open(LIFE, 'w', encoding='utf-8', newline='').write(t)
        print('[ OK ] 插入 _NEG_HEADS / _negated')
    else:
        print('[SKIP] 已有 _negated')
    ok = pat(LIFE, DOC_OLD, DOC_NEW, 'detect_activity 文档')
    ok = pat(LIFE, OLD, NEW, 'detect_activity 否定') and ok

    import ast
    src = io.open(LIFE, 'r', encoding='utf-8', newline='').read()
    try:
        ast.parse(src)
        print('[ OK ] 语法 PASS')
    except SyntaxError as e:
        print('[FAIL] 语法 %s' % e)
        return 1
    print('行=%d CRLF=%d gap=%d' % (src.count('\n'), src.count('\r\n'),
                                   src.count('\n') - src.count('\r\n')))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
