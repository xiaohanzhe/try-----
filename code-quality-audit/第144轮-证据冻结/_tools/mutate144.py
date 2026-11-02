# -*- coding: utf-8 -*-
"""第144轮破坏性负控制：把本轮的每道闸**逐条打坏**，看它是否真会报红。

## 为什么必须做

第144轮改的东西全是"**静态登记**"（JSON 内容 / 写盘路径 / `.gitignore` 一行），
这类改动最容易写出**恒真判据**：断言"文件里有没有某个字符串"，只要自己写的时候
手滑把断言写成"总为真"，跑起来一样是绿的，而且**永远绿**。

⇒ 每道闸都要配一次"真把被测物改坏"的对照，且必须满足：
  (a) 破坏**真的落进了被测分支**（打不上就报错，不许静默跳过）；
  (b) 报红的必须是**指定的那一条**，不是"某处红了"；
  (c) 恢复后必须**重新全绿**（否则说明我改坏了东西没还原）。

## 8 个破坏点

| # | 打坏什么 | 该谁红 |
|---|---|---|
| M1 | 冻结值 `files_scanned` 137 → 138 | A1 |
| M2 | `_note` 键改名（等于没说明） | A2 |
| M3 | `check138` 写盘指回 `_evidence/phase138.json` | A3 / A4 / B1 |
| M4 | `.gitignore` 删掉 `regress/_out/` 那行 | A5 |
| M5 | `check138` 写出的键改名（`bad_size` → `bad_size_`） | B2 |
| M6 | `eval113.merge_patches` 的「只有旧键⇒保留」分支改没 | C2 |
| M7 | 本套件自己的判据描述里塞计数标记字面量 | D1 |
| M8 | 扫描面塌掉（`.py` → `.pyz`，实扫 0 个） | B1b |

★ M7 / M8 打的是 `check144.py` **自己** —— "守别人的人自己不守"是本仓反复踩的坑，
  所以它俩必须能红，否则 D 段就是装饰。
"""
import io
import os
import shutil
import subprocess
import sys

PY = r'C:\Python311\python.exe'
HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
AUDIT = os.path.join(ROOT, 'code-quality-audit')
SELF = os.path.abspath(__file__)
CHECK144 = os.path.join(HERE, 'check144.py')
FROZEN = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_evidence',
                      'phase138.json')
CHECK138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools',
                        'check138.py')
