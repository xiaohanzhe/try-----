# -*- coding: utf-8 -*-
"""第44轮 · 生成房间几何资产 `assets/scenes/_room_geometry.json`。

为什么需要这个文件
------------------
渲染层（P1）要画房间，必须知道**房间的世界尺寸**（相机钳制、背景铺排、
物件裁剪全靠它）。但产品场景 JSON 里**没有** `w`/`h` 字段 —— 第 36~40 轮
登记场景时只登记了 `bg` / `original_room_id`（见 `_index.json`）。

而第 44 轮的全量普查 `<轮次>/_evidence/rooms44/<章>.json` **已经采到了宽高**
（`rooms44.csx` 的 [B] 段：`每个 room 的宽高 / 图层数 / 图层类型`）。

⇒ 本脚本把散在证据目录里的几何数据**蒸馏进仓库资产**。
  这条纪律来自记忆 §0：**回归套件不许依赖"用后即删"的临时区**；
  `_evidence/` 虽然长期保留，但它是"轮次证据"（可能被归档/清理），
  而渲染层要的是"产品数据"。两者分开，各归其位。

输入 → 输出
-----------
  in : code-quality-audit/第44轮-原作对话框复刻/_evidence/rooms44/{ch1..ch5}.json
  out: ralsei_pet/assets/scenes/_room_geometry.json

输出形状（**扁平、带章号、对齐产品口径**）::

    {
      "schema_version": 1,
      "source": "第44轮 rooms44.csx [B] 段（UTMT 现场反编译五章 data.win）",
      "authority": "…",
      "rooms": {
        "ch1:2": {"w": 320, "h": 240, "name": "room_krisroom", "n_layers": 8},
        ...
      }
    }

键 = `"<章>:<原作 room_id>"`。为什么不用嵌套 dict：
产品侧要按 `original_room_id` 反查（`_index.json` 的登记行里叫这个名字），
扁平键一次 `.get()` 命中，不必先知道章号再套一层。

★ 本脚本只做"搬运 + 规整"，**不推断、不补默认值** ——
  采不到的 (章,room) 就**不写进表**（缺项由调用方按"未知房间 → 退化为
  相机全屏"处理，不在这里伪造 640×480）。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')          # 仓库根
EVID = os.path.join(HERE, '..', '_evidence', 'rooms44')
OUT = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_room_geometry.json')

CHAPTERS = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')
SCHEMA_VERSION = 1


def load_chapter(ch):
    path = os.path.join(EVID, ch + '.json')
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    rooms = data.get('rooms')
    if not isinstance(rooms, list):
        raise ValueError('%s: rooms 不是 list' % ch)
    return data, rooms


def main():
    out_rooms = {}
    stats = {}
    dup = []

    for ch in CHAPTERS:
        data, rooms = load_chapter(ch)
        n = 0
        for r in rooms:
            if not isinstance(r, dict):
                continue
            rid = r.get('id')
            w = r.get('w')
            h = r.get('h')
            # ★ 缺 w/h 或非正 → 不写进表（不伪造尺寸）
            if not isinstance(rid, int) or not isinstance(w, int) or not isinstance(h, int):
                continue
            if w <= 0 or h <= 0:
                continue
            key = '%s:%d' % (ch, rid)
            if key in out_rooms:
                dup.append(key)
                continue
            rec = {'w': w, 'h': h}
            name = r.get('name')
            if isinstance(name, str) and name:
                rec['name'] = name
            nl = r.get('n_layers')
            if isinstance(nl, int):
                rec['n_layers'] = nl
            out_rooms[key] = rec
            n += 1
        stats[ch] = n

    payload = {
        'schema_version': SCHEMA_VERSION,
        'source': '第44轮 rooms44.csx [B] 段（UTMT 现场反编译五章 data.win）',
        'authority': ('原作 Data.Rooms[i].Width/Height。键 = "<章>:<原作 room_id>"，'
                      'id 即 Data.Rooms 下标（与 scr_roomname 对齐）。'),
        'note': ('渲染层用它做相机钳制 / 背景铺排 / 物件裁剪。'
                 '★ 采不到的 (章,room) 不写进表 —— 不伪造 640x480。'
                 '缺项由调用方按"未知房间"退化处理。'),
        'stats': stats,
        'rooms': out_rooms,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write('\n')

    print('[OK] 写出 %s' % OUT)
    print('     rooms = %d' % len(out_rooms))
    for ch in CHAPTERS:
        print('       %s = %d' % (ch, stats[ch]))
    if dup:
        print('[WARN] 重复键 %d 个（已跳过）: %s' % (len(dup), dup[:5]))
    print('     文件大小 = %.1f KB' % (os.path.getsize(OUT) / 1024.0))


if __name__ == '__main__':
    main()
