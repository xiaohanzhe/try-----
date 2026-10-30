# -*- coding: utf-8 -*-
u"""probe118_doors.py —— 真机探针：**走到看得见的那扇门上按 E，能不能进对应的世界？**

为什么点名这件事
----------------
第112轮续四起，四扇门**脱离房间图层**、改由屏幕层画在**屏幕四边中点**（用户逐字
「放到屏幕边缘哦」「那个门你单独放在外面呗」）。但**交互**一路没动过：
`main.interact_scene_prop()` 仍然把"实体位置"用 `screen_to_room()` 折回**房间逻辑坐标**，
再用房间坐标去和 `desktop.json` 里门的 `pos`（(64,0)/(64,112)/(0,70)/(140,42)）算射线。
⇒ **看得见的位置**（屏幕边缘）与**算得到的位置**（房间 320×240 内）不是同一处。

本探针要回答的三件事（四门逐一）：
  ① 站到**画出来的那扇门**上，`interact_scene_prop()` 选中了哪一件？
  ② 场景真的切过去了吗（切到了哪个 scene_id）？
  ③ 如果是靠"降级路径"碰巧选对的，如实记下来（那不是"看得见所以能点"）。

做法
----
真起 App（沙箱三闸），把桌宠窗口**中心**摆到门矩形的中心（= 视觉上站在门上），
朝向设为"朝屏幕外"，然后调**产品自己的**交互入口 `interact_scene_prop()`。
每次切换后回桌面再测下一扇。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118_doors.py
"""
import ctypes
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
OUT = os.path.join(ROUND, '_evidence')
os.makedirs(OUT, exist_ok=True)

# ---- 沙箱三闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='probe118_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                                  # noqa: E402
from PyQt5.QtCore import QTimer                                   # noqa: E402
from PyQt5.QtWidgets import QApplication                          # noqa: E402

L = []


def say(m):
    s = '[probe118] %s' % m
    L.append(s)
    sys.stdout.write(s + '\n')
    sys.stdout.flush()


M.check_single_instance()
M.install_crash_guard()
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
_W, _H = window._desktop_layer_size()
_W, _H = int(_W), int(_H)
say('沙箱=%s 画布=%dx%d' % (_SB, _W, _H))

# ★ `npc_interact` 的朝向是**字符串**（`FACE_DOWN='down'` …），不是 0/1/2/3。
FACE = {'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right'}
CASES = [('A', 'up', 'oneshot'), ('B', 'down', None),
         ('C', 'left', 'ut'), ('D', 'right', 'ch1')]
RES = []
_st = {'i': 0, 'phase': 'wait', 't': 0, 'cur': ''}


def _door_rects():
    u"""`{letter: (x,y,w,h)}` —— 直接问产品（`_desktop_screen_doors`），不自己算。"""
    out = {}
    try:
        items = window._desktop_screen_doors(_W, _H)
        for it in items:
            spr, r, a = it
            # 贴图名 → 字母（A/B/C/D 的 sprite 在 desktop.json 里一一对应）
            nm = str(spr)
            for k in ('oneshot_black', 'niko_door_portal', 'desk_door_ut',
                      'desk_door_deltarune'):
                if k in nm:
                    out[{'oneshot_black': 'A', 'niko_door_portal': 'B',
                         'desk_door_ut': 'C', 'desk_door_deltarune': 'D'}[k]] = tuple(r)
    except Exception as e:
        say('取门矩形失败 %r' % (e,))
    return out


def _scene_now():
    try:
        return str(getattr(window, 'current_scene', '') or '')
    except Exception:
        return ''


def _goto_desktop():
    try:
        if _scene_now() != 'desktop':
            window.travel_to_scene('desktop')
    except Exception as e:
        say('回桌面失败 %r' % (e,))


def _wrap_props():
    u"""给每件 prop 的 `interact` 套一层记录器 ⇒ 知道**谁**被选中（不只靠日志）。"""
    hit = {}
    for p in (getattr(window, 'item_props', None) or []):
        try:
            orig = p.interact

            def make(orig=orig, p=p):
                def f(actor=None):
                    hit['key'] = getattr(p, 'key', None)
                    hit['kind'] = type(p).__name__
                    try:
                        hit['desc'] = p.describe()
                    except Exception:
                        hit['desc'] = ''
                    return orig(actor)
                return f
            p.interact = make()
        except Exception:
            continue
    return hit


