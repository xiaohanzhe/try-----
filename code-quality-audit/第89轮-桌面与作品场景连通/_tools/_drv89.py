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

TARGETS = ['ch1.castle_town.castle_town', 'uty.rooms.rm_intro', 'oneshot.barrens.Blue', 'desktop']
STEP_MS = 9000
_idx = [0]


def step():
    if _idx[0] >= len(TARGETS):
        print('[DRV] done', flush=True)
        app.quit()
        return
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


QTimer.singleShot(4000, step)
QTimer.singleShot(4000 + STEP_MS * (len(TARGETS) + 1), app.quit)
app.exec_()
