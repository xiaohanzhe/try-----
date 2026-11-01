# -*- coding: utf-8 -*-
"""第133轮 · 判据自纠的取证（不猜，逐条实测）。

C4/D2/D3/E3 报红之后，先确认是"夹具不保真"还是"产品真有问题"：
  1. `strip_action_parentheticals` 对括注自评到底删不删？（决定"位置"是不是硬约束）
  2. 句首括号的短句是不是被**老闸** `looks_like_narration` 拦的？（D2 的样本选错了没有）
  3. `_clean_ai_reply` 在 main.py 里是不是类方法？（E3 的 AST 找法错了没有）
  4. 清空规则表之后，S1/S2/S3 是不是真的全部放行？（D3 断言方向有没有写反）
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
if PET not in sys.path:
    sys.path.insert(0, PET)
from modules import event_speech as E          # noqa: E402

S3 = u'嗯…（这里说的是你自己的事，而不是直接给出建议）'
S3_ONLY = u'（这里说的是你自己的事，而不是直接给出建议）'

print('=== 1. strip 对括注自评 ===')
for t in (S3, S3_ONLY):
    s = E.strip_action_parentheticals(t)
    print('  原文 %r' % t)
    print('    strip → %r  （删了 = %s）' % (s, s != t))
    print('    meta(原文)=%s  meta(strip后)=%s'
          % (E.looks_like_meta_leak(t), E.looks_like_meta_leak(s)))

print('=== 2. 句首括号是谁拦的 ===')
for t in (u'（这里有点暗，我看不太清。）', u'嗯，这里有点暗。'):
    print('  %r → narration=%s meta=%s ooc=%s banned=%s guard=%r'
          % (t, E.looks_like_narration(t), E.looks_like_meta_leak(t),
             E.looks_out_of_character(t), E.looks_like_assistant_speak(t),
             E.guard_reaction(t)))

print('=== 3. _clean_ai_reply 的 AST 位置 ===')
with io.open(os.path.join(PET, 'src', 'main.py'), 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())
found = []
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == '_clean_ai_reply':
        found.append((n.lineno, [x.func.id for x in ast.walk(n)
                                 if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)]))
print('  递归找到 %d 个 _clean_ai_reply：%r' % (len(found), found[:2]))
print('  顶层 body 里找得到 = %s'
      % any(isinstance(n, ast.FunctionDef) and n.name == '_clean_ai_reply'
            for n in tree.body))

print('=== 4. 清空规则表之后的判定 ===')
orig = E._META_LEAK_RES
S1 = u'我不该用亮起来的开头，先就着那件事问一句。'
S2 = u'先就着你说的那件事问一句："这么说，你是觉得……"'
try:
    E._META_LEAK_RES = ()
    for t in (S1, S2, S3):
        print('  清空后 guard(%r) = %r' % (t[:12], E.guard_reaction(t)))
finally:
    E._META_LEAK_RES = orig
print('  恢复后条数 = %d' % len(E._META_LEAK_RES))
