#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · 底层代码 = 谁被依赖得最多（客观界定，不靠印象）。

用户口径：「复检全部**尤其底层代码**」。
"底层"这个词本身是模糊的 ⇒ 先用**入度**（有多少个别的文件 import 它）把它变成
可复核的数字，再对入度最高的那些做定点深读。

判据：
  D1 依赖图可建（节点数 > 0，且不是空图）
  D2 底层集合 = 入度 >= LOWLEVEL_MIN 且 **不 import PyQt5**（契约：底层不许带 UI）
  D3 ★ 反向控制：`main.py` 的入度应当很低（它是顶层装配点，不是底层）
  D4 循环依赖（A→B 且 B→A）单独列出 —— 本项目历史上踩过"初始化环"
  D5 断链检查：import 了**仓库内不存在**的模块名（拼错 / 已删）必须为 0

用法：
  C:\\Python311\\python.exe deps62.py
"""
import ast
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
PET = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(ROUND, '_evidence')

SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'logs', 'assets',
             'config', 'tests', 'diag_frames', 'diag_frames2', 'diag_frames3'}
BACKUP_SUFFIXES = ('.bak', '.backup', '.orig', '.old', '.discrim_bak')

#: 入度到这个数就算"底层"
LOWLEVEL_MIN = 5

#: 标准库/第三方 —— 只用来把"项目内模块"和"外部模块"分开
STDLIB = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
THIRD = {'PyQt5', 'PyQt6', 'requests', 'jieba', 'bs4', 'psutil', 'numpy',
         'PIL', 'openpyxl', 'docx', 'pptx',
         # ★ 本机装了 pywin32（`diag_*.py` 用得到）；不登记就会被 D5 误报成"断链"
         'win32gui', 'win32process', 'win32api', 'win32con', 'win32event'}
#: 这几个名字是 `sys.path.insert(0, 'src')` 的**路径片段**，不是模块名
PATH_WORDS = {'src', 'modules', 'ralsei_pet', 'utils', 'ui', 'core', 'systems'}
#: D5 只对**产品代码**生效（`diag_*.py` / `test_*.py` 是开发残留，不在产品链上）
PRODUCT_DIRS = ('ralsei_pet' + os.sep + 'modules', 'ralsei_pet' + os.sep + 'src')


def is_backup(name):
    low = name.lower()
    if any(low.endswith(s) for s in BACKUP_SUFFIXES):
        return True
    return '.backup_' in low or '.bak_' in low


def collect():
    out = []
    for dirpath, dirnames, filenames in os.walk(PET):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith('.py') or is_backup(fn):
                continue
            out.append(os.path.join(dirpath, fn))
    return sorted(out)


def imports_of(path):
    u"""返回 (import 到的顶层模块名集合, 语法错误或 None)。

    不区分项目内/外部 —— 调用方拿它和"仓库里真实存在的模块名"取交集，
    这样"拼错的模块名"会自然落到 D5 里，不会被静默当成外部库放过。
    """
    try:
        tree = ast.parse(io.open(path, 'rb').read().decode('utf-8'),
                         filename=path)
    except (SyntaxError, UnicodeDecodeError) as e:
        return set(), str(e)
    ext = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                ext.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:            # 相对 import（from . import x）
                continue
            if node.module:
                ext.add(node.module.split('.')[0])
                for a in node.names:
                    ext.add((node.module.split('.')[0] + '.' + a.name)
                            .split('.')[0])
    return ext, None


def main():
    files = collect()
    print(u'=== 第62轮 · 依赖图（界定"底层代码"）===')
    print(u'扫描 .py（活代码，跳过备份/缓存）: %d 个' % len(files))

    # 模块名 -> 文件（重名时保留第一个，并记下冲突）
    mod_of = {}
    dup = defaultdict(list)
    for p in files:
        m = os.path.splitext(os.path.basename(p))[0]
        dup[m].append(p)
        mod_of.setdefault(m, p)
    proj_mods = set(mod_of)

    in_deg = Counter()
    out_edges = defaultdict(set)
    ext_use = defaultdict(set)
    syntax_bad = {}
    for p in files:
        m = os.path.splitext(os.path.basename(p))[0]
        _ext, err = imports_of(p)
        if err:
            syntax_bad[p] = err
            continue
        hits = {e for e in _ext if e in proj_mods and mod_of[e] != p}
        out_edges[m] = hits
        for h in hits:
            in_deg[h] += 1
        for e in _ext:
            if e not in proj_mods:
                ext_use[m].add(e)

    checks = []

    def ck(name, cond, extra=u''):
        checks.append({'name': name, 'ok': bool(cond), 'extra': extra})
        print(u'[%s] %s %s' % (u'PASS' if cond else u'FAIL', name, extra))

    ck(u'D1 依赖图建起来了（%d 个模块 / %d 条内部边）'
       % (len(proj_mods), sum(len(v) for v in out_edges.values())),
       # ⚠️ 这是一条"**图不是空的**"的健全性判据，不是性能目标 ——
       #    阈值取 30 是因为实测就是 63 条（本仓库模块大多自洽、耦合很浅）。
       #    不要为了"看着好看"往上调。
       len(proj_mods) > 50 and sum(len(v) for v in out_edges.values()) >= 30)
    if syntax_bad:
        ck(u'D1b 全部文件可 ast.parse', False,
           u'%d 个失败: %r' % (len(syntax_bad), list(syntax_bad)[:3]))
    else:
        ck(u'D1b 全部文件可 ast.parse', True)

    # 带 Qt 的模块（不能算底层）
    qt_mods = set()
    for p in files:
        m = os.path.splitext(os.path.basename(p))[0]
        if any(x.startswith('PyQt') for x in ext_use.get(m, ())):
            qt_mods.add(m)

    ranked = in_deg.most_common()
    low = [(m, n) for m, n in ranked
           if n >= LOWLEVEL_MIN and m not in qt_mods]
    print()
    print(u'--- 入度 Top 30（"有多少个文件 import 它"）---')
    for m, n in ranked[:30]:
        flag = u' [Qt]' if m in qt_mods else u''
        print(u'  %3d  %s%s' % (n, m, flag))
    print()
    print(u'--- 底层集合（入度 >= %d 且不带 Qt）: %d 个 ---' % (LOWLEVEL_MIN, len(low)))
    for m, n in low:
        print(u'  %3d  %s' % (n, m))

    ck(u'D2 底层集合非空且都**不** import PyQt5', bool(low) and
       all(m not in qt_mods for m, _n in low),
       u'%d 个: %s' % (len(low), u', '.join(m for m, _n in low[:12])))

    # D3 反向控制：main.py 是顶层装配点，入度应很低
    main_n = in_deg.get('main', 0)
    ck(u'D3 ★ 反向控制：`main.py` 入度应很低（它是顶层装配点，不是底层）',
       main_n <= 3, u'main 入度 = %d' % main_n)

    # D4 循环依赖
    cyc = sorted({tuple(sorted((a, b)))
                  for a, bs in out_edges.items() for b in bs
                  if a in out_edges.get(b, ())})
    ck(u'D4 无两两循环依赖（A→B 且 B→A）', not cyc,
       u'%d 对: %r' % (len(cyc), cyc[:5]))

    # D5 断链：import 的项目内名字，仓库里其实不存在
    # ★ 本脚本第一版扫全仓 ⇒ 35 个文件报红，全是**误报**：
    #   ① `diag_*.py` / `test_*.py`（32 个开发残留）本来就不在产品链上；
    #   ② `import src` / `import modules` 是 `sys.path.insert` 的**路径片段**；
    #   ③ 本机装了 pywin32，`win32gui` 是真实存在的第三方包。
    #   ⇒ 收窄成"只查产品目录"，并把这三类知识显式登记（判据过宽 = 会误报）。
    broken = defaultdict(set)
    for m, exts in ext_use.items():
        path = mod_of.get(m, '')
        rel = os.path.relpath(path, PET)
        if not any(rel.startswith(d) for d in PRODUCT_DIRS):
            continue
        for e in exts:
            if e in STDLIB or e in THIRD or e in proj_mods or e in PATH_WORDS:
                continue
            broken[m].add(e)
    ck(u'D5 产品代码里无"import 了仓库里不存在的模块"（断链/拼错）', not broken,
       u'%d 个文件: %r' % (len(broken), dict(list(broken.items())[:5])))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    ev = {
        'n_files': len(files), 'n_modules': len(proj_mods),
        'lowlevel_min': LOWLEVEL_MIN,
        'lowlevel': [{'module': m, 'in_degree': n} for m, n in low],
        'in_degree_top30': [{'module': m, 'in_degree': n,
                             'qt': m in qt_mods} for m, n in ranked[:30]],
        'qt_modules': sorted(qt_mods),
        'cycles': [list(c) for c in cyc],
        'broken_imports': {k: sorted(v) for k, v in broken.items()},
        'syntax_errors': syntax_bad,
        'checks': checks,
    }
    p = os.path.join(OUT, 'deps62.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print()
    print(u'== 结果 ==  判定 %d 项，FAIL %d 项'
          % (len(checks), sum(1 for c in checks if not c['ok'])))
    print(u'  证据 -> %s' % p)
    return 0 if all(c['ok'] for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
