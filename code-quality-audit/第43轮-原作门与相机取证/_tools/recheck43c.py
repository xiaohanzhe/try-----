# -*- coding: utf-8 -*-
"""第43轮 重要核心文件复检（记忆文件）——六类判据，逐项 PASS/FAIL 落盘。

复检脚本自己也会说谎 ⇒ 判据报红先怀疑判据（见 skill core-file-recheck）。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(REPO, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
OUT = os.path.join(REPO, 'code-quality-audit', '第43轮-原作门与相机取证',
                   '_evidence', '核心文件复检.txt')

rows = []


def chk(name, ok, detail):
    rows.append((name, bool(ok), detail))


def git(args):
    return subprocess.run(['git'] + args, cwd=REPO, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.decode('utf-8', 'replace')


mem_b = open(MEM, 'rb').read()
det_b = open(DET, 'rb').read()
mem = mem_b.decode('utf-8')
det = det_b.decode('utf-8')
head = git(['rev-parse', '--short', 'HEAD']).strip()

# ① 可解码 / 无控制字符
ctrl = [c for c in mem if ord(c) < 32 and c not in '\n\r\t']
chk('① 可解码·无控制字符', len(ctrl) == 0, '控制字符=%d' % len(ctrl))

# ② 结构自检：12 个标题全在 + 无超长粘连行
need = ['## 0. 铁律', '## 1. 环境', '## 2. git push', '## 3. 勿回退契约', '## 4. 验证脚本教训',
        '## 5. 人味改造线', '## 6. H4/H5', '## 7. 场景系统线', '## 8. 性能线', '## 9. 用户口径',
        '## 10. 历轮索引', '## 11. 🔴 待用户裁定']
miss = [h for h in need if h not in mem]
longlines = [(i + 1, len(l)) for i, l in enumerate(mem.split('\n')) if len(l) > 900]
chk('② 结构（12 标题齐+无超长行）', (not miss) and (not longlines),
    '缺=%s 超长行=%s' % (miss, longlines))

# ③ 编码：无 BOM / 无 U+FFFD / 纯 LF
bom = mem_b[:3] == b'\xef\xbb\xbf' or det_b[:3] == b'\xef\xbb\xbf'
fffd = mem.count('\ufffd') + det.count('\ufffd')
crlf_m, crlf_d = mem_b.count(b'\r\n'), det_b.count(b'\r\n')
chk('③ 编码（无BOM/无FFFD/纯LF）', (not bom) and fffd == 0 and crlf_m == 0 and crlf_d == 0,
    'BOM=%s fffd=%d CRLF(mem,det)=(%d,%d)' % (bom, fffd, crlf_m, crlf_d))

# ④ 恒真/占位复核
suspect = [w for w in ['TODO', 'FIXME', '待填', '占位符', 'XXXX', '\u0000'] if w in mem]
chk('④ 恒真/占位复查', not suspect, '可疑=%s' % suspect)

# ⑤ 逐令牌回验（基准 = HEAD 版 MEMORY.md）
old = git(['cat-file', 'blob', 'HEAD:.workbuddy/memory/MEMORY.md'])
toks = set()
for m in re.finditer(r'\b[0-9a-f]{7}\b', old):
    toks.add(m.group(0))
for m in re.finditer(r'§[0-9]+(?:\.[0-9]+)*', old):
    toks.add(m.group(0))
for m in re.finditer(r'`([^`\n]{4,80})`', old):
    s = m.group(1).strip()
    if re.search(r'[A-Za-z_]', s):
        toks.add(s)
for m in re.finditer(r'[A-Za-z0-9_\\.\-]*[\\/][A-Za-z0-9_\\.\-]{3,}', old):
    toks.add(m.group(0))
for m in re.finditer(r'\b[0-9][0-9,\.]{1,12}\b', old):
    toks.add(m.group(0))
for m in re.finditer(r'\b[A-Z][A-Z0-9_]{4,}\b', old):
    toks.add(m.group(0))
toks = {t for t in toks if len(t) >= 3} - {'000', '1000', '10000', '2000', '3000', '4000'}


def hit(t, txt):
    return (t in txt) or (t.lstrip('\u00a7') in txt)


def comp(t, txt):
    ps = [p for p in re.split(r'[\\/]+', t) if len(p) >= 3]
    return len(ps) >= 2 and all(p in txt for p in ps)


missing = [t for t in sorted(toks)
           if not (hit(t, mem) or hit(t, det)) and not (comp(t, mem) or comp(t, det))]
chk('⑤ 逐令牌回验（基准 %s）' % head, len(missing) == 0,
    '令牌=%d missing=%d %s' % (len(toks), len(missing), missing))

# ⑥ 注入上限
js = len(mem.strip().encode('utf-16-le')) // 2
chk('⑥ 注入上限 js_len', js <= 9999, 'js_len=%d (limit 9999, 余量 %d)' % (js, 9999 - js))

lines = ['# 第43轮 重要核心文件复检（记忆文件）', '',
         '基准提交 = %s' % git(['rev-parse', 'HEAD']).strip(),
         'MEMORY.md bytes=%d js_len=%d lines=%d' % (len(mem_b), js, mem.count('\n') + 1),
         '详版 bytes=%d lines=%d' % (len(det_b), det.count('\n') + 1), '', '---', '']
allok = True
for n, ok, d in rows:
    if not ok:
        allok = False
    lines.append('[%s] %s  —— %s' % ('PASS' if ok else 'FAIL', n, d))
lines += ['', '总判定：%s' % ('全部 PASS' if allok else '存在 FAIL')]

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
