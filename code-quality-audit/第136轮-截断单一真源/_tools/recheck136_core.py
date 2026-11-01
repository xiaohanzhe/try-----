# -*- coding: utf-8 -*-
"""第136轮：改过核心文件后的最小复检（语法/接线/常量/自检）。

★ 用 `ast.parse` 而不是 `py_compile`：后者会产 `.pyc`，把工作区弄脏（第109轮教训）。
"""
import ast
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES                                     # noqa: E402

fails = []
_n = {'p': 0}


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        fails.append(desc)
    print('%s %s%s' % ('[PASS]' if cond else '[FAIL]', desc, ('  ' + extra) if extra else ''))


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


print('=' * 70)
print('1. 语法')
for rel in ('src/main.py', 'modules/event_speech.py'):
    p = os.path.join(PET, rel)
    try:
        ast.parse(read(p))
        check('语法 OK：%s' % rel, True)
    except SyntaxError as e:
        check('语法 OK：%s' % rel, False, str(e))

print('')
print('2. 模块自检（event_speech._selfcheck）')
msg = ES._selfcheck()
check('event_speech 自检通过', '通过' in msg, msg)

print('')
print('3. 常量与接线')
check('AUTO_SPEAK_MAX_CHARS == 40', ES.AUTO_SPEAK_MAX_CHARS == 40, '%r' % (ES.AUTO_SPEAK_MAX_CHARS,))
check('EVENT_MAX_CHARS 仍是 24（本轮没动它）', ES.EVENT_MAX_CHARS == 24, '%r' % (ES.EVENT_MAX_CHARS,))
check("`…` 在 _SENTENCE_ENDS 里", u'…' in ES._SENTENCE_ENDS, '%r' % ES._SENTENCE_ENDS)
check("`——` 不在（语料里只作插入语）", u'—' not in ES._SENTENCE_ENDS)

src = read(os.path.join(PET, 'src', 'main.py'))
check('main.py 调的是 fit_sentences(text, AUTO_SPEAK_MAX_CHARS)',
      u'text = fit_sentences(text, AUTO_SPEAK_MAX_CHARS)' in src)

# ★★ 判据从"文本扫 `for sep in (`"改成 **AST**：第一版就是纯文本扫，
#   而我新写的注释里**引用了那段旧代码**⇒判据当场误报（同类第 6 次，§108.6）。
#   纯文本扫既会把注释算进去，也会漏掉换个写法的循环。这里按 AST 查 `For` 的 target。
_t_main = ast.parse(src)
_auto = [n for n in ast.walk(_t_main)
         if isinstance(n, ast.FunctionDef) and n.name == u'start_autonomous_speech']
_sep_loops_auto = [n.lineno for n in (ast.walk(_auto[0]) if _auto else [])
                   if isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                   and n.target.id == u'sep']
check('start_autonomous_speech 里没有 `for sep in ...` 循环（AST）', not _sep_loops_auto,
      'lineno=%r' % (_sep_loops_auto,))

# 全文件还有几处同族实现 —— **只登记，不当失败**（见下方 INFO）
_sep_loops_all = [n.lineno for n in ast.walk(_t_main)
                  if isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                  and n.target.id == u'sep']
print('[INFO] main.py 其余 `for sep in ...`：%r' % (_sep_loops_all,))
print('       ↑ 应恰好 1 处（`_clean_ai_reply` 的 220 字上限，语义与 fit_sentences 等价、'
      '本轮**有意不统一**）')
check('同族实现只剩 1 处（第三条截断链没在本轮被复制出更多）', len(_sep_loops_all) == 1,
      '%d 处' % len(_sep_loops_all))
check('main.py 的注释不再是"只保留第一句"那种肯定式断言',
      u'# 只保留第一句，避免模型长篇大论撑爆对话框' not in src)

print('')
print('4. 行为抽查（三条最容易看错的）')
B7 = u'主人好久没跟我说话啦，是不是很忙呀？要不要休息一下呢？'
check('B7 那条：整句保留（27 字）', ES.fit_sentences(B7, 40) == B7, repr(ES.fit_sentences(B7, 40)))
check('超长无标点：压到 40 字内', len(ES.fit_sentences(u'我想起你说的那件事了那时候你说你有点不知道该怎么办'
                                                u'我一直记着后来也没敢问你今天好一点了没有我这边一直听着呢')) <= 40)
check('事件链没被带坏：`诶？！好舒服呀。` 仍是完整一句',
      ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。') == u'诶？！好舒服呀。')
check('`……` 不被切一半', ES.first_sentence(u'真的很好呀……') == u'真的很好呀……')

print('')
print('=' * 70)
print('复检：PASS=%d FAIL=%d' % (_n['p'], len(fails)))
if fails:
    for d in fails:
        print('  - %s' % d)
sys.exit(0 if not fails else 1)
