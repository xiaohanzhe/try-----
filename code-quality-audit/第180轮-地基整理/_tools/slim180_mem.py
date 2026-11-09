# -*- coding: utf-8 -*-
u"""第180轮 · 记忆缩容的**判据**：证明"腾出来的地方"不是"删掉的信息"。

做法：速查本这一轮删掉的全是**过程数字与重复索引**。
每一条被删的数字/事实，都必须在**详版**里能找到原文；
找不到 ⇒ 拒绝（说明我在削语义）。

三条闸：
  S1 `js_len`（UTF-16 码元，含 CRLF）≤ 10000 —— 与 `check95 A2` 同一口径
  S2 被删事实的**每一个 token** 都能在详版里找到（配**负控制**：一个肯定不存在的串必须找不到，
     否则说明扫描器恒真）
  S3 速查本的关键铁律仍在（防止"为了腾地方把整段删了"）

用法：python slim180_mem.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(REPO, '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md')

_n = {'p': 0, 'f': 0}


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


mem = rd(MEM)
det = rd(DET)

#: ★★★ 本轮从速查本里删掉的**每一项事实**：其标识 token 必须在详版出现。
#: （不是"删了什么就列什么"，而是"我声称信息还在详版里，逐条举证"。）
#: ★★ 第一版用的是裸数字（`801`）⇒ 命中的其实是大数 `18016` 里的子串
#:    —— **子串假阳性**。改成**锚定短语**（带回上下文），这样"命中了别的事实"就过不了。
DELETED = [
    (u'169 的边数与优先级区间', [u'**1,828**', u'7088~7189']),
    (u'169 的一房多出口计数', [u'一房多出口场景']),
    (u'171 的实例表增量', [u'1,936 → **1,961**', u'196 → **221**']),
    (u'172 的扇数与落边数', [u'881 扇', u'798 条']),
    (u'173 的物化条数与解得目标', [u'**820**', u'**801 / 820**']),
    (u'174 的优先级区间', [u'**8100 ~ 8150**']),
    (u'176 的门路由总数', [u'3,047 个门物件']),
    (u'174 / 176 的变异数', [u'变异 8/8', u'变异 9/9']),
    (u'178 的 164 BBA 第三项', [u'BBA']),
    (u'168~179 各轮章节标题仍在', [u'§169', u'§170', u'§171', u'§172', u'§173',
                                    u'§175', u'§176', u'§177', u'§178', u'§179',
                                    u'§180', u'§181']),
]
#: 负控制：这两个串**不应该**在详版出现（证明下面的扫描不是恒真）
NEG = [u'这个字符串故意不存在_zz7', u'另一条负控制_qq9']

print('')
print('=' * 70)
print(u'S1 体积（与 `check95 A2` 同口径：UTF-16 码元，含 CRLF）')
print('=' * 70)
js = sum(2 if ord(c) > 0xFFFF else 1 for c in mem)
check(u'S1 速查本 `js_len` ≤ 10000', 0 < js <= 10000,
      u'js_len=%d  chars=%d  余量=%+d' % (js, len(mem), 10000 - js))

print('')
print('=' * 70)
print(u'S2 删掉的事实都在详版里（逐条举证 + 负控制）')
print('=' * 70)
check(u'S2.0 分母闸：待举证项 >= 10（防止列表被清空后整段恒真）',
      len(DELETED) >= 10, u'项数=%d' % len(DELETED))

_lost = []
for desc, toks in DELETED:
    miss = [t for t in toks if t not in det]
    if miss:
        _lost.append((desc, miss))
    check(u'S2 %s' % desc, not miss, u'缺=%r' % (miss,) if miss else u'')

_hit = [t for t in NEG if t in det]
check(u'S2.9 负控制：故意不存在的串**找不到**（否则扫描器恒真）', not _hit,
      u'误命中=%r' % (_hit,))

print('')
print('=' * 70)
print(u'S3 速查本的关键铁律仍在（防"整段删掉换体积"）')
print('=' * 70)
KEEP = [
    (u'动手前四步', u'动手前四步'),
    (u'工作区会被回滚', u'回滚'),
    (u'HWND_TOP==0 假值', u'HWND_TOP==0'),
    (u'站谁上面优先于 Y（本轮新增）', u'站谁上面'),
    (u'G2 全 IDENTICAL 要求', u'IDENTICAL'),
    (u'gitpush 必须 --refspec', u'--refspec'),
    (u'不许叫"主人"', u'主人'),
    (u'改动即 commit+push', u'commit+push'),
    (u'误报清单', u'误报清单'),
    (u'已裁定不重问', u'绝不重问'),
]
for desc, tok in KEEP:
    check(u'S3 %s' % desc, tok in mem, u'' if tok in mem else u'缺 token=%r' % tok)

print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _lost:
    print(u'★ 下列事实在详版里**找不到**，说明削语义了：')
    for d, m in _lost:
        print(u'   %s → %r' % (d, m))
print('=' * 70)
sys.exit(0 if _n['f'] == 0 else 1)
