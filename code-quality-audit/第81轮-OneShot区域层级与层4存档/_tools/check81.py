# -*- coding: utf-8 -*-
u"""第81轮回归锁：**OneShot 区域层级（6 区）** + **层4 存档**不许静默漂移。

用户裁决（逐字）
----------------
> **「按照我之前的决策和你的建议来就好」**
> 区域口径 → **「5 区（推荐）」**
> 层4 落盘范围 → **「全量：计划+驻留+last_sleep（推荐）」**

守什么
------
* **A ★★★ OneShot 6 区完整性**：263 间**全覆盖**、两两零交集、逐区计数 == 官方事实源
  （`map_colors` / `zone_names` / `minimap_nodes` 三源互证的勘查产物 `oneshot_zones81.json`）。
* **B ★★ 分片真在位**：6 个 `_zone.oneshot.<area>.json` 全在盘，旧的单区域分片已退场。
* **C ★★ 真装载**：走产品唯一入口 `load_index()` + `load_scene(sid, entry=)`，
  每个区域**都**挑样本真装载（"数据写对了 ≠ 产品读得到"）。
* **D ★★★ 层4 存档**：`npc_plan_store` 零依赖 · `Book` 往返等价（驻留表 + 规划 + last_sleep）
  · main 侧四处接线（建书 / `plan_of`+`note` / `last_sleep_of`+`note_sleep` / 落盘）。
* **E ★★ 量桌宠口径**：`last_sleep` 降权**真生效**（方向对：被降权的那处更少被选）。
* **F 三处 WIRING 诚实**：`wired=True` 且 `not_yet` 清空（不留谎）。
* **G 判据自身体检**：标记打印点计数 + 负控制 · 记账守恒 + 漏记负控制 · 被测文件在盘。

★ 零网络 / 零 UI / 零外部盘（官方源盘的 .tmx 复核只在 B 段，缺了 SKIP 不假红）。
★ 判据名/明细里**不许**出现 `[PASS]` / `[FAIL]` 字面量（会污染 `run_all.count_results()`）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
R81 = os.path.join(ROOT, 'code-quality-audit', '第81轮-OneShot区域层级与层4存档')
ZONES81 = os.path.join(R81, '_evidence', 'oneshot_zones81.json')
BAK_ROOMS = os.path.join(R81, '_evidence',
                         '_zone.oneshot.rooms.before81.json')

#: 官方 5 区（4 个 minimap 区 + 1 个"主线/未列"）+ 1 个未分区汇总。
#  ★ 键 = 官方英文 zone key（`oneshot_minimap_nodes.json` / `map_colors.json` 的 name）。
#  ★ `UNZONED` 是**汇总键**（不在官方源里）—— 收纳"官方三源都没提到"的 22 间。
EXPECT_AREAS = ['barrens', 'glen', 'refuge', 'refuge_ground', 'mainline', 'unzoned']
EXPECT_OFFICIAL = {'Blue': 35, 'Green': 55, 'Red': 73, 'RedGround': 9, 'Purple': 69}

PASS = 0
FAIL = 0
FAILED = []
CALLS = 0


def check(name, cond, detail=''):
    global PASS, FAIL, CALLS
    CALLS += 1
    if cond:
        PASS += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s    %s' % (name, detail))


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def load(p):
    return json.loads(read(p))


# ================================================================ 数据就位
print('=' * 74)
print('第81轮：OneShot 区域层级（6 区） + 层4 存档')
print('=' * 74)

idx = load(os.path.join(SCENES, '_index.json'))
worlds = load(os.path.join(SCENES, '_worlds.json'))

# ================================================================ A 6 区完整性
print()
print('=' * 74)
print('A OneShot 6 区完整性（官方三源互证的勘查产物为准）')
print('=' * 74)

z_exists = os.path.exists(ZONES81)
check('A1 勘查产物在位（oneshot_zones81.json）', z_exists, ZONES81)

z = load(ZONES81) if z_exists else {}
z_counts = z.get('counts') or {}
z_members = z.get('members') or {}

check('A2 勘查产物覆盖 263/263（covered_total == expected_total）',
      z.get('covered_total') == z.get('expected_total') == 263,
      'covered=%s expected=%s' % (z.get('covered_total'), z.get('expected_total')))

check('A3 ★★ 勘查产物零交集（overlaps 为空）',
      (z.get('overlaps') or []) == [], 'overlaps=%s' % (z.get('overlaps') or [])[:3])

# ★ 逐区计数：勘查产物里的官方 4 区 + mainline(紫) 必须逐值对上
count_bad = {k: (z_counts.get(k), v) for k, v in EXPECT_OFFICIAL.items()
             if z_counts.get(k) != v}
check('A4 ★★★ 逐区计数 == 官方事实源（Blue35/Green55/Red73/RedGround9/Purple69）',
      not count_bad, '不符=%s' % (count_bad or '无'))

# ★ 产品索引里 oneshot 章的 areas 键集 == 期望 6 区
ch = (idx.get('chapters') or {}).get('oneshot') or {}
prod_areas = sorted((ch.get('areas') or {}).keys())
check('A5 ★★ 产品索引 oneshot 章恰有 6 个区域',
      prod_areas == sorted(EXPECT_AREAS),
      'areas=%s' % prod_areas)


def _all_scenes_of(chapter):
    out = {}
    for _aid, _a in ((chapter or {}).get('areas') or {}).items():
        for sid, ent in ((_a or {}).get('scenes') or {}).items():
            out[sid] = ent
    return out


idx_scenes = _all_scenes_of(ch)
check('A6 产品索引 oneshot 场景数 == 263（跨 6 区求和）',
      len(idx_scenes) == 263, 'n=%d' % len(idx_scenes))

# ★★ 逐区计数 == 勘查产物逐区计数（索引侧，不是勘查侧）
area_n = {a: len(((ch.get('areas') or {}).get(a) or {}).get('scenes') or {})
          for a in prod_areas}
# 索引侧 slug -> 官方 key 的映射（用于比对）
_SLUG2KEY = {'barrens': 'Blue', 'glen': 'Green', 'refuge': 'Red',
             'refuge_ground': 'RedGround', 'mainline': 'Purple'}
mism = {}
for slug, key in _SLUG2KEY.items():
    if area_n.get(slug) != EXPECT_OFFICIAL.get(key):
        mism[slug] = (area_n.get(slug), EXPECT_OFFICIAL.get(key))
check('A7 ★★★ 索引逐区计数 == 官方事实源（两处派生自同一事实）',
      not mism, '不符=%s；索引实得=%s' % (mism or '无', area_n))

# ★ 总和守恒：6 区之和 == 263
check('A8 ★ 6 区计数之和 == 263（无漏无重）',
      sum(area_n.values()) == 263, 'sum=%d %s' % (sum(area_n.values()), area_n))

# ★★ scene_id 前缀真带区域（`oneshot.<area>.`）—— 否则分片改了前缀没改
pref_bad = []
for a in prod_areas:
    for sid in ((ch.get('areas') or {}).get(a) or {}).get('scenes') or {}:
        if not sid.startswith('oneshot.%s.' % a):
            pref_bad.append(sid)
check('A9 ★★ 每条 scene_id 前缀 == 它所在区域（`oneshot.<area>.`）',
      not pref_bad, '不符=%s' % (pref_bad[:5] or '无'))

# ★ 未分区那群名字自带证据（抽查 3 个）
unz = set(((ch.get('areas') or {}).get('unzoned') or {}).get('scenes') or {})
unz_names = {idx_scenes[s].get('name') for s in unz if s in idx_scenes}
evid = [n for n in unz_names if isinstance(n, str)
        and ('IGNORE' in n.upper() or 'UNUSED' in n.upper()
             or 'demo' in n or n.startswith('C') and n[1:].isdigit())]
check('A10 ★ 未分区 22 间的名字自带证据（IGNORE/UNUSED/demo/Cn…）',
      len(evid) >= 6 and area_n.get('unzoned') == 22,
      'unzoned=%s 证据样本=%s' % (area_n.get('unzoned'), sorted(evid)[:6]))

# ================================================================ B 分片真在位
print()
print('=' * 74)
print('B 分片真在位（6 新分片在 · 旧单区域分片已退场）')
print('=' * 74)

zone_files = sorted(f for f in os.listdir(SCENES)
                    if f.startswith('_zone.oneshot.') and f.endswith('.json'))
expect_files = sorted('_zone.oneshot.%s.json' % a for a in EXPECT_AREAS)
check('B1 ★★ 6 个区域分片全在盘（文件逐个点名）',
      zone_files == expect_files, '实得=%s' % zone_files)

check('B2 ★★ 旧的单区域分片 `_zone.oneshot.rooms.json` 已退场（不共存）',
      not os.path.exists(os.path.join(SCENES, '_zone.oneshot.rooms.json')),
      '')
check('B3 旧分片**已备份**（迁移可回溯）',
      os.path.exists(BAK_ROOMS), BAK_ROOMS)

# ================================================================ C 真装载
print()
print('=' * 74)
print('C 真装载（走产品唯一入口，不是自己读 JSON）')
print('=' * 74)

sys.path.insert(0, PET)
import modules.scene_system as SS  # noqa: E402

idx_loaded = SS.load_index(SCENES)
check('C1 产品索引加载器 `load_index()` ok=True',
      idx_loaded.get('ok') is True, 'err=%s' % idx_loaded.get('error'))

flat = idx_loaded.get('scenes') or {}
flat_os = {k: v for k, v in flat.items() if k.startswith('oneshot.')}
check('C2 ★ `load_index()` 展平表里恰有 263 个 oneshot 场景',
      len(flat_os) == 263, 'n=%d' % len(flat_os))

# ★★★ 逐间真装载（全部 263，不是抽样）
n_ok, errs = 0, []
for sid in sorted(idx_scenes):
    try:
        got = SS.load_scene(sid, entry=flat.get(sid))
        if got is not None and getattr(got, 'name', None):
            n_ok += 1
    except Exception as e:
        errs.append((sid, str(e)))
check('C3 ★★★ 263 个 scene_id 逐个喂 `load_scene(entry=)`，全部真装载',
      n_ok == 263 and not errs, 'ok=%d 抛=%d %s' % (n_ok, len(errs), errs[:2]))

# ★ 每个区域**都**挑样本真装载（防"某区整块读不到"）
per_area_bad = []
for a in prod_areas:
    sids = sorted(((ch.get('areas') or {}).get(a) or {}).get('scenes') or {})
    if not sids:
        per_area_bad.append((a, 'empty'))
        continue
    sid = sids[0]
    got = SS.load_scene(sid, entry=flat.get(sid))
    if got is None or not getattr(got, 'name', None):
        per_area_bad.append((a, sid))
check('C4 ★★ 6 个区域**各**挑一条真装载（防"某区整块丢"）',
      not per_area_bad, '坏=%s' % (per_area_bad or '无'))

# ★ 负控制：编造 scene_id 装载不到
fake = SS.load_scene('oneshot.__nope__.__nope__', entry=None)
check('C5 ★ 负控制：编造 scene_id 装载不到（证明 C3/C4 非恒真）',
      fake is None, '')

# ================================================================ D 层4 存档
print()
print('=' * 74)
print('D 层4 存档（Plan/Intent/RoamState 落 data_store）')
print('=' * 74)

STORE = os.path.join(PET, 'modules', 'npc_plan_store.py')
MAIN = os.path.join(PET, 'src', 'main.py')
ROAM_PY = os.path.join(PET, 'modules', 'npc_roam.py')
INTENT_PY = os.path.join(PET, 'modules', 'npc_intent.py')
store_src = read(STORE)
main_src = read(MAIN)
stree = ast.parse(store_src)
mtree = ast.parse(main_src)

# D1 ★★ 零依赖纪律：顶层 import ⊆ 标准库白名单
_ALLOWED_TOP = {'collections', 'importlib', 'json', 'os', 'io', 'math', 'time',
                'random', 'logging', 're'}
top_imports = set()
inner_imports = []
for node in stree.body:
    if isinstance(node, ast.Import):
        for a in node.names:
            top_imports.add(a.name.split('.')[0])
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            top_imports.add(node.module.split('.')[0])
# ★★ 零函数内 import（`check56` A3 同规：不区分标准库/项目，一律禁）
for node in ast.walk(stree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for sub in ast.walk(node):
            if sub is node:
                continue
            if isinstance(sub, (ast.Import, ast.ImportFrom)):
                inner_imports.append(getattr(node, 'name', '?'))
top_bad = sorted(top_imports - _ALLOWED_TOP)
check('D1 ★★ `npc_plan_store` 顶层只 import 标准库白名单',
      not top_bad, '越界=%s 实得=%s' % (top_bad, sorted(top_imports)))
check('D2 ★★★ 零函数内 import（`check56` A3 同规）',
      not inner_imports, '函数内 import=%s' % (inner_imports[:5] or '无'))

# ★ 零项目内 import（不经 importlib 静态 import）
proj_imp = [n for n in ast.walk(stree)
            if isinstance(n, ast.ImportFrom) and n.module
            and n.module.split('.')[0].startswith('modules')]
check('D3 ★ `npc_plan_store` 不静态 import 任何项目内模块（软依赖走 importlib）',
      not proj_imp, '')

# D4 Book 往返等价（真 import 真跑）
sys.path.insert(0, os.path.join(PET, 'modules'))
import modules.npc_plan_store as NPS  # noqa: E402
import modules.npc_roam as NR        # noqa: E402
import modules.npc_intent as NI      # noqa: E402

roam = NR.RoamState(enabled=True)
roam.put('susie', 'ch1.town.town_church', now=100.0, dwell=600.0, reason='w')
book = NPS.Book(roam=roam)
book.plan_of('susie').note(NI.Intent('go_scene', 'ch1.town.town_church'))
book.note_sleep('susie', 'ch1.kris_room.kris_room')

d = book.to_dict()
book2 = NPS.Book.from_dict(d)
check('D4 ★★ `Book` 往返：schema_version 保留',
      d.get('schema_version') == NPS.SCHEMA_VERSION, 'v=%s' % d.get('schema_version'))
check('D5 ★★★ `Book` 往返：驻留表被还原（roam 不是 None）',
      book2.roam is not None and
      book2.roam.resident_of('susie') == 'ch1.town.town_church',
      'roam=%r' % (book2.roam.resident_of('susie') if book2.roam else None,))
check('D6 ★★★ `Book` 往返：**昨晚睡哪** 被还原（层4 的核心）',
      book2.last_sleep_of('susie') == 'ch1.kris_room.kris_room',
      'last_sleep=%r' % (book2.last_sleep_of('susie'),))
check('D7 ★★ `Book` 往返：上一次意图被还原（`decide(last=...)` 吃的）',
      getattr(book2.plan_of('susie').intent, 'what', None) == 'go_scene',
      'what=%r' % (getattr(book2.plan_of('susie').intent, 'what', None),))

# D8 容错：坏输入 ⇒ 空书（不抛）
check('D8 ★ 容错：版本不符 / 坏结构 ⇒ 空书（不抛）',
      NPS.Book.from_dict({'schema_version': 9}).ids() == []
      and NPS.Book.from_dict('not a dict').ids() == []
      and NPS.Book.from_dict(None).ids() == [],
      '')

# D9 ★ main 侧四处接线（AST）
cls = None
for n in mtree.body:
    if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet':
        cls = n
        break


def _methods(klass, name):
    return [n for n in ast.walk(klass)
            if isinstance(n, ast.FunctionDef) and n.name == name] if klass else []


def _calls_of(fn):
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


ini = _methods(cls, 'init_npc_systems')
ini_src = ast.get_source_segment(main_src, ini[0]) if ini else ''
check('D9 ★ main `init_npc_systems` 真建书并读回（`load()` + 预声明 `Book()`）',
      'npc_plan_store_mod.load' in ini_src
      and 'npc_plan_store_mod.Book()' in ini_src,
      '')

dec_m = _methods(cls, '_npc_roam_decide')
dec_calls = _calls_of(dec_m[0]) if dec_m else set()
check('D10 ★★★ main `_npc_roam_decide` 真用 `plan_of()` + `note()`（层4 读+写）',
      'plan_of' in dec_calls and 'note' in dec_calls,
      'calls=%s' % sorted(c for c in dec_calls if c in ('plan_of', 'note')))


def _kw_value_is_none(fn, kw):
    seen = False
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            for k in n.keywords:
                if k.arg == kw:
                    seen = True
                    if not (isinstance(k.value, ast.Constant)
                            and k.value.value is None):
                        return False
    return seen


check('D11 ★★★ `_npc_roam_decide` 的 `last=` **不再恒为 None**（层4 之前是硬编码）',
      not _kw_value_is_none(dec_m[0] if dec_m else ast.Pass(), 'last'),
      '')

slp_m = _methods(cls, '_npc_roam_sleep')
slp_calls = _calls_of(slp_m[0]) if slp_m else set()
check('D12 ★★★ main `_npc_roam_sleep` 真用 `last_sleep_of()` + `note_sleep()`',
      'last_sleep_of' in slp_calls and 'note_sleep' in slp_calls,
      'calls=%s' % sorted(c for c in slp_calls
                          if c in ('last_sleep_of', 'note_sleep')))

ps_m = _methods(cls, '_npc_plan_save')
check('D13 ★★ main `_npc_plan_save` 在位且真调 `npc_plan_store_mod.save()`',
      bool(ps_m) and 'save' in _calls_of(ps_m[0]),
      '')

pf_m = _methods(cls, '_npc_plan_file')
check('D14 ★★ main `_npc_plan_file` 真走 `data_store.app_file()`（唯一入口）',
      bool(pf_m) and 'app_file' in _calls_of(pf_m[0]), '')

tick_m = _methods(cls, '_npc_roam_tick')
check('D15 ★★★ main `_npc_roam_tick` 真调 `_npc_plan_save()`（世界变了就落盘）',
      bool(tick_m) and '_npc_plan_save' in _calls_of(tick_m[0]), '')

check('D16 ★ 退出收尾有 `_npc_plan_save(force=True)` 兜底',
      '_npc_plan_save(force=True)' in main_src, '')

# D17 ★ 文件名同源（main.NPC_LIFE_FILE == npc_plan_store.FILENAME）
check('D17 ★ `main.NPC_LIFE_FILE` == `npc_plan_store.FILENAME`（两处一词，不许打错）',
      "NPC_LIFE_FILE = 'npc_life.json'" in main_src
      and NPS.FILENAME == 'npc_life.json',
      'FILENAME=%s' % NPS.FILENAME)

# ================================================================ E 降权真生效
print()
print('=' * 74)
print('E 层4 闭环：`last_sleep` 降权真生效（方向对）')
print('=' * 74)

# ★★★ "函数写对了 ≠ 产品用上了" —— 断的是产品路径上的**效果**。
# ★ 夹具关键：**家**与**朋友家**必须是两个**不同**的地点。
HOME = 'ch1.kris_room.kris_room'
FRIEND_HOME = 'ch1.town.town_home'
hits = {}
for tag, ls in (('none', None), ('friend', FRIEND_HOME)):
    n = 0
    for day in range(400):
        s, _why = NI.choose_sleep_scene(
            'susie', 1000.0 + day * 86400, home=HOME,
            friends=[('lancer', 1.0, FRIEND_HOME)],
            reachable=[HOME, FRIEND_HOME], last_sleep=ls)
        if s == HOME:
            n += 1
    hits[tag] = n
# ★ 方向：`last_sleep=FRIEND_HOME` ⇒ 被削的是**朋友家** ⇒ **自己家**应当更常被选。
check('E1 ★★★ 连睡降权**真生效**（昨睡朋友家 ⇒ 自己家更常被选）',
      hits['none'] < hits['friend'],
      '无记忆选自己家 %d 次 / 昨睡朋友家后 %d 次' % (hits['none'], hits['friend']))

# E2 负控制：两处**同值**时（家 == 朋友家）降权无可比较 ⇒ 两次必相等
same = []
for ls in (None, HOME):
    n = 0
    for day in range(400):
        s, _ = NI.choose_sleep_scene(
            'susie', 1000.0 + day * 86400, home=HOME,
            friends=[('lancer', 1.0, HOME)],
            reachable=[HOME], last_sleep=ls)
        if s == HOME:
            n += 1
    same.append(n)
check('E2 ★ 负控制：只有一个地点时降权无可比较（两次皆 400/400）',
      same == [400, 400], '实得=%s' % same)

# ================================================================ F 三处 WIRING
print()
print('=' * 74)
print('F 三处 WIRING 诚实（不许留谎）')
print('=' * 74)

import modules.npc_roam as _NR2   # noqa: E402
import modules.npc_intent as _NI2  # noqa: E402
check('F1 ★ `npc_plan_store.WIRING` wired=True', NPS.WIRING.get('wired') is True,
      '')
check('F2 ★★ `npc_plan_store.WIRING.not_yet` 已清空', NPS.WIRING.get('not_yet') == [],
      'not_yet=%s' % (NPS.WIRING.get('not_yet'),))
check('F3 ★★ `npc_intent.WIRING` wired 翻正 =True', _NI2.WIRING.get('wired') is True,
      '')
check('F4 ★★ `npc_intent.WIRING.not_yet` 已清空', _NI2.WIRING.get('not_yet') == [],
      'not_yet=%s' % (_NI2.WIRING.get('not_yet'),))
check('F5 ★★ `npc_roam.WIRING.not_yet` 已清空（两条层4 待办已兑现）',
      _NR2.WIRING.get('not_yet') == [],
      'not_yet=%s' % (_NR2.WIRING.get('not_yet'),))
check('F6 ★ `npc_roam.WIRING.used_by` 登记了 `npc_plan_store`',
      any('npc_plan_store' in u for u in (_NR2.WIRING.get('used_by') or [])),
      '')
# ★ 每一条 wired=True 都必须在 used_by 里说清谁在用（"谁用它"不许空着）
check('F7 ★★ 三处 wired=True 的 used_by 都非空',
      all(bool(w.get('used_by')) for w in
          (NPS.WIRING, _NI2.WIRING, _NR2.WIRING) if w.get('wired')),
      '')

# ================================================================ G 判据自身体检
print()
print('=' * 74)
print('G 判据自身体检')
print('=' * 74)

SELF = read(os.path.abspath(__file__))
selftree = ast.parse(SELF)


def _print_points(tree, marker):
    """数「print 实参子树里出现 marker 字面量」的打印点（递归扫，`%` 格式化通吃）。"""
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'print':
            for a in node.args:
                for sub in ast.walk(a):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                            and marker in sub.value:
                        n += 1
    return n


n_mark = _print_points(selftree, '[PASS]') + _print_points(selftree, '[FAIL]')
# ★ 只该有 check() 本体那 2 处；★ 本文件明文里也不许出现裸标记（见抬头）。
check('G1 ★ 全文计数标记打印点恰 2（= check() 本体的 PASS+FAIL）',
      n_mark == 2, '打印点=%d' % n_mark)

fake_src = ("def f():\n    print('[PASS] x')\n"
            "def g():\n    print('[PASS] y')\n")
check('G1n 负控制：额外打标记的源码必须数出 > 1（证明 G1 非恒真）',
      _print_points(ast.parse(fake_src), '[PASS]') > 1, '')

check('G2 ★ 记账守恒（独立计数器 CALLS == PASS+FAIL）',
      CALLS == PASS + FAIL, 'CALLS=%d PASS+FAIL=%d' % (CALLS, PASS + FAIL))


def _broken_entry():
    global CALLS
    CALLS += 1
    return CALLS


_c0, _p0, _f0 = CALLS, PASS, FAIL
_brk = (_broken_entry() != PASS + FAIL)
CALLS, PASS, FAIL = _c0, _p0, _f0
check('G2n 负控制：漏记一格的假入口必须破坏守恒（证明 G2 有鉴别力）', _brk, '')

check('G3 被测文件都在盘上',
      os.path.exists(STORE) and os.path.exists(MAIN)
      and os.path.exists(ZONES81) and os.path.exists(ROAM_PY)
      and os.path.exists(INTENT_PY), '')

# ★ G4 本套件**不吃**"目录里有几个模块"这类脆弱计数 —— 断言"没有对 modules 目录做
#   枚举式计数"（那种判据会随新增模块假红，`round5_smoke` 已实名为 count-agnostic）。
#   ★★ 判据侧教训：第一版写成 `'模块数' not in SELF` —— 而**判据名里就有"模块数"三个字**
#      ⇒ 自指污染、恒假。改成扫**结构**（有没有 listdir 一个叫 modules 的目录，
#      或对它的结果取 len），既避开自指又真守得住。
_g4_bad = False
for _node in ast.walk(selftree):
    if isinstance(_node, ast.Call):
        _f = _node.func
        _fname = _f.id if isinstance(_f, ast.Name) else (
            _f.attr if isinstance(_f, ast.Attribute) else '')
        if _fname in ('listdir', 'scandir', 'glob'):
            for _a in ast.walk(_node):
                if isinstance(_a, ast.Constant) and isinstance(_a.value, str) \
                        and _a.value.strip('/\\') == 'modules':
                    _g4_bad = True
check('G4 ★ 本套件不对 modules 目录做枚举式计数（避开"加模块就假红"）',
      not _g4_bad, '')

# ★★ G5 防"无声无息不比对"：`run_all.py` 的比对分支是
#     `if args.update or old is None: cmp_txt = 'BASELINE'`（:2143）
#     ⇒ **新套件进了 `SUITES` 却忘了固基线** ⇒ `old is None` ⇒ 永远打印 `BASELINE`，
#       **看起来一切正常**（不是 IDENTICAL 也不是 DIFF），等于**根本没在守**。
#     ★ 本段实测踩到：`check80` 上段入列 `SUITES` 但从未 `--update` 过 ⇒ 基线 72 条
#       vs SUITES 73 条，差的就是它。
# 判据：基线里的套件集合 **==** `run_all.SUITES` 的 id 集合（含 SKIP 项也须在基线里）。
#   负控制：把一个真 id 从基线副本里摘掉，必须判否（证明判据真在比对集合）。
_BL_JSON = os.path.join(HERE, '..', '..', 'regress', 'baseline.json')
_bl_ids = set()
try:
    with io.open(os.path.normpath(_BL_JSON), encoding='utf-8') as _fh:
        _bl_ids = set((json.load(_fh).get('suites') or {}).keys())
except Exception:
    _bl_ids = set()
# 从 `run_all.py` 的 SUITES 里取 id（AST，不吃字符串自指）
_RUNALL = os.path.join(HERE, '..', '..', 'regress', 'run_all.py')
_ra_ids = set()
try:
    with io.open(os.path.normpath(_RUNALL), encoding='utf-8') as _fh:
        _ratree = ast.parse(_fh.read())
    for _n in ast.walk(_ratree):
        if isinstance(_n, ast.Assign) and any(
                isinstance(_t, ast.Name) and _t.id == 'SUITES' for _t in _n.targets):
            for _el in getattr(_n.value, 'elts', []):
                for _k, _v in zip(getattr(_el, 'keys', []), getattr(_el, 'values', [])):
                    if isinstance(_k, ast.Constant) and _k.value == 'id' \
                            and isinstance(_v, ast.Constant):
                        _ra_ids.add(_v.value)
except Exception:
    _ra_ids = set()
_missing = sorted(_ra_ids - _bl_ids)
check('G5 ★★ 新套件必须已固化进基线（防"入列 SUITES 却漏 --update ⇒ 永远 BASELINE ⇒ 静默不比对"）',
      bool(_ra_ids) and bool(_bl_ids) and not _missing,
      'suite=%d baseline=%d 缺=%s' % (len(_ra_ids), len(_bl_ids), _missing or '无'))
# 负控制：从基线副本摘掉一个真 id ⇒ 缺集必须非空（证明 G5 有鉴别力，非恒真）
_bl_minus = set(_bl_ids)
if _ra_ids:
    _bl_minus.discard(sorted(_ra_ids)[0])
check('G5n 负控制：摘掉一个真 id 后缺集必须非空（证明 G5 非恒真）',
      bool(_ra_ids & _bl_minus) and sorted(_ra_ids - _bl_minus) != [],
      '摘=%s' % (sorted(_ra_ids)[0] if _ra_ids else '?',))

print()
print('=' * 74)
print('结果：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：%s' % FAILED)
print('=' * 74)
sys.exit(1 if FAIL else 0)
