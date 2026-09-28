#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · 收尾复检（六类判据，逐项 PASS/FAIL 落盘）。

为什么必须有它：本轮改了**产品数据**（12 份人设正文 + `_personas.json` 索引）。
按项目铁律「改过重要核心文件必须复检」—— 不许只说"改完了"，要逐项自证。

六类（与 skill `core-file-recheck` 同形）
----------------------------------------
R1 语法/可解析：所有本轮新增/改动的 .py 都能 `ast.parse`（**不用 `py_compile`**，
   它会产 `.pyc` 从而改变被测状态）。
R2 结构：① 13 份人设都以 SPEAK_RULES 尾部收束（说明删除没破坏结构）
   ② 索引仍是 13 条且带 `extraction_fix`。
R3 编码：本轮涉及的人设文件与证据 JSON 无 BOM、无 U+FFFD。
R4 **恒真判据复查**：本轮新写工具里不得出现 `check(名字, True)` / `ok(名字, True)`
   这类"看着在守其实没守"的写法。
R5 **逐令牌回验**：索引的 `sha256/bytes/chars` 与磁盘逐条一致（**按保留 EOL 读**）；
   并且那条"下一个角色的开场白"必须**已不在任何一份人设里**。
R6 工作区：`git status --porcelain` 的改动集合 ⊆ 本轮预期。

用法：
  C:\\Python311\\python.exe -X utf8 recheck62.py
