# -*- coding: utf-8 -*-
"""场景自主寻路 —— 「Ralsei 自己在原作地图上走过去」的路线规划层。

回答用户这条需求（第 45 轮）：
    「假设 Ralsei 和我说话，语境里表达了我们该去教堂看看，
      那 Ralsei 怎么自主地按路线去教堂这类的路线问题」

★ 为什么本模块必须存在（把问题拆对，这是本模块的全部理由）
----------------------------------------------------------
用户那句话里藏着**三个不同的问题**，它们不能用同一套机制解决：

    ① 意图：他是不是想去某处？        文本 → 目标词
       吃 AI 的理解力，必须联网/真机才能验。        ← 留给 P1（本模块只留接口）
    ② 定位：目的地是哪个场景？        "教堂" → scene_id
       吃命名匹配 + 别名表，**确定性、可离线回归**。  ← ★ 本模块
    ③ 寻路：从当前位置怎么走过去？     起点+终点 → 路径
       吃原作拓扑（782 条边），**确定性、可离线回归**。← ★ 本模块

把 ① 也塞进来 = 又要联网又要真机又要判"AI 理解对不对"，那正是"验不了就
永远做不完"的坑。所以本模块**只做 ②③**，① 留一个可替换的接口占位。

零依赖纪律（🔴 与 scene_routing / scene_system 同源，违反会崩在 import 期）
---------------------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
原因：`main.py` 在 import 期就要 `from modules.scene_controller import SceneController`，
控制器再 import 本模块。回头 import 项目内模块就会把「初始化环」接上（已踩 4 次）。

三条设计律（与 scene_routing 同源，都有正/负控制断言）
----------------------------------------------------
1. **走不到 → 返回 `None`（+ 可读原因），不就近凑一个** ——
   静默降级是本项目头号敌人。"ch4 走不到教堂"是真的走不到，
   必须如实报告，不能拿"看起来近的"场景冒充。
2. **坏边/坏场景跳过，不作废整张图** —— 一条边坏了不该让整个小镇不可达。
3. **未知字段放行**（渐进增强）—— 给边加权重、给别名加同义词时，
   老版本读到不认识的键不该崩、也不该误判。

★ 与原作的关系
--------------
原作的房间切换是**硬编码在剧情脚本里**的（`room_goto(45)`），由剧本作者决定。
桌面宠物没有剧作者，**决策者只能是 AI**；但 AI 只需要决定"去哪"（②），
"怎么去"**完全由原作拓扑决定**（③）—— 这正是用户说的「相当于场景复现」。
"""
import logging
import os

from scene_system import _read_json, scenes_dir  # noqa: F401

_log = logging.getLogger(__name__)

#: 别名表 schema 版本。读到不认识 → 拒绝加载（同 scene_system 纪律）。
ALIASES_SCHEMA_VERSION = 1

#: 别名表文件名（`_` 前缀 = 框架文件，不会被当成场景定义加载）。
_ALIASES_FILENAME = '_aliases.json'

#: 房间图文件名 —— ★ 由第 42 轮反汇编取证产出，**落在 code-quality-audit 下**
#: （不是 assets/scenes）。找不到就返回空图（寻路能力降级为"只能走一步"），
#: **不抛**：寻路是锦上添花，绝不能拖垮对话/移动主路径。
_ROOM_GRAPH_REL = os.path.join(
    'code-quality-audit', '第42轮-原作拓扑取证', '_evidence', '_room_graph.json')


# ===========================================================================
#  读取
# ===========================================================================

def aliases_path(scene_dir_path=None):
    """别名表绝对路径。文件**不存在也照常返回**（调用方判存在）。"""
    return os.path.join(scene_dir_path or scenes_dir(), _ALIASES_FILENAME)


def room_graph_path(repo_root=None):
    """房间图绝对路径。`repo_root` 缺省 = `scenes_dir()` 往上三层（assets/scenes → ralsei_pet → 仓库根）。"""
    if repo_root is None:
        # scenes_dir() = <repo>/ralsei_pet/assets/scenes
        # → 上三层 = <repo>
        sd = scenes_dir()
        repo_root = os.path.abspath(os.path.join(sd, os.pardir, os.pardir, os.pardir))
    return os.path.join(repo_root, _ROOM_GRAPH_REL)


