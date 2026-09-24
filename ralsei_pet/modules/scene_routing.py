# -*- coding: utf-8 -*-
"""场景路由 —— 「什么语境下走哪条路、去哪个场景」的决策数据层。

这个模块回答用户这条需求：
    「根据场景系统，你也得给模型训练在什么语境下怎么走路线，去哪个场景」
    「你只需要留好拓展的接口，等咱开始做场景系统你才能真正根据地图线路来规划」

分层（**这是本模块存在的全部理由**）
------------------------------------
    语境（用户说了什么 / 发生了什么）
        ↓  match()   —— 纯函数，可单独测
    一条路线（route）
        ↓  apply()   —— 交给控制器，只写状态
    切到某个场景（scene_id）

**路由是数据，不是代码。** 全部规则写在 `assets/scenes/_routes.json` 里，
本模块只做「读 + 匹配」。这样用户后期想加一条「下雨天就去屋檐下」的规则，
只需要改 JSON，不需要碰 Python —— 这与场景系统「新增场景零改 main.py」
是同一条产品纪律。

零依赖纪律（🔴 与 scene_system 同源，违反会崩在 import 期）
-----------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
原因见 `scene_system.py` 的模块 docstring：`main.py` 在 import 期就要
`from modules.scene_controller import SceneController`，而控制器会 import
本模块。回头 import 项目内模块就会把「初始化环」接上（已踩 4 次）。

三条设计律（与 scene_system 同源，都有正/负控制断言）
----------------------------------------------------
1. **算不出/匹配不上 → 返回 `None`，不伪装成"就有条默认路线"** ——
   静默降级是本项目头号敌人。匹配不上就是"没有理由换场景"，调用方该
   保持原地不走。
2. **坏规则跳过，不作废整个路由表** —— 一条规则写错不该让所有场景都去不了。
3. **未知字段一律放行/忽略** —— 渐进增强：将来给规则加新条件（时间、天气、
   信任度）时，老版本读到新 JSON 不该崩，也不该误判。

与原作的关系
------------
原作没有"路由表"这种东西 —— 它的房间切换是**硬编码在剧情脚本里**的
（`room_goto(45)`），由剧本作者决定。桌面宠物没有剧作者，**决策者只能是 AI**。
所以本模块的定位是「给 AI 一张能走的地图 + 一组可解释的理由」，而不是
「复刻原作的剧情顺序」——见 `原作场景线路研究_2026-09-22.md` 的启示 4：
**路由（去哪）与渲染（画什么）必须分开**。
"""
import logging
import os

from scene_system import _read_json, scenes_dir  # noqa: F401

_log = logging.getLogger(__name__)

#: 路由表 schema 版本。读到不认识的版本**拒绝加载**（同 scene_system 纪律）。
ROUTES_SCHEMA_VERSION = 1

#: 路由表文件名。与 `_index.json` / `_anchors.json` 同目录、同 `_` 前缀
#: （`_` 前缀 = 框架文件，不会被当成场景定义去加载）。
_ROUTES_FILENAME = '_routes.json'

#: 匹配到的路线里，**优先级**字段的合法范围。越小的越先命中。
#: 缺省 `_DEFAULT_PRIORITY` 让"没写优先级的规则"排在所有显式规则的后面，
#: 但**仍在兜底之前** —— 这正是"具体规则 > 笼统规则 > 兜底"的写法。
_DEFAULT_PRIORITY = 500

#: ⚠️ 这里**故意没有** `_FALLBACK_PRIORITY`（第 38 轮删除）。
#: 曾经的 `_FALLBACK_PRIORITY = 10000` 是个**零引用的死常量** —— 兜底走的是
#: `match()` 里"一个候选都没有"那条**独立分支**，根本不参与
#: `(priority, -score, 声明序)` 排序，所以"兜底优先级"是个不存在的机制；
#: 而 `_routes.json` 里也没有任何规则用 10000（实为 100~900）。
#: 留着它只会让人以为兜底也在排序里 —— 属"看起来在守其实没守"的一类，故删。
#: 别再把它加回来：要表达"兜底最后"，正确的位置是 `match()` 的兜底分支。


# ===========================================================================
#  读取
# ===========================================================================

def routes_path(scene_dir_path=None):
    """路由表的绝对路径。文件**不存在也照常返回**（调用方判存在）。"""
    return os.path.join(scene_dir_path or scenes_dir(), _ROUTES_FILENAME)


