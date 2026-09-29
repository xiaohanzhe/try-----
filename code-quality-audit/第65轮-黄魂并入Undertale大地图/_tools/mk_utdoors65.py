# -*- coding: utf-8 -*-
u"""由 dump_uty65.csx 生成 Undertale 版变体 dump_utdoors65.csx。

为什么不复制粘贴：两份 csx 只差 4 处（输出前缀 / 环境变量名 / 匹配集合），
复制会带来"改了 A 忘了改 B"的漂移风险 ⇒ 用程序化变换生成，并把变换规则写在注释里。

差异：
  1. 环境变量 R65_OUT -> UT65_OUT；缺省目录 r65/ -> u65/
  2. 产物前缀 r65_ -> u65_，GML 目录 gml65/ -> gml65ut/
  3. 匹配集合加入 obj_marker* （Undertale 的落点对象，需连代码一起看）
"""
from __future__ import print_function
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, u'dump_uty65.csx')
DST = os.path.join(HERE, u'dump_utdoors65.csx')

s = io.open(SRC, encoding='utf-8').read()

REPL = [
    (u'R65_OUT', u'UT65_OUT'),
    (u'"r65"', u'"u65"'),
    (u'r65_rooms.json', u'u65_rooms.json'),
    (u'r65_doorinst.json', u'u65_doorinst.json'),
    (u'r65_index.json', u'u65_index.json'),
    (u'r65_objnames.txt', u'u65_objnames.txt'),
    (u'r65_codenames.txt', u'u65_codenames.txt'),
    (u'r65_log.txt', u'u65_log.txt'),
    (u'"gml65"', u'"gml65ut"'),
    (u'dump65 rooms=', u'dumpdoors65ut rooms='),
    (u'datafile 同级的 r65/', u'datafile 同级的 u65/'),
    # 匹配集合：加入 marker
    (u'    "obj_fakedoorway", "obj_locked_door", "obj_dalvDoor", "obj_doorparent"',
     u'    "obj_fakedoorway", "obj_locked_door", "obj_dalvDoor", "obj_doorparent",\n'
     u'    "obj_markerparent", "obj_markerA", "obj_markerB", "obj_markerC", "obj_markerD"'),
    (u'    if (s.StartsWith("obj_doorway")) return true;',
     u'    if (s.StartsWith("obj_doorway")) return true;\n'
     u'    if (s.StartsWith("obj_marker")) return true;'),
    # 锚点按"游戏身份"分派：黄魂用 obj_doorway/obj_exit/obj_door；
    # Undertale（含红与黄 mod）用 obj_doorA~D —— 这两套名字不通用，
    # 第65轮就因为给 Undertale 用了黄魂锚点而 anchorHIT=0（判据侧错，不是提取失败）。
    (u'string[] MUST_HIT = new string[] { "obj_doorway", "obj_exit", "obj_door" };',
     u'string[] MUST_HIT = new string[] { "obj_doorA", "obj_doorB", "obj_doorC", "obj_doorD" };'),
]
for a, b in REPL:
    if a not in s:
        raise SystemExit(u'!! 变换锚点缺失（说明源文件变了）：%r' % a)
    s = s.replace(a, b)

s = s.replace(u'// 第65轮 · 黄魂（Undertale Yellow）门实例 + 门对象代码 转储',
              u'// 第65轮 · Undertale 门/落点对象代码 转储（由 dump_uty65.csx 程序化生成）')

io.open(DST, 'w', encoding='utf-8', newline='\n').write(s)
print(u'OK -> %s  (%d bytes)' % (DST, len(s.encode('utf-8'))))
