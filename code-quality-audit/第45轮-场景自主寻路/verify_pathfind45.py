# -*- coding: utf-8 -*-
"""第45轮 · 场景自主寻路回归锁（G2 的一部分）。

用户的原始需求（第45轮唯一指令）
--------------------------------
    「假设 Ralsei 和我说话，语境里表达了我们该去教堂看看，
      那 Ralsei 怎么自主地按路线去教堂这类的路线问题」

本轮把这句话拆成三个**不同**的问题，只上锁其中两个（确定性、可离线回归）：

    ① 意图：他是不是想去某处？   文本 → 目标词        吃 AI  → 留给 P1，只留接口
    ② 定位：目的地是哪个场景？   『教堂』→ scene_id    ★ 本锁
    ③ 寻路：从当前怎么走过去？   起点+终点 → 路径      ★ 本锁

本锁守什么
----------
A 数据层（别名表 / 原件房间图）在位且事实正确；
B ③ BFS 纯函数的语义（**正负控制成对**：可达 / 不可达 / 起终点相同 / 坏输入）；
C ② 语义定位的**消歧顺序**（先章、后精度）—— 这是本轮真踩到的缺陷，专设回归锁；
D 门面 plan_from_text 的端到端链路 + **如实报告走不到**（设计律 1）；
E 产品接线（AST：main.py 预声明 4 字段 / 控制器真调 scene_pathfind /
  _scene_chapter_id 在 switch 里被赋值）。

判据纪律（本项目踩过的坑，逐条遵守）
------------------------------------
· **不写恒真判据**（"看着在守其实没守"）—— 每条都有鉴别力，见每段注释；
· **正 / 负控制成对** —— 只说"教堂能定位到"不够，还要证明"不存在的地方**不能**定位到"；
· **行为判据用真实量级输入** —— 用真实 _index.json（1,014 场景）与真实 _room_graph.json
  （782 边），不用手搓的 3 条假数据；
· **能从源码拿的别 import** —— E 段走 AST（不 import PyQt，不实例化 App）；
· ★ **不依赖 E:\\Download\\_tmp**（按约定"用后即删"）—— 一旦依赖，临时区被清后
  不是报红而是**静默失去鉴别力**。

**不联网、不调用 Ollama、不需要显示器**（纯数据 + 纯函数 + AST）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')          # = 仓库根（锁在 第45轮.../ 下）
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
SCENES = os.path.join(PET, 'assets', 'scenes')
ALIASES = os.path.join(SCENES, '_aliases.json')
INDEX = os.path.join(SCENES, '_index.json')
GRAPH = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证',
                     '_evidence', '_room_graph.json')
PATHFIND_SRC = os.path.join(MOD, 'scene_pathfind.py')
CTRL_SRC = os.path.join(MOD, 'scene_controller.py')
MAIN_SRC = os.path.join(SRC, 'main.py')

sys.path.insert(0, MOD)

import scene_system as SS      # noqa: E402
import scene_pathfind as SP    # noqa: E402

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', cid, msg))


def _read_text(path):
    with io.open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


# ===========================================================================
#  A 数据层
# ===========================================================================

def seg_a():
    # ---- A1 别名表存在且 schema 合法 ----
    if not os.path.isfile(ALIASES):
        check('A1', False, 'A1 _aliases.json 不存在')
        return None
    al = SP.load_aliases()
    check('A1', al.get('ok') and al.get('entries'),
          'A1 别名表可加载且非空（schema_version=%r，词条 %d 条）'
          % (SP.ALIASES_SCHEMA_VERSION, len(al.get('entries') or {})))

    # ---- A2 别名表里**每条**都要能被真实索引命中（零命中 = 死词条）----
    # 为什么这条重要：初版有 7 个词条（"暗之圣域"等）命中数为 0 —— 因为它们只出现在
    # **章节名/区域名**里，而当时的 _haystack 只扫场景名。**死词条 = 看着有别名，
    # 实际永远匹配不上**。所以必须逐条拿真实索引验证，不能只验"文件非空"。
    idx = SS.load_index()
    dead = []
    for zh in (al.get('entries') or {}):
        rv = SP.resolve_target(zh, idx, al['entries'])
        if not rv.get('ok'):
            dead.append(zh)
    check('A2', not dead,
          'A2 别名表零命中词条 = 0（共 %d 条，真实索引 1,014 场景）'
          % len(al.get('entries') or {}))
    for d in dead[:5]:
        print('      [DEAD] %s' % d)

    # ---- A3 原件房间图加载且边数 == 原作取证事实 ----
    #   ★ 边数只有等值判据才有鉴别力：>0 是恒真（文件在手就 >0）。
    #   782 = 238+323+79+72+70（第42轮反汇编取证事实），写死在这里，
    #   万一有人重跑取证把某章丢了，这条会立刻报红。
    rg = SP.load_room_graph()
    got = rg.get('n_edges')
    per_ch = {ch: len(rec) for ch, rec in (rg.get('edges_by_chapter') or {}).items()}
    expect_ch = {'ch1': 238, 'ch2': 323, 'ch3': 79, 'ch4': 72, 'ch5': 70}
    check('A3', rg.get('ok') and got == 782 and per_ch == expect_ch,
          'A3 原作房间图 782 条边 / 五章分章数正确（实得 %r，分章 %r）'
          % (got, per_ch))

    # ---- A4 邻接表自洽（坏边/自环被丢弃，边数守恒不满不溢）----
    #   ⚠️ 邻接表是**两层**：`{章: {src: [edge,...]}}`。
    #   第一版写成 `sum(len(v) for v in adj.values())` = 只数了**源房间数**（442），
    #   不是边数 —— 判据本身写错了（不是产品错）。正确 = Σ 每章 Σ 每个源的出边数。
    adj = SP.build_adjacency(rg.get('edges_by_chapter') or {})
    n_adj = sum(len(edges) for table in adj.values() for edges in table.values())
    check('A4', n_adj == 782 and set(adj) == set(expect_ch),
          'A4 邻接表边数与房间图一致（%d）且五章齐全' % n_adj)

    # ---- A5 索引可用（② 的地基）----
    check('A5', idx.get('ok') and len(idx.get('scenes') or {}) == 1014,
          'A5 场景索引可用（1,014 场景）')
    return {'idx': idx, 'aliases': al['entries'], 'graph': rg,
            'adj': adj, 'entries': al['entries']}


# ===========================================================================
#  B ③ BFS 纯函数（正负控制成对）
# ===========================================================================

def seg_b(ctx):
    adj1 = ctx['adj']['ch1']

    # ---- B1 正控制：ch1 krisroom(2) → town_church(15) 恰 7 跳 ----
    #   "去教堂"的标准答案链路（四章共有）：
    #   krisroom → krishallway → torhouse → town_krisyard → town_north
    #   → town_mid → town_south → town_church  = 7 条边、8 个房间。
    #   这是**用户原场景**的正确答案，任何改动让它不再是 7 都会报红。
    path = SP.shortest_path(adj1, 2, 15)
    check('B1', isinstance(path, list) and len(path) == 7,
          'B1 ③ ch1 krisroom(2)→town_church(15) 最短 = 7 跳（实得 %s）'
          % (len(path) if isinstance(path, list) else path))

    # ---- B2 路径连续且首尾正确（不是"长度对了但接错"）----
    ok2 = False
    detail = ''
    if isinstance(path, list):
        seq = [2] + [e['dst'] for e in path]
        chain_ok = all(path[i]['src'] == seq[i] for i in range(len(path)))
        ok2 = chain_ok and seq[0] == 2 and seq[-1] == 15 and len(set(seq)) == len(seq)
        detail = 'seq=%s' % (seq,)
    check('B2', ok2, 'B2 ③ 路径首=2 尾=15 且逐边 src 接得上、无环（%s）' % detail)

    # ---- B3 起终点相同 → 空路径 []（不是 None）----
    #   语义区分：「已经在目的地」= 不需要走（[]）；「走不到」= None。
    #   混成同一个值会让调用方无法区分"无需移动"和"导航失败"。
    same = SP.shortest_path(adj1, 15, 15)
    check('B3', same == [],
          'B3 ③ 起终点相同 → []（空路径，区别于走不到的 None；实得 %r）' % (same,))

    # ---- B4 负控制：真走不到 → None（**不伪造**）----
    #   挑一个在 ch1 图里出度为 0 或明显断链的房间。ch1 房间 2 可达 15；
    #   反向 15→2 若无回程边应走不到。用**正向不可达**构造：
    #   取 ch1 里 15 的入边集合反推 —— 直接断言"不存在路时给 None"。
    #   做法：造一个只有 2→3 的迷你图，问 3→2（无回边）→ 必须 None。
    mini = {2: [{'src': 2, 'dst': 3, 'door': 'd', 'kind': 'delta'}]}
    unr = SP.shortest_path(mini, 3, 2)
    check('B4', unr is None,
          'B4 ③ 负控制：无回边时 3→2 → None（不就近凑；实得 %r）' % (unr,))

    # ---- B5 负控制：坏输入不抛 ----
    ok5 = True
    bad_cases = [(None, 1, 2), ({}, 1, 2), (adj1, None, 2), (adj1, 1, None),
                 ('x', 1, 2), (adj1, 'a', 'b')]
    for a, s, g in bad_cases:
        try:
            SP.shortest_path(a, s, g)
        except Exception as e:
            ok5 = False
            print('      [RAISE] (%r,%r,%r) → %r' % (a if not isinstance(a, dict) else 'dict', s, g, e))
    check('B5', ok5, 'B5 负控制：坏输入（None/非 dict/非 int 起终点）→ 不抛')

    # ---- B6 确定性：同一对起终点两次给同一条路径 ----
    p1 = SP.shortest_path(adj1, 2, 15)
    p2 = SP.shortest_path(adj1, 2, 15)
    check('B6', p1 == p2, 'B6 ③ 确定性：同一对起终点两次结果一致')

    # ---- B7 原作的**五章可达性**事实（如实记录，不修饰）----
    #   ★ 这条锁的是"如实报告"，不是"都能到"：
    #   ch1 从 krisroom 可到 town_church；ch4 缺 torhouse→town_krisyard 回程边
    #   （第42轮取证漏采），ch5 krisroom 出度=0 ⇒ 走不到。**发现走不到要承认**，
    #   而不是给个假路径。ch4/ch5 的缺口已列入待办（重跑 UTMT 补采）。
    reach1 = SP.plan_route(ctx['graph']['edges_by_chapter'], 'ch1', 2, 15)
    # ch4：krisroom 在原作下标 15 → 试去 town_church（ch4 里同名房间）
    ch4_scenes = ctx['idx']['chapters'].get('ch4', {}).get('areas', {})
    ch4_rooms = {}
    for ak, av in ch4_scenes.items():
        for sid, srec in (av.get('scenes') or {}).items():
            rid = srec.get('original_room_id')
            if isinstance(rid, int):
                ch4_rooms.setdefault(srec.get('name_raw') or sid, rid)
    k4 = ch4_rooms.get('room_krisroom')
    c4 = ch4_rooms.get('room_town_church')
    reach4 = (SP.plan_route(ctx['graph']['edges_by_chapter'], 'ch4', k4, c4)
              if isinstance(k4, int) and isinstance(c4, int) else None)
    check('B7', reach1.get('ok') and (reach4 is None or reach4.get('ok') is False),
          'B7 ③ 如实报告：ch1 可达教堂；ch4 krisroom(%r)→town_church(%r) 走不到 '
          '（取证缺口，见报告 §4；实得 ok=%r）'
          % (k4, c4, None if reach4 is None else reach4.get('ok')))


# ===========================================================================
#  C ② 语义定位 + 消歧顺序（本轮真缺陷的回归锁）
# ===========================================================================

def seg_c(ctx):
    idx, aliases = ctx['idx'], ctx['aliases']

    # ---- C1 正控制：『教堂』+ current_chapter='ch1' → 唯一命中 town_church ----
    r = SP.resolve_target('教堂', idx, aliases, current_chapter='ch1')
    check('C1', r.get('ok') and r.get('scene_id') == 'ch1.hometown.town_church'
          and not r.get('ambiguous') and r.get('tier') == 1,
          'C1 ② 『教堂』+ch1 → ch1.hometown.town_church 唯一（tier=%r）'
          % (r.get('tier'),))

    # ---- C2 负控制：不认识的目的地 → ok=False（不随便挑一个）----
    r2 = SP.resolve_target('不存在的地方xyz', idx, aliases, current_chapter='ch1')
    check('C2', not r2.get('ok') and r2.get('scene_id') is None and r2.get('error'),
          'C2 ② 负控制：不存在的目的地 → ok=False + error（%r）' % (r2.get('error'),))

    # ---- C3 空/非字符串目标 → ok=False ----
    ok3 = True
    for bad in ('', '   ', None, 5, []):
        rb = SP.resolve_target(bad, idx, aliases)
        if rb.get('ok'):
            ok3 = False
            print('      [BAD] %r → ok=True' % (bad,))
    check('C3', ok3, 'C3 ② 空串/纯空格/None/非字符串目标 → 一律 ok=False')

    # ---- C4 ★消歧顺序回归锁：先章、后精度 ----
    #   这是本轮**真实踩到的缺陷**：初版先按 tier 取最精确，
    #   于是『医院』在 ch1 被送到 **ch5 的花园医院**（dw_garden_hospital 是 tier0
    #   尾段精确，而 ch1 的 hospital_lobby 是 tier1）—— 荒谬。
    #   修法：先按 current_chapter 过滤，再取最精确 tier。
    #   本条的鉴别力 = **断言结果不得属于 ch5**（旧写法会立刻报红）。
    r4 = SP.resolve_target('医院', idx, aliases, current_chapter='ch1')
    ch_of = [c.get('chapter_id') for c in (r4.get('candidates') or [])]
    no_cross = bool(ch_of) and all(c == 'ch1' for c in ch_of)
    if r4.get('scene_id'):
        no_cross = r4['scene_id'].startswith('ch1.')
    check('C4', r4.get('ok') and no_cross,
          'C4 ★②消歧顺序：『医院』+ch1 **绝不跨到 ch5**（候选章=%r）' % (sorted(set(ch_of)),))

    # ---- C5 不给章时多解 → ambiguous（**不替用户决定**）----
    r5 = SP.resolve_target('教堂', idx, aliases)
    check('C5', r5.get('ok') and r5.get('ambiguous') and r5.get('scene_id') is None
          and len(r5.get('candidates') or []) > 1,
          'C5 ② 无章时『教堂』多解 → ambiguous=True 且 scene_id=None（候选 %d 个）'
          % len(r5.get('candidates') or []))

    # ---- C6 分级匹配生效：tier0（尾段精确）优先于 tier1（场景名含）----
    #   为什么要分级：一刀切 `'church' in name` 会命中 **166 个**场景（ch4 暗之圣域
    #   有 100+ 个 church_*）。分级后 ch1 内只剩 tail==church 的那批。
    #   负控制 = "166 个候选"这个荒谬量级不得复现（ch1 内 < 10）。
    nc1 = len(r.get('candidates') or [])
    check('C6', nc1 <= 10,
          'C6 ② 分级匹配把 ch1 内『教堂』候选压到 ≤10（实得 %d，未分级时全域 166）'
          % nc1)

    # ---- C7 别名关键词真的在起作用（中→英）----
    #   产品场景名口径 = 「区域中文名·尾段原样」（命名=不译）⇒ 『教堂』这两个字
    #   在场景名里**根本不存在**。所以别名表是必需品：没有它 C1 就全军覆没。
    #   负控制：传 aliases=None 时『教堂』在 ch1 内不应命中 town_church。
    r7 = SP.resolve_target('教堂', idx, None, current_chapter='ch1')
    check('C7', not (r7.get('scene_id') == 'ch1.hometown.town_church'),
          'C7 ② 别名关键词必需：不给别名表时『教堂』不再命中 town_church（实得 %r）'
          % (r7.get('scene_id'),))


# ===========================================================================
#  D 门面 plan_from_text 端到端
# ===========================================================================

def seg_d(ctx):
    idx, aliases, graph = ctx['idx'], ctx['aliases'], ctx['graph']

    # ---- D1 用户原场景全链路：从 ch1 krisroom 说『教堂』----
    plan = SP.plan_from_text('教堂', idx, graph, aliases,
                             current_scene_id='ch1.kris_room.kris_s_room')
    check('D1', plan.get('ok') and plan.get('scene_id') == 'ch1.hometown.town_church'
          and plan.get('hops') == 7 and len(plan.get('path') or []) == 8,
          'D1 端到端：krisroom 说『教堂』→ ok / 目标正确 / 7 跳 8 房（实得 ok=%r hops=%r）'
          % (plan.get('ok'), plan.get('hops')))

    # ---- D2 path 首尾 == 起点/目标，且 steps 逐条有形 ----
    ok2 = False
    if plan.get('ok'):
        p = plan.get('path') or []
        steps = plan.get('steps') or []
        ok2 = (p[0] == 'ch1.kris_room.kris_s_room'
               and p[-1] == 'ch1.hometown.town_church'
               and len(steps) == 7
               and all(s.get('from') and s.get('to') and s.get('reason') for s in steps))
    check('D2', ok2, 'D2 path 首=起点 尾=教堂，7 条 steps 每条 from/to/reason 齐全')

    # ---- D3 describe_plan 真能拼出可朗读的中文（且有步数）----
    text = SP.describe_plan(plan)
    check('D3', isinstance(text, str) and '目的地' in text and '7' in text
          and text.count('\n') >= 7,
          'D3 describe_plan 拼出中文计划（%d 行）' % (text.count('\n') + 1 if text else 0))

    # ---- D4 负控制：计划不可用 → describe_plan 返回 ''（不硬说）----
    check('D4', SP.describe_plan({'ok': False}) == '' and SP.describe_plan(None) == ''
          and SP.describe_plan({'ok': True, 'steps': []}) == '',
          'D4 负控制：计划不可用/空步骤 → describe_plan 返回 ""（不硬说）')

    # ---- D5 负控制：目标不存在 → 全链路 ok=False ----
    bad = SP.plan_from_text('不存在的地方xyz', idx, graph, aliases,
                            current_scene_id='ch1.kris_room.kris_s_room')
    check('D5', not bad.get('ok') and bad.get('error'),
          'D5 负控制：目标不存在 → ok=False + error（%r）' % (bad.get('error'),))

    # ---- D6 跨章 → 如实报"未支持"（不假装能走）----
    #   原作门位移只在章内；跨章要走"暗之泉"（另一条机制，见报告 §5）。
    #   ⚠️ 这个反例**试错了两次**，两次都是判据选错而非产品错：
    #     ① 『图书馆』—— ch1 真有 `hometown.library` ⇒ 它本来就不是跨章，产品返回 ok 是对的；
    #     ② 『赛博都市』—— 跨章前先命中 52 个候选 ⇒ 被"多解闸"拦下，测不到跨章闸。
    #   真正的反例必须**唯一命中 + 只在别章**：这里用『第三圣域』
    #   （唯一 → ch4.third_sanctuary.sanctuary_3；ch1 零命中 → 章过滤不生效 → 落 ch4）。
    #   ★ 附前置正控制：先证明该词确实是"唯一 + 落在 ch4"，否则反例不成立。
    rv_cross = SP.resolve_target('第三圣域', idx, aliases, current_chapter='ch1')
    cand_ch = sorted({c.get('chapter_id') for c in (rv_cross.get('candidates') or [])})
    precond = (rv_cross.get('ok') and not rv_cross.get('ambiguous')
               and cand_ch == ['ch4'])
    cross = SP.plan_from_text('x', idx, graph, aliases,
                              current_scene_id='ch1.kris_room.kris_s_room',
                              extract_goal=lambda t: '第三圣域')
    check('D6', precond and (not cross.get('ok')) and '跨章' in (cross.get('error') or ''),
          'D6 负控制：跨章（第三圣域 唯一→ch4，人在 ch1）→ ok=False + 跨章原因'
          '（前置 %r，候选章 %r，err=%r）'
          % (precond, cand_ch, cross.get('error')))

    # ---- D7 非字符串/None 文本 → 不抛 ----
    ok7 = True
    for bad_txt in (None, 5, [], {}):
        try:
            SP.plan_from_text(bad_txt, idx, graph, aliases,
                              current_scene_id='ch1.kris_room.kris_s_room')
        except Exception as e:
            ok7 = False
            print('      [RAISE] %r → %r' % (bad_txt, e))
    check('D7', ok7, 'D7 负控制：非字符串文本 → 不抛（寻路绝不拖垮主路径）')

    # ---- D8 当前场景未知 → 如实报错 ----
    unk = SP.plan_from_text('教堂', idx, graph, aliases,
                            current_scene_id='chX.nope.nope')
    check('D8', not unk.get('ok') and unk.get('error'),
          'D8 当前场景未登记 → ok=False + error（%r）' % (unk.get('error'),))

    # ---- D9 ★ 走不到时**不返回半个计划**（设计律 1）----
    #   半计划 = 会走一半停住。断言 ok=False 时 path/steps 必为空。
    check('D9', (not bad.get('ok')) and not bad.get('path') and not bad.get('steps'),
          'D9 ★设计律1：失败时 path/steps 均为空（不返回半个计划）')


# ===========================================================================
#  E 产品接线（AST —— 不 import PyQt、不实例化 App）
# ===========================================================================

def seg_e(ctx):
    # ---- E1 模块零依赖纪律：scene_pathfind 只准标准库 ----
    #   违反会把"初始化环"接上（已踩 4 次）→ main.py 在 import 期就崩。
    tree = ast.parse(_read_text(PATHFIND_SRC))
    bad_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split('.')[0]
                if top in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6'):
                    bad_imports.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or '').split('.')[0]
            if mod in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6'):
                bad_imports.append(node.module)
    # 只允许 import scene_system 一个项目内模块（它是同源零依赖层）。
    allowed_local = {'scene_system'}
    local_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split('.')[0]
            if top in ('modules',) or os.path.isfile(os.path.join(MOD, top + '.py')):
                local_imports.add(top)
        elif isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split('.')[0]
                if os.path.isfile(os.path.join(MOD, top + '.py')):
                    local_imports.add(top)
    check('E1', not bad_imports and local_imports <= allowed_local,
          'E1 scene_pathfind 零 Qt + 项目内依赖 ⊆ {scene_system}（禁 Qt=%r，本地=%r）'
          % (bad_imports, sorted(local_imports)))

    # ---- E2 控制器真的 import 并调用 scene_pathfind（防"函数写对了没人用"）----
    ctrl_txt = _read_text(CTRL_SRC)
    ctrl_tree = ast.parse(ctrl_txt)
    called = set()
    for node in ast.walk(ctrl_tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == 'scene_pathfind'):
            called.add(node.attr)
    need = {'load_aliases', 'load_room_graph', 'resolve_target',
            'plan_from_text', 'describe_plan'}
    check('E2', need <= called,
          'E2 控制器真调 scene_pathfind.%s（缺 %r）'
          % ('/'.join(sorted(need)), sorted(need - called)))

    # ---- E3 ★ 4 个只读方法必须在控制器上真实存在 ----
    ctrl_cls = None
    for node in ast.walk(ctrl_tree):
        if isinstance(node, ast.ClassDef):
            ctrl_cls = node
            break
    methods = {n.name for n in (ctrl_cls.body if ctrl_cls else [])
               if isinstance(n, ast.FunctionDef)}
    need_m = {'load_pathfind_data', 'resolve_destination',
              'plan_route_to', 'plan_route_text'}
    check('E3', need_m <= methods,
          'E3 控制器 4 个只读寻路方法齐全（缺 %r）' % sorted(need_m - methods))

    # ---- E4 ★ 零行为变化：寻路方法体里**不许**出现 switch / QTimer ----
    #   与第38轮路由层同纪律：计划算出来了，但"要不要真走"由 P1 的 AI 决策链定。
    #   负控制：如果哪天有人在 load_pathfind_data 里偷偷 switch，这条报红。
    viol = []
    for node in ast.walk(ctrl_tree):
        if isinstance(node, ast.FunctionDef) and node.name in need_m:
            seg = ast.get_source_segment(ctrl_txt, node) or ''
            for bad in ('self.switch(', '.switch(', 'QTimer', 'start('):
                if bad in seg:
                    viol.append('%s: %s' % (node.name, bad))
    check('E4', not viol,
          'E4 ★零行为变化：寻路 4 方法体内无 switch/QTimer（违例 %r）' % viol)

    # ---- E5 main.py 预声明 4 个字段 ----
    #   为什么必须预声明（宿主 init_systems，不是 __init__）：控制器用
    #   `pet.__dict__.get(...)` 读，缺字段会静默走"未加载"分支；
    #   而预声明让"字段存在"成为可断言的事实。
    main_tree = ast.parse(_read_text(MAIN_SRC))
    declared = set()
    for node in ast.walk(main_tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                        and t.value.id == 'self'):
                    declared.add(t.attr)
    need_d = {'_scene_aliases', '_scene_room_graph',
              '_pathfind_loaded', '_scene_chapter_id'}
    check('E5', need_d <= declared,
          'E5 main.py 预声明 4 个寻路字段（缺 %r）' % sorted(need_d - declared))

    # ---- E6 ★ _scene_chapter_id 必须在 switch() 里被赋值为章 id ----
    #   这是②消歧的**唯一数据来源**。若 switch 不投影它，C4 的消歧就是死的
    #   （永远拿到 None → 永远退化为"全域 tier 排序"）。所以必须锁"赋值在 switch 里"。
    asgn_in_switch = []
    for node in ast.walk(ctrl_tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'switch':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if (isinstance(t, ast.Attribute)
                                and t.attr == '_scene_chapter_id'):
                            asgn_in_switch.append(sub.lineno)
    # ⚠️ 判据噪声修正（第50轮）：原先把 `行号` 打进消息 —— 任何**无关**改动
    #   （第50轮给 main.py 加球容器接线）都会让行号位移 ⇒ 基线 DIFF（假警报）。
    #   行号不是稳定可观测，消息里只留**计数**（计数才是判据本体）。
    check('E6', len(asgn_in_switch) == 1,
          'E6 ★switch() 里 _scene_chapter_id 恰被赋值 1 次（实得 %d 处）'
          % len(asgn_in_switch))

    # ---- E7 幂等守卫：load_pathfind_data 必须读 _pathfind_loaded ----
    guard = False
    for node in ast.walk(ctrl_tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'load_pathfind_data':
            seg = ast.get_source_segment(ctrl_txt, node) or ''
            guard = '_pathfind_loaded' in seg
    check('E7', guard, 'E7 load_pathfind_data 幂等守卫读 _pathfind_loaded')


def main():
    ctx = seg_a()
    if ctx is None:
        return _finish()
    seg_b(ctx)
    seg_c(ctx)
    seg_d(ctx)
    seg_e(ctx)
    return _finish()


def _finish():
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_all = len(results)
    print('')
    print('合计：PASS=%d FAIL=%d' % (n_pass, n_all - n_pass))
    return 0 if n_pass == n_all else 1


if __name__ == '__main__':
    sys.exit(main())
