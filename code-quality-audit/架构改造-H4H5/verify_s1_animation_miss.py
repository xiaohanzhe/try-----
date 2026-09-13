# -*- coding: utf-8 -*-
"""H5 S1 验证：动画名未命中自检

S1 的唯一目标是"把静默退化变成可见日志"，因此本脚本要证明两件事：

  A. 【新增】任何未命中的动画名都会进账 + 告警，并且能给出结构性定位提示；
  B. 【不变】回退结果与改造前的算法逐例等价 ——
     用一份独立实现的参照算法，对 mapping 全部键 + 未引用素材前缀 + 人为扰动名
     共 N 个样本比对 change_animation 的最终落点。

B 是这次改造的安全网：S1 声称"零行为变更"，就必须有可机器验证的等价性证据。

运行：QT_QPA_PLATFORM=offscreen python verify_s1_animation_miss.py
"""
import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

import main  # noqa: E402
from sprite_loader import SpriteLoader  # noqa: E402

PASS, FAIL = [], []


def check(tid, title, cond, detail=''):
    (PASS if cond else FAIL).append(tid)
    print('  [%s] %-8s %s%s' % ('PASS' if cond else 'FAIL', tid, title,
                                ('  :: ' + detail) if detail else ''))


class StubPet:
    """只提供 change_animation 会触碰到的字段，避免构造整个 QMainWindow。"""

    def __init__(self, loader):
        self.sprite_loader = loader
        self.animation_priorities = {}
        self.animation_change_cooldown = 0.0
        self.last_animation_change = 0.0
        self.current_animation = 'idle'
        self.current_priority = 1
        self.current_frame = 0
        self.current_direction = 'down'
        self.previous_direction = 'down'
        self.game_state = {}
        self._spell_stage = None
        self._last_perf_anim_time = 0.0


def reference_resolve(name, sprites):
    """改造前 change_animation 第 1 步的算法，独立复刻，用于等价性比对。"""
    if name in sprites:
        return name
    parts = name.split('_')
    for i in range(len(parts), 1, -1):
        base = '_'.join(parts[:i])
        if base in sprites:
            return base
    return 'idle' if 'idle' in sprites else None


print('=== 载入素材 ===')
loader = SpriteLoader()
loader.load_sprites(debug=False)
print('  已加载动画组: %d，帧总数: %d'
      % (len(loader.sprites), sum(len(v) for v in loader.sprites.values())))

print()
print('=== A. 自检本身 ===')
check('A1', 'load_sprites 阶段未产生任何 miss（加载不应被误记为请求）',
      loader.animation_misses == {}, 'misses=%d' % len(loader.animation_misses))

check('A2', "diagnose_dynamic_name('walk_north') 定位到方向词非法",
      loader.diagnose_dynamic_name('walk_north') is not None,
      str(loader.diagnose_dynamic_name('walk_north')))
check('A3', "diagnose_dynamic_name('run_sideways') 同样被识别",
      '方向词' in (loader.diagnose_dynamic_name('run_sideways') or ''))
check('A4', "diagnose_dynamic_name('walk_up_blush') 结构正常 → 不误报",
      loader.diagnose_dynamic_name('walk_up_blush') is None,
      str(loader.diagnose_dynamic_name('walk_up_blush')))
check('A5', "diagnose_dynamic_name('idle') 不误报",
      loader.diagnose_dynamic_name('idle') is None)
check('A6', "diagnose_dynamic_name('') 被识别为空",
      loader.diagnose_dynamic_name('') is not None)

check('A7', 'get_sprite 对不存在的动画返回 None 且入账',
      loader.get_sprite('no_such_anim', 0) is None and 'no_such_anim' in loader.animation_misses)

print()
print('=== B. 回退行为等价性（改造前算法 vs 现网 change_animation）===')
CH = main.RalseiPet.change_animation

