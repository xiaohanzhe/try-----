# -*- coding: utf-8 -*-
u"""第160轮探针：**语义等价的改写会不会被判据当成破坏**（假红实证）。

## 为什么要单独立一个探针

`recheck159_core H5g` 第 159 轮写的是"**同一个 `if` 里**既有 `not x` 又有 `x != x.strip()`"。
判据绑的是**写法**（if 的形状），不是**语义**（两半都在）。于是下面这段**完全等价**的代码

```python
if not isinstance(npc_id, str) or not npc_id:
    return None
if npc_id != npc_id.strip():
    return None
```

会被判成"缺一半" ⇒ **假红**。判据过窄比不写还危险（会训练人"改判据"而不是"改代码"）。

## 本探针做什么

把 main.py 的宿主 `npc_id` 闸**临时**改成上面那种两段式，跑一遍两个套件，看谁红；
再**字节级还原**并校验 sha1。同一个注入，改判据前后各跑一次 —— **成对**。

用法：
    python probe160.py --before    # 改判据之前：预期 recheck159 H5g 假红
    python probe160.py             # 改判据之后：预期两个套件全绿
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
R159 = os.path.join(ROOT, 'code-quality-audit', '第159轮-空白名字不算人', '_tools')
CHECK159 = os.path.join(R159, 'check159.py')
RECHECK159 = os.path.join(R159, 'recheck159_core.py')

OLD = u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None"""

NEW = u"""        if not isinstance(npc_id, str) or not npc_id:
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\uff08%r\uff09', npc_id)
            return None
        if npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1a\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None"""


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def _c(s):
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


def _sha(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


def _run(path):
    p = subprocess.Popen([sys.executable, path], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode('utf-8', 'replace')
    reds = [ln[7:].split()[0] for ln in out.splitlines() if ln.startswith('[FAIL] ')]
    return p.returncode, reds


base = _read(MAIN)
base_sha = _sha(base)
o, n = _c(OLD), _c(NEW)
if base.count(o) != 1:
    print(u'[ABORT] 锚点出现 %d 次' % (base.count(o),))
    sys.exit(2)

print(u'基线 sha1: main=%s' % (base_sha[:12],))
print(u'注入：宿主 `npc_id` 闸 → **两个连续的 if**（语义等价：先挡空/非 str，再挡首尾空白）')
_write(MAIN, base.replace(o, n))
try:
    rc1, red1 = _run(CHECK159)
    rc2, red2 = _run(RECHECK159)
finally:
    _write(MAIN, base)
    if _sha(_read(MAIN)) != base_sha:
        print(u'[FAIL] 还原失败（sha1 不一致）')
        sys.exit(2)

print(u'')
print(u'check159          rc=%d 红：%s' % (rc1, u' '.join(red1) or u'（无）'))
print(u'recheck159_core   rc=%d 红：%s' % (rc2, u' '.join(red2) or u'（无）'))
print(u'')
print(u'还原后 sha1 一致：%s' % (_sha(_read(MAIN)) == base_sha,))
print(u'')
if '--before' in sys.argv:
    print(u'== 改判据**前**（判据绑了 if 的形状）==')
    print(u'预期：check159 全绿（它那时还没有"两半"判据）· recheck159_core **H5g 假红**。')
else:
    print(u'== 改判据**后**（只看"同函数内两半都在"）==')
    print(u'预期：两个套件**都全绿** —— 等价改写不再被判成破坏。')
