# -*- coding: utf-8 -*-
"""第94轮 · 睡眠定点探针：S3.3 根因（睡着后动画被覆盖成 idle）。

同时打印：
  · `sleep` / `idle` / `pose` 等动画的**容器尺寸**（= 该动画所有帧的最大 w/h），
    用来解释"S3 里窗口从 46x82 跳到 138x94"是不是动画切换引起的；
  · 睡眠期间每 0.1s 的状态快照（`is_sleeping` / `is_recovering` / `_play_once_active`
    / `is_splat` / `is_spellcasting` / `current_animation` / 窗口尺寸）。
"""
import ctypes
import io
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(SRC, 'src'), SRC, os.path.join(SRC, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVID = os.path.join(ROOT, 'code-quality-audit', '第94轮-基础宠物真机全功能验收', '_evidence')
OUT = os.path.join(EVID, 'probe94_sleep.txt')
_buf = []


def w(s=''):
    _buf.append(str(s))
    try:
        print(s, flush=True)
    except Exception:
        pass
    try:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_buf))
    except Exception:
        pass


from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

import main as main_mod

p = main_mod.RalseiPet()
app.processEvents()
if not p.isVisible():
    p.show()
app.processEvents()
w('=== 第94轮 睡眠定点探针 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))

# ---- ① 各动画的"容器尺寸"（= 该动画所有帧的最大 w/h，setGeometry 用的就是它） ----
w()
w('---- ① 动画容器尺寸（宽 x 高，按宽度排序；只列 >=100 宽的）----')
sizes = {}
for name, frames in (p.sprite_loader.sprites or {}).items():
    cw = ch = 0
    for f in (frames or []):
        if f is not None and not f.isNull():
            cw = max(cw, f.width())
            ch = max(ch, f.height())
    if cw:
        sizes[name] = (cw, ch)
for name, wh in sorted(sizes.items(), key=lambda kv: -kv[1][0])[:25]:
    w('  %-28s %sx%s' % (name, wh[0], wh[1]))
w()
w('  sleep = %r   idle = %r   pose = %r   walk_right = %r   run_right = %r'
  % (sizes.get('sleep'), sizes.get('idle'), sizes.get('pose'),
     sizes.get('walk_right'), sizes.get('run_right')))

# ---- ①.5 劫持 change_animation：谁把动画切走的，栈帧说话 ----
_calls = []
_orig_ca = p.change_animation


def _spy_ca(name, *a, **kw):
    try:
        import traceback as _tb
        st = _tb.extract_stack()
        # 只留本仓库内的帧，去掉探针自身
        frames = []
        for f in st[:-1]:
            fn = f.filename.replace('\\', '/')
            if 'probe94' in fn:
                continue
            frames.append('%s:%d(%s)' % (os.path.basename(fn), f.lineno, f.name))
        _calls.append((time.time(), name, kw.get('force', (a[0] if a else None)), ' <- '.join(frames[-4:])))
    except Exception:
        pass
    return _orig_ca(name, *a, **kw)


p.change_animation = _spy_ca

# ---- ② 睡眠期间状态快照 ----
w()
w('---- ② 入睡后每 0.1s 状态快照 ----')
p.wake_up()
app.processEvents()
time.sleep(0.3)
app.processEvents()
p.last_interaction_time = time.time() - 600.0
for _a in ('_sleep_stir_time', '_sleep_stir_count'):
    if hasattr(p, _a):
        try:
            delattr(p, _a)
        except Exception:
            pass
p.enter_sleep_mode()
app.processEvents()
w('  enter_sleep_mode() 后立即：is_sleeping=%r anim=%r'
  % (p.is_sleeping, p.current_animation))
_t_enter = time.time()
_calls.clear()

changed_at = None
prev = p.current_animation
for i in range(150):         # 150 x 0.1s = 15.0s（pet_ai 的 idle 冷却 2~5s ⇒ 至少覆盖 3 次重试）
    end = time.time() + 0.1
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    anim = p.current_animation
    flag = ''
    if anim != prev:
        flag = '   <== 变化 %r -> %r' % (prev, anim)
        if changed_at is None:
            changed_at = i * 0.1
        prev = anim
    w('  t=%4.1fs  anim=%-14r  is_sleeping=%-5r  is_recovering=%-5r  _play_once=%-5r  '
      'is_splat=%-5r  is_spellcasting=%-5r  size=%sx%s%s'
      % (i * 0.1, anim, p.is_sleeping, getattr(p, 'is_recovering', None),
         getattr(p, '_play_once_active', None), getattr(p, 'is_splat', None),
         getattr(p, 'is_spellcasting', None), p.width(), p.height(), flag))
    if changed_at is not None and i * 0.1 > changed_at + 1.0:
        break

w()
w('  首次动画变化发生在 t=%.1fs' % (changed_at if changed_at is not None else -1))
w()
w('---- ③ 入睡后所有 change_animation 调用（相对 enter_sleep_mode 的秒数）----')
for ts, name, force, stack in _calls:
    w('  t=%+5.2fs  %-16r force=%-5r  %s' % (ts - _t_enter, name, force, stack))

# ---- ④ 负控制①：守卫函数本身（正/负成对）----
w()
w('---- ④ 负控制①：pet_ai._skip_if_critical() 对 is_sleeping 的响应 ----')
_ai = getattr(p, 'pet_ai', None)
if _ai is None:
    w('  [SKIP] 无 pet_ai')
else:
    _was = p.is_sleeping
    p.is_sleeping = True
    _skip_sleep = _ai._skip_if_critical()
    p.is_sleeping = False
    _skip_awake = _ai._skip_if_critical()
    p.is_sleeping = _was
    w('  is_sleeping=True  -> _skip_if_critical()=%r（期望 True）' % _skip_sleep)
    w('  is_sleeping=False -> _skip_if_critical()=%r（期望 False，需先清掉别的关键状态）'
      % _skip_awake)
    w('  当前其它关键状态：_spell_stage=%r game.is_playing=%r _is_being_dragged=%r '
      'is_jumping=%r is_falling=%r'
      % (getattr(p, '_spell_stage', None),
         getattr(p, 'game_state', {}).get('is_playing'),
         getattr(p, '_is_being_dragged', False),
         getattr(p, 'is_jumping', False), getattr(p, 'is_falling', False)))

# ---- ⑤ 负控制②（B 修复的独立验证）：强行顶掉 sleep，看能否**自愈** ----
#   为什么需要这一段：A 修复后 pet_ai 不再触发 ⇒ B（force=True）**没被走到**，
#   不给它一个独立入口，B 就是"写了但没验"。这里模拟"任何外部系统把 sleep 顶掉"，
#   正确行为 = 下一个 update_animation 节拍（167ms）内自愈回 sleep。
w()
w('---- ⑤ 负控制②：睡眠中被强行改成 idle，是否自愈回 sleep ----')
_orig_ca('idle', force=True)          # 直接调原函数，绕过 ④ 的劫持记录
app.processEvents()
w('  强改后立即：anim=%r' % p.current_animation)
_healed = None
for i in range(60):                   # 最多 6s
    end = time.time() + 0.1
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    if p.current_animation == 'sleep':
        _healed = (i + 1) * 0.1
        break
w('  自愈耗时 = %s  末态 anim=%r  is_sleeping=%r'
  % (('%0.1fs' % _healed) if _healed is not None else '未自愈（>6s）',
     p.current_animation, p.is_sleeping))

try:
    p.close()
except Exception:
    pass
os._exit(0)
