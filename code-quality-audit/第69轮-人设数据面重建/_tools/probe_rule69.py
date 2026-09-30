# -*- coding: utf-8 -*-
"""第69轮 · 反推第64轮的**组装规则**（用旧索引里记的 sha256 当硬真值）。

问题
----
`extract_personas69.py --write` 把尾块也写成了 CRLF ⇒ 50 条旧记录的
`bytes`/`chars`/`sha256` 全部与索引不符（`sha256_lf` 不变）。
需要知道第64轮到底怎么拼的，才能把 47 条**逐字节**还原回去。

硬真值
------
旧 `_personas.json` 里每条记着 `bytes` / `chars` / `sha256`（磁盘 CRLF 版本）。
⇒ 只有能**同时**复现这 50 组 (bytes, chars, sha256) 的规则才是对的。
（★ 判据不靠"我觉得应该这样"，靠历史 hash。）
"""
import hashlib
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
REL = 'ralsei_pet/assets/npc/persona'
N = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')

idx = json.loads(io.open(os.path.join(N, '_personas.json'), 'rb').read().decode('utf-8'))
old = {r['id']: r for r in idx['personas']}
TAIL = idx['tail_text']

print('tail_text 行数 = %d，内部 \\n = %d'
      % (len(TAIL.split('\n')), TAIL.count('\n')))
print('tail_text 结尾 = %r' % TAIL[-40:])
print('')
for i, l in enumerate(TAIL.split('\n')):
    print('  %2d | %s' % (i + 1, l[:70]))
print('')


def blobs(ids):
    out = {}
    for i in ids:
        p = '%s/%s.txt' % (REL, i)
        h = subprocess.run(['git', 'ls-files', '-s', '--', p],
                           cwd=ROOT, capture_output=True).stdout.decode().strip()
        if not h:
            continue
        out[i] = subprocess.run(['git', 'cat-file', 'blob', h.split()[1]],
                                cwd=ROOT, capture_output=True).stdout
    return out


IDS = sorted(old)
B = blobs(IDS)
print('取到 HEAD blob = %d / %d' % (len(B), len(IDS)))

# ---------- 候选规则 ----------
MARK = '【本项目补充'


def r_all_crlf(b):
    return b.replace(b'\n', b'\r\n')


def r_split_at_mark(b):
    """尾块（含其前导空行）保持 LF，正文转 CRLF。"""
    t = b.decode('utf-8', 'replace')
    i = t.index(MARK)
    return (t[:i].replace('\n', '\r\n') + t[i:]).encode('utf-8')


def r_split_before_blank(b):
    """正文（含尾块前的空行）转 CRLF，自 【本项目补充 起保持 LF。"""
    t = b.decode('utf-8', 'replace')
    i = t.index(MARK)
    j = t.rindex('\n', 0, i)          # 尾块前最后一个换行
    return (t[:j].replace('\n', '\r\n') + t[j:]).encode('utf-8')


def r_body1_tail(b):
    """正文 rstrip 后 + '\\n' + tail_text + '\\n'（尾块用 JSON 里的 LF 原文）。"""
    t = b.decode('utf-8', 'replace')
    i = t.index(MARK)
    body = t[:i].rstrip('\n')
    return (body.replace('\n', '\r\n') + '\n' + TAIL + '\n').encode('utf-8')


def r_body2_tail(b):
    """正文 rstrip 后 + '\\r\\n\\r\\n' + tail_text + '\\n'。"""
    t = b.decode('utf-8', 'replace')
    i = t.index(MARK)
    body = t[:i].rstrip('\n')
    return (body.replace('\n', '\r\n') + '\r\n\r\n' + TAIL + '\n').encode('utf-8')


def r_body2_tail_mixed(b):
    """正文 rstrip 后 + '\\n\\n' + tail_text + '\\n'（分隔两行都是裸 LF）。"""
    t = b.decode('utf-8', 'replace')
    i = t.index(MARK)
    body = t[:i].rstrip('\n')
    return (body.replace('\n', '\r\n') + '\n\n' + TAIL + '\n').encode('utf-8')


RULES = [r_all_crlf, r_split_at_mark, r_split_before_blank,
         r_body1_tail, r_body2_tail, r_body2_tail_mixed]

print('')
print('=== 规则命中率（判据：bytes + chars + sha256 三项全等）===')
best = None
for fn in RULES:
    hit = tot = 0
    for i in IDS:
        if i not in B:
            continue
        tot += 1
        raw = fn(B[i])
        r = old[i]
        if (len(raw) == r['bytes']
                and len(raw.decode('utf-8', 'replace')) == r['chars']
                and hashlib.sha256(raw).hexdigest() == r['sha256']):
            hit += 1
    print('  %-22s %3d / %3d' % (fn.__name__, hit, tot))
    if best is None or hit > best[1]:
        best = (fn, hit, tot)

print('')
print('★ 最佳规则 = %s（%d / %d）' % (best[0].__name__, best[1], best[2]))

# ---------- 逐条分类：每个文件是"哪些规则能命中" ----------
print('')
print('=== 逐条分类 ===')
buckets = {}
for i in IDS:
    if i not in B:
        continue
    r = old[i]
    names = []
    for fn in RULES:
        raw = fn(B[i])
        if (len(raw) == r['bytes']
                and len(raw.decode('utf-8', 'replace')) == r['chars']
                and hashlib.sha256(raw).hexdigest() == r['sha256']):
            names.append(fn.__name__)
    key = ','.join(names) if names else '<无规则命中>'
    buckets.setdefault(key, []).append(i)

for k in sorted(buckets, key=lambda x: -len(buckets[x])):
    print('  [%d] %s' % (len(buckets[k]), k))
    print('      %s' % ', '.join(buckets[k]))

