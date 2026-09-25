# -*- coding: utf-8 -*-
"""场景系统 —— 数据层（纯数据 + 纯函数）。

这个模块是「把原作的世界搬到桌面上」这条需求的**地基**。它只做两件事：

  1. 把 `assets/scenes/` 下的 JSON 读进内存（`load_index` / `load_scene` /
     `load_zone` / `load_anchors`）；场景数据有**两个来源**：独立
     `<scene_id>.json`（87 个"锚点"）与**区域分片** `_zone.<章>.<区>.json`
     （其余场景）。分片是"拿火把赶夜路"的那支火把 —— 走到哪读到哪。
  2. 提供一组**无副作用、可单独测**的纯函数做几何/选帧/深度计算
     （`resolve_anchor` / `pick_variant` / `visible_objects` / `depth_of`）。

它**不知道** Qt 的存在，也**不知道**桌宠主程序的存在 —— 见下面的「零依赖纪律」。

零依赖纪律（🔴 违反会崩在 import 期）
------------------------------------
本模块**禁止** `import` 任何 Qt 模块、**禁止** `import` 任何项目内模块
（`logger_utils` / `data_store` / `sprite_loader` … 一律不许）。

原因：`main.py` 在 **import 期**就要 `from modules.scene_controller import
SceneController`，而 `scene_controller` 会 import 本模块。若本模块回头 import
项目内模块，就把「初始化环」重新接上 —— 本项目已经因为这件事崩过 4 次
（见 `lazy_log.py` 的 docstring，以及 `event_speech.py` 的同类纪律）。
所以：日志用标准库 `logging`，而且**本模块一行日志都不打**（纯函数不需要）。

为什么几何计算都放在这里，而不是主程序里
----------------------------------------
场景系统要做的事里，**最容易出错、也最值得单独测**的是三件纯计算：

  · 「锚点 → 屏幕像素」（`resolve_anchor`）—— 决定物件画在哪；
  · 「同一物件给多帧，这一帧画哪张」（`pick_variant`）—— 决定画什么；
  · 「谁该画在谁前面」（`depth_of`）—— 决定遮挡关系。

把它们提成纯函数（吃 dict、吐数字/字符串、不摸全局状态），才能在**没有显示器、
没有 QApplication、没有素材文件**的回归环境里断言 —— G2 全部 24 套件就是在
那种环境里跑的。反过来，只要这三件事留在主程序的 `update_animation` 里，就只能
靠"真机肉眼看"来验证，而「真机肉眼看」在本项目历史上漏掉的 bug 最多。

数据模型（三级：章节 / 区域 / 场景）
------------------------------------
::

    chapter  「第一章 · 黑暗世界」
      └── area    「城堡镇」
            └── scene   「城堡镇·广场」  ← 真正被"切到"的东西

三级是**为了后期不返工**才现在就划出来的。原作的场景切换机制经过调研，
房间 ID 是 `章号 * 10000 + 房间号` 的扁平结构（见
`场景系统扩展接口设计方案_2026-09-22.md` §0 的抄/不抄对照表）—— 我们保留
chapter/area 作为**标签**（用于 UI 分组、AI 描述词），但真正决定加载什么素材的
只有 `scene_id`。**桌面（`desktop`）是一个与"城堡镇·广场"完全平级的场景**，
不开任何后门 —— 这是用户明确要求的（「桌面也会被我当成一个场景」）。

素材路径的两套口径（⚠️ 别踩）
------------------------------
本项目的素材**有一半在仓库外**：`SpriteLoader` 的 `sprite_dir` 解析到
`<仓库根>/deltarune_ralsei/`（即 `ralsei_pet/` 的**上一级**），而不是
`ralsei_pet/assets/`。

而场景 JSON（`_index.json` / `desktop.json`）住在 `ralsei_pet/assets/scenes/`。

所以**同一个 JSON 里的路径，按前缀分两套口径** —— 由 `kind` 字段决定，
不由路径字符串猜（猜路径是"可读性换健壮性"的亏本买卖，且会在用户把场景包
搬到别处时静默失效）：

  · `kind == 'sprite'` → 相对于**仓库根**（与 `SpriteLoader.sprite_dir` 同源）；
  · 其余（`image` / `prop` / `bg`） → 相对于**本 JSON 所在目录**。

`resolve_asset_path()` 是这两套口径的**唯一翻译点**，别在别处再写一遍。
"""
import json
import logging
import os

_log = logging.getLogger(__name__)  # 标准库；本模块不主动打日志

# ===========================================================================
#  常量
# ===========================================================================

