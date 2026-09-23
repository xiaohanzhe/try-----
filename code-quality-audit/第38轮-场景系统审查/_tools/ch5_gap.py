# -*- coding: utf-8 -*-
"""第 38 轮：取出 ch5 被漏掉的 5 个官方命名地点 + ch2 多出的 2 条。只读。"""
import io
import json
import os
import re

DRW = r'E:\Download\_tmp\drw'
DR = r'E:\Download\_tmp\dr_out'
ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
out = []


def w(s=''):
    out.append(str(s))
    print(s)


def roomnames(chapter_folder, dump_folder):
    with io.open(os.path.join(DRW, chapter_folder, '_roomname_code.txt'),
                 'r', encoding='utf-8') as fh:
        txt = fh.read()
    with io.open(os.path.join(DR, dump_folder, 'rooms_map.json'), 'r',
                 encoding='utf-8') as fh:
        d = json.load(fh)
    rooms = d.get('rooms') if isinstance(d, dict) else d
    return txt, [str(r.get('name') or '') for r in rooms]


txt5, names5 = roomnames('chapter5_windows', 'chapter5_windows')
# 逐分支抓 (id, 该分支里的中文字面量 或 lang key)
blocks = re.split(r'if \(arg0 == (\d+)\)', txt5)
pairs = []
for i in range(1, len(blocks) - 1, 2):
    rid = int(blocks[i])
    body = blocks[i + 1]
    lits = re.findall(r'"([^"]{1,40})"', body)
    pairs.append((rid, lits[:4]))

w('=== ch5 scr_roomname 全部分支（26 条）===')
for rid, lits in pairs:
    res = names5[rid] if 0 <= rid < len(names5) else '?'
    flag = '  ← 我们漏了' if rid in (205, 222, 224, 225, 230) else ''
    w('  id=%-4d 资源名=%-34s 返回=%s%s' % (rid, res, lits, flag))
w('')

txt2, names2 = roomnames('chapter2_windows', 'chapter2_windows')
blocks2 = re.split(r'if \(arg0 == (\d+)\)', txt2)
w('=== ch2「多出」的 199 / 200（scr_roomname 里没有）===')
for rid in (199, 200):
    res = names2[rid] if 0 <= rid < len(names2) else '?'
    w('  id=%-4d 资源名=%s' % (rid, res))
w('')

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, 'ch5漏登记与ch2多登记.txt'), 'w',
             encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('ok')
