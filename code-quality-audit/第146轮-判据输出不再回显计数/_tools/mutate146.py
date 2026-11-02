# -*- coding: utf-8 -*-
u"""第146轮 · 破坏性负控制：把改动逐个改回去，**指定**判据必须报红。

`check146` 全绿本身证明不了什么 —— 全绿也可能是因为判据恒真。
这里逐条破坏，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|---|---|
| M1 | `check138 D1` 的 extra 改回 `u'%d 个' % len(_targets)` | `A3` `B3` `C2` `D1` |
| M2 | `check138 D2` 的 extra 改回 `u'%d 处' % _n_calls` | `A3` `B3` `C2` `D1` |
| M3 | `D1` 的 extra 换成**死字串**（判定还在，只是不再跟着走） | `A4` `D1` `D2` |
| M4 | `measure146._insert_probe` 变成 no-op（**夹具不保真**） | `B1` `B2` `B4` |
| M5 | `check138 A4` 的 `_missing` 去掉否定过滤（命中列表 → 规模量） | `A2` `B3` `C2` `C3` |

## ★★★ 期望值第一版全写窄了，逐条查过：多红的**都是真红**

第一版按"直觉"写（M1/M2 只 `A3+C2`、M3 只 `D1+D2`、M4 只 `B1+B2`、M5 只 `A2+C2+C3`），
跑出来每一条都多红 1~2 个。**没有一条是误报**，逐条归因：

| 多红的 | 为什么它是**真**红 |
|---|---|
| `M1/M2 → B3` | 旧形状下 `check138` 的 stdout **真的**随套件数漂 —— 这就是本轮那个病本身，`B3` 抓它天经地义 |
| `M1/M2 → D1` | `u'%d 个' % len(_targets)` 的 eval 结果里既没 `True` 也没 `False` ⇒ "过阈/不过阈给不同结论"真的不成立了 |
| `M3 → A4` | 死字串里 `_targets` / `_n_calls` 两个名字真没了 ⇒ "只是改成算布尔，不是删掉"真的被违反 |
| `M4 → B4` | 探针没真塞进去 ⇒ 两个数没动 ⇒ `B4`（旧形状下两行必然不同）**该**红 —— 这正是它存在的意义 |
| `M5 → B3` | `_missing` 从"缺 0 个"变成"144/145 个" ⇒ A4 的输出真的跟着套件数漂了 |

⇒ 判据没问题，**是我的期望值偷懒**（只想着"我改的那一处"）。这就是"报红先怀疑判据"
的逆用：怀疑过了、查清了、确认判据是对的 —— 那就改期望，并把理由写在这儿，
省得下一个人重走一遍。

★ M4 是"夹具不保真"那一类（第 85 轮 `mutate85` 的教训）：探针没真塞进去，
`B3`（输出没变）会**照样绿** —— 所以 `B1`（Δfiles==1）必须挡住它。
这条破坏就是用来证明 `B1` 真的在挡。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
AUDIT = os.path.join(ROOT, 'code-quality-audit')
CHECK146 = os.path.join(HERE, 'check146.py')
MEASURE = os.path.join(HERE, 'measure146.py')
CHECK138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools', 'check138.py')
PY = u'C:\\Python311\\python.exe'

_n_ok = 0
_n_bad = 0
_failed = []


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _sha1(p):
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def _run146():
    u"""跑 `check146`，返回 (变红的判据编号集合, 退出码)。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK146], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    txt = out.decode('utf-8', 'replace')
    toks = set()
    for line in txt.splitlines():
        if not line.startswith(u'[FAIL] '):
            continue
        body = line[len(u'[FAIL] '):]
        toks.add(body.split(u' ')[0])
    return toks, p.returncode, txt


def mutate(tag, path, old, new, expect):
    u"""改一处 → 跑 → 断言恰好 `expect` 变红 → **按字节还原**。"""
    src = _read(path)
    if src.count(old) != 1:
        check(u'%s 定位唯一（出现 %d 次）' % (tag, src.count(old)), False)
        return
    sha0 = _sha1(path)
    try:
        _write(path, src.replace(old, new))
        got, rc, txt = _run146()
        ok = (got == set(expect)) and rc != 0
        check(u'%s 破坏后**恰好** %s 变红' % (tag, u'+'.join(expect)),
              ok, u'实得 %s' % (u'+'.join(sorted(got)) or u'（无）'))
        if not ok:
            for line in txt.splitlines():
                if line.startswith(u'[FAIL] '):
                    print(u'        %s' % line)
    finally:
        _write(path, src)
        check(u'%s 已按字节还原（sha1 一致）' % tag, _sha1(path) == sha0)


print(u'=' * 78)
print(u'M 破坏性负控制（每处都断言**恰好**指定的判据变红）')
print(u'=' * 78)

mutate(u'M1', CHECK138,
       u"u'\u8fc7\u9608=%s\uff08\u95f8\u95e8 \u2265100\uff09' % (len(_targets) >= 100)",
       u"u'%d \u4e2a' % len(_targets)",
       [u'A3', u'B3', u'C2', u'D1'])

mutate(u'M2', CHECK138,
       u"u'\u8fc7\u9608=%s\uff08\u95f8\u95e8 \u22652000\uff09' % (_n_calls >= 2000)",
       u"u'%d \u5904' % _n_calls",
       [u'A3', u'B3', u'C2', u'D1'])

mutate(u'M3', CHECK138,
       u"u'\u8fc7\u9608=%s\uff08\u95f8\u95e8 \u2265100\uff09' % (len(_targets) >= 100)",
       u"u'\u8fc7\u9608=True\uff08\u95f8\u95e8 \u2265100\uff09'",
       [u'A4', u'D1', u'D2'])

mutate(u'M4', MEASURE,
       u'    return src[:i] + PROBE_ENTRY + src[i:]',
       u'    return src',
       [u'B1', u'B2', u'B4'])

mutate(u'M5', CHECK138,
       u'p for p in _suite_scripts() if not os.path.exists(p)',
       u'p for p in _suite_scripts() if os.path.exists(p)',
       [u'A2', u'B3', u'C2', u'C3'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run146()
check(u'Z1 收口全绿（PASS=26 FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))

print(u'')
print(u'=' * 78)
print(u'mutate146：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
