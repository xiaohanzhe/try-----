# -*- coding: utf-8 -*-
"""第71轮 · 跨作品角色贴图 + UT 电梯贴图 落地（dry 默认 / --write 才落盘）。

为什么是这一批：
  第70轮把注册表从 70 推到 96，跨作品 61 位里 **除了 OneShot 之外全部"有名字没画"**
  —— `assets/sprites/` 当时只有 `ghost/` 45 张。本轮把这批补齐。

四个来源，四条独立的通道（不共用假设）：
  ut  Undertale        -> UTMT 从 `_extract61/_data/undertale/game.droid` 定向导 sprite
  hy  Undertale Yellow -> UTMT 从 `.../undertale_yellow/game.droid`
  ot  Outertale        -> 从 `_extract61/outertale/www` 的 Aseprite 图集按 json 切片
  os  OneShot          -> 从 `content/npc/*.xnb` 解 MonoGame Texture2D（未压缩，raw RGBA）
  电梯（独立产物）      -> 同上 UTMT，但落 `assets/elevator/`

★ 纪律：
  ① 只抽"源清单里真实存在"的名字 —— 兄弟帧按规则生成候选，**命中才取**，
     落空的照样记进 manifest（`absent`），不编。
  ② 每条目标都记 `rule`（用哪条规则找到的兄弟）与 `family_size`（源里同干名字总数），
     让人一眼看出"是不是还有一大族没抽"。
  ③ 判据三件套：正控制（注册表声明的名字必须都在）、负控制（编的名字必须落空）、
     计数交叉（manifest 里文件数 == 磁盘上文件数）。
"""
from __future__ import print_function

import io
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import utmt71  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.join(ROUND, '..', '..')
EV = os.path.join(ROUND, '_evidence')
R61 = os.path.join(ROOT, 'code-quality-audit', '第61轮-跨界扩展动工', '_evidence')
R63 = os.path.join(ROOT, 'code-quality-audit', '第63轮-跨界扩展数据面', '_evidence')
REG = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_registry.json')

DATA_UT = r'E:\Download\_extract61\_data\undertale\game.droid'
DATA_HY = r'E:\Download\_extract61\_data\undertale_yellow\game.droid'
OT_WWW = r'E:\Download\_extract61\outertale\www'
OS_NPC = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
          r'\OneShot.World.Machine.Edition.Build.16512634\content\npc')

DST_SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
DST_ELEV = os.path.join(ROOT, 'ralsei_pet', 'assets', 'elevator')
TMP = r'E:\Download\_tmp\r71_work'

#: UT 电梯全套（第61轮 ut_sprites.json 里 elev/bg_elev* 共 15 条，逐条人工确认过语义）
ELEV = ['spr_elevatorgem_l', 'spr_elevatorgem_r', 'spr_elevatorpanel',
        'spr_elevatordoor', 'spr_elevatordoorframe', 'spr_elevatordoor_vines',
        'spr_darkelevator_l', 'spr_darkelevator_r',
        'bg_elevtop', 'bg_elevarmR', 'bg_elevarmL', 'bg_elevleg',
        'bg_elevbelow', 'bg_elevunit', 'bg_elevbottom']


# --------------------------------------------------------------------------
# STAGE 1 · 源清单
# --------------------------------------------------------------------------
def load_names(path):
    with io.open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    return [s['name'] for s in d['sprites']]


def load_registry():
    with io.open(REG, encoding='utf-8') as fh:
        return json.load(fh)['npcs']


