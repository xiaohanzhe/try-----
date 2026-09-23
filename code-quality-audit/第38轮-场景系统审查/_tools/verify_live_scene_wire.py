# -*- coding: utf-8 -*-
"""第三十八轮：真机验证 —— **P0 接线真的生效了吗？**

为什么要这一步（本项目最贵的坑是「函数写对了但产品用不上」，踩过 4 次）：
G2 的 `scene_p0` 只能证明"源码里有 `self.scene.load()` 这个调用"，
**不能**证明"产品启动时它真的跑通了、状态真的被填了"。
所以必须在**产品进程内**（`main.RalseiPet()` 起来之后）读宿主的内部状态。

判据（全部要 PASS）：
  L1  _scene_loaded is True            ← 接线前实测恒为 False
  L2  current_scene == 'desktop'       ← 用户口径「桌面当默认场景」
  L3  索引 ok 且场景数 = 产品索引真实条数（不写死具体数字）
  L4  _scene_anchors 非空
  L5  _routes_loaded is True 且路由表 ok
  L6  self.scene.ready is True（经**转发壳**读到，不是直接摸宿主）
  L7  经 switch() 切到"住在区域分片里"的场景能成功（证明 entry 真的传下去了）
  L8  scene_objects == []（P0 零消费者 ⇒ 画面上不该有任何物件）
  L9  负控制：**没有调用 load() 的控制器**必须 `_scene_loaded` 仍为 False
      （证明 L1 的 True 来自接线，而不是 SceneController 构造自带）

不联网、不调 Ollama、用 offscreen 平台（不需要显示器）。
"""
import io
import os
import sys
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
os.chdir(SRC)
for _p in (SRC, MODS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(
    tempfile.mkdtemp(prefix='ralsei_v38_'), 'RalseiMemory')

out = []
RES = []


def w(s):
    out.append(str(s))
    print(s)


def ok(name, cond, detail=''):
    RES.append((bool(cond), name))
    w(('[PASS] ' if cond else '[FAIL] ') + name
      + ('' if cond else '   <<< ' + str(detail)))


from PyQt5.QtWidgets import QApplication  # noqa: E402
app = QApplication(sys.argv)

import main as M  # noqa: E402

w('=== 第三十八轮 真机验证：P0 接线 ===')
pet = M.RalseiPet()
w('装置已就绪: RalseiPet 构造成功（说明接线没有拖垮启动）')
w('')

sc = pet.scene

# ---- L1/L2/L3/L4：宿主状态字段真的被填了 ----
_loaded = pet.__dict__.get('_scene_loaded')
_cur = pet.__dict__.get('current_scene')
_idx = pet.__dict__.get('_scene_index') or {}
_n_scenes = len(_idx.get('scenes') or {})
_anchors = pet.__dict__.get('_scene_anchors') or {}

ok('L1 main.py 的 P0 接线让 _scene_loaded 变成 True（接线前恒为 False）',
   _loaded is True, '_scene_loaded=%r' % _loaded)

ok("L2 启动即落在默认场景 'desktop'（用户口径：桌面当默认场景）",
   _cur == 'desktop', 'current_scene=%r' % _cur)

ok('L3 索引可用且登记了场景（ok=True，场景数>0）',
   bool(_idx.get('ok')) and _n_scenes > 0,
   'ok=%r n=%d error=%r' % (_idx.get('ok'), _n_scenes, _idx.get('error')))
w('      （实测场景数 = %d，此处不写死具体数字，随素材增减）' % _n_scenes)

ok('L4 锚点表已加载（_scene_anchors 非空）',
   len(_anchors) > 0, 'anchors=%d' % len(_anchors))

# ---- L5：路由表 ----
_routes = pet.__dict__.get('_scene_routes') or {}
ok('L5 P0 接线也加载了路由表（_routes_loaded=True 且 ok）',
   pet.__dict__.get('_routes_loaded') is True and bool(_routes.get('ok')),
   '_routes_loaded=%r ok=%r' % (pet.__dict__.get('_routes_loaded'),
                                _routes.get('ok')))

# ---- L6：经**转发壳**读（不是直接摸宿主） ----
ok('L6 经转发壳 self.scene.ready 读到 True（壳本身没挡住）',
   sc.ready is True, 'ready=%r' % sc.ready)

# ---- L7：切到"住在区域分片里"的场景 ----
#     分片场景必须靠 `switch()` 把登记行（含 chapter_id/area_id）传给数据层才读得到。
_zone_target = 'ch1.castle_town.castle_darkdoor'
_entry = (pet.__dict__.get('_scene_index') or {}).get('scenes', {}).get(_zone_target)
_sw = sc.switch(_zone_target)
_st = pet.__dict__.get('_scene_state')
ok('L7 能切到"区域分片里"的场景（证明 switch 把 entry 传给了数据层）',
   _sw is True and _st is not None
   and getattr(_st, 'scene_id', None) == _zone_target,
   'sw=%r state=%r entry=%r' % (_sw, _st, _entry))
w('      分片登记行: chapter=%r area=%r file=%r'
  % ((_entry or {}).get('chapter_id'), (_entry or {}).get('area_id'),
     (_entry or {}).get('file')))
w('      切后描述 = %r' % sc.description())

# ---- L7b：切回桌面（桌面必须在索引里、且切得回去） ----
ok('L7b 切回 desktop 成功（桌面与作品内场景同级同构）',
   sc.switch('desktop') is True
   and pet.__dict__.get('current_scene') == 'desktop',
   'current=%r' % pet.__dict__.get('current_scene'))

# ---- L8：零消费者 ⇒ 不该有物件 ----
ok('L8 scene_objects 为空列表（P0 无渲染层消费者 ⇒ 画面上零变化）',
   pet.__dict__.get('scene_objects') == [],
   'scene_objects=%r' % (pet.__dict__.get('scene_objects'),))

# ---- 路由判定（走产品路径） ----
_route = sc.pick_route({'mood': 'sleepy'})
w('')
w('pick_route(mood=sleepy) -> %r' % ((_route or {}).get('to')))
w('route_reason = %r' % sc.route_reason())
w('destinations_text 行数 = %d'
  % len([x for x in (sc.destinations_text() or '').splitlines() if x]))

# ---- L9：负控制 —— 没接线的控制器不许自己变 True ----
#     用桩宿主手搓一个 SceneController，**不调 load()**：必须仍是 False。
#     这条是 L1 的"反面"：若 L9 也 True，说明 True 不是接线带来的，L1 就没意义了。
import scene_controller as _C  # noqa: E402


class _StubHost(object):
    _CONTROLLER_ATTRS = ('scene',)

    def __init__(self):
        self._scene_index = None
        self._scene_state = None
        self.current_scene = None
        self.scene_objects = []
        self._scene_anchors = {}
        self._scene_loaded = False
        self._scene_routes = None
        self._routes_loaded = False
        self._scene_route_reason = ''
        self.scene = _C.SceneController(self)


_stub = _StubHost()
ok('L9 负控制：**未调用 load()** 的控制器 _scene_loaded 仍是 False'
   '（证明 L1 的 True 来自接线而非构造自带）',
   _stub.__dict__.get('_scene_loaded') is False and _stub.scene.ready is False,
   '_scene_loaded=%r ready=%r' % (_stub.__dict__.get('_scene_loaded'),
                                  _stub.scene.ready))

# ---- 收尾 ----
w('')
pet.close()
w('close() 完成，无异常')

n_fail = sum(1 for c, _ in RES if not c)
w('')
w('=' * 60)
w('总计 %d 项，通过 %d，失败 %d' % (len(RES), len(RES) - n_fail, n_fail))
for c, n in RES:
    if not c:
        w('  FAIL: %s' % n)

path = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查',
                    '_evidence', '真机_P0接线验证.txt')
os.makedirs(os.path.dirname(path), exist_ok=True)
with io.open(path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('\nwritten:', path)
sys.exit(1 if n_fail else 0)
