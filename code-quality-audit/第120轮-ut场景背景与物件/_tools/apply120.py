# -*- coding: utf-8 -*-
u"""第120轮接线：把烘好的房间图写进场景资产（只改 `bg` / `bg_source` 两个字段）。

纪律（每条都有代价）：
  · **按房间名匹配，不按 `original_room_id`**。`_zone.ut.rooms.json` 的 358 个场景里
    有 20 个是附加房间（`room_steamworks_*`、`room_god`…），它们的 id 338~357
    **不是 UT 的房间下标**；按 id 接线会把图贴错房间且**不报错**。
  · **只拷真正被引用到的图**。第一版把 358 张 outertale 图全拷进 `bg/`，
    结果 338 张成了孤儿（白胖 2.8 MB，`check_bg120 D1` 直接报红）。
  · 找不到对应图就**保持 `bg: null`**，不猜、不留假路径。
  · 幂等：连跑两次字节相同。

用法（两轮）：
    python apply120.py --game ut --baked <dir> --copy-to <bg> --zone <json>
    python apply120.py --game outertale --baked <dir> --copy-to <bg> --zone <json> \
                       --only-missing --source-tag ot

⛔⛔ **第二行那个用法本人在本轮已判定为错，别照着跑。**
    它拿外传 outertale 的同名烘图去补 ut 章的 20 个空场景，事后取证：

        ut game.droid ROOM = 338
        ot game.droid ROOM = 358 = UT 的 338 间（全含） + 20 间 outertale 独有

    ⇒ 那 20 个名字**不是 UT 的房间**（第77轮从跨作品大图迁入时混进 ut 章），
      给它们贴外传像素 = 拿外传美术冒充原作画面。已由 `revert120_ot.py` 撤线。
      保留这行是为了说清"当时为什么这么跑、错在哪"，**不是**可复用的配方。
"""
import argparse
import io
import json
import os
import shutil
import sys


def load_json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def dump_like(p, data):
    u"""按仓库既有排版写回：`indent=1` + `ensure_ascii=False` + LF。"""
    s = json.dumps(data, ensure_ascii=False, indent=1).replace('\r\n', '\n')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s if s.endswith('\n') else s + '\n')


def bake_index(baked, game):
    u"""烘图目录 → {房间名: 源文件}。"""
    prefix = game + '_'
    out = {}
    for fn in sorted(os.listdir(baked)):
        if fn.endswith('.png') and fn.startswith(prefix):
            out[fn[len(prefix):-4]] = os.path.join(baked, fn)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True)
    ap.add_argument('--baked', required=True, help='烘图目录（<game>_<room>.png）')
    ap.add_argument('--copy-to', required=True, help='仓库里的 bg 目录')
    ap.add_argument('--zone', action='append', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--only-missing', action='store_true',
                    help='只给**当前没有 bg** 的场景接线（第二轮补另一款游戏时用）')
    ap.add_argument('--source-tag', default=None,
                    help='bg_source 里的来源标记，缺省取 --game')
    a = ap.parse_args(argv)

    by_room = bake_index(a.baked, a.game)
    if not by_room:
        print('[FAIL] %s 里没有 %s*.png' % (a.baked, a.game))
        return 2
    print('[ok] 烘图 %d 张' % len(by_room))

    zones = [(zp, load_json(zp)) for zp in a.zone]
    tag = a.source_tag or a.game

    # ---- 1. 先在内存里定案：谁要接、接哪张 ----
    plan = []            # [(zp, data, [(sid, scene, room, want)])]
    stat = {'consider': 0, 'assign': 0, 'had': 0, 'none': 0}
    need = {}            # 目标文件名 -> 源文件
    for zp, d in zones:
        scenes = d.get('scenes') or {}
        hits = []
        for sid, sc in scenes.items():
            if not isinstance(sc, dict):
                continue
            stat['consider'] += 1
            if a.only_missing and sc.get('bg'):
                stat['had'] += 1
                continue
            room = sc.get('name')
            src = by_room.get(room)
            if not src:
                stat['none'] += 1
                continue
            want = 'bg/%s%s.png' % (a.game + '_', room)
            hits.append((sid, sc, room, want))
            need[want[len('bg/'):]] = src
        plan.append((zp, d, hits))

    # ---- 2. 只拷被引用到的图 ----
    copied = same = 0
    if not a.dry_run:
        os.makedirs(a.copy_to, exist_ok=True)
        for fn, src in sorted(need.items()):
            dst = os.path.join(a.copy_to, fn)
            if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src):
                with open(dst, 'rb') as f1, open(src, 'rb') as f2:
                    if f1.read() == f2.read():
                        same += 1
                        continue
            shutil.copyfile(src, dst)
            copied += 1
    print('[ok] 拷入 bg/：新写 %d 张，已相同跳过 %d 张（共需要 %d 张）'
          % (copied, same, len(need)))

    # ---- 3. 写回 ----
    for zp, d, hits in plan:
        for sid, sc, room, want in hits:
            sc['bg'] = want
            sc['bg_source'] = 'room.bake120.%s' % tag
            stat['assign'] += 1
        if not a.dry_run and hits:
            dump_like(zp, d)
        print('  %-42s 新接线 %d' % (os.path.basename(zp), len(hits)))

    print('---- 考虑 %d 场景：新接线 %d / 本来就有 %d / 找不到图 %d'
          % (stat['consider'], stat['assign'], stat['had'], stat['none']))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