#: 场景表 schema 版本。读到不认识的版本一律**拒绝加载**（回落空态），
#: 而不是"尽力解析" —— 后者会让升级后的半坏数据静默产出错画面的场景。
SCENE_SCHEMA_VERSION = 1

#: `assets/scenes/` 相对本模块的位置：modules/ → ralsei_pet/ → assets/scenes/
_SCENES_SUBPATH = ('assets', 'scenes')

#: `kind` → 路径基准。见模块 docstring「素材路径的两套口径」。
_KIND_ROOT = 'root'                # 仓库根（<仓库>/ralsei_pet/modules/… 上两级）
_KIND_SCENE_DIR = 'scene_dir'      # 场景 JSON 自己所在的目录

#: 物件类型 → 路径口径。**不在表里的 kind 一律按 scene_dir 处理** —— 这样新增
#: 物件类型时默认是安全的那一侧（素材跟着场景包走），而不是默认去摸仓库根。
_KIND_SCOPE = {
    'sprite': _KIND_ROOT,
    'image': _KIND_SCENE_DIR,
    'prop': _KIND_SCENE_DIR,
    'bg': _KIND_SCENE_DIR,
}

#: 深度基准。`depth_of()` 返回的是**排序键**（小的画在前、大的画在后），
#: 不是像素值。基准取 1_000_000，所有物件从它往下减，于是：
#:   · 负的 delta（更靠后/更远）→ 键更大 → 画得更晚 → 盖住别人；
#:   · 正的 delta（更靠前/更近）→ 键更小 → 画得更早 → 被别人盖。
#: 与 `paintEvent` 现有"唯一动作是填透明"的极简渲染层不冲突：排序键只是一个
#: 数字，P1 才有人消费它。
_DEPTH_BASE = 1000000

#: 无锚点时的兜底位置（屏幕比例）。用比例不用像素，是为了多屏/不同 DPI 下
#: 都能落在"大致同一个视觉位置"。
_DEFAULT_ANCHOR = (0.5, 1.0)

#: 区域分片的文件名模板：`_zone.<chapter>.<area>.json`。
#: 「分片」= 把同一 (章, 区域) 下**没有独立 `<scene_id>.json`** 的场景打包成一个
#: 文件。它是「拿火把赶夜路」里那支火把 —— 走进一片区域时**整片读一次**，
#: 而不是读 1,013 个小文件（实测 835 ms）或启动时全读进来。
_ZONE_PREFIX = '_zone.'
_ZONE_SUFFIX = '.json'


# ===========================================================================
#  路径解析
# ===========================================================================

