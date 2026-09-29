# -*- coding: utf-8 -*-
"""速查本压缩后的：体积 + 结构自检 + 逐令牌回验（只读）。"""
import os, re

BASE = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory"
MEM = os.path.join(BASE, "MEMORY.md")
DET = os.path.join(BASE, "参考-契约与历轮（详版）.md")
USER_MEM = r"C:\Users\23002\.workbuddy\MEMORY.md"
OUT = r"E:\Download\_tmp\verify_mem_out.txt"

buf = []
def p(*a):
    buf.append(' '.join(str(x) for x in a))

raw = open(MEM, 'rb').read()
txt = raw.decode('utf-8')
js = len(txt.strip().encode('utf-16-le')) // 2
p("[体积] js_len = %d / 10000   余量 = %d   （目标 <=9500：%s）"
  % (js, 10000 - js, 'PASS' if js <= 9500 else 'FAIL'))
p("[体积] utf8 bytes = %d   codepoints = %d" % (len(raw), len(txt)))

# 结构自检
heads = re.findall(r'(?m)^## .*$', txt)
p("[结构] 章节数 = %d  (期望 12：%s)" % (len(heads), 'PASS' if len(heads) == 12 else 'FAIL'))
for h in heads:
    p("        " + h)
glued = [i + 1 for i, ln in enumerate(txt.split('\n')) if ln.startswith('##') and not ln.startswith('## ')]
p("[结构] 粘连标题 = %s  (期望 []：%s)" % (glued, 'PASS' if not glued else 'FAIL'))
p("[编码] BOM = %s（期望 False：%s）  U+FFFD 数 = %d（期望 0：%s）"
  % (raw[:3] == b'\xef\xbb\xbf', 'PASS' if raw[:3] != b'\xef\xbb\xbf' else 'FAIL',
     txt.count('\ufffd'), 'PASS' if txt.count('\ufffd') == 0 else 'FAIL'))
p("[编码] CRLF 数 = %d（本文件应为 0）" % txt.count('\r\n'))

det = open(DET, 'rb').read().decode('utf-8') if os.path.exists(DET) else ''
umem = open(USER_MEM, 'rb').read().decode('utf-8') if os.path.exists(USER_MEM) else ''
p("[回验] 详版字符数 = %d（utf8 bytes %d） ； 用户级 MEMORY 字符数 = %d" % (len(det), len(det.encode('utf-8')), len(umem)))

# 逐令牌回验：本轮从速查本删掉的可检索令牌
TOKENS = [
    "agent-memory-compaction",
    "自评失准",
    "7B",
    "红与黄",
    "幽灵族精灵",
    "上帝类",
    "spr_npc_",
    "行走动画",
    "Lancer",
    "13 份人设",
    "13 → 50",
    "幽灵",
    "scr_murderlv",
    "60 字符",
]
bad = []
for t in TOKENS:
    where = []
    if t in txt:
        where.append('速查本')
    if t in det:
        where.append('详版')
    if t in umem:
        where.append('用户级')
    tag = 'PASS' if where else 'FAIL'
    if not where:
        bad.append(t)
    p("[回验] %-26s %s   -> %s" % (repr(t), tag, ' + '.join(where) or '（哪里都没有！）'))
p("[回验] 汇总：缺失令牌 = %s  => %s" % (bad, 'PASS' if not bad else 'FAIL'))

# 负控制：确认判据能报红（人为造一个不存在的令牌）
neg = "____definitely_not_present____"
p("[负控制] 假令牌是否被判红：%s" % ('PASS' if (neg not in txt and neg not in det) else 'FAIL'))

open(OUT, 'w', encoding='utf-8').write('\n'.join(buf))
