# -*- coding: utf-8 -*-
"""第十五轮 · 真机启动路径冒烟（离屏）。

为什么还要跑这个：G2 各套件都是"只装需要的表面"的 stub 驱动 —— 能证明**被测的那条链**
没坏，但证明不了"整只宠物还能起来"。本轮删了 main.py 里 155 + 67 行（含 movement 主循环
每 1 秒会走到的 `check_window_movement` 分支），所以额外起一次**真的 RalseiPet**，
把"楼层刷新 / 楼层检查 / 跳跃检查 / 重力坠落"四条链在真实对象上各跑一遍。

隔离：启动前就设 `RALSEI_MEMORY_DIR` → `find_device_dir` 见到即 return，
既不碰用户真实 E 盘、也不触发沙箱删除配额守卫（见 MEMORY 环境铁律 9）。

结果自己写 UTF-8 文件（不用 PowerShell 捕获 —— 中文会二次编码成方块字）。
"""
import io
import os
import sys
import tempfile
import time
import traceback

OUT = os.environ.get('R15_SMOKE_OUT') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '_out_smoke.txt')
iso = tempfile.mkdtemp(prefix='r15_smoke_')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(iso, 'RalseiMemory')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

lines = []
fails = []


def say(msg):
    lines.append(msg)


def step(name, fn):
    try:
        r = fn()
        say('[ OK ] %s  -> %s' % (name, r))
        return r
    except Exception as e:
        fails.append('%s :: %s' % (name, e))
        say('[FAIL] %s  -> %s' % (name, e))
        say(traceback.format_exc())
        return None


from PyQt5.QtWidgets import QApplication            # noqa: E402

app = QApplication.instance() or QApplication([])
say('RALSEI_MEMORY_DIR = %s' % os.environ['RALSEI_MEMORY_DIR'])
say('QT_QPA_PLATFORM  = %s' % os.environ['QT_QPA_PLATFORM'])

import main as M                                    # noqa: E402
say('main.py 行数 = %d' % len(io.open(os.path.join(PET, 'src', 'main.py'),
                                     encoding='utf-8').read().split('\n')))

pet = None
try:
    pet = M.RalseiPet()
    say('[ OK ] RalseiPet() 实例化成功')
except Exception as e:
    fails.append('RalseiPet() :: %s' % e)
    say('[FAIL] RalseiPet() 实例化失败 -> %s' % e)
    say(traceback.format_exc())

if pet is not None:
    step('floor_manager.update_floors()',
         lambda: 'floors=%d underlying_windows=%d'
                 % (len(pet.floor_manager.floors),
                    len(pet.floor_manager.underlying_windows)))
    step('floor_manager.is_floor_valid(desktop)',
         lambda: pet.floor_manager.is_floor_valid(pet.floor_manager.desktop_floor))
    step('check_window_movement() ×3（1 秒节拍那条链）',
         lambda: [pet.check_window_movement() for _ in range(3)] and 'no exception')
    step('check_nearby_windows(pos)（跳跃决策；本轮删掉了尾部老启发式）',
         lambda: pet.check_nearby_windows(pet.pos()) or 'no exception')

    def _fall():
        pet.start_falling()
        frames = 0
        for i in range(600):
            frames = i
            pet.handle_gravity_fall(0.033, time.time())
            if not getattr(pet, 'is_gravity_falling', False):
                break
        return 'frames=%d landed=%s z=%s' % (
            frames, getattr(pet.current_floor, 'get', lambda k, d=None: '?')('type'),
            pet.spatial_pos.get('z'))
    step('start_falling() → handle_gravity_fall() 直到落地', _fall)

    def _jump():
        fm = pet._floors_for_jump()
        if fm is None:
            return '无可见窗口（离屏环境正常）→ 楼层为空，不跳跃'
        cur = getattr(pet, 'current_floor', None) or fm.desktop_floor
        from PyQt5.QtCore import QRect
        rect = QRect(pet.pos().x(), pet.pos().y(), pet.width(), pet.height())
        plan = pet._nearest_floor_jump(fm, cur, rect)
        return 'floors=%d cur=%s plan=%s' % (
            len(fm.floors), cur.get('type'), 'None' if plan is None
            else (plan[0].get('type'), plan[1]))
    step('_nearest_floor_jump()（跳跃规划，不改状态）', _jump)

say('')
say('结论：%s' % ('全部通过' if not fails else '有 %d 项失败' % len(fails)))
for f in fails:
    say('  FAIL: %s' % f)

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(lines) + '\n')

# 离屏退出：Qt 事件循环里可能挂着托盘/定时器，直接 os._exit 保干净退出码
os._exit(1 if fails else 0)
