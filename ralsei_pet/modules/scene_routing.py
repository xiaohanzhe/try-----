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


def _pet_logger_name(_name):
    """把模块 `__name__` 映射到 `ralsei_pet.` 命名空间下的名字。

    ★ 为什么需要它（第75轮实测）：一批模块历史上用**扁平导入**取日志器
      （`try: from logger_utils import get_logger / except ImportError: 降级`）。
      当 main.py 以**包形式**加载（`from modules.x import ...`）时，
      模块内 `from logger_utils import ...` 必然 ImportError ⇒ 静默走降级
      ⇒ 拿到**裸 logger**（`modules.xxx`）⇒ 两个后果：
        ① 不在 `ralsei_pet` 树下 ⇒ 挂在根上的**文件 handler 收不到**；
        ② 没有祖先 `setLevel(INFO)` ⇒ 有效级别退回 **30 (WARNING)** ⇒ INFO 全丢。
      表现就是"故障查不到"、"日志里零故障记录"。

    ★ 为什么用标准库字符串运算而不是 import `logger_utils`：
      `logging` 是**进程级全局注册表** —— 只要名字拼对，拿到的就是同一个对象。
      所以本函数**一行项目 import 都不需要**，从而不违反纯数据层的
      「零依赖 / 白名单」契约（`scene_render` 顶层 import ⊆ logging、
      `team_hp` 禁 `from modules`、`soul_overlay` 不拖业务模块 … 那几条闸）。
    """
    if not _name or _name == '__main__':
        return 'ralsei_pet.main'
    if _name.startswith('ralsei_pet.'):
        return _name
    if _name.startswith('modules.'):
        return 'ralsei_pet.' + _name
    return 'ralsei_pet.' + _name

import os
import random

from scene_system import _read_json, scenes_dir  # noqa: F401

_log = logging.getLogger(_pet_logger_name(__name__))

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
         'hidden': [hidden, ...],     # `_hidden_rooms` 字段（第182轮；原样带出）
         'gates': [gate, ...],        # `_gates` 字段（第184轮；原样带出）
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
        'hidden': [],
        'gates': [],
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

    # ★ 第182轮：隐藏房登记（顶层 `_hidden_rooms`）。**原样带出来**，不做取舍 ——
    #   取舍（enabled / 概率合法 / once / 已发现）全部由 `pick_hidden()` 一处判，
    #   免得"加载器悄悄筛掉一条"变成事后查不到的静默降级（设计律 1/2）。
    raw_hidden = raw.get('_hidden_rooms')
    hidden = []
    if isinstance(raw_hidden, (list, tuple)):
        for order, entry in enumerate(raw_hidden):
            if isinstance(entry, dict):
                hidden.append(dict(entry, _order=order))
            else:
                _log.warning('隐藏房登记第 %d 条不是对象（已跳过）', order)

    # ★ 第184轮：门控登记（顶层 `_gates`）。同上**原样带出** —— "哪条也算数"
    #   由 `gate_for()` / `gate_target()` 判，加载器不悄悄地筛。
    raw_gates = raw.get('_gates')
    gates = []
    if isinstance(raw_gates, (list, tuple)):
        for order, entry in enumerate(raw_gates):
            if isinstance(entry, dict):
                gates.append(dict(entry, _order=order))
            else:
                _log.warning('门控登记第 %d 条不是对象（已跳过）', order)

    result['ok'] = True
    result['schema_version'] = version
    result['routes'] = routes
    result['fallback'] = fallback
    result['hidden'] = hidden
    result['gates'] = gates
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

    # --- ★★ 第122轮：**对象级**路由（`when_src` = 触发它的那个原作对象名）---
    #   为什么需要它：ut 的门对象叫 `obj_door_ruins13` / `obj_door_s_musfade` 这种，
    #   **不带字母** ⇒ `when_door` 那套表达不了"是这一扇门、不是同场景的另一扇"。
    #   实测同一间 ut 房里最多有 3 个不同的门对象（`probe_doors122` 的粒度统计），
    #   只按 `when_scene` 会挑错门。
    #
    #   ★ 与 `when_door` **故意不同**：`when_door` 缺席时"放行"（没指定就走它）；
    #     这里缺席时**判不匹配**。理由：一条对象级规则如果被"不知道是哪个对象"的
    #     语境选中，就等于**凭空指定了一扇门** —— 那正是"走错房间"。
    #     不放行 ⇒ 最多是这条规则暂时用不上（可观测），而不是静默走错。
    want_src = route.get('when_src')
    if isinstance(want_src, str) and want_src:
        have_src = _get(context, 'src')
        if not (isinstance(have_src, str) and have_src):
            return False, 0
        if want_src != '*' and have_src != want_src:
            return False, 0
        score += 1

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
#  隐藏房 —— 「进门那一刻掷骰子，掷中就改去隐藏房」（第182轮）
# ===========================================================================