EVAL113 = os.path.join(AUDIT, u'第113轮-全体角色AI训练', '_tools', 'eval113.py')
GITIGNORE = os.path.join(ROOT, '.gitignore')
BAK = os.path.join('D:\\_tmp', 'mut144')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=u''):
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


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def _run(suite):
    r = subprocess.run([PY, suite], cwd=os.path.dirname(suite),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


def _apply(path, pairs):
    """逐条替换，返回 (原文, 命中说明)。任何一条打不上就返回 None。"""
    src = _read(path)
    orig = src
    hits = []
    for old, new in pairs:
        # ★ 多行夹具要同时试 CRLF / LF：本仓踩过"夹具 0 处"却静默通过的坑。
        done = None
        for cand_o, cand_n in ((old, new),
                               (old.replace(u'\n', u'\r\n'),
                                new.replace(u'\n', u'\r\n'))):
            if cand_o and cand_o in src:
                src = src.replace(cand_o, cand_n, 1)
                done = u'CRLF' if u'\r\n' in cand_o else u'LF'
                break
        if done is None:
            return None, u'打不上：%s' % old[:40]
        hits.append(done)
    if src == orig:
        return None, u'空操作（替换前后一样）'
    _write(path, src)
    return orig, u'/'.join(hits)


def _drop_line(path, line):
    src = _read(path)
    for nl in (u'\r\n', u'\n'):
        pat = line + nl
        if pat in src:
            _write(path, src.replace(pat, u'', 1))
            return src, (u'CRLF' if nl == u'\r\n' else u'LF')
    return None, u'那一行不存在'


MUT = [
    ('M1', u'冻结值 `files_scanned` 137 → 138', FROZEN,
     [(u'"files_scanned": 137', u'"files_scanned": 138')], CHECK144, ['A1']),
    ('M2', u'`_note` 键改名（等于没有说明）', FROZEN,
     [(u'"_note":', u'"_note_removed":')], CHECK144, ['A2']),
    ('M3', u'`check138` 写盘指回 `_evidence/phase138.json`', CHECK138,
     [(u"_LIVE = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')",
       u"_LIVE = os.path.join(ROUND, '_evidence')"),
      (u"os.path.join(_LIVE, 'phase138.live.json')",
       u"os.path.join(_LIVE, 'phase138.json')")], CHECK144, ['A3', 'A4', 'B1']),
    ('M5', u'`check138` 写出的键改名（`bad_size`）', CHECK138,
     [(u"'bad_size': len(_bad_sz)", u"'bad_size_': len(_bad_sz)")],
     CHECK144, ['B2']),
    ('M6', u'`merge_patches` 的「只有旧键⇒保留」分支改没', EVAL113,
     [(u'k not in new', u'k not in neu')], CHECK144, ['C2']),
    ('M7', u'本套件判据描述里塞计数标记字面量', CHECK144,
     [(u"u'D2 \u6ca1\u6709", u"u'[PASS] D2 \u6ca1\u6709")], CHECK144, ['D1']),
    ('M8', u'扫描面塌掉（`.py` → `.pyz`）', CHECK144,
     [(u"if not fn.endswith(u'.py'):", u"if not fn.endswith(u'.pyz'):")],
     CHECK144, ['B1b']),
]


def main():
    head(u'0 · 前置：现在必须是全绿的（否则"打坏后报红"说明不了任何事）')
    rc0, out0 = _run(CHECK144)
    check(u'0a 打坏之前 `check144` 是绿的', rc0 == 0 and u'FAIL=0' in out0,
          u'rc=%d' % rc0)
    base_vals = _read(FROZEN)

    head(u'阶段一 · 逐个打坏')
    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    for mid, desc, path, pairs, suite, expect in MUT:
        bak = os.path.join(BAK, os.path.basename(path) + '.' + mid)
        shutil.copy2(path, bak)
        orig, how = _apply(path, pairs)
        if orig is None:
            shutil.copy2(bak, path)
            check(u'%s %s —— **破坏没打上**' % (mid, desc), False, how)
            continue
        try:
            rc, out = _run(suite)
            reds = [u'[FAIL] %s' % j for j in expect]
            miss = [r for r in reds if r not in out]
            check(u'%s %s ⇒ 该红的红（%s）' % (mid, desc, u' + '.join(expect)),
                  not miss and rc != 0,
                  u'%s ｜ 缺 %s' % (how, u','.join(miss) or u'无'))
        finally:
            shutil.copy2(bak, path)
            same = _read(path) == orig
            check(u'%s 已还原（字节级一致）' % mid, same)

    head(u'阶段二 · `.gitignore` 那一行（单独处理：删行，不是替换）')
    bak = os.path.join(BAK, '.gitignore.M4')
    shutil.copy2(GITIGNORE, bak)
    orig_gi, how = _drop_line(GITIGNORE, u'code-quality-audit/regress/_out/')
    if orig_gi is None:
        shutil.copy2(bak, GITIGNORE)
        check(u'M4 `.gitignore` 删掉 `regress/_out/` 那行 ⇒ A5 红', False, how)
    else:
        try:
            rc, out = _run(CHECK144)
            check(u'M4 `.gitignore` 删掉 `regress/_out/` 那行 ⇒ A5 红',
                  u'[FAIL] A5' in out and rc != 0, how)
        finally:
            shutil.copy2(bak, GITIGNORE)
            check(u'M4 已还原（字节级一致）', _read(GITIGNORE) == orig_gi)

    head(u'阶段三 · 收口：全部还原后必须回到全绿')
    check(u'R1 冻结文件与打坏前逐字一致', _read(FROZEN) == base_vals)
    rc, out = _run(CHECK144)
    check(u'R2 收口复跑 `check144` 全绿', rc == 0 and u'FAIL=0' in out,
          u'rc=%d' % rc)
    check(u'R3 备份目录只在外部盘（没污染工作区）',
          os.path.abspath(BAK).startswith('D:')
          and not os.path.isdir(os.path.join(ROUND, '_bak')))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
