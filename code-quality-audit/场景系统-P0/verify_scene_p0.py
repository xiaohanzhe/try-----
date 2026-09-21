# -*- coding: utf-8 -*-
"""场景系统 P0 骨架验证 —— 接口在位 + 纯函数正确 + **零行为变化**。

背景
----
用户原话：「我后期会给他添加场景系统，也就是把原作的世界搬到桌面上，你要留好
拓展接口哦（桌面也会被我当成一个场景，你自己看一下原作的场景切换这类的，为
后期添加做准备）」。

拆成两条硬要求：
  1. **留好拓展接口** —— 接口必须真的落到代码里（能被 import、能被调、能过
     回归），而不是只写在文档里。「函数写对了但产品用不上」是本项目最贵的坑
     （踩过 4 次），反过来「接口写好了但没人调用」同样不算交付。
  2. **桌面是一等场景** —— 它必须与作品内场景**同级同构**，不许开任何后门。
     本项目物理层早已把桌面当一等公民（`floor_manager.desktop_floor`），
     场景层必须对齐这一点。

为什么 P0 的验收标准是"零行为变化"
----------------------------------
P0 只做骨架，**不接渲染层**。所以唯一能证明"骨架没搞坏东西"的判据就是：
**不切场景时，整个 G2 的 24 套件输出逐字节不动**（1169 PASS）。
本套件是这条判据的补充 —— 它守住"骨架自身的内在正确性"（纯函数算得对、
转发壳不成环、状态不劈裂），而 G2 守住"骨架没干扰既有行为"。

分组
----
  A 模块存在与零依赖纪律（禁 Qt / 禁项目内 import —— 初始化环）
  B 数据文件契约（_index / _anchors / desktop 三份 JSON 的 schema 与内容）
  C 纯函数：resolve_anchor（含 pos 优先 / 锚点命中 / 兜底 / 非法输入负控制）
  D 纯函数：pick_variant（单帧 / variants / frames 别名 / 空→None）
  E 纯函数：depth_of（显式 depth / y 推导 / 兜底）
  F 纯函数：visible_objects（过滤 + 排序 + 不改原 dict）
  G SceneState（from_dict 容错 / describe 唯一入口）
  H 控制器双向转发（不成环 / 状态不劈裂 / 缺失名抛 AttributeError）
  J main.py 三处接线（import / _CONTROLLER_ATTRS / 预声明 / 实例化）
  K 桌面场景与作品内场景**同级同构**（不许开后门）

本套件**不联网、不实例化 App、不需要显示器**（纯数据 + 桩宿主）。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import json
import os
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODS = os.path.join(PET, 'modules')
for _p in (PET, SRC, MODS):
    if _p not in sys.path:
        sys.path.append(_p)

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


# ---------------------------------------------------------------- 源码工具
MAIN_PY = os.path.join(SRC, 'main.py')
SCENE_SYS_PY = os.path.join(MODS, 'scene_system.py')
SCENE_CTL_PY = os.path.join(MODS, 'scene_controller.py')
SCENES_DIR = os.path.join(PET, 'assets', 'scenes')


def _read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


MAIN_TEXT = _read(MAIN_PY)
SCENE_SYS_TEXT = _read(SCENE_SYS_PY)
SCENE_CTL_TEXT = _read(SCENE_CTL_PY)

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def code_only_src(src):
    """剥掉注释/字符串后的 token 串联（空白抹平）。

    铁律：`"字面量" in 源码` 会被注释/文档串误命中，所以源码级断言一律走这里；
    且 tokenize **不产空白 token**，拼回必须用 ' '.join。
    """
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in _DROP:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


CODE_MAIN = code_only_src(MAIN_TEXT)
CODE_SCENE_SYS = code_only_src(SCENE_SYS_TEXT)
CODE_SCENE_CTL = code_only_src(SCENE_CTL_TEXT)

import scene_system as S          # noqa: E402
import scene_controller as C      # noqa: E402

# ===========================================================================
#  A  模块存在与零依赖纪律
# ===========================================================================
section('A 模块存在与零依赖纪律')


def _imports_of(src):
    """列出源码里 import 到的顶层模块名（AST 口径，避免正则漏判/误判）。"""
    import ast
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.name or '').split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:      # 相对导入：不以模块名形式出现，单独标记
                names.add('.' * node.level)
            elif node.module:
                names.add(node.module.split('.')[0])
    return names


SCENE_SYS_IMPORTS = _imports_of(SCENE_SYS_TEXT)
SCENE_CTL_IMPORTS = _imports_of(SCENE_CTL_TEXT)

ok('A1 scene_system.py 存在且可 import（拿到 SCENE_SCHEMA_VERSION）',
   hasattr(S, 'SCENE_SCHEMA_VERSION') and isinstance(S.SCENE_SCHEMA_VERSION, int),
   'SCENE_SCHEMA_VERSION=%r' % getattr(S, 'SCENE_SCHEMA_VERSION', None))

ok('A2 scene_controller.py 存在且可 import（拿到 SceneController）',
   hasattr(C, 'SceneController'),
   'SceneController=%r' % getattr(C, 'SceneController', None))

# 初始化环：scene_system 会被 scene_controller import，而后者在 main.py 的
# import 期就被 import → 本模块若回头 import 项目内模块 / Qt，环就接上了。
_PROJECT_INTERNAL = {
    'logger_utils', 'data_store', 'memory_store', 'lazy_log', 'sprite_loader',
    'dialogue_ui', 'dialogue_system', 'emotion_system', 'config_manager',
    'floor_manager', 'ai_driver', 'event_speech', 'relationship',
    'search_summarizer', 'autonomous_agent', 'sound_manager', 'pet_ai',
    'desktop_interaction', 'command_manager', 'api_client', 'modules', 'main',
    'customization_system', 'apps_controller',
}
_QT_MODULES = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6'}

ok('A3 scene_system.py 不 import 任何 Qt 模块',
   not (SCENE_SYS_IMPORTS & _QT_MODULES),
   'imports=%s' % sorted(SCENE_SYS_IMPORTS))

ok('A4 scene_system.py 不 import 任何项目内模块（初始化环纪律）',
   not (SCENE_SYS_IMPORTS & _PROJECT_INTERNAL),
   '越界=%s' % sorted(SCENE_SYS_IMPORTS & _PROJECT_INTERNAL))

# 负控制：上面的判据必须真能抓人 —— 拿一份「故意 import Qt」的合成源码试一次。
_FAKE_BAD = 'import sys\nfrom PyQt5.QtCore import QTimer\nfrom logger_utils import get_logger\n'
_FAKE_BAD_IMPORTS = _imports_of(_FAKE_BAD)
ok('A5 负控制：A3/A4 的判据真能抓到越界 import（合成样本）',
   bool(_FAKE_BAD_IMPORTS & _QT_MODULES)
   and bool(_FAKE_BAD_IMPORTS & _PROJECT_INTERNAL),
   '合成样本检出 qt=%s internal=%s' % (
       sorted(_FAKE_BAD_IMPORTS & _QT_MODULES),
       sorted(_FAKE_BAD_IMPORTS & _PROJECT_INTERNAL)))

# scene_controller 只许 import 标准库 + 零依赖的姊妹数据层模块
#
# 白名单里为什么有两个 data 层模块（第 29 轮扩的）：
#   · `scene_system`  —— 场景数据 + 几何纯函数；
#   · `scene_routing` —— 路由数据 + 匹配纯函数（第 29 轮新增）。
# 两者是**平级的零依赖模块**（各自都禁 Qt / 禁项目内业务模块，有 A2/A3 与
# 路由套件的 A2/A3 双份断言守着）。控制器 import 它们不会接上初始化环 ——
# 环的风险来自"回头 import 有反向依赖的业务模块"（logger_utils / data_store…），
# 而不是来自这两个纯数据模块。
# ⚠️ 本白名单是**显式**的：新增一条必须在这里加一行。这个"麻烦"是刻意的 ——
#    它逼每次放宽都成为一次有意识的决定（本轮就是被这条断言逮到的）。
_CTL_ALLOWED = {'logging', 'scene_system', 'scene_routing'}
_CTL_OVER = ((SCENE_CTL_IMPORTS & _QT_MODULES)
             | (SCENE_CTL_IMPORTS & (_PROJECT_INTERNAL - {'scene_system'}))
             | (SCENE_CTL_IMPORTS - _CTL_ALLOWED))
ok('A6 scene_controller.py 只 import 标准库 + 零依赖数据层（不 import Qt / 业务模块）',
   not _CTL_OVER,
   'imports=%s（越界=%s）' % (sorted(SCENE_CTL_IMPORTS), sorted(_CTL_OVER)))

# 负控制：A6 的白名单不许宽到"什么都放得过"
_FAKE_CTL_BAD = 'import logging\nimport json\nfrom data_store import x\n'
_FCB = _imports_of(_FAKE_CTL_BAD)
ok('A6b 负控制：A6 的判据真能抓到"业务模块 + 未列入白名单的标准库"',
   bool(_FCB & _PROJECT_INTERNAL)
   and bool(_FCB - _CTL_ALLOWED),
   '越界=%s' % sorted((_FCB & _PROJECT_INTERNAL) | (_FCB - _CTL_ALLOWED)))

# 源码级：module 里不许出现 QTimer/QWidget 这类名字（防"忘了 import 但抄了代码"）
ok('A7 scene_system.py 源码里不出现 Qt 类名（防漏 import 的抄写残留）',
   all(k not in CODE_SCENE_SYS for k in
       ('QTimer', 'QWidget', 'QPixmap', 'QPainter', 'QMainWindow')),
   '源码里命中 Qt 名')

# ===========================================================================
#  B  数据文件契约
# ===========================================================================
section('B 数据文件契约')

for _f in ('_index.json', '_anchors.json', 'desktop.json'):
    _p = os.path.join(SCENES_DIR, _f)
    ok('B1.%s 存在且是合法 UTF-8 JSON' % _f,
       os.path.isfile(_p) and isinstance(
           json.load(io.open(_p, encoding='utf-8')), dict),
       'path=%s exists=%s' % (_p, os.path.isfile(_p)))

_IDX = S.load_index()
ok('B2 _index.json 能被 load_index 解析（ok=True，schema 版本匹配）',
   _IDX.get('ok') is True and _IDX.get('schema_version') == S.SCENE_SCHEMA_VERSION,
   'ok=%r err=%r ver=%r' % (_IDX.get('ok'), _IDX.get('error'),
                            _IDX.get('schema_version')))

ok('B3 索引里登记了 desktop 场景（桌面是一等场景的登记证据）',
   'desktop' in (_IDX.get('scenes') or {}),
   '登记的场景=%s' % sorted((_IDX.get('scenes') or {}).keys()))

ok('B4 索引 default_scene 指向一个真的登记过的场景',
   (_IDX.get('default_scene') or '') in (_IDX.get('scenes') or {}),
   'default_scene=%r' % _IDX.get('default_scene'))

_DESK = S.load_scene('desktop')
ok('B5 desktop.json 能被 load_scene 加载（返回 SceneState 而非 None）',
   _DESK is not None and getattr(_DESK, 'scene_id', None) == 'desktop',
   'scene=%r' % _DESK)

# P0 的关键：桌面上**没有任何可渲染项** → 接上渲染层后画面与现状完全一致。
ok('B6 desktop.json 在 P0 是零可渲染项（bg/bgm/objects 全空 → 零行为变化的前提）',
   _DESK is not None and _DESK.bg is None and _DESK.bgm is None
   and _DESK.objects == [],
   'bg=%r bgm=%r objects=%r' % (
       getattr(_DESK, 'bg', '?'), getattr(_DESK, 'bgm', '?'),
       getattr(_DESK, 'objects', '?')))

_ANCH = S.load_anchors()
ok('B7 _anchors.json 能被 load_anchors 解析（锚点表非空）',
   isinstance(_ANCH, dict) and len(_ANCH) > 0,
   'n=%d' % len(_ANCH) if isinstance(_ANCH, dict) else 'not-dict')

ok('B8 锚点值都是合法的二元比例（0.0~1.0）',
   all(isinstance(v, tuple) and len(v) == 2
       and all(isinstance(x, float) for x in v)
       and all(0.0 <= x <= 1.0 for x in v)
       for v in _ANCH.values()),
   'anchors=%r' % _ANCH)

# 负控制：load_index 对不存在的目录必须回落 ok=False，而不是抛异常。
_MISSING = S.load_index(os.path.join(SCENES_DIR, '__definitely_no_such_dir__'))
ok('B9 负控制：目录不存在时 load_index 回落 ok=False（不抛异常）',
   isinstance(_MISSING, dict) and _MISSING.get('ok') is False
   and _MISSING.get('error'),
   'result=%r' % _MISSING)

_MISSING_SCENE = S.load_scene('__definitely_no_such_scene__')
ok('B10 负控制：场景不存在时 load_scene 返回 None（不抛异常）',
   _MISSING_SCENE is None,
   'result=%r' % _MISSING_SCENE)

# 路径穿越：场景 id 会被拼进路径 → 必须被拦，否则能读仓库外任意 JSON。
ok('B11 负控制：场景 id 含路径穿越（../ 、分隔符）时 load_scene 拒绝',
   S.load_scene('../../config') is None
   and S.load_scene('a/b') is None
   and S.load_scene('..') is None,
   '穿越 id 未被拦')

# ===========================================================================
#  C  纯函数：resolve_anchor
# ===========================================================================
section('C 纯函数：resolve_anchor')

_RECT = (0, 0, 1920, 1080)

ok('C1 pos 优先于 anchor（写了绝对像素就不看锚点）',
   S.resolve_anchor({'pos': [10, 20], 'anchor': 'ground_center'}, _RECT,
                    {'ground_center': (0.5, 1.0)}) == (10, 20),
   'got=%r' % (S.resolve_anchor({'pos': [10, 20], 'anchor': 'ground_center'},
                                _RECT, {'ground_center': (0.5, 1.0)}),))

ok('C2 anchor 命中全局表 → 按屏幕比例换算',
   S.resolve_anchor({'anchor': 'ground_center'}, _RECT,
                    {'ground_center': (0.5, 1.0)}) == (960, 1080),
   'got=%r' % (S.resolve_anchor({'anchor': 'ground_center'}, _RECT,
                                {'ground_center': (0.5, 1.0)}),))

ok('C3 无 pos 且无 anchor（或锚点名不存在）→ 兜底屏幕底部中央',
   S.resolve_anchor({}, _RECT, {}) == (960, 1080)
   and S.resolve_anchor({'anchor': 'no_such_anchor'}, _RECT, {}) == (960, 1080),
   '无参=%r 未知锚=%r' % (S.resolve_anchor({}, _RECT, {}),
                          S.resolve_anchor({'anchor': 'no_such_anchor'}, _RECT, {})))

ok('C4 多屏（虚拟桌面含负坐标）换算正确',
   S.resolve_anchor({'anchor': 'screen_center'}, (-1920, 0, 1920, 1080),
                    {'screen_center': (0.5, 0.5)}) == (0, 540),
   'got=%r' % (S.resolve_anchor({'anchor': 'screen_center'},
                                (-1920, 0, 1920, 1080),
                                {'screen_center': (0.5, 0.5)}),))

# 负控制：算不出来必须返回 None，不许伪装成 (0,0) —— 静默降级是本项目头号敌人。
ok('C5 负控制：screen_rect 非法 → 返回 None（不是 (0,0)）',
   S.resolve_anchor({}, (1, 2, 3), {}) is None
   and S.resolve_anchor({}, None, {}) is None
   and S.resolve_anchor({}, 'nope', {}) is None,
   'got=%r' % (S.resolve_anchor({}, (1, 2, 3), {}),))

# 正/负成对：非 dict 物件也不能炸。
ok('C6 负控制：obj 不是 dict → 不抛异常（返回兜底位或 None）',
   S.resolve_anchor('nope', _RECT, {}) is None
   or S.resolve_anchor('nope', _RECT, {}) == (960, 1080),
   'got=%r' % (S.resolve_anchor('nope', _RECT, {}),))

# ===========================================================================
#  D  纯函数：pick_variant
# ===========================================================================
section('D 纯函数：pick_variant')

ok('D1 单帧（str）原样返回',
   S.pick_variant('a.png') == 'a.png',
   'got=%r' % S.pick_variant('a.png'))

ok('D2 variants 按 tick 轮播（含回绕）',
   [S.pick_variant({'variants': ['a', 'b', 'c']}, t) for t in range(4)]
   == ['a', 'b', 'c', 'a'],
   'got=%r' % [S.pick_variant({'variants': ['a', 'b', 'c']}, t) for t in range(4)])

ok('D3 frames 是 variants 的别名（复用 animations.json 的心智模型）',
   S.pick_variant({'frames': ['x', 'y']}, 1) == 'y',
   'got=%r' % S.pick_variant({'frames': ['x', 'y']}, 1))

ok('D4 传 list 本身等价于 {"variants": [...]}',
   S.pick_variant(['a', 'b'], 1) == 'b',
   'got=%r' % S.pick_variant(['a', 'b'], 1))

ok('D5 负控制：候选为空 / None / 非字符串元素 → 返回 None（不抛）',
   S.pick_variant({'variants': []}) is None
   and S.pick_variant(None) is None
   and S.pick_variant(123) is None
   and S.pick_variant({'variants': [1, 2]}) is None,
   'got=%r %r %r %r' % (
       S.pick_variant({'variants': []}), S.pick_variant(None),
       S.pick_variant(123), S.pick_variant({'variants': [1, 2]})))

ok('D6 坏元素被跳过而不是整体作废（一个坏元素不该让物件消失）',
   # clean = ['a','b']；tick=1 → idx 1%2 = 1 → 'b'
   S.pick_variant({'variants': [None, 'a', 7, 'b']}, 1) == 'b'
   and S.pick_variant({'variants': [None, 'a', 7, 'b']}, 0) == 'a',
   'got=%r %r' % (S.pick_variant({'variants': [None, 'a', 7, 'b']}, 1),
                  S.pick_variant({'variants': [None, 'a', 7, 'b']}, 0)))

ok('D7 tick 为非法值时不抛（按 0 处理）',
   S.pick_variant({'variants': ['a', 'b']}, 'bad') == 'a',
   'got=%r' % S.pick_variant({'variants': ['a', 'b']}, 'bad'))

# ===========================================================================
#  E  纯函数：depth_of
# ===========================================================================
section('E 纯函数：depth_of')

ok('E1 显式 depth 覆盖一切',
   S.depth_of({'depth': 5, 'y': 9999}) == 5,
   'got=%r' % S.depth_of({'depth': 5, 'y': 9999}))

ok('E2 无 depth 时由 y 推导（越小 = 越远 = 键越大）',
   S.depth_of({'y': 0}) > S.depth_of({'y': 500}),
   'y0=%r y500=%r' % (S.depth_of({'y': 0}), S.depth_of({'y': 500})))

ok('E3 都没有 → 基准值（不按列表顺序伪造深度）',
   S.depth_of({}) == S.depth_of({'nope': 1}) == S._DEPTH_BASE,
   'got=%r' % S.depth_of({}))

ok('E4 负控制：depth/y 是垃圾值时不抛，回落基准',
   S.depth_of({'depth': 'x'}) == S._DEPTH_BASE
   and S.depth_of({'y': None}) == S._DEPTH_BASE
   and S.depth_of('nope') == S._DEPTH_BASE,
   'got=%r %r %r' % (S.depth_of({'depth': 'x'}), S.depth_of({'y': None}),
                     S.depth_of('nope')))

# ===========================================================================
#  F  纯函数：visible_objects
# ===========================================================================
section('F 纯函数：visible_objects')


def _mk_scene(objects, scene_id='t', chapter_id='c', area_id='a'):
    st = S.SceneState.from_dict({
        'schema_version': S.SCENE_SCHEMA_VERSION,
        'scene_id': scene_id, 'chapter_id': chapter_id, 'area_id': area_id,
        'objects': objects,
    })
    return st


_OBJS = [
    {'id': 'far', 'kind': 'image', 'pos': [100, 10], 'y': 10},
    {'id': 'near', 'kind': 'image', 'pos': [200, 900], 'y': 900},
    {'id': 'off', 'kind': 'image', 'pos': [300, 500], 'enabled': False},
    {'id': 'alpha0', 'kind': 'image', 'pos': [400, 500], 'alpha': 0.0},
    {'id': 'cond_no', 'kind': 'image', 'pos': [500, 500],
     'cond': {'scene_id': 'other'}},
    {'id': 'cond_yes', 'kind': 'image', 'pos': [600, 500],
     'cond': {'scene_id': 't'}},
]
_VIS = S.visible_objects(_mk_scene(_OBJS), _RECT, {})

ok('F1 过滤掉 enabled=False 的物件',
   'off' not in [o['id'] for o in _VIS],
   'ids=%s' % [o['id'] for o in _VIS])

ok('F2 过滤掉 alpha<=0 的物件',
   'alpha0' not in [o['id'] for o in _VIS],
   'ids=%s' % [o['id'] for o in _VIS])

ok('F3 cond 相等判定生效（不匹配的丢、匹配的留）',
   'cond_no' not in [o['id'] for o in _VIS]
   and 'cond_yes' in [o['id'] for o in _VIS],
   'ids=%s' % [o['id'] for o in _VIS])

ok('F4 结果按 depth_of 升序（先画远的、后画近的）',
   # 逐个算一遍（别口算，这里真踩过）：
   #   near(y=900)     → depth = 1000000-900 = 999100   ← 站得最低 → 最靠前 → 最后画
   #   far(y=10)       → depth = 1000000-10  = 999990
   #   cond_yes(无 y)  → depth = _DEPTH_BASE  = 1000000 ← 无深度信息 → 排最后
   # 升序 = 先画 999100，再 999990，最后 1000000。
   # 「无深度信息排最后」是刻意的：没有 y/depth 的物件（纯逻辑锚点）不该
   # 插到有明确空间关系的物件中间。要它靠前就显式写 depth。
   [o['id'] for o in _VIS] == ['near', 'far', 'cond_yes'],
   'ids=%s' % [o['id'] for o in _VIS])

ok('F5 每个结果都带上了算好的屏幕坐标 _x/_y',
   all('_x' in o and '_y' in o for o in _VIS)
   and [o for o in _VIS if o['id'] == 'near'][0]['_x'] == 200,
   'near=%r' % [o for o in _VIS if o['id'] == 'near'])

ok('F6 纯函数纪律：不改原物件 dict（_x/_y 只出现在返回值里）',
   all('_x' not in o and '_y' not in o for o in _OBJS),
   '原 dict 被污染了')

ok('F7 未知 cond 键一律放行（渐进增强：老场景包不被新条件误杀）',
   [o['id'] for o in S.visible_objects(
       _mk_scene([{'id': 'x', 'pos': [1, 1], 'cond': {'future_key': 'z'}}]),
       _RECT, {})] == ['x'],
   '未知条件键把物件误杀了')

ok('F8 负控制：scene=None / 非列表 objects → 返回空列表（不抛）',
   S.visible_objects(None, _RECT, {}) == []
   and S.visible_objects(S.SceneState.from_dict({'objects': 'nope'}),
                         _RECT, {}) == [],
   'got=%r' % S.visible_objects(None, _RECT, {}))

# 正/负成对：能算出位置的留、算不出的丢。
ok('F9 正/负成对：screen_rect 非法 → 全部物件都算不出位置 → 空结果',
   S.visible_objects(_mk_scene(_OBJS), (1, 2, 3), {}) == [],
   'got=%r' % S.visible_objects(_mk_scene(_OBJS), (1, 2, 3), {}))

# 稳定排序：同深度保持声明顺序。
_SAME = S.visible_objects(_mk_scene([
    {'id': 'p', 'pos': [1, 1]}, {'id': 'q', 'pos': [2, 2]},
    {'id': 'r', 'pos': [3, 3]}]), _RECT, {})
ok('F10 同深度保持声明顺序（稳定排序）',
   [o['id'] for o in _SAME] == ['p', 'q', 'r'],
   'ids=%s' % [o['id'] for o in _SAME])

# ===========================================================================
#  G  SceneState
# ===========================================================================
section('G SceneState')

ok('G1 from_dict 对垃圾输入不抛（返回空 SceneState）',
   S.SceneState.from_dict(None) is not None
   and S.SceneState.from_dict('nope') is not None
   and S.SceneState.from_dict([]).objects == [],
   '垃圾输入炸了')

ok('G2 from_dict 跳过 objects 里的坏元素（非 dict 元素被丢弃）',
   S.SceneState.from_dict({'objects': ['bad', {'id': 'good'}, 7]}).objects
   == [{'id': 'good'}],
   'got=%r' % S.SceneState.from_dict({'objects': ['bad', {'id': 'good'}, 7]}).objects)

ok('G3 from_dict 的 anchors 只保留合法二元数值对',
   S.SceneState.from_dict({'anchors': {
       'ok': [0.5, 0.5], 'bad': [1, 2, 3], 'bad2': 'x'}}).anchors == {'ok': (0.5, 0.5)},
   'got=%r' % S.SceneState.from_dict({'anchors': {
       'ok': [0.5, 0.5], 'bad': [1, 2, 3], 'bad2': 'x'}}).anchors)

ok('G4 describe() 是给 AI 的**唯一入口**：scene_id 为空 → 空串（调用方整段不注入）',
   S.SceneState.from_dict({}).describe() == '',
   'got=%r' % S.SceneState.from_dict({}).describe())

ok('G5 describe() 输出场景的中文描述（章节/区域/场景名）',
   _DESK is not None and _DESK.describe() == '桌面',
   'got=%r' % (getattr(_DESK, 'describe', lambda: None)() if _DESK else None))

# ===========================================================================
#  H  控制器双向转发
# ===========================================================================
section('H 控制器双向转发')


class _StubHost(object):
    """复刻 `RalseiPet` 与 `SceneController` 之间的转发契约（**最小面**）。

    ⚠️ 桩必须跟着真实方法面走（本项目踩过 4 次）—— 这里逐条对齐
    `main.py`：`_CONTROLLER_ATTRS` + 宿主 `__getattr__` 的 MRO 探测写法。
    """
    _CONTROLLER_ATTRS = ('scene',)

    def __init__(self):
        # 复刻 main.py init_systems 里那 6 个预声明字段。
        self._scene_index = None
        self._scene_state = None
        self.current_scene = None
        self.scene_objects = []
        self._scene_anchors = {}
        self._scene_loaded = False
        self.calls = []
        self.scene = C.SceneController(self)

    def __getattr__(self, name):
        for attr in _StubHost._CONTROLLER_ATTRS:
            ctrl = self.__dict__.get(attr)
            if ctrl is None:
                continue
            impl = getattr(type(ctrl), name, None)
            if impl is not None:
                return getattr(ctrl, name)
        raise AttributeError(name)

    def play_animation_once(self, n):
        self.calls.append(n)
        return True


_H = _StubHost()

ok('H1 load() 成功：ready=False → True，current_scene=desktop',
   _H.scene.ready is False and _H.scene.load() is True
   and _H.scene.ready is True and _H.current_scene == 'desktop',
   'ready=%r load=%r current=%r' % (_H.scene.ready, _H.scene.load(),
                                    _H.current_scene))

ok('H2 load() 幂等（重复调用不炸、不改变状态）',
   _H.scene.load() is True and _H.current_scene == 'desktop',
   'current=%r' % _H.current_scene)

ok('H3 available_scenes() 列出索引里的场景',
   _H.scene.available_scenes() == ['desktop'],
   'got=%r' % (_H.scene.available_scenes(),))

ok('H4 switch(不存在的场景) → False，且**保持当前场景不变**（不切空场景）',
   _H.scene.switch('__no_such__') is False and _H.current_scene == 'desktop',
   'ret=%r current=%r' % (_H.scene.switch('__no_such__'), _H.current_scene))

ok('H5 switch(路径穿越 id) → False（与 load_scene 的拦截同源）',
   _H.scene.switch('../../config') is False,
   'ret=%r' % (_H.scene.switch('../../config'),))

# 状态归属铁律：控制器**不许**把业务状态留在自己身上（否则状态劈两份）。
ok('H6 状态全在宿主：控制器实例字典里除 "p" 外没有任何键',
   [k for k in _H.scene.__dict__ if k != 'p'] == [],
   '控制器自有键=%r' % [k for k in _H.scene.__dict__ if k != 'p'])

ok('H7 控制器 → 宿主的方法转发真的通（forward 到 play_animation_once）',
   _H.scene.play_animation_once('idle') is True and _H.calls == ['idle'],
   'calls=%r' % _H.calls)

ok('H8 缺失的名字抛原始 AttributeError（保住 hasattr / getattr 默认值语义）',
   hasattr(_H.scene, '__definitely_missing_xyz__') is False
   and getattr(_H.scene, '__definitely_missing_xyz__', 'dflt') == 'dflt',
   'hasattr=%r' % hasattr(_H.scene, '__definitely_missing_xyz__'))

# 负控制（防递归）：宿主侧的探测必须只用「类上有没有」，不许 hasattr 控制器实例。
# 用源码断言守住这条 —— 真机踩过 RecursionError 崩在构造期。
# ⚠️ 这里**必须走 AST**，不能走 code_only_src 的字符串匹配：那个清洗器会剥掉
#    STRING token，于是 `name != 'p'` 被洗成 `name!=`（字面量没了）→ 断言恒假。
#    「能上 AST 就上 AST」是本项目第七条验证铁律（正则口径漏判过 4 个死代码）。
ok('H9 宿主 __getattr__ 用 getattr(type(ctrl), name) 探测（不用 hasattr(ctrl,...) → 不成环）',
   'getattr(type(ctrl),name' in CODE_MAIN or 'getattr(type(ctrl),name)' in CODE_MAIN,
   'main.py 里找不到 type(ctrl) 探测写法')


def _setattr_skips_p(src):
    """AST 口径：`__setattr__` 里有没有 `if name != 'p'` 这条护栏。

    为什么要 AST：文本口径会被注释提到 'p' 而误判为"有"（假绿），
    也会被 code_only_src 剥掉字符串字面量而误判为"没有"（假红）—— 两头都踩过。
    """
    import ast
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.FunctionDef) or node.name != '__setattr__':
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Compare):
                continue
            left = sub.left
            if not (isinstance(left, ast.Name) and left.id == 'name'):
                continue
            for op, comp in zip(sub.ops, sub.comparators):
                if (isinstance(op, ast.NotEq)
                        and isinstance(comp, ast.Constant)
                        and comp.value == 'p'):
                    return True
    return False


def _controller_attrs_tuple(src):
    """AST 口径：取出 `_CONTROLLER_ATTRS = (...)` 里的字符串元素。"""
    import ast
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == '_CONTROLLER_ATTRS':
                    if isinstance(node.value, (ast.Tuple, ast.List)):
                        return tuple(
                            e.value for e in node.value.elts
                            if isinstance(e, ast.Constant)
                            and isinstance(e.value, str))
    return ()


ok('H10 负控制：控制器 __setattr__ 必跳过 "p"（否则永远拿不回宿主）',
   _setattr_skips_p(SCENE_CTL_TEXT),
   'scene_controller 的 __setattr__ 里找不到 `name != "p"` 护栏')

# 负控制：上面的 AST 判据必须真能抓人 —— 拿一份「故意漏掉护栏」的合成源码试一次。
ok('H10b 负控制：漏护栏的合成源码必须被判为 False（判据有鉴别力）',
   not _setattr_skips_p('class X:\n'
                        '    def __setattr__(self, name, value):\n'
                        '        object.__setattr__(self, name, value)\n'),
   '合成样本被判为 True → 判据没有鉴别力')

ok('H11 resolve_objects() 是给 P1 渲染层的入口，现在就能调（空场景 → 空列表）',
   _H.scene.resolve_objects((0, 0, 1920, 1080)) == [],
   'got=%r' % (_H.scene.resolve_objects((0, 0, 1920, 1080)),))

ok('H12 description() 与 SceneState.describe() 同源（AI 注入的唯一出口）',
   _H.scene.description() == _H._scene_state.describe() == '桌面',
   'ctrl=%r state=%r' % (_H.scene.description(),
                         _H._scene_state.describe() if _H._scene_state else None))

# ===========================================================================
#  J  main.py 三处接线
# ===========================================================================
section('J main.py 三处接线')

ok('J1 main.py import 了 SceneController（import 期就要可用）',
   'frommodules.scene_controllerimportSceneController' in CODE_MAIN,
   'main.py 里找不到 import')

ok("J2 _CONTROLLER_ATTRS 里登记了 'scene'（宿主转发壳才认它）",
   # AST 口径：直接取元组的字符串元素。
   # ⚠️ 之前的字符串口径 `"'scene'" in CODE_MAIN` **必定假红** ——
   #    code_only_src 会剥掉所有 STRING token，元组被洗成 `('','','',...)`。
   #    （同一个坑第 5 次踩：找字符串字面量必须走 AST 或 code_no_comment。）
   'scene' in _controller_attrs_tuple(MAIN_TEXT)
   and 'games' in _controller_attrs_tuple(MAIN_TEXT),
   '_CONTROLLER_ATTRS=%r' % (_controller_attrs_tuple(MAIN_TEXT),))

ok('J3 init_systems 里创建了 self.scene = SceneController(self)',
   'self.scene=SceneController(self)' in CODE_MAIN,
   'main.py 里找不到实例化')

# 预声明：漏一个 → 该字段首次赋值会落到控制器自己的 __dict__ → 状态劈两份。
# ⚠️ 断言写的是**字段名在这些赋值里出现**，不是断言"赋值行数"（数字会漂）。
_SCENE_FIELDS = ('_scene_index', '_scene_state', 'current_scene',
                 'scene_objects', '_scene_anchors', '_scene_loaded')
_MAIN_NOSPACE = CODE_MAIN
for _f in _SCENE_FIELDS:
    _assigned = ('self.%s=' % _f) in _MAIN_NOSPACE
    ok('J4.%s 已在 main.py 预声明（self.%s = ...）' % (_f, _f),
       _assigned,
       'main.py 里找不到 self.%s = 的预声明' % _f)

# 交叉验证：控制器真正读写的字段，必须全在上面那 6 个里（防"控制器偷偷用新字段"）。
ok('J5 控制器自身不引入任何新字段名（全部走宿主已预声明的 6 个）',
   [k for k in _H.scene.__dict__ if k != 'p'] == [],
   '控制器自有键=%r' % [k for k in _H.scene.__dict__ if k != 'p'])

# ===========================================================================
#  K  桌面是一等场景（同级同构，不开后门）
# ===========================================================================
section('K 桌面是一等场景（同级同构）')

_DESK_RAW = json.load(io.open(os.path.join(SCENES_DIR, 'desktop.json'),
                             encoding='utf-8'))
ok('K1 desktop.json 用的是与作品内场景**同一套 schema**（schema_version 一致）',
   _DESK_RAW.get('schema_version') == S.SCENE_SCHEMA_VERSION,
   'ver=%r' % _DESK_RAW.get('schema_version'))

ok('K2 desktop 在索引里走的是**普通的 chapter/area/scene 三级结构**（不是特例分支）',
   ('desktop' in ((_IDX.get('chapters') or {}).get('desktop', {})
                  .get('areas', {}) or {}).get('desktop', {})
   .get('scenes', {}) if isinstance(_IDX.get('chapters'), dict) else False),
   'chapters=%r' % list((_IDX.get('chapters') or {}).keys()))

# 「不开后门」的源码级证据：控制器里不许出现 "if scene_id == 'desktop'" 这类特判。
ok('K3 控制器里没有针对 desktop 的特判分支（桌面不许开后门）',
   "=='desktop'" not in CODE_SCENE_CTL
   and '"desktop"' not in CODE_SCENE_CTL,
   'scene_controller 里出现了 desktop 特判')

# 桌面在物理层早就是一等公民（floor_manager.desktop_floor）—— 场景层对齐它。
ok('K4 场景层的桌面与物理层的桌面口径一致（floor_manager 把桌面当一等楼层）',
   'desktop_floor' in _read(os.path.join(MODS, 'floor_manager.py')),
   'floor_manager 里找不到 desktop_floor')

# ===========================================================================
#  汇总
# ===========================================================================
print('')
print('=' * 60)
print('总计 %d 项，通过 %d，失败 %d' % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - ' + f)
sys.exit(1 if FAIL else 0)