#: 隐藏房的默认语义 —— **只出现一次**。
#: `_hidden_rooms` 条目写 `once: false` 可以显式允许反复出现；不写、写 null、
#: 写别的值一律按 `true` 处理（口径见第182轮用户裁定：「真随机 + 进过一次就锁」）。
#: ⚠️ 默认取"锁"而不是"不锁"是**故意**的：漏锁的后果是用户反复撞进同一间房
#:    （立刻看得见、像 bug）；漏放的后果只是那间房不再出现（与"没实现"同形）。
_HIDDEN_ONCE_DEFAULT = True


def _hidden_probability(entry):
    """取一条隐藏房登记的概率（float）；不合法 → `None`（调用方跳过，设计律 2）。

    合法范围是 `(0, 1]` 的开区间到 1：`0` 等于"登记了但永不出现"（该直接不写
    这条登记），`>1` 是笔误。**不在**这里做四舍五入或纠偏 —— 静默改写数据
    比跳过更坏（同设计律 2 的理由）。
    """
    try:
        p = float(entry.get('probability'))
    except (TypeError, ValueError):
        return None
    if not (0.0 < p <= 1.0):
        return None
    return p


def hidden_key(entry):
    """一条隐藏房登记的**锁键** = 它的目标 `scene`。取不到 → `''`。

    单提出来是因为"写锁"和"查锁"必须是同一个键 —— 两处各取一次
    `entry['scene']` 就是两个笔误机会（同 `route_target` 的理由）。
    """
    if not isinstance(entry, dict):
        return ''
    scene = entry.get('scene')
    return scene if isinstance(scene, str) else ''


def pick_hidden(hidden, from_scene, seen=None, roll=None):
    """**站在 `from_scene`、正要迈出门**时，判定要不要改去某间隐藏房。

    返回命中的那一条登记（dict，已补 `_probability`），没有命中 → `None`。

    :param hidden: `load_routes()['hidden']`。
    :param from_scene: 当前所在场景 id（原作的 `room == room_xxx` 那个 `room`）。
    :param seen: 已经发现过的场景集合（dict / set / list 都行，只做 `in` 判断）。
    :param roll: **可注入的随机源**（返回 `[0, 1)` 的无参可调用）。不传就用
        `random.random()`。★ 判据靠它把"掷骰"变成确定行为 —— 不给注入点
        就只能统计频率，那种判据既慢又不稳（第182轮的口径）。

    ★ 为什么掷骰在**出门时**而不是"进门后"：原作那段是门对象的 `Alarm_2`，
      条件是 `if (room == room_forest_area5) { … room_goto(room_man) … }` ——
      `room` 是**你正站着的这间**，掷中就直接把目的地换成隐藏房。所以判据的
      主语是"从哪儿出发"，不是"原本要去哪儿"。

    ★ 多条登记挂在同一个 `from_scene` 时**按声明序逐条掷、先命中先得**：
      这样"两间隐藏房同时可用"的极端情况下行为仍然可解释（写在前面的优先），
      而不是取决于 dict 的遍历顺序。

    ★ 不掷骰的三种情况（都不是错误，直接跳过）：`enabled` 不是 `True`
      （只留档不投用）、概率不合法、`once` 且已经发现过。
    """
    if not from_scene or not isinstance(hidden, (list, tuple)):
        return None
    seen = seen if seen is not None else ()
    rnd = roll or random.random

    for entry in sorted((e for e in hidden if isinstance(e, dict)),
                        key=lambda e: e.get('_order', 0)):
        if entry.get('enabled') is not True:
            continue
        target = hidden_key(entry)
        if not target:
            continue
        if entry.get('from_scene') != from_scene:
            continue

        once = entry.get('once')
        once = _HIDDEN_ONCE_DEFAULT if once is None else bool(once)
        if once and target in seen:
            continue

        p = _hidden_probability(entry)
        if p is None:
            continue
        try:
            r = float(rnd())
        except Exception:
            # 随机源坏了不能让走动崩掉 —— 当作"没掷中"，下一跳还有机会。
            continue
        if 0.0 <= r < p:
            hit = dict(entry)
            hit['_probability'] = p
            return hit
    return None