def load_aliases(scene_dir_path=None):
    """读 `_aliases.json` → `{'ok','entries','error'}`。**永不抛**。

    `entries` 形状：`{中文词: [英文关键词, ...]}`。
    `ok=False` 时 `entries` 是空 dict —— 调用方按"没有别名"处理（②退化为纯场景名匹配）。
    """
    result = {'ok': False, 'entries': {}, 'error': None}
    path = aliases_path(scene_dir_path)
    if not os.path.isfile(path):
        result['error'] = '%s 不存在' % _ALIASES_FILENAME
        return result

    raw = _read_json(path)
    if not isinstance(raw, dict):
        result['error'] = '%s 不是合法 JSON 对象' % _ALIASES_FILENAME
        return result

    version = raw.get('schema_version')
    if version != ALIASES_SCHEMA_VERSION:
        result['error'] = 'schema_version 不支持: %r（期望 %r）' % (
            version, ALIASES_SCHEMA_VERSION)
        return result

    entries = raw.get('entries')
    if not isinstance(entries, dict):
        result['error'] = 'entries 必须是对象'
        return result

    # 归一：值必须是字符串列表；非法的**跳过这一个词**（设计律 2）。
    clean = {}
    skipped = 0
    for zh, kws in entries.items():
        if not isinstance(zh, str) or not zh:
            skipped += 1
            continue
        if isinstance(kws, str):
            kws = [kws]
        if not isinstance(kws, (list, tuple)):
            skipped += 1
            continue
        got = [k for k in kws if isinstance(k, str) and k]
        if not got:
            skipped += 1
            continue
        clean[zh] = got

    result['ok'] = True
    result['entries'] = clean
    if skipped:
        _log.warning('别名表有 %d 个词条被跳过（形状不合法）', skipped)
    return result


def load_room_graph(repo_root=None):
    """读 `_room_graph.json` → `{'ok','edges_by_chapter','error'}`。**永不抛**。

    `edges_by_chapter` 形状：`{章: [{'src':int,'dst':int,'door':str,'kind':str}, ...]}`。
    邻接表**按需在 build_adjacency() 里建**（读的时候不建，省一次全表遍历）。
    """
    result = {'ok': False, 'edges_by_chapter': {}, 'error': None}
    path = room_graph_path(repo_root)
    if not os.path.isfile(path):
        result['error'] = '房间图不存在: %s' % path
        return result

    raw = _read_json(path)
    if not isinstance(raw, dict):
        result['error'] = '房间图不是合法 JSON 对象'
        return result

    chapters = raw.get('chapters')
    if not isinstance(chapters, dict):
        result['error'] = '房间图缺 chapters'
        return result

    out = {}
    total = 0
    for ch, rec in chapters.items():
        if not isinstance(rec, dict):
            continue
        edges = rec.get('edges')
        if not isinstance(edges, (list, tuple)):
            continue
        good = []
        for e in edges:
            # 坏边跳过，不作废整张图（设计律 2）。
            if not isinstance(e, dict):
                continue
            src, dst = e.get('src'), e.get('dst')
            if not isinstance(src, int) or not isinstance(dst, int):
                continue
            if src == dst:
                # 自环对寻路毫无价值（且是数据异常信号）→ 丢弃。
                continue
            good.append({
                'src': src,
                'dst': dst,
                'door': e.get('door') if isinstance(e.get('door'), str) else '',
                'kind': e.get('kind') if isinstance(e.get('kind'), str) else '',
            })
        out[ch] = good
        total += len(good)

    result['ok'] = True
    result['edges_by_chapter'] = out
    result['n_edges'] = total
    if total == 0:
        result['error'] = '房间图里一条可用边都没有'
    return result


def build_adjacency(graph):
    """把 `{'章': [edge,...]}` 变成 `{章: {src: [edge,...]}}`。空输入 → 空 dict。"""
    adj = {}
    if not isinstance(graph, dict):
        return adj
    for ch, edges in graph.items():
        table = {}
        for e in edges or []:
            table.setdefault(e['src'], []).append(e)
        adj[ch] = table
    return adj


# ===========================================================================
#  ★ ③ 寻路（纯函数 —— 回归锁主战场）
# ===========================================================================