"""
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
NPC = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
OUT = os.path.join(ROUND, '_evidence')

RESULTS = []


def ck(name, cond, extra=u''):
    RESULTS.append({'name': name, 'ok': bool(cond), 'extra': extra})
    print(u'[%s] %s %s' % (u'PASS' if cond else u'FAIL', name, extra))


def info(name, extra=u''):
    u"""纯信息行（不算判据）。

    ★ 为什么要有它：R4b 原本写成 `ck(名字, True, 豁免清单)` —— 外观是断言、
    实际没守任何东西。R4 规则立刻把它自己抓出来了（`recheck62.py:189`）。
    这正说明"信息就该长得像信息"，别借 `ck` 的壳。见项目铁律
    「判据串 no-op 必须显式打印，否则假绿」。
    """
    RESULTS.append({'name': name, 'ok': True, 'info': True, 'extra': extra})
    print(u'[INFO] %s %s' % (name, extra))


def read(p):
    return io.open(p, 'rb').read()


def src_text(p):
    return read(p).decode('utf-8', 'replace')


# --------------------------------------------------------------- R1
def r1():
    bad = []
    files = []
    for d in (HERE, OUT):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith('.py'):
                files.append(os.path.join(d, f))
    for f in files:
        try:
            ast.parse(src_text(f), filename=f)
        except Exception as e:
            bad.append((os.path.basename(f), repr(e)[:60]))
    ck(u'R1 本轮 .py 全部可 ast.parse（检查 %d 个）' % len(files), not bad,
       u'%r' % (bad[:3],))
    ck(u'R1b 负控制：故意坏语法必须被判不可解析', _parse_fails(u'def (:\n'))


def _parse_fails(text):
    try:
        ast.parse(text)
        return False
    except SyntaxError:
        return True


# --------------------------------------------------------------- R2
#: ★ 第一版把整句写死成 `不要用"主人"…称呼用户` 并要求 `endswith` —— 结果报"13 份全未收束"。
#:   真相：① 文件里用的是**全角引号**，我字面量写的是 ASCII 引号；② 该句之后还有半句
#:   `；按你的性格直接称呼"你"。`，所以 `endswith` 本来就不成立。
#:   ⇒ 判据窄到只能匹配我脑子里的那份文本（**判据过窄 = 会误报**）。
#:   现在改用两个**短词元**做子串判定，不再依赖标点与位置。
SPEAK_TOKENS = (u'服务腔', u'称呼用户')


def r2():
    idx = json.load(io.open(os.path.join(NPC, '_personas.json'), encoding='utf-8'))
    ps = idx.get('personas') or []
    ck(u'R2a 索引仍是 13 条', len(ps) == 13, u'实际 %d' % len(ps))
    tails = []
    for it in ps:
        t = src_text(os.path.join(NPC, it['file']))
        last = [l for l in t.split(u'\n') if l.strip()]
        last = last[-1] if last else u''
        tails.append((it['id'], last, all(k in last for k in SPEAK_TOKENS)))
    bad = [x[0] for x in tails if not x[2]]
    ck(u'R2b 13 份人设末行都是 SPEAK_RULES 收束句（结构未被删坏）', not bad,
       u'未收束: %r' % (bad[:3],))
    ck(u'R2b2 负控制：把末行换成别的文本必须被判未收束',
       not all(k in u'随便一句别的' for k in SPEAK_TOKENS))
    ck(u'R2c 索引带 extraction_fix 记录（可追溯本轮改了什么）',
       isinstance(idx.get('extraction_fix'), dict))


# --------------------------------------------------------------- R3
def r3():
    bad = []
    for it in (json.load(io.open(os.path.join(NPC, '_personas.json'),
                                 encoding='utf-8')).get('personas') or []):
        p = os.path.join(NPC, it['file'])
        raw = read(p)
        t = raw.decode('utf-8', 'replace')
        if raw[:3] == b'\xef\xbb\xbf' or u'\ufffd' in t:
            bad.append(it['id'])
    ck(u'R3a 13 份人设无 BOM / 无 U+FFFD', not bad, u'%r' % (bad[:3],))
    bad2 = []
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(('.json', '.txt')):
            continue
        raw = read(os.path.join(OUT, f))
        try:
            t = raw.decode('utf-8')
        except UnicodeDecodeError:
            bad2.append(f)
            continue
        if raw[:3] == b'\xef\xbb\xbf' or u'\ufffd' in t:
            bad2.append(f)
    ck(u'R3b 证据区无 BOM / 无 U+FFFD', not bad2, u'%r' % (bad2[:3],))


# --------------------------------------------------------------- R4
#: ★ 第一版用**正则**扫行 —— 结果三处误报：docstring 里提到 `check(..., True)`、
#:   自检样本的**字符串字面量**里写着 `check('L1', True, ...)`、
#:   以及 `if bad: FAIL / else: PASS` 这种**守卫分支**里的合法 `True`。
#:   ⇒ 改走 **AST**（本项目铁律：能上 AST 就上 AST），并把"位于某个 `if` 的 `orelse`
#:   里"的 `True` 视为**守卫型**（等价于 `audit_truth62` 的 `guarded` 档）。
CK_FUNCS = ('check', 'ok', 'ck', 'expect', 'verify')


def _guarded_lines(tree):
    u"""收集"位于某个 If.orelse 子树内"的所有行号（守卫型兜底）。"""
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for st in node.orelse:
            for sub in ast.walk(st):
                if hasattr(sub, 'lineno'):
                    lines.add(sub.lineno)
    return lines


def _const_true_calls(tree):
    u"""2 号实参是字面量 True 的断言调用。"""
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        nm = getattr(f, 'id', None) or getattr(f, 'attr', None)
        if nm not in CK_FUNCS or len(node.args) < 2:
            continue
        a = node.args[1]
        if isinstance(a, ast.Constant) and a.value is True:
            hits.append(node.lineno)
    return hits


def _else_above(src, ln):
    u"""**文本 oracle**：第 ln 行是否位于某个 `else:` 之下（缩进回退到最近更浅行）。

    与 AST 的 `If.orelse` 是**两套独立机制** ⇒ 可用来交叉验证 AST 判定，
    避免"用同一个函数自证同一个结论"的恒真。
    """
    lines = src.split(u'\n')
    idx = ln - 1
    if not (0 <= idx < len(lines)):
        return False
    tgt = lines[idx]
    tind = len(tgt) - len(tgt.lstrip())
    for j in range(idx - 1, -1, -1):
        s = lines[j]
        if not s.strip():
            continue
        if (len(s) - len(s.lstrip())) < tind:
            return s.strip().startswith(u'else')
    return False


def r4():
    hollow, guarded = [], []
    files = [f for f in sorted(os.listdir(HERE)) if f.endswith('.py')]
    for f in files:
        try:
            tree = ast.parse(src_text(os.path.join(HERE, f)), filename=f)
        except SyntaxError:
            continue
        g = _guarded_lines(tree)
        for ln in _const_true_calls(tree):
            (guarded if ln in g else hollow).append(u'%s:%d' % (f, ln))
    ck(u'R4 本轮 %d 个工具无"非守卫型"的 check(名字, True)' % len(files),
       not hollow, u'%r' % (hollow[:4],))
    # R4b：用**独立机制**复核每一条"守卫型"豁免（AST 说是 orelse ⇒ 文本 oracle 说是 else 下）
    off = [lab for lab in guarded
           if not _else_above(src_text(os.path.join(HERE, lab.rsplit(u':', 1)[0])),
                              int(lab.rsplit(u':', 1)[1]))]
    info(u'R4b 守卫型豁免清单', u'%r' % (guarded,))
    ck(u'R4b2 ★ 独立复核：豁免项确实位于 `else:` 之下（%d 项）' % len(guarded),
       not off, u'与 AST 不符: %r' % (off[:3],))
    # 正控制：合成的 bare True 必须被 AST 抓到；合成的守卫型必须进豁免
    t1 = ast.parse(u'check("x", True)\n')
    t2 = ast.parse(u'if bad:\n    check("x", False)\nelse:\n    check("x", True)\n')
    ck(u'R4c 正控制：裸 check(..., True) 必须被抓到', bool(_const_true_calls(t1)))
    ck(u'R4d 正控制：守卫型 check(..., True) 必须落进豁免而不是裸红',
       _const_true_calls(t2) and bool(_guarded_lines(t2)))
    ck(u'R4e 正/负控制：文本 oracle 对 `else:` 之下返回 True、对裸行返回 False',
       _else_above(u'if x:\n    pass\nelse:\n    check("y", True)\n', 4)
       and not _else_above(u'check("y", True)\n', 1))


# --------------------------------------------------------------- R5
def r5():
    idx = json.load(io.open(os.path.join(NPC, '_personas.json'), encoding='utf-8'))
    bad = []
    for it in idx['personas']:
        t = read(os.path.join(NPC, it['file'])).decode('utf-8')
        b = t.encode('utf-8')
        if (len(t) != it.get('chars') or len(b) != it.get('bytes')
                or hashlib.sha256(b).hexdigest() != it.get('sha256')):
            bad.append(it['id'])
    ck(u'R5a 索引 sha256/bytes/chars 与磁盘逐条一致（保留 EOL 读）', not bad,
       u'不一致: %r' % (bad[:3],))
    # 逐令牌回验：那条外来开场白必须已不在任何一份人设里
    MARK = u'以下是一段可直接用于 AI 角色扮演的 system prompt'
    left = [it['id'] for it in idx['personas']
            if MARK in read(os.path.join(NPC, it['file'])).decode('utf-8')]
    ck(u'R5b 逐令牌回验：外来开场白行已从全部 13 份消失', not left,
       u'仍有: %r' % (left[:3],))


# --------------------------------------------------------------- R6
#: ★ 第一版直接读 `git status --porcelain` —— git 默认 `core.quotepath=true`，
#:   把非 ASCII 路径转义成 `"code-quality-audit/\347\254\25462..."`，
#:   于是 `startswith(中文前缀)` 永不命中 ⇒ 报 2 个**假**"意外项"。
#:   ⇒ 用 `-c core.quotepath=false -z`：既不转义、也天然规避含空格路径被加引号。
R6_ALLOWED = (
    'ralsei_pet/assets/npc/',
    u'code-quality-audit/第62轮-复检与7B人设实测/',
    u'第六十二轮复检与7B人设实测报告',
)


def _r6_parse(raw):
    u"""把 `git status --porcelain -z` 的字节解析成 ['XY path', ...]。"""
    entries = []
    for f in [x for x in raw.split(b'\x00') if x]:
        s = f.decode('utf-8', 'replace')
        # `-z` 下重命名是「`R  new`\0`old`」两段 ⇒ 第 2 段没有 "XY " 头
        if len(s) >= 3 and s[2] == u' ' and s[:2].strip():
            entries.append(s)
        elif entries:
            entries[-1] = entries[-1] + u' -> ' + s
    return entries


def _r6_extra(entries, allowed_pref):
    u"""不在本轮预期前缀内的条目（纯函数，便于负控制）。"""
    return [l for l in entries if not l[3:].startswith(allowed_pref)]


def r6():
    try:
        out = subprocess.run(
            ['git', '-c', 'core.quotepath=false', 'status', '--porcelain', '-z'],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        entries = _r6_parse(out.stdout)
    except Exception as e:
        ck(u'R6 工作区状态可读', False, repr(e)[:80])
        return
    extra = _r6_extra(entries, R6_ALLOWED)
    ck(u'R6 工作区改动 ⊆ 本轮预期（%d 项）' % len(entries), not extra,
       u'意外项: %r' % (extra[:3],))
    ck(u'R6b 负控制：仓库外路径必须被判为意外项',
       bool(_r6_extra([u'?? src/evil.py'], R6_ALLOWED)))
    ck(u'R6c 负控制：路径解析不得残留转义（无 \\\\3xx 八进制）',
       not any(u'\\3' in l for l in entries))
    for l in entries:
        print(u'      %s' % l[:110])


def main():
    print(u'=== 第62轮 · 收尾复检（六类）===')
    for fn in (r1, r2, r3, r4, r5, r6):
        fn()
    print()
    n_fail = sum(1 for r in RESULTS if not r['ok'])
    n_info = sum(1 for r in RESULTS if r.get('info'))
    print(u'合计：判据 %d 项（另信息 %d 项），FAIL %d 项'
          % (len(RESULTS) - n_info, n_info, n_fail))
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    p = os.path.join(OUT, 'recheck62.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'results': RESULTS, 'n_fail': n_fail},
                            ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % p)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
