# -*- coding: utf-8 -*-
"""
第 39 轮 · Stage 1：把全量场景里**能拿到真背景**的那些落盘（零编造）。

口径（沿用第 37 轮，刻意不变）：
  · **真背景 = 房间自带 `bg_sprite` / `asset_sprites` 且尺寸 ≥ 300×200**
    → **原样复制原作 PNG**，不缩放、不裁切、不合成。
  · 拿不到真背景的场景**一律不动**（仍 `bg: null`）—— 用"区域代表素材"凑近似
    属第 37 轮的既有决定，本轮**不扩大**它的适用范围，留给用户裁定。

产出：
  · `assets/scenes/bg/<scene_id 点换下划线>.png`（新文件）
  · `_evidence/真背景导出清单.txt` / `.json`

⚠️ 命名冲突纪律：已存在的目标文件**只核验不改写**（第 37 轮吃过"无法覆写既有文件"
   的亏；且覆盖会让"哪张是第几轮产物"失去可追溯性）。
"""
import io
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_common as C   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
OUT_BG = os.path.join(SCENES, 'bg')
EV = os.path.join(REPO, 'code-quality-audit', '第39轮-全量场景背景', '_evidence')

L = []


def w(s=''):
    print(s)
    L.append(s)


def main():
    t0 = time.time()
    dry = '--dry' in sys.argv
    rooms = C.load_rooms()
    inv = C.load_assets(rooms)
    scenes = C.collect_scenes(SCENES)
    os.makedirs(EV, exist_ok=True)
    if not dry:
        os.makedirs(OUT_BG, exist_ok=True)

    w('第 39 轮 · 真背景落盘  %s   %s' % (time.strftime('%Y-%m-%d %H:%M:%S'),
                                          '[DRY RUN]' if dry else ''))
    w('=' * 78)
    w('判据：房间自带 bg_sprite / asset_sprites 且宽高均 ≥ %s' % (C.MIN_REAL_BG,))
    w('全量场景 %d 个（%d 锚点 + %d 分片）' % (
        len(scenes),
        sum(1 for s in scenes if s[4] == 'anchor'),
        sum(1 for s in scenes if s[4] == 'zone')))
    w('')

    real, approx, none_ = [], [], []
    for sid, ch, area, rid, src in scenes:
        room = (rooms.get(ch) or {}).get(rid)
        nm, tiled, how = C.classify(room, ch, area, inv)
        rec = dict(scene_id=sid, chapter=ch, area=area, room_id=rid, asset=nm,
                   tiled=tiled, how=how, kind=src,
                   room_w=(room or {}).get('width'), room_h=(room or {}).get('height'))
        if how in C.REAL_HOWS:
            real.append(rec)
        elif how == 'none':
            none_.append(rec)
        else:
            approx.append(rec)

    w('分类：真背景 %d ｜ 近似 %d ｜ 未配上 %d' % (len(real), len(approx), len(none_)))
    w('')

    # ---- 落盘 ----
    before = set(os.listdir(OUT_BG)) if os.path.isdir(OUT_BG) else set()
    rows, n_new, n_exists, n_err = [], 0, 0, 0
    for r in real:
        ch = r['chapter']
        asset = r['asset']
        src_png = inv[ch][asset][0]
        sw, sh = inv[ch][asset][1]
        fname = C.bg_filename(r['scene_id'])
        outp = os.path.join(OUT_BG, fname)
        r['file'] = fname
        r['src'] = src_png
        r['src_dims'] = [sw, sh]
        if os.path.isfile(outp):
            d = C.png_dims(outp)
            r['mode'] = 'EXISTS'
            r['out_dims'] = list(d) if d else None
            r['dims_match'] = (d == (sw, sh))
            n_exists += 1
        elif dry:
            r['mode'] = 'DRY'
            r['out_dims'] = None
            r['dims_match'] = None      # 干跑没落盘，不假称"尺寸一致"
        else:
            try:
                shutil.copyfile(src_png, outp)
                d = C.png_dims(outp)
                r['mode'] = 'COPY'
                r['out_dims'] = list(d) if d else None
                r['dims_match'] = (d == (sw, sh))
                n_new += 1
                if not r['dims_match']:
                    n_err += 1
            except Exception as e:
                r['mode'] = 'ERR %s' % e
                r['out_dims'] = None
                r['dims_match'] = False
                n_err += 1
        rows.append(r)

    # ---- 磁盘核验（不信内存 list，去 os.listdir 查）----
    after = set(os.listdir(OUT_BG)) if os.path.isdir(OUT_BG) else set()
    added = sorted(after - before)
    w('落盘：新建 %d ｜ 已存在(核验) %d ｜ 出错 %d' % (n_new, n_exists, n_err))
    w('磁盘核验：bg/ 之前 %d 项 → 之后 %d 项，实际新增 %d 项'
      % (len(before), len(after), len(added)))
    w('')

    w('─' * 78)
    w('逐条明细（%d 条真背景）' % len(rows))
    w('─' * 78)
    w('  %-46s %-9s %-14s %-30s %s' % ('scene_id', '章', '模式', '素材', '尺寸(源->落盘)'))
    for r in rows:
        w('  %-46s %-9s %-14s %-30s %s->%s%s' % (
            r['scene_id'], r['chapter'], r['mode'], r['asset'],
            '%dx%d' % tuple(r['src_dims']),
            r.get('out_dims') or '-',
            '' if r['dims_match'] is not False else '   ❗尺寸不一致'))

    # ---- ★ 尺寸一致性单列（这是"口径是否被前几轮遗留文件污染"的判据）----
    mismatch = [r for r in rows if r['dims_match'] is False]
    w('')
    w('★ 与当前口径源图尺寸不一致的已存在文件：%d 个' % len(mismatch))
    for r in mismatch:
        w('   %-46s %-30s 源 %s / 磁盘 %s' % (
            r['scene_id'], r['asset'],
            '%dx%d' % tuple(r['src_dims']), r.get('out_dims')))

    # ---- 尺寸分布（看一眼会不会有"小图当背景"的观感问题）----
    dims_cnt = {}
    for r in rows:
        k = '%dx%d' % tuple(r['src_dims'])
        dims_cnt[k] = dims_cnt.get(k, 0) + 1
    w('')
    w('源图尺寸分布（按出现次数降序）：')
    for k, v in sorted(dims_cnt.items(), key=lambda kv: -kv[1]):
        w('   %-14s %3d' % (k, v))

    # ---- 按房间尺寸比对标（真背景是否"够铺满一个房间"）----
    w('')
    w('源图宽 vs 房间宽（>1 表示素材比房间宽，缩放余地大）：')
    ratios = []
    for r in rows:
        if r.get('room_w'):
            ratios.append((r['src_dims'][0] / float(r['room_w']), r['scene_id'],
                           r['src_dims'], r['room_w'], r['room_h']))
    ratios.sort()
    for ratio, sid, sd, rw, rh in ratios[:5]:
        w('   最小 %.2f  %-44s 素材 %s / 房间 %sx%s' % (ratio, sid, sd, rw, rh))
    for ratio, sid, sd, rw, rh in ratios[-3:]:
        w('   最大 %.2f  %-44s 素材 %s / 房间 %sx%s' % (ratio, sid, sd, rw, rh))

    man = dict(
        generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        min_real_bg=list(C.MIN_REAL_BG),
        total_scenes=len(scenes), real=len(real), approx=len(approx), unset=len(none_),
        new_files=n_new, exists=n_exists, errors=n_err,
        disk_before=len(before), disk_after=len(after),
        how_counts=dict((h, sum(1 for r in real if r['how'] == h))
                        for h in sorted(set(r['how'] for r in real))),
        rows=[{k: v for k, v in r.items() if k != 'src'} for r in rows],
    )
    with open(os.path.join(EV, '真背景导出清单.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(man, f, ensure_ascii=False, indent=2)

    # 近似档也留一份，供用户裁定（**不进场景数据**）
    with open(os.path.join(EV, '近似档待裁定清单.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(generated_at=man['generated_at'], count=len(approx),
                       how_counts=dict((h, sum(1 for r in approx if r['how'] == h))
                                       for h in sorted(set(r['how'] for r in approx))),
                       rows=approx), f, ensure_ascii=False, indent=2)

    w('')
    w('耗时 %.1fs' % (time.time() - t0))
    w('结论：%s' % ('OK' if (n_err == 0 and len(added) == n_new) else '❗有异常，见上'))
    with open(os.path.join(EV, '真背景导出清单.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    print('\n清单 -> _evidence/真背景导出清单.txt')


if __name__ == '__main__':
    main()