def shortest_path(adjacency, start, goal):
    """章内 **BFS 最短路径**（= 最少门数）。走不到 → `None`。

    :param adjacency: `build_adjacency()` 的结果（**单章**的 `{src:[edge]}`）。
    :param start/goal: 房间下标（int）。
    :return: `[edge, edge, ...]`（从 start 到 goal 的边序列）；走不到 → None。

    **为什么 BFS 不是 Dijkstra**：原作门是**等权**的（走一扇门就是一扇门，
    没有"这扇门更费劲"），所以最短路径 = 最少门数 = BFS。加权重只会引入一个
    假的"代价"概念。

    **为什么不按几何距离**：第 44 轮已证伪 —— 落点坐标是**房间自己坐标系里的
    局部坐标**（10~300 的小数值），跨房比距离**在原理上不成立**
    （见 第44轮/_evidence/routes44/路由重建说明.txt 第二节）。**只能走图**。

    **确定性**：同层扩展顺序 = `adjacency` 里边的出现顺序（原作取证顺序），
    所以同一对起终点**每次给同一条路径** —— 可回归、可解释。
    """
    if not isinstance(adjacency, dict):
        return None
    if start == goal:
        return []          # 已在目的地：空路径（不是 None —— "不需要走"）
    if start is None or goal is None:
        return None

    # BFS：队列存 (当前房, 到当前房的边序列)
    from collections import deque
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        cur, path = queue.popleft()
        for edge in adjacency.get(cur) or []:
            nxt = edge['dst']
            if nxt in seen:
                continue
            new_path = path + [edge]
            if nxt == goal:
                return new_path
            seen.add(nxt)
            queue.append((nxt, new_path))
    return None            # 不伪造：真的走不到


def plan_route(edges_by_chapter, chapter, start_index, goal_index):
    """单章寻路的门面：建邻接表 → BFS。返回 `{'ok','edges','hops','error'}`。

    坏输入一律 `ok=False` + `error`（**不抛**）。
    """
    bad = {'ok': False, 'edges': [], 'hops': 0, 'error': None}
    if not isinstance(edges_by_chapter, dict):
        bad['error'] = 'edges_by_chapter 不是 dict'
        return bad
    edges = edges_by_chapter.get(chapter)
    if edges is None:
        bad['error'] = '没有这一章的房间图: %r' % (chapter,)
        return bad
    if not isinstance(start_index, int) or not isinstance(goal_index, int):
        bad['error'] = '起终点必须是房间下标（int）'
        return bad

    adj = build_adjacency({chapter: edges})[chapter]
    path = shortest_path(adj, start_index, goal_index)
    if path is None:
        # ★ 设计律 1：如实报告"走不到"，不就近凑。
        bad['error'] = '从房间 %d 走不到房间 %d（原作拓扑不通）' % (
            start_index, goal_index)
        return bad
    return {'ok': True, 'edges': path, 'hops': len(path), 'error': None}


# ===========================================================================
#  ★ ② 语义定位（纯函数）
# ===========================================================================

def _scene_pool(scene_index):
    """把索引摊平成 `[{scene_id,name,chapter_id,chapter_name,area_key,area_name,
    original_room_id}, ...]`。

    为什么要把 `area_key`（英文 slug）也带上：产品场景名是
    「区域中文名·尾段原样」（口径：命名 = 不译），例如 `家乡·town_church`
    —— **中文只到区域名**。所以『教堂』在场景名里**根本不存在**（存在的只有
    church）；反过来『暗之圣域』只出现在**区域名**里。两边都要能匹配。
    """
    out = []
    if not isinstance(scene_index, dict) or not scene_index.get('ok'):
        return out
    chapters = scene_index.get('chapters')
    if not isinstance(chapters, dict):
        return out
    for ch, crec in chapters.items():
        if not isinstance(crec, dict):
            continue
        ch_name = crec.get('name') or ''
        areas = crec.get('areas') or {}
        if not isinstance(areas, dict):
            continue
        for area_key, arec in areas.items():
            if not isinstance(arec, dict):
                continue
            area_name = arec.get('name') or ''
            scenes = arec.get('scenes') or {}
            if not isinstance(scenes, dict):
                continue
            for sid, srec in scenes.items():
                if not isinstance(srec, dict):
                    continue
                out.append({
                    'scene_id': sid,
                    'name': srec.get('name') or sid,
                    'chapter_id': ch,
                    'chapter_name': ch_name,
                    'area_key': area_key,
                    'area_name': area_name,
                    'original_room_id': srec.get('original_room_id'),
                })
    return out


