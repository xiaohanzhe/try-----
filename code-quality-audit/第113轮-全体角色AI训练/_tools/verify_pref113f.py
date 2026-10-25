# -*- coding: utf-8 -*-
"""验偏好判据改动：正/负控制成对 + 恒真防护。"""
import os
import sys

HERE = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第113轮-全体角色AI训练\_tools'
sys.path.insert(0, HERE)
import train30 as T   # noqa: E402

ok = bad = 0


def ck(desc, cond, detail=''):
    global ok, bad
    if cond:
        ok += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        bad += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


print('=== 词干提取 ===')
st = T.pref_stems(['在线滑板游戏', '恶作剧', '园艺'])
for k, v in st.items():
    print('  %-10s -> %s' % (k, v))

ck('词干含原词', all(k in v for k, v in st.items()))
ck('「在线滑板游戏」抽出「滑板」', '滑板' in st['在线滑板游戏'])
ck('泛词「游戏」被剔除（防恒真）', '游戏' not in st['在线滑板游戏'])
ck('泛词「在线」被剔除', '在线' not in st['在线滑板游戏'])
ck('单字主题被跳过', T.pref_stems(['花']) == {})

print('\n=== 命中判定（拿第113轮真实回答）===')
CASES = [
    ('susie 第5轮（具体：说了滑板）', '啊……那回我把一个滑板摔进Noelle的包里，让她以为是梦里的事。', True),
    ('susie 第4轮（空泛：只说"那个"）', '哈，你说那个啊。有时候确实会沉迷进去好几个小时……', False),
    ('asgore 第4轮（说了园艺）', '我觉得做园艺就是一种很好的放松方式，照顾那些花的时候会忘掉烦恼。', True),
    ('asgore 第6轮（只说花店，没说园艺）', '我想应该是花店吧——空气里有种特殊的香味。', False),
]


def hit_of(fin, stems):
    out = []
    for topic, cands in stems.items():
        for w in cands:
            if w in fin:
                out.append(w)
                break
    return out


for desc, text, want in CASES:
    stems = st
    got = bool(hit_of(text, stems))
    ck('%-32s 期望=%s' % (desc, want), got == want, '实际=%s 命中=%s' % (got, hit_of(text, stems)))

print('\n=== 恒真防护：纯泛词回答不许命中 ===')
VAGUE = ['这个东西啊，就那样吧。', '有时候会吧，反正没什么特别的。', '我也说不上来。']
for v in VAGUE:
    ck('泛词回答不命中 %r' % v[:12], not hit_of(v, st), '命中=%s' % hit_of(v, st))

print('\n=== 问法已改（不再二选一）===')
tpl = T.PREF_TEMPLATES[0]
ck('第1问不再含「还是闲着没事才碰一碰」', '闲着没事才碰一碰' not in tpl, tpl[:52])
ck('第1问要求「说个具体的」', '说个具体的' in tpl)

print('\nPASS=%d FAIL=%d' % (ok, bad))
sys.exit(1 if bad else 0)
