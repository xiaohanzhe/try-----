# -*- coding: utf-8 -*-
"""回验缺口：用更宽的形态在速查本 ∪ 详版 ∪ 用户级里找等价令牌。"""
import os, re

BASE = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory"
MEM = os.path.join(BASE, "MEMORY.md")
DET = os.path.join(BASE, "参考-契约与历轮（详版）.md")
UMEM = r"C:\Users\23002\.workbuddy\MEMORY.md"
OUT = r"E:\Download\_tmp\verify_mem2_out.txt"

txt = open(MEM, encoding='utf-8').read()
det = open(DET, encoding='utf-8').read()
um = open(UMEM, encoding='utf-8').read()
allsrc = {'速查本': txt, '详版': det, '用户级': um}

PATTERNS = {
    'ghost_png_line': re.compile(r'.{0,90}45 PNG.{0,90}'),
    'sprite_family': re.compile(r'.{0,60}(族精灵|精灵族|个精灵|组精灵|10 组|family).{0,60}'),
    'walk_frame': re.compile(r'.{0,70}(行走帧|行走动画|walk 帧|walk帧|无行走|行走).{0,70}'),
    'persona13': re.compile(r'.{0,50}(13\s*份人设|13份人设|13 份人设|13 → 50|13→50).{0,50}'),
    'lancer_frame': re.compile(r'.{0,60}Lancer.{0,90}'),
}

buf = []
def p(*a):
    buf.append(' '.join(str(x) for x in a))

p("== 1) 速查本里 ghost 那行（确认我删掉了什么） ==")
for m in re.finditer(r'.{0,40}sprites/ghost.{0,120}', txt):
    p("  [速查本] " + m.group(0))

for name, pat in PATTERNS.items():
    p("")
    p("== %s ==" % name)
    hit = False
    for where, src in allsrc.items():
        for m in pat.finditer(src):
            hit = True
            p("  [%s] %s" % (where, m.group(0).replace('\n', ' ⏎ ')))
    if not hit:
        p("  （三处都没有）")

open(OUT, 'w', encoding='utf-8').write('\n'.join(buf))
