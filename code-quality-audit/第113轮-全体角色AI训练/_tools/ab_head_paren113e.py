# -*- coding: utf-8 -*-
"""修改前(HEAD) vs 修改后(工作区) 的 strip_action_parentheticals 逐条对照。

★ 目的：3 条 FAIL 里必须分清「我引入的」和「本来就有的」——
   否则会把既有行为记成新 bug，或者放过真回归。
"""
import importlib.util
import io
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
OLD = r'C:\Users\23002\AppData\Local\Temp\rb113\event_speech_HEAD.py'

src = subprocess.run(['git', 'show', 'HEAD:ralsei_pet/modules/event_speech.py'],
                     cwd=ROOT, capture_output=True).stdout
io.open(OLD, 'wb').write(src)
print('HEAD 版已落盘 %d 字节' % len(src))

sys.path.insert(0, ROOT + r'\ralsei_pet')
sys.path.insert(0, ROOT + r'\ralsei_pet\modules')

from modules.event_speech import strip_action_parentheticals as NEW   # noqa: E402

spec = importlib.util.spec_from_file_location('es_old', OLD)
es_old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(es_old)
OLD_F = es_old.strip_action_parentheticals

CASES = [
    ('正', '第1轮', '烦死了。（你皱起眉头看着屏幕那边的人，“你别这么盯着我看。我才没空想东想西的！”）'),
    ('正', '第3轮', '先啃点东西充饥。（你轻描淡写地说道）不过晚上得开夜车。'),
    ('正', '第4轮', '哈，你说那个啊。（你的目光闪烁了一下，“有时候确实会沉迷进去好几个小时……”）'),
    ('正', '第6轮', '嗯……其实我没特别想留下的地方。（你的目光游离，“不过在黑暗世界的湖边挺好的。”）'),
    ('负', '你懂的', '（你懂的）那种感觉。'),
    ('负', '你说的对', '（你说的对）那就这么办。'),
    ('负', '笑', '（笑）随你便。'),
    ('负', '小声', '（小声）别告诉别人。'),
    ('负', '第一人称心里话', '（其实我很害怕）但我还是要去。'),
    ('负', '你叫什么', '（你叫什么名字）我先问问。'),
    ('负', '你想去吗', '（你想去吗）我等你决定。'),
]

print('%-4s %-14s %-10s %-10s %s' % ('类', '标签', 'HEAD', '现在', '判定'))
changed = 0
for kind, tag, s in CASES:
    a = OLD_F(s)
    b = NEW(s)
    if a != b:
        changed += 1
    verdict = '★ 本轮改变' if a != b else '-- 未变'
    print('%-4s %-14s %-10s %-10s %s'
          % (kind, tag, ('删' if a != s else '留'), ('删' if b != s else '留'), verdict))

print('\n本轮改变条数 =', changed)
print('（正控制希望「留→删」，负控制希望「留→留」）')
