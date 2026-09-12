# -*- coding: utf-8 -*-
"""性能基准：真实系统上一次全量窗口枚举耗时，换算优化前后主线程阻塞比例"""
import os
import sys
import time

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from desktop_interaction import DesktopInteraction

di = DesktopInteraction.__new__(DesktopInteraction)
di.parent = None
di.privacy_apps = ['微信', 'QQ']
di.user_opened_privacy_apps = set()
di.update_timer = None

# 跑 3 次取平均（绕过缓存）
samples = []
for _ in range(3):
    t0 = time.perf_counter()
    wins = di.get_all_visible_windows(use_cache=False)
    samples.append((time.perf_counter() - t0) * 1000)

avg_ms = sum(samples) / len(samples)
n = len(wins)

print(f"可见窗口数: {n}")
print(f"单次全量枚举平均耗时: {avg_ms:.1f} ms（采样: {[f'{s:.1f}' for s in samples]} ms）")

# 优化前：floor 每 1s 一次 + nearby 每 3s 一次 → 60s 内 80 次
before_calls = 60 / 1.0 + 60 / 3.0  # 80
before_block = before_calls * avg_ms / 1000

# 优化后：floor 每 2s + nearby 每 5s，TTL 2s 合并 → 60s 内实际枚举约 30 次
after_calls = 60 / 2.0
after_block = after_calls * avg_ms / 1000

print(f"\n优化前: 约 {before_calls:.0f} 次/分 → 主线程阻塞 {before_block:.1f} 秒/分 ({before_block/60*100:.1f}%)")
print(f"优化后: 约 {after_calls:.0f} 次/分 → 主线程阻塞 {after_block:.1f} 秒/分 ({after_block/60*100:.1f}%)")
print(f"阻塞时间减少: {(1 - after_block / before_block) * 100:.0f}%")
