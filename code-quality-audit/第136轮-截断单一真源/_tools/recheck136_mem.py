# -*- coding: utf-8 -*-
"""第136轮：速查本（MEMORY.md）改动后的**逐令牌回验**。

## 为什么必须做

用户口径：「压也**只做结构性去重/合并**，**不许为凑体积削语义**」；
「删令牌必先确认详版可检索」（第 2026-09-23 那次就是靠这一步抓到两个 hash 被压丢）。

本轮为了给 §136 腾出 12 → 0 字符的空间，从速查本删/改了几处。
下面**逐个**回详版 `in` 一次：**被删的令牌必须还能在详版里搜到**，
否则要么补回速查本，要么先补详版。

★ 匹配用"宽式"（去掉 `§`、markdown 星号、空格差异），避免"判据太窄"的误报 ——
  这是 §135 `recheck135_mem C3` 踩过的坑。
"""
import io
import os
import re
import sys

MEM = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..',
                                   '.workbuddy', 'memory'))
QUICK = os.path.join(MEM, 'MEMORY.md')
DETAIL = os.path.join(MEM, '参考-契约与历轮（详版）.md')


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def norm(s):
    """宽式归一：去 markdown 星号/反引号、去 `§`、压空白、全角括号留原样。"""
    s = s.replace(u'**', u'').replace(u'`', u'').replace(u'§', u'')
    s = re.sub(u'\\s+', u'', s)
    return s


quick = read(QUICK)
detail = read(DETAIL)
nq, nd = norm(quick), norm(detail)

n = {'p': 0, 'f': 0}
fails = []


def check(desc, cond, extra=u''):
    cond = bool(cond)
    n['p' if cond else 'f'] += 1
    if not cond:
        fails.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


# ---------------------------------------------------------------- 被删/改的令牌
# (速查本里原来的写法, 详版必须还能搜到的宽式片段, 说明)
REMOVED = [
    (u'github.com/xiaohanzhe/try-----.git', u'github.com/xiaohanzhe/try',
     u'远端仓库地址（速查本改成"见 gitpush.py"）'),
    (u'api.timeout≥60', u'timeout≥60', u'性能线底座参数'),
    (u'反引号', u'反引号', u'`python -c` 被吞的具体原因'),
    (u'尊重用户口径', u'尊重用户口径', u'记忆口径的措辞告诫'),
    (u'<12 字逐字同', u'12字以下只认', u'复读判据的 12 字门槛'),
    (u'我不该用亮起来的开头', u'亮起来的开头', u'元话语泄漏的实例句'),
    (u'check115', u'check115', u'第115轮套件号（从锁号速查里移出）'),
    (u'桌面4门§109.2', u'桌面4门', u'场景进度（移出 §19，§7 仍在）'),
]

head(u'一、被删/改令牌：详版必须仍可检索')
for raw, wide, why in REMOVED:
    check(u'详版仍能搜到 %s（%s）' % (raw, why), norm(wide) in nd,
          u'' if norm(wide) in nd else u'**详版搜不到：%s**' % wide)

head(u'二、这些令牌确实已不在速查本里（证明"删了"不是"我以为删了"）')
for raw, wide, why in REMOVED:
    gone = norm(raw) not in nq
    check(u'速查本已不含 %s' % raw, gone, u'' if gone else u'**还在**')

head(u'三、本轮新增的关键令牌两边都在')
for tok in (u'136', u'截断单一真源', u'B7b', u'负控制靶子'):
    check(u'速查本含 %s' % tok, norm(tok) in nq)
    check(u'详版含 %s' % tok, norm(tok) in nd)

head(u'四、体积硬闸（check95 A2 口径：UTF-16 码元）')
js = len(quick.encode('utf-16-le')) // 2
check(u'速查本 js_len ≤ 10000', js <= 10000, u'%d / 10000（余 %d）' % (js, 10000 - js))
check(u'速查本无 BOM', not quick.startswith(u'\ufeff'))
check(u'速查本无 U+FFFD（替换字符）', u'\ufffd' not in quick)
check(u'详版 §136 整节在位', u'## §136.1' in detail and u'## §136.8' in detail)

print(u'')
print(u'=' * 78)
print(u'逐令牌回验：PASS=%d FAIL=%d' % (n['p'], n['f']))
if fails:
    for d in fails:
        print(u'  - %s' % d)
sys.exit(0 if not fails else 1)
