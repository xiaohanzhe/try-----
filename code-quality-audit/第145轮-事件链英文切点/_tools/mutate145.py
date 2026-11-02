# -*- coding: utf-8 -*-
"""第145轮破坏性负控制：把本轮每一道闸**逐条打坏**，看它是否真会报红。

## 为什么必须做

本轮改的是"切点表 + 一个过滤函数"。这类改动的判据最容易写成**恒真**：
断言"表里有 `.`"只要自己没写错就永远真；断言"`Well, well, well.` 能被切出来"
也可能因为**被测函数根本没走到那条分支**而假绿。

⇒ 每道闸配一次"真改坏被测物"的对照，并且：
  (a) 破坏必须**真落进被测分支**（打不上就报错，不许静默跳过）；
  (b) 报红的必须是**指定的那一条**，不是"某处红了"；
  (c) 还原后必须**重新全绿**，且**字节级一致**。

## 8 个破坏点

| # | 打坏什么 | 该谁红 |
|---|---|---|
| M1 | `_SENTENCE_ENDS` 里去掉 `.` | B1 + C1 |
| M2 | `_SENTENCE_ENDS` 里去掉 `…`（第136轮加的） | B2 |
| M3 | `_SENTENCE_ENDS` 里加 `,`（句内停顿当句末） | B3 |
| M4 | `first_sentence` 改回自己扫表（不调 `_sentence_ends`） | B5 + B7 |
| M5 | 小数点守卫 `isdigit` 改成 `isalpha`（等于失效） | B8 + C4 |
| M6 | "头太短不算"守卫 `if False`（缩写点不再挡） | B9 + C2 |
| M7 | `fit_sentences` 改回自己扫表 | B6 + B7 |
| M8 | **本套件自己**的判据描述里塞计数标记字面量 | E2 |

★ M8 打的是 `check145.py` 自己 —— "守别人的人自己不守"是本仓反复踩的坑。

★ 备份一律落 `D:\\_tmp\\mut145\\`（**绝不放工作区**：`git add -A` 会把它们记成删除）。
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
PET = os.path.join(ROOT, 'ralsei_pet')
ES_PATH = os.path.join(PET, 'modules', 'event_speech.py')
CHECK = os.path.join(HERE, 'check145.py')
BAK = os.path.join('D:\\_tmp', 'mut145')

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
    """逐条替换；打不上就返回 None（不许静默跳过）。"""
    orig = _read(path)
    src = orig
    how = []
    for old, new in pairs:
        done = None
        for cand in ((old, new),
                     (old.replace(u'\n', u'\r\n'), new.replace(u'\n', u'\r\n'))):
            if cand[0] and cand[0] in src:
                src = src.replace(cand[0], cand[1], 1)
                done = u'CRLF' if u'\r\n' in cand[0] else u'LF'
                break
        if done is None:
            return None, u'打不上：%s' % old[:44]
        how.append(done)
    if src == orig:
        return None, u'空操作'
    _write(path, src)
    return orig, u'/'.join(how)


MUT = [
    ('M1', u'`_SENTENCE_ENDS` 去掉 `.`',
     [(u"_SENTENCE_ENDS = u'。！？!?\\n….'", u"_SENTENCE_ENDS = u'。！？!?\\n…'")],
     ['B1', 'C1']),
    ('M2', u'`_SENTENCE_ENDS` 去掉 `…`（第136轮加的）',
     [(u"_SENTENCE_ENDS = u'。！？!?\\n….'", u"_SENTENCE_ENDS = u'。！？!?\\n.'")],
     ['B2']),
    ('M3', u'`_SENTENCE_ENDS` 里加 `,`',
     [(u"_SENTENCE_ENDS = u'。！？!?\\n….'", u"_SENTENCE_ENDS = u'。！？!?\\n….,'")],
     ['B3']),
    ('M4', u'`first_sentence` 改回自己扫表',
     [(u'    ends = _sentence_ends(t)          # ★ 第145轮：与另一条链共用一处实现\n'
       u'    if ends:',
       u'    ends = sorted(i for i, ch in enumerate(t) if ch in _SENTENCE_ENDS)\n'
       u'    if ends:')],
     ['B5', 'B7']),
    ('M5', u'小数点守卫 `isdigit` → `isalpha`（等于失效）',
     [(u"if j + 1 < len(t) and t[j + 1].isdigit():",
       u"if j + 1 < len(t) and t[j + 1].isalpha():")],
     ['B8', 'C4']),
    ('M6', u'"头太短不算"守卫改成 `if False`（缩写点不再挡）',
     [(u'if len(t[:j + 1].strip()) < MIN_FIRST_CHARS:',
       u'if False:')],
     # ★ 只期望 B9：`C2` **不会**跟着红 —— 缩写点有**两层**防线（过滤 + `first_sentence`
     #   自己那条 `len(head) >= MIN_FIRST_CHARS`），拆一层另一层还兜得住。
     #   所以 C2 的鉴别力由 `check145 C9`（把 MIN 调 0）单独证，而不是靠这里。
     ['B9']),
    ('M7', u'`fit_sentences` 改回自己扫表',
     [(u'    ends = _sentence_ends(t)          # ★ 第145轮：与另一条链共用一处实现\n'
       u'    # 放得下（且不是"切完只剩几个字"）的切点',
       u'    ends = sorted(i for i, ch in enumerate(t) if ch in _SENTENCE_ENDS)\n'
       u'    # 放得下（且不是"切完只剩几个字"）的切点')],
     ['B6', 'B7']),
    ('M8', u'本套件判据描述里塞计数标记字面量',
     [(u"u'E1 没有", u"u'[PASS] E1 没有")],
     ['E2']),
]


def main():
    head(u'0 · 前置：现在必须是全绿的')
    rc0, out0 = _run(CHECK)
    check(u'0a 打坏之前 `check145` 是绿的', rc0 == 0 and u'FAIL=0' in out0,
          u'rc=%d' % rc0)
    base = _read(ES_PATH)

    head(u'阶段一 · 逐个打坏（产品文件 event_speech.py）')
    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    for mid, desc, pairs, expect in MUT:
        target = CHECK if mid == 'M8' else ES_PATH
        bak = os.path.join(BAK, os.path.basename(target) + '.' + mid)
        shutil.copy2(target, bak)
        orig, how = _apply(target, pairs)
        if orig is None:
            shutil.copy2(bak, target)
            check(u'%s %s —— **破坏没打上**' % (mid, desc), False, how)
            continue
        try:
            rc, out = _run(CHECK)
            miss = [j for j in expect if u'[FAIL] %s' % j not in out]
            check(u'%s %s ⇒ 该红的红（%s）' % (mid, desc, u' + '.join(expect)),
                  not miss and rc != 0,
                  u'%s ｜ 缺 %s' % (how, u','.join(miss) or u'无'))
        finally:
            shutil.copy2(bak, target)
            check(u'%s 已还原（字节级一致）' % mid, _read(target) == orig)

    head(u'阶段二 · 收口')
    check(u'R1 `event_speech.py` 与打坏前逐字一致', _read(ES_PATH) == base)
    rc, out = _run(CHECK)
    check(u'R2 收口复跑 `check145` 全绿', rc == 0 and u'FAIL=0' in out,
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