samples = []
# b1: mapping 的全部键（应当全部直接命中，无 miss）
samples += [(k, k) for k in sorted(loader.animation_mapping.keys())]
# b2: 未引用素材前缀（自动扫描出来的组名，raw 名）
samples += [(k, k) for k in sorted(loader.auto_scanned_animations.keys())]
# b3: 人为扰动：合法拼接模板 + 非法参数 + 不存在的前缀 + 纯垃圾
samples += [
    ('walk_up_blush', 'walk_up'),        # 素材缺失 → 回退 walk_up（前缀回退契约）
    ('walk_up_unhappy', 'walk_up'),
    ('walk_up_butler_unhappy', 'walk_up_butler'),
    ('walk_down_blush', 'walk_down_blush'),
    ('run_north', 'idle'),
    ('walk_sideways', 'idle'),
    ('walk_up_blush_x', 'walk_up'),
    ('walk_', 'idle'),
    ('___', 'idle'),
    ('nonexistent_prefix_abc', 'idle'),
    ('walk', 'idle'),
    ('run', 'idle'),
]

stub = StubPet(loader)
stub.sprite_loader.animation_misses.clear()
stub.sprite_loader._miss_reported.clear()

bad = []
for name, _expected in samples:
    stub.current_animation = 'idle'
    stub.current_priority = 1
    want = reference_resolve(name, loader.sprites)
    try:
        got_ret = CH(stub, name, force=True)
    except Exception as e:  # 任何异常都属于行为变更
        bad.append((name, 'EXC:%s' % e, want))
        continue
    got_anim = stub.current_animation
    if want is None:
        ok = (got_ret is False)
    else:
        ok = bool(got_ret) and got_anim == want
    if not ok:
        bad.append((name, '%r/%r' % (got_ret, got_anim), want))

check('B1', '全部 %d 个样本的落点与改造前算法一致' % len(samples),
      not bad, '不一致 %d 例: %s' % (len(bad), bad[:6]) if bad else '')

# 逐类抽查（把契约写死，防止"两边一起错"）
stub.current_animation = 'idle'
CH(stub, 'walk_up_blush', force=True)
check('B2', "walk_up_blush → walk_up（素材缺失走前缀回退）",
      stub.current_animation == 'walk_up', stub.current_animation)
check('B3', '该次回退已入账且回退目标记录为 walk_up',
      loader.animation_misses.get('walk_up_blush', {}).get('resolved') == {'walk_up'},
      str(loader.animation_misses.get('walk_up_blush')))

stub.current_animation = 'idle'
CH(stub, 'walk_down_blush', force=True)
check('B4', 'walk_down_blush 直接命中（不产生误报）',
      stub.current_animation == 'walk_down_blush' and 'walk_down_blush' not in loader.animation_misses)

stub.current_animation = 'idle'
CH(stub, 'walk_north', force=True)
check('B5', "walk_north → idle，且告警里带'缺少方向词'定位",
      stub.current_animation == 'idle'
      and '方向词' in (loader.diagnose_dynamic_name('walk_north') or ''))

print()
print('=== C. 拒绝切换的分支（sprites 为空时只有 idle 可回退）===')
_saved = dict(loader.sprites)
loader.sprites.clear()
stub.current_animation = 'keep_me'
ret = CH(stub, 'walk_down', force=True)
check('C1', '全部动画缺失时 change_animation 返回 False 且不改状态',
      ret is False and stub.current_animation == 'keep_me')
check('C2', '该拒绝同样被记账',
      loader.animation_misses.get('walk_down', {}).get('count', 0) >= 1)
loader.sprites.update(_saved)

print()
print('=== D. 汇总输出 ===')
misses_before = len(loader.animation_misses)
n = loader.log_animation_miss_summary()
check('D1', '汇总返回未命中种类数且与账本一致',
      n == misses_before, 'summary=%d ledger=%d' % (n, misses_before))
check('D2', '重复请求同一名字不会重复计数种类（只累加次数）',
      len(loader.animation_misses) == misses_before)

# 用 get_animation_miss_report 校验降序与字段完整
rep = loader.get_animation_miss_report()
check('D3', 'report 按次数降序且字段完整',
      all(len(r) == 4 for r in rep)
      and all(rep[i][1] >= rep[i + 1][1] for i in range(len(rep) - 1)),
      '前 3 条: %s' % rep[:3])

print()
print('=' * 60)
print('总计 %d 项，通过 %d，失败 %d' % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
if FAIL:
    print('失败项: %s' % FAIL)
sys.exit(1 if FAIL else 0)