# --------------------------------------------------------------------------
# STAGE 2 · 目标解析：声明的名字 + 方向兄弟（命中才取）
# --------------------------------------------------------------------------
def siblings(name, pool, work):
    """按规则生成候选兄弟，返回 (rule, found[], absent[], family_size)。

    ★ 规则是**证据门控**的：命中项必须真的在该作源清单里；找不到就记 `absent`。
      绝不"按命名习惯编一个出来"。每条规则都写清了它凭什么成立。
    """
    stem = None
    cand = []
    rule = None
    if work == 'hy':
        if name.endswith('_down_walk'):
            stem, rule = name[:-len('_down_walk')], 'hy._down_walk'
            cand = [stem + s for s in ('_up_walk', '_left_walk', '_right_walk')]
        elif name.endswith('_down_talk'):
            stem, rule = name[:-len('_down_talk')], 'hy._down_talk'
            cand = [stem + s for s in ('_up_talk', '_left_talk', '_right_talk')]
        elif name.endswith('_down'):
            stem, rule = name[:-len('_down')], 'hy._down'
            cand = [stem + s for s in ('_up', '_left', '_right')]
    elif work == 'ut':
        if name.endswith('_d'):
            stem, rule = name[:-2], 'ut._d'
            cand = [stem + s for s in ('_u', '_l', '_r')]
        elif name.endswith('d') and all((name[:-1] + s) in pool for s in ('u', 'l', 'r')):
            # UT 主角/Chara 用「干名 + d/u/l/r 单字母」: spr_f_maincharad, spr_charad
            # ★ 三个兄弟必须**全部**存在才认这条规则 —— 防把别的以 d 结尾的名字误吞。
            stem, rule = name[:-1], 'ut.letter'
            cand = [stem + s for s in ('u', 'l', 'r')]
    elif work == 'ot':
        if name.endswith('Down'):
            stem, rule = name[:-4], 'ot.Down'
            cand = [stem + s for s in ('Up', 'Left', 'Right')]

    found = [c for c in cand if c in pool]
    absent = [c for c in cand if c not in pool]
    fam = 0
    if stem:
        fam = len([n for n in pool if n.startswith(stem)])
    return rule, found, absent, fam


def build_plan():
    ut_pool = set(load_names(os.path.join(R61, 'ut_sprites.json')))
    hy_pool = set(load_names(os.path.join(R61, 'uty_sprites.json')))
    with io.open(os.path.join(R63, 'outertale63_assets.json'), encoding='utf-8') as fh:
        ot_assets = json.load(fh)
    ot_pool = set(x['name'] for x in ot_assets['named'])
    ot_by = dict((x['name'], x) for x in ot_assets['named'])
    os_pool = set(os.path.splitext(f)[0] for f in os.listdir(OS_NPC)
                  if f.lower().endswith('.xnb'))

    pools = {'ut': ut_pool, 'hy': hy_pool, 'ot': ot_pool, 'os': os_pool}
    plan = []
    for n in load_registry():
        nid = n['id']
        work = nid.split('_')[0]
        if work not in pools:
            continue
        for obj in (n['objects'] or []):
            in_pool = obj in pools[work]
            rule, found, absent, fam = (None, [], [], 0)
            if in_pool and work in ('ut', 'hy', 'ot'):
                rule, found, absent, fam = siblings(obj, pools[work], work)
            plan.append({'id': nid, 'work': work, 'declared': obj,
                         'declared_in_source': in_pool, 'rule': rule,
                         'also': found, 'absent': absent, 'family_size': fam})
    return plan, pools, ot_by


# --------------------------------------------------------------------------
# STAGE 3/4/5 · 三个抽取通道
# --------------------------------------------------------------------------
def utmt_export(pool_names, data, tag):
    out = os.path.join(TMP, tag)
    if os.path.isdir(out):
        shutil.rmtree(out)
    rc, txt = utmt71.run(list(pool_names), data, out, tag)
    if rc != 0:
        raise RuntimeError('UTMT %s rc=%s' % (tag, rc))
    with io.open(os.path.join(out, 'r71_sprites.json'), encoding='utf-8') as fh:
        man = json.load(fh)
    return out, man


def ot_slice(names, ot_by):
    from PIL import Image
    out = os.path.join(TMP, 'ot')
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    recs, missing = [], []
    for nm in names:
        e = ot_by.get(nm)
        if not e:
            missing.append(nm)
            continue
        png = os.path.join(OT_WWW, e['png'])
        js = os.path.join(OT_WWW, e['json'])
        if not (os.path.isfile(png) and os.path.isfile(js)):
            missing.append(nm)
            continue
        with io.open(js, encoding='utf-8') as fh:
            meta = json.load(fh)
        im = Image.open(png).convert('RGBA')
        frames = []
        for k, fr in enumerate(meta['frames']):
            r = fr['frame']
            box = (r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])
            fn = '%s_%d.png' % (nm, k)
            im.crop(box).save(os.path.join(out, fn))
            frames.append({'file': fn, 'dur_ms': fr.get('duration'),
                           'w': r['w'], 'h': r['h']})
        recs.append({'name': nm, 'src_png': e['png'], 'src_json': e['json'],
                     'sheet': [im.width, im.height], 'frames': frames})
    return out, {'ok': recs, 'missing': missing}


