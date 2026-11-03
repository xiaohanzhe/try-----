# -*- coding: utf-8 -*-
u"""第147轮 · 破坏性负控制：把 `_hard_cut` 的每一层拆掉，**指定**判据必须报红。

`check147` 全绿本身证明不了什么 —— 全绿也可能是因为判据恒真。
这里逐条破坏产品（`modules/event_speech.py`），断言**恰好**是那几条判据变红
（多红一条、少红一条都算不合格），然后**按字节还原**（sha1 校验）。
最后再跑一次 `check147`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|---|---|
| M1 | `_WORDY` 里塞进 `曾经`（CJK） | `A4` `B2` `C2` `C3` |
| M2 | 退让整段关掉（`if sp > 0:` → `if False:`） | `B1` `B4` `B5` `B10` `C1` `D2` |
| M3 | 两侧判据 `and` → `or`（切点一侧够就算词中） | `C3` |
| M4 | 删掉底线②（留下 ≥ 半个预算） | `B11` |
| M5 | **双拆**底线①＋②（`sp >= 0` 且条件恒真） | `B7` `B11` `D1` |
| M6 | `first_sentence` 那处调用退回裸 `t[:max_chars]` | `A2` `B1` `B4` `B10` `C1` `D2` |

## 三条写在这里的教训

**① M4 / M5 是"覆盖不足"暴露出来的。**
第一版 `check147` 只有 `NOSPACE` 一个底线样本。拿它验底线②
（`len(keep) * 2 >= max_chars`）时发现：删掉这一整条，**整套判据照样全绿** ——
因为前面的闸已经把它挡住了。⇒ 补了 `HALF`（空格在第 8 位、退过去只剩 8 字 < 12）
才有 `B11` 能单独钉住它。**没有样本的"防线"在判据里等于不存在。**

**② `NOSPACE` 这个名字一直在骗人。**
它是 `'a' + 'bcdef…'` —— **拼起来一个空格都没有**（原注释写"只有一个空格且在开头"，假）。
所以它测的其实是 `rfind(' ') == -1`（没有切点），压根没进底线①。
把它拆成两个样本才对上号：`NOSPACE`（无空格，走公开入口，`B12`）＋ `SPACE0`（空格在第 0 位）。

**③ 底线① 从公开 API **走不到** —— 这是查出来的，不是猜的。**
`first_sentence` / `fit_sentences` 开头都有 `t = text.strip()` ⇒ 前置空格在进函数前就没了
⇒ `sp == 0` 在公开入口不可达。所以 `B7` 只能直接喂 `_hard_cut`（单元级探针）。
这也顺带解释了 M5 为什么要"拆干净"：底线① 在底线② 存在时是**冗余的**（`keep=''` 时
`0 * 2 >= 24` 本来就是 False）⇒ 单拆① 毫无反应（我先试了，确实全绿）。
多道防线要**同时拆**才复现病灶（第 95 轮 §95.13 的老账）。

## 期望值写窄过一次，两条都是我的错

- `M2` 漏了 `B5`：关掉退让后 **40 字链**（`PROTEC|T`）当然也退回半个词 —— 我只想着 24 字链。`B5` 红是**真红**。
- `M5` 多算了 `B7` 少算了 `D1`：`B7` 的样本当时还是那个"名字叫无空格其实无空格"的
  `NOSPACE`（`sp == -1` 永远进不了分支）；而 `if True:` 把 `MIN_FIRST_CHARS` 也一并废了
  ⇒ `D1`（关掉 MIN 必须退回硬截）真的不成立。两处都是判据对、期望错。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'modules', 'event_speech.py')
CHECK147 = os.path.join(HERE, 'check147.py')
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


def _run147():
    u"""跑 `check147`，返回 (变红的判据编号集合, 退出码, 原始输出)。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK147], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    txt = out.decode('utf-8', 'replace')
    toks = set()
    for line in txt.splitlines():
        if not line.startswith(u'[FAIL] '):
            continue
        toks.add(line[len(u'[FAIL] '):].split(u' ')[0])
    return toks, p.returncode, txt