# ===========================================================================
#  门控 —— 「同一扇门随剧情状态改去向」（第184轮）
# ===========================================================================
#
# 要解决的问题（一句话）
# ----------------------
# `_routes.json` 里一条规则只能表达「从哪个场景的哪扇门出去」→ 一个固定目标。
# 原作却常有「**同一扇门，剧情早期去 A，之后去 B**」——最典型的是 ch2
# `obj_doorw_musfade.Alarm_2`：
#
#     if (flag[917] == 0 && phase == 0)                  room_goto(dog_traffic);
#     else if (flag[917] < 2 && flag[918] == 0 && 1/50)  room_goto(man);
#     else                                               room_goto(moss);
#
# 三分支里 `dog_traffic` 与 `moss` 是**确定性的两支**，区别只在"剧情状态"；
# 第169轮把三分支物化成三条无条件边（`7121/7122/7123`），于是 priority 最小的
# `7121` 永远赢 ⇒ `moss` **永远不可达**（第183轮的 `[NOTE]`）。
#
# 表达形状：**顶层 `_gates`，不碰 route 对象**
# ---------------------------------------------
# 塞进 route 对象（比如给 7121 加个 `when_gate` 键）要动两条规则，而 `check169`
# 的 `_original` 指纹、`check176` 的规范化 sha1 都对 route 逐字段敏感 ⇒ 会撞一排
# 与本轮无关的老锁。放顶层只影响"统计文件字节数"的纯回显套件。
#
#   "_gates": [{
#       "when_scene": "<从哪个场景出发>",
#       "when_door":  "W",                       # 门字母；缺省=任意门
#       "mark":       "ch2.city.dog_traffic",    # 状态键（plot_mark 的 key）
#       "set_mark_when_arrive": "<到这就写那笔账>",
#       "to_when_unset": "<未写过 → 去这>",
#       "to_when_set":   "<写过   → 去这>"
#   }]
#
# ★ 门控**先于** priority 生效：`route_for_door` 一进来就问它，命中就直接返回，
#   不再走 `_pick_by_pos` / priority 那套。理由：门控描述的是"这个门此刻是哪一支
#   分支"，与"两条并列边谁更具体"不是同一个问题，混在一起排会得到无从解释的结果。

#: `is_done` 没注入时按"账还没记"处理 —— **fail-open**，见 `gate_target`。
_GATE_ASSUME_UNSET = False


def _gate_str(entry, key):
    """取门控项里的一个字符串字段；取不到 / 空 / 非字符串 → `''`。"""
    if not isinstance(entry, dict):
        return ''
    v = entry.get(key)
    return v if isinstance(v, str) and v else ''


def gate_for(gates, scene_id, door=None):
    """找出**管着 (场景, 门) 这一对**的门控项；没有 → `None`。

    :param gates: `load_routes()['gates']`。
    :param scene_id: 出发场景 id。
    :param door: 门字母（`'W'` 这种）。**可以是 `None`** —— 见下。

    匹配规则（三条，都很窄）
    ------------------------
      ① `when_scene` 必须等于 `scene_id`（支持 `'*'` 通配）；
      ② `when_door` 为空 / 缺省 → 任意门都算；有值则须与 `door` 相等
         （支持 `'*'`）；
      ③ 按 `_order` 声明序取**第一条**命中的。

    ★★ 为什么"没给 `door`"时**不匹配**，而不是像 `when_door` 那样放行
    ---------------------------------------------------------------
    `when_door` 是个**筛选条件**：不知道是哪扇门时放行，最多是多挑中一条本来
    也合适的规则。门控不一样 —— 它会**改变目的地**。不知道是哪扇门就套门控，
    等于"随便走哪个门都送去 moss"，那正是"走错房间"。
    ⇒ 这里故意 **fail-closed**（缺信息就不套用），与 `when_src` 同款理由：
      不放行最多是门控暂时不生效（可观测），放行则是静默走错。
    """
    if not scene_id or not isinstance(gates, (list, tuple)):
        return None
    for entry in sorted((e for e in gates if isinstance(e, dict)),
                        key=lambda e: e.get('_order', 0)):
        want_scene = _gate_str(entry, 'when_scene')
        if not want_scene:
            continue
        if want_scene != '*' and want_scene != scene_id:
            continue
        want_door = _gate_str(entry, 'when_door')
        if want_door:
            if not (isinstance(door, str) and door):
                continue          # ★ 缺门信息 ⇒ 不套门控（见 docstring）
            if want_door != '*' and want_door != door:
                continue
        return entry
    return None


