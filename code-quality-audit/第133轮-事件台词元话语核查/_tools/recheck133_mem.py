# -*- coding: utf-8 -*-
"""第133轮 · 记忆文件复检（速查本 / 详版 / 当日日志）。

口径与第128~132轮同一套：A 体积（`check95 A2` 硬闸 = **UTF-16 码元** ≤ 10000）
B 编码（无 BOM / 无 U+FFFD / 三个文件各自行尾不混用）
C 新增在位（本轮该出现的令牌都必须真在盘上）
D **删后有据**：速查本里被压掉的令牌，逐个去详版/§7 里 `in` 一次（`agent-memory-compaction` 的硬要求）
E 日志 **append-only**（上一轮末段仍在 + 本轮段落真在 + 字节只增）
F 守恒（速查本净变化、详版净增，都能说清）
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(ROOT, '.workbuddy', 'memory')
QUICK = os.path.join(MEM, 'MEMORY.md')
FULL = os.path.join(MEM, '参考-契约与历轮（详版）.md')
JOURNAL = os.path.join(MEM, '2026-11-01.md')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
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


def rb(p):
    with io.open(p, 'rb') as f:
        return f.read()


def rt(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


QB, QB_T = rb(QUICK), rt(QUICK)
FB, FB_T = rb(FULL), rt(FULL)
JB, JB_T = rb(JOURNAL), rt(JOURNAL)

# ---------------------------------------------------------------- A 体积
head(u'A. 体积（硬闸 = UTF-16 码元 ≤ 10000）')
_q_len = len(QB_T.encode('utf-16-le')) // 2
check(u'A1 速查本 ≤ 10000（UTF-16 码元口径）', _q_len <= 10000,
      u'%d / 10000（余 %d）' % (_q_len, 10000 - _q_len))
check(u'A2 速查本 ≥ 9000（不是靠砍成摘要凑限）', _q_len >= 9000, u'%d' % _q_len)
check(u'A3 详版比速查本大一个量级（详版真的是详版）',
      len(FB) > len(QB) * 20, u'%d vs %d 字节' % (len(FB), len(QB)))

# ---------------------------------------------------------------- B 编码
head(u'B. 编码（BOM / U+FFFD / 行尾不混用）')
for name, b, t in ((u'速查本', QB, QB_T), (u'详版', FB, FB_T), (u'日志', JB, JB_T)):
    check(u'B %s 无 BOM' % name, not b.startswith(b'\xef\xbb\xbf'))
    check(u'B %s 无 U+FFFD' % name, u'\ufffd' not in t, u'%d 次' % t.count(u'\ufffd'))
    _crlf = t.count(u'\r\n')
    _lf = t.count(u'\n') - _crlf
    check(u'B %s 行尾不混用（CRLF=%d / LF=%d）' % (name, _crlf, _lf),
          _crlf == 0 or _lf == 0)

# ---------------------------------------------------------------- C 新增在位
head(u'C. 本轮新增必须真在盘上')
for tok in (u'check133', u'133＝事件链闸', u'事件链装闸', u'§133'):
    check(u'C 速查本含 %s' % tok, tok in QB_T)
for tok in (u'## §133', u'§133.1', u'§133.4', u'§133.5', u'§133.8',
            u'first_sentence', u'strip_action_parentheticals', u'396'):
    check(u'C 详版含 %s' % tok, tok in FB_T)
for tok in (u'第133轮', u'判据自纠 6 处', u'6351'):
    check(u'C 日志含 %s' % tok, tok in JB_T)

# ---------------------------------------------------------------- D 删后有据
head(u'D. 本轮压缩过的令牌：仍可检索（速查本 or 详版，任一处即可）')
# ★ 第一版把 D 写成"速查本里必须已经没有了" ⇒ 报了 4 条红，红的是**我的假设**：
#   这几个令牌在 §7 里本来就有（压缩动的是 §10 的近轮要点，不是 §7）；
#   `check113` 更是 **`recheck113b` 的子串**（子串匹配的经典误报）。
#   真正要守的是"删掉的令牌还能找回来"，不是"它必须不在速查本里"。改成两处并集。
DROP = [u'room_area1', u'139 条', u'outertale', u'check124',
        u'训练偏好消歧', u'recheck113b']
for tok in DROP:
    where = []
    if tok in QB_T:
        where.append(u'速查本')
    if tok in FB_T:
        where.append(u'详版')
    check(u'D 仍可检索 %s' % tok, bool(where), u'在：%s' % (u'/'.join(where) or u'无'))
# 被压掉的**数字**必须整对保留（详版 §131 表格里是分开的两列，不是 `6/6→1/6` 这个箭头写法）
check(u'D2 第131轮 6/6 这个数在详版里还在', u'6/6' in FB_T)
check(u'D2b 第131轮 1/6 这个数在详版里还在', u'1/6' in FB_T)
check(u'D2c 第131轮 3/3 / 2/3 在详版里还在', u'3/3' in FB_T and u'2/3' in FB_T)
# 负控制：编一个不存在的令牌，上面那套检查必须判否（证明不是恒真）
check(u'D.n ★负控制：编造的令牌在两边都必须找不到',
      (u'这段令牌绝对不存在-133' not in QB_T)
      and (u'这段令牌绝对不存在-133' not in FB_T))

# ---------------------------------------------------------------- E 日志 append-only
head(u'E. 当日日志 append-only')
check(u'E1 上一轮（第132轮）的末段仍在（没被覆盖重写）',
      u'没发新请求验证"拦掉之后重采样出来的那句好不好"' in JB_T)
check(u'E2 本轮段落真的追加在**其后**',
      JB_T.find(u'## 第133轮') > JB_T.find(u'## 第132轮') >= 0,
      u'第132轮 @%d / 第133轮 @%d' % (JB_T.find(u'## 第132轮'),
                                      JB_T.find(u'## 第133轮')))
check(u'E3 日志里出现了本轮的实测数字（42 条 / 0/42 / 6351）',
      all(x in JB_T for x in (u'42 条真机', u'0/42', u'6351')))
check(u'E4 日志体积 ≥ 20 KB（只增不减）', len(JB) >= 20000, u'%d 字节' % len(JB))

# ---------------------------------------------------------------- F 守恒
head(u'F. 守恒账')
_q_lines = len([x for x in QB_T.splitlines() if x.strip()])
_f_secs = [x for x in FB_T.splitlines() if x.startswith(u'## §13')]
check(u'F1 详版 §13x 小节数 ≥ 4（130/131/132/133 都在）', len(_f_secs) >= 4,
      u'%d 个：%s' % (len(_f_secs), u' '.join(x[3:8] for x in _f_secs)))
check(u'F2 速查本行数在合理区间（56 → 未爆增）', 50 <= _q_lines <= 70,
      u'%d 行' % _q_lines)
check(u'F3 速查本仍是"铁律+索引+裁定"形态（不含本轮报告正文）',
      u'_evidence' not in QB_T and u'34/0' not in QB_T)

print(u'')
print(u'=' * 78)
print(u'recheck133_mem：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
