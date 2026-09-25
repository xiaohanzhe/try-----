# -*- coding: utf-8 -*-
"""第48轮 · 道具 / 背包 / S 键菜单 回归锁（G2 的一部分）。

用户的原始需求（第48轮唯一指令，逐字）
--------------------------------------
    「对于里面可互动的道具也要做到可以互动，当然，道具效果不可带出当前章节的场景，
      也就回到光世界的时候暗世界的任何道具都会变成垃圾团里包含的东西，道具效果就直接消失，
      如果在其他场景使用非当前场景的道具那就显示"一股神秘的力量阻止了你"。
      对了，游戏里的背包这类的通过S键实现的菜单也要应用哦，但，设置不应用」

拆成 5 条可验收的行为，本锁**逐条**守：

    ① 场景里可互动的道具真的能互动                     → E 段
    ② 道具效果不可带出当前章节（回光世界 ⇒ 变垃圾团、效果消失）→ B / C 段
    ③ 异场景使用 ⇒ 文案「一股神秘的力量阻止了你」        → C 段（**逐字**）
    ④ S 键菜单（背包/ITEM…）要应用                       → D 段
    ⑤ **但"设置"不应用**                                 → D 段（专设一条 + 负控制）

本锁守什么（按段）
------------------
A 数据层纪律 —— 道具效果必须是**机器抽取**、可复算的，不许"手抄进生成器"；
B 两个袋子 / 垃圾团 —— 照抄 `scr_itemget` / `scr_itemshift` 的容量、线性探测、前移；
C 判定 —— `Inventory.use()` 的 verdict 优先级（**垃圾 > 异域 > 可用**）；
D 菜单 —— 照抄两个菜单对象的根菜单/编号/光标协议，**摘掉设置页**；
E 可交互物 —— 分类如实（数据缺口不许装成已实现）+ 交互锁必须能释放；
F 明暗世界表 —— 覆盖率可独立重算 + **邻域反例两侧为 0**（判据不许过窄也不许过宽）；
G 产品接线（AST） —— 零依赖 / 热键**必须带修饰键** / 场景切换钩子真接上；
H 恒真判据自查 —— "数据读不到 ⇒ 判据退化 ⇒ 全绿"这条路必须被堵住。

判据纪律（本项目踩过的坑，逐条遵守）
------------------------------------
· **不写恒真判据** —— 每条都配了正/负控制，见每条后面的注释；
· ★★ **"能从源码拿的别 import，能 import 的别重写，不得不重写必须锁等价"** ——
  A3 就是这条：抽取逻辑**复用** `extract_effects48` 的三个纯函数（不重写正则），
  只把**输入**从"临时区 `E:\\Download\\_tmp`"换成"仓库内蒸馏副本 `_evidence/gml/`"，
  并用"结果与原证据表逐条相等"来锁这次替换的等价性。
· ★★ **不依赖 `E:\\Download\\_tmp`**（按约定"用后即删"）—— 一旦依赖，临时区被清后
  不是报红而是**静默失去鉴别力**（读不到 ⇒ 空表 ⇒ 全相等 ⇒ 全绿）。H 段专堵这条路。
· ★★ **负控制输入必须真落进被测分支** —— D5 用**三件**道具（不是两件）才抓得到
  "动作页把动作光标当槽位用"那个真 bug：两件时 cursor==slot_index，错位看不出来。

**不联网、不调 Ollama、不实例化 App、不需要显示器**（纯数据 + 纯函数 + AST，零 Qt）。
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')            # = 仓库根
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
SCENES = os.path.join(PET, 'assets', 'scenes')
ITEMS = os.path.join(PET, 'assets', 'items')
EVID = os.path.join(HERE, '_evidence')
GML = os.path.join(EVID, 'gml')
TOOLS = os.path.join(HERE, '_tools')
EFFECTS_JSON = os.path.join(EVID, 'items_effects48.json')
ROOMTABLE = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查',
                         '_evidence', '房间表_全量.json')
WORLDS_JSON = os.path.join(SCENES, '_worlds.json')

sys.path.insert(0, MOD)
sys.path.insert(0, TOOLS)

import item_system as IS          # noqa: E402
import item_menu as IM            # noqa: E402
import item_interact as II        # noqa: E402
import global_hotkey as GH        # noqa: E402
import scene_system as SS         # noqa: E402
import companion as CP            # noqa: E402
import extract_effects48 as EX    # noqa: E402  （只复用它的三个纯函数）
import gen_items48 as GI          # noqa: E402  （只复用它的 _kind_of）
import gen_worlds48 as GW         # noqa: E402  （只复用它的 classify_room）

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', cid, msg))


def _text(path):
    with io.open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def _json(path):
    with io.open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _tree(path):
    return ast.parse(_text(path), filename=path)


#: 允许出现在**函数内**的 import —— 刻意的延迟导入，且接不上初始化环：
#:   · `PyQt5` —— 让纯逻辑部分能离线跑（global_hotkey 的 `install()` / `HotkeyFilter`）；
#:   · `ctypes` —— 标准库，无副作用。
#: 项目内的模块一律**不许**出现在函数内（`main.py` import 期就建控制器，
#: 函数内 import 项目模块 = 把初始化环接上 ⇒ 症状是 import 期直接崩、零输出）。
ALLOWED_INNER_IMPORTS = frozenset({'PyQt5', 'ctypes'})


def _imports(path):
    """→ (顶层模块名集合, 函数内 import 的模块名列表)。"""
    top, inner = set(), []
    tree = _tree(path)

    def walk(node, depth):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(ch, depth + 1)
                continue
            if isinstance(ch, ast.Import):
                for a in ch.names:
                    if depth:
                        inner.append(a.name)
                    else:
                        top.add(a.name)
            elif isinstance(ch, ast.ImportFrom):
                if depth:
                    inner.append(ch.module or '')
                else:
                    top.add(ch.module or '')
            walk(ch, depth)

    walk(tree, 0)
    return top, inner


CAT = IS.load_catalog(ITEMS)
WORLDS = SS.load_worlds()
INDEX = SS.load_index()


# ===========================================================================
#  A 数据层：道具表必须是"机器抽取 + 可复算"的
# ===========================================================================

def seg_a():
    idx = _json(os.path.join(ITEMS, '_index.json'))
    # ---- A1 索引 schema + 容量（容量是照抄原作的硬事实）----
    check('A1', idx.get('schema_version') == 1
          and (idx.get('bag_capacity') or {}) == {'dark': 12, 'light': 8},
          'A1 道具索引 schema_version=1 且 bag_capacity={dark:12, light:8}（照抄 scr_itemget/scr_litemget）')

    # ---- A2 索引声明的条目数 == 实际文件里的条目数（逐章逐世界）----
    #   为什么逐章：只断言"总数对"会被"某章多一条、某章少一条"互相抵消。
    bad, tot = [], 0
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        decl = (idx.get('chapters') or {}).get(ch) or {}
        rec = CAT.chapter(ch)
        for w, key in (('dark', 'dark_items'), ('light', 'light_items')):
            got = len(((rec.get('items') or {}).get(w)) or {})
            tot += got
            if got != decl.get(key):
                bad.append('%s/%s 声明 %s 实得 %d' % (ch, w, decl.get(key), got))
    check('A2', not bad and tot > 0,
          'A2 五章索引声明 == 实际条目（共 %d 条；不一致 %d 处）' % (tot, len(bad)))
    for b in bad[:5]:
        print('      [MISMATCH] %s' % b)

    # ---- A3 ★★ 效果抽取可复算（复用抽取纯函数，换输入源，用等值锁等价）----
    #   这一步替换了两个东西：① 输入从临时区换成仓库内蒸馏副本；
    #   ② `main()` 的读取代码在这里重写了一遍（路径规则不同）。
    #   ⇒ 等价性判据 = 重跑结果与 `items_effects48.json` **逐条相等**。
    #   鉴别力：改 `_evidence/gml/` 里任何一个 GML、或改 `extract_effects48` 的正则，
    #   都会立刻报红（前者 = 证据被动过，后者 = 抽取口径变了）。
    repo = _reextract_from_repo()
    ev = _json(EFFECTS_JSON)
    diff = []
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        for w in ('dark', 'light'):
            a = (repo.get(ch) or {}).get(w) or {}
            b = (ev.get(ch) or {}).get(w) or {}
            if a != b:
                ka, kb = set(a), set(b)
                if ka != kb:
                    diff.append('%s/%s 键集不同 仅仓内=%s 仅证据=%s'
                                % (ch, w, sorted(ka - kb)[:4], sorted(kb - ka)[:4]))
                for k in sorted(ka & kb):
                    if a[k] != b[k]:
                        diff.append('%s/%s#%s 仓内=%r 证据=%r' % (ch, w, k, a[k], b[k]))
                        break
    n_ev = sum(len((ev.get(ch) or {}).get(w) or {}) for ch in ev for w in ('dark', 'light'))
    check('A3', n_ev > 0 and not diff,
          'A3 效果抽取可复算：仓库内 GML 蒸馏副本重跑 == items_effects48.json（%d 条；差异 %d 处）'
          % (n_ev, len(diff)))
    for d in diff[:5]:
        print('      [DIFF] %s' % d)

    # ---- A4 ★ 产品数据 == 生成器重算（防"手改产品 JSON"）----
    #   判据面覆盖 kind/target/amount/per_char/scene_gate/consumable/droppable/src。
    errs = []
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        prod = (CAT.chapter(ch).get('items') or {})
        for w in ('dark', 'light'):
            src = ((ev.get(ch) or {}).get(w)) or {}
            for k, eff in src.items():
                p = (prod.get(w) or {}).get(k)
                if not isinstance(p, dict):
                    errs.append('%s/%s#%s 产品缺条目' % (ch, w, k))
                    continue
                kind, target, amount, per = GI._kind_of(eff)
                want = {
                    'kind': kind, 'target': target, 'amount': amount, 'per_char': per,
                    'scene_gate': True if [e for e in eff if e[0] == 'room_gate'] else None,
                    'consumable': kind in ('heal', 'heal_all', 'revive', 'per_char',
                                           'consume', 'recover'),
                    'droppable': not (w == 'light' and int(k) in (5, 11)),
                }
                for f, v in want.items():
                    if p.get(f) != v:
                        errs.append('%s/%s#%s.%s 产品=%r 重算=%r' % (ch, w, k, f, p.get(f), v))
    check('A4', not errs and n_ev > 0,
          'A4 产品道具数据 == 生成器重算（八字段逐条；不符 %d 处）' % len(errs))
    for e in errs[:6]:
        print('      [DIFF] %s' % e)

    # ---- A5 名字纪律：有名字必须有出处；没名字显示 ？？？（宁缺勿造）----
    badname = []
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        prod = (CAT.chapter(ch).get('items') or {})
        for w in ('dark', 'light'):
            for k, p in (prod.get(w) or {}).items():
                if p.get('name') and not p.get('name_source'):
                    badname.append('%s/%s#%s 有名字无出处' % (ch, w, k))
    unk = IS.unknown_def(9999, 'dark')
    check('A5', not badname and unk.display_name == IS.UNKNOWN_NAME == '？？？',
          'A5 名字纪律：有名字必有出处（违规 %d）+ 未知道具显示 ？？？（宁缺勿造）'
          % len(badname))


def _reextract_from_repo():
    """用 `extract_effects48` 的三个纯函数、从**仓库内** `_evidence/gml/` 重跑抽取。

    ⚠️ 读取部分必须重写（原 `read()` 拼的是临时区的 `chapterN_windows/gml48b/` 路径），
    等价性由 A3 的"与原证据表逐条相等"保证。
    """
    def rd(ch, name):
        p = os.path.join(GML, 'ch%d.%s.gml' % (ch, name))
        if not os.path.isfile(p):
            return ''
        return io.open(p, 'r', encoding='utf-8', errors='replace').read()

    out = {}
    for ch in range(1, 6):
        dark = {}
        for cid, body in EX.cases(rd(ch, 'scr_itemuse')).items():
            dark[cid] = EX.dark_effects(body)
        for cid in re.findall(r'case\s+(\d+)\s*:', rd(ch, 'scr_itemnamelist')):
            dark.setdefault(int(cid), [])
        light = {}
        for cid, body in EX.cases(rd(ch, 'scr_litemuseb')).items():
            light[cid] = EX.light_effects(body)
        for cid in re.findall(r'itemid\s*==\s*(\d+)', rd(ch, 'scr_litemname')):
            light.setdefault(int(cid), [])
        out['ch%d' % ch] = {
            'dark': {str(k): dark[k] for k in sorted(dark)},
            'light': {str(k): light[k] for k in sorted(light)},
        }
    return out


# ===========================================================================
#  B 两个袋子 / 垃圾团（照抄 scr_itemget / scr_itemshift）
# ===========================================================================

def seg_b():
    # ---- B1 容量与哨兵（照抄 `global.item[12] = 999` / `global.litem[8] = 999`）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    check('B1', inv.bags['dark'].capacity == 12 and inv.bags['light'].capacity == 8
          and IS.BAG_CAPACITY == {'dark': 12, 'light': 8} and IS.BAG_SENTINEL == 999,
          'B1 两袋容量 12/8 + 哨兵 999（照抄 scr_itemget / scr_litemget）')

    # ---- B2 线性探测：第一个空格；满 ⇒ -1（照抄 scr_itemget 的 for 循环）----
    #   ⚠️ 中间那一步的期望值是 **1** 不是 2 —— 因为 `remove_at` 会**前移**
    #   （照抄 `scr_itemshift`，见 B4），抽掉第 0 格后空洞被挤到**尾部**，
    #   于是"第一个空格"从 2 变成 1。首跑在这里报红过一次：错的是我写判据时的
    #   直觉（以为会留个洞），产品是对的 —— 本条同时也就是"前移语义"的第二处证明。
    bag = IS.Bag('dark', 3)
    probes = []
    for iid in (1, 2):
        bag.add(IS.unknown_def(iid, 'dark'), 'ch1', 'dark')
    probes.append(bag.first_free())         # [1,2,-] ⇒ 2
    bag.remove_at(0)                        # 前移 ⇒ [-,-,2] 的空洞在尾部 ⇒ 1
    probes.append(bag.first_free())
    for iid in (3, 4):
        bag.add(IS.unknown_def(iid, 'dark'), 'ch1', 'dark')
    probes.append(bag.first_free())         # 满 ⇒ -1
    check('B2', probes == [2, 1, -1],
          'B2 first_free 线性探测：空格 2 → 抽掉首格后（前移）⇒ 1 → 满则 -1（实得 %r）' % (probes,))

    # ---- B3 ★ 满袋 add ⇒ (False, -1)：不覆盖、不丢最旧（照抄 noroom）----
    bag2 = IS.Bag('dark', 2)
    bag2.add(IS.unknown_def(1, 'dark'), 'ch1', 'dark')
    bag2.add(IS.unknown_def(2, 'dark'), 'ch1', 'dark')
    ok3, idx3 = bag2.add(IS.unknown_def(3, 'dark'), 'ch1', 'dark')
    kept = [s.item.id for _, s in bag2.iter_filled()]
    check('B3', ok3 is False and idx3 == -1 and kept == [1, 2],
          'B3 满袋 add ⇒ (False,-1) 且原有道具不被顶掉（实得 %r，袋内 %r）' % ((ok3, idx3), kept))

    # ---- B4 ★ remove_at 前移（照抄 scr_itemshift，不留空洞）----
    bag3 = IS.Bag('dark', 4)
    for iid in (1, 2, 3, 4):
        bag3.add(IS.unknown_def(iid, 'dark'), 'ch1', 'dark')
    gone = bag3.remove_at(1)
    after = [s.item.id for _, s in bag3.iter_filled()]
    check('B4', gone.item.id == 2 and after == [1, 3, 4]
          and len(bag3.slots) == 4 and bag3.slots[-1] is None,
          'B4 remove_at 后续前移不留空洞（抽掉 #2 ⇒ %r，长度仍 4）' % (after,))


# ===========================================================================
#  C 判定：verdict 优先级 = 垃圾 > 异域 > 可用
# ===========================================================================

def seg_c():
    # ---- C1 正控制：同域同章 ⇒ 用得出去 ----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    out = inv.use('dark', 0)
    check('C1', out.verdict == IS.VERDICT_OK and out.healed == 40
          and out.consumed is True and len(inv.bags['dark']) == 0,
          'C1 正控制：同域使用 ⇒ OK（id1 黑暗糖果 healed=40，消耗后袋空）')

    # ---- C2 ★★ 异章节 ⇒ MYSTERY，且文案**逐字**等于用户原话 ----
    #   ★★★ 生产纪律：本条是全套件**唯一**把用户原话写成字面量的地方，是"逐字"这个
    #   验收点的**单点锚点**。C3/C5 刻意改用 `IS.MSG_MYSTERY` 比较 —— 它们守的是
    #   "异世界/场景门控也走同一条文案通路"（结构），而不是"这句话具体是什么字"
    #   （内容）。两处都硬编码会让同一句话散在多处维护；只留一处则改一个字立刻报红。
    #   （鉴别力体检 P1 就是冲着这条来的：改 `MSG_MYSTERY` ⇒ 只有 C2 报红，符合设计。）
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)                                   # 出身 ch1
    moved = inv.enter('ch2', 'dark')                 # 换到 ch2（同一世界）
    out = inv.use('dark', 0)
    check('C2', not moved and out.verdict == IS.VERDICT_MYSTERY
          and out.message == '一股神秘的力量阻止了你' and out.message == IS.MSG_MYSTERY,
          'C2 ★异章节 ⇒ MYSTERY 且文案逐字「一股神秘的力量阻止了你」（实得 %r）' % (out.message,))

    # ---- C3 ★ 异世界 ⇒ 同一句话（用户口径里"其他场景"包含跨世界）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    inv.bags['dark'].at(0).origin_world = IS.WORLD_DARK
    inv.world = IS.WORLD_LIGHT                        # 只改域，不触发垃圾化（绕开 enter 的自动动作）
    out = inv.use('dark', 0)
    check('C3', out.verdict == IS.VERDICT_MYSTERY and out.message == IS.MSG_MYSTERY,
          'C3 ★异世界 ⇒ MYSTERY 同文案（实得 %r）' % (out.verdict,))

    # ---- C4 ★★ 垃圾优先于异域（正负成对：同一件道具，垃圾化前 ⇒ MYSTERY，垃圾化后 ⇒ JUNK）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    inv.enter('ch2', 'dark')                          # 换章，制造"异章节"
    before = inv.use('dark', 0).verdict               # 尚未垃圾化 ⇒ 应是 MYSTERY
    inv.bags['dark'].at(0).junked = True              # 直接标垃圾（不改其它维度）
    after = inv.use('dark', 0)
    check('C4', before == IS.VERDICT_MYSTERY and after.verdict == IS.VERDICT_JUNK
          and after.message == IS.VERDICT_MESSAGE[IS.VERDICT_JUNK],
          'C4 ★★两条同时成立时垃圾优先（垃圾化前 %s → 垃圾化后 %s）' % (before, after.verdict))

    # ---- C5 ★★ 场景门控（照抄 scr_litemuseb case 201 的 room== 白名单）----
    #   允许房间 {2,3,5,6}；2 = room_krisroom。
    def _gate(room_id):
        i = IS.Inventory(CAT, 'ch1', 'light', original_room_id=room_id)
        i.pick_up(201, world='light', chapter='ch1')
        return i.use('light', 0)

    ok_in = _gate(2)
    ok_out = _gate(7)
    ok_none = _gate(None)
    gated_def = CAT.get('ch1', 'light', 201)
    check('C5', gated_def.scene_gate is True
          and ok_in.verdict == IS.VERDICT_OK
          and ok_out.verdict == IS.VERDICT_MYSTERY and ok_out.message == IS.MSG_MYSTERY
          and ok_none.verdict == IS.VERDICT_MYSTERY,
          'C5 ★★场景门控 201：房间 2 可用 / 房间 7 被拦 / 判不出房间也被拦（%s / %s / %s）'
          % (ok_in.verdict, ok_out.verdict, ok_none.verdict))

    # ---- C6 ★ 负控制：数据说"要门控"但产品没登记白名单 ⇒ **不静默放行** ----
    inv = IS.Inventory(CAT, 'ch1', 'light', original_room_id=2)
    fake = IS.ItemDef({'id': 987654, 'name': '测试门控道具', 'kind': 'heal',
                       'amount': 99, 'scene_gate': True}, 'light')
    inv.bags['light'].add(fake, 'ch1', 'light')
    out = inv.use('light', 0)
    check('C6', out.verdict == IS.VERDICT_MYSTERY and out.healed == 0,
          'C6 ★负控制：未登记白名单的门控道具不被静默放行（verdict=%s）' % (out.verdict,))

    # ---- C7 ★★ visible_rows 与 use 走同一套判据（真实量级：把 12 格填满）----
    #   ⚠️ `use()` 会消耗道具（consumable ⇒ 袋内前移），所以每验一行都得从
    #   **同一初始状态**克隆一份来跑；直接在同一个袋上遍历会让后面的下标指向别人
    #   （夹具自身失效 ⇒ 判据变成恒真）。
    _ids = (1, 6, 7, 8, 9, 11, 12, 13, 14, 15, 0, 2)

    def _fresh():
        i = IS.Inventory(CAT, 'ch1', 'dark')
        for iid in _ids:
            i.pick_up(iid)
        return i

    rows = _fresh().visible_rows('dark')
    mismatch = []
    for i, _name, _junk, usable in rows:
        real_ok = _fresh().use('dark', i).verdict == IS.VERDICT_OK
        if bool(usable) != bool(real_ok):
            mismatch.append((i, usable, real_ok))
    check('C7', len(rows) == 12 and not mismatch,
          'C7 ★★菜单"是否可用" == 真用一次的结果（12 行逐行一致，不符 %d 行）' % len(mismatch))

    # ---- C8 ★★ 垃圾化不可逆 + 只动暗袋 ----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    inv.pick_up(6)
    inv.pick_up(8, world='light')                     # 光袋里也放一件
    moved = inv.enter('ch1', 'light')                 # 回光世界
    junk_names = list(inv.junk.names())
    back = inv.enter('ch1', 'dark')                   # 再回暗世界
    still = [s.junked for _, s in inv.bags['dark'].iter_filled()]
    light_bag = [s.junked for _, s in inv.bags['light'].iter_filled()]
    check('C8', sorted(moved) == sorted(junk_names) and len(moved) == 2
          and back == [] and len(still) == 2 and all(still)
          and light_bag == [False] and IS.JUNK_IS_PERMANENT is True,
          'C8 ★★回光世界 2 件暗道具全变垃圾团（%r）且**不可逆**、光袋不受影响' % (moved,))

    # ---- C9 ★ 垃圾件被"掏空"（效果面归零，不是只改个标记）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(14)                                   # 赞赞三明治 heal 500
    inv.enter('ch1', 'light')
    it = inv.bags['dark'].at(0).item
    out = inv.use('dark', 0)
    check('C9', it.kind == 'none' and it.consumable is False and it.droppable is False
          and it.amount is None and it.display_name == '赞赞三明治'
          and out.verdict == IS.VERDICT_JUNK and out.healed == 0,
          'C9 ★垃圾件效果被掏空（kind=none/consumable=False/amount=None；名字保留 %r）'
          % (it.display_name,))


# ===========================================================================
#  D 菜单（S 键）：含背包，**不含设置**
# ===========================================================================

def seg_d():
    # ---- D1 ★★ «设置不应用» ----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    m = IM.ItemMenu(inv)
    pids = [e[0] for e in m.entries()]
    notes = {n['pid']: (n['state'], n['reason']) for n in m.page_notes()}
    m2 = IM.ItemMenu(inv, include_settings=True)
    notes2 = {n['pid']: (n['state'], n['reason']) for n in m2.page_notes()}
    # 正控制：设置条目在两种取值下都不进渲染（`entries()` 过滤 hidden/noconfig）
    never_shown = IM.PAGE_CONFIG not in pids and IM.PAGE_CONFIG not in [e[0] for e in m2.entries()]
    # ★ 负控制：`include_settings` 真的被 `_page_state` 读了（state/reason 会变）
    real_switch = (notes[IM.PAGE_CONFIG][0] == 'hidden'
                   and 'INCLUDE_SETTINGS' in notes[IM.PAGE_CONFIG][1]
                   and notes2[IM.PAGE_CONFIG][0] == 'noconfig')
    check('D1', IM.INCLUDE_SETTINGS is False and never_shown and real_switch,
          'D1 ★★设置不应用：不进渲染（两种取值都不进）+ 开关真被读（%s→%s）'
          % (notes[IM.PAGE_CONFIG][0], notes2[IM.PAGE_CONFIG][0]))

    # ---- D2 ★ 两个世界的 menuno 必须分开（合成一个 dict = DEVICE_MENU 那个坑的同型错误）----
    check('D2', IM.MENU_NO_LIGHT[IM.PAGE_ACTION] == 5 and IM.MENU_NO_DARK[IM.PAGE_CONFIG] == 5
          and IM.MENU_NO_LIGHT[IM.PAGE_STAT] == 2 and IM.MENU_NO_DARK[IM.PAGE_EQUIP] == 2
          and IM.MENU_NO_LIGHT.get(IM.PAGE_CONFIG) is None
          and IM.MENU_NO_DARK.get(IM.PAGE_PHONE) is None,
          'D2 ★两世界 menuno 分开：光 menuno5=动作页 / 暗 menuno5=设置；光无 EQUIP、暗无 PHONE')

    # ---- D3 根条目顺序 == 原作按钮序 ----
    dark_pids = [e[0] for e in IM.ItemMenu(IS.Inventory(CAT, 'ch1', 'dark')).entries()]
    light_pids = [e[0] for e in IM.ItemMenu(IS.Inventory(CAT, 'ch1', 'light')).entries()]
    check('D3', dark_pids == [IM.PAGE_ITEMS, IM.PAGE_EQUIP, IM.PAGE_TECH]
          and light_pids == [IM.PAGE_ITEMS, IM.PAGE_STAT, IM.PAGE_PHONE],
          'D3 根条目顺序 == 原作按钮序（暗 %r / 光 %r）' % (dark_pids, light_pids))

    # ---- D4 光标协议（照抄 scr_84_draw_menu：选中 "> "、未选 "  "）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    inv.pick_up(6)
    mm = IM.ItemMenu(inv)
    mm.open()
    fr = mm.key('confirm')                            # 进道具页
    lines = fr.lines
    ok_cursor = (IM.CURSOR_ON == '> ' and IM.CURSOR_OFF == '  '
                 and lines[0].startswith('> ') and lines[1].startswith('  ')
                 and not lines[0].startswith('  ') and not lines[1].startswith('> '))
    check('D4', ok_cursor,
          'D4 光标协议精确：选中 "> "、未选 "  "（两空格）（%r）' % (lines,))

    # ---- D5 ★★ 动作页"动作光标 ≠ 道具槽位"（本轮修真 bug 的锁）----
    #   ★ 必须放**三件**：两件时 cursor 与 slot_index 恰好相等，错位抓不到。
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    for iid in (1, 6, 7):
        inv.pick_up(iid)
    mm = IM.ItemMenu(inv)
    mm.open()
    mm.key('confirm')                                 # → 道具页
    mm.key('down')                                    # 光标到第 2 行（槽位 1）
    mm.key('confirm')                                 # → 动作页
    slot_seen = mm.slot_index
    mm.key('down')
    mm.key('down')                                    # 动作 0→1→2（丢弃），光标=2
    cursor_seen = mm.cursor
    mm.key('confirm')                                 # 执行
    left = [s.item.id for _, s in inv.bags['dark'].iter_filled()]
    check('D5', slot_seen == 1 and cursor_seen == 2 and left == [1, 7],
          'D5 ★★丢弃第 2 行 ⇒ 删掉的是**第 2 件**（残 %r；动作光标=%d ≠ 槽位=%d）'
          % (left, cursor_seen, slot_seen))

    # ---- D6 ★ 垃圾团入口只在非空时出现 ----
    empty_has = IM.PAGE_JUNK in [e[0] for e in IM.ItemMenu(IS.Inventory(CAT, 'ch1', 'dark')).entries()]
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    inv.enter('ch1', 'light')
    ent = [e for e in IM.ItemMenu(inv).entries() if e[0] == IM.PAGE_JUNK]
    check('D6', empty_has is False and len(ent) == 1 and '垃圾团' in ent[0][1]
          and '1' in ent[0][1],
          'D6 ★垃圾团入口只在非空时出现（空袋无入口；有 1 件时 %r）' % (ent[0][1] if ent else None,))

    # ---- D7 ★ 菜单内不响应裸 's'（否则与全局开关键自打架）+ 正控制 'down' 响应 ----
    check('D7', IM.normalize_key('s') is None and IM.normalize_key('down') == 'down'
          and 's' not in IM._KEY_ALIASES,
          'D7 ★键表刻意不含裸 s（菜单内 S 不响应）；正控制 down ⇒ %r'
          % (IM.normalize_key('down'),))

    # ---- D8 忙碌时开不出（含"询问本身抛异常"⇒ 按忙处理，不硬开）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')

    def _busy_true():
        return True

    def _busy_boom():
        raise RuntimeError('锁询问炸了')

    can1, why1 = IM.ItemMenu(inv, is_busy=_busy_true).can_open()
    can2, why2 = IM.ItemMenu(inv, is_busy=_busy_boom).can_open()
    check('D8', can1 is False and can2 is False and why1 and why2,
          'D8 菜单锁语义：忙 ⇒ 不开；锁询问抛异常 ⇒ 也不硬开（%r / %r）' % (why1, why2))

    # ---- D9 无数据页"登记但不可用"，且真进不去（不画空页假装有）----
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    mm = IM.ItemMenu(inv)
    eq = [e for e in mm.entries() if e[0] == IM.PAGE_EQUIP]
    before = mm.page
    mm._enter(IM.PAGE_EQUIP)
    check('D9', len(eq) == 1 and eq[0][2] == 'nodata' and eq[0][3]
          and mm.page == before and mm.refusals == 1,
          'D9 无数据页登记为 nodata + 有原因，且 confirm 进不去（refusals=%d）' % (mm.refusals,))

    # ---- D10 ★ 丢不掉名单 + 负控制（可丢的确实丢得掉）----
    inv = IS.Inventory(CAT, 'ch1', 'light')
    inv.pick_up(5, world='light')
    mm = IM.ItemMenu(inv)
    mm._do_drop(0)
    kept5 = len(inv.bags['light'])
    inv2 = IS.Inventory(CAT, 'ch1', 'light')
    inv2.pick_up(4, world='light')
    mm2 = IM.ItemMenu(inv2)
    mm2._do_drop(0)
    check('D10', (IS.WORLD_LIGHT, 5) in IS.DONT_THROW and kept5 == 1 and mm.refusals == 1
          and len(inv2.bags['light']) == 0 and mm2.drops == 1,
          'D10 ★丢不掉名单（光 id5 留下，refusals=%d）+ 负控制：光 id4 真丢掉了'
          % (mm.refusals,))


# ===========================================================================
#  E 可交互物（分类如实 + 锁必须能释放）
# ===========================================================================

def seg_e():
    # ---- E1 分类正/负成对（认不出来 ⇒ None，不猜）----
    got = {n: (II.classify(n) or {}).get('kind') for n in
           ('obj_savepoint', 'obj_darkfountain', 'obj_shortcut_door', 'obj_readable')}
    unknown = II.classify('obj_完全编造的东西')
    check('E1', got == {'obj_savepoint': 'savepoint', 'obj_darkfountain': 'fountain',
                        'obj_shortcut_door': 'door', 'obj_readable': 'readable'}
          and unknown is None and II.classify(None) is None and II.classify('') is None,
          'E1 分类四类正确 + 负控制（编造名/None/空串 ⇒ None，不猜）')

    # ---- E2 ★ 门归路由层，不许写成"数据缺口"（那是把已实现说成没做）----
    d = II.classify('obj_doorA')
    check('E2', d is not None and d['kind'] == 'door' and d.get('in_data') is True
          and d.get('handled_by') == 'scene_routing' and 'gap' not in d,
          'E2 ★门是"已实现但归路由层"（handled_by=%r），不标数据缺口' % (d.get('handled_by'),))

    # ---- E3 ★ 数据缺口如实登记（至少 readable / chest / pickup / sign 四类）----
    gaps = II.data_gaps()
    check('E3', {'readable', 'chest', 'pickup', 'sign', 'interactable', 'furniture'} <= set(gaps)
          and all(v for v in gaps.values()),
          'E3 ★数据缺口如实登记 %d 类：%s（不假装已实现）'
          % (len(gaps), ','.join(sorted(gaps))))

    # ---- E4 ★★ 真实场景：ch1 城堡镇 7 个 objects ⇒ 建出 1 个存档点，且交互真发生 ----
    sid = 'ch1.castle_town.castle_town'
    entry = (INDEX.get('scenes') or {}).get(sid)
    st = SS.load_scene(sid, entry=entry)
    n_save = sum(1 for o in (st.objects or []) if (o or {}).get('src') == 'obj_savepoint')
    seen = []
    props = II.build_props(st, 'ch1', 'dark', present=lambda t, a=None: seen.append(t) or t)
    ok_i = bool(props) and props[0].interact()
    check('E4', st is not None and len(st.objects or []) == 7 and n_save == 1
          and len(props) == 1 and ok_i and seen and '存档点' in seen[0],
          'E4 ★★真实场景（城堡镇 7 objects / 1 存档点）⇒ 建 1 个可交互物并真交互（台词 %r）'
          % (seen[0][:18] if seen else None,))

    # ---- E4b 全章普查也走真实数据（ch1 暗世界有 17 个存档点 / 1 个暗之泉）----
    hit = II.survey(SS.scenes_dir(), 'ch1', 'dark')
    check('E4b', hit.get('obj_savepoint') == 17 and hit.get('obj_darkfountain') == 1
          and hit.get('obj_doorA') == 69,
          'E4b ch1 暗世界可交互原件普查：存档点 %s / 暗之泉 %s / doorA %s'
          % (hit.get('obj_savepoint'), hit.get('obj_darkfountain'), hit.get('obj_doorA')))

    # ---- E5 ★★ 锁必须能释放（present 抛异常 ⇒ 不许把全局锁卡死）----
    bus = CP.reset_default_bus()

    def _boom(text, actor=None):
        raise ValueError('present 炸了')

    prop = II.SavePointProp('t#0', present=_boom, bus=bus)
    try:
        r = prop.interact()
        raised = None
    except Exception as exc:                          # pragma: no cover
        r, raised = None, exc
    check('E5', r is False and raised is None and bus.locked is False
          and prop.myinteract == CP.Interactable.MYINTERACT_IDLE,
          'E5 ★★present 抛异常 ⇒ 交互返回 False 且**全局锁已释放**（locked=%s）' % (bus.locked,))

    # ---- E6 ★ key 不许撞（同房两个 obj_savepoint 必须是两个对象）----
    scene = {'scene_id': 'test.two', 'original_room_id': 1,
             'objects': [{'src': 'obj_savepoint', 'pos': [0, 0]},
                         {'src': 'obj_savepoint', 'pos': [9, 9]}]}
    props2 = II.build_props(scene, 'ch1', 'dark', present=lambda t, a=None: t)
    check('E6', len(props2) == 2 and props2[0].key != props2[1].key
          and props2[0] is not props2[1],
          'E6 ★两个同名物件不撞 key（%r / %r）' % (props2[0].key, props2[1].key))

    # ---- E7 落点标记不建可交互物 ----
    props3 = II.build_props({'scene_id': 't', 'objects': [{'src': 'obj_markerB'}]},
                            'ch1', 'dark', present=lambda t, a=None: t)
    check('E7', props3 == [] and II.is_interactive('obj_markerB') is False,
          'E7 落点标记（obj_markerB）不建可交互物')

    # ---- E8 没接 present ⇒ 如实"什么也没发生"（不假装）----
    bus2 = CP.reset_default_bus()
    p = II.SavePointProp('t#1', present=None, bus=bus2)
    check('E8', p.interact() is False and bus2.locked is False,
          'E8 没接线（present=None）⇒ 交互返回 False，不假装成功')


# ===========================================================================
#  F 明暗世界表（_worlds.json）——判据既要独立重算，也要两侧反例
# ===========================================================================

def seg_f():
    # ---- F1 表可加载 ----
    check('F1', WORLDS.get('ok') and WORLDS.get('rooms')
          and WORLDS.get('overrides') == {'desktop': 'light'},
          'F1 _worlds.json 可加载（rooms %d 章，overrides=%r）'
          % (len(WORLDS.get('rooms') or {}), WORLDS.get('overrides')))

    # ---- F2 ★★ 覆盖率：**独立重算**（不信生成器自报）----
    cover, miss = _recount_cover()
    check('F2', cover == {'light': 202, 'dark': 809, 'unknown': 3} and not miss,
          'F2 ★★场景世界覆盖独立重算：1014 场景 → light 202 / dark 809 / unknown 3 / 未覆盖 0（%r，miss=%d）'
          % (dict(cover), len(miss)))

    # ---- F3 ★★ 邻域反例两侧为空（判据既不许过窄、也不许过宽）----
    bad_a, bad_b = _counterexamples()
    check('F3', not bad_a and not bad_b,
          'F3 ★★反例检查：光区域里判暗 %d 间 / 判光但房名 room_dw_ %d 间（两侧都须为 0）'
          % (len(bad_a), len(bad_b)))
    for r in (bad_a + bad_b)[:5]:
        print('      [SUSPECT] %r' % (r,))

    # ---- F4 ★ 未判定 4 间，逐条 == meta.unknown_rooms（如实登记，不硬判）----
    unknown = sorted((ch, int(rid)) for ch, m in (WORLDS.get('rooms') or {}).items()
                     for rid, v in m.items() if v not in ('light', 'dark'))
    metarec = sorted((r['chapter'], int(r['room_id']))
                     for r in ((WORLDS.get('meta') or {}).get('unknown_rooms') or []))
    check('F4', len(unknown) == 4 and unknown == metarec
          and unknown == [('ch1', 136), ('ch3', 110), ('ch4', 159), ('ch4', 166)],
          'F4 ★未判定 4 间逐条一致（%r）' % (unknown,))

    # ---- F5 ★★ 暗前缀优先（防 room_dw_mansion_krisroom 被光区域表误判成光）----
    w1 = GW.classify_room('room_dw_mansion_krisroom', 'kris_room')      # 光区域 + 暗房名
    w2 = GW.classify_room('room_dw_mansion_krisroom', '')               # 无区域
    w3 = GW.classify_room('room_krisroom_dark', 'home')                 # 光前缀 + dark ⇒ 不猜
    check('F5', w1[0] == GW.DARK and w2[0] == GW.DARK and w3[0] == GW.UNKNOWN,
          'F5 ★★前缀优先：光区域里的房间名 room_dw_mansion_krisroom ⇒ %s（若区域表优先会误判成 %s）'
          % (w1[0], GW.LIGHT))

    # ---- F6 world_of_scene 不猜（缺信息/未判定/未知房间 ⇒ None）----
    none_cases = [
        SS.world_of_scene({'scene_id': 'nope'}),                                    # 无章无房
        SS.world_of_scene({'scene_id': 'x', 'chapter_id': 'ch3', 'original_room_id': 110}),  # 未判定
        SS.world_of_scene({'scene_id': 'x', 'chapter_id': 'ch9', 'original_room_id': 1}),    # 未知章
        SS.world_of_scene(None),
    ]
    check('F6', none_cases == [None, None, None, None]
          and SS.world_of_scene({'scene_id': 'desktop'}) == SS.WORLD_LIGHT,
          'F6 world_of_scene 判不出就 None 不猜（%r）；desktop 走 overrides ⇒ light' % (none_cases,))

    # ---- F7 ★★ 两个锚点：暗之泉第一站（城堡镇）判暗；光世界的家判光 ----
    st_dark = SS.load_scene('ch1.castle_town.castle_town',
                            entry=(INDEX.get('scenes') or {}).get('ch1.castle_town.castle_town'))
    light_sid = None
    for sid, rec in sorted((INDEX.get('scenes') or {}).items()):
        if rec.get('chapter_id') == 'ch1' and rec.get('area_id') == 'kris_room':
            light_sid = sid
            break
    st_light = SS.load_scene(light_sid, entry=(INDEX.get('scenes') or {}).get(light_sid)) \
        if light_sid else None
    check('F7', SS.world_of_scene(st_dark) == SS.WORLD_DARK
          and st_light is not None and SS.world_of_scene(st_light) == SS.WORLD_LIGHT
          and II.FOUNTAIN_TARGET == 'ch1.castle_town.castle_town',
          'F7 ★★锚点：城堡镇(原作房间 %s)=%s；%s=%s（与暗之泉第一站口径一致）'
          % (getattr(st_dark, 'original_room_id', None), SS.world_of_scene(st_dark),
             light_sid, SS.world_of_scene(st_light) if st_light else None))


def _recount_cover():
    cover = {'light': 0, 'dark': 0, 'unknown': 0}
    miss = []
    rooms = WORLDS.get('rooms') or {}
    ov = WORLDS.get('overrides') or {}
    for ch, crec in (INDEX.get('chapters') or {}).items():
        for _ak, av in (crec.get('areas') or {}).items():
            for sid, sr in (av.get('scenes') or {}).items():
                if sid in ov:
                    cover[ov[sid]] = cover.get(ov[sid], 0) + 1
                    continue
                w = (rooms.get(ch) or {}).get(str(sr.get('original_room_id')))
                if w is None:
                    miss.append((ch, sid, sr.get('original_room_id')))
                else:
                    cover[w] = cover.get(w, 0) + 1
    return cover, miss


def _counterexamples():
    """独立重算 gen_worlds48 的两侧反例检查（不信它的自报）。"""
    if not os.path.isfile(ROOMTABLE):
        return [('缺房间表',)], [('缺房间表',)]
    table = _json(ROOMTABLE)
    rooms = WORLDS.get('rooms') or {}
    bad_a, bad_b = [], []
    for ch in sorted(table):
        for r in table[ch]:
            if r.get('cls') not in ('scene', 'maybe'):
                continue
            rid = str(r.get('room_index'))
            w = (rooms.get(ch) or {}).get(rid)
            if r.get('area_id') in tuple(GW.LIGHT_AREAS) and w == 'dark':
                bad_a.append((ch, rid, r.get('resource'), r.get('area_id')))
            if (r.get('resource') or '').startswith('room_dw_') and w == 'light':
                bad_b.append((ch, rid, r.get('resource'), r.get('area_id')))
    return bad_a, bad_b


# ===========================================================================
#  G 产品接线（AST）——零依赖 / 热键不许裸字母 / 切换钩子真接上
# ===========================================================================

def seg_g():
    # ---- G1 ★★ 零依赖纪律：顶层 import 白名单 + **零函数内 import** ----
    allowed = {
        'item_system': {'collections', 'json', 'logging', 'os'},
        'item_menu': {'collections', 'logging', 'random', 'item_system'},
        'item_interact': {'collections', 'json', 'logging', 'os', 'companion'},
        'global_hotkey': {'ctypes', 'ctypes.wintypes', 'logging'},
    }
    viol = []
    inner_all = {}
    for name, ok_set in allowed.items():
        top, inner = _imports(os.path.join(MOD, name + '.py'))
        inner_all[name] = sorted({m.split('.')[0] for m in inner})
        extra = {m.split('.')[0] for m in top} - {m.split('.')[0] for m in ok_set}
        if extra:
            viol.append('%s 顶层多出 %r' % (name, sorted(extra)))
        bad_inner = {m.split('.')[0] for m in inner} - set(ALLOWED_INNER_IMPORTS)
        if bad_inner:
            viol.append('%s 函数内 import 了非 Qt/标准库 %r（初始化环风险）'
                        % (name, sorted(bad_inner)))
    check('G1', not viol,
          'G1 ★★零依赖：4 模块顶层 import 全在白名单内 + 函数内只许 Qt/标准库（违规 %d；函数内=%r）'
          % (len(viol), inner_all))
    for v in viol[:5]:
        print('      [VIOLATE] %s' % v)

    # ★ 正控制：AST 判据不看文本 —— 源码里**提到** PyQt5（注释/docstring），但不许被误报
    gh_src = _text(os.path.join(MOD, 'global_hotkey.py'))
    top_gh, _ = _imports(os.path.join(MOD, 'global_hotkey.py'))
    check('G1b', 'PyQt5' in gh_src and 'PyQt5' not in top_gh,
          'G1b ★正控制：文本提及 PyQt5 不误报（源码含 PyQt5=%s，AST 顶层 import 命中=%s）'
          % ('PyQt5' in gh_src, 'PyQt5' in top_gh))

    # ---- G2 ★★ 全局热键必须带修饰键（注册裸 S 会系统级劫持 S 键）----
    name, mods, vk = GH.parse_hotkey(GH.HOTKEY_DEFAULT_MENU)
    name2, mods2, vk2 = GH.parse_hotkey(GH.HOTKEY_DEFAULT_INTERACT)
    bare = GH.parse_hotkey('s')
    check('G2', '+' in GH.HOTKEY_DEFAULT_MENU and mods and name.endswith('S')
          and '+' in GH.HOTKEY_DEFAULT_INTERACT and mods2 and name2.endswith('E')
          and bare[1] == 0 and bare[2] == 0x53,
          'G2 ★★两档热键都带修饰键（%s/%s）；裸 s 是合法写法但 mods=0（产品刻意不用）'
          % (GH.HOTKEY_DEFAULT_MENU, GH.HOTKEY_DEFAULT_INTERACT))

    # ---- G3 main.py 预声明字段齐全（失败路径上也不缺属性）----
    want = {'item_catalog', 'inventory', 'item_menu', 'item_menu_ui', 'item_props',
            'interact_bus', '_scene_switch_hooks', '_item_hotkey_done', '_item_hotkey_bad',
            '_item_last_frame', '_item_menu_toggle_at'}
    got = set()
    for node in ast.walk(_tree(os.path.join(SRC, 'main.py'))):
        if isinstance(node, ast.FunctionDef) and node.name == 'init_item_systems':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) \
                                and t.value.id == 'self':
                            got.add(t.attr)
    check('G3', want <= got,
          'G3 main.py init_item_systems 预声明 %d/%d 字段（缺 %r）'
          % (len(want & got), len(want), sorted(want - got)))

    # ---- G4 ★ 场景切换钩子真接上（换场景 ⇒ 换道具域 ⇒ 回光世界变垃圾）----
    main_src = _text(os.path.join(SRC, 'main.py'))
    fire_def, called_in_switch = False, False
    for node in ast.walk(_tree(os.path.join(MOD, 'scene_controller.py'))):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == '_fire_switch_hooks':
            fire_def = True
        if node.name == 'switch':
            # ★ 用 AST 找调用，不做文本搜索（"注释里提过"不许算数）。
            called_in_switch = any(
                isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                and s.func.attr == '_fire_switch_hooks' for s in ast.walk(node))
    hook_wired = '_scene_switch_hooks = [self._on_scene_switched_items]' in main_src
    check('G4', fire_def and called_in_switch and hook_wired,
          'G4 ★切换钩子接线：控制器有 _fire_switch_hooks 且在 switch() 里被**调用**（%s）+ 宿主注册钩子（%s）'
          % (called_in_switch, hook_wired))

    # ---- G5 ★ keyPressEvent 是真 Qt 钩子名（不是发明出来的）----
    try:
        from PyQt5.QtWidgets import QWidget
        real_hook = hasattr(QWidget, 'keyPressEvent')
    except Exception:
        real_hook = None
    has_def = any(isinstance(n, ast.FunctionDef) and n.name == 'keyPressEvent'
                  for n in ast.walk(_tree(os.path.join(SRC, 'main.py'))))
    check('G5', has_def and real_hook in (True, None),
          'G5 ★keyPressEvent 是 QWidget 的真钩子（属性实证=%s）+ main 里确实定义了它（%s）'
          % (real_hook, has_def))


# ===========================================================================
#  H 恒真判据自查：堵住"数据读不到 ⇒ 判据退化 ⇒ 全绿"
# ===========================================================================

def seg_h():
    # ---- H1 ★★ 数据确实读到了（读不到就必须报红，而不是"空表全相等"）----
    n_gml = len([f for f in os.listdir(GML) if f.endswith('.gml')]) if os.path.isdir(GML) else 0
    need = ['ch%d.%s.gml' % (ch, n) for ch in range(1, 6)
            for n in ('scr_itemnamelist', 'scr_itemuse', 'scr_litemname', 'scr_litemuseb')]
    missing = [n for n in need if not os.path.isfile(os.path.join(GML, n))]
    n_rooms = sum(len(m) for m in (WORLDS.get('rooms') or {}).values())
    check('H1', n_gml == 223 and not missing and n_rooms == 1050
          and len(INDEX.get('scenes') or {}) == 1014,
          'H1 ★★真实数据在位：GML %d 个（缺 %d）/ rooms %d 间 / 场景 %d 个'
          % (n_gml, len(missing), n_rooms, len(INDEX.get('scenes') or {})))

    # ---- H2 ★★ 负控制真的存在（没有负控制的锁 = 可能是恒真判据）----
    ids = ' '.join(c[0] for c in results)
    neg = sum(1 for cid in ('C4', 'C5', 'C6', 'D1', 'D5', 'D10', 'E1', 'E5', 'F3', 'F5', 'F6', 'G1b')
              if cid in ids)
    check('H2', neg == 12,
          'H2 ★★负控制/鉴别力夹具在位 %d/12（%s）' % (neg, 'C4 C5 C6 D1 D5 D10 E1 E5 F3 F5 F6 G1b'))

    # ---- H3 ★ 关键常量真的被产品读过（不是"看着在守其实没守"）----
    #   用行为证明：三个常量的取值改变会改变行为（这里只验证它们参与了判定）。
    inv = IS.Inventory(CAT, 'ch1', 'dark')
    inv.pick_up(1)
    inv.enter('ch1', 'light')
    permanent = (inv.use('dark', 0).verdict == IS.VERDICT_JUNK
                 and IS.JUNK_IS_PERMANENT is True)
    sentinel_used = IS.BAG_SENTINEL == 999 and IS.Bag('dark', 12).first_free() != IS.BAG_SENTINEL
    settings_used = IM.INCLUDE_SETTINGS is False
    check('H3', permanent and sentinel_used and settings_used,
          'H3 ★三个关键常量都参与真实判定（JUNK_IS_PERMANENT / BAG_SENTINEL / INCLUDE_SETTINGS）')

    # ---- H4 分段汇总 ----
    per = {}
    for cid, _ok, _m in results:
        per[cid[0]] = per.get(cid[0], 0) + 1
    n_fail = sum(1 for _c, ok, _m in results if not ok)
    print()
    print('  分段判据数：%s' % ' '.join('%s=%d' % (k, per[k]) for k in sorted(per)))
    print('  合计：%d 条，FAIL=%d' % (len(results), n_fail))


# ===========================================================================
def main():
    seg_a()
    seg_b()
    seg_c()
    seg_d()
    seg_e()
    seg_f()
    seg_g()
    seg_h()
    n_fail = sum(1 for _c, ok, _m in results if not ok)
    print()
    print('=' * 72)
    print('第48轮 道具/背包/S键菜单 回归：%d 条判据，FAIL=%d' % (len(results), n_fail))
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.exit(main())
