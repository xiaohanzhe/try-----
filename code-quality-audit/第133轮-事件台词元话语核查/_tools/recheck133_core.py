# -*- coding: utf-8 -*-
"""第133轮 · 改过核心文件后的复检（`ralsei_pet/modules/event_speech.py`）。

按"改过重要核心文件必须复检"的六项：① 语法 ② 结构 ③ 编码 ④ 恒真判据
⑤ 逐令牌回验（注释里每一条可检索的断言都回原文件核一次）⑥ 工作区与回归。

★ 复检**不许改变被测状态**：一律 `ast.parse` / 只读字节，不 `py_compile`（会产 `.pyc`）。
★ 每条都带分母或正负控制，"全绿"必须能说明它拦得住什么。
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TARGET = os.path.join(ROOT, 'ralsei_pet', 'modules', 'event_speech.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
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


with io.open(TARGET, 'rb') as f:
    RAW = f.read()
TEXT = RAW.decode('utf-8')

# ---------------------------------------------------------------- ① 语法
head(u'① 语法 / 可编译（ast.parse，不产 .pyc）')
try:
    TREE = ast.parse(TEXT)
    check(u'1.1 event_speech.py 语法可解析', True)
except SyntaxError as e:
    TREE = None
    check(u'1.1 event_speech.py 语法可解析', False, repr(e))

MAIN_TREE = ast.parse(io.open(MAIN, 'r', encoding='utf-8').read())
check(u'1.2 main.py 语法可解析', MAIN_TREE is not None)

# ---------------------------------------------------------------- ② 结构
head(u'② 结构自检（函数都在、注释没粘连、文档串完整）')


def func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


if TREE is not None:
    names = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]
    for fn in ('looks_like_meta_leak', 'guard_reaction', 'strip_action_parentheticals',
               'looks_like_narration', 'looks_out_of_character',
               'looks_like_assistant_speak', 'first_sentence', 'build_prompt'):
        check(u'2.x 函数在位：%s' % fn, fn in names)
    g = func(TREE, 'guard_reaction')
    doc = ast.get_docstring(g) or ''
    check(u'2.1 guard_reaction 的文档串覆盖五道闸（出戏/客服腔/元话语/括号/旁白）',
          all(k in doc for k in (u'出戏', u'客服腔', u'元话语', u'括号', u'旁白')),
          u'%d 字符' % len(doc))
    check(u'2.2 文档串里那条**纠错**记录在位（"实测否掉了这个理由"）',
          u'实测否掉了这个理由' in doc)
    # ★ 第一版写的是"文档串里不许出现『硬约束』" ⇒ 报红，而红的是判据：
    #   纠错句本身就写着"我以为这是硬约束"。禁词法在这里必然误伤（"判据只判提到某名字=恒真"的同型）。
    #   改成断"假结论的措辞没了 + 纠错的措辞在"。
    check(u'2.3 文档串里的假结论已撤（不再出现"必须排在…之前"）',
          u'必须排在' not in doc, u'残留=%s' % (u'必须排在' in doc))
    check(u'2.3b 且纠错结论在位（"两种顺序等价"）', u'两种顺序等价' in doc)

# 注释粘连：连续两行注释之间不该出现"半句接半句"（如上一行末尾无标点且下一行不是续行）
# 这里用一个可判的近似：新插的注释块里不允许出现两个连续空注释行
_lines = TEXT.splitlines()
_gi = [i for i, ln in enumerate(_lines) if ln.startswith(u'def guard_reaction')]
if _gi:
    i0 = _gi[0]
    _block = []
    j = i0 - 1
    while j >= 0 and (_lines[j].startswith(u' ') or _lines[j].startswith(u'#') or not _lines[j].strip()):
        _block.append(_lines[j])
        j -= 1
        if len(_block) > 40:
            break
    check(u'2.4 guard_reaction 上方的注释块非空（说明改动带说明）', len(_block) > 5,
          u'%d 行' % len(_block))

# ---------------------------------------------------------------- ③ 编码
head(u'③ 编码（BOM / U+FFFD / 行尾）')
check(u'3.1 无 BOM', not RAW.startswith(b'\xef\xbb\xbf'))
check(u'3.2 无 U+FFFD（替换字符）', u'\ufffd' not in TEXT,
      u'出现 %d 次' % TEXT.count(u'\ufffd'))
_crlf = TEXT.count(u'\r\n')
_lf = TEXT.count(u'\n') - _crlf
check(u'3.3 行尾不混用（CRLF=%d / 裸 LF=%d，两者必有一个为 0）' % (_crlf, _lf),
      _crlf == 0 or _lf == 0)

# ---------------------------------------------------------------- ④ 恒真判据
head(u'④ 恒真判据复查（本轮新写的 check 不许有 `check(..., True)`）')
_c133 = os.path.join(ROUND, '_tools', 'check133.py')
_t = ast.parse(io.open(_c133, 'r', encoding='utf-8').read())
_bad = []
for n in ast.walk(_t):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
            _bad.append(n.lineno)
check(u'4.1 check133 无恒真判据', not _bad, u'%d 处' % len(_bad))
# 正控制：往源码里塞一条假的恒真判据必须被同一个检查抓到
_src = io.open(_c133, 'r', encoding='utf-8').read()
_fake = _src.replace(u"check(u'A0 证据文件在'", u"check(u'FAKE 恒真', True)\ncheck(u'A0 证据文件在'", 1)
_t2 = ast.parse(_fake)
_bad2 = []
for n in ast.walk(_t2):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
            _bad2.append(getattr(n, 'lineno', -1))
check(u'4.2 ★正控制：塞一条 `check(..., True)` 后同一个检查必须报出来（证明 4.1 非恒真）',
      len(_bad2) == 1, u'抓到 %d 处' % len(_bad2))

# ---------------------------------------------------------------- ⑤ 逐令牌回验
head(u'⑤ 逐令牌回验（注释里每条可检索的断言都回原文件核一次）')
TOKENS = [
    (u'main.py 14171 行的「只发 persona，一个字节都不变」',
     MAIN, u'只发 persona，一个字节都不变'),
    (u'main.py 里的 `lean=True` 调用点', MAIN, u'lean=True'),
    (u'`_clean_ai_reply` 存在', MAIN, u'def _clean_ai_reply'),
    (u'`strip_action_parentheticals` 的文档串（只认动作/描述/引号）',
     TARGET, u'动作旁白'),
    (u'本轮取证脚本 diag133.py 真在盘上', None, None),
    (u'本轮回归锁 check133.py 真在盘上', None, None),
    (u'`_META_LEAK_RES` 五个规则仍在', TARGET, u'我不该.{0,12}(开头|语气|问一句|留个)'),
    (u'「第132轮」的出处注释仍在（跨轮指针没断）', TARGET, u'第132轮'),
    (u'「第133轮」的新指针在位', TARGET, u'第133轮'),
]
for desc, path, tok in TOKENS:
    if path is None:
        p = os.path.join(ROUND, '_tools',
                         'diag133.py' if 'diag133' in desc else 'check133.py')
        check(u'5 文件存在：%s' % desc, os.path.isfile(p), p)
        continue
    body = io.open(path, 'r', encoding='utf-8', newline='').read()
    check(u'5 回验：%s' % desc, tok in body, u'缺 %r' % tok)

# 负控制：一个**故意不存在**的令牌必须验不过（证明上面的检查有鉴别力）
check(u'5.n ★负控制：编一个不存在的令牌必须判 False',
      u'这段令牌绝对不存在-133' not in TEXT)

# ---------------------------------------------------------------- ⑥ 工作区 / 回归
head(u'⑥ 工作区与回归')
r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True)
_porc = r.stdout.decode('utf-8', 'replace')
print(_porc or u'(工作区干净)')
check(u'6.1 git status 可执行', r.returncode == 0)
check(u'6.2 本轮只该动这几处（人设/记忆文件不许被捎带改）',
      not any(x in _porc for x in (u'ralsei_persona.md', u'assets/npc/')),
      u'检出 %d 个改动路径' % len([x for x in _porc.splitlines() if x.strip()]))
check(u'6.3 回归锁的结论由 run_all 负责，这里只断言"它跑过"（不写死 PASS 数）',
      os.path.isfile(os.path.join(ROOT, 'code-quality-audit', 'regress', '_out',
                                  'check133.txt')))

print(u'')
print(u'=' * 78)
print(u'recheck133_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
