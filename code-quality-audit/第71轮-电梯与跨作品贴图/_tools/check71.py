# -*- coding: utf-8 -*-
"""第71轮 · 常驻锁：跨作品贴图 + UT 电梯素材不许静默漂移。

为什么值得常驻：本轮把 61 位跨作品 NPC 从"有名字没画"变成"有画"，
并把 UT 那部电梯的零件抽了出来。**素材是二进制**，`run_all` 的 IDENTICAL
判据只比"判据输出文本"—— PNG 被谁覆盖了、少了几张，没人会知道。
⇒ 用这张锁把"哪些名字应该有文件、几张、多大"钉住。

设计纪律（都从历轮教训来）：
  ① **零 Qt、零存储、零网络、零外部盘** ⇒ 可进 G2（记忆铁律：回归套件不许依赖外部盘）。
     本脚本只读 `ralsei_pet/assets/**` 与 `_evidence/*.json`，都在仓库里。
  ② **正/负控制成对**：正控制 = 声明的名字必须有文件；负控制 = 编造的名字必须没有，
     且"A 判据对空集/假集必须报红"由**内存内负输入**证明（不靠人眼）。
  ③ **不做自比**：A 判据的真源 = `_registry.json`（数据面契约），不是本轮自己写的 manifest。
     manifest 只用来做**对账**（E 段），不当真理。
  ④ **判据名里不许自带 `[PASS]`/`[FAIL]`/`[OK]` 字样**（会污染 run_all 的计数）。
  ⑤ 零第三方依赖：PNG 尺寸直接读 IHDR（不 import PIL）。
  ⑥ ★ G 段（电梯**数据面**）多一条"诚实判据"：组件只允许写 `spec_only`，
     且必须列出 `not_yet`。理由 = 本项目最贵的坑「函数写对了 ≠ 产品用上了」——
     本轮产品侧跨作品场景面**还没建**（`_index.json` 只有 desktop + ch1~ch5），
     谁要是把这条 link 改成"已接线"，G8 必须报红。
"""
from __future__ import print_function

import io
import json
import os
import re
import struct
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
# ★ 本脚本住在 `<轮次>/_tools/` ⇒ 到仓库根要**三级**（第66轮那条 `'..','..'` 的经验
#   只适用于直接放在 `<轮次>/` 下的脚本，照抄会少一级 —— 本轮实测踩过一次）。
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets')
SPR = os.path.join(ASSETS, 'sprites')
ELEV = os.path.join(ASSETS, 'elevator')
REG = os.path.join(ASSETS, 'npc', '_registry.json')
EV = os.path.join(HERE, '_evidence')

FAILS = []
NCHECK = 0

#: 四作各自的资产目录名 = NPC id 的前缀
WORKS = ('ut', 'hy', 'ot', 'os')