def load_routes(scene_dir_path=None):
    """读 `_routes.json` → 路由表。**永不抛**。

    返回（形状与 `load_index` 同款 —— 永远同一种 dict）::

        {'ok': bool,
         'schema_version': int,
         'routes': [route, ...],      # 已按 (priority, 声明序) 稳定排序
         'fallback': route | None,    # `_fallback` 字段
         'error': str | None}

    每条 `route` 是原 dict 的浅拷贝 + 补充键：
      · `_order`  声明顺序（稳定排序用，不暴露给业务）

    `ok=False` 时 `routes` 为空列表 —— 调用方按"没有任何路由"处理即可，
    不需要额外判 None（同 `load_index` 的理由）。
    """
    result = {
        'ok': False,
        'schema_version': 0,
        'routes': [],
        'fallback': None,
        'error': None,
    }
    path = routes_path(scene_dir_path)
    if not os.path.isfile(path):
        result['error'] = '%s 不存在' % _ROUTES_FILENAME
        return result

    raw = _read_json(path)
    if not isinstance(raw, dict):
        result['error'] = '%s 不是合法 JSON 对象' % _ROUTES_FILENAME
        return result

    version = raw.get('schema_version')
    if version != ROUTES_SCHEMA_VERSION:
        # 明确拒绝，不"尽力解析"——半坏的规则会静默把人送到错场景。
        result['error'] = 'schema_version 不支持: %r（期望 %r）' % (
            version, ROUTES_SCHEMA_VERSION)
        return result

    entries = raw.get('routes')
    if not isinstance(entries, (list, tuple)):
        result['error'] = 'routes 必须是数组'
        return result

    routes = []
    skipped = 0
    for order, entry in enumerate(entries):
        # 坏规则跳过，不作废整表（设计律 2）。
        if not isinstance(entry, dict):
            skipped += 1
            continue
        to = entry.get('to')
        if not isinstance(to, str) or not to:
            # 没有目标场景的规则毫无意义 —— 跳过并计数（不静默）。
            skipped += 1
            continue
        merged = dict(entry)
        merged['_order'] = order
        routes.append(merged)

    # 稳定排序：先按 priority 升序，同 priority 保持声明顺序。
    # Python 的 sorted 是稳定的 → 同 priority 的规则"先写的先命中"。
    routes.sort(key=lambda r: (_priority_of(r), r.get('_order', 0)))

    fallback = raw.get('_fallback')
    if not isinstance(fallback, dict) or not isinstance(fallback.get('to'), str):
        fallback = None

    result['ok'] = True
    result['schema_version'] = version
    result['routes'] = routes
    result['fallback'] = fallback
    if skipped:
        # 只在有问题时记一条，且**带上数量** —— 排查"我加的场景怎么去不了"
        # 时，这条日志是唯一线索。
        _log.warning('路由表有 %d 条规则被跳过（缺 to / 非对象）', skipped)
    return result


def _priority_of(route):
    """取规则的优先级（int）。非数值/缺省 → `_DEFAULT_PRIORITY`。"""
    if not isinstance(route, dict):
        return _DEFAULT_PRIORITY
    try:
        return int(route.get('priority', _DEFAULT_PRIORITY))
    except (TypeError, ValueError):
        return _DEFAULT_PRIORITY


# ===========================================================================
#  匹配（纯函数 —— 回归锁主战场）
# ===========================================================================

def _get(context, key, default=None):
    """从 context 取一个字段。context 允许是 dict 或任意带属性的对象。"""
    if isinstance(context, dict):
        return context.get(key, default)
    return getattr(context, key, default)


def _as_set(value):
    """把一个"可能是标量、可能是列表"的字段归一成 set；空 → 空 set。

    为什么不直接 `set(value)`：`set("abc")` 会变成 `{'a','b','c'}` —— 用户
    写 `"mood": "abc"` 时会静默匹配上任何单字符，这是个"看起来很合理"的坑。
    字符串一律当**单个值**处理。
    """
    if value is None:
        return set()
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, (list, tuple, set, frozenset)):
        return {v for v in value if isinstance(v, str) and v}
    return set()