def _haystack(rec):
    """一条场景记录的"可匹配文本"（小写）。三层：场景名 / 章节名 / 区域（key+名）。"""
    return ' '.join([
        str(rec.get('name') or ''),
        str(rec.get('chapter_name') or ''),
        str(rec.get('area_key') or ''),
        str(rec.get('area_name') or ''),
    ]).lower()


def _name_tail(rec):
    """场景名的**尾段**（`区域中文名·尾段原样` 里的后一半）。没有 `·` → 整名。"""
    nm = str(rec.get('name') or '')
    if '·' in nm:
        return nm.rsplit('·', 1)[-1]
    return nm


def _match_tier(rec, want_low, kws):
    """匹配等级（越小越精确）。**这是 ② 能用起来的关键**。

    ★ 为什么必须有分级：『教堂』一刀切会命中 **166 个**场景 —— 因为 ch4 的
    暗之圣域区里有 100+ 个 `church_*` 房间（`church_bellplay` /
    `church_librarybookenemy` …）。但用户说"去教堂"时想的显然是
    **家乡的那一座**（`town_church`）。

    分级（从精确到笼统）：
      0 = 场景名**尾段恰好等于**目标/关键词（`town_church` 对 `church`）
      1 = 场景名**含**目标/关键词（`church_main`、`church_entrance`）
      2 = 只在**区域/章节**层面命中（`暗之圣域` → 该区所有场景）
      -1 = 不命中

    同 tier 内再由 `resolve_target` 按「当前章优先 → 名字短 → 字典序」排。
    """
    tail = _name_tail(rec).lower()
    full = str(rec.get('name') or '').lower()
    cands = [want_low] + list(kws)
    for c in cands:
        if c and tail == c:
            return 0
    for c in cands:
        if c and c in full:
            return 1
    for c in cands:
        if c and c in _haystack(rec):
            return 2
    return -1


def resolve_target(target, scene_index, aliases=None, current_chapter=None):
    """把用户口语里的目的地（如『教堂』）定位到场景。

    :param target: 用户说的目的地词（中文或英文）。
    :param scene_index: `load_index()` 的结果。
    :param aliases: `load_aliases()` 的 `entries`（`{中文:[英文关键词]}`）。
    :param current_chapter: 当前所在章 id —— ★ 用作**首选消歧手段**：
        若该章内有任意候选，就**只在章内挑**（"我们去教堂"通常指**这一章**的
        教堂；"去医院"时人在 ch1，绝不该被送到 ch5 的花园医院）。
    :return: `{'ok','scene_id','candidates','ambiguous','error','tier'}`

    ★ 歧义处理（**不猜，但也不把 166 个候选甩给调用方**）
    -----------------------------------------------
    「教堂」在五章命中 **166 个**场景（ch4 暗之圣域有 100+ 个 `church_*`）。
    处理分三步：
      1. **章优先**：给了 `current_chapter` 且该章内有候选 → 只留该章的。
      2. **精度优先**：在剩下的里按**匹配等级**（见 `_match_tier`）只留最精确
         的一级。例：`town_church` 是 tier 0（尾段精确），`church_bellplay`
         是 tier 1 ⇒ 只留 `town_church` 这类（每章一座），候选从 166 骤降。
      3. 仍唯一 → 直接给 `scene_id`；仍多解 → `ambiguous=True` +
         `candidates` 交回调用方（**不替用户决定**）。
    零命中 → `ok=False`（设计律 1：匹配不上 ≠ 随便挑一个）。
    """
    result = {'ok': False, 'scene_id': None, 'candidates': [],
              'ambiguous': False, 'tier': None, 'error': None}
    if not isinstance(target, str) or not target.strip():
        result['error'] = '目标词为空'
        return result

    pool = _scene_pool(scene_index)
    if not pool:
        result['error'] = '场景索引不可用'
        return result

    want = target.strip()
    want_low = want.lower()

    # 别名关键词（中文 → 英文）：只在**没有中文直接命中**时才需要，
    # 但 tier 计算要把两者一起看 —— 否则『教堂』(中文零直接命中) 会漏。
    kws = []
    if isinstance(aliases, dict):
        kws = [k.lower() for k in (aliases.get(want) or []) if isinstance(k, str)]

    # 逐条算 tier
    tiered = []
    for rec in pool:
        t = _match_tier(rec, want_low, kws)
        if t >= 0:
            tiered.append((t, rec))
    if not tiered:
        result['error'] = '没有场景匹配 %r' % want
        return result

    # ★ 消歧顺序（**先章、后精度**）—— 这个顺序是本轮调出来的：
    #   用户说"去医院"时人在 ch1，ch1 有 `hospital_lobby`(tier1)，
    #   而 ch5 有 `dw_garden_hospital`(tier0 尾段精确)。若**先按 tier 排**，
    #   就会把人送到第五章的花园医院 —— 荒谬。所以：
    #     ① 若给了 current_chapter 且**该章有任意候选** → 只在章内挑；
    #     ② 章内再按 tier 取最精确的一级；
    #     ③ 没给章 → 直接按 tier 取最精确的一级。
    if current_chapter:
        same = [pair for pair in tiered if pair[1]['chapter_id'] == current_chapter]
        if same:
            tiered = same

    best_tier = min(t for t, _ in tiered)
    hits = [rec for t, rec in tiered if t == best_tier]
    result['tier'] = best_tier

    # 排序：名字短优先 → scene_id 字典序（确定性）
    hits.sort(key=lambda rec: (len(rec['name'] or ''), rec['scene_id']))

    result['ok'] = True
    if len(hits) == 1:
        result['scene_id'] = hits[0]['scene_id']
        result['candidates'] = [hits[0]]
        result['ambiguous'] = False
    else:
        # ★ 多个命中：不猜，交回调用方。
        result['ambiguous'] = True
        result['candidates'] = hits
        result['scene_id'] = None
    return result