def gate_target(gate, is_done=None):
    """这条门控此刻该走哪一支 → 目标 scene_id；表达不了 → `None`。

    :param gate: `gate_for()` 的返回值。
    :param is_done: **注入的查账可调用**（`mark -> bool`）。本模块零依赖、
        **不许** import `plot_mark`（`check84` 用 AST 强制），所以只能注入。

    ★★★ `is_done` 没给 / 调用抛异常 ⇒ 按**"账还没记"**处理（`_GATE_ASSUME_UNSET`）
    ---------------------------------------------------------------------------
    这是 **fail-open**：门继续指向 `to_when_unset`，也就是"今天的行为"。
    反过来（当"已记"处理）会让门**悄悄改去另一间房**，而这件事**没有任何报错**，
    只能靠"我怎么走到这儿来了"发现 —— 那是最坏的一类故障。
    代价是：`is_done` 传丢了 ⇒ 门控**静默不生效**。这一条用判据钉死
    （`check184` 钉 `main.py` 的传参链），不指望运行时自证。
    """
    mark = _gate_str(gate, 'mark')
    if not mark:
        return None
    done = _GATE_ASSUME_UNSET
    if callable(is_done):
        try:
            done = bool(is_done(mark))
        except Exception:
            # 查账坏了 → 当"没记"（同上：不擅自改道）。
            done = _GATE_ASSUME_UNSET
    to = _gate_str(gate, 'to_when_set' if done else 'to_when_unset')
    return to or None


def gate_overrides(gates, scene_id, is_done=None):
    """把**这一场景**的门控一次性求成 `{门字母: 目标场景}`，供下游当纯数据用。

    用途：`item_interact.build_props()` 是零依赖 L1（`G1` 硬闸禁止 import 项目内
    模块），它自己读不了 `plot_mark` 的账 ⇒ 由宿主算好这张表再传下去。

    ★ 只收 `when_door` 是**具体字母**的条目：
      空 / 缺省会命中任意门，没有"字母"可当 key；`'*'` 同理。
      这种条目仍然能通过 `gate_for(gates, scene, door)` 单点查询，
      只是没法打包成 `{字母: 目标}` 这张表。**不猜一个 key 出来**。
    ★ 同一字母出现两条且目标不同 ⇒ 按声明序**先写的赢**（与 `gate_for` 一致）；
      这里不报错也不合并 —— 数据写错该由判据抓，不该由运行时替人挑。
    """
    out = {}
    if not scene_id or not isinstance(gates, (list, tuple)):
        return out
    for entry in sorted((e for e in gates if isinstance(e, dict)),
                        key=lambda e: e.get('_order', 0)):
        if _gate_str(entry, 'when_scene') not in ('*', scene_id):
            continue
        letter = _gate_str(entry, 'when_door')
        if not letter or letter == '*':
            continue
        if letter in out:
            continue
        tgt = gate_target(entry, is_done)
        if tgt:
            out[letter] = tgt
    return out


def gate_marks_on_arrival(gates, scene_id):
    """**真站进了 `scene_id`** 时该写哪些账 → `[mark, ...]`（去重、保声明序）。

    ★ 为什么记账要由表驱动、而不是在 `main` 里写 `if sid == '...dog_traffic'`：
      写死一个房间 id 意味着"下一间要门控就得改代码"，而本项目的惯例是
      能让数据说话的都放数据里（`_hidden_rooms` / `_routes` 都是这么长的）。
    ★ 只返回**该写的**，不判断"是否已经写过" —— 去重与幂等是 `plot_mark.mark_done`
      的事（它对同一个 key 重复写只是覆盖同一个 `True`）。
    """
    out = []
    if not scene_id or not isinstance(gates, (list, tuple)):
        return out
    for entry in sorted((e for e in gates if isinstance(e, dict)),
                        key=lambda e: e.get('_order', 0)):
        arrive = _gate_str(entry, 'set_mark_when_arrive')
        mark = _gate_str(entry, 'mark')
        if not arrive or not mark:
            continue
        if arrive != scene_id:
            continue
        if mark not in out:
            out.append(mark)
    return out


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
