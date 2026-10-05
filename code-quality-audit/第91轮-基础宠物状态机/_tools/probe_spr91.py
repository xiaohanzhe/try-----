# -*- coding: utf-8 -*-
"""第91轮：直接问 SpriteLoader —— 'sleep' / 'walk_down_sleep' / 'idle' 到底加载出了什么？

这是「睡眠动画是否真的会播出」的最终判据：
  · 若 get_sprite('sleep') 返回 None ⇒ 名字登记了、但**帧加载不到** ⇒ 播出来仍是旧动画。
  · 若返回 QPixmap  ⇒ 真能渲染，再看尺寸/是否与 idle 不同。
必须先建 QApplication（裸进程脚本用 QPixmap 的前提）。
"""
import os
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
CWD = os.path.join(ROOT, 'ralsei_pet')
os.chdir(CWD)
sys.path.insert(0, CWD)

from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from modules.sprite_loader import SpriteLoader  # noqa: E402

try:
    s = SpriteLoader()
except TypeError as e:
    print('SpriteLoader() 需要参数:', e)
    raise SystemExit(1)

print('sprite_dir =', s.sprite_dir)
print('存在 =', os.path.exists(s.sprite_dir))
dct = [a for a in dir(s) if not a.startswith('__')
       and isinstance(getattr(s, a, None), dict)]
print('dict 属性:', dct)
for k in ('sleep', 'walk_down_sleep', 'idle', 'walk_down', 'sit', 'fall'):
    for f in (0, 1):
        try:
            sp = s.get_sprite(k, f)
        except Exception as e:
            print('%-16s f%d EXC %s' % (k, f, e))
            continue
        if sp is None:
            print('%-16s f%d -> None' % (k, f))
        else:
            print('%-16s f%d -> %s %dx%d' % (k, f, type(sp).__name__, sp.width(), sp.height()))