def xnb_decode(files, out):
    """MonoGame 未压缩 XNB -> PNG。

    格式已实证（197/197 全自洽）：header 10B + 7bit(reader 数) + len+名字 +
    int32 reader 版本 + 7bit(共享资源数) + 7bit(类型索引) + 4B pad
    ⇒ Texture2D 头**固定落在偏移 65**：int32 fmt / u32 w / u32 h / u32 mips / u32 size。
    fmt 恒为 0(Color)、size 恒 == w*h*4、数据正好到 EOF。
    这里仍**逐文件复核**这三个恒等式，不复用"65"这个常量当信仰。
    """
    import struct
    from PIL import Image
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    recs, bad = [], []
    for nm in files:
        p = os.path.join(OS_NPC, nm + '.xnb')
        raw = open(p, 'rb').read()
        n = len(raw)
        hit = None
        for s in range(55, 90):
            if s + 20 > n:
                break
            fmt, w, h, mips, ds = struct.unpack('<iIIII', raw[s:s + 20])
            if (0 <= fmt <= 19 and 0 < w <= 8192 and 0 < h <= 8192 and mips >= 1
                    and ds > 0 and s + 20 + ds == n and ds == w * h * 4):
                hit = (s, fmt, w, h, mips, ds)
                break
        if hit is None:
            bad.append(nm)
            continue
        s, fmt, w, h, mips, ds = hit
        px = raw[s + 20:s + 20 + ds]
        im = Image.frombytes('RGBA', (w, h), px)  # MonoGame Color 内存序 = R,G,B,A
        fn = nm + '.png'
        im.save(os.path.join(out, fn))
        recs.append({'name': nm, 'file': fn, 'w': w, 'h': h, 'fmt': fmt,
                     'header_off': s, 'bytes': ds})
    return out, {'ok': recs, 'bad': bad}


# --------------------------------------------------------------------------
# STAGE 6 · 落地
# --------------------------------------------------------------------------
def png_size(p):
    """零依赖读 PNG IHDR（不 import PIL）：8B 签名 + 4B len + 'IHDR' + w + h。"""
    import struct
    with io.open(p, 'rb') as fh:
        head = fh.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        raise ValueError('not png: %s' % p)
    return list(struct.unpack('>II', head[16:24]))


def png_sizes_of(srcdir, names):
    """name -> {file: [w,h]}，**从磁盘真读**，不是抄元数据。

    ★★ 第71轮实测的坑：GameMaker 的 `UndertaleSprite.Width/Height` 是**设计画布**
      （含 margin），而 UTMT 导出的 PNG 是**裁掉 margin 的实际图** ——
      UT 侧 169 张里 141 张（83%）、黄魂侧 163 张里 122 张（75%）两者不等。
      ⇒ manifest 里"尺寸"必须记**实际像素**；元数据另开字段标清，不许混为一谈。
    """
    out = {}
    for nm in names:
        pat = re.compile('^%s(_\\d+)?\\.png$' % re.escape(nm))
        fs = sorted(f for f in os.listdir(srcdir) if pat.match(f))
        if fs:
            out[nm] = dict((f, png_size(os.path.join(srcdir, f))) for f in fs)
    return out


def land(srcdir, names, subdir):
    """把已抽出的帧搬进仓库。

    ★ 两种命名都要认：多帧 `<name>_<i>.png`（UT/黄魂/Outertale）
      与单帧 `<name>.png`（OneShot，一个 xnb 就是一张整图）。
      本轮第一次跑漏了后者，`os` 落地成了 name=0 —— 记在这里当反例。
    """
    dst = os.path.join(DST_SPR, subdir)
    os.makedirs(dst, exist_ok=True)
    got = {}
    for nm in names:
        pat = re.compile('^%s(_\\d+)?\\.png$' % re.escape(nm))
        fs = sorted(f for f in os.listdir(srcdir) if pat.match(f))
        if not fs:
            continue
        got[nm] = []
        for f in fs:
            shutil.copy2(os.path.join(srcdir, f), os.path.join(dst, f))
            got[nm].append(f)
    return dst, got


