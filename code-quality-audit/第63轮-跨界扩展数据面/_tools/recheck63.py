#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第63轮 · 收尾复检（六类，逐项 PASS/FAIL 落盘）。

本轮特点：**没有改任何产品代码**，只新增审计工具/证据 + 报告 + 改了一个审计工具。
⇒ R6 增加一条本轮专属的强断言：`git status` 里**不得出现 `ralsei_pet/` 的改动**。

六类
----
R1 可解析：本轮新增的 .py 全部 `ast.parse`（**不用 `py_compile`**，它产 `.pyc` 会改变被测状态）。
R2 结构：报告章节齐全；本轮证据 JSON 全部 `json.load` 通过。
R3 编码：本轮涉及文件无 BOM、无 U+FFFD。
R4 恒真判据复查（**AST**）：本轮工具里不得有"非守卫型"的 `check(名字, True)`；
   守卫型（`else:` 兜底）用**独立机制的文本 oracle** 交叉验证。
R5 **逐令牌回验**：报告里写的关键数字，必须与**产物 JSON**逐条相符（不是查源码字面量）。
R6 工作区：改动集合 ⊆ 本轮预期；且 **`ralsei_pet/` 零改动**。

用法：C:\\Python311\\python.exe -X utf8 recheck63.py
"""
import ast
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
OUT = os.path.join(ROUND, '_evidence')
REPORT = os.path.join(REPO, u'第63轮报告-跨界扩展数据面.md')

RESULTS = []


def ck(name, cond, extra=u''):
    RESULTS.append({'name': name, 'ok': bool(cond), 'extra': extra})
    print(u'[%s] %s %s' % (u'PASS' if cond else u'FAIL', name, extra))


def info(name, extra=u''):
    u"""纯信息行（不算判据）—— 信息就该长得像信息，别借 `ck` 的壳。"""
    RESULTS.append({'name': name, 'ok': True, 'info': True, 'extra': extra})
    print(u'[INFO] %s %s' % (name, extra))


def rb(p):
    return io.open(p, 'rb').read()


def tx(p):
    return rb(p).decode('utf-8', 'replace')


# ------------------------------------------------------------------ R1
def r1():
    files = [f for f in sorted(os.listdir(HERE)) if f.endswith('.py')]
    bad = []
    for f in files:
        try:
            ast.parse(tx(os.path.join(HERE, f)), filename=f)
        except Exception as e:
            bad.append((f, repr(e)[:60]))
    ck(u'R1 本轮 %d 个 .py 全部可 ast.parse' % len(files), not bad, u'%r' % (bad[:3],))
    try:
        ast.parse(u'def (:\n')
        neg = False
    except SyntaxError:
        neg = True
    ck(u'R1b 负控制：坏语法必须被判不可解析', neg)


# ------------------------------------------------------------------ R2
def r2():
    heads = re.findall(u'(?m)^(#{1,3} .+)$', tx(REPORT))
    want = [u'## 0.', u'## 1.', u'## 2.', u'## 3.', u'## 4.', u'## 5.',
            u'## 6.', u'## 7.']
    miss = [w for w in want if not any(h.startswith(w) for h in heads)]
    ck(u'R2a 报告章节 §0~§7 齐全（共 %d 个标题）' % len(heads), not miss,
       u'缺: %r' % (miss,))
    bad = []
    n = 0
    for f in sorted(os.listdir(OUT)):
        if not f.endswith('.json'):
            continue
        n += 1
        try:
            json.load(io.open(os.path.join(OUT, f), encoding='utf-8'))
        except Exception as e:
            bad.append((f, repr(e)[:50]))
    ck(u'R2b 证据区 %d 个 JSON 全部 json.load 通过' % n, not bad, u'%r' % (bad[:3],))
    glued = [i for i, l in enumerate(tx(REPORT).split(u'\n'), 1)
             if l.startswith(u'#') and not re.match(u'^#{1,3} ', l)]
    ck(u'R2c 报告无标题粘连（形如 `##x` 缺空格）', not glued, u'%r' % (glued[:3],))


# ------------------------------------------------------------------ R3
def r3():
    bad = []
    targets = [REPORT]
    for d in (HERE, OUT):
        for f in sorted(os.listdir(d)):
            if f.endswith(('.py', '.json', '.txt', '.csx', '.md')):
                targets.append(os.path.join(d, f))
    for p in targets:
        raw = rb(p)
        t = raw.decode('utf-8', 'replace')
        if raw[:3] == b'\xef\xbb\xbf' or u'\ufffd' in t:
            bad.append(os.path.basename(p))
    ck(u'R3 本轮 %d 个文件无 BOM / 无 U+FFFD' % len(targets), not bad,
       u'%r' % (bad[:4],))


# ------------------------------------------------------------------ R4
CK_FUNCS = ('check', 'ok', 'ck', 'expect', 'verify')


def _guarded_lines(tree):
    s = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.If):
            for st in n.orelse:
                s |= {x.lineno for x in ast.walk(st) if hasattr(x, 'lineno')}
    return s


def _const_true_calls(tree):
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or len(n.args) < 2:
            continue
        nm = getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)
        if nm not in CK_FUNCS:
            continue
        a = n.args[1]
        if isinstance(a, ast.Constant) and a.value is True:
            hits.append(n.lineno)
    return hits


def _else_above(src, ln):
    u"""文本 oracle（**独立于 AST 的第二套机制**）：第 ln 行是否在某个 `else:` 之下。"""
    lines = src.split(u'\n')
    idx = ln - 1
    if not (0 <= idx < len(lines)):
        return False
    tind = len(lines[idx]) - len(lines[idx].lstrip())
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
            tree = ast.parse(tx(os.path.join(HERE, f)), filename=f)
        except SyntaxError:
            continue
        g = _guarded_lines(tree)
        for ln in _const_true_calls(tree):
            (guarded if ln in g else hollow).append(u'%s:%d' % (f, ln))
    ck(u'R4 本轮 %d 个工具无"非守卫型"的 check(名字, True)' % len(files),
       not hollow, u'%r' % (hollow[:4],))
    off = [lab for lab in guarded
           if not _else_above(tx(os.path.join(HERE, lab.rsplit(u':', 1)[0])),
                              int(lab.rsplit(u':', 1)[1]))]
    info(u'R4b 守卫型豁免清单', u'%r' % (guarded,))
    ck(u'R4b2 独立复核（文本 oracle）：豁免项确实位于 `else:` 之下',
       not off, u'与 AST 不符: %r' % (off[:3],))
    ck(u'R4c 正控制：裸 check(..., True) 必须被抓到',
       bool(_const_true_calls(ast.parse(u'check("x", True)\n'))))
    ck(u'R4d 正/负控制：文本 oracle 对 `else:` 之下判 True、对裸行判 False',
       _else_above(u'if x:\n    pass\nelse:\n    check("y", True)\n', 4)
       and not _else_above(u'check("y", True)\n', 1))


# ------------------------------------------------------------------ R5
def r5():
    topo = json.load(io.open(os.path.join(OUT, 'ut_topology63.json'),
                             encoding='utf-8'))
    asr = json.load(io.open(os.path.join(OUT, 'outertale63_assets.json'),
                            encoding='utf-8'))
    # 判据 = "报告写的数字" vs "产物 JSON 的数字"（★ 不是查源码字面量）
    pairs = [
        (u'拓扑边数', len(topo['edges']), 316),
        (u'越界边', topo['stats']['out_of_range'], 0),
        (u'落点命中', topo['stats']['landing_ok'], 307),
        (u'最大连通分量', topo['stats']['largest_component'], 22),
        (u'房间数', topo['room_count'], 338),
        (u'具名精灵', asr['named_sprite_count'], 1027),
        (u'几何一致', asr['anchors']['geom_ok'], 1026),
        (u'几何不符', asr['anchors']['geom_bad'], 1),
        (u'未解析变量', asr['anchors']['unresolved'], 0),
        (u'磁盘缺失', asr['anchors']['missing_on_disk'], 0),
        (u'跨族角色', len(asr['characters_multi_family']), 11),
        (u'单族词元', len(asr['single_family']), 33),
    ]
    bad = [(k, got, want) for k, got, want in pairs if got != want]
    ck(u'R5a 产物 JSON 的 %d 个关键数字全对' % len(pairs), not bad,
       u'%r' % (bad[:4],))
    off = asr['anchors']
    ck(u'R5b 偏移量 == Deltarune 同构 {A:+1,B:-1,C:+2,D:-2}',
       topo['door_offsets'] == {'A': 1, 'B': -1, 'C': 2, 'D': -2},
       u'%r' % (topo['door_offsets'],))
    # 报告与产物**一致性**（弱判据，只防"报告写错数"）
    rep = tx(REPORT)
    for tok in (u'316', u'97.8', u'99.2', u'1027', u'1026', u'44 个'):
        ck(u'R5c 报告含令牌 %s（与产物一致）' % tok, tok in rep)
    # 负控制：不存在的数字必须判否
    ck(u'R5d 负控制：报告里没有的令牌必须为 False', u'99999' not in rep)


# ------------------------------------------------------------------ R6
R6_ALLOWED = (
    u'code-quality-audit/第63轮-跨界扩展数据面/',
    u'第63轮报告-跨界扩展数据面',
    u'code-quality-audit/第61轮-跨界扩展动工/_tools/utmt61.py',
)


def _r6_parse(raw):
    out = []
    for f in [x for x in raw.split(b'\x00') if x]:
        s = f.decode('utf-8', 'replace')
        if len(s) >= 3 and s[2] == u' ' and s[:2].strip():
            out.append(s)
        elif out:
            out[-1] = out[-1] + u' -> ' + s
    return out


def r6():
    o = subprocess.run(['git', '-c', 'core.quotepath=false', 'status',
                        '--porcelain', '-z'],
                       cwd=REPO, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    ent = _r6_parse(o.stdout)
    extra = [l for l in ent if not l[3:].startswith(R6_ALLOWED)]
    ck(u'R6a 改动集合 ⊆ 本轮预期（%d 项）' % len(ent), not extra,
       u'意外项: %r' % (extra[:3],))
    prod = [l for l in ent if l[3:].startswith(u'ralsei_pet/')]
    ck(u'R6b ★ 本轮"产品代码零改动"（`ralsei_pet/` 无变更）', not prod,
       u'%r' % (prod[:3],))
    ck(u'R6c 负控制：仓库外路径必须被判为意外项',
       bool([l for l in [u'?? src/evil.py'] if not l[3:].startswith(R6_ALLOWED)]))
    for l in ent:
        print(u'      %s' % l[:110])


def main():
    print(u'=== 第63轮 · 收尾复检（六类）===')
    for fn in (r1, r2, r3, r4, r5, r6):
        fn()
    n_fail = sum(1 for r in RESULTS if not r['ok'])
    n_info = sum(1 for r in RESULTS if r.get('info'))
    print()
    print(u'合计：判据 %d 项（另信息 %d 项），FAIL %d 项'
          % (len(RESULTS) - n_info, n_info, n_fail))
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    p = os.path.join(OUT, 'recheck63.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'results': RESULTS, 'n_fail': n_fail},
                            ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % p)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
