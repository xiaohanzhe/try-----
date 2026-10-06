# -*- coding: utf-8 -*-
"""第80轮回归锁：**OneShot 263 场景迁入** + **层3 就寝接线**不许静默漂移。

用户裁决（逐字，第79轮收尾）
----------------------------
> 「**废除，默认打开，我现在不方便，先跳过，要**」

逐词落地：
* **「废除」**     → 层3：NPC 就寝**不再用常量** `BEDTIME_HOME_SCENE`，
                     改**逐人决策**（`npc_intent.choose_sleep_scene`）。
* **「默认打开」** → `NPC_AUTONOMOUS_MOVE` 默认 **True**（由 `check79` W2 守）。
* **「先跳过」**   → A4 `chkdsk E: /f` **不做**（无判据可守，如实登记）。
* **「要」**       → Q1：接 **OneShot 263**（本套件 A~F 段）。

守什么
------
* **A ★★ OneShot 迁入完整性**：勘查产物 263 间，逐间都能在产品索引一一对上。
* **B ★★ 锚点优先**：`original_room_id` + `name` 与勘查产物**逐条全等**；
  对外部源盘缺失则 SKIP（**不假红** —— 第77轮纪律）。
* **C ★★★ 既有契约零破坏**：迁入前 8 章（desktop/ch1~5/ut/uty）**逐值不变**；
  增量**恰好** +oneshot 一章。
* **D ★★ 真装载**：走产品**唯一入口** `load_index()` + `load_scene(sid, entry=)`
  逐个过一遍（"数据写对了 ≠ 产品读得到"）。
* **E 明暗表同步**：`_worlds.json` 的 `areas`/`rooms` 两处都加 `oneshot`，
  且 263 间**全 `unknown`**（照抄 UT/黄魂，**一个 light/dark 都不许猜**）。
* **F ★★★ 层3 就寝**：旧常量 → 逐人决策的接线链（`decide_sleep` → `sleep_fn` 注入）。

★ 零网络 / 零 UI / 零外部盘（源盘只在 B 段用，缺了 SKIP）；不需要显示器。
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
R80 = os.path.join(ROOT, 'code-quality-audit', '第80轮-OneShot场景迁入')
SRC80 = os.path.join(R80, '_evidence', 'oneshot80.json')
BAK_IDX = os.path.join(R80, '_evidence', 'index_before80.json')
BAK_WORLDS = os.path.join(R80, '_evidence', 'worlds_before80.json')

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
print('第80轮：OneShot 迁入 + 层3 就寝')
print('=' * 74)

idx = load(os.path.join(SCENES, '_index.json'))
worlds = load(os.path.join(SCENES, '_worlds.json'))

# ================================================================ A 迁入完整性
print()
print('=' * 74)
print('A OneShot 迁入完整性')
print('=' * 74)

src_exists = os.path.exists(SRC80)
check('A1 勘查产物在位（oneshot80.json）', src_exists, SRC80)

src = load(SRC80) if src_exists else {'nodes': [], 'edges': [], 'anchors_ok': False}
nodes = src.get('nodes') or []

ch = (idx.get('chapters') or {}).get('oneshot')
check('A2 产品索引里有 `oneshot` 章', ch is not None,
      'chapters=%s' % list(idx.get('chapters') or {}))

# ★★ 第81轮：区域由 1 个（rooms）变 6 个 ⇒ 取值改成**区域无关**（遍历全部 areas）。
#   比原来更严：不再依赖"恰好有个叫 rooms 的区域"。
def _all_scenes_of(chapter):
    """→ `{scene_id: entry}`（展平该章全部区域的场景）。非法输入 ⇒ `{}`。"""
    out = {}
    for _aid, _a in ((chapter or {}).get('areas') or {}).items():
        for sid, ent in ((_a or {}).get('scenes') or {}).items():
            out[sid] = ent
    return out


def _area_ids_of(chapter):
    return sorted(((chapter or {}).get('areas') or {}).keys())


idx_scenes = _all_scenes_of(ch)
check('A3 迁入场景数 == 263（跨全部区域求和）', len(idx_scenes) == 263,
      'n=%d areas=%s' % (len(idx_scenes), _area_ids_of(ch)))

check('A4 勘查节点数 == 263', len(nodes) == 263, 'n=%d' % len(nodes))

# ★ 逐间：勘查产物里的每一间都能在索引里找到同 room_id 的行
idx_by_rid = {}
for sid, sc in idx_scenes.items():
    rid = sc.get('original_room_id')
    if isinstance(rid, int):
        idx_by_rid.setdefault(rid, []).append(sid)
src_rids = set(n['index'] for n in nodes)
missing = sorted(src_rids - set(idx_by_rid))
check('A5 ★★ 勘查的每一间都能在索引一一对上（零缺失）',
      not missing, '缺=%s' % (missing[:8] or '无'))

# ================================================================ B 锚点优先
print()
print('=' * 74)
print('B 锚点优先（id/name 逐条全等）')
print('=' * 74)

check('B1 勘查产物自证 anchors_ok=True', src.get('anchors_ok') is True,
      'anchors=%s' % (src.get('anchors') or [])[:3])

# 逐条比对 name（来自官方 oneshot_map_names.json，见勘查脚本）
name_bad = []
for n in nodes:
    hits = idx_by_rid.get(n['index']) or []
    if not hits:
        continue
    ok = any(idx_scenes[s].get('name') == n['name'] for s in hits)
    if not ok:
        name_bad.append((n['index'], n['name']))
check('B2 ★★ 逐条 name 全等（官方名字表口径）', not name_bad,
      '不符=%s' % (name_bad[:6] or '无'))

# ★ B 段对源盘的依赖：源盘缺 ⇒ SKIP 不假红（第77轮纪律）
SRC_DIR = os.environ.get(
    'ONESHOT_DIR',
    'C:\\Users\\23002\\Desktop\\项目文件夹\\niko的秘密'
    '\\OneShot.World.Machine.Edition.Build.16512634')
src_ok = os.path.isdir(SRC_DIR)
if src_ok:
    import glob
    tmx = glob.glob(os.path.join(SRC_DIR, 'gamedata', 'maps', '*.tmx'))
    check('B3 ★ 源盘在位且 .tmx 数 == 263（原地复核，不只看旧产物）',
          len(tmx) == 263, 'tmx=%d' % len(tmx))
else:
    print('[SKIP] 源盘不在（%s）⇒ B3 跳过，不假红' % SRC_DIR)

# ================================================================ C 零破坏
print()
print('=' * 74)
print('C 既有契约零破坏')
print('=' * 74)

if os.path.exists(BAK_IDX):
    old = load(BAK_IDX)
    old_ch = old.get('chapters') or {}
    # ★★ 第89轮修正（判据过窄 ⇒ 误报，记忆 §4 铁律）：本条的**意图**是
    #   "第80轮迁入 OneShot 时不许碰到**别的作品**"，不是"desktop 从此永不改动"。
    #   第89轮给 desktop 房间挂了 8 扇世界门（`obj_doorA~F/W/X`）—— 那是**该轮
    #   的设计目标**（用户口径："先能让我看到场景可以切换"），改的正是 desktop
    #   自己那一条。把它算进"变了的作品"是把两件事混为一谈。
    #   ⇒ 排除 desktop（它本就不属于任何原作房间，`original_room_id=-1`），
    #     并**保留**对它的正向断言（下方 "desktop 仍是一等场景"）。
    diffs = [k for k, v in old_ch.items()
             if k != 'desktop' and idx.get('chapters', {}).get(k) != v]
    check('C1 ★★★ 迁入前 8 章（除 desktop 自身）逐值不变', not diffs,
          '变了=%s' % (diffs or '无'))
    added = set(idx.get('chapters') or {}) - set(old_ch)
    removed = set(old_ch) - set(idx.get('chapters') or {})
    check('C2 ★ 增量恰好 +oneshot（不多不少）',
          added == {'oneshot'} and not removed,
          '新增=%s 删除=%s' % (sorted(added), sorted(removed)))
    n_old = sum(len(a.get('scenes') or {})
                for c in old_ch.values() for a in (c.get('areas') or {}).values())
    n_new = sum(len(a.get('scenes') or {})
                for c in (idx.get('chapters') or {}).values()
                for a in (c.get('areas') or {}).values())
    check('C3 ★ 总数 == 迁入前 + 263', n_new == n_old + 263,
          '%d -> %d (+%d)' % (n_old, n_new, n_new - n_old))
else:
    print('[SKIP] 备份不在 ⇒ C1/C2/C3 跳过')

# desktop 仍是一等场景（default_scene / 同构三级）
check('C4 桌面仍是一等场景（default_scene 不变）',
      idx.get('default_scene') == 'desktop', '%s' % idx.get('default_scene'))

# ================================================================ D 真装载
print()
print('=' * 74)
print('D 真装载（走产品唯一入口，不是自己读 JSON）')
print('=' * 74)

sys.path.insert(0, PET)
import modules.scene_system as SS  # noqa: E402

idx_loaded = SS.load_index(SCENES)
check('D1 产品索引加载器 `load_index()` ok=True',
      idx_loaded.get('ok') is True, 'err=%s' % idx_loaded.get('error'))

flat = idx_loaded.get('scenes') or {}
flat_oneshot = {k: v for k, v in flat.items() if k.startswith('oneshot.')}
check('D2 ★ `load_index()` 展平表里恰有 263 个 oneshot 场景',
      len(flat_oneshot) == 263, 'n=%d' % len(flat_oneshot))

# ★★★ 逐个真装载
n_ok, errs = 0, []
for sid in sorted(idx_scenes):
    try:
        got = SS.load_scene(sid, entry=flat.get(sid))
        if got is not None and getattr(got, 'name', None):
            n_ok += 1
    except Exception as e:
        errs.append((sid, str(e)))
check('D3 ★★★ 263 个 scene_id 逐个喂 `load_scene(entry=)`，全部真装载',
      n_ok == 263 and not errs, 'ok=%d 抛=%d %s' % (n_ok, len(errs), errs[:2]))

# ★ 真名（不是回落 id）+ room_id 真带上
#   第81轮：不再硬编码 `oneshot.rooms.Start`（区域已变），改从**数据里挑一条真 scene_id**。
_sample_sid = None
for _sid, _ent in sorted(idx_scenes.items()):
    if (_ent or {}).get('name') == 'Start':
        _sample_sid = _sid
        break
if _sample_sid is None:
    _sample_sid = sorted(idx_scenes)[0] if idx_scenes else ''
one = SS.load_scene(_sample_sid, entry=flat.get(_sample_sid))
check('D4 ★ name 是真名（Start），不是回落 id',
      bool(one) and getattr(one, 'name', None) == 'Start',
      'sid=%s name=%s' % (_sample_sid, getattr(one, 'name', None)))
check('D5 ★★ 装载结果带 original_room_id（渲染层查几何要用）',
      bool(one) and isinstance(getattr(one, 'original_room_id', None), int),
      'rid=%s' % getattr(one, 'original_room_id', None))

# ★ 负控制：编造 scene_id 必须装载不到
fake = SS.load_scene('oneshot.__nope__.__nope__', entry=None)
check('D5n ★ 负控制：编造 scene_id 装载不到（证明 D3/D4 非恒真）', fake is None, '')

# ================================================================ E 明暗表同步
print()
print('=' * 74)
print('E `_worlds.json` 同步（照抄 UT/黄魂，不猜）')
print('=' * 74)

# ★★ 第81轮：区域由 1 个变 6 个 ⇒ E1 改成**集合相等**（比原来更严：
#    不写死 "rooms"，而是要求 `_worlds.areas.oneshot` 的键集
#    **恰等于** `_index.json` 里 oneshot 章的 areas 键集，且值全 `unknown`。
_w_os_areas = (worlds.get('areas') or {}).get('oneshot') or {}
_idx_os_areas = set(_area_ids_of(ch))
check('E1 ★ `_worlds.areas.oneshot` 键集 == 索引 areas 键集，且全 unknown',
      set(_w_os_areas) == _idx_os_areas
      and all(v == 'unknown' for v in _w_os_areas.values())
      and len(_w_os_areas) > 0,
      'worlds=%s idx=%s' % (sorted(_w_os_areas), sorted(_idx_os_areas)))

w_rooms = (worlds.get('rooms') or {}).get('oneshot') or {}
check('E2 `rooms.oneshot` == 263 间', len(w_rooms) == 263, 'n=%d' % len(w_rooms))
check('E3 ★★ 263 间全 `unknown`（一个 light/dark 都不许猜）',
      all(v == 'unknown' for v in w_rooms.values()),
      '非unknown=%s' % [k for k, v in w_rooms.items() if v != 'unknown'][:5])
check('E4 `rooms.oneshot` 的 id 集 == 索引里的 room_id 集（两处派生自同一事实）',
      set(int(k) for k in w_rooms) == set(idx_by_rid),
      '差=%s' % sorted(set(int(k) for k in w_rooms) ^ set(idx_by_rid))[:6])

# UT/黄魂口径未被本轮改动
check('E5 ★ UT/黄魂 的 rooms 仍全 unknown（没被顺手改坏）',
      all(v == 'unknown' for v in (worlds.get('rooms') or {}).get('ut', {}).values())
      and all(v == 'unknown' for v in (worlds.get('rooms') or {}).get('uty', {}).values()),
      '')

# ================================================================ F 层3 就寝
print()
print('=' * 74)
print('F 层3 就寝（旧常量 -> 逐人决策）')
print('=' * 74)

ROAM = os.path.join(PET, 'modules', 'npc_roam.py')
MAIN = os.path.join(PET, 'src', 'main.py')
roam_src = read(ROAM)
main_src = read(MAIN)
rtree = ast.parse(roam_src)
mtree = ast.parse(main_src)

# F1 `decide_sleep` 在位且在 `npc_roam` 里
ds = [n for n in ast.walk(rtree)
      if isinstance(n, ast.FunctionDef) and n.name == 'decide_sleep']
check('F1 `npc_roam.decide_sleep()` 在位', bool(ds), '')

# F2 ★ `step()` 真接受 `sleep_fn`（否则决策层没入口）
st = [n for n in ast.walk(rtree)
      if isinstance(n, ast.FunctionDef) and n.name == 'step']
st_args = set()
for n in ast.walk(st[0]) if st else []:
    if isinstance(n, ast.arg):
        st_args.add(n.arg)
check('F2 ★★ `step()` 真带 `sleep_fn` 形参（层3 的注入口）',
      'sleep_fn' in st_args, 'args=%s' % sorted(st_args))

# F3 ★★★ `step()` 真**调用** `decide_sleep`（否则"接了但没接上"）
st_calls = set()
for n in ast.walk(st[0]) if st else []:
    if isinstance(n, ast.Call):
        if isinstance(n.func, ast.Name):
            st_calls.add(n.func.id)
        elif isinstance(n.func, ast.Attribute):
            st_calls.add(n.func.attr)
check('F3 ★★★ `step()` 真调 `decide_sleep()`（不是死代码）',
      'decide_sleep' in st_calls, 'calls=%s' % sorted(st_calls))

# F4 ★★ main 侧：`_npc_roam_sleep` 在位 + 真调 `choose_sleep_scene`
cls = None
for n in mtree.body:
    if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet':
        cls = n
        break
sleep_m = [n for n in ast.walk(cls)
           if isinstance(n, ast.FunctionDef) and n.name == '_npc_roam_sleep'] if cls else []
check('F4 ★★ `main._npc_roam_sleep` 在位', bool(sleep_m), '')
sl_calls = set()
for n in ast.walk(sleep_m[0]) if sleep_m else []:
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        sl_calls.add(n.func.attr)
check('F5 ★★★ `_npc_roam_sleep` 真调 `choose_sleep_scene`（真源，不自造一套）',
      'choose_sleep_scene' in sl_calls, 'calls=%s' % sorted(sl_calls))

# F6 ★★★ `_npc_roam_tick` 真把 `sleep_fn` 注入 `step()`
tick = [n for n in ast.walk(cls)
        if isinstance(n, ast.FunctionDef) and n.name == '_npc_roam_tick'] if cls else []
injected = False
for n in ast.walk(tick[0]) if tick else []:
    if isinstance(n, ast.Call):
        for kw in n.keywords:
            if kw.arg == 'sleep_fn':
                injected = True
check('F6 ★★★ `_npc_roam_tick` 真把 `sleep_fn` 注入 `step()`（层3 不是死代码）',
      injected, '')

# F7 ★★ 旧口径**对 NPC 已废弃**（注释里要有声明；判据不锁具体措辞）
depre = False
for ln in main_src.splitlines():
    s = ln.strip()
    if s.startswith('#') and 'NPC' in s and ('不适用' in s or '废弃' in s or '无关' in s):
        depre = True
        break
check('F7 ★★ `BEDTIME_HOME_SCENE` 处有「NPC 不适用/已废弃」注释声明',
      depre, '')

# ================================================================ G 判据自身体检
print()
print('=' * 74)
print('G 判据自身体检')
print('=' * 74)

SELF = read(os.path.abspath(__file__))
stree = ast.parse(SELF)


def _print_points(tree, marker):
    """数「print 实参里出现 marker 字面量」的打印点。

    ★★ 判据侧教训（第80轮现场踩到）：第一版只认 `ast.Constant` 实参
      ⇒ 本套件 `check()` 写的是 `print('[PASS] %s' % name, detail)`，
         标记落在 **`BinOp`（% 格式化）** 里 ⇒ 一个都没数到（得 0，报假红）。
      ⇒ 改**递归扫整棵实参子树**的 `ast.Constant`（`ast.walk`），两种写法通吃。
      ★ 这与 `run_all.count_results()` 的口径一致 —— 它也是按**输出行**数，
        而输出行正是 `%` 格式化之后的文本。
    """
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


n_mark = _print_points(stree, '[PASS]') + _print_points(stree, '[FAIL]')
# ★ 只该有 check() 本体那 2 处（PASS 一处 + FAIL 一处）。
check('G1 ★ 判据名/明细里不含计数标记字样（免得自指污染 run_all 计数）',
      n_mark == 2, '打印点=%d（应恰 2 = check() 本体的 PASS+FAIL）' % n_mark)


def _print_points_fake(tree, marker):
    return _print_points(tree, marker)


fake_src = ("def f():\n    print('[PASS] x')\n"
            "def g():\n    print('[PASS] y')\n")
check('G1n 负控制：同样的检测喂"额外打标记"的源码必须数出 > 1（证明 G1 非恒真）',
      _print_points_fake(ast.parse(fake_src), '[PASS]') > 1, '')

# 记账守恒
check('G2 ★ 记账守恒（独立计数器 CALLS == PASS+FAIL，抓漏记/错记）',
      CALLS == PASS + FAIL, 'CALLS=%d PASS+FAIL=%d' % (CALLS, PASS + FAIL))


def _broken_entry():
    global CALLS
    CALLS += 1
    return CALLS


_c0, _p0, _f0 = CALLS, PASS, FAIL
_brk = (_broken_entry() != PASS + FAIL)
CALLS, PASS, FAIL = _c0, _p0, _f0
check('G2n 负控制：漏记一格的假入口必须破坏守恒（证明 G2 有鉴别力）', _brk, '')

# 被测文件在盘（■ 免得"文件没了判据还绿"）
check('G3 被测文件都在盘上',
      os.path.exists(ROAM) and os.path.exists(MAIN)
      and os.path.exists(SRC80), '')

print()
print('=' * 74)
print('结果：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：%s' % FAILED)
print('=' * 74)
sys.exit(1 if FAIL else 0)
