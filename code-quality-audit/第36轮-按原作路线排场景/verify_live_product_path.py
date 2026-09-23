# -*- coding: utf-8 -*-
"""第三十六轮：真机验证 —— 产品进程内走真实路径加载新场景数据。

为什么要这一步（本项目最贵的坑是「函数写对了但产品用不上」）：
上面的回归锁是在**独立进程**里 import 模块 + 显式传 SCENE_DIR 跑通的。
那只能证明"模块能读我给的目录"，**不能**证明"产品启动时真的会用这套数据"。
所以这一步必须在**产品进程内**（main.RalseiPet() 起来之后）读宿主的
内部状态字段，看 current_scene / _scene_index / scene_objects 是不是真的被填了。

不联网、不调 Ollama、不开窗口可见（用 offscreen 平台跑，不需要显示器）。
"""
import io
import json
import os
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
os.chdir(SRC)
sys.path.insert(0, SRC)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# 隔离真实存储（照 G2 的口径，别污染用户 E 盘）
import tempfile
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(
    tempfile.mkdtemp(prefix='ralsei_v36_'), 'RalseiMemory')

out = []
def w(s):
    out.append(str(s))
    print(s)

from PyQt5.QtWidgets import QApplication  # noqa: E402
app = QApplication(sys.argv)

import main as M  # noqa: E402

w('=== 产品进程内验证场景系统 ===')
pet = M.RalseiPet()

w('装置已就绪: RalseiPet 构造成功')

# --- 1. 场景系统是否真的加载了 ---
idx = pet.__dict__.get('_scene_index')
w('')
w('--- 1. 宿主状态字段 ---')
w('_scene_loaded = %r' % pet.__dict__.get('_scene_loaded'))
w('_scene_index is None = %r' % (idx is None))
if isinstance(idx, dict):
    w('  索引 ok = %r' % idx.get('ok'))
    w('  索引场景数 = %d' % len(idx.get('scenes') or {}))
    w('  索引 error = %r' % idx.get('error'))
w('current_scene = %r' % pet.__dict__.get('current_scene'))
w('_scene_state = %r' % pet.__dict__.get('_scene_state'))
w('scene_objects = %r' % pet.__dict__.get('scene_objects'))
w('_scene_anchors keys = %d' % len(pet.__dict__.get('_scene_anchors') or {}))

# --- 2. 经控制器（转发壳）读 ---
w('')
w('--- 2. 经转发壳 self.scene 访问 ---')
sc = pet.scene
w('self.scene.ready = %r' % sc.ready)
w('self.scene.available_scenes() 条数 = %d' % len(sc.available_scenes()))
w('self.scene.description() = %r' % sc.description())
w('self.scene.destinations_text() 行数 = %r'
  % len([x for x in (sc.destinations_text() or '').splitlines() if x]))

# --- 3. 真的切一个原作场景 ---
w('')
w('--- 3. 切到原作场景（走产品 switch）---')
target = 'ch1.field.field_great_door'
ok = sc.switch(target)
w('switch(%r) = %r' % (target, ok))
w('切后 current_scene = %r' % pet.__dict__.get('current_scene'))
st = pet.__dict__.get('_scene_state')
w('切后 _scene_state = %r' % st)
w('切后 describe() = %r' % sc.description())
w('切后 bg = %r' % (getattr(st, 'bg', None),))
w('切后 bgm = %r' % (getattr(st, 'bgm', None),))

# --- 4. 往返切换 ---
w('')
w('--- 4. 往返切换 ---')
for t in ['ch2.cyber_city.cyber_city_entrance', 'desktop',
          'ch5.garden.garden_beginning', 'desktop']:
    r = sc.switch(t)
    w('  switch(%-45s) = %r  current=%r' % (t, r, pet.__dict__.get('current_scene')))

# --- 5. 路由（走产品路径）---
w('')
w('--- 5. 产品路由判定 ---')
sc.load_routes()
w('pick_route(mood=sleepy) = %r'
  % (sc.pick_route({'mood': 'sleepy'}) or {}).get('to'))
w('route_reason = %r' % sc.route_reason())

# --- 6. 关窗退出 ---
w('')
w('--- 6. 收尾 ---')
pet.close()
w('close() 完成，无异常')

path = os.path.join(ROOT, 'code-quality-audit', '第36轮-按原作路线排场景',
                    '_evidence', '真机产品路径验证.txt')
os.makedirs(os.path.dirname(path), exist_ok=True)
with io.open(path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('\nwritten:', path)
