# -*- coding: utf-8 -*-
u"""第168轮 · 把 UTMT 取证产物收敛成一份**机器可读**的证据 `_evidence/doors168.json`。

输入（本脚本不改它们，只解析）：
    <本目录>/_evidence/probe168_ch1.txt
    <本目录>/_evidence/probe168_ch2.txt
两份都是 `_tools/probe168.csx` 的输出（`UndertaleModCli.exe load <data.win> -s probe168.csx`，
★ `stdin` 必须是 DEVNULL，否则 .NET 的 `ConsolePal.GetCursorPosition()` 挂死、日志 0 字节）。

输出 `doors168.json` 三段：
    marker_objects  {章: {对象名: sprite 名}}   —— 证 `obj_markerw` 有专属 `spr_markerW`、
                                                   `obj_markerX` 是**字母 X** 而不是通用
    entrance        {门对象: entrance 值}        —— 证 W 与 A/B/C/D/X 同一套机制
    door_codes      {门对象: Alarm_2 的 code 名}
判据 `check168.E` 读的就是这份（不是读注释）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'doors168.json')

MK = re.compile(r'^  (obj_marker\S*)\s+sprite=(\S*)\s+parent=')
ENT = re.compile(r'^  (gml_Object_obj_\S+?)\s+entrance=(-?\d+)\s+room_guard_cmp=(\d+)\s+ins=(\d+)')
DOOR = re.compile(r'^### (gml_Object_obj_door\S+?)\s+ins=')


def parse(path):
    mrk, ent, codes = {}, {}, {}
    if not os.path.isfile(path):
        raise SystemExit(u'缺取证文件 %s' % path)
    for ln in io.open(path, encoding='utf-8', errors='replace', newline='').read().split('\n'):
        m = MK.match(ln)
        if m:
            mrk[m.group(1)] = m.group(2)
            continue
        m = ENT.match(ln)
        if m:
            ent[m.group(1)] = {'entrance': int(m.group(2)),
                               'room_guard_cmp': int(m.group(3)),
                               'ins': int(m.group(4))}
            continue
        m = DOOR.match(ln)
        if m:
            codes[m.group(1)] = m.group(1)
    return mrk, ent, codes


out = {'note': (u'第168轮 UTMT 取证收敛。源文件 probe168_ch1.txt / probe168_ch2.txt '
                u'由 _tools/probe168.csx 生成；本文件由 _tools/make_evidence168.py 收敛，'
                u'判据 check168.E 直接读这份。'),
       'chapters': {}}
for ch in ('ch1', 'ch2'):
    p = os.path.join(EV, 'probe168_%s.txt' % ch)
    mrk, ent, codes = parse(p)
    out['chapters'][ch] = {'marker_objects': mrk,
                           'door_entrance': ent,
                           'door_codes': sorted(codes)}
    print(u'%s：marker %d 个 / door 机制 %d 条' % (ch, len(mrk), len(ent)))

text = json.dumps(out, ensure_ascii=False, indent=1)
io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))
