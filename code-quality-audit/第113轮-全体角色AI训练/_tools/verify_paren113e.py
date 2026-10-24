# -*- coding: utf-8 -*-
"""第113轮e 验证：修完之后，正控制必删、负控制必留（成对）。"""
import os
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools'))

from modules.event_speech import strip_action_parentheticals as S   # noqa: E402
import common113 as C                                              # noqa: E402

# ---- 正控制：真实模型输出，修完必须把旁白删掉、台词留下 ----
POS = [
    ('第1轮', '烦死了。（你皱起眉头看着屏幕那边的人，“你别这么盯着我看。我才没空想东想西的！”）', '烦死了。'),
    ('第3轮', '先啃点东西充饥。（你轻描淡写地说道）不过晚上得开夜车。', '先啃点东西充饥。不过晚上得开夜车。'),
    ('第4轮', '哈，你说那个啊。（你的目光闪烁了一下，“有时候确实会沉迷进去好几个小时……”）',
     '哈，你说那个啊。'),
    ('第6轮', '嗯……其实我没特别想留下的地方。（你的目光游离，“不过在黑暗世界的湖边挺好的。”）',
     '嗯……其实我没特别想留下的地方。'),
]

# ---- 负控制：这些都是正常台词，一个都不许动 ----
NEG = [
    '（你懂的）那种感觉。',
    '（你说的对）那就这么办。',
    '（笑）随你便。',
    '（其实我很害怕）但我还是要去。',
    '（你叫什么名字）我先问问。',
    '（你想去吗）我等你决定。',
]

print('=== 正控制（产品护栏：旁白必须消失，台词必须留下）===')
ok = bad = 0
for tag, src, want in POS:
    got = S(src)
    hit = (got == want)
    print('[%s] %-6s %r' % ('PASS' if hit else 'FAIL', tag, got))
    if not hit:
        print('        期望 %r' % want)
    ok, bad = (ok + 1, bad) if hit else (ok, bad + 1)

print('\n=== 负控制（产品护栏：一个字都不许改）===')
for src in NEG:
    got = S(src)
    hit = (got == src)
    print('[%s] %r' % ('PASS' if hit else 'FAIL', got))
    ok, bad = (ok + 1, bad) if hit else (ok, bad + 1)

print('\n=== 训练判据（4 条真实输出必须全部报违规）===')
for tag, src, _ in POS:
    m = C._PAREN_RE.search(src)
    hit = bool(m)
    print('[%s] %-6s %s' % ('PASS' if hit else 'FAIL', tag, m.group(0)[:40] if m else '★ 仍漏报'))
    ok, bad = (ok + 1, bad) if hit else (ok, bad + 1)

# ★ 训练判据 `_PAREN_RE` 的**设计口径就是「出现括号 ⇒ 违规」**（不论内容长短），
#   与产品护栏「只删第二人称旁白、保留第一人称心里话」**不是同一把尺**。
#   ⇒ 这里的负控制只能用「完全不含括号的正常台词」，拿 `（你懂的）` 当负控制是**选错了**。
NEG_GATE = [
    '那种感觉，你知道的。',
    '那就这么办吧。',
    '随你便，我无所谓。',
]
print('\n=== 训练判据负控制（无括号的正常台词不许误报）===')
for src in NEG_GATE:
    hit = not C._PAREN_RE.search(src)
    print('[%s] %r' % ('PASS' if hit else 'FAIL', src))
    ok, bad = (ok + 1, bad) if hit else (ok, bad + 1)

print('\n=== 两把尺的分工（必须不同，否则等于没分开）===')
_demo = '（你懂的）那种感觉。'
print('    产品护栏对 %r ⇒ %r（保留）' % (_demo, S(_demo)))
print('    训练判据对同一条 ⇒ %s（违规）' % ('报违规' if C._PAREN_RE.search(_demo) else '不报'))
print('    ★ 两者不同 = 口径确实分歧，写进报告，别硬凑成一致')

print('\n=== 既有行为（不是本轮引入，已用 HEAD 版对照确认不变）===')
_p = '（小声）别告诉别人。'
print('    产品护栏对 %r ⇒ %r' % (_p, S(_p)))
print('    ⇒ HEAD 版同样删掉（`_ACTION_MODIFIERS` 含「小声」），本轮**未改变**它')

print('\n=== 恒真防护：负控制真的走进了被测分支吗 ===')
print('    负控制里确实含有括号字符 =', all(('（' in x or '(' in x) for x in NEG))
print('    正控制里确实含有括号字符 =', all(('（' in x or '(' in x) for _, x, _ in POS))

print('\nPASS=%d FAIL=%d' % (ok, bad))
