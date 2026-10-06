# -*- coding: utf-8 -*-
import os, sys, time
PKG = 'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本\\ralsei_pet'
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)
os.environ.pop('QT_QPA_PLATFORM', None)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
app = QApplication.instance() or QApplication([])
from main import RalseiPet
pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')

TARGETS = ['ch1.castle_town.castle_town', 'desktop']
STEP_MS = 7000
_idx = [0]


def step():
    if _idx[0] >= len(TARGETS):
        print('[DRV] done', flush=True)
        return                      # 不 quit：保持窗口在屏上给父进程抓
    t = TARGETS[_idx[0]]
    _idx[0] += 1
    try:
        r = pet.travel_to_scene(t)
        ok = r.get('ok') if isinstance(r, dict) else r
        sid = r.get('scene_id') if isinstance(r, dict) else None
        print('[DRV] travel_to_scene(' + repr(t) + ') ok=' + repr(ok)
              + ' sid=' + repr(sid)
              + ' now=' + repr(pet.__dict__.get('current_scene')), flush=True)
    except Exception as e:
        print('[DRV] EXC ' + repr(e), flush=True)
    QTimer.singleShot(STEP_MS, step)


def report():
    try:
        print('[DRV] scene=' + repr(pet.__dict__.get('current_scene'))
              + ' canvas_visible=' + repr(pet.scene_canvas.isVisible())
              + ' canvas_iswin=' + repr(pet.scene_canvas.isWindow())
              + ' canvas_geo=' + repr((pet.scene_canvas.x(), pet.scene_canvas.y(),
                                       pet.scene_canvas.width(), pet.scene_canvas.height()))
              + ' plan_n=' + repr(len(pet.scene_canvas.plan())), flush=True)
    except Exception as e:
        print('[DRV] report EXC ' + repr(e), flush=True)


QTimer.singleShot(12000, step)
for _i in range(len(TARGETS) + 1):
    QTimer.singleShot(12000 + STEP_MS * _i + 2500, report)
app.exec_()
