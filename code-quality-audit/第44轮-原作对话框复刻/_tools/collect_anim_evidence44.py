# -*- coding: utf-8 -*-
"""把 E:\\Download\\_tmp 下的动效普查产物蒸馏进仓库证据目录。"""
import io
import os

BASE = os.path.dirname(os.path.abspath(__file__))
E = os.path.join(BASE, '..', '_evidence')
SRC = r'E:\Download\_tmp\drw\chapter1_windows'

rows = []
rows.append('=== 原作动效全量普查（第44轮续 · anim44.csx @ chapter1_windows/data.win）===')
rows.append('')
rows.append(io.open(os.path.join(SRC, 'anim44.txt'), encoding='utf-8').read().strip())
rows.append('')
rows.append('=== sprite 播放参数（spranim44.csx，字段名 GMS2PlaybackSpeed）===')
KEEP = ('[', '多帧', 'spr_savepoint', 'spr_susier_plain', 'spr_krisu_bright',
        'spr_darkdoor', 'spr_shortcut_door', 'spr_giantdarkdoor', 'spr_fountainedge')
for ln in io.open(os.path.join(SRC, 'spranim44.txt'), encoding='utf-8').read().splitlines():
    if any(k in ln for k in KEEP):
        rows.append('  ' + ln)
rows.append('')
rows.append('=== 关键发现 ===')
rows.append('1) 背景层 HSpeed/VSpeed 非零 = 0 / 191'
      '  ⇒ 无背景滚动（复核第43轮：背景移动=相机平移，不是视差）')
rows.append('2) 图层 EffectType 非空 = 0       ⇒ 无 shader 特效层')
rows.append('3) 瓦片 AnimationFrames>1 = 0      ⇒ 无瓦片动画')
rows.append('4) 房间级 Sequence = 0             ⇒ 无时间轴演出')
rows.append('5) 多帧 sprite = 523 / 1097 (47.7%) ⇒ 唯一动效载体 = sprite 逐帧动画')
rows.append('6) GMS2PlaybackSpeed 全为 1、Type=FramesPerGameFrame、FPS=30'
      ' ⇒ 单帧 33.3ms')
rows.append('')
rows.append('=== 产品落地（第44轮续）===')
rows.append('· 数据层：多帧物件的 objects 元素加 anim{base,frames,frame_ms,src}')
rows.append('· 参数源：ralsei_pet/assets/scenes/_sprite_anim.json（6 个多帧 sprite）')
rows.append('· 渲染层：scene_render._anim_frame_index 按毫秒时间戳取帧')
rows.append('· 覆盖：532 场景 / 2043 objects 中 105 条带动画')
rows.append('    spr_savepoint 72 / spr_shortcut_door 23 / spr_darkdoor 5 /')
rows.append('    spr_krisu_bright 3 / spr_giantdarkdoor 1 / spr_susier_plain 1')
rows.append('')
rows.append('=== 踩坑留痕（必须保留）===')
rows.append('第一版脚本用 Speed / PlaybackSpeed 字段名（那是 GML 变量名），')
rows.append('在 UTMT 的 UndertaleSprite 上这两个属性**根本不存在** ⇒ 静默取到 null')
rows.append('⇒ 全表 speed=0 的**假数据**（会误推出「原作 sprite 都不动」的错误结论）。')
rows.append('正确字段名 = GMS2PlaybackSpeed / GMS2PlaybackSpeedType，')
rows.append('靠打印属性名清单（probespr44.csx）才发现。')
rows.append('教训：解析器/探针的输出必须先过「已知真值」锚点，否则"提取成功"'
      '不等于"提取正确"。')

out = os.path.join(E, '动效普查44.txt')
with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(rows) + '\n')
print('写入 %s  %d B' % (out, os.path.getsize(out)))