# ===========================================================================
#  门面：把 ① ② ③ 串起来
# ===========================================================================

def _default_extract_goal(text):
    """① 意图识别的**占位实现**（P1 会换成 AI）。

    现在只做一件最保守的事：把文本原样当"目标词"候选 —— 由 ② 去判定它
    是否真的是个场景。这**不会**误伤（匹配不上就 `ok=False`），
    也**不会**抢 P1 的活（P1 换成 AI 后，本函数整体被替换）。

    ⚠️ 为什么不做关键词表：那会退化成"可逐字搬走的固定例句"
    （记忆 §5 头号失真源）。正确做法（P1）是让 AI 在回复里带结构化标记
    （如 `[[go:教堂]]`），再解析标记 —— 复用既有的人味护栏，不新造一套。
    """
    if not isinstance(text, str):
        return None
    t = text.strip()
    return t or None


def plan_from_text(text, scene_index, room_graph, aliases=None,
                   current_scene_id=None, extract_goal=None):
    """① 文本 → ② 场景 → ③ 路径。返回一份**可解释**的导航计划。**永不抛**。

    :return::
        {'ok': bool,
         'goal': str|None,            # ① 识别出的目标词
         'scene_id': str|None,        # ② 定位到的场景（歧义时为 None）
         'ambiguous': bool,           # ② 是否多解（候选见 candidates）
         'candidates': [...],         # ② 候选（含章/区域，供选择）
         'path': [scene_id, ...],     # ③ 逐跳场景 id（含起点）
         'steps': [{from,to,door,reason}, ...],   # ③ 逐步（可朗读给 AI）
         'hops': int,
         'error': str|None}

    任何一步失败都**如实**把 `ok` 置 False 并给出 `error`，
    不返回"半个计划"（半个计划 = 会走一半停住）。
    """
    result = {
        'ok': False, 'goal': None, 'scene_id': None, 'ambiguous': False,
        'candidates': [], 'path': [], 'steps': [], 'hops': 0, 'error': None,
    }
    try:
        extractor = extract_goal if callable(extract_goal) else _default_extract_goal
        goal = extractor(text)
        result['goal'] = goal
        if not goal:
            result['error'] = '这句话里看不出要去哪'
            return result

        # 当前场景 → 章 + 房间下标（换算见下）
        cur = _locate_scene(current_scene_id, scene_index)
        if cur is None:
            result['error'] = '当前场景未知或未登记: %r' % (current_scene_id,)
            return result

        # ② 定位目标
        rv = resolve_target(goal, scene_index, aliases,
                            current_chapter=cur['chapter_id'])
        result['ambiguous'] = rv.get('ambiguous', False)
        result['candidates'] = rv.get('candidates') or []
        if not rv.get('ok'):
            result['error'] = rv.get('error')
            return result
        if rv.get('ambiguous'):
            # ★ 不猜：多个候选 → 让调用方选（把候选连同章/区域返回）。
            result['error'] = '目标有 %d 个候选，需要指定是哪一个' % len(result['candidates'])
            return result

        tgt = _locate_scene(rv['scene_id'], scene_index)
        if tgt is None:
            result['error'] = '目标场景未登记 original_room_id: %r' % (rv['scene_id'],)
            return result
        result['scene_id'] = rv['scene_id']

        # 跨章不算（原作门位移只在章内；跨章要走"暗之泉"另说）
        if tgt['chapter_id'] != cur['chapter_id']:
            result['error'] = '跨章寻路未支持（当前 %s，目标 %s）' % (
                cur['chapter_id'], tgt['chapter_id'])
            return result

        # ③ 寻路
        pr = plan_route(room_graph.get('edges_by_chapter') if isinstance(room_graph, dict)
                        else None,
                        cur['chapter_id'], cur['room_index'], tgt['room_index'])
        if not pr.get('ok'):
            result['error'] = pr.get('error')
            return result

        # 把"房间下标路径"翻回"场景 id 路径 + 可朗读步骤"
        idx_by_room = _scene_id_by_room(scene_index, cur['chapter_id'])
        path_ids = [cur['scene_id']]
        steps = []
        cur_id = cur['scene_id']
        for e in pr['edges']:
            nxt_id = idx_by_room.get(e['dst'])
            if not nxt_id:
                # 中间落到一个"没登记为场景"的房间 → 如实报告（不跳过、不伪造）。
                result['error'] = '路径经过未登记为场景的房间（原作下标 %d）' % e['dst']
                return result
            steps.append({
                'from': cur_id, 'to': nxt_id,
                'door': e.get('door') or '',
                'reason': _step_reason(idx_by_room, e, path_ids),
            })
            path_ids.append(nxt_id)
            cur_id = nxt_id

        result['ok'] = True
        result['path'] = path_ids
        result['steps'] = steps
        result['hops'] = pr['hops']
        return result
    except Exception as e:      # 寻路是锦上添花，绝不拖垮主路径
        _log.debug('寻路失败（已降级为不换场景）: %s', e)
        result['error'] = '寻路内部错误: %s' % e
        return result


