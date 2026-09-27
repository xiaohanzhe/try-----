# -*- coding: utf-8 -*-
"""第56轮 · `check56` 鉴别力体检（mutation test）。

做法：对产品源码做 7 处**定点破坏**，每次跑一遍 `check56`，
断言"该报红的那条断言真的报红了"，然后**原样还原**。

为什么必须做：本项目最贵的坑是"**判据恒真**"和"**函数写对了却没人调用**"。
套件全绿只说明"没报红"，不说明"报红的能力存在"。这里逐条把能力验出来。

判据：每次破坏必须让**指定的那条**断言变 FAIL；破坏没命中真守卫（或套件根本没跑）
都会被这一层抓住（那时 `expected` 不出现 ⇒ 本体检自己报红）。

用法：C:\\Python311\\python.exe _tools\\mutate56.py
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
CHECK = os.path.join(ROUND, 'check56.py')

PL = os.path.join(PET, 'modules', 'npc_placement.py')
NS = os.path.join(PET, 'modules', 'npc_system.py')
MN = os.path.join(PET, 'src', 'main.py')

# (标签, 文件, 原文, 破坏后, 期望报红的断言前缀)
MUTATIONS = [
    ('M1 pace 零长度段改成"每帧都声称动过"', PL,
     '                #    那边已改成 `return False`，这里对齐。\n                return False',
     '                #    那边已改成 `return False`，这里对齐。\n                return True',
     'W12'),
    ('M2 结对每人走"整份超出量"（过冲 ⇒ 在 gap 附近抖）', PL,
     'half = min(step, rem * 0.5)', 'half = step',
     'B10c'),
    ('M3 结对朝向退回"只看 x"（上下两人都朝下看）', PL,
     "        facing_a = _facing_between(bx - ax, by - ay) or 'down'\n"
     "        facing_b = _facing_between(ax - bx, ay - by) or 'down'",
     "        facing_a = _facing_for(bx - ax) or 'down'\n"
     "        facing_b = _facing_for(ax - bx) or 'down'",
     'B13'),
    ('M4 编队 anchor 重复入队（落后量少一帧）', PL,
     'if trail.head() != ap:', 'if True:',
     'G6'),
    ('M5 错位量加错轴（污染"落后量"这条可测量）', PL,
     '                y += lat', '                x += lat',
     'G6'),
    ('M6 巡逻零长度段改成"每帧空转"', PL,
     '                self.alt -= 1\n                return False',
     '                self.alt -= 1\n                return True',
     'W6'),
    ('M7 pace 第一趟不上浮（回到 __init__ 恒取 ystart）', PL,
     "            #   ⇒ **从第一帧起就上浮**才是原样。\n"
     "            self.y_target = (self.ystart - ORIGINAL_PACE_RISE\n"
     "                             if self.target != self.xstart else self.ystart)",
     "            #   ⇒ **从第一帧起就上浮**才是原样。\n"
     "            self.y_target = self.ystart",
     'W11'),
    ('M8 桌面闸被短路（白名单外也放行）', NS,
     "        if desktop_allowed(npc):\n"
     "            return GateResult(True, REASON_OK, 'desktop_allowed')",
     "        if True:\n"
     "            return GateResult(True, REASON_OK, 'desktop_allowed')",
     'K2'),
    ('M9 桌面闸"只认 world 不认 scene_id"（数据层走的是 scene_id）', NS,
     "    if scene_id == DESKTOP_SCENE or world == DESKTOP_SCENE:",
     "    if scene_id == DESKTOP_SCENE and world == DESKTOP_SCENE:",
     'T21'),
    ('M10 每帧推进的调用点被摘掉（"写了没人调用"）', MN,
     'self.npc_placement_tick(elapsed_time)',
     'self._npc_placement_tick_removed(elapsed_time)',
     'T4'),
    ('M11 房间站位不再按场景筛（"全城的人都挤进这一间"）', MN,
     '                self.npc_bodies = book.initial_bodies(\n'
     '                    self._npc_scene_roster(scene_id))',
     '                self.npc_bodies = book.initial_bodies()',
     'T16'),
    ('M12 开局不播身体（"开局无人站位"）', MN,
     '            self._npc_seed_bodies(self._npc_scene_id())\n'
     '        except Exception as e:\n'
     '            _log.warning(\'NPC 站位初始化失败（开局无站位）: %s\', e)',
     '            pass\n'
     '        except Exception as e:\n'
     '            _log.warning(\'NPC 站位初始化失败（开局无站位）: %s\', e)',
     'T13'),
]


def run_check():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([sys.executable, '-X', 'utf8', CHECK],
                       cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=env)
    return p.stdout.decode('utf-8', 'replace')


def fails_of(out):
    return set(re.findall(r'^\[FAIL\] (\S+)', out, re.M))


def main():
    base = run_check()
    bf = fails_of(base)
    print('== 基线 ==')
    print('  rc=%s FAIL=%d %s' % ('0' if 'FAIL 0 项' in base else '?', len(bf), sorted(bf)))
    if bf:
        print('  ⚠️ 基线本来就红 ⇒ 体检中止')
        return 1
    ok = True
    for tag, path, old, new, expect in MUTATIONS:
        src = io.open(path, 'r', encoding='utf-8', newline='').read()
        if src.count(old) != 1:
            print('[FAIL] %s：破坏点出现 %d 次（应为 1）⇒ 源码变了？' % (tag, src.count(old)))
            ok = False
            continue
        try:
            io.open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new, 1))
            out = run_check()
            f = fails_of(out)
            hit = sorted(x for x in f if x == expect or x.startswith(expect))
            print('[%s] %s ⇒ 报红 %d 条，命中期望(%s)：%s %s'
                  % ('PASS' if hit else 'FAIL', tag, len(f), expect, hit or '（空！）',
                     sorted(f)[:6]))
            if not hit:
                ok = False
        finally:
            io.open(path, 'w', encoding='utf-8', newline='').write(src)
            # 逐字回验还原成功
            back = io.open(path, 'r', encoding='utf-8', newline='').read()
            if back != src:
                print('[FAIL] %s：还原失败！' % tag)
                ok = False
    # 收尾：确认已还原到基线（再跑一次必须全绿）
    after = run_check()
    print('== 还原后 ==')
    print('  FAIL=%d %s' % (len(fails_of(after)),
                            '(全绿)' if 'FAIL 0 项' in after else '(未恢复！)'))
    if 'FAIL 0 项' not in after:
        ok = False
    print('\n==== %s ====' % ('鉴别力体检通过' if ok else '有未命中，见上'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