def tick():
    _st['t'] += 1
    if _st['t'] < 8:                      # 让启动那一串定时器先跑完
        return
    i = _st['i']
    rects = _door_rects()
    if _st['phase'] == 'wait':
        if not rects:
            return
        say('门矩形 = %r' % (rects,))
        _st['phase'] = 'reset'
        return

    if _st['phase'] == 'reset':
        _goto_desktop()
        if _scene_now() != 'desktop':
            return
        if i >= len(CASES):
            return _finish()
        _st['phase'] = 'run'
        return

    if _st['phase'] == 'run':
        letter, face, want = CASES[i]
        r = rects.get(letter)
        if not r:
            say('!! 缺门 %s 的矩形，跳过' % letter)
            _st['i'] += 1
            _st['phase'] = 'reset'
            return
        fg = window.frameGeometry()
        cx = int(r[0] + r[2] // 2)
        cy = int(r[1] + r[3] // 2)
        window.move(cx - fg.width() // 2, cy - fg.height() // 2)
        try:
            window._interact_facing = FACE[face]
        except Exception:
            pass
        app.processEvents()
        # 记录"产品自己怎么看这件事"
        try:
            actor = window._npc_interact_actor_room_xy()
        except Exception:
            actor = None
        try:
            f_now = window._npc_interact_facing()
        except Exception:
            f_now = None
        hit = _wrap_props()
        n_props = len(getattr(window, 'item_props', None) or [])
        before = _scene_now()
        # ★ B 是彩蛋门：交互会弹出**模态选择框**（`dr_choice`），不处理会把探针卡死。
        #   ⇒ 只对 B 打桩：记录"选择框被调用 + 选项文案"，返回"取消"（=我再考虑考虑）。
        _rec = {'chosen': None, 'opts': None}
        _orig_choose = None
        if letter == 'B':
            try:
                from modules import dr_choice as _dc
                _orig_choose = _dc.choose

                def _stub_choose(parent=None, options=None, scale=1.0,
                                 default_index=0, cancel_index=None, prompt=None):
                    _rec['opts'] = list(options or [])
                    _rec['prompt'] = prompt
                    _rec['default_index'] = default_index
                    return (cancel_index if cancel_index is not None else 1)
                _dc.choose = _stub_choose
            except Exception as e:
                say('!! 打桩 dr_choice 失败 %r' % (e,))
        ok = None
        try:
            ok = bool(window.interact_scene_prop())
        except Exception as e:
            say('!! 门 %s interact 抛异常 %r' % (letter, e))
        finally:
            if _orig_choose is not None:
                try:
                    from modules import dr_choice as _dc2
                    _dc2.choose = _orig_choose
                except Exception:                                # noqa: BLE001
                    pass
        app.processEvents()
        after = _scene_now()
        row = {'letter': letter, 'face': face, 'want_scene_prefix': want,
               'door_rect': list(r), 'pet_center': [cx, cy],
               'actor_room': list(actor) if isinstance(actor, tuple) else actor,
               'facing': f_now, 'n_props': n_props,
               'picked_key': hit.get('key'), 'picked_kind': hit.get('kind'),
               'picked_desc': hit.get('desc'),
               'choice_opts': _rec['opts'], 'choice_prompt': _rec.get('prompt'),
               'choice_default': _rec.get('default_index'),
               'interact_ok': ok, 'scene_before': before, 'scene_after': after}
        RES.append(row)
        say('门 %s：actor房间=%r 朝向=%r 选中=%r(%s) ok=%r 场景 %s → %s'
            % (letter, row['actor_room'], row['facing'], row['picked_key'],
               row['picked_kind'], ok, before, after))
        _st['i'] += 1
        _st['phase'] = 'reset'


def _finish():
    try:
        _goto_desktop()
    except Exception:
        pass
    p = os.path.join(OUT, 'probe118_doors.json')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'canvas': [_W, _H], 'results': RES},
                           ensure_ascii=False, indent=2))
    say('written %s' % p)
    say('--- 小结 ---')
    for r in RES:
        got = r['scene_after']
        want = r['want_scene_prefix']
        if want is None:
            # 门 B = 彩蛋门：**永远进不去** ⇒ 成功 = 选中 NikoHomeDoorProp 且交互"发生了"
            # （以前是 `ok=False` = 被准入门槛直接拒掉，连三连确认都不弹）。
            ok = (r.get('picked_kind') == 'NikoHomeDoorProp' and r.get('interact_ok') is True
                  and got == r['scene_before'])
            note = '彩蛋门：不进场景，只弹三连确认'
        else:
            ok = (got != r['scene_before']) and str(got).startswith(want)
            note = '期望前缀 %s' % want
        say('门 %s ⇒ %s（%s）%s' % (r['letter'], got, note, 'OK' if ok else '未达'))
    try:
        window.close()
    except Exception:
        pass
    app.quit()


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(60)
app.exec_()