def project_root():
    """仓库根：`<根>/ralsei_pet/modules/scene_system.py` → 向上两级。

    与 `sprite_loader._project_root()` **同一定义**（那里是精灵素材的基准）。两处
    必须一致，否则 `kind='sprite'` 的物件会画不出来或画到别的目录。
    这里重写一份而不是 import 那个函数 —— 见模块 docstring 的零依赖纪律。
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def scenes_dir(project_root_override=None):
    """`<根>/ralsei_pet/assets/scenes/`。目录**不存在也照常返回**（调用方判存在）。"""
    if project_root_override:
        return os.path.join(project_root_override, 'ralsei_pet', *_SCENES_SUBPATH)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', *_SCENES_SUBPATH))


def resolve_asset_path(rel_path, kind, scene_dir_path=None):
    """把物件声明的相对路径翻成绝对路径。**两套口径的唯一翻译点**。

    :param rel_path: JSON 里写的路径，如 `"props/box.png"` 或
                     `"spr_ralsei_idle_0.png"`。为空 → 返回 `None`（该物件没有素材，
                     是合法的：可以只有坐标、作为"逻辑锚点"存在）。
    :param kind: 物件类型（`sprite` / `image` / `prop` / `bg` / 未来新增）。
    :param scene_dir_path: 该 JSON 所在目录（`load_scene` 会把 `_dir` 塞进返回值）。

    绝对路径**原样返回**（用户可能想指向 `E:\\...` 上的大素材，这不该被拦截）。
    """
    if not rel_path:
        return None
    if os.path.isabs(rel_path):
        return rel_path
    scope = _KIND_SCOPE.get(kind, _KIND_SCENE_DIR)
    if scope == _KIND_ROOT:
        base = project_root()
    else:
        base = scene_dir_path or scenes_dir()
    return os.path.normpath(os.path.join(base, rel_path))


# ===========================================================================
#  JSON 读取（一切失败都回落，绝不抛）
# ===========================================================================

def _read_json(path):
    """读一个 UTF-8 JSON。**任何异常都返回 None**，交给调用方回落。

    为什么不在这里吞掉之后记日志：本模块一行日志都不打（初始化环纪律），
    而且"文件不存在"在下次启动时是**正常路径**（首次运行还没有任何场景包）。
    真正需要知道"为什么没加载上"的是调用方，它拿到 None 自己决定要不要说话。
    """
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def load_index(scene_dir_path=None):
    """读 `_index.json` → 场景索引。

    返回（**永不抛**）::

        {'ok': bool,                   # 整个索引是否可用
         'schema_version': int,
         'chapters': {chapter_id: {...}},
         'scenes':   {scene_id: {...}},   # 展平后的场景登记表
         'default_scene': str | None,     # 启动场景
         'error': str | None}             # ok=False 时的原因（中文，给日志用）

    `ok=False` 时 `scenes` 是空 dict —— 调用方按"没有任何场景"处理即可，
    不需要额外判 None。这条形状约定（**永远返回同一种 dict**）比"失败时
    返回 None"好，因为后者会在调用方漏判时崩在 `KeyError`/`TypeError` 上，
    而崩的位置离真正的原因很远。
    """
    result = {
        'ok': False,
        'schema_version': 0,
        'chapters': {},
        'scenes': {},
        'default_scene': None,
        'error': None,
    }
    base = scene_dir_path or scenes_dir()
    path = os.path.join(base, '_index.json')
    if not os.path.isfile(path):
        result['error'] = '_index.json 不存在'
        return result

    raw = _read_json(path)
    if not isinstance(raw, dict):
        result['error'] = '_index.json 不是合法 JSON 对象'
        return result

    version = raw.get('schema_version')
    if version != SCENE_SCHEMA_VERSION:
        # 明确拒绝，不"尽力解析"：半坏的数据会静默产出错骨架的场景。
        result['error'] = 'schema_version 不支持: %r（期望 %r）' % (version, SCENE_SCHEMA_VERSION)
        return result

    chapters = raw.get('chapters') or {}
    if not isinstance(chapters, dict):
        result['error'] = 'chapters 必须是对象'
        return result

    scenes = {}
    for chapter_id, chapter in chapters.items():
        if not isinstance(chapter, dict):
            continue
        for area_id, area in (chapter.get('areas') or {}).items():
            if not isinstance(area, dict):
                continue
            for scene_id, entry in (area.get('scenes') or {}).items():
                if not isinstance(entry, dict):
                    continue
                # 登记表是**展平**的：真正决定加载什么的是 scene_id，chapter/area
                # 只作标签（UI 分组 / AI 描述词）。理由见模块 docstring。
                merged = dict(entry)
                merged['scene_id'] = scene_id
                merged['chapter_id'] = chapter_id
                merged['chapter_name'] = chapter.get('name') or chapter_id
                merged['area_id'] = area_id
                merged['area_name'] = area.get('name') or area_id
                scenes[scene_id] = merged

    result['ok'] = True
    result['schema_version'] = version
    result['chapters'] = chapters
    result['scenes'] = scenes
    result['default_scene'] = raw.get('default_scene') or None
    return result


# ---------------------------------------------------------------------------
#  明 / 暗世界（第48轮：道具效果"不可带出当前章节"的判据基础）
# ---------------------------------------------------------------------------
#  ★ 为什么需要这一层
#    用户口径：「回到光世界的时候暗世界的任何道具都会变成垃圾团里包含的东西」。
#    要判"是不是回到了光世界"，就得知道**当前场景属于哪个世界**。
#    原作判据是 `global.darkzone`（0=光明世界 / 1=暗世界，第46轮实证），
#    但它写在**每间房的创建代码**里 —— 属第42轮 `dump_rooms.csx` 的取证缺口。
#    ⇒ 本轮改用"原作房间 resource 名"这条**可审计替代判据**，
#      产物 = `_worlds.json`（生成器与自检见
#      `code-quality-audit/第48轮-道具与背包系统/_tools/gen_worlds48.py`）。
#    ⇒ 本模块只负责**读**，判据本身不在这里（数据在文件里，可单独复核）。

WORLDS_FILENAME = '_worlds.json'

#: 世界取值（与 `item_system.WORLD_*` 同字面量；本模块零依赖，不 import 它）。
WORLD_LIGHT = 'light'
WORLD_DARK = 'dark'


def load_worlds(scene_dir_path=None):
    """读 `_worlds.json` → 场景明暗世界表。

    返回（**永不抛**，形状恒定 —— 与 `load_index` 同一条约定）::

        {'ok': bool,
         'rooms': {chapter_id: {str(room_id): 'light'|'dark'|'unknown'}},
         'areas': {chapter_id: {area_id: 'light'|'dark'|'mixed'}},
         'overrides': {scene_id: 'light'|'dark'},   # 产品口径的场景级覆盖
         'meta': {...},                              # 判据说明 / 未判定清单
         'error': str | None}

    `ok=False` 时 `rooms` 为空 —— 调用方按"不知道世界"处理（**不要**默认成暗世界：
    猜错会让"回到光世界"在不该触发的时候触发，把玩家的道具变成垃圾）。
    """
    result = {'ok': False, 'rooms': {}, 'areas': {}, 'overrides': {},
              'meta': {}, 'error': None}
    base = scene_dir_path or scenes_dir()
    path = os.path.join(base, WORLDS_FILENAME)
    raw = _read_json(path)
    if raw is None:
        result['error'] = '%s 不存在或不可读' % WORLDS_FILENAME
        return result
    if not isinstance(raw, dict):
        result['error'] = '%s 顶层不是对象' % WORLDS_FILENAME
        return result
    rooms = raw.get('rooms')
    if not isinstance(rooms, dict):
        result['error'] = '%s 缺 rooms' % WORLDS_FILENAME
        return result
    result['rooms'] = rooms
    result['areas'] = raw.get('areas') if isinstance(raw.get('areas'), dict) else {}
    ov = raw.get('overrides')
    result['overrides'] = ov if isinstance(ov, dict) else {}
    result['meta'] = raw.get('meta') if isinstance(raw.get('meta'), dict) else {}
    result['ok'] = True
    return result


def world_of_scene(scene, worlds=None, scene_dir_path=None):
    """一个场景属于哪个世界 → `'light'` / `'dark'`，**判不出来就 `None`**。

    判据顺序（**先场景级覆盖，再按原作房间 id**）：
      1. `overrides[scene_id]` —— 只用于我们自建、不对应原作房间的场景（如 `desktop`）；
      2. `rooms[chapter_id][str(original_room_id)]` —— 主力判据；
      3. 都查不到 ⇒ `None`（**不猜**）。

    参数 `scene` 可以是 `SceneState`，也可以是原始 dict（渲染层/接线层都可能调）。
    """
    if scene is None:
        return None
    if isinstance(scene, dict):
        sid = scene.get('scene_id') or scene.get('id')
        ch = scene.get('chapter_id')
        rid = scene.get('original_room_id')
    else:
        sid = getattr(scene, 'scene_id', None)
        ch = getattr(scene, 'chapter_id', None)
        rid = getattr(scene, 'original_room_id', None)
    table = worlds if isinstance(worlds, dict) else load_worlds(scene_dir_path)
    if not table.get('ok'):
        return None
    ov = table.get('overrides') or {}
    if sid and sid in ov:
        return ov[sid]
    if not ch or rid is None:
        return None
    rec = (table.get('rooms') or {}).get(ch)
    if not isinstance(rec, dict):
        return None
    w = rec.get(str(rid))
    if w == 'unknown':
        # 「未判定」是一个**显式状态**，不是"暗世界"（见 gen_worlds48 的未判定清单）。
        return None
    return w if w in (WORLD_LIGHT, WORLD_DARK) else None


def zone_filename(chapter_id, area_id):
    """`(章, 区域)` → 分片文件名。**对名字做裁剪**（它会被拼进路径）。

    裁剪规则与 `load_scene` 拦路径穿越同源：只留字母/数字/`_`/`-`，
    其余一律丢掉。空掉的话用 `unknown` 兜底（宁可读不到，也不越界读）。
    """
    def clean(value):
        text = str(value or '').strip()
        text = ''.join(ch for ch in text if ch.isalnum() or ch in '_-')
        return text or 'unknown'
    return '%s%s.%s%s' % (_ZONE_PREFIX, clean(chapter_id), clean(area_id),
                          _ZONE_SUFFIX)


def load_zone(chapter_id, area_id, scene_dir_path=None):
    """读一个**区域分片** → `{scene_id: SceneState}`。**永不抛**；读不到返回 `{}`。

    为什么按"区域"打包而不是"一个房间一个文件"：见 `_ZONE_PREFIX` 的注释。
    这里只负责**读一片**；"什么时候读"是控制器的事（P0 里它跟着 `switch` 走）。

    返回 `{}` 的四种情况（都属于**正常路径**，不该报错）：
    该区域全是锚点场景（没有分片）、分片文件不存在、JSON 坏了、schema 不符。
    """
    if not chapter_id or not area_id:
        return {}
    base = scene_dir_path or scenes_dir()
    path = os.path.join(base, zone_filename(chapter_id, area_id))
    if not os.path.isfile(path):
        return {}
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return {}
    if raw.get('schema_version') != SCENE_SCHEMA_VERSION:
        return {}

    out = {}
    for scene_id, entry in (raw.get('scenes') or {}).items():
        if not isinstance(entry, dict):
            continue
        merged = dict(entry)
        # 分片里的场景**不重复写**这四样（章/区标签由分片自己给），
        # 但 `load_scene` 走独立文件那条路时它们来自 `load_index` 的 merge
        # ⇒ 这里补齐，保证两条来源产出的 `SceneState` 形状完全一致。
        merged.setdefault('scene_id', scene_id)
        merged.setdefault('chapter_id', raw.get('chapter_id'))
        merged.setdefault('area_id', raw.get('area_id'))
        merged.setdefault('area_name', raw.get('area_name'))
        scene = SceneState.from_dict(merged)
        scene.dir_path = base
        out[scene_id] = scene
    return out


def load_scene(scene_id, scene_dir_path=None, entry=None):
    """读一个场景定义 → `SceneState`。**永不抛**；读不到返回 `None`。

    两个来源，**查找顺序固定**（同一场景只出现在一个来源，不会二选一）：

      1. 独立文件 `<scene_id>.json` —— 第 36 轮登记的 87 个"锚点"场景走这条；
      2. **区域分片** `_zone.<chapter>.<area>.json` —— 第 38 轮新增的 926 个走这条。
         需要 `entry`（索引里的登记行）来知道自己在哪个 (章, 区域)。

    :param entry: 可选。`load_index()['scenes'][scene_id]`。给了它，
                  独立文件缺失时才会去分片里找；不给就只认独立文件
                  （向后兼容：老调用方 `load_scene(sid)` 行为完全不变）。

    为什么独立文件"存在但坏掉"时不静默改读分片：那会让一份半坏的数据
    **悄悄换一个数据源**，产出的场景看起来正常但来源已经不是你预期的那份。
    宁可返回 `None`（调用方保持当前场景），也不静默换源。

    找不到文件 / JSON 坏掉 / schema 不符 → `None`。调用方（控制器）拿到 None
    时应当**保持当前场景不变**，而不是切到一个空场景 —— 后者会让桌宠所在的世界
    突然变白，"切场景失败"表现得像"世界没了"。
    """
    if not scene_id:
        return None
    base = scene_dir_path or scenes_dir()
    # scene_id 会被拼进路径 → 拦掉 `..` 与分隔符，避免 `../../etc/passwd`
    # 这类"场景 id"读到仓库外的任意 JSON（场景 id 将来会来自用户点的 UI）。
    if os.sep in scene_id or '/' in scene_id or scene_id in ('.', '..'):
        return None
    path = os.path.join(base, scene_id + '.json')
    if os.path.isfile(path):
        raw = _read_json(path)
        if not isinstance(raw, dict):
            return None
        if raw.get('schema_version') != SCENE_SCHEMA_VERSION:
            return None
        scene = SceneState.from_dict(raw)
        scene.dir_path = base
        # ★ 独立文件场景（第 36 轮登记的 87 个）**不带** original_room_id ——
        #   它写在 `_index.json` 的登记行里。从 entry 补一次，让渲染层
        #   无论走哪条来源都能查房间几何（否则这 87 个场景会退化为"房间未知"）。
        if scene.original_room_id is None and isinstance(entry, dict):
            _oid = entry.get('original_room_id')
            if isinstance(_oid, int):
                scene.original_room_id = _oid
        return scene

    # ---- 来源 2：区域分片 ----
    if isinstance(entry, dict):
        chapter_id = entry.get('chapter_id')
        area_id = entry.get('area_id')
        if chapter_id and area_id:
            scene = load_zone(chapter_id, area_id, base).get(scene_id)
            if scene is not None and scene.original_room_id is None:
                _oid = entry.get('original_room_id')
                if isinstance(_oid, int):
                    scene.original_room_id = _oid
            return scene
    return None


def load_anchors(scene_dir_path=None):
    """读 `_anchors.json` → 城市/屏幕级的锚点表（`{name: (rx, ry)}`）。

    「锚点」= 命名落点。借原作 `marker` 机制：让场景物件引用**名字**
    （`"anchor": "ground_center"`）而不是硬写像素 —— 换分辨率、换多屏布局时
    物件仍落在"该落的地方"。像素坐标照旧可以直接写，两者并存（像素优先）。

    读不到就返回空 dict：锚点表不是必需品，缺了只代表物件必须写坐标。
    """
    base = scene_dir_path or scenes_dir()
    raw = _read_json(os.path.join(base, '_anchors.json'))
    if not isinstance(raw, dict):
        return {}
    anchors = raw.get('anchors')
    if not isinstance(anchors, dict):
        return {}
    out = {}
    for name, value in anchors.items():
        pair = _as_pair(value)
        if pair is not None:
            out[name] = pair
    return out


# ===========================================================================
#  纯函数（回归锁的主战场）
# ===========================================================================

def _as_pair(value):
    """把 `[x, y]` / `(x, y)` 归一成 `(float, float)`；不是二元数值序列 → None。"""
    try:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _as_rect(value):
    """把 `[l, t, r, b]` 归一成 `(float, float, float, float)`；不合法 → None。"""
    try:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return None
        return tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return None


def resolve_anchor(obj, screen_rect, anchors=None):
    """把一个物件声明的位置，翻成屏幕绝对像素 `(x, y)`；算不出 → `None`。

    优先级（**从具体到笼统**，先命中的赢）：

      1. `obj['pos']` = `[x, y]` —— **绝对屏幕像素**。最高优先级：写死了就是写死了，
         用户明确要求精确落点时不该被锚点"纠正"。
      2. `obj['anchor']` —— 先查场景自带的 `obj['anchor_pos']`（相对该物件所在
         区域的矩形），再查全局 `anchors` 表（相对**屏幕**）。
      3. 都没有 → 屏幕底部中央 `(0.5, 1.0)` 比例的兜底位。

    :param obj: 物件 dict（`{'pos'|'anchor'|'anchor_pos', ...}`）。
    :param screen_rect: `(left, top, right, bottom)` 屏幕矩形（虚拟桌面，可负）。
    :param anchors: `load_anchors()` 的结果（`{name: (rx, ry)}`），可空。
    :return: `(int, int)` 或 `None`（`screen_rect` 不合法时）。

    为什么返回 `None` 而不是 `(0, 0)`：`(0, 0)` 是一个"看起来很合理"的位置，
    于是它会把"我算不出来"伪装成"物件就该在左上角" —— 本项目最怕的就是这种
    静默降级。返回 `None` 逼调用方显式决定（跳过该物件 / 用别的兜底）。
    """
    rect = _as_rect(screen_rect)
    if rect is None:
        return None
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top

    pos = _as_pair(obj.get('pos')) if isinstance(obj, dict) else None
    if pos is not None:
        return (int(round(pos[0])), int(round(pos[1])))

    if not isinstance(obj, dict):
        return None

    rel = None
    local = _as_pair(obj.get('anchor_pos'))
    if local is not None:
        rel = local
    else:
        name = obj.get('anchor')
        if name and isinstance(anchors, dict):
            rel = _as_pair(anchors.get(name))
    if rel is None:
        rel = _DEFAULT_ANCHOR

    return (int(round(left + width * rel[0])), int(round(top + height * rel[1])))


def pick_variant(entry, tick=0):
    """从一个物件/背景的**多帧候选**里挑这一拍该画的那一帧。

    支持三种写法（**按声明顺序判断，第一个能用的赢**）：

      · `entry` 是 str      → 就它自己（单帧，最常见）
      · `entry` 有 `variants`（list）→ 按 `tick` 轮播：`variants[tick % len]`
      · `entry` 有 `frames`（list）  → 同上（与 `animations.json` 的 `frames` 同名，
        纯属便于复用同一套心智模型）

    传入 list 本身也接受（等价于 `{'variants': [...]}`）。

    :param tick: 单调递增的整数（调用方给帧号/秒数都行，本函数只做取模）。
    :return: 选中的字符串；**候选列表为空 / 元素不是字符串 → `None`**。
    """
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry
    if isinstance(entry, (list, tuple)):
        candidates = list(entry)
    elif isinstance(entry, dict):
        candidates = entry.get('variants')
        if not candidates:
            candidates = entry.get('frames')
        if isinstance(candidates, str):
            # `{'frames': 'a.png'}` —— 写成单帧字符串是常见笔误，别报错，直接用。
            return candidates
        candidates = list(candidates) if isinstance(candidates, (list, tuple)) else []
    else:
        return None

    # 只保留字符串元素：混进数字/None 时不整体作废，而是跳过坏的那些 ——
    # 一个坏元素不该让整个物件消失。
    clean = [c for c in candidates if isinstance(c, str) and c]
    if not clean:
        return None
    try:
        idx = int(tick) % len(clean)
    except (TypeError, ValueError):
        idx = 0
    return clean[idx]


def visible_objects(scene, screen_rect, anchors=None):
    """筛出"这一刻真的该画"的物件，并按**从后到前**排好序。

    过滤规则（全部在这里，别散到渲染层去）：

      1. `enabled is False` → 丢掉（场景包作者临时关掉一个物件不必删它）。
      2. `cond` 条件不满足 → 丢掉。目前支持 `{'scene_id'|'chapter_id'|'area_id': x}`
         这类**相等判定**；未知键**一律放行**（`cond` 是渐进增强，将来加条件时
         老场景包不该被误杀）。
      3. 算不出屏幕位置（`resolve_anchor` 返回 None）→ 丢掉。
      4. alpha 为 0 / 负 → 丢掉（完全透明的物件没有绘制意义，但保留 `0` 之外的
         小数值，半透明是合法的）。

    排序：`depth_of` 升序 = 先画远的、后画近的。
    稳定排序保证**同深度的物件保持声明顺序**（Python 的 `sorted` 是稳定的）。

    :return: `[dict]`，每个元素是**原物件 dict 的浅拷贝 + 两个补充键**：
             `_x` / `_y`（屏幕绝对像素）。不改原 dict（纯函数纪律）。
    """
    if scene is None:
        return []
    objects = getattr(scene, 'objects', None) or []
    if not isinstance(objects, (list, tuple)):
        return []

    kept = []
    for order, obj in enumerate(objects):
        if not isinstance(obj, dict):
            continue
        if obj.get('enabled') is False:
            continue

        cond = obj.get('cond')
        if isinstance(cond, dict) and not _cond_ok(cond, scene):
            continue

        try:
            alpha = float(obj.get('alpha', 1.0))
        except (TypeError, ValueError):
            alpha = 1.0
        if alpha <= 0.0:
            continue

        # 有 `repeat` 的物件（地面瓷砖、栅栏）**不在 P0 展开** —— 展开是 P1 的
        # 渲染层工作，P0 只保证它不会把坐标算错。方法：让它退回单点锚定。
        point = resolve_anchor(obj, screen_rect, anchors)
        if point is None:
            continue

        merged = dict(obj)
        merged['_x'], merged['_y'] = point
        merged['_order'] = order
        kept.append(merged)

    kept.sort(key=lambda o: (depth_of(o), o.get('_order', 0)))
    return kept


def _cond_ok(cond, scene):
    """物件级条件判定。未知键放行（渐进增强，见 `visible_objects` 文档）。"""
    scene_id = getattr(scene, 'scene_id', None)
    chapter_id = getattr(scene, 'chapter_id', None)
    area_id = getattr(scene, 'area_id', None)
    for key, want in cond.items():
        have = {
            'scene_id': scene_id,
            'chapter_id': chapter_id,
            'area_id': area_id,
        }.get(key)
        if have is None:
            continue  # 未知条件键 → 放行
        if isinstance(want, (list, tuple, set)):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def depth_of(obj):
    """物件的绘制排序键。**越小越先画（越远），越大越晚画（越近）**。

    三个来源，优先级从具体到笼统：

      1. `obj['depth']` —— 显式覆盖，场景包作者说了算。
      2. `obj['y']` —— 借原作的"脚底排序"思路（原作 `scr_depth()` 用
         `100000 - (y*10 + h*10)`），但这里**不引入 h**：本项目物件的"高度"
         未必有素材（可能只是逻辑锚点），缺 h 时用 0 会让排序抖动。
         用 y 单变量排序已经能满足"站得低的画在前面"这个唯一诉求。
      3. 都没有 → 0（= 与屏幕顶部同深度），**不按列表顺序伪造深度** ——
         声明顺序由 `visible_objects` 的稳定排序来保，不该混进深度键。
    """
    if not isinstance(obj, dict):
        return _DEPTH_BASE
    depth = obj.get('depth')
    if depth is not None:
        try:
            return int(round(float(depth)))
        except (TypeError, ValueError):
            pass
    y = obj.get('y')
    if y is not None:
        try:
            return _DEPTH_BASE - int(round(float(y)))
        except (TypeError, ValueError):
            pass
    return _DEPTH_BASE


# ===========================================================================
#  SceneState —— 一个场景的只读视图
# ===========================================================================

class SceneState(object):
    """一个已加载场景的**只读视图**（把 JSON dict 摊成好用的属性）。

    为什么不做成纯 dict：调用方（控制器、渲染层、AI 描述注入）需要反复读
    `scene.scene_id` / `scene.bgm` / `scene.objects`，dict 写法
    `scene['scene_id']` 每处都要防 KeyError。属性形式配 `.get()` 兜底更稳。

    **不可变**：本类的属性在 `from_dict` 之后不再被改写。要改场景 = 换一个
    `SceneState`。这样"场景切换"就退化成一次引用赋值，不存在"改了一半"的
    中间态（本项目踩过"双真源"很多次，见记忆 §4）。
    """

    __slots__ = ('scene_id', 'name', 'chapter_id', 'chapter_name', 'area_id',
                 'area_name', 'bg', 'bgm', 'ambient', 'objects', 'anchors',
                 'transition', 'raw', 'dir_path', 'original_room_id')

    def __init__(self):
        self.scene_id = None
        self.name = None
        self.chapter_id = None
        self.chapter_name = None
        self.area_id = None
        self.area_name = None
        self.bg = None          # 背景声明（str | dict | None）
        self.original_room_id = None   # ★ 原作 Data.Rooms 下标（渲染层查房间几何用）
        self.bgm = None         # BGM 路径（str | None）—— "在放就不换"由控制器判
        self.ambient = None     # 环境氛围声明（光照/天气/粒子，dict | None）
        self.objects = []       # 物件列表（list[dict]）
        self.anchors = {}       # 场景自带锚点（相对本场景区域矩形）
        self.transition = None  # 转场声明（dict | None）
        self.raw = {}           # 原始 dict（调试/前向兼容用，别改它）
        self.dir_path = None    # 本场景 JSON 所在目录（_KIND_SCENE_DIR 的基准）

    @classmethod
    def from_dict(cls, raw):
        """从 JSON dict 造一个 `SceneState`。**缺字段一律给安全默认值**。"""
        self = cls()
        if not isinstance(raw, dict):
            return self
        self.raw = raw
        self.scene_id = raw.get('scene_id') or raw.get('id')
        self.name = raw.get('name') or self.scene_id
        self.chapter_id = raw.get('chapter_id')
        self.chapter_name = raw.get('chapter_name')
        self.area_id = raw.get('area_id')
        self.area_name = raw.get('area_name')
        self.bg = raw.get('bg')
        # ★ 原作房间下标：**两个来源，一个字段**。
        #   分片里的场景自带 `original_room_id`；独立文件场景（第 36 轮登记）
        #   写在 `_index.json` 的登记行里（`entry`），所以 `from_dict` 之后
        #   控制器可能还要用 `entry` 补一次 —— 见 `load_scene()`。
        _oid = raw.get('original_room_id')
        self.original_room_id = _oid if isinstance(_oid, int) else None
        self.bgm = raw.get('bgm')
        self.ambient = raw.get('ambient')

        objects = raw.get('objects')
        # 只留 dict 元素：物件列表里混进字符串等坏元素时，跳过坏的而不是整体作废。
        self.objects = [o for o in objects if isinstance(o, dict)] \
            if isinstance(objects, (list, tuple)) else []

        anchors = raw.get('anchors')
        if isinstance(anchors, dict):
            clean = {}
            for name, value in anchors.items():
                pair = _as_pair(value)
                if pair is not None:
                    clean[name] = pair
            self.anchors = clean

        transition = raw.get('transition')
        self.transition = transition if isinstance(transition, dict) else None
        return self

    # -- 便于日志/断言的可读表示 -------------------------------------------
    def __repr__(self):
        return '<SceneState %r objects=%d>' % (self.scene_id, len(self.objects))

    def describe(self):
        """一句话中文描述 —— 给 AI 上下文注入用的**唯一入口**。

        为什么不把整个 JSON 塞进 prompt：AI 只需要"我现在在哪"，不需要知道
        物件列表、坐标、素材路径。多喂的每一个 token 都在稀释真正重要的信息
        （人设、当前话题）。所以这里只吐场景名 + 章节/区域名。

        返回空串表示"没有可说的"（`scene_id` 为空）—— 调用方拿到空串就该
        **整段不注入**，而不是注入一句"我在某个地方"。
        """
        if not self.scene_id:
            return ''
        parts = []
        if self.chapter_name:
            parts.append(self.chapter_name)
        if self.area_name and self.area_name != self.chapter_name:
            parts.append(self.area_name)
        if self.name and self.name not in parts:
            parts.append(self.name)
        return '、'.join(parts) if parts else (self.scene_id or '')
