# -*- coding: utf-8 -*-
"""第113轮k · 小补丁：`place_matches` 里把 `_` 也当分隔符。

为什么
------
`\b` 在正则里认 `\w` = `[A-Za-z0-9_]`，所以 `town_school` 里的 `school`
**不是**词首（前面是 `_`）⇒ `\bschool\b` 匹配不上。

调用方一般已经过 `room_word()`（它会把 `_` 转空格），但：
  · `room_word` 只剥前缀、转空格，它对**已经转过**的文本是幂等的；
  · 万一哪条调用链忘了转，这里就会**静默漏判**（漏一个地点，不报错）。
⇒ 两边都做。多一层防护比"靠调用方记得"可靠。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')

OLD = (
    "    s = str(text or '').lower()\r\n"
    "    if not s or kind not in PLACE_WORDS:\r\n"
)
NEW = (
    "    # ★ `_` 转空格：`town_school` 里的 `school` 在正则里**不是**词首\r\n"
    "    #   （`\\w` 含 `_`）⇒ `\\bschool\\b` 匹配不上。调用方一般已过 `room_word`，\r\n"
    "    #   但这里再容一次 —— 任何一边漏了都不会静默失效。\r\n"
    "    s = str(text or '').replace('_', ' ').lower()\r\n"
    "    if not s or kind not in PLACE_WORDS:\r\n"
)


def main():
    t = io.open(LIFE, encoding='utf-8', newline='').read()
    gap = len(t.splitlines()) - t.count('\r\n')
    assert gap in (0, 1), 'npc_life.py 不是全 CRLF：gap=%d' % gap
    # ★ 判据必须用**只可能出现在这一处**的整句：第一版用 ，
    #   而  里本来就有那一句 ⇒ 永远判"已改"、静默跳过。
    #   这就是本项目反复踩的"判据自己说谎"。
    if "s = str(text or '').replace('_', ' ').lower()" in t:
        print('已是容错版，跳过')
        return 0
    n = t.count(OLD)
    assert n == 1, '锚命中 %d 次（需 1）' % n
    c0 = t.count('\r\n')
    t2 = t.replace(OLD, NEW, 1)
    assert t2 != t
    got = t2.count('\r\n') - c0
    need = NEW.count('\r\n') - OLD.count('\r\n')
    assert got == need, 'CRLF 增量 %d（应 %d）' % (got, need)
    gap2 = len(t2.splitlines()) - t2.count('\r\n')
    assert gap2 in (0, 1)
    io.open(LIFE, 'w', encoding='utf-8', newline='').write(t2)
    assert io.open(LIFE, encoding='utf-8', newline='').read() == t2
    print('OK 行数=%d CRLF增量=%d' % (len(t2.splitlines()), got))
    return 0


if __name__ == '__main__':
    sys.exit(main())