def _match_one(route, context):
    """单条规则是否匹配。返回 `(matched: bool, score: int)`。

    `score` = 命中了多少个**具体条件**，用于同优先级下的第二排序键
    （命中条件更多的规则更具体 → 更该赢）。**只看条件，不看 priority。**

    支持的匹配键（**全部为"非空即需命中"语义**）：

      · `when_scene`   当前场景 id —— 支持 `"*"` 表示"任意场景"
      · `when_area`    当前区域 id
      · `when_chapter` 当前章节 id
      · `when_door`    ★第44轮：出口标识（门）。**语义与其他键相反，见下**。
      · `when_mood`    宠物心情（控制器从 emotion_system 投影进来）
      · `when_event`   触发事件名（如 `"user_idle_5min"`）
      · `when_keywords` 语境关键词 —— context 里需有 `keywords` 集合，
                        任一命中即可（**OR 语义**，与其余键的 AND 语义不同，
                        这是刻意的：关键词是"说到某类话题"，多条同类词当然该
                        只要中一个）

    ★ `when_door` 为什么是"反向"语义（第44轮新增）
    ------------------------------------------
    原作一个房间常有多个出口（实测 297 个起点场景里 **125 个有多于 1 条出边**，
    最多 3 条）—— 比如 `room_krishallway` 同时有 doorB(-1，回卧房) 与
    doorC(+2，去浴室)。这正是用户点名的「**共同卡口**」问题：
    `when_scene` 单条件无法区分"从哪个门出去"。

    如果 `when_door` 走"非空即需命中"，那么带 `when_door` 的规则在
    **context 没给 door 时**会判不匹配 ⇒ 只剩不带 `when_door` 的那条能赢，
    于是"随便走一个门"这件事永远轮不到门规则。所以要反过来：

      · `when_door` 为空 / 缺省 → **本键不参与判定**（与其它键一致，放行）；
      · `when_door` 有值，且 context **也没给** `door` → **放行**（记为命中，
        但 score 不加）—— 这是"没指定就走它"，让多出口场景仍有确定归宿；
      · `when_door` 有值，且 context **给了** `door` → 相等才命中。
        `when_door: "*"` = "指定了任意门都行"。

    这样既保住"没指定时有个确定答案"，又能在指定门时精确分流。
    仍然**不伪造**：没有匹配规则时照常返回 `None`（设计律 1）。

    **未知键一律忽略**（设计律 3）——将来加 `when_weather` / `when_hour`
    时，老版本读到不认识的条件会选择**放行**而不是"判不匹配"。
    ⚠️ 注意这里的方向：放行的风险是"老版本可能去错场景"，拒绝的风险是
    "新规则在老版本上永远不生效且没人知道"。选放行，因为前者能被观测到，
    后者是静默的。
    """
    if not isinstance(route, dict):
        return False, 0

    score = 0
    # --- 场景/区域/章节：单一值，相等判定（支持 "*" 通配） ---
    for key, field in (('when_scene', 'scene_id'),
                       ('when_area', 'area_id'),
                       ('when_chapter', 'chapter_id')):
        want = route.get(key)
        if want is None:
            continue
        if not isinstance(want, str) or not want:
            continue
        have = _get(context, field)
        if want == '*':
            score += 1
            continue
        if have != want:
            return False, 0
        score += 1

    # --- ★ 门（出口）：反向语义，见 docstring ---
    want_door = route.get('when_door')
    if isinstance(want_door, str) and want_door:
        have_door = _get(context, 'door')
        if isinstance(have_door, str) and have_door:
            if want_door != '*' and have_door != want_door:
                return False, 0
            score += 1
        # context 没给 door → 放行但不加分（"没指定就走它"）

    # --- 多值集合：交集非空即命中 ---
    for key, field in (('when_mood', 'mood'), ('when_event', 'event')):
        want = _as_set(route.get(key))
        if not want:
            continue
        have = _get(context, field)
        have_set = _as_set(have)
        if not (want & have_set):
            return False, 0
        score += 1

    # --- 关键词：OR 语义（见 docstring）---
    want_kw = _as_set(route.get('when_keywords'))
    if want_kw:
        have_kw = _as_set(_get(context, 'keywords'))
        if not (want_kw & have_kw):
            return False, 0
        score += 1

    return True, score


def match(routes, context):
    """从路由表里挑出**该走的那条**。挑不到 → `None`。

    :param routes: `load_routes()` 的结果（dict），或规则的 list。
    :param context: 当前语境。dict 或带属性的对象，键见 `_match_one`。
    :return: 命中的 route（dict）或 `None`。

    排序：**先 priority 升序，再 score 降序，再声明序升序**。
    为什么要第二键 score：用户写两条 `priority` 相同的规则时，
    "命中条件更多的那条"显然更具体、更该赢 —— 否则结果取决于 JSON 里的
    书写顺序，那是个很难解释的行为（"我明明写了先判断心情"）。

    ⚠️ **返回 None 的语义**（设计律 1）：不是"随便挑一个"，而是
    **"没有任何理由换场景"**。调用方必须显式决定怎么办（通常是原地不动）。
    """
    if isinstance(routes, dict):
        table = routes if routes.get('ok') else {'routes': [], 'fallback': None}
    else:
        table = {'routes': routes or [], 'fallback': None}

    candidates = []
    for route in table.get('routes') or []:
        ok, score = _match_one(route, context)
        if ok:
            candidates.append((_priority_of(route), -score,
                               route.get('_order', 0), route))
    if candidates:
        candidates.sort(key=lambda t: (t[0], t[1], t[2]))
        return candidates[0][3]

    fallback = table.get('fallback')
    if isinstance(fallback, dict) and isinstance(fallback.get('to'), str):
        # 兜底也要回一个**浅拷贝 + 标记**，让调用方能分辨"这是兜底不是命中"。
        # ⚠️ 兜底**不参与 priority 排序**，也不该参与：能走到这一行就说明
        #    `candidates` 是空的 —— 没有第二个候选，"排在谁后面"无从谈起。
        #    所以本模块不含"兜底优先级"常量（见文件头常量区的说明）。
        fb = dict(fallback)
        fb['_fallback'] = True
        return fb
    return None


