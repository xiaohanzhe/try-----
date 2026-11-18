# -*- coding: utf-8 -*-
"""第198轮探针：看一眼「记错」到底长什么样，再决定判据怎么写。

先看输出，后写断言 —— 反过来容易写出恒真判据。
"""
import os
import re
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

_here = os.path.dirname(os.path.abspath(__file__))
_pet = os.path.abspath(os.path.join(_here, '..', '..', '..', 'ralsei_pet'))
sys.path.insert(0, os.path.join(_pet, 'modules'))

from memory_system import MemorySystem  # noqa: E402

TEXTS = [
    u'我下午三点十五分去买了3个面包',
    u'今天15:30 我跑了2次操场',
    u'刚才吃了5个饺子',
    u'昨天跟你聊到2点',
    u'前天买了4个苹果',
    u'我今天有点累',
    u'刚下过雨，路上湿',
    u'明天要早起开会',
    u'昨晚看了3集动画',
    u'刚才在楼下碰到邻居家的狗',
]
KEY_TEXTS = [
    u'升到5级了，这是第3次升级',
]


def main():
    d = tempfile.mkdtemp(prefix='mem198_', dir=r'D:\_tmp')
    try:
        m = MemorySystem(None, memory_dir=d)
        for t in TEXTS:
            m.add_fragment(t, who='user')
        for t in KEY_TEXTS:
            m.remember_key('level_up', t)

        print('== 片段总数 = %d  keys = %d ==' % (len(m.fragments), len(m.keys)))

        # 逐条问 misfire_mode
        modes = []
        for f in m.fragments:
            modes.append((f.get('text'), m.misfire_mode(f)))
        from collections import Counter
        print('== misfire 分布 ==',
              Counter(x[1] or '(不触发)' for x in modes))
        for t, md in modes:
            if md:
                print('   %-6s %s' % (md, t))

        print()
        print('== key 是否免疫 ==')
        for k in m.keys:
            print('   kind=%s  mode=%r  text=%s'
                  % (k.get('kind'), m.misfire_mode(k), k.get('text')))

        print()
        print('== recall_text 实际输出（cue=面包/操场/饺子）==')
        for cue in (u'面包', u'操场', u'饺子'):
            out = m.recall_text(cue, limit=3)
            print('-- cue=%s --' % cue)
            print(out or '(空)')

        print()
        print('== 确定性：同一片段问两次 ==')
        f0 = m.fragments[0]
        print('   1st=%r' % m.misfire_mode(f0))
        print('   2nd=%r' % m.misfire_mode(f0))

        print()
        print('== 数字不新增（SOFTEN 只减不增）==')
        bad = 0
        for f in m.fragments:
            if m.misfire_mode(f) != 'soften':
                continue
            src = str(f.get('text') or '')
            out = m._misfire_soften(src)
            a = set(re.findall(r'\d+', src))
            b = set(re.findall(r'\d+', out))
            if not b <= a:
                bad += 1
                print('   NEW DIGITS %r -> %r' % (src, out))
        print('   违规条数 = %d' % bad)

        print()
        print('== RATE=0 时是否逐字回到旧格式 ==')
        m.MISFIRE_RATE = 0.0
        for cue in (u'面包',):
            print(m.recall_text(cue, limit=3))
        m.MISFIRE_RATE = 1.0
        print('-- RATE=1.0, cue=面包 --')
        print(m.recall_text(u'面包', limit=3))
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    main()