def mutate(tag, pairs, expect):
    u"""按 `pairs`（[(old, new), …]）改 → 跑 → 断言恰好 `expect` 变红 → 按字节还原。"""
    src = _read(SRC)
    bad = [(o, src.count(o)) for o, _n in pairs if src.count(o) != 1]
    if bad:
        check(u'%s 每处锚点都唯一' % tag, False,
              u'；'.join(u'%r 出现 %d 次' % (o[:28], c) for o, c in bad))
        return
    sha0 = _sha1(SRC)
    try:
        new_src = src
        for o, n in pairs:
            new_src = new_src.replace(o, n, 1)
        _write(SRC, new_src)
        got, rc, txt = _run147()
        ok = (got == set(expect)) and rc != 0
        check(u'%s 破坏后**恰好** %s 变红' % (tag, u'+'.join(expect)),
              ok, u'实得 %s' % (u'+'.join(sorted(got)) or u'（无）'))
        if not ok:
            for line in txt.splitlines():
                if line.startswith(u'[FAIL] '):
                    print(u'        %s' % line)
    finally:
        _write(SRC, src)
        check(u'%s 已按字节还原（sha1 一致）' % tag, _sha1(SRC) == sha0)


print(u'=' * 78)
print(u'M 破坏性负控制（每处都断言**恰好**指定的判据变红）')
print(u'=' * 78)

# M1 白名单漏进 CJK —— 第147轮第一版就是这么栽的（中文被改 151 / 57 条）
# ★ 锚点刻意选在 `_WORDY = (u'` 这个**纯 ASCII 前缀**上：第 70 行源码里写的是
#   字面转义 `\u2019`（不是那个字符本身），拿它当锚点会在"源码文本 vs 运行时值"
#   之间来回踩坑。改前缀既唯一、又同样把 CJK 塞进了白名单。
mutate(u'M1', [(u"_WORDY = (u'", u"_WORDY = (u'\\u66fe\\u7ecf")],
       [u'A4', u'B2', u'C2', u'C3'])

# M2 退让整段关掉 ⇒ 回到"切在半个单词上"（24 与 40 两条链都会中招）
mutate(u'M2', [(u'        if sp > 0:', u'        if False:')],
       [u'B1', u'B4', u'B5', u'B10', u'C1', u'D2'])

# M3 切点两侧 `and` → `or`：右侧那个字不再是必要条件
mutate(u'M3', [(u"cut[-1] in _WORDY and t[len(cut)] in _WORDY",
                u"cut[-1] in _WORDY or t[len(cut)] in _WORDY")],
       [u'C3'])

# M4 只删底线②
mutate(u'M4', [(u'if len(keep.strip()) >= MIN_FIRST_CHARS and len(keep) * 2 >= max_chars:',
                u'if len(keep.strip()) >= MIN_FIRST_CHARS:')],
       [u'B11'])

# M5 底线①＋② 一起拆（单拆① 无反应，见文件头教训③；`if True:` 顺带废掉 MIN ⇒ D1 也红）
mutate(u'M5', [(u'        if sp > 0:', u'        if sp >= 0:'),
               (u'            if len(keep.strip()) >= MIN_FIRST_CHARS and len(keep) * 2 >= max_chars:',
                u'            if True:')],
       [u'B7', u'B11', u'D1'])

# M6 `first_sentence` 那一处退回裸硬截（三处调用退化一处）
mutate(u'M6', [(u'    if len(t) > max_chars:\r\n        t = _hard_cut(t, max_chars)\r\n    t = t.strip()',
                u'    if len(t) > max_chars:\r\n        t = t[:max_chars]\r\n    t = t.strip()')],
       [u'A2', u'B1', u'B4', u'B10', u'C1', u'D2'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run147()
check(u'Z1 收口全绿（PASS=26 FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))

print(u'')
print(u'=' * 78)
print(u'mutate147：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
