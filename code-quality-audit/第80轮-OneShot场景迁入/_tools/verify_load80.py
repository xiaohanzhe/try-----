# -*- coding: utf-8 -*-
u"""第80轮：**真装载**验证 —— 产品加载器真能读出这 263 个 OneShot 场景。

★ 纪律（「函数写对了 ≠ 产品用上了」）：不只看 JSON 写没写，
  要**真调产品的加载函数**，逐个场景过一遍。

零网络 / 零 UI / 不需要显示器。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)

SCENES = os.path.join(PET, 'assets', 'scenes')
PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=''):
    global PASS, FAIL
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


print('=' * 74)
print('第80轮 · OneShot 场景「真装载」验证')
print('=' * 74)

# ---- 1. 产品侧数据层真能被 import 并加载 ----
import modules.scene_system as SS  # noqa: E402

DATA = None
for attr in ('SceneData', 'SceneIndex', 'load_index', 'load_scenes'):
    if hasattr(SS, attr):
        DATA = attr
        break
print('scene_system 导出: %s' % [a for a in dir(SS) if not a.startswith('__')][:20])
check('S1 产品数据层可 import', hasattr(SS, 'SceneData') or DATA is not None,
      'attr=%s' % DATA)

# ---- 2. 索引文件真读得到 oneshot 章 ----
idx = json.loads(read(os.path.join(SCENES, '_index.json')))
ch = idx['chapters'].get('oneshot')
check('S2 索引里有 oneshot 章', ch is not None,
      'chapters=%s' % list(idx['chapters'].keys()))
scenes = (ch or {}).get('areas', {}).get('rooms', {}).get('scenes', {})
check('S3 oneshot 场景数 == 263', len(scenes) == 263, 'n=%d' % len(scenes))

# ---- 3. 逐条字段自洽（与 Deltarune 分片场景同构）----
bad_key = []
bad_rid = []
for sid, sc in scenes.items():
    if not (isinstance(sc.get('name'), str) and sc['name']
            and 'bg' in sc and 'bg_source' in sc and 'objects' in sc):
        bad_key.append(sid)
    if not isinstance(sc.get('original_room_id'), int):
        bad_rid.append(sid)
check('S4 每个场景都有 name/bg/bg_source/objects（字段集同构）',
      not bad_key, '缺字段=%d' % len(bad_key))
check('S5 每个场景 original_room_id 都是 int', not bad_rid,
      '缺=%d' % len(bad_rid))
check('S6 scene_id 前缀 == oneshot.rooms.',
      all(s.startswith('oneshot.rooms.') for s in scenes),
      '样例=%s' % sorted(scenes)[:2])

# ---- 4. ★★★ 真装载：走产品**唯一入口** `load_index()` + `load_scene(sid, entry=)` ----
#      ★ 纪律：「函数写对了 ≠ 产品用上了」⇒ 不自己读 JSON，真调产品函数。
#      ★★ 踩坑记录（本轮真踩到）：第一版只调 `load_scene(sid)` ⇒ 263 个全 None，
#         差点误判成"迁入失败"。真因见 `load_scene` docstring：
#         **分片场景必须给 `entry`**（索引登记行），否则它只认独立文件。
#         ⇒ 正确路径 = `load_index()['scenes'][sid]` 当 entry。
idx_loaded = SS.load_index(SCENES) if hasattr(SS, 'load_index') else None
check('S7 ★ 产品索引加载器 `load_index()` 真跑通（ok=True）',
      bool(idx_loaded) and idx_loaded.get('ok') is True,
      'ok=%s err=%s' % (getattr(idx_loaded, 'get', lambda *a: None)('ok'),
                        getattr(idx_loaded, 'get', lambda *a: None)('error')))
flat = (idx_loaded or {}).get('scenes') or {}

# ---- 5. ★★★ 把 263 个 scene_id 逐个喂进产品装载入口（带 entry，走分片）----
load_scene = getattr(SS, 'load_scene', None)
n_ok = 0
errs = []
missing = []
if callable(load_scene):
    for sid in sorted(scenes):
        try:
            got = load_scene(sid, entry=flat.get(sid))
            if got is not None and getattr(got, 'name', None):
                n_ok += 1
            else:
                missing.append((sid, repr(got)[:60]))
        except Exception as e:
            errs.append((sid, str(e)))
    check('S8 ★★★ 逐个喂 263 个 scene_id 进 `load_scene(entry=)`，全部真装载',
          n_ok == 263 and not errs and not missing,
          'ok=%d 空=%d 抛=%d %s' % (n_ok, len(missing), len(errs),
                                    (errs[:2] or missing[:2])))
    # ★ 且装出来的 name 是**真名**（`Start`），不是回落成 id
    try:
        one = load_scene('oneshot.rooms.Start',
                         entry=flat.get('oneshot.rooms.Start'))
    except Exception:
        one = None
    check('S8b ★ 装出来的 name 是真名（`Start`），不是回落成 id',
          bool(one) and getattr(one, 'name', None) == 'Start',
          'name=%s' % getattr(one, 'name', None))
    # ★★ 且 room_id 真带上（渲染层要拿它查房间几何，丢了会"房间未知"）
    check('S8c ★★ 装载结果带 original_room_id（渲染层查几何要用，不许丢）',
          bool(one) and isinstance(getattr(one, 'original_room_id', None), int),
          'rid=%s' % getattr(one, 'original_room_id', None))

# ---- 6. ★ 负控制：编造一个 scene_id 必须装载不到 ----
if callable(load_scene):
    try:
        fake = load_scene('oneshot.rooms.__no_such_scene__', entry=None)
    except Exception:
        fake = None
    check('S8n ★ 负控制：编造的 scene_id 必须装载不到（证明 S8 非恒真）',
          fake is None, 'fake=%r' % (fake,))

# ---- 7. _worlds.json 同步 ----
w = json.loads(read(os.path.join(SCENES, '_worlds.json')))
check('S9 _worlds.json 有 oneshot.rooms == unknown',
      (w['areas'].get('oneshot') or {}).get('rooms') == 'unknown',
      '%s' % (w['areas'].get('oneshot'),))
check('S10 _worlds.json rooms.oneshot == 263 间且全 unknown',
      len(w['rooms'].get('oneshot') or {}) == 263
      and all(v == 'unknown' for v in (w['rooms'].get('oneshot') or {}).values()),
      'n=%d' % len(w['rooms'].get('oneshot') or {}))

# ---- 8. 分片文件在位 ----
zp = os.path.join(SCENES, '_zone.oneshot.rooms.json')
check('S11 分片文件 _zone.oneshot.rooms.json 在位', os.path.exists(zp), zp)

# ---- 9. 既有章节零破坏（★ 与写入前的备份逐值比对，不靠"我觉得没动"）----
BAK = os.path.join('E:\\', 'Download', '_tmp', '_index.before80.json')
if os.path.exists(BAK):
    old = json.loads(read(BAK))
    diffs = []
    for k, v in old['chapters'].items():
        if idx['chapters'].get(k) != v:
            diffs.append(k)
    check('S12 ★★ 既有 8 章（desktop/ch1~5/ut/uty）**逐值不变**',
          not diffs, '变了=%s' % (diffs or '无'))
    check('S12b ★ 增量恰好 +oneshot 一章',
          set(idx['chapters']) - set(old['chapters']) == {'oneshot'}
          and set(old['chapters']) - set(idx['chapters']) == set(),
          '新增=%s' % (set(idx['chapters']) - set(old['chapters']),))
else:
    print('[SKIP] 备份不在，跳过零破坏比对（如实跳过）')

print()
print('=' * 74)
print('结果：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：%s' % FAILED)
print('=' * 74)
sys.exit(1 if FAIL else 0)