def _locate_scene(scene_id, scene_index):
    """`scene_id` → `{'chapter_id','room_index','scene_id'}`；找不到 → None。"""
    if not isinstance(scene_id, str) or not scene_id:
        return None
    pool = _scene_pool(scene_index)
    for rec in pool:
        if rec['scene_id'] != scene_id:
            continue
        rid = rec.get('original_room_id')
        if not isinstance(rid, int):
            return None
        return {'chapter_id': rec['chapter_id'], 'room_index': rid,
                'scene_id': scene_id}
    return None


def _scene_id_by_room(scene_index, chapter):
    """`{房间下标: scene_id}`（**限单章**）。用于把下标路径翻回场景 id。"""
    out = {}
    for rec in _scene_pool(scene_index):
        if rec['chapter_id'] != chapter:
            continue
        rid = rec.get('original_room_id')
        if isinstance(rid, int) and rid not in out:
            out[rid] = rec['scene_id']
    return out


def _step_reason(idx_by_room, edge, path_ids):
    """给一步配一句"为什么走这扇门"（注入给 AI，让它能说出因果）。"""
    door = edge.get('door') or ''
    kind = edge.get('kind') or ''
    if kind == 'delta':
        return '走 %s 出去' % door if door else '从出口出去'
    if kind == 'table':
        return '走 %s 出去（表驱动门）' % door if door else '从出口出去'
    return '走 %s 出去' % door if door else '继续前进'


def describe_plan(plan):
    """把导航计划拼成**给 AI 看的一段中文**（可注入 system 尾部）。

    返回空串 = 计划不可用 → 调用方应**整段不注入**
    （同 scene_routing.describe_destinations 的纪律：没有可说的就别硬说）。
    """
    if not isinstance(plan, dict) or not plan.get('ok'):
        return ''
    steps = plan.get('steps') or []
    if not steps:
        return ''
    lines = ['【我打算这么走过去】（目的地：%s，共 %d 步）'
             % (plan.get('scene_id'), plan.get('hops') or len(steps))]
    for i, s in enumerate(steps, 1):
        lines.append('%d. %s → %s：%s' % (i, s.get('from'), s.get('to'),
                                          s.get('reason') or ''))
    return '\n'.join(lines)