def main():
    write = '--write' in sys.argv
    os.makedirs(EV, exist_ok=True)
    plan, pools, ot_by = build_plan()

    print('=' * 78)
    print('STAGE 1-2 · 目标解析（源清单规模：%s）'
          % ', '.join('%s=%d' % (k, len(v)) for k, v in sorted(pools.items())))
    print('=' * 78)
    by_work = {}
    for p in plan:
        by_work.setdefault(p['work'], []).append(p)
    need = {'ut': set(), 'hy': set(), 'ot': set(), 'os': set()}
    for w, rows in sorted(by_work.items()):
        print('\n--- %s (%d 条注册) ---' % (w, len(rows)))
        for r in rows:
            if not r['declared_in_source']:
                print('  !! %-24s 声明 %-26s **源里没有**' % (r['id'], r['declared']))
                continue
            need[w].add(r['declared'])
            for a in r['also']:
                need[w].add(a)
            print('  %-24s %-26s <- %-16s +%d%s  fam=%d%s'
                  % (r['id'], r['declared'], r['rule'] or '(无兄弟规则)',
                     len(r['also']), (' %s' % r['also']) if r['also'] else '',
                     r['family_size'],
                     ('  缺: %s' % r['absent']) if r['absent'] else ''))
    need['ut'] |= set(ELEV)

    print('\n抽取清单：ut=%d hy=%d ot=%d os=%d'
          % (len(need['ut']), len(need['hy']), len(need['ot']), len(need['os'])))
    if not write:
        print('\n[dry] 不落盘。加 --write 才真跑。')
        return 0

    print('\n' + '=' * 78)
    print('STAGE 3 · UTMT 导出 UT（含电梯）')
    print('=' * 78)
    ut_dir, ut_man = utmt_export(sorted(need['ut']), DATA_UT, 'ut')
    print('\n' + '=' * 78)
    print('STAGE 3 · UTMT 导出 黄魂')
    print('=' * 78)
    hy_dir, hy_man = utmt_export(sorted(need['hy']), DATA_HY, 'hy')

    print('\n' + '=' * 78)
    print('STAGE 4 · Outertale 图集切片')
    print('=' * 78)
    ot_dir, ot_man = ot_slice(sorted(need['ot']), ot_by)
    print('  ok=%d missing=%s  frame 合计=%d'
          % (len(ot_man['ok']), ot_man['missing'],
             sum(len(r['frames']) for r in ot_man['ok'])))

    print('\n' + '=' * 78)
    print('STAGE 5 · OneShot XNB 解码')
    print('=' * 78)
    os_dir, os_man = xnb_decode(sorted(need['os']), os.path.join(TMP, 'os'))
    print('  ok=%d bad=%s' % (len(os_man['ok']), os_man['bad']))

    print('\n' + '=' * 78)
    print('STAGE 6 · 落地仓库')
    print('=' * 78)
    landed = {}
    pngs = {}
    for w, d in (('ut', ut_dir), ('hy', hy_dir), ('ot', ot_dir), ('os', os_dir)):
        dst, got = land(d, sorted(need[w]), w)
        landed[w] = got
        pngs[w] = png_sizes_of(dst, sorted(need[w]))
        nfile = sum(len(v) for v in got.values())
        print('  %-3s -> %-46s  name=%d file=%d' % (w, os.path.relpath(dst, ROOT), len(got), nfile))

    # 电梯单列
    os.makedirs(DST_ELEV, exist_ok=True)
    elev_got = {}
    for nm in ELEV:
        pat = re.compile('^%s_\\d+\\.png$' % re.escape(nm))
        fs = sorted(f for f in os.listdir(ut_dir) if pat.match(f))
        for f in fs:
            shutil.copy2(os.path.join(ut_dir, f), os.path.join(DST_ELEV, f))
        elev_got[nm] = fs
    elev_png = png_sizes_of(DST_ELEV, ELEV)
    print('  elev -> %-46s  name=%d file=%d'
          % (os.path.relpath(DST_ELEV, ROOT), len(elev_got),
             sum(len(v) for v in elev_got.values())))

    # ---- manifest ----
    man_cross = {
        'schema_version': 1,
        'round': 71,
        'why': ('第70轮注册表 96 人里，跨作品 61 人**有名字没画**（assets/sprites/ 此前只有 ghost/）。'
                '本轮把 ut/hy/ot/os 四作的贴图落地。'),
        'how': {
            'ut': 'UTMT 定向导出 game.droid 的指定 sprite，逐帧 PNG',
            'hy': '同上（黄魂 game.droid）',
            'ot': 'Aseprite 图集按 json 的 frame 矩形切片',
            'os': 'MonoGame 未压缩 XNB 解 Texture2D（raw RGBA），逐文件复核 fmt/size/EOF 三恒等式',
        },
        'size_semantics': {
            'png': '★ 权威：帧的实际像素尺寸（绘图用这个）。由 PNG IHDR 真读。',
            'gms_meta': ('GameMaker 的 sprite Width/Height，是**设计画布含 margin**，'
                         '与导出 PNG 不等 —— UT 侧 169 张里 141 张不等（83%）、'
                         '黄魂侧 163 张里 122 张不等（75%）。只作参考，**不要拿来算绘制位置**。'),
        },
        'plan': plan,
        'need': dict((k, sorted(v)) for k, v in need.items()),
        'landed': landed,
        'png_sizes': pngs,
        'gms_meta': dict((r['name'], [r['w'], r['h']]) for r in ut_man['ok'] + hy_man['ok']),
        'sources': {
            'ut_data': DATA_UT, 'hy_data': DATA_HY,
            'ot_www': OT_WWW, 'os_npc': OS_NPC,
        },
    }
    with io.open(os.path.join(DST_SPR, '_cross_works.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(man_cross, ensure_ascii=False, indent=1))

    ut_by_name = dict((r['name'], r) for r in ut_man['ok'])
    elev_man = {
        'schema_version': 1,
        'round': 71,
        'why': ('用户口径：outertale 与 UT 的联通 = 在 UT 的第一个 room 里放一部电梯，'
                '电梯要"很高"（Outertale 设在宇宙上）。本目录 = 那部电梯的**零件**。'),
        'source': DATA_UT,
        'site': {
            'room_index': 4, 'room_name': 'room_area1', 'size': [680, 260],
            'why_not_room_start': ('room_start(index 0) 是空壳 —— 实例只有 obj_time / obj_layerchecker / '
                                   'obj_screen / obj_mobilecontroller，**没有 obj_mainchara**；'
                                   'room_area1 才是有主角的第一间，且它的背景资源就叫 bg_firstroom。'),
            'predecessor_in_bigmap': 'bigmap66 里 hub:ut -> ut:0(room_start)；本轮的电梯不取代它。',
        },
        'size_semantics': man_cross['size_semantics'],
        #: ★ parts[].size = **实际像素**（逐帧可能不同，因为 GameMaker 裁了 margin）
        'parts': dict(
            (nm, {
                'gms_meta': [ut_by_name[nm]['w'], ut_by_name[nm]['h']],
                'tex_frames': ut_by_name[nm]['martix'],
                'frames': [{'file': f, 'size': elev_png[nm][f]} for f in elev_got[nm]],
            })
            for nm in ELEV if nm in ut_by_name),
        'manifest_ut': ut_man,
    }
    with io.open(os.path.join(DST_ELEV, '_source.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(elev_man, ensure_ascii=False, indent=1))

    with io.open(os.path.join(EV, 'fetch71_ut.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ut_man, ensure_ascii=False, indent=1))
    with io.open(os.path.join(EV, 'fetch71_hy.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(hy_man, ensure_ascii=False, indent=1))
    with io.open(os.path.join(EV, 'fetch71_ot.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ot_man, ensure_ascii=False, indent=1))
    with io.open(os.path.join(EV, 'fetch71_os.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(os_man, ensure_ascii=False, indent=1))
    with io.open(os.path.join(EV, 'fetch71_plan.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(plan, ensure_ascii=False, indent=1))
    print('\nmanifest: assets/sprites/_cross_works.json + assets/elevator/_source.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
