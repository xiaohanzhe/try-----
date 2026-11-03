# -*- coding: utf-8 -*-
u"""第151轮 · 破坏性负控制：逐条拆掉"开机示范差事"这个口子，**指定**判据必须报红。

`check151` 全绿证明不了什么 —— 全绿也可能因为判据恒真。
这里逐条破坏产品，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次 `check151`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|------|----------|
| M1 | 出厂默认从 `None` 改成一条真差事 | `A1` `A2` `B5` `C1` `C3` |
| M2 | 绕过公开入口，直接 `npc_errand.assign(...)`（不给门控看） | `A6` `A7` `B3` `C2` |
| M3 | 去掉"看板非空就不派" | `A5` |
| M4 | 调用挪到 `_npc_seed_bodies` **之前**（依赖还没就位） | `B2` |
| M5 | 再加一处调用（一拍派两次） | `B1` `B4` |
| M6 | 把注释里的例子改成**门控必拒**的那条 | `A3` `A4` `A5` |
| M7 | 去掉 `not board.enabled` 的提前返回 | `A9` |

## 期望又写窄了三次（三次都是**判据对、期望错**）

- **`M1` 多红了 `B5`/`C3`**：`B5` 断"默认值是 `= None` 这个形式"，`C3` 断
  "解析到的那行例子就在 `NPC_ERRAND_DEMO = None` 这段注释里" —— 默认值一改，
  这两条的**前提**就没了，它们红得对。（顺带说明 `B5` 不是 `A1` 的复读：
  `A1` 断运行时值，`B5` 断**源码写法**，防"写成 `= ()` 看着像空、其实不是 None"。）
- **`M6` 多红了 `A4`/`A5`**：它们都建立在 `_e_b`（那条派出的差事）之上，
  例子一改成门控必拒 ⇒ `_e_b is None` ⇒ **下游一起塌**。这不是三条独立信号，
  是**同一条链上的三个观测点**（fail-closed，不是判据坏了）。

⇒ 这两次和第150轮那三次是同一类：写 `mutate` 的期望集合时，
**先问"这件事还有谁在盯？谁在它下游？"**

## 两处"红得应该"的说明（省得以后误当判据坏了）

**① `M2` 一次红四条，因为它们各看一层。**
`B3`/`C2` 断"有没有走公开入口"，`A6` 断"门控还真拦得住吗"，
`A7` 断"被拒时留不留痕"。绕过入口 ⇒ 这四件事**一起不成立**，
不是四条独立信号，是**同一次改动的四个观测面**。

**② `M6` 只红 `A3` —— 这正是本轮特意改过的原因。**
第一版 `A3` 里写死了 `('ralsei', 'oneshot.barrens.Blue', …)`，
那么把注释改成 `('os_niko', 'desktop', …)`（门控必拒）**也照样绿** ——
因为它验的是"我写的样本"，不是"文档里那个"。
现在 `A3` 从源码注释里**解析**那个元组 ⇒ 文档写坏了它就红。
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
CHECK151 = os.path.join(HERE, 'check151.py')
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
    # ★ 字节忠实：`newline=''` 保住 CRLF，否则还原时整份文件的 EOL 都被改写
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _sha1(p):
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


#: 开工前的字节指纹。Z2 拿它当对照 —— 不许写成"再读一遍跟自己比"（恒真）。
_SHA0 = ((MAIN, _sha1(MAIN)),)


def _run151():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK151], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    txt = out.decode('utf-8', 'replace')
    toks = set()
    for line in txt.splitlines():
        if not line.startswith(u'[FAIL] '):
            continue
        toks.add(line[len(u'[FAIL] '):].split(u' ')[0])
    return toks, p.returncode, txt


def mutate(tag, path, pairs, expect):
    src = _read(path)
    bad = [(o, src.count(o)) for o, _n in pairs if src.count(o) != 1]
    if bad:
        check(u'%s 每处锚点都唯一' % tag, False,
              u'；'.join(u'%r 出现 %d 次' % (o[:30], c) for o, c in bad))
        return
    sha0 = _sha1(path)
    try:
        new_src = src
        for o, n in pairs:
            new_src = new_src.replace(o, n, 1)
        if new_src == src:
            check(u'%s 破坏确实改动了源码' % tag, False, u'替换后与原文相同')
            return
        _write(path, new_src)
        got, rc, txt = _run151()
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

# M1 出厂就派（差事的零回归靠"恒空看板"，这一改三处行为判据全塌）
mutate(u'M1', MAIN,
       [(u'    NPC_ERRAND_DEMO = None\r\n',
         u"    NPC_ERRAND_DEMO = ('ralsei', 'oneshot.barrens.Blue', '\u53bb\u770b\u770b')\r\n")],
       [u'A1', u'A2', u'B5', u'C1', u'C3'])

# M2 绕过公开入口：直接塞进看板 ⇒ 门控根本不知道（"示范差事是特权"）
mutate(u'M2', MAIN,
       [(u'            e = self.assign_errand(npc_id, dest_scene, what)\r\n',
         u'            e = self.npc_errand.assign(0.0, npc_id, dest_scene, what)\r\n')],
       [u'A6', u'A7', u'B3', u'C2'])

# M3 去掉"看板非空就不派" ⇒ 每次开机重派一遍（种子变成刷子）
mutate(u'M3', MAIN,
       [(u'        if board is None or not board.enabled or len(board):\r\n',
         u'        if board is None or not board.enabled:\r\n')],
       [u'A5'])

# M4 调用挪到 `_npc_seed_bodies` 之前：三样依赖还没就位
#   ⚠️ 锚点不能用单行 `self._npc_seed_bodies(self._npc_scene_id())` —— 全文件出现 3 次。
#     用 try/except 整块（那句 warning 文本唯一）才够特异。
mutate(u'M4', MAIN,
       [(u'        self._npc_errand_demo()\r\n', u''),
        (u'        try:\r\n'
         u'            self._npc_seed_bodies(self._npc_scene_id())\r\n'
         u'        except Exception as e:\r\n'
         u"            _log.warning('NPC \u7ad9\u4f4d\u521d\u59cb\u5316\u5931\u8d25"
         u"\uff08\u5f00\u5c40\u65e0\u7ad9\u4f4d\uff09: %s', e)\r\n",
         u'        self._npc_errand_demo()\r\n'
         u'        try:\r\n'
         u'            self._npc_seed_bodies(self._npc_scene_id())\r\n'
         u'        except Exception as e:\r\n'
         u"            _log.warning('NPC \u7ad9\u4f4d\u521d\u59cb\u5316\u5931\u8d25"
         u"\uff08\u5f00\u5c40\u65e0\u7ad9\u4f4d\uff09: %s', e)\r\n")],
       [u'B2'])

# M5 再加一处调用（同一个开机流程派两次）
mutate(u'M5', MAIN,
       [(u'        self._npc_errand_demo()\r\n',
         u'        self._npc_errand_demo()\r\n        self._npc_errand_demo()\r\n')],
       [u'B1', u'B4'])

# M6 注释里的例子改成门控必拒的那条（文档写坏了必须报红 —— 见文件头 ②）
mutate(u'M6', MAIN,
       [(u"('ralsei', 'oneshot.barrens.Blue', '\u53bb\u770b\u770b')",
         u"('os_niko', 'desktop', '\u53bb\u770b\u770b')")],
       [u'A3', u'A4', u'A5'])

# M7 去掉"看板没开就别问门控"的提前返回（A9 靠"有没有真去调"才辨得出）
mutate(u'M7', MAIN,
       [(u'        if board is None or not board.enabled or len(board):\r\n',
         u'        if board is None or len(board):\r\n')],
       [u'A9'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run151()
check(u'Z1 收口全绿（FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))
check(u'Z2 被改过的文件已按字节还原（与**开工前**指纹一致）',
      all(_sha1(p) == s for p, s in _SHA0),
      u'%s' % ([(os.path.basename(p), _sha1(p) == s) for p, s in _SHA0],))

print(u'')
print(u'=' * 78)
print(u'mutate151：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
