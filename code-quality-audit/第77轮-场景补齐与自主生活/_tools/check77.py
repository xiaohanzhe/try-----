# -*- coding: utf-8 -*-
"""第 77 轮回归锁：**跨作品场景迁入产品索引不许静默漂移**。

守的是什么
----------
用户口径（逐字）：

> 「感觉场景数太少了…**5 个作品加起来**（三角符文，ut，oneshot，黄魂，outertale）
>  **怎么可能就 1000 刚出头呢，自己复查一下**」

复查结论：`1,014` **只是三角符文**。UT(358) / 黄魂(287) 只活在跨作品大图
`bigmap66.json` 里，**从来没有写进** `ralsei_pet/assets/scenes/_index.json`。
本轮把它们**迁入产品索引**（1,014 → **1,659**）。

本套件守三条
------------
1. **A 迁入完整性**：大图里 ut/uty 的**每一个**房间都能在产品索引里找到
   （一一对应，不许少、不许编）。
2. **B 锚点优先**：迁入的 `w/h/name` 必须与**原作转储**（`ut_rooms.json`）
   **逐条全等** —— "提取成功"≠"提取正确"，所以拿三个源交叉验。
3. **C 既有契约零破坏**：Deltarune 的 1,014 个场景与 4 个 unknown 世界判定
   **一字不动**（迁移只许"加"，不许"改"）。

★ 判据自身体检（F 段）：每个 FAIL 都能说出"谁错了"。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# <repo>/code-quality-audit/<轮次>/_tools  → 上溯三层才是仓库根
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
BIGMAP = os.path.join(ROOT, 'code-quality-audit', '第66轮-大图连通与mod并入',
                      '_evidence', 'bigmap66.json')
SRC_DIR = r'E:\Download\_extract61\_data'

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


def _probe_ledger():
    """F4 自检：**造一个失败**，看它是否真进账。

    ★★ 这里绝不能走 `check()` —— 它会往 stdout 打一行 `[FAIL]`，
    而 `regress/run_all.py:1795` 的 `count_results()` 是 **正则数 `[FAIL]` 字面量**。
    探针那一行会被数成"套件自己失败了一条"，于是**整套回归报 `FAIL=1`**，
    即使本套件自报 `FAIL=0`。
    ⇒ 探针必须**只动计数器、不打 stdout**（也就不污染成套件的 FAIL 计数）。
    """
    global PASS, FAIL
    p0, f0 = PASS, FAIL
    FAIL += 1                      # 手写记账，绕开 check() 的 print
    FAILED.append('__probe__')
    got = (FAIL == f0 + 1 and '__probe__' in FAILED)
    FAIL = f0                      # 精确还原，探针不留痕
    FAILED.remove('__probe__')
    return got and (PASS, FAIL) == (p0, f0)


def jload(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


print('=' * 74)
print('A 迁入完整性：大图 ut/uty 每一个房间都必须在产品索引里')
print('=' * 74)

idx = jload(os.path.join(SCENES, '_index.json'))
big = jload(BIGMAP)

# 产品索引里的场景 → 按 (work, room_id) 建表
idx_scenes = {}
for chk, chv in (idx.get('chapters') or {}).items():
    for areak, areav in (chv.get('areas') or {}).items():
        for sid, srec in ((areav or {}).get('scenes') or {}).items():
            idx_scenes.setdefault(chk, {})[srec.get('original_room_id')] = sid

big_by_work = {}
for n in big['nodes']:
    big_by_work.setdefault(n.get('work'), {})[n['index']] = n

for work, ch in (('ut', 'ut'), ('uty', 'uty')):
    bn = big_by_work.get(work) or {}
    idxn = idx_scenes.get(ch) or {}
    missing = sorted(set(bn) - set(idxn))
    check('A1 %s：大图 %d 个房间**全部**在产品索引里（缺 %d）'
          % (work, len(bn), len(missing)),
          len(bn) > 0 and not missing,
          '索引 %d 个；缺 %r' % (len(idxn), missing[:5]))

# 反向：索引里不许有"大图没有"的房间（防编造）
for work, ch in (('ut', 'ut'), ('uty', 'uty')):
    bn = big_by_work.get(work) or {}
    idxn = idx_scenes.get(ch) or {}
    extra = sorted(set(idxn) - set(bn))
    check('A2 %s：索引里**没有**大图之外的房间（防编造）' % work,
          not extra, '多出 %r' % (extra[:5],))

check('A3 两章合计 == 645（358 + 287，与第66轮大图逐值一致）',
      len(idx_scenes.get('ut') or {}) == 358
      and len(idx_scenes.get('uty') or {}) == 287,
      'ut=%d uty=%d' % (len(idx_scenes.get('ut') or {}),
                        len(idx_scenes.get('uty') or {})))

print()
print('=' * 74)
print('B 锚点优先：迁入的 name/w/h 必须与**原作转储**逐条全等')
print('=' * 74)

for work, ch in (('ut', 'ut'), ('uty', 'uty')):
    sub = 'undertale' if work == 'ut' else 'undertale_yellow'
    src = os.path.join(SRC_DIR, sub, 'ut_rooms.json')
    if not os.path.isfile(src):
        check('B0 %s 原作转储在位' % work, False, src)
        continue
    raw = jload(src)['rooms']
    bn = big_by_work[work]
    bad = []
    for r in raw:
        n = bn.get(r['index'])
        if n is None or n['name'] != r['name'] or n['w'] != r['w'] or n['h'] != r['h']:
            bad.append(r['index'])
    check('B1 %s：原作 %d 间与原版逐条全等（名字+宽+高），不符 %d'
          % (work, len(raw), len(bad)),
          len(raw) > 0 and not bad, '不符 %r' % (bad[:5],))

# 几何表：迁入的场景必须能查到尺寸（否则渲染层退化成"未知房间"）
geom = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']
miss_g = []
for ch in ('ut', 'uty'):
    for rid in (idx_scenes.get(ch) or {}):
        if ('%s:%s' % (ch, rid)) not in geom:
            miss_g.append((ch, rid))
check('B2 ★ 迁入的 645 个场景**全部**能在 `_room_geometry.json` 查到尺寸',
      not miss_g, '缺 %d %r' % (len(miss_g), miss_g[:3]))

# ★★ 几何表纪律（该文件的 note 明写"采不到的**不写进表**——不伪造 640x480"）
for ch in ('ut', 'uty'):
    checked = [k for k in geom if k.startswith(ch + ':')]
    check('B3 ★ %s 几何条目数 == 索引场景数（多一个都是伪造）' % ch,
          len(checked) == len(idx_scenes.get(ch) or {}),
          '几何 %d vs 索引 %d' % (len(checked), len(idx_scenes.get(ch) or {})))

print()
print('=' * 74)
print('C 既有契约零破坏（Deltarune 的一字不动）')
print('=' * 74)

# Deltarune 五章 + desktop 的分章数必须与第47/76轮基线**逐值相同**
BASE = {'desktop': 1, 'ch1': 128, 'ch2': 236, 'ch3': 187, 'ch4': 261, 'ch5': 201}
got = {ch: len(idx_scenes.get(ch) or {}) for ch in BASE}
check('C1 ★ Deltarune 六章分章数**逐值不变**（迁移只加不改）',
      got == BASE, '得 %r' % (got,))

# 世界表：Deltarune 部分不动，ut/uty 全 unknown
w = jload(os.path.join(SCENES, '_worlds.json'))
dr_unknown = sorted((ch, int(rid)) for ch, m in (w.get('rooms') or {}).items()
                    if ch in BASE and ch != 'desktop'
                    for rid, v in m.items() if v not in ('light', 'dark'))
check('C2 ★★ Deltarune 的未判定 4 间**逐条不变**',
      dr_unknown == [('ch1', 136), ('ch3', 110), ('ch4', 159), ('ch4', 166)],
      '%r' % (dr_unknown,))
imp = [(ch, rid) for ch, m in (w.get('rooms') or {}).items()
       if ch in ('ut', 'uty') for rid, v in m.items() if v == 'unknown']
check('C3 ★★ ut/uty 的 645 间**全部** unknown（无 darkzone 取证 ⇒ 不许猜）',
      len(imp) == 645,
      'unknown %d' % len(imp))
# 负控制：不许有人偷偷给 ut/uty 判 light/dark
guessed = [(ch, rid) for ch, m in (w.get('rooms') or {}).items()
           if ch in ('ut', 'uty') for rid, v in m.items() if v in ('light', 'dark')]
check('C4 ★★ 负控制：ut/uty 里**一个** light/dark 都没有（猜了就会把玩家道具变垃圾）',
      not guessed, '猜了 %r' % (guessed[:5],))

# 别名表：允许为空覆盖（现网 64 条只服务 Deltarune）
al = jload(os.path.join(SCENES, '_aliases.json'))
check('C5 别名表可加载且非空（第45轮的 64 条不许被迁入动作弄坏）',
      len((al.get('entries') or {})) >= 60,
      '%d 条' % len((al.get('entries') or {})))

print()
print('=' * 74)
print('D 副产品：`ruined` 特质转正（UT 废墟区域带来的真实能力）')
print('=' * 74)

MODULES = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MODULES)
import npc_life as L                                          # noqa: E402

_ids = []
for chk, chv in (idx.get('chapters') or {}).items():
    _ids.append(chk)
    for areak, areav in (chv.get('areas') or {}).items():
        _ids.append(areak)
        for sid in ((areav or {}).get('scenes') or {}):
            _ids.append(sid)

ruin_hits = sum(1 for s in _ids if L._token_hits('ruin', s))
check('D1 ★★ `ruin` 令牌现网 ≥1 命中（第73轮时为 0；UT 废墟区域已迁入）',
      ruin_hits > 0, '命中 %d' % ruin_hits)
check('D2 ★★ 无第二份真相：本位表与预留表的**令牌集不相交**',
      not ({t: sorted(set(L.TRAIT_TOKENS.get(t, ()))
                      & set(L.TRAIT_TOKENS_RESERVED.get(t, ())))
            for t in set(L.TRAIT_TOKENS) | set(L.TRAIT_TOKENS_RESERVED)
            if set(L.TRAIT_TOKENS.get(t, ())) & set(L.TRAIT_TOKENS_RESERVED.get(t, ()))}),
      'ruined live=%r res=%r' % (L.TRAIT_TOKENS.get('ruined'),
                                 L.TRAIT_TOKENS_RESERVED.get('ruined')))
_zero = [(t, tok) for t, toks in L.TRAIT_TOKENS.items() for tok in toks
         if not any(L._token_hits(tok, s) for s in _ids)]
check('D3 ★ 本位令牌**逐条**现网 ≥1 命中（零命中 = 虚假宣传）',
      not _zero, str(_zero[:3] or '(全命中)'))
# ★ 第80轮：OneShot 263 场景迁入 ⇒ `sun`(bright) / `sky`(cosmic) 语义正确、已**转正**；
#   `square` / `street` 语义错位（几何方形 / 街名）⇒ 移入 `BANNED_TOKENS('OMITTED')`。
#   ⇒ 判据改为**随事实**：预留表逐条仍必须 0 命中（这个不变、更严），
#     但**把已被扬弃的禁词从预留表里排除**后逐条验（禁词本就不许在任何表里出现）。
_banned_om = set(L.banned_tokens('OMITTED'))
_nz = [(t, tok) for t, toks in L.TRAIT_TOKENS_RESERVED.items() for tok in toks
       if tok not in _banned_om and any(L._token_hits(tok, s) for s in _ids)]
check('D4 ★ 预留令牌**逐条**仍 0 命中（Outertale 未接入 ⇒ 不许混进本位凑数；'
      '第80轮起禁词已排除）',
      not _nz, str(_nz[:3] or '(全 0 命中)'))
# ★ 第80轮改口径：`bright`/`cosmic` 由 OneShot 的 `sun`/`sky` **部分兑现** ⇒
#   旧断言"仍零命中"已过时。新断言**更严**：把两条**转正令牌**排除后，
#   `bright`/`cosmic` 的**其余令牌**（预留槽）仍必须 0 命中 —— 即"没有偷偷扩大覆盖"。
_live_bc = set(L.TRAIT_TOKENS.get('bright', ())) | set(L.TRAIT_TOKENS.get('cosmic', ()))
_res_leak = [tok for t in ('bright', 'cosmic')
             for tok in L.TRAIT_TOKENS_RESERVED.get(t, ())
             if tok not in _banned_om and any(L._token_hits(tok, s) for s in _ids)]
check('D5 ★ 如实：`bright`/`cosmic` 的能力**只由转正令牌兑现**，'
      '预留槽不许偷偷命中（不许假装覆盖了全部明亮与宇宙）',
      not _res_leak and _live_bc <= {'sun', 'sky'},
      'live_bright=%r live_cosmic=%r res_leak=%r' % (
          L.TRAIT_TOKENS.get('bright'), L.TRAIT_TOKENS.get('cosmic'), _res_leak))

print()
print('=' * 74)
print('E 契约与工具在位')
print('=' * 74)

CROSS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_crossworld.json')
cj = jload(CROSS)
check('E1 跨世界契约已推进到第77轮且记了迁入事实',
      (cj.get('round') or 0) >= 77
      and (cj.get('round77') or {}).get('scene_import', {}).get('scenes') == 645,
      'round=%s import=%r' % (cj.get('round'),
                              (cj.get('round77') or {}).get('scene_import')))
check('E2 契约 `wired_how` 写明了 `ruined` 转正（不是含糊带过）',
      'ruined' in (cj.get('scene_traits', {}).get('wired_how') or '')
      and '第77轮' in (cj.get('scene_traits', {}).get('wired_how') or ''),
      'len=%d' % len(cj.get('scene_traits', {}).get('wired_how') or ''))

TOOLS = os.path.join(ROOT, 'code-quality-audit', '第77轮-场景补齐与自主生活', '_tools')
for t in ('build77.py', 'worlds77.py', 'geometry77.py'):
    check('E3 工具 %s 在盘上' % t, os.path.isfile(os.path.join(TOOLS, t)))

# 分片文件真在盘上
for ch in ('ut', 'uty'):
    zp = os.path.join(SCENES, '_zone.%s.rooms.json' % ch)
    check('E4 分片 %s 在盘上且 chapter_id 自洽' % os.path.basename(zp),
          os.path.isfile(zp) and jload(zp).get('chapter_id') == ch)

print()
print('=' * 74)
print('F 判据自身体检')
print('=' * 74)

# F1 build77 的字段必须与既有分片**逐字同构**（第一版自造 file='__zone__' 导致两处报红）
_z = jload(os.path.join(SCENES, '_zone.ut.rooms.json'))['scenes']
_sample = list(_z.values())[0]
check('F1 ★★ 迁入场景的字段集 == 既有分片场景字段集（防"自造字段"）',
      set(_sample) == {'name', 'name_raw', 'name_derived', 'original_room_id',
                       'bg', 'bg_source', 'objects'},
      '字段=%r' % sorted(_sample))
check('F2 ★★ 每个迁入场景都显式声明 bg 键（E1a 判据的守点）',
      all('bg' in s for s in _z.values()),
      '缺 %d' % sum(1 for s in _z.values() if 'bg' not in s))
check('F3 ★ 迁入场景的 bg 全为 None 且 bg_source == "none"（没素材就如实留空）',
      all(s.get('bg') is None and s.get('bg_source') == 'none'
          for s in _z.values()),
      '异常 %d' % sum(1 for s in _z.values()
                    if not (s.get('bg') is None and s.get('bg_source') == 'none')))
_n_before = PASS + FAIL
_noop_ok = _probe_ledger()              # ★ 不打 stdout：见该函数注释（否则会污染套件 FAIL 计数）
check('F4 记账口不是 no-op（造失败真进账，且探针自身零痕迹：不打失败标记、不动计数）',
      _noop_ok, '探测前后计数净增=%d' % (PASS + FAIL - _n_before))

print()
print('=' * 74)
print('第77轮 跨作品场景迁入锁：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：')
    for n in FAILED:
        print('  - %s' % n)
print('=' * 74)
sys.exit(1 if FAIL else 0)
