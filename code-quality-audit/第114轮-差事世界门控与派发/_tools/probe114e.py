# -*- coding: utf-8 -*-
"""探针 E（只读）：**门控放行矩阵** —— 为 rec114 的 C 段挑一个"真能去"的用例。

背景（`rec114` 离屏首跑抓到的两件事）
------------------------------------------------
  ① **真 bug**：`handle_errand_command` 门控拒绝时**不落记忆**（已修）。
  ② **判据用例设计错**：C 段拿 `susie` 派去 `oneshot` ⇒ 被拒。
     日志原文：`去不了（oneshot 不属于 苏西）`。
     ★ 这不是产品 bug —— 苏西是 Deltarune 角色、`RoamScope.HOME`，
       按第72轮口径她本来就进不去别人的暗世界。**别为让它变绿去放松门控**。

所以先在这里把"谁 → 去哪 → 放行吗"打成一张表，再据此改 C 段的用例。
★ 本探针**只读**：不派差事、不写盘、不改任何状态。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

from PyQt5.QtWidgets import QApplication  # noqa: E402
_app = QApplication.instance() or QApplication(sys.argv)

import main as M  # noqa: E402
from modules import npc_system as nsys  # noqa: E402

pet = M.RalseiPet()
reg = pet.npc_registry

# 目的地的"世界"（产品自己的口径）
DESTS = [
    ('ch1.kris_room.kris_s_room', '三角符文·光世界一侧'),
    ('ch1.card_castle.card_castle_1f', '三角符文·暗世界一侧'),
    ('oneshot.mainline.INIT', 'OneShot 起始'),
    ('oneshot.barrens.Blue', 'OneShot 荒野'),
    ('ut.rooms.room_start', 'UT 坠落处'),
    ('desktop', '电脑桌面'),
]

print('== 目的地 → 世界 ==')
WORLD = {}
for sid, label in DESTS:
    w = pet._npc_errand_world(sid)
    WORLD[sid] = w
    print('  %-34s %-22s -> %s' % (sid, label, w))

TARGETS = ['ralsei', 'susie', 'kris', 'lancer', 'os_niko', 'niko',
           'ut_papyrus', 'hy_sans']

print('\n== 角色档案 ==')
for tid in TARGETS:
    n = reg.get(tid)
    if n is None:
        print('  %-12s (注册表里没有)' % tid)
        continue
    print('  %-12s %-10s scope=%-9s chapters=%s carried=%s' % (
        tid, getattr(n, 'name_cn', '?'), getattr(n, 'roam_scope', '?'),
        list(getattr(n, 'chapters', ()) or ()),
        '?' if not hasattr(n, 'escape_via_bubble') else n.escape_via_bubble))

print('\n== 放行矩阵（os=无球；ball=装进球）==')
for tid in TARGETS:
    if reg.get(tid) is None:
        continue
    for sid, label in DESTS:
        w = WORLD[sid]
        for carried in (False, True):
            try:
                g = nsys.world_gate(reg.get(tid), w, scene_id=sid, carried=carried)
                res = 'OK  %s' % g.detail if g.ok else '拒  %s' % g.detail
            except Exception as e:
                res = '异常 %r' % (e,)
            print('  %-12s %-34s %-5s %s' % (
                tid, sid, 'ball' if carried else 'os', res))

print('\n== rec114 常用组合的"真候选目的地" ==')
for tid in TARGETS:
    if reg.get(tid) is None:
        continue
    good = [sid for sid, _ in DESTS
            if nsys.world_gate(reg.get(tid), WORLD[sid], scene_id=sid,
                               carried=False).ok]
    print('  %-12s 无球可去: %s' % (tid, good or '(无)'))

pet.close()
print('\n[done] probe114e 只读完成')
