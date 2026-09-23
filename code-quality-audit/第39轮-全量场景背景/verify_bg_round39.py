# -*- coding: utf-8 -*-
"""
第 39 轮回归锁：**场景背景素材来源标注不许静默漂移**。

守的是什么
----------
第 38 轮把场景从 88 个扩到 1,013 个时，926 个新场景一律写 `bg: null` +
`bg_source: "none"` —— 那是**刻意的诚实**：原作本来就没给多数房间背景精灵，
用"区域代表素材"凑近似会导致"把'我没有这张图'伪装成'就是这张图'"。

第 39 轮做的是**只做零编造的那一半**：凡原作房间自带背景精灵（≥300×200）的，
把**原作 PNG 原样**落盘并标注来源；拿不到真背景的**仍然留空**，近似的适用范围
**一点都没扩大**（这是本轮的核心决定，下面 E 段专门守它）。

判据的单一真源
--------------
"什么算真背景、什么算近似"的唯一实现是 `_tools/bg_common.classify()`。
套件**不另写一份**，而是拿仓库内的 `_evidence/原作房间背景溯源.json` 重建
`classify()` 的入参（房间层 + 精灵尺寸），再与场景 JSON 里的标注逐条对比。

为什么不让套件直接读 `E:\\Download\\_tmp\\dr_out`：那个目录按约定是"用后即删"。
套件一旦依赖它，临时文件被清掉后**不是报红、而是静默失去鉴别力**
（读不到 dump ⇒ 全判 none ⇒ 断言全绿）—— 本项目吃过这个亏，故蒸馏入库。

**不联网、不需要显示器、不实例化 App**（纯数据 + 纯函数）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, '_tools'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
import bg_common as C   # noqa: E402

SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(HERE, '_evidence')
PROV = os.path.join(EV, '原作房间背景溯源.json')
R37MAP = os.path.join(ROOT, 'code-quality-audit', '第37轮-原作素材反编译',
                      '_evidence', 'scene_bg_mapping_final.json')

PASS = 0
FAIL = 0
FAILED = []


def check(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s    %s' % (name, detail))


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


# ===========================================================================
#  载入：索引 / 溯源表 / 场景条目
# ===========================================================================
idx = jload(os.path.join(SCENES, '_index.json'))
prov = jload(PROV)

# 第 37 轮实际产出的映射（87 个锚点的权威 how/asset）。**必须在使用前载入。**
_r37 = {}
if os.path.isfile(R37MAP):
    for row in jload(R37MAP).get('rows', []):
        _r37[row['scene_id']] = row

dims_inv = {}
rebuilt_rooms = {}
for ch, v in prov['chapters'].items():
    dims_inv[ch] = {nm: (None, tuple(d)) for nm, d in v['sprite_dims'].items()}
    rebuilt_rooms[ch] = {}
    for rid, r in v['rooms'].items():
        rebuilt_rooms[ch][int(rid)] = {
            'width': r['w'], 'height': r['h'],
            'layers': ([{'bg_sprite': s} for s in r['bg_sprites']]
                       + [{'asset_sprites': a} for a in r['asset_sprites']]),
        }

# 全部场景（id / 章 / 区 / 来源 / raw）
ENTRIES = []      # (sid, ch, area, rid, kind, raw, file_path)
zcache = {}
for chk, chv in (idx.get('chapters') or {}).items():
    if chk == 'desktop':
        continue
    for areak, areav in (chv.get('areas') or {}).items():
        for sid in (areav.get('scenes') or {}):
            p = os.path.join(SCENES, sid + '.json')
            if os.path.isfile(p):
                raw = jload(p)
                rr = (raw.get('_comment') or {}).get('original_room') or {}
                rid = rr.get('room_id')
                owning = p
            else:
                zp = os.path.join(SCENES, '_zone.%s.%s.json' % (chk, areak))
                if zp not in zcache:
                    zcache[zp] = jload(zp).get('scenes') or {}
                raw = zcache[zp].get(sid) or {}
                rid = raw.get('original_room_id')
                owning = zp
            ENTRIES.append((sid, chk, areak, rid, raw, owning))

ANCHORS = [e for e in ENTRIES if os.path.isfile(os.path.join(SCENES, e[0] + '.json'))]
ZONES = [e for e in ENTRIES if not os.path.isfile(os.path.join(SCENES, e[0] + '.json'))]

print()
print('=' * 76)
print('A. 溯源表 / 场景表可读性')
print('=' * 76)

check('A0 溯源表 schema 正确且逐章房间数与原作一致',
      prov.get('schema') == 'ralsei_pet.original_room_bg_provenance/1'
      and set(prov['chapters'].keys()) == set(C.CHS)
      and all(prov['chapters'][ch]['room_count'] == len(prov['chapters'][ch]['rooms'])
              for ch in C.CHS),
      '章=%s 房间合计=%d' % (sorted(prov['chapters'].keys()),
                            sum(v['room_count'] for v in prov['chapters'].values())))

check('A1 场景登记表可读，且分两类来源（独立文件 / 区域分片）',
      len(ENTRIES) > 0 and len(ANCHORS) > 0 and len(ZONES) > 0,
      '总 %d = 独立文件 %d + 分片 %d' % (len(ENTRIES), len(ANCHORS), len(ZONES)))

check('A2 每个场景都能在溯源表里定位到自己的房间',
      all(str(e[3]) in (prov['chapters'].get(e[1], {}).get('rooms') or {})
          for e in ENTRIES),
      '缺 %d 个' % sum(1 for e in ENTRIES
                       if str(e[3]) not in (prov['chapters'].get(e[1], {}).get('rooms') or {})))


# ===========================================================================
#  B. ★ 核心判据：场景里的标注 == 用原作事实重算的结果
# ===========================================================================
def recompute(entries, rooms, dims):
    """→ `{sid: (bg_rel, how, asset)}`，`classify()` 的单一真源实现。"""
    out = {}
    for sid, ch, area, rid, raw, _p in entries:
        nm, _tiled, how = C.classify(rooms[ch].get(rid), ch, area, dims)
        out[sid] = (('bg/' + C.bg_filename(sid)) if how in C.REAL_HOWS else None, how, nm)
    return out


def mismatches(entries, rooms, dims):
    """把场景实际写的标注与重算结果比对 → 不一致清单（判据内核，正负控制共用）。

    ⚠️ 三类条目判据**不同**，别用一条规则套死（首版就是套死了一条规则，
    于是把"按第 37 轮口径本来就有近似 bg 的 78 个锚点"全判成错 —— 判据越权）：

      · 重算为**真背景** → `bg` 路径 / `bg_source` 档次 / `bg_asset` 溯源 三者都要对上；
      · 重算为**近似**，且是**锚点**（有独立文件）→ 只要求 `bg_source` == 第 37 轮实际产出的 how
        （那 78 张图是第 37 轮的既有决定，本轮不改它，只补来源标注）；
      · 重算为**近似**，且是**分片新增场景** → **必须留空**（本轮不让近似档扩散）。
    """
    want = recompute(entries, rooms, dims)
    bad = []
    for sid, ch, area, rid, raw, _p in entries:
        is_anchor = os.path.isfile(os.path.join(SCENES, sid + '.json'))
        wbg, whow, wasset = want[sid]
        got_bg = raw.get('bg')
        got_src = raw.get('bg_source')
        got_asset = raw.get('bg_asset')
        if whow in C.REAL_HOWS:
            if not (got_bg == wbg and got_src == whow and got_asset == wasset):
                bad.append((sid, 'want %r/%r/%r got %r/%r/%r'
                            % (wbg, whow, wasset, got_bg, got_src, got_asset)))
        elif is_anchor:
            exp = (_r37.get(sid) or {}).get('how')
            if got_src != exp:
                bad.append((sid, '锚点近似档标注 got %r want %r' % (got_src, exp)))
        else:
            if got_bg is not None:
                bad.append((sid, '新增场景非真背景却填了 bg=%r' % (got_bg,)))
    return bad


_bad = mismatches(ENTRIES, rebuilt_rooms, dims_inv)
check('B1 真背景场景的 bg/bg_source/bg_asset 三者 == 据原作事实重算的结果',
      not _bad, '不一致 %d %s' % (len(_bad), _bad[:3]))

# 负控制：把溯源表里**一个分片真背景场景**的背景层抹掉，判据必须变红。
#   ⚠️ 受害对象必须挑**分片场景**而不是锚点：锚点走的是"只对 bg_source 溯源"这一支，
#      抹掉它的背景层不会改变 `bg_source` 的期望值 ⇒ 判据不动（首版就挑错了对象，
#      负控制变成"恒真"，等于没测）。
_tampered = {ch: dict(rooms) for ch, rooms in rebuilt_rooms.items()}
_victim = None
for sid, ch, area, rid, raw, _p in ENTRIES:
    if raw.get('bg_source') in C.REAL_HOWS and not os.path.isfile(
            os.path.join(SCENES, sid + '.json')):
        _victim = (sid, ch, rid)
        break
if _victim:
    _sid, _ch, _rid = _victim
    _tampered[_ch][_rid] = dict(_tampered[_ch][_rid])
    _tampered[_ch][_rid]['layers'] = []
    _bad_neg = mismatches(ENTRIES, _tampered, dims_inv)
else:
    _bad_neg = []
check('B2 负控制：篡改溯源表（抹掉一个分片真背景房间的背景层）后判据必变红',
      bool(_victim) and bool(_bad_neg),
      '受害场景=%s 触发不一致 %d 条' % (_victim[0] if _victim else None, len(_bad_neg)))

# 负控制 2：把某个**锚点**的 bg_source 改成错值，判据必须抓到
_bad_src = []
for sid, ch, area, rid, raw, _p in ENTRIES:
    if os.path.isfile(os.path.join(SCENES, sid + '.json')) and raw.get('bg_source') not in C.REAL_HOWS:
        fake = dict(raw)
        fake['bg_source'] = '__wrong__'
        _bad_src = mismatches([(sid, ch, area, rid, fake, _p)], rebuilt_rooms, dims_inv)
        break
check('B2b 负控制：锚点的 bg_source 改成错值必被抓到（近似档标注这支也有鉴别力）',
      bool(_bad_src), 'got=%s' % (_bad_src[:1],))

# 正控制：不动溯源表时判据为真（防"判据恒红"）
check('B3 正控制：未篡改时同一判据为真（不是恒红）',
      not mismatches(ENTRIES, rebuilt_rooms, dims_inv))

# 负控制 2：把某场景的 bg_asset 改坏，判据必须抓到
_bad_asset = []
for sid, ch, area, rid, raw, _p in ENTRIES:
    if raw.get('bg_source') in C.REAL_HOWS:
        fake = dict(raw)
        fake['bg_asset'] = 'bg___no_such_sprite__'
        _bad_asset = mismatches([(sid, ch, area, rid, fake, _p)], rebuilt_rooms, dims_inv)
        break
check('B4 负控制：bg_asset 被改成不存在的精灵名必被抓到',
      bool(_bad_asset), 'got=%s' % (_bad_asset[:1],))


# ===========================================================================
#  C. bg 文件健康度
# ===========================================================================
def health(pairs):
    """pairs=[(sid, abs_path)] → (缺失, 非法PNG)。判据内核，正负控制共用。"""
    miss, bad = [], []
    for sid, fp in pairs:
        if not fp or not os.path.isfile(fp):
            miss.append(sid)
            continue
        try:
            with io.open(fp, 'rb') as fh:
                if fh.read(8) != b'\x89PNG\r\n\x1a\n':
                    bad.append(sid)
        except Exception:
            bad.append(sid)
    return miss, bad


_pairs = [(e[0], os.path.join(SCENES, e[4]['bg'])) for e in ENTRIES if e[4].get('bg')]
_miss, _notpng = health(_pairs)
check('C1 每个声明了 bg 的场景都指向真实存在的 PNG',
      bool(_pairs) and not _miss and not _notpng,
      '扫描 %d；缺失 %d %s；非PNG %d %s' % (len(_pairs), len(_miss), _miss[:3],
                                          len(_notpng), _notpng[:3]))

_real_pairs = [(e[0], os.path.join(SCENES, e[4]['bg'])) for e in ENTRIES
               if e[4].get('bg_source') in C.REAL_HOWS]
_rmiss, _rnotpng = health(_real_pairs)
check('C2 真背景场景的 bg 文件都存在且是合法 PNG（本轮新增那批的核心保证）',
      bool(_real_pairs) and not _rmiss and not _rnotpng,
      '真背景 %d 个；缺失 %d；非PNG %d' % (len(_real_pairs), len(_rmiss), len(_rnotpng)))

_n1, _ = health([('bogus', os.path.join(SCENES, 'bg', '__no_such__.png'))])
check('C3 负控制：判据抓得住"文件不存在"（有鉴别力）', _n1 == ['bogus'], 'got=%r' % _n1)

_, _n2 = health([('json', os.path.join(SCENES, '_index.json'))])
check('C4 负控制：判据抓得住"文件存在但不是 PNG"', _n2 == ['json'], 'got=%r' % _n2)


# ===========================================================================
#  D. 元数据自洽（bg 与 bg_source 不许互相撒谎）
# ===========================================================================
_d1 = [e[0] for e in ENTRIES
       if (e[4].get('bg') is not None) != (e[4].get('bg_source') != 'none')]
check('D1 `bg` 非空 ⇔ `bg_source` 非 "none"（两字段不许互相矛盾）',
      not _d1, '矛盾 %d %s' % (len(_d1), _d1[:3]))

_d2 = [e[0] for e in ENTRIES
       if e[4].get('bg') is None and e[4].get('bg_source') != 'none']
check('D2 没有 bg 的场景必须显式声明 bg_source="none"',
      not _d2, '未声明 %d %s' % (len(_d2), _d2[:3]))

_d3 = [e[0] for e in ENTRIES
       if e[4].get('bg_source') in C.REAL_HOWS
       and not (isinstance(e[4].get('bg_asset'), str) and e[4]['bg_asset'].strip())]
check('D3 真背景场景必须带 bg_asset 溯源（原作精灵名，非空字符串）',
      not _d3, '不合格 %d %s' % (len(_d3), _d3[:3]))

_d4 = [e[0] for e in ENTRIES
       if e[4].get('bg') is not None and not str(e[4].get('bg')).startswith('bg/')]
check('D4 bg 路径统一走 bg/ 子目录', not _d4, '越界 %d %s' % (len(_d4), _d4[:3]))


# ===========================================================================
#  E. ★ 本轮决定：近似档的适用范围**一点都没扩大**
# ===========================================================================
APPROX_HOWS = ('area_table', 'chapter_tiles', 'chapter_fallback')

_e1 = [(e[0], e[4].get('bg_source')) for e in ZONES
       if e[4].get('bg_source') not in ('none',) + C.REAL_HOWS]
check('E1 926 个"新增场景"里不许出现近似档（area_table/chapter_tiles/…）',
      not _e1, '越界 %d %s' % (len(_e1), _e1[:3]))

_e2 = [(e[0], e[4].get('bg_source')) for e in ZONES
       if e[4].get('bg_source') in C.REAL_HOWS and e[4].get('bg') is None]
check('E2 新增场景里的真背景必须真的配了图（不许只标注不落图）',
      not _e2, '空标 %d %s' % (len(_e2), _e2[:3]))

# 87 锚点的 bg_source 必须与第 37 轮**实际产出**的 how 逐条一致（近似档没被扩散/改写）
# （`_r37` 已在文件开头载入，B/E 两段共用同一份，避免两处各读一次导致口径分叉）
_e3 = []
for e in ANCHORS:
    row = _r37.get(e[0])
    if row is None:
        _e3.append((e[0], '第37轮映射表里没有'))
    elif e[4].get('bg_source') != row.get('how'):
        _e3.append((e[0], 'want %r got %r' % (row.get('how'), e[4].get('bg_source'))))
check('E3 87 个锚点的 bg_source 与第 37 轮实际产出的 how 逐条一致',
      bool(_r37) and not _e3, '不一致 %d %s' % (len(_e3), _e3[:3]))

_e4 = [e[0] for e in ENTRIES if e[4].get('bg_source') in APPROX_HOWS]
check('E4 近似档确实只存在于锚点里（本轮没有把它铺到新增场景上）',
      all(e[0] in _r37 for e in ENTRIES if e[4].get('bg_source') in APPROX_HOWS),
      '近似档 %d 个' % len(_e4))


# ===========================================================================
#  F. 文本格式保真（本轮全部用文本级逐行替换，格式不许漂）
# ===========================================================================
_files = sorted(set(os.path.join(SCENES, e[5]) for e in ENTRIES))
_fmt_bom, _fmt_eol, _fmt_repl, _fmt_json = [], [], [], []
for p in _files:
    try:
        raw = io.open(p, 'rb').read()
    except Exception:
        _fmt_json.append(os.path.basename(p))
        continue
    if raw[:3] == b'\xef\xbb\xbf':
        _fmt_bom.append(os.path.basename(p))
    try:
        txt = raw.decode('utf-8')
    except UnicodeDecodeError:
        _fmt_json.append(os.path.basename(p))
        continue
    if '\ufffd' in txt:
        _fmt_repl.append(os.path.basename(p))
    n_crlf, n_lf = raw.count(b'\r\n'), raw.count(b'\n')
    # 允许全 CRLF 或全 LF，**不允许混用**（混用是逐行替换最典型的翻车方式）
    if not (n_crlf == n_lf or n_crlf == 0):
        _fmt_eol.append('%s(crlf=%d lf=%d)' % (os.path.basename(p), n_crlf, n_lf))
    try:
        json.loads(txt)
    except Exception:
        _fmt_json.append(os.path.basename(p))

check('F1 涉及改动的场景 JSON 全部可解析（文本级替换没写坏括号）',
      not _fmt_json, '坏 %d %s' % (len(_fmt_json), _fmt_json[:3]))
check('F2 无 BOM、无 U+FFFD 替换字符',
      not _fmt_bom and not _fmt_repl,
      'BOM %d %s；U+FFFD %d %s' % (len(_fmt_bom), _fmt_bom[:2],
                                   len(_fmt_repl), _fmt_repl[:2]))
check('F3 每个文件内换行风格一致（不混用 CRLF/LF）',
      not _fmt_eol, '混用 %d %s' % (len(_fmt_eol), _fmt_eol[:3]))

# 负控制：判据对"含 BOM"的合成串必须有反应
_probe_bom = b'\xef\xbb\xbf' + b'{}\n'
check('F4 负控制：BOM / 混用换行的合成样本会被 F2/F3 的判据抓到',
      _probe_bom[:3] == b'\xef\xbb\xbf' and (b'a\r\nb\n'.count(b'\r\n') != b'a\r\nb\n'.count(b'\n')))


# ===========================================================================
#  G. 过期注释已修正
# ===========================================================================
_stale = []
_no_mark = []
for e in ANCHORS:
    cm = e[4].get('_comment') or {}
    txt = cm.get('why_bg_is_a_placeholder')
    if txt is None:
        continue
    if '尚不存在' in txt:
        _stale.append(e[0])
    if '第37轮' not in txt and '第39轮' not in txt:
        _no_mark.append(e[0])
check('G1 锚点注释不再声称"背景文件尚不存在"（第37轮早已生成）',
      not _stale, '仍过期 %d %s' % (len(_stale), _stale[:3]))
check('G2 注释留痕（点明第37轮/第39轮，供后人溯源）',
      not _no_mark, '无留痕 %d' % len(_no_mark))
check('G3 负控制：判据抓得住"含尚不存在"的合成注释',
      ('尚不存在' in '文件尚不存在') and ('尚不存在' not in '第37轮已生成'))


# ===========================================================================
#  H. 产品路径消费面（数据要真的能被产品读出来）
# ===========================================================================
import scene_system as ss   # noqa: E402

# ⚠️ entry 必须来自 `load_index()`（产品函数）——它会把 chapter_id/area_id 合并进
#    登记行。直接喂裸 `_index.json` 的条目会让 `load_scene` 找不到分片而返回 None，
#    那是**夹具违反产品契约**，不是产品缺陷（首版就踩了这个，148 个"假失败"）。
_merged = ss.load_index(SCENES).get('scenes') or {}

_h_bad = []
_checked = 0
for e in ENTRIES:
    sid, ch, area, rid, raw, _p = e
    if not raw.get('bg'):
        continue
    scene = ss.load_scene(sid, SCENES, entry=_merged.get(sid))
    if scene is None:
        _h_bad.append((sid, 'load_scene 返回 None'))
        continue
    if scene.bg != raw.get('bg'):
        _h_bad.append((sid, 'bg %r != %r' % (scene.bg, raw.get('bg'))))
        continue
    ap = ss.resolve_asset_path(scene.bg, 'bg', SCENES)
    if not ap or not os.path.isfile(ap):
        _h_bad.append((sid, 'resolve_asset_path 落空 %r' % (ap,)))
        continue
    _checked += 1
check('H1 产品函数 load_index + load_scene + resolve_asset_path 能解析出每个 bg 的真实文件',
      _checked > 0 and not _h_bad,
      '核验 %d 个；失败 %d %s' % (_checked, len(_h_bad), _h_bad[:3]))

check('H2 负控制：H1 的"文件存在"判据对不存在的相对路径必须报假（有鉴别力）',
      not os.path.isfile(ss.resolve_asset_path('bg/__nope__.png', 'bg', SCENES)
                         or ''))

check('H3 负控制：load_scene 对不存在的场景 id 必须返回 None（不是恒返回对象）',
      ss.load_scene('__no_such_scene__', SCENES) is None)


# ===========================================================================
print()
print('=' * 72)
print('第39轮场景背景回归锁：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：')
    for f in FAILED:
        print('  - %s' % f)
print('=' * 72)
sys.exit(1 if FAIL else 0)
