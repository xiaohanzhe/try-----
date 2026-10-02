# -*- coding: utf-8 -*-
"""第76轮 R4 回归锁：视角跟随锚点 = 灵魂（用户口径）。

锁什么：
  A 结构：`_camera_target_rect` 存在 · `camera_follow` 真的改用它 ·
          `_screen_point_to_room_rect` 是**唯一**公式真源（两处都调它）；
  B ★★ 等价性：`_pet_target_rect` 与灵魂锚点**同口径** —— 用同一屏幕点喂两者，
          结果必须逐值相等（否则"换锚点就量级错"）。这是 R4 最关键的判据。
  C 行为（离线桩）：灵魂可见 ⇒ 锚点跟灵魂中心；灵魂不可见 ⇒ 退回宠物。

判据纪律：`print('[PASS] %s')` 字面量；负控制成对；断行为不断赋值。
"""
import io
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

_passed = 0
_failed = 0


def check(desc, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print('[PASS] %s' % desc)
    else:
        _failed += 1
        print('[FAIL] %s' % desc)


def _read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


_src = _read(MAIN)
_tree = None
import ast  # noqa: E402
_tree = ast.parse(_src)

# =============================================================== A. 结构
check('A 存在 _camera_target_rect 定义',
      re.search(r'def _camera_target_rect\(', _src) is not None)
check('A 存在 _screen_point_to_room_rect 定义',
      re.search(r'def _screen_point_to_room_rect\(', _src) is not None)

# camera_follow 的实参必须是 _camera_target_rect（不是 _pet_target_rect）
_cf = re.findall(r'camera_follow\([^)]*\)', _src)
check('A camera_follow 恰 1 处（实得 %d）' % len(_cf), len(_cf) == 1)
check('A camera_follow 的锚点 = _camera_target_rect',
      bool(_cf) and '_camera_target_rect(' in _cf[0])
check('A camera_follow 不再直接用 _pet_target_rect',
      bool(_cf) and '_pet_target_rect(' not in _cf[0])

# ★ 单一真源：两条路径都必须调 _screen_point_to_room_rect
_body_pet = _extract_func = None


def _func_src(name):
    for node in ast.walk(_tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(_src, node)
    return None


_s_pet = _func_src('_pet_target_rect')
_s_cam = _func_src('_camera_target_rect')
_s_conv = _func_src('_screen_point_to_room_rect')

check('A _pet_target_rect 真调用 _screen_point_to_room_rect（单一真源）',
      bool(_s_pet) and '_screen_point_to_room_rect(' in _s_pet)
check('A _camera_target_rect 真调用 _screen_point_to_room_rect（单一真源）',
      bool(_s_cam) and '_screen_point_to_room_rect(' in _s_cam)
# ★ 负控制：公式本体不应在 _pet_target_rect 里再写一份
check('A 负控制：_pet_target_rect 里不再有自己那份 roi 归一化（无 kx = rw）',
      bool(_s_pet) and 'kx = rw' not in _s_pet)
check('A 公式本体只在 _screen_point_to_room_rect 里（kx = rw 恰 1 处）',
      _src.count('kx = rw') == 1)

# _camera_target_rect 必须优先灵魂
check('A _camera_target_rect 先判 _soul_visible()',
      bool(_s_cam) and '_soul_visible()' in _s_cam)
check('A _camera_target_rect 取灵魂中心 soul.state.center()',
      bool(_s_cam) and 'soul.state.center()' in _s_cam)
check('A _camera_target_rect 有退回 _pet_target_rect（灵魂不可用）',
      bool(_s_cam) and 'self._pet_target_rect(' in _s_cam)
# ★ 顺序：灵魂分支必须在退回之前
_i_soul = _s_cam.find('_soul_visible()') if _s_cam else -1
_i_back = _s_cam.find('return self._pet_target_rect(') if _s_cam else -1
check('A 顺序：灵魂判定在退回之前（soul=%d back=%d）' % (_i_soul, _i_back),
      _i_soul >= 0 and _i_back >= 0 and _i_soul < _i_back)

# ★★★ 第76轮真机抓到的真 bug：`soul.state.size` 是 property，不是方法。
#   产品里写成 `size()` 会抛 TypeError，而整个方法在 try 里 ⇒ 静默退回宠物 ⇒
#   "套件全绿但 R4 从未生效"。这条判据直接盯住那个写法。
check('A ★★ 产品不许写 soul.state.size()（size 是 property，不是方法）',
      'state.size()' not in _src)
check('A ★★ 产品写的是 soul.state.size（裸属性，无括号）',
      'soul.state.size' in _src and 'soul.state.size()' not in _src)

# ★ 真源码对照：从 `soul_entity.py` 读 `SoulState`，证明 `size` 真是 property、
#   `center` 真是方法 —— 否则上面两条判据就是"自说自话"。
_SOUL_ENTITY = os.path.join(ROOT, 'ralsei_pet', 'modules', 'soul_entity.py')
try:
    _se = _read(_SOUL_ENTITY)
    _se_tree = ast.parse(_se)
    _size_is_prop = False
    _center_is_func = False
    for node in ast.walk(_se_tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SoulState':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    if sub.name == 'center':
                        _center_is_func = True
                    if sub.name == 'size':
                        _size_is_prop = any(
                            isinstance(d, ast.Name) and d.id == 'property'
                            for d in sub.decorator_list)
    check('A ★★ 真源码：SoulState.size 是 property（证明上面判据非自说自话）',
          _size_is_prop)
    check('A ★★ 真源码：SoulState.center 是方法', _center_is_func)
except Exception as _e:
    check('A 读 soul_entity.py 失败: %r' % (_e,), False)

# =============================================================== B. 等价性（真跑）
# 造一个最小宿主：只装两个方法依赖的字段
import types as _t


class _FakeSoulState(object):
    """★★ 模拟 `soul_entity.SoulState` 的**真实**接口。

    ⚠️ `size` 是 **property**（返回元组），`center()` 才是方法 ——
    第76轮第一版把 `size` 造成了方法，于是产品里写成 `soul.state.size()`
    这个真 bug 被夹具"配合"着放过了（离线套件假绿，真机一跑才暴露）。
    夹具的职责是**复刻真实接口**，不是"能跑就行"。
    """

    def __init__(self, x, y, w, h):
        self._c = ((x + w / 2.0), (y + h / 2.0))
        self._s = (w, h)

    def center(self):
        return self._c

    @property
    def size(self):
        return self._s


class _FakeSoul(object):
    def __init__(self, cx, cy, w=48, h=48):
        self.state = _FakeSoulState(cx - w / 2.0, cy - h / 2.0, w, h)

    def isVisible(self):
        return True


# 把源码里那两个方法挂到桩对象上（真跑真源码，不重写）
_ns = {}
# 抽取三个方法源码，合成一个可 exec 的最小类体
_methods = []
for _n in ('_screen_point_to_room_rect', '_pet_target_rect',
           '_camera_target_rect', '_virtual_screen_size', '_soul_visible'):
    _fs = _func_src(_n)
    if _fs:
        # 去一层缩进，变成类体同级方法
        _methods.append('\n'.join(l[4:] if l.startswith('    ') else l
                                  for l in _fs.splitlines()))
_klass = 'class _Stub:\n' + '\n'.join(
    '\n'.join('    ' + l for l in m.splitlines()) for m in _methods)
_klass += '\n    pass\n'
exec(compile(_klass, '<stub>', 'exec'), _ns)
_Stub = _ns['_Stub']

stub = _Stub()
stub._virtual_screen_rect = lambda: (0, 0, 1920, 1080)
stub._virtual_screen_size = types.MethodType(lambda self: (1920.0, 1080.0), stub)
stub.pos = lambda: types.SimpleNamespace(x=lambda: 100.0, y=lambda: 200.0)
stub.width = lambda: 120.0
stub.height = lambda: 80.0
stub.soul = None

# 宠物中心 = (100+120/2, 200+80/2) = (160, 240)；让灵魂中心同为 (160,240)
room = (0.0, 0.0, 640.0, 480.0)

_r_pet = stub._pet_target_rect(room)
stub.soul = _FakeSoul(160.0, 240.0)
stub._soul_visible = types.MethodType(lambda self: True, stub)
_r_cam_soul = stub._camera_target_rect(room)

check('B ★★ 等价性：同一屏幕点 ⇒ 宠物锚点 == 灵魂锚点（逐值）',
      _r_pet is not None and len(_r_cam_soul) == 4
      and all(abs(a - b) < 1e-6 for a, b in zip(_r_pet, _r_cam_soul)))
print('#   宠物锚点=%r' % (_r_pet,))
print('#   灵魂锚点=%r' % (_r_cam_soul,))

# 负控制：灵魂移到别处 ⇒ 锚点必须跟着变（证明真的在读灵魂）
stub.soul = _FakeSoul(1600.0, 900.0)
_r_cam_far = stub._camera_target_rect(room)
check('B 负控制：灵魂移到 (1600,900) ⇒ 锚点必须随之改变（A ≠ B）',
      any(abs(a - b) > 1e-6 for a, b in zip(_r_cam_soul, _r_cam_far)))
print('#   灵魂远端锚点=%r' % (_r_cam_far,))

# =============================================================== C. 行为（退回）
stub._soul_visible = types.MethodType(lambda self: False, stub)
_r_back = stub._camera_target_rect(room)
check('C 行为：灵魂不可见 ⇒ 退回宠物锚点（== _pet_target_rect）',
      _r_back is not None and all(abs(a - b) < 1e-6 for a, b in zip(_r_pet, _r_back)))

# 负控制：房间未知也不抛
_r_noroom = stub._camera_target_rect(None)
check('C 负控制：room_rect=None 不抛且有 4 元组', _r_noroom is None or len(_r_noroom) == 4)

# 判据 no-op 显式打印
print('#   [no-op] "_camera_target_rect(" in main => %s'
      % ('_camera_target_rect(' in _src))
print('#   [no-op] camera_follow 用的是 _camera_target_rect => %s'
      % (bool(_cf) and '_camera_target_rect(' in _cf[0]))

print('=== 第76轮 R4 回归：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(1 if _failed else 0)
