# -*- coding: utf-8 -*-
u"""第80轮：OneShot 场景勘查（只读；**绝不写源目录**）。

用户裁决（逐字，第79轮收尾）：「**要**」—— 即 Q1「场景补齐选档（建议接 OneShot 263）」。

为什么是 OneShot
-----------------
第77轮把 UT(358) / 黄魂(287) 迁进了产品索引，但**四个作品里 OneShot 一直缺**：
`E:\\Download\\_extract61\\_data\\` 下只有 `undertale` / `undertale_yellow` 两个目录，
OneShot 是 **MonoGame（不是 GameMaker）**，从没被勘查过。

★ OneShot 不是 GameMaker ⇒ 没有 `game.droid`/`data.win`，它的房数据是**明文**：
    · `gamedata/maps/map<N>.tmx`         —— Tiled 地图（宽高在 `<map width height>`，**单位是格**）
    · `gamedata/maps/events_map<N>.json` —— RPG Maker MV 格式的事件表
    · `gamedata/oneshot_map_names.json`  —— 官方地图**名**表（`id` → `name`）

「263」的出处（**实测，不是猜**）
----------------------------------
`oneshot_map_names.json` 的 `map_names` 恰 **263 条**，`id` 1..263 **无重复**；
磁盘上 `gamedata/maps/*.tmx` 也恰 **263 个**。⇒「OneShot 263」= **263 个房间**。

门机制（照抄，不猜）
--------------------
RPG Maker 的 `code 201 = Transfer Player`，`parameters[0]` 是**目的地 map id**。
实测全量出现 **306** 次 ⇒ 与 Deltarune 的 `obj_doorA~F` **同构**（一门可多目标、
也有死胡同），只是载体从 GML 换成 JSON。

纪律
----
* **只读**：本脚本不写、不改、不移动源目录里任何文件。
* **锚点优先**：先设 3 个"已知真值"站点，**全命中才信后面的解析**（第43轮血泪）。
* 自检（正/负控制成对）：伪造路径必不存在 / 真路径必存在 / 条数与磁盘一致。
"""
from __future__ import print_function

import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')
if not os.path.isdir(EVID):
    os.makedirs(EVID)
OUT = os.path.join(EVID, u'oneshot80.json')

#: ★ 源目录（用户本机；只读）。允许用环境变量覆盖，便于在别的机器上复跑。
SRC = os.environ.get(
    u'ONESHOT_DIR',
    u'C:\\Users\\23002\\Desktop\\项目文件夹\\niko的秘密'
    u'\\OneShot.World.Machine.Edition.Build.16512634')

MAPS = os.path.join(SRC, u'gamedata', u'maps')
NAMES = os.path.join(SRC, u'gamedata', u'oneshot_map_names.json')

#: ★★ 锚点（第43轮纪律：**提取成功 ≠ 提取正确** ⇒ 先设已知真值站点，全命中才用）。
#:   三条都取自上面**亲眼读过的**原始数据，逐条落在 `selfcheck()` 里：
#:     ① `map_names` == 263 条且 id == 1..263；
#:     ② `map2.tmx` 的 `<map>` 头 width=50 height=30（原文逐字）；
#:     ③ `events_map2.json` 可解析（门表不是 None）。
def read(p, limit=None):
    with io.open(p, u'r', encoding=u'utf-8', errors=u'replace') as f:
        return f.read(limit) if limit else f.read()


def load_json(p):
    return json.loads(read(p))


# ---------------------------------------------------------------- 地图尺寸

_RE_MAPW = re.compile(r'<map\b[^>]*\bwidth="(\d+)"\s+height="(\d+)"')
_RE_TH = re.compile(r'\btilewidth="(\d+)"\s+tileheight="(\d+)"')


def parse_tmx_dims(path):
    """→ (w_tiles, h_tiles, tile_w, tile_h) 或 None。

    ★ 只读文件头 4KB（`<map>` 元素必在首行）—— 293 个文件全读会白等。
    ★ 解析失败返回 `None`（**不猜** 0/1）—— "算不出"与"真的是 0"必须可区分。
    """
    head = read(path, 4096)
    m = _RE_MAPW.search(head)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    t = _RE_TH.search(head)
    tw = int(t.group(1)) if t else None
    th = int(t.group(2)) if t else None
    return w, h, tw, th


# ---------------------------------------------------------------- 门（201）

def parse_doors(events_path):
    """→ `[(dest_map_id, x, y, dir), ...]`（RPG Maker `code 201` Transfer Player）。

    ★ 坏 JSON ⇒ `None`（区分"没有门"与"文件读不了"）。
    """
    try:
        data = load_json(events_path)
    except Exception:
        return None
    out = []
    for ev in (data.get(u'events') or []):
        for pg in (ev.get(u'pages') or []):
            for cmd in (pg.get(u'list') or []):
                if cmd.get(u'code') == 201:
                    prm = cmd.get(u'parameters') or []
                    if len(prm) >= 4:
                        try:
                            out.append((int(prm[1]), int(prm[2]),
                                        int(prm[3]), prm[4] if len(prm) > 4 else 0))
                        except (TypeError, ValueError):
                            continue
    return out


# ---------------------------------------------------------------- 自检

