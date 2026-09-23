# -*- coding: utf-8 -*-
"""
第 39 轮 · 把"原作房间背景事实"蒸馏成**可入库的溯源表**。

为什么必须蒸馏进仓库，而不是让套件去读 `E:\\Download\\_tmp\\dr_out`：
那个目录按项目约定是**用后即删**的临时区。一旦套件依赖它，删掉临时文件后
套件不是"报红"而是**静默失去鉴别力**（读不到 dump ⇒ 全判 `none` ⇒ 断言全绿）。
这正是本项目吃过多次的"恒真判据"陷阱。

蒸馏**只保留 `classify()` 真正用到的字段**，并且保证能**重建出等价输入**：
  · 每房间：`name` / `w` / `h` / `bg_sprites`(有序) / `asset_sprites`(有序, 已展平)
  · 每章：`sprite_dims`（名字 → [w, h]），只装被引用到的名字

重建方式（套件里照此做，**不另写一份 classify**）：
    layers = [{'bg_sprite': s} for s in bg_sprites] \\
           + [{'asset_sprites': a} for a in asset_sprites]
    classify({'width': w, 'height': h, 'layers': layers}, ch, area, inv)
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_common as C   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(REPO, 'code-quality-audit', '第39轮-全量场景背景', '_evidence')


def main():
    rooms = C.load_rooms()
    inv = C.load_assets(rooms)
    out = {
        'schema': 'ralsei_pet.original_room_bg_provenance/1',
        'generated_at': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
        'note': ('源自 UTMT 反编译产出的 rooms_map.json（每章一份）。这里只保留 '
                 'classify() 用到的字段，并附被引用精灵的像素尺寸 —— '
                 '目的是让回归套件**不依赖 E:\\Download 临时区**也能复算档次。'),
        'source': {
            'rooms_map': r'E:\Download\_tmp\dr_out\<chapter>_windows\rooms_map.json',
            'sprites': r'E:\Download\_tmp\dr_out\<chapter>_windows\Sprites',
            'dump_script': 'code-quality-audit/第37轮-原作素材反编译/_tools/dump_rooms.csx',
            'regenerate': '用 UTMT CLI 对每章 data.win 重跑 dump_rooms.csx',
        },
        'min_real_bg': list(C.MIN_REAL_BG),
        'chapters': {},
    }
    for ch in C.CHS:
        rs = rooms.get(ch) or {}
        inv_ch = inv.get(ch) or {}
        ch_out = {'room_count': len(rs), 'rooms': {}, 'sprite_dims': {}}
        used = set()
        for rid, r in sorted(rs.items()):
            bg_sp, as_sp = [], []
            for ly in r.get('layers') or []:
                bs = ly.get('bg_sprite')
                if bs and bs != 'UndertaleSprite':
                    bg_sp.append(bs)
                for a in ly.get('asset_sprites') or []:
                    if a:
                        as_sp.append(a)
            ch_out['rooms'][str(rid)] = {
                'name': r.get('name'), 'w': r.get('width'), 'h': r.get('height'),
                'bg_sprites': bg_sp, 'asset_sprites': as_sp,
            }
            used.update(bg_sp)
            used.update(as_sp)
        # ★ 尺寸表必须装**全量** `inv_ch`，不能只装"被房间引用的名字"：
        #   classify() 的 `chapter_tiles` 分支是在**整章所有 `*_tiles`** 里挑最大的，
        #   只装被引用的名字会让重建后的 inv 缺候选 ⇒ 静默掉到 chapter_fallback。
        #   （首版就是只装了 used，自检当场抓到 844 条不一致 —— 这就是"探针不保真"。）
        for nm in sorted(inv_ch):
            w, h = inv_ch[nm][1]
            ch_out['sprite_dims'][nm] = [w, h]
        ch_out['referenced_not_in_inv'] = sorted(used - set(inv_ch))
        out['chapters'][ch] = ch_out

    os.makedirs(EV, exist_ok=True)
    p = os.path.join(EV, '原作房间背景溯源.json')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=False)
    size = os.path.getsize(p)
    print('溯源表 -> %s  (%d B, %.1f KB)' % (p, size, size / 1024.0))
    print('逐章 rooms / 有 bg_sprite 引用 / 尺寸表条目：')
    for ch, v in out['chapters'].items():
        nb = sum(1 for r in v['rooms'].values() if r['bg_sprites'])
        print('   %-4s rooms=%-4d 有bg_sprite=%3d  sprite_dims=%d'
              % (ch, v['room_count'], nb, len(v['sprite_dims'])))

    # ---- 自检：用溯源表重建 + classify，结果必须与直接读 dump 完全一致 ----
    prov = json.load(io.open(p, encoding='utf-8'))
    dims_inv = {}
    for ch, v in prov['chapters'].items():
        dims_inv[ch] = {nm: (None, tuple(d)) for nm, d in v['sprite_dims'].items()}
    # 只重算"被场景引用到的房间"就够，但全量更便宜、区分度更高
    diff = []
    scenes = C.collect_scenes(SCENES)
    for sid, ch, area, rid, src in scenes:
        a = C.classify((rooms.get(ch) or {}).get(rid), ch, area, inv)
        pv = prov['chapters'][ch]['rooms'].get(str(rid))
        if pv is None:
            diff.append((sid, rid, '溯源表缺该房间'))
            continue
        rebuilt = {'width': pv['w'], 'height': pv['h'],
                   'layers': ([{'bg_sprite': s} for s in pv['bg_sprites']]
                              + [{'asset_sprites': a2} for a2 in pv['asset_sprites']])}
        b = C.classify(rebuilt, ch, area, dims_inv)
        if a != b:
            diff.append((sid, rid, '%s -> %s' % (a, b)))
    print('')
    print('自检：溯源表重建 classify 与原始 dump 分类一致 %s'
          % ('全部一致 ✓' if not diff else '❗不一致 %d 条 %s' % (len(diff), diff[:5])))
    return 0 if not diff else 1


if __name__ == '__main__':
    sys.exit(main())