def route_target(route):
    """从一条 route 取目标 `scene_id`；取不到 → `None`。

    单独提出来是因为调用方（尤其 AI 工具层）经常只需要这一个字段，
    却要为此判 `isinstance` + `.get` —— 三处各写一遍就是三个笔误机会。
    """
    if not isinstance(route, dict):
        return None
    to = route.get('to')
    return to if isinstance(to, str) and to else None


def route_reason(route):
    """从一条 route 取"为什么要走"的自然语言理由；取不到 → `''`。

    这个字符串是**给 AI 看的**：路由命中后把它塞进上下文，AI 才知道
    "我为什么突然走到这儿了"，才可能说出「刚才聊到城堡，我就想带你去看看」
    这类有因果的话，而不是无缘无故换了个背景。
    """
    if not isinstance(route, dict):
        return ''
    reason = route.get('reason')
    return reason if isinstance(reason, str) else ''


def describe_route(route):
    """一条 route 的单行中文摘要（给日志 / AI 工具返回 / 调试用）。"""
    if not isinstance(route, dict):
        return ''
    to = route_target(route) or '<未指定>'
    priority = _priority_of(route)
    reason = route_reason(route)
    tag = '兜底' if route.get('_fallback') else 'priority=%d' % priority
    parts = ['→ ' + to, '(%s)' % tag]
    if reason:
        parts.append('- ' + reason)
    return ' '.join(parts)


# ===========================================================================
#  自省 —— 给 AI 的"我能去哪"清单
# ===========================================================================

def destinations(routes, scene_index=None):
    """列出路由表**可达的全部场景**（去重、稳定排序）。

    :param scene_index: `load_index()` 的结果。给了就**只列真实存在的场景**
        （避免 AI 被送到一个没登记的场景 —— 那会切失败，表现为"走了一半
        停住"）。不给就按路由表原样列。

    :return: `[{'scene_id','reason','name','chapter_name','area_name'}, ...]`
    """
    known = None
    if isinstance(scene_index, dict) and scene_index.get('ok'):
        known = scene_index.get('scenes') or {}

    seen = {}
    table = routes if isinstance(routes, dict) else {'routes': routes or []}
    all_routes = list(table.get('routes') or [])
    fb = table.get('fallback')
    if isinstance(fb, dict):
        all_routes.append(fb)

    for route in all_routes:
        to = route_target(route)
        if not to or to in seen:
            continue
        if known is not None and to not in known:
            continue
        entry = known.get(to, {}) if known else {}
        seen[to] = {
            'scene_id': to,
            'reason': route_reason(route),
            'name': entry.get('name') or to,
            'chapter_name': entry.get('chapter_name') or '',
            'area_name': entry.get('area_name') or '',
        }
    return [seen[k] for k in sorted(seen)]


def describe_destinations(routes, scene_index=None):
    """把可达场景拼成一段中文，**给 AI 上下文注入**。

    返回空串 = 没有可达场景 → 调用方应**整段不注入**
    （与 `SceneState.describe()` 同一条纪律：没有可说的就别硬说一句）。

    格式刻意保持**短**：每个场景一行，行首是 id（AI 要能原样吐出来当参数）。
    """
    items = destinations(routes, scene_index)
    if not items:
        return ''
    lines = []
    for it in items:
        label = it['name']
        # 章节名与场景名重复时不重复说（"桌面、桌面"这种）。
        extra = []
        if it['chapter_name'] and it['chapter_name'] != label:
            extra.append(it['chapter_name'])
        if it['area_name'] and it['area_name'] not in (label,) + tuple(extra):
            extra.append(it['area_name'])
        tail = ('（%s）' % '·'.join(extra)) if extra else ''
        reason = ('：' + it['reason']) if it['reason'] else ''
        lines.append('- %s = %s%s%s' % (it['scene_id'], label, tail, reason))
    return '\n'.join(lines)