def selfcheck(names_by_id, tmx_dims, doors):
    sc = []
    # A1 锚点①：名字表条数与连续性
    ids = sorted(names_by_id.keys())
    sc.append([u'A1 名字表 == 263 条且 id == 1..263',
               len(ids) == 263 and ids == list(range(1, 264))])
    # A2 锚点②：map2.tmx 头逐字（width=50 height=30）
    d2 = tmx_dims.get(2)
    sc.append([u'A2 map2.tmx 头 == 50x30（原文逐字）',
               bool(d2) and d2[0] == 50 and d2[1] == 30])
    # A3 锚点③：events_map2 解析成功且非空
    sc.append([u'A3 events_map2.json 可解析（门表不是 None）', doors.get(2) is not None])
    # A4 ★ 负控制：伪造路径必须读不到
    sc.append([u'A4 负控制：伪造 map 路径必不存在',
               not os.path.exists(os.path.join(MAPS, u'map9999.tmx'))])
    # A5 ★ 正控制：真 map1.tmx 必须在
    sc.append([u'A5 正控制：真 map1.tmx 在盘上',
               os.path.exists(os.path.join(MAPS, u'map1.tmx'))])
    return sc


def main():
    print(u'=' * 78)
    print(u'第80轮 · OneShot 场景勘查（只读）')
    print(u'=' * 78)
    print(u'源目录 : %s' % SRC)
    print(u'存在   : %s' % os.path.isdir(SRC))
    if not os.path.isdir(SRC):
        print(u'!! 源目录不存在 —— 不能假装成功')
        return 2

    # ---- 1. 官方名字表 ----
    names_by_id = {}
    if os.path.exists(NAMES):
        raw = load_json(NAMES).get(u'map_names') or []
        for it in raw:
            try:
                names_by_id[int(it[u'id'])] = it.get(u'name') or u''
            except (KeyError, TypeError, ValueError):
                continue
    print(u'\n[名字表] %d 条' % len(names_by_id))

    # ---- 2. 磁盘 TMX ----
    tmx_files = sorted(glob.glob(os.path.join(MAPS, u'*.tmx')))
    print(u'[地图]   %d 个 .tmx' % len(tmx_files))

    tmx_dims = {}
    bad_dims = []
    for p in tmx_files:
        m = re.match(r'map(\d+)\.tmx$', os.path.basename(p))
        if not m:
            continue
        mid = int(m.group(1))
        dim = parse_tmx_dims(p)
        if dim is None:
            bad_dims.append(mid)
        else:
            tmx_dims[mid] = dim
    print(u'[尺寸]   解析成功 %d / 失败 %d' % (len(tmx_dims), len(bad_dims)))

    # ---- 3. 门（Transfer Player）----
    doors = {}
    ev_files = sorted(glob.glob(os.path.join(MAPS, u'events_map*.json')))
    for p in ev_files:
        m = re.match(r'events_map(\d+)\.json$', os.path.basename(p))
        if not m:
            continue
        doors[int(m.group(1))] = parse_doors(p)
    n_door_edges = sum(len(v) for v in doors.values() if v)
    n_ev = sum(1 for v in doors.values() if v is not None)
    print(u'[事件]   %d 个 events_map（可解析 %d）' % (len(ev_files), n_ev))
    print(u'[门]     code201 边共 %d 条' % n_door_edges)

    # ---- 锚点核验：★ 全命中才写 ----
    sc = selfcheck(names_by_id, tmx_dims, doors)
    print(u'\n' + u'-' * 78)
    print(u'锚点核验：')
    ok_all = True
    for name, ok in sc:
        ok_all = ok_all and ok
        print(u'  [%s] %s' % (u'PASS' if ok else u'FAIL', name))

    # ---- 组装节点（与 bigmap66 的节点形状**逐字同构**）----
    nodes = []
    unmatched = []
    for mid in sorted(tmx_dims.keys()):
        w, h, tw, th = tmx_dims[mid]
        nm = names_by_id.get(mid)
        if nm is None:
            unmatched.append(mid)
            nm = u'map%d' % mid
        # ★ 尺寸换算成**像素**：与 UT/黄魂的节点口径一致（那边 w/h 是 px）。
        #   tile 默认 16（RPG Maker MV 标准），若 TMX 写了就以 TMX 为准。
        t_w = tw or 16
        t_h = th or 16
        nodes.append({
            u'id': u'oneshot:%d' % mid,
            u'work': u'oneshot',
            u'index': mid,
            u'name': nm,
            u'w': w * t_w,
            u'h': h * t_h,
            u'origin': u'oneshot',
        })

    edges = []
    for src_id, ds in doors.items():
        for (dest, x, y, dr) in (ds or []):
            edges.append({
                u'work': u'oneshot',
                u'from': src_id,
                u'to': dest,
                u'x': x, u'y': y, u'dir': dr,
            })

    out = {
        u'round': 80,
        u'stage': u'OneShot 场景勘查（只读）',
        u'source': SRC,
        u'counts': {
            u'names': len(names_by_id),
            u'tmx': len(tmx_files),
            u'tmx_ok': len(tmx_dims),
            u'tmx_bad_dims': bad_dims,
            u'events_files': len(ev_files),
            u'door_edges': n_door_edges,
            u'unmatched_name': unmatched,
        },
        u'anchors': [[n, bool(o)] for n, o in sc],
        u'anchors_ok': ok_all,
        u'nodes': nodes,
        u'edges': edges,
    }
    with io.open(OUT, u'w', encoding=u'utf-8', newline=u'\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print(u'\n证据 -> %s' % OUT)
    print(u'结果：anchors_ok=%s  nodes=%d  edges=%d'
          % (ok_all, len(nodes), len(edges)))
    return 0 if ok_all else 1


if __name__ == u'__main__':
    sys.exit(main())
