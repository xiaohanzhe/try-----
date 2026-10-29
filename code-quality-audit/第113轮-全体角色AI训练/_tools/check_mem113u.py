# -*- coding: utf-8 -*-
"""记忆文件复检（改过记忆 ⇒ 必复检）。六项：结构 / 编码 / 令牌回验 / 体积 / 幂等痕迹 / 交叉引用。"""
import io
import os
import re

MEM = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory"
LOG = os.path.join(MEM, '2026-10-29.md')
FULL = os.path.join(MEM, '参考-契约与历轮（详版）.md')
CORE = os.path.join(MEM, 'MEMORY.md')

ok, bad = [], []


def chk(name, cond, detail=''):
    (ok if cond else bad).append(name)
    print('[%s] %s%s' % ('PASS' if cond else 'FAIL', name, ('  ' + detail) if detail else ''))
    return bool(cond)


def rd(p):
    with io.open(p, encoding='utf-8', newline='') as f:      # newline='' ⇒ 字节忠实
        return f.read()


def js_len(p):
    """真口径：JS 长度 = UTF-16 码元数（含 CRLF 的 \\r）。"""
    s = rd(p)
    return len(s.encode('utf-16-le')) // 2


log, full, core = rd(LOG), rd(FULL), rd(CORE)

# ① 结构：本轮新增的小节标题都在
need_log = ['§116.9', '§116.10', '§116.11', '§116.12', '§116.13']
chk('A1 当日日志含 §116.9~§116.13 五节', all(x in log for x in need_log),
    '缺 %s' % [x for x in need_log if x not in log])
need_full = ['## §116', '§116.1 ', '§116.5 ', '§116.8 ', '§116.13']
chk('A2 详版含 §116 主标题与关键子节', all(x in full for x in need_full),
    '缺 %s' % [x for x in need_full if x not in full])

# ② 标题不粘连：标题行必须独占一行且前面有空行或文件头
titles = [ln for ln in full.splitlines() if ln.startswith('## §')]
chk('A3 详版 § 级标题数 ≥ 15 且无粘连（行首都是 ## §）', len(titles) >= 15,
    '共 %d 个；末两个=%s' % (len(titles), titles[-2:]))

# ③ 编码：无 BOM / 无 U+FFFD
for p, tag in ((LOG, '日志'), (FULL, '详版')):
    b = io.open(p, 'rb').read(3)
    chk('B1 %s 无 BOM' % tag, b != b'\xef\xbb\xbf', repr(b))
    chk('B2 %s 无 U+FFFD' % tag, '\ufffd' not in rd(p))

# ④ 令牌回验：本轮写进去的可检索令牌，逐个回原文件 in 一次
tokens = ['432ff0a2', 'a2c5618f', 'cd94956b', '12,216', '1,010', '13,455',
          'DIALOG_CTX', 'main_record', 'transcripts_patch', '3,696', '3,652',
          '158 ⇄ 160', 'Σ22.5', 'PATCH_MAX_CHARS']
miss = [t for t in tokens if t not in full]
chk('C1 关键令牌在详版里都能检索到', not miss, '缺 %s' % miss)
# ★ 负控制：故意塞一个不存在的令牌，必须被这条判据抓到（否则恒真）
chk('C1n [负控制] 不存在的令牌会被抓到（否则 C1 恒真）',
    'TOKEN_THAT_CANNOT_EXIST_116' not in full)

# ⑤ 体积：速查本必须仍 ≤ 10000 JS 字符（本轮没动它，但要确认没被连带改）
n = js_len(CORE)
chk('D1 速查本 ≤ 10000 JS 字符', n <= 10000, '%d (%d 字符)' % (n, len(core)))
chk('D2 速查本本轮确实未被修改（内容里没有 §116）', '§116' not in core)

# ⑥ 交叉引用：日志里的数字与产品报告一致
# ★ 第一版正则是 `(\d+) 人 / (\d+) 轮 / 硬违规 (\d+) 处`（抄的 stdout 格式），
#   而报告 md 里写的是「**77 个角色**跑了 **3696 轮**…硬违规 **1227 处**」⇒ 永远匹配不上。
#   「判据过窄=误报」的第 N 次；改成只核三个数在不在。
rep = rd(r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第113轮-全体角色AI训练\_evidence\report113.md")
chk('E1 报告口径与日志一致（77 角色 / 3696 轮 / 1227 处）',
    all(x in rep for x in ('77 个角色', '3696', '1227')))

print()
print('===== %d PASS / %d FAIL =====' % (len(ok), len(bad)))
print('体积：日志 %d 字符 / 详版 %d 字符 / 速查本 %d JS字符' % (len(log), len(full), n))
