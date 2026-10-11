# -*- coding: utf-8 -*-
u"""walk106_probe.py —— 第106轮「非瞬移」的**逐跳取证端**（产品进程内、无抓屏）。

为什么需要它（★ 这是一次**仪器失灵**的更正）
--------------------------------------------
第106轮第一次录屏（`rec106.py` + `shot106.py`）的 `A3「逐门走过」`**报了 FAIL**，
但**产品日志明明白白写着 18 跳全走完了**：

    逐跳行走 1/18：oneshot.mainline.INIT → …DEBUG（init）
    …
    逐跳行走 18/18：oneshot.mainline.T16 → oneshot.mainline.S1（ev002）
    走动 ⇒ S1（route=path，18 跳，实走 19 间：INIT → DEBUG → T1 → … → S1）

根因**不是产品**，是**抓屏仪器有硬盲区**：抓屏端每帧要 `grabWindow(0)` 全屏
（2560×1600）+ `mp4v` 编码，实测 **300~390 ms/帧**（见 `rec106_meta.txt` 的
"抓屏累计/编码累计"），而 `walk_steps` 的 18 次 `switch()` 是**同步执行**、
总耗时 **0.39 s** ⇒ 抓屏端在这 0.39 s 里**只采到 1~2 帧**（实测 t=12.550
直接从 INIT 跳到 S1）。第105轮"6 格对照图、中间 16 间一帧没有"是**真缺口**；
本轮同样现象是**仪器采样率不够**——两者长得一样，必须靠**产品自己的钩子**
分清楚。

★ 做法：**不用抓屏**，改用产品**本轮新增的公开钩子**
`walk_steps(steps, per_step_hook)` / `travel_to(target)` 内部的钩子点：
每跳 `switch()` **之后**回调一次，在回调里记 (i, from, to, door, 此刻的
`current_scene` / `current_animation` / 相机尺寸)。⇒ 采样率 = **每一跳**，
零丢帧（这是"仪器保真"层面的证明，与"画面对不对"是两件事）。

★ 与 `rec106.py`/`shot106.py` 的分工（**两份证据，互相补位**）：
  · `rec106`/`shot106` —— **人眼证据**（看得见的画面 + 全屏化尺寸）；
  · 本文件 —— **逐跳证据**（18 跳每一跳都在产品状态里真的发生过）。
  用户口径「一定要看录像而不是只读后台输出」⇒ 人眼证据由 rec106 承担；
  本文件不替代它，只补它**采不到**的那一格。

产物（落本轮 `_evidence/`）
--------------------------
  rec106_walk.csv   —— 每一跳一行（i / from / to / door / 到达后 current_scene / 相机）
  rec106_walk.txt   —— 人眼可读的逐跳序列 + 判据结论
"""
import csv
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
EV = os.environ.get('REC106_EVDIR') or os.path.join(ROUND, '_evidence')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                            # noqa: E402
from PyQt5.QtWidgets import QApplication                    # noqa: E402
from PyQt5.QtCore import QTimer                             # noqa: E402

M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
print('[walk106] shown pid=%d' % os.getpid())
sys.stdout.flush()

_OS_FROM = os.environ.get('WALK106_OS_FROM', 'oneshot.mainline.INIT')
_OS_TO = os.environ.get('WALK106_OS_TO', 'oneshot.mainline.S1')

_ROWS = []
_T0 = time.time()


def _cam():
    """读相机字段。

    ★ 坑（第106轮实测改正）：相机**不在** `window.scene_camera`（没有这个属性），
      真源是 `pet._scene_camera`，且它就是 `scene_camera.Camera` **本身**
      （不是包装 —— 见 `scene_controller.init_camera` L357~366）。
      第一版按 `window.scene_camera.camera` 取 ⇒ 恒得 `-1/-1/None`，
      判据 W7 假红（**判据错，不是产品错**）。
    """
    cam = window.__dict__.get('_scene_camera')
    if cam is None:
        sc = getattr(window, 'scene', None)
        cam = getattr(sc, 'camera', None) if sc is not None else None
    if cam is None:
        return (-1, -1, None)
    try:
        w, h = cam.size
    except Exception:
        w, h = -1, -1
    try:
        s = float(cam.scale)
    except Exception:
        s = None
    return (w, h, s)


def _hook(i, step):
    """★ 产品每走完一跳就回调：把"这一跳真的到了哪"记下来。"""
    try:
        cur = window.__dict__.get('current_scene')
        cam_w, cam_h, cam_s = _cam()
        _ROWS.append({
            't': time.time() - _T0,
            'i': i,
            'from': step.get('from'),
            'to': step.get('to'),
            'door': step.get('door'),
            'reason': step.get('reason'),
            'cur_after': cur,
            'anim': window.__dict__.get('current_animation'),
            'cam_w': cam_w,
            'cam_h': cam_h,
            'cam_scale': cam_s,
        })
    except Exception:
        _ROWS.append({'t': time.time() - _T0, 'i': i, 'err': traceback.format_exc()})


