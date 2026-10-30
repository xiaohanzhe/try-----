# -*- coding: utf-8 -*-
u"""第120轮修正：撤掉误接到 ut 章的 20 张 outertale 烘图。

## 为什么要撤

第120轮第二轮接线是这么跑的：

    python apply120.py --game outertale --only-missing --source-tag ot \
                       --zone assets/scenes/_zone.ut.rooms.json ...

它的用意是"ut 这边缺图的房间，看看 outertale 有没有同名图"。
**这个用意本身是错的。**

实测（`_evidence/raw/{ut,outertale}/viz120.*.tsv`，本轮 UTMT 现取）：

    ut  game.droid  ROOM = 338
    ot  game.droid  ROOM = 358   =  UT 的 338 间（全含） + 20 间 outertale 独有
    ut 独有房间 = 0

⇒ `_zone.ut.rooms.json` 那 358 个场景名里，多出来的 20 个
（`room_steamworks_*` / `room_newhome_*` / `room_of_bog` / `coming_soon` …）
**根本不是 UT 的房间**，是第 77 轮从跨作品大图 `bigmap66.json` 迁入时混进 ut 章的。

给它们贴 outertale 的像素 = 拿外传美术冒充原作画面，属于编造。
用户口径「一切根据原作」⇒ 宁可如实留空。

## 撤成什么

`bg: null` + `bg_source: "none"`（= check77 F3 的原意「没素材就如实留空」）。
**不动**这 20 个场景本身的存在与命名 —— 它们该归哪一章是另一件事
（第120轮报告 §120.6 已登记为待裁定项，动归属会改场景总数与多套老判据的分母）。

## 图怎么办

20 张 `bg/outertale_*.png` 只被这 20 个 ut 场景引用（全仓唯一引用点，已核）。
撤线后就是孤儿 ⇒ 删除，避免 `check_bg120 D1` 报孤儿。
删之前把 sha256/尺寸写进 `_evidence/ot20_manifest.tsv`，可随时从 outertale
dump 用 `bake120.py` 原样重现（工具与 dump 都在仓库/证据里）。

用法：python revert120_ot.py [--dry-run]
"""
import glob
import hashlib
import io
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.join(HERE, '..')
ROOT = os.path.join(ROUND, '..', '..')
REPO = os.path.normpath(ROOT)

ZONE = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_zone.ut.rooms.json')
BGDIR = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', 'bg')
RAW = os.path.join(ROUND, '_evidence', 'raw')
EV = os.path.join(ROUND, '_evidence', 'ot20_manifest.tsv')


def rooms_of(tsv):
    u"""从 `<game>/viz120.<game>.tsv` 的 ROOM 段取房间名集合。"""
    out = set()
    for ln in io.open(tsv, encoding='utf-8').read().splitlines():
        p = ln.split('\t')
        if p and p[0] == 'ROOM' and len(p) > 2:
            out.add(p[2])
    return out


def png_size(path):
    u"""读 PNG 头拿宽高（不解码整图）。"""
    with open(path, 'rb') as f:
        head = f.read(33)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return (None, None)
    w, h = struct.unpack('>II', head[16:24])
    return (w, h)


def dump_like(p, data):
    u"""按仓库既有排版写回：`indent=1` + `ensure_ascii=False` + LF。"""
    s = json.dumps(data, ensure_ascii=False, indent=1).replace('\r\n', '\n')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s if s.endswith('\n') else s + '\n')


def main(argv):
    dry = '--dry-run' in argv

    ut_rooms = rooms_of(os.path.join(RAW, 'ut', 'viz120.ut.tsv'))
    ot_rooms = rooms_of(os.path.join(RAW, 'outertale', 'viz120.outertale.tsv'))
    if not ut_rooms or not ot_rooms:
        print('[FAIL] 房间表没读到（ut=%d ot=%d）' % (len(ut_rooms), len(ot_rooms)))
        return 2
    print('[ok] ut dump %d 间 / outertale dump %d 间 / ot 独有 %d 间'
          % (len(ut_rooms), len(ot_rooms), len(ot_rooms - ut_rooms)))

    d = json.load(io.open(ZONE, encoding='utf-8', newline=''))
    scenes = d['scenes']

    # ---- 1. 找出"名字不在 UT 自己的 dump 里"的房，且当前接了图 ----
    alien = []
    for sid, sc in scenes.items():
        if not isinstance(sc, dict):
            continue
        nm = sc.get('name')
        if nm in ut_rooms:
            continue
        alien.append((sid, nm, sc.get('bg'), sc.get('bg_source')))

    with_bg = [a for a in alien if a[2]]
    print('[info] ut 章里名不在 UT dump 的场景 %d 个，其中当前接了图的 %d 个'
          % (len(alien), len(with_bg)))
    for sid, nm, bg, src in alien:
        flag = 'OT-ONLY' if nm in ot_rooms else 'UNKNOWN '
        print('   %s %-40s %-34s %s' % (flag, sid, nm, src))
    if not with_bg:
        print('[ok] 没有需要撤的（幂等）')
        return 0

    # ---- 2. 记清单（sha256 + 尺寸），再撤线 ----
    man = []
    for sid, nm, bg, src in with_bg:
        p = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', bg.replace('/', os.sep))
        if os.path.isfile(p):
            h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
            w, hh = png_size(p)
            man.append((os.path.basename(p), str(h), str(w), str(hh), str(os.path.getsize(p))))

    if not dry:
        with io.open(EV, 'w', encoding='utf-8', newline='\n') as f:
            f.write('file\tsha256\tw\th\tbytes\n')
            for row in sorted(man):
                f.write('\t'.join(row) + '\n')
        print('[ok] 清单落盘 %s（%d 行）' % (os.path.relpath(EV, REPO), len(man)))

        for sid, nm, bg, src in with_bg:
            scenes[sid]['bg'] = None
            scenes[sid]['bg_source'] = 'none'
        dump_like(ZONE, d)
        print('[ok] 已撤线 %d 个场景（bg=null / bg_source="none"）' % len(with_bg))

    # ---- 3. 删孤儿图（只删"撤线后全仓无人引用"的）----
    refs = set()
    for zp in glob.glob(os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '*.json')):
        try:
            dd = json.load(io.open(zp, encoding='utf-8'))
        except Exception:
            continue
        for v in (dd.get('scenes') or {}).values():
            if isinstance(v, dict) and v.get('bg'):
                refs.add(os.path.basename(v['bg']))

    # ★ 坑（首版踩过）：`refs` 是扫**磁盘上尚未写回**的 json 得到的，那 20 个场景
    #   此刻还挂着 bg ⇒ 它们仍算"被引用" ⇒ 孤儿数恒为 0，图留在盘上发霉，
    #   `check_bg120 D1` 随后报 20 张孤儿。必须把这批**本轮要撤掉的引用**先减掉。
    reverted = set(os.path.basename(bg) for _s, _n, bg, _src in with_bg if bg)
    refs_after = refs - reverted
    orphans = sorted(fn for fn, _h, _w, _hh, _b in man if fn not in refs_after)
    print('[info] 撤线后无人引用的图 %d 张' % len(orphans))
    if dry:
        for fn in orphans:
            print('   would delete', fn)
        return 0
    n = 0
    for fn in orphans:
        p = os.path.join(BGDIR, fn)
        if os.path.isfile(p):
            os.remove(p)
            n += 1
    print('[ok] 删除孤儿图 %d 张' % n)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
