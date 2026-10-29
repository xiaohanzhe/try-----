# -*- coding: utf-8 -*-
u"""第118轮：把可读物 Alarm 的 GML 解析成「(房间, 条件, 键)」——解第二层守卫。

为什么改用 GML 文本而不是指令流
--------------------------------
第117轮抽的是指令流（`PushBltn{room}; PushI N; Cmp; Bf; Push '键'`），
它只能看到 `room == N` 这一层，**看不到 `&& x < 130` 之后的第二个条件**。
`UndertaleModCli dump -c <code>` 把控制流还原成了 `if (...) { ... }`，
读它才能看清第二层到底是什么。

实测到的第二层（ut 的 8 个 Alarm 全看过）：
    · 位置：`x < 130` / `x > 130` / `x < 204 && x > 144` / `y >= 125 && x > 800`
    · 剧情：`global.flag[7] == 1` / `global.plot < 126` / `scr_murderlv() >= 16` / `murdererlv1() == 1`
    · 实例：`read > 1` / `specialread > 1`
    · 另有 `global.msc = N`（正文不在本表里，交给 msc 脚本）

产出：`_evidence/readable_conds118.tsv`
    alarm    depth    cond                        target    key
`cond` 是 ` && ` 连接的**全部**外层条件（第 1 层通常是 `room == <名>`）。

用法：python conds118.py [--game ut]
"""
import argparse
import collections
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
RAW = os.path.join(ROUND, '_evidence', 'raw')

#: 反编译产物的临时目录（UTMT 跑在 D 盘）；解析完会蒸馏进 `_evidence/raw/<game>/gml_readable/`
GML_DIRS = {
    'ut': r'D:\_wb_tmp\dw_ut\gml_rd\CodeEntries',
    'outertale': r'D:\_wb_tmp\dw_ut\gml_rd_ot\CodeEntries',
}

RE_IF = re.compile(r'^if \((.*)\)$')
RE_ELSE_IF = re.compile(r'^else if \((.*)\)$')
RE_MSG = re.compile(r'^global\.msg\[(\d+)\]\s*=\s*scr_gettext\("([^"]+)"\);$')
RE_MSC = re.compile(r'^global\.msc\s*=\s*(\d+);$')


def parse_file(path):
    """→ [(conds(list), target, key)]，按出现顺序。"""
    with io.open(path, encoding='utf-8', errors='replace', newline='') as f:
        lines = f.read().splitlines()

    stack = {}          # depth -> cond 字符串
    pending = None      # 等待 `{` 落位的 if 条件
    pending_else = False
    depth = 0
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = RE_IF.match(s)
        if m:
            pending = m.group(1)
            pending_else = False
            continue
        m = RE_ELSE_IF.match(s)
        if m:
            # `else if (c)` ⇒ 语义上还带着上一个 if 的否定，但这里只做**数据绑定**，
            # 记录成 `!(上一条) && c` 会把条件变成不可判；本脚本改为**照实标 `ELSE_IF`**，
            # 由下游决定要不要用（不猜）。
            pending = 'ELSE_IF: ' + m.group(1)
            pending_else = True
            continue
        if s == 'else':
            pending = 'ELSE_OF: ' + str(stack.get(depth) or '')
            pending_else = True
            continue
        if s == '{':
            depth += 1
            if pending is not None:
                stack[depth] = pending
                pending = None
            else:
                stack[depth] = None
            continue
        if s == '}':
            stack.pop(depth, None)
            if depth > 0:
                depth -= 1
            continue

        m = RE_MSG.match(s)
        if m:
            conds = [stack[d] for d in range(1, depth + 1) if stack.get(d)]
            out.append((conds, 'msg[%s]' % m.group(1), m.group(2)))
            continue
        m = RE_MSC.match(s)
        if m:
            conds = [stack[d] for d in range(1, depth + 1) if stack.get(d)]
            out.append((conds, 'msc', 'MSC_%s' % m.group(1)))
            continue
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default='ut')
    ap.add_argument('--gml-dir', default=None,
                    help='不给就按 --game 取 GML_DIRS；也可指向仓库内蒸馏副本 raw/<game>/gml_readable')
    a = ap.parse_args(argv)

    gml_dir = a.gml_dir or GML_DIRS.get(a.game)
    if not gml_dir or not os.path.isdir(gml_dir):
        print('[FAIL] 找不到反编译目录：%r（先跑 cli_help115.py dump）' % gml_dir)
        return 2
    out_path = os.path.join(ROUND, '_evidence', 'readable_conds118.%s.tsv' % a.game)

    files = sorted(f for f in os.listdir(gml_dir)
                   if f.startswith('gml_Object_obj_readable')
                   and f.endswith('_Alarm_0.gml'))
    if not files:
        print('[FAIL] %s 里没有任何 obj_readable*_Alarm_0.gml —— 先跑 dump' % gml_dir)
        return 2

    rows = []
    n_by_target = collections.Counter()
    n_msc = 0
    n_else = 0
    for f in files:
        alarm = f[:-4]
        for conds, target, key in parse_file(os.path.join(gml_dir, f)):
            if key.startswith('MSC_'):
                n_msc += 1
            for c in conds:
                if c.startswith(('ELSE_IF:', 'ELSE_OF:')):
                    n_else += 1
            rows.append((alarm, len(conds), ' && '.join(conds), target, key))
            n_by_target[target] += 1

    if not rows:
        print('[FAIL] 一条都没解析出来 —— 解析器没匹配上，别当成"没有条件"')
        return 1

    with io.open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(u'alarm\tdepth\tcond\ttarget\tkey\n')
        for r in rows:
            f.write(u'\t'.join(str(x) for x in r) + u'\n')

    print('[%s] 解析 %d 个 Alarm → %d 条赋值（msc %d / else 条件 %d）'
          % (a.game, len(files), len(rows), n_msc, n_else))
    print('     目标分布：%s' % dict(n_by_target))
    print('     写出 %s' % os.path.relpath(out_path, os.path.dirname(ROUND)))

    # 条件形态统计（看清第二层到底有哪几类）
    kinds = collections.Counter()
    for _a, _d, cond, _t, _k in rows:
        for atom in cond.split(' && '):
            if not atom:
                continue
            head = atom.split()[0]
            kinds[head] += 1
    print('     条件原子（按首词）：%s' % dict(kinds.most_common(12)))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