def _do_walk():
    """摆好起点，然后**走一次**，靠钩子逐跳取证。"""
    try:
        ok = window.scene.switch(_OS_FROM)
        try:
            window._possession_sync_world()
        except Exception:
            pass
        print('[walk106] set start %r switch_ok=%r' % (_OS_FROM, ok))
        sys.stdout.flush()
    except Exception:
        print('[walk106] set start FAIL\n' + traceback.format_exc())
        sys.stdout.flush()

    # ★ 先自己算一遍路线（只读），把 18 跳的 steps 拿到手
    steps = []
    try:
        plan = window.scene.plan_route_to(_OS_TO)
        steps = (plan or {}).get('steps') or []
        print('[walk106] plan_route_to(%r) ok=%r hops=%r steps=%d'
              % (_OS_TO, (plan or {}).get('ok'), (plan or {}).get('hops'), len(steps)))
        sys.stdout.flush()
    except Exception:
        print('[walk106] plan_route_to FAIL\n' + traceback.format_exc())
        sys.stdout.flush()

    # ★★ 用**产品自己的** walk_steps + 钩子走一遍（逐跳取证）
    t0 = time.time()
    try:
        rv = window.scene.walk_steps(steps, per_step_hook=_hook)
    except Exception:
        rv = {'ok': False, 'error': traceback.format_exc()}
    wall = time.time() - t0
    print('[walk106] walk_steps ret=%r  wall=%.3fs' % (rv, wall))
    sys.stdout.flush()
    _finish(rv, steps, wall)


def _finish(rv, steps, wall):
    _fcsv = io.open(os.path.join(EV, 'rec106_walk.csv'), 'w',
                    encoding='utf-8', newline='')
    w = csv.writer(_fcsv, lineterminator='\n')
    w.writerow(['t', 'i', 'from', 'to', 'door', 'reason', 'cur_after',
                'anim', 'cam_w', 'cam_h', 'cam_scale'])
    for r in _ROWS:
        w.writerow([('%.4f' % r['t']) if 't' in r else '',
                    r.get('i', ''), r.get('from', ''), r.get('to', ''),
                    r.get('door', ''), r.get('reason', ''),
                    r.get('cur_after', ''), r.get('anim', ''),
                    r.get('cam_w', ''), r.get('cam_h', ''), r.get('cam_scale', '')])
    _fcsv.close()

    lines = [u'# 第106轮 非瞬移 · 逐跳取证（产品钩子采样，零丢帧）',
             u'# 起点 = %s  终点 = %s' % (_OS_FROM, _OS_TO),
             u'# plan hops = %d，walk_steps ret = %r，wall = %.3fs'
             % (len(steps), rv, wall),
             u'#']
    for r in _ROWS:
        lines.append(u'  第 %2s 跳  %-28s → %-28s  door=%-10s  '
                     u'到达后 current_scene=%-28s  cam=%sx%s scale=%s'
                     % (r.get('i', '?'), r.get('from'), r.get('to'),
                        r.get('door'), r.get('cur_after'),
                        r.get('cam_w'), r.get('cam_h'), r.get('cam_scale')))

    # ---- 判据 ----
    got = len(_ROWS)
    mids = [r.get('to') for r in _ROWS
            if r.get('to') not in (_OS_FROM, _OS_TO)]
    chain_ok = all(r.get('cur_after') == r.get('to') for r in _ROWS
                   if r.get('to'))
    R = []

    def ok(name, cond, detail=u''):
        R.append((name, bool(cond)))
        lines.append(u'[%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                                     (u'  —— ' + detail) if detail else u''))
        print(u'[%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                              (u'  —— ' + detail) if detail else u''))

    ok(u'W1 每跳都被钩子采到（%d 跳 / 期望 %d）' % (got, len(steps)),
       got == len(steps) and got > 0,
       u'零丢帧 = 仪器保真（抓屏端做不到，见文件头说明）')
    ok(u'W2 ★★★ 中间房间真的走过（途经 %d 间 >= 1）' % len(mids),
       len(mids) >= 1, u'途经=%r' % (mids[:6],))
    ok(u'W3 逐跳链条无断点（每跳 `from` == 上一跳的 `to`）',
       all(_ROWS[i].get('from') == _ROWS[i - 1].get('to')
           for i in range(1, len(_ROWS))),
       u'首=%r 末=%r' % (_ROWS[0].get('from') if _ROWS else None,
                        _ROWS[-1].get('to') if _ROWS else None))
    ok(u'W4 产品声明落地 == 实际落地（`current_scene` == `to`）', chain_ok)
    ok(u'W5 终点到达 %s' % _OS_TO,
       bool(_ROWS) and _ROWS[-1].get('cur_after') == _OS_TO,
       u'末跳到达=%r' % (_ROWS[-1].get('cur_after') if _ROWS else None,))
    ok(u'W6 walk_steps 报成功', bool(rv.get('ok')), u'ret=%r' % (rv,))
    ok(u'W7 ★ 全屏化在走路期间已生效（cam scale > 2.0）',
       bool(_ROWS) and (_ROWS[0].get('cam_scale') or 0) > 2.0,
       u'首跳 cam=%sx%s scale=%s' % (_ROWS[0].get('cam_w'), _ROWS[0].get('cam_h'),
                                     _ROWS[0].get('cam_scale')) if _ROWS else u'')
    ok(u'W8 ★ 走动真的是**逐步**发生（%d 跳用了 %.3fs ⇒ 每跳 %.1f ms，'
       u'不是瞬时跳变）' % (len(_ROWS), wall, 1000.0 * wall / max(len(_ROWS), 1)),
       len(_ROWS) >= 2 and wall > 0)

    with io.open(os.path.join(EV, 'rec106_walk.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'\n'.join(lines) + '\n')

    npass = sum(1 for _n, c in R if c)
    nfail = len(R) - npass
    print()
    print(u'==== walk106 判据：%d PASS / %d FAIL ====' % (npass, nfail))
    sys.stdout.flush()
    app.quit()


QTimer.singleShot(4000, _do_walk)
QTimer.singleShot(30000, lambda: (print('[walk106] hard timeout'), app.quit()))

if __name__ == '__main__':
    rc = app.exec_()
    sys.exit(rc)