def check(name, cond, extra=''):
    global NCHECK
    NCHECK += 1
    # 判据名不许自带标记字面量（run_all 按 '[PASS]'/'[OK]' 计数）
    for tok in ('[PASS]', '[FAIL]', '[OK]'):
        if tok in name:
            FAILS.append('判据名字面量污染: %s' % name)
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def read_json(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def png_size(p):
    """零依赖读 PNG IHDR：8B 签名 + 4B len + 'IHDR' + w(4B BE) + h(4B BE)。

    ★ 返回 **list**（不是 tuple）—— 本轮实测踩过：本函数原返回 `struct.unpack`
      的 tuple，而调用方拿它跟 manifest 里的 list 比，`tuple != list` **恒为 True**，
      于是 D2b/D2d 成了恒真判据、无脑报红。返回值类型必须与比较对象一致。
    """
    with io.open(p, 'rb') as fh:
        head = fh.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        raise ValueError('not png: %s' % p)
    return list(struct.unpack('>II', head[16:24]))


# --------------------------------------------------------------------------
# 真源：注册表（数据面契约），不是本轮 manifest
# --------------------------------------------------------------------------
REGJ = read_json(REG)
XWORK = []
for n in REGJ['npcs']:
    work = n['id'].split('_')[0]
    if work in WORKS:
        for obj in (n.get('objects') or []):
            XWORK.append((n['id'], work, obj))

MAN = read_json(os.path.join(SPR, '_cross_works.json'))
ELEVMAN = read_json(os.path.join(ELEV, '_source.json'))

# 磁盘索引：work -> {名前缀: [文件]}
ON_DISK = {}
for w in WORKS:
    d = os.path.join(SPR, w)
    ON_DISK[w] = sorted(os.listdir(d)) if os.path.isdir(d) else []


def files_for(work, obj):
    """`<obj>_<i>.png`（多帧）或 `<obj>.png`（整图）都算命中。"""
    pat = re.compile('^%s(_\\d+)?\\.png$' % re.escape(obj))
    return [f for f in ON_DISK[work] if pat.match(f)]


def missing_of(pairs):
    """返回 pairs 里"没有落地文件"的那些（A 判据的**可复用内核**）。

    ★ 单独抽出来是为了让"判据有鉴别力"这件事能被**程序**证明（见 F 段）。
    """
    return [(nid, w, obj) for (nid, w, obj) in pairs if not files_for(w, obj)]


# --------------------------------------------------------------------------
# A 正控制
# --------------------------------------------------------------------------
print('=' * 74)
print('A 正控制：注册表声明的跨作品贴图必须**逐条**有落地文件')
print('=' * 74)
_miss = missing_of(XWORK)
check('A1 注册表里 %d 条「跨作品 NPC × 原作物件名」全部有落地 PNG'
      % len(XWORK), not _miss, '缺失=%s' % (_miss or '(无)'))

# 逐作计数（便于定位）
for w in WORKS:
    ids = sorted(set(nid for nid, ww, _ in XWORK if ww == w))
    objs = [o for _, ww, o in XWORK if ww == w]
    nf = sum(len(files_for(w, o)) for o in objs)
    check('A2[%s] %d 位 NPC / %d 个物件名，共落地 %d 张'
          % (w, len(ids), len(objs), nf),
          bool(objs) and all(files_for(w, o) for o in objs))

# --------------------------------------------------------------------------
# B 负控制
# --------------------------------------------------------------------------
print('=' * 74)
print('B 负控制：编造的名字必须落空')
print('=' * 74)
FAKE = [
    (None, 'ut', 'spr_zzz_no_such_sprite_71'),
    (None, 'hy', 'spr_zzz_no_such_sprite_71'),
    (None, 'ot', 'iocZzzNoSuchSprite71'),
    (None, 'os', 'zzz_no_such_npc_71'),
]
_fake_hit = [(w, o) for _, w, o in FAKE if files_for(w, o)]
check('B1 4 个编造名在磁盘上都不存在', not _fake_hit, '意外命中=%s' % (_fake_hit or '(无)'))

# 负控制必须真落进被测分支：造一条"声明名首字母改掉"的假条目，内核必须报红
_real = [p for p in XWORK if p[1] == 'ut'][:1]
if _real:
    nid, w, obj = _real[0]
    _tampered = [(nid, w, obj + '_X71')]
    _t = missing_of(_tampered)
else:
    _t = []
check('B2 把声明名改一个字后，缺失检测**必须报红**（证明内核不是在数空集）',
      bool(_real) and len(_t) == 1, '改后缺失=%s' % _t)

# A 判据对**空集**必须判"无需报红"但也不能被当成 PASS 的证据 ⇒ 显式打印非 no-op
check('B3 内核记账口非 no-op（空输入返回空、真输入返回真）',
      missing_of([]) == [] and len(_miss) == len(missing_of(XWORK)))
check('B4 A1 的输入不是空集合（否则 all([]) 恒真）', len(XWORK) >= 60,
      '实际 %d 条' % len(XWORK))

# --------------------------------------------------------------------------
# C 计数交叉（manifest 只是对账用）
# --------------------------------------------------------------------------
print('=' * 74)
print('C 对账：manifest 声明 vs 磁盘实际')
print('=' * 74)
C_DIFF = []
for w in WORKS:
    declared = MAN['landed'].get(w) or {}
    n_decl = sum(len(v) for v in declared.values())
    if n_decl != len(ON_DISK[w]):
        C_DIFF.append('%s 声明 %d / 磁盘 %d' % (w, n_decl, len(ON_DISK[w])))
check('C1 四作「manifest 文件数 == 磁盘文件数」', not C_DIFF, str(C_DIFF or '(一致)'))

_need_keys = set()
for w in WORKS:
    for o in MAN['need'][w]:
        _need_keys.add((w, o))
_declared_keys = set()
for w in WORKS:
    for o in (MAN['landed'].get(w) or {}):
        _declared_keys.add((w, o))
check('C2 landed 的键集 == need 的键集（不许"抽了但没记"或"记了但没抽"）',
      _declared_keys == _need_keys,
      '多=%s 少=%s' % (sorted(_declared_keys - _need_keys),
                       sorted(_need_keys - _declared_keys)))

# --------------------------------------------------------------------------
# D 电梯
# --------------------------------------------------------------------------
print('=' * 74)
print('D 电梯零件')
print('=' * 74)
E_PARTS = ELEVMAN['parts']
_d_miss = [nm for nm in E_PARTS if not [f for f in os.listdir(ELEV)
                                        if re.match('^%s_\\d+\\.png$' % re.escape(nm), f)]]
check('D1 15 个零件逐条有文件', len(E_PARTS) == 15 and not _d_miss,
      '零件=%d 缺=%s' % (len(E_PARTS), _d_miss or '(无)'))

_d_size = []
for nm, rec in sorted(E_PARTS.items()):
    for fr in rec['frames']:
        p = os.path.join(ELEV, fr['file'])
        if not os.path.isfile(p):
            _d_size.append('%s 缺文件' % fr['file'])
            continue
        w, h = png_size(p)
        if [w, h] != list(fr['size']):
            _d_size.append('%s 声明%s 实际%dx%d' % (fr['file'], fr['size'], w, h))
check('D2 每张电梯 PNG 的实际像素 == manifest 逐帧声明尺寸（真读 IHDR）',
      not _d_size, str(_d_size[:4] or '(全一致)'))

# ★ 反例钉住：manifest 里不许把 GameMaker 的**设计画布**尺寸当成 PNG 尺寸。
#   本轮第一版就是这么写的，被 D2 抓了个正着（bg_elevarmL 声明 68x41 实际 62x39）。
#   现在要求：如果两者不等，必须**分开两个字段**，且 size 用实际值。
_d_sem = []
for nm, rec in sorted(E_PARTS.items()):
    if 'gms_meta' not in rec:
        _d_sem.append('%s 缺 gms_meta' % nm)
    for fr in rec['frames']:
        p = os.path.join(ELEV, fr['file'])
        if os.path.isfile(p) and png_size(p) != list(fr['size']):
            _d_sem.append('%s size 字段不是实际像素' % fr['file'])
check('D2b size 字段是「实际像素」而非「GameMaker 设计画布」，且 gms_meta 另存',
      not _d_sem, str(_d_sem[:4] or '(语义正确)'))
check('D2c 确实存在"元数据 ≠ 实际像素"的零件（证明这条区分不是空谈）',
      any(rec['gms_meta'] != fr['size'] for rec in E_PARTS.values()
          for fr in rec['frames']),
      'bg_elevarmL 元数据=%s 实际=%s'
      % (E_PARTS['bg_elevarmL']['gms_meta'], E_PARTS['bg_elevarmL']['frames'][0]['size']))

# ★ 跨作品侧同款语义也要在 manifest 里写清（尺寸不在这里逐张比，只比"字段在位 + 与实际一致"）
_g_sem = []
for w in WORKS:
    for obj, fs in (MAN['png_sizes'].get(w) or {}).items():
        for f, sz in fs.items():
            p = os.path.join(SPR, w, f)
            if not os.path.isfile(p) or png_size(p) != list(sz):
                _g_sem.append('%s/%s' % (w, f))
check('D2d 跨作品 manifest 的 png_sizes 与磁盘逐张一致', not _g_sem,
      str(_g_sem[:4] or '(全一致)'))

_elev_on_disk = [f for f in os.listdir(ELEV) if f.endswith('.png')]
_n_elev_decl = sum(len(r['frames']) for r in E_PARTS.values())
check('D3 电梯 PNG 数 == manifest 声明数', len(_elev_on_disk) == _n_elev_decl,
      '磁盘 %d / 声明 %d' % (len(_elev_on_disk), _n_elev_decl))

check('D4 落点写清了"为什么不是 room_start"（原文可回查）',
      'room_start' in json.dumps(ELEVMAN['site'], ensure_ascii=False)
      and 'obj_mainchara' in json.dumps(ELEVMAN['site'], ensure_ascii=False))

# --------------------------------------------------------------------------
# E 计划 vs 注册表
# --------------------------------------------------------------------------
print('=' * 74)
print('E 计划与数据面契约一致')
print('=' * 74)
_plan = set((p['id'], p['work'], p['declared']) for p in MAN['plan'])
_reg = set(XWORK)
check('E1 manifest.plan 的 (id, work, 声明名) 集合 == 注册表推出来的集合',
      _plan == _reg,
      '多=%s 少=%s' % (sorted(_plan - _reg)[:3], sorted(_reg - _plan)[:3]))

_n_declared_in_src = sum(1 for p in MAN['plan'] if p['declared_in_source'])
check('E2 声明的名字**全部**在源清单里真实存在（不许凭空）',
      _n_declared_in_src == len(MAN['plan']),
      '%d/%d' % (_n_declared_in_src, len(MAN['plan'])))

_rules = sorted(set(p['rule'] for p in MAN['plan'] if p['rule']))
check('E3 每条兄弟帧都记了用哪条规则找到的（可审计）',
      all(p['rule'] or not p['also'] for p in MAN['plan']),
      '出现过的规则=%s' % _rules)

# --------------------------------------------------------------------------
# G 电梯数据面（连接 / 几何 / 外景 / 内部动画）  ★ 素材之外的"规格"面
# --------------------------------------------------------------------------
print('=' * 74)
print('G 电梯数据面：ut <-> ot 的这条连接')
print('=' * 74)
LINKP = os.path.join(ELEV, '_link.json')
LINK = read_json(LINKP) if os.path.isfile(LINKP) else None
check('G1 电梯数据面 _link.json 存在且 schema 对得上',
      isinstance(LINK, dict) and LINK.get('schema_version') == 1
      and LINK.get('kind') == 'cross_work_link',
      'file=%s' % os.path.basename(LINKP))

_low = ((LINK or {}).get('endpoints') or {}).get('lower') or {}
_site = ELEVMAN['site']
check('G2 下端落点与零件表 _source.json#site 完全一致（两处不许各说各话）',
      _low.get('room_index') == _site['room_index']
      and _low.get('room_resource') == _site['room_name']
      and list(_low.get('room_size') or []) == list(_site['size']),
      '%s:%s %s' % (_low.get('room_index'), _low.get('room_resource'),
                    _low.get('room_size')))

# ★ 跨轮次交叉验证：第66轮大图的节点 ut:4（读仓库内文件，不碰外部盘）
BM66 = os.path.join(ROOT, 'code-quality-audit', '第66轮-大图连通与mod并入',
                    '_evidence', 'bigmap66.json')
_bm = read_json(BM66) if os.path.isfile(BM66) else {}
_n4 = None
for _n in (_bm.get('nodes') or []):
    if _n.get('id') == 'ut:4':
        _n4 = _n
        break
check('G3 下端落点与第66轮大图节点 ut:4 一致（跨轮次交叉验证）',
      _n4 is not None
      and _n4['name'] == _low.get('room_resource')
      and [_n4['w'], _n4['h']] == list(_low.get('room_size') or []),
      'bigmap66 ut:4 = %s' % json.dumps(
          {'name': _n4['name'], 'size': [_n4['w'], _n4['h']]} if _n4 else None,
          ensure_ascii=False))


def geom_consistent(shaft):
    """井道三数自洽：`speed*ascend == height` 且 `screens == height/screen_px`。

    ★ 抽成函数是为了让"判据有鉴别力"能被**程序**证明（G4n 三条负控制都走它）。
    """
    try:
        sp, du = float(shaft['speed_px_per_s']), float(shaft['ascend_s'])
        hp, sc = float(shaft['height_px']), float(shaft['screens'])
        spx = float(shaft['screen_px'])
    except (KeyError, TypeError, ValueError):
        return False
    if sp <= 0 or du <= 0 or spx <= 0:
        return False
    return abs(sp * du - hp) <= 1e-6 and abs(hp / spx - sc) <= 1e-6


def high_ok(shaft):
    """「很高」的**量化**判据：屏数 ≥ 下限。（用户只说"很高"，这里把形容词变阈值。）"""
    try:
        return (float(shaft['screens']) >= float(shaft['min_screens_for_high'])
                and float(shaft['min_screens_for_high']) > 0)
    except (KeyError, TypeError, ValueError):
        return False


_sh = (LINK or {}).get('shaft') or {}
check('G4 井道几何自洽：速度 × 时长 == 高度，屏数 == 高度 / 屏高',
      geom_consistent(_sh),
      '%.1f px/s × %.1f s = %.1f px；%.1f / %.1f = %.1f 屏'
      % (_sh.get('speed_px_per_s', -1), _sh.get('ascend_s', -1),
         _sh.get('height_px', -1), _sh.get('height_px', -1),
         _sh.get('screen_px', -1), _sh.get('screens', -1)))
check('G5 「很高」过量化下限（不是形容词，是可测阈值）',
      high_ok(_sh),
      '%.1f 屏 ≥ 下限 %.1f'
      % (_sh.get('screens', -1), _sh.get('min_screens_for_high', -1)))

# ★ 负控制：证明 G4/G5 的内核真在判，而不是"看着在守"
_b1 = dict(_sh); _b1['height_px'] = float(_sh.get('height_px') or 0) + 1.0
_b2 = dict(_sh); _b2['screens'] = float(_sh.get('screens') or 0) - 1.0
_b3 = dict(_sh)
_b3['min_screens_for_high'] = float(_sh.get('screens') or 0) + 1.0
check('G4n 几何内核有鉴别力（改 height / 改 screens 必须报红；抬高下限必须不过）',
      (not geom_consistent(_b1)) and (not geom_consistent(_b2))
      and (not high_ok(_b3)),
      '三次负输入都落进被测分支')

# --- 零件内外分工：15 件恰好全覆盖、不重叠、无凭空 -------------------------
_pc = (LINK or {}).get('parts_cover') or {}
_ext = list(_pc.get('exterior') or [])
_cab = list(_pc.get('cabin') or [])
_shp = list(_pc.get('shaft') or [])
_all = _ext + _cab + _shp
check('G6 15 个零件内外分工恰好全覆盖（无重复 / 无凭空 / 无遗漏）',
      len(_all) == len(set(_all)) == len(E_PARTS) and set(_all) == set(E_PARTS),
      '外景 %d + 轿厢 %d + 井道 %d = %d（真源 %d）'
      % (len(_ext), len(_cab), len(_shp), len(_all), len(E_PARTS)))

# --- 内部动画时长：四拍之和 == total，且"上升"拍 == 几何的 ascend_s --------
_an = ((LINK or {}).get('interior') or {}).get('animation') or {}
_ph = _an.get('phases') or []
_sum = sum(int(p.get('ms') or 0) for p in _ph)
_asc = [int(p.get('ms') or 0) for p in _ph if p.get('id') == 'ascend']
check('G7 四拍时长之和 == total_ms，且"上升"拍 == 几何的 ascend_s（动画不许与几何脱钩）',
      bool(_ph) and _sum == int(_an.get('total_ms') or -1)
      and len(_asc) == 1
      and abs(_asc[0] / 1000.0 - float(_sh.get('ascend_s') or 0)) <= 1e-9,
      '合计 %d ms；上升拍 %s ms' % (_sum, _asc))

# --- 诚实判据（★ 见文件头 ⑥）--------------------------------------------
_wr = (LINK or {}).get('wiring') or {}
check('G8 接线状态如实写 spec_only，且 not_yet 非空（不许谎称"电梯已经能坐了"）',
      _wr.get('status') == 'spec_only' and bool(_wr.get('not_yet')),
      'status=%r；not_yet %d 条'
      % (_wr.get('status'), len(_wr.get('not_yet') or [])))

# --------------------------------------------------------------------------
# F 判据自身体检
# --------------------------------------------------------------------------
print('=' * 74)
print('F 判据自身体检')
print('=' * 74)
check('F1 四个作品目录都非空（"原文目录真被读到"）',
      all(ON_DISK[w] for w in WORKS),
      str(dict((w, len(ON_DISK[w])) for w in WORKS)))
check('F2 本轮判据条数非 0，且经 check() 记账', NCHECK >= 13, 'NCHECK=%d' % NCHECK)
check('F3 判据名里没有自带的计数标记字样（防污染 run_all 的 PASS 计数）',
      not [f for f in FAILS if f.startswith('判据名字面量污染')])

print('')
print('---- 第71轮 素材锁：%d 项判据，FAIL=%d ----' % (NCHECK, len(FAILS)))
if FAILS:
    for f in FAILS:
        print('   FAIL: %s' % f)
sys.exit(0 if not FAILS else 1)
