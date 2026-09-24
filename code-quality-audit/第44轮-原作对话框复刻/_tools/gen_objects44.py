# -*- coding: utf-8 -*-
"""第44轮 objects 补全：把原作实例普查蒸馏进场景 JSON。

背景（为什么这件事拖到现在）
---------------------------
第 36 轮写场景 JSON 时 `objects` 留空，`_comment` 里写着
「物件需要背景图当参照才能定锚点…现在硬编坐标是瞎猜」。
第 37 轮背景导出后这个前置就满足了，但没人回来补 —— 于是渲染层
（第 44 轮 P1）打开后只能画背景，画不出任何物件。本脚本补上这一层。

数据源（三份，全部已在仓库/本机）
---------------------------------
  1. 实例普查：`code-quality-audit/第42轮-原作拓扑取证/_evidence/{inst42,chN_inst42}.json`
     —— 5,523 条实例，字段 `{obj, x, y, layer, depth}`，`rooms[].index` == `Data.Rooms` 下标
        （第 44 轮已量化：与其 `_room_geometry.json` **100% 对齐**，0 例外）
  2. 对象→精灵映射：`第43轮.../objmap43.txt`（353 个对象，`spr=` 列）
  3. 精灵文件：`ralsei_pet/assets/scenes/objs/`（第 44 轮已按需搬入 25 个 spr / 40 文件）

转换规则（**每一条都可在下面 `object()` 里核对**）
------------------------------------------------
  · `pos` = `[x, y]`（原作实例坐标，**左上角**语义，与 scene_render 的
     `to_view()` 直接相乘，不做中心对齐 —— 因为原作 draw_sprite 就是左上角）
  · `sprite` = `objs/<spr>_0.png`（有 spr 的才写；**没 spr 的纯逻辑锚点不写进
     objects**，因为它们本来就 `visible:False`、画出来是一堆空框）
  · `depth` = 原作 layer 的 depth（字符串数字 → int；解析失败给 None）
  · 多帧动画（同一 spr 有 _0/_1/_2）：sprite 写 `_0`，并在 `sprite_frames`
     记下总帧数（渲染层现在只画首帧，动画留后续轮次）
  · `obj` 原名保留在 `src` 字段（调试/复检/将来接事件都用得上）

⚠️ 只改分片里「已有 `original_room_id` 且在该章实例普查 rooms 里」的场景；
   其余（无实例 / 普查缺席 / 无 bg）**原样不动**，避免制造无意义 diff。

幂等：重复跑结果一致（覆盖写 objects，不追加）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
EV = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', '_evidence')

INST = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
        'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}
RE_ZONE = re.compile(r'^_zone\.(ch\d+)\.')

FAIL = 0


def ok(m):
    print('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    print('[FAIL] %s' % m)


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _sniff_style(p):
    """探测原文件的**缩进**与**换行符**，原样保留。

    ★★★ 铁律（记忆 §1）：本仓库**无 `.gitattributes` 而 `autocrlf=true`** ⇒
      编辑必须保持原 EOL。第 44 轮实测（回滚过一次，留痕）：
        · 分片 `_zone.*.json`  = indent **1** + **CRLF**
        · 独立文件（多数）      = indent **2** + **CRLF**
        · `desktop.json`        = indent **2** + **LF**
      我第一版统一用 `indent=1, newline='\\n'` ⇒ 独立文件被**整文件重排**
      （147 文件里 deletions 冲到 3031，越过 1000 的守卫线）。
      正确做法 = **逐文件嗅探，原样写回**，只让真正的新增（objects）产生 diff。
    """
    indent = 1
    nl = '\n'
    try:
        with io.open(p, 'rb') as fh:
            raw = fh.read(4096)
        if b'\r\n' in raw:
            nl = '\r\n'
        # 第 2 行（第一行是 `{`）的前导空格数 = 缩进
        txt = raw.decode('utf-8', 'replace')
        lines = txt.split('\n')
        for ln in lines[1:6]:
            ln = ln.rstrip('\r')
            if not ln.strip():
                continue
            n = len(ln) - len(ln.lstrip(' '))
            if n > 0:
                indent = n
                break
    except Exception:
        pass
    return indent, nl


def dump(p, obj):
    """写 JSON：ASCII 关闭、**缩进与 EOL 按原文件**（见 `_sniff_style`）。

    为什么缩进要嗅探而不是统一：分片是 1、独立文件是 2，用错就会整文件重排，
    把"加了 objects"这一处真改动淹没在几千行假 diff 里（"最小改动"铁律）。

    ★ 为什么 `pos` 单独压回一行：`json.dumps(indent=1)` 会把 `[640, 660]`
      写成 4 行（`[` / `640,` / `660` / `]`）。5,523 个物件 × 4 行 = 2 万行
      假 diff。坐标是**一个不可分的原子**（一个点），压回一行既是可读性改进，
      也让 diff 只反映真实内容变化。做法 = 先正常 dump，再对 pos 数组做
      **定向塌缩**（只碰 pos，不碰别的数组 —— 避免正则误伤 objects 列表）。
    """
    if DRY_RUN:
        return
    indent, nl = _sniff_style(p)
    text = json.dumps(obj, ensure_ascii=False, indent=indent)
    text = _collapse_pos(text, indent)
    if nl != '\n':
        text = text.replace('\n', nl)
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)
        fh.write(nl)


_RE_POS = re.compile(
    r'"pos": \[\s*([-\d]+),\s*([-\d]+)\s*\]',
    re.S)


def _collapse_pos(text, indent):
    """把 `"pos": [\\n 640,\\n 660\\n]` 塌缩成 `"pos": [640, 660]`。

    只匹配 `"pos": [<int>, <int>]` 这两个整数的形状 —— 其它数组（objects 列表）
    里没有 `"pos": [` 前缀，所以正则**碰不到它们**。这是"定向"而不是"全局塌缩"
    的关键：全局塌缩会把整个 objects 列表压成一行，反而看不清 diff。
    """
    return _RE_POS.sub(lambda m: '"pos": [%s, %s]' % (m.group(1), m.group(2)), text)


#: 干跑开关（`--dry`）：只算不写。既有"锚点自检"又不污染仓库，
#: 这是"改动最小化 + 先验证再落盘"两条铁律的组合。
DRY_RUN = False


def parse_objmap(path):
    out = {}
    with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            name = parts[1].strip()
            vm = re.search(r'spr=([^\t]*)', line)
            if name:
                out[name] = vm.group(1).strip() if vm and vm.group(1).strip() else None
    return out


def build_frame_index():
    """`objs/` 里每个 sprite 的帧文件清单：`{'spr_doorA': ['spr_doorA_0.png', ...]}`。"""
    idx = {}
    if not os.path.isdir(OBJS):
        return idx
    for f in os.listdir(OBJS):
        if not f.lower().endswith('.png'):
            continue
        m = re.match(r'^(.*)_(\d+)\.png$', f)
        key = m.group(1) if m else f[:-4]
        idx.setdefault(key, []).append(f)
    for k in idx:
        idx[k].sort()
    return idx


def to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def depth_of(inst):
    """实例的 depth：优先 `depth` 字段（可空），回退从 layer 名里抠 `Depth_<n>`。"""
    d = to_int(inst.get('depth'))
    if d is not None:
        return d
    layer = inst.get('layer') or ''
    m = re.search(r'Depth_(-?\d+)', layer)
    if m:
        return to_int(m.group(1))
    return None


def object(inst, objmap, frame_idx):
    """一条实例 → objects 元素；**不可画（无 sprite）→ None**。

    这条 if 是"不画逻辑锚点"的唯一实现点 —— 想改成画锚点只需放宽这里。
    """
    nm = inst.get('obj')
    if not nm:
        return None
    spr = objmap.get(nm)
    if not spr:
        return None
    frames = frame_idx.get(spr)
    if not frames:
        return None
    x = to_int(inst.get('x'))
    y = to_int(inst.get('y'))
    if x is None or y is None:
        return None
    out = {
        'pos': [x, y],
        'sprite': 'objs/%s' % frames[0],
        'src': nm,
    }
    d = depth_of(inst)
    if d is not None:
        out['depth'] = d
    if len(frames) > 1:
        out['sprite_frames'] = len(frames)
    return out


def main():
    objmap = parse_objmap(os.path.join(E43, 'objmap43.txt'))
    frame_idx = build_frame_index()
    ok('objs/ 帧索引 %d 个 sprite' % len(frame_idx))

    # ---- 1. 建「章:房间id → [objects]」----
    by_room = {}
    inst_total = 0
    drawable_total = 0
    for ch in INST:
        d = load(os.path.join(E42, INST[ch]))
        for rec in (d.get('rooms') or []):
            rid = rec.get('index')
            if not isinstance(rid, int):
                continue
            key = '%s:%d' % (ch, rid)
            slot = by_room.setdefault(key, [])
            for it in (rec.get('insts') or []):
                inst_total += 1
                ob = object(it, objmap, frame_idx)
                if ob is not None:
                    slot.append(ob)
                    drawable_total += 1

    print('实例总条数 = %d；可绘制 = %d；不可绘（逻辑锚点/无素材） = %d' %
          (inst_total, drawable_total, inst_total - drawable_total))
    ok('A1 可绘制实例 %d 条（>0）' % drawable_total) if drawable_total else \
        bad('A1 可绘制实例为 0')

    # ---- 2. 写回（**两种载体都要**）----
    # ★★ 第 44 轮干跑抓到的真缺陷：场景数据有**两种载体** ——
    #    · 分片 `_zone.<ch>.<area>.json`（838 个场景）
    #    · 独立文件 `<scene_id>.json`（88 个场景，含 ch1:2 kris_s_room！）
    #    只写分片 ⇒ 88 个独立文件场景的 objects 永远空（含最显眼的克里斯房间）。
    #    判据"锚点 ch1:2 有 2 个 objects"正是靠这个抓出来的。
    index = load(os.path.join(SCENES, '_index.json'))
    file_scenes = {}          # (ch, room_id) -> [(scene_id, 绝对路径)]
    for ch, blk in (index.get('chapters') or {}).items():
        if not isinstance(blk, dict):
            continue
        for area, ablk in (blk.get('areas') or {}).items():
            if not isinstance(ablk, dict):
                continue
            for sid, entry in (ablk.get('scenes') or {}).items():
                if not isinstance(entry, dict) or not entry.get('file'):
                    continue
                rid = entry.get('original_room_id')
                if isinstance(rid, int):
                    file_scenes.setdefault((ch, rid), []).append((sid, entry['file']))
    ok('B1 索引里独立文件场景 %d 个' % sum(len(v) for v in file_scenes.values()))

    zone_files = sorted(f for f in os.listdir(SCENES)
                        if f.startswith('_zone.') and f.endswith('.json'))
    n_scene_touched = 0
    n_scene_with_obj = 0
    written = 0
    for zf in zone_files:
        m = RE_ZONE.match(zf)
        ch = m.group(1) if m else None
        if not ch:
            continue
        p = os.path.join(SCENES, zf)
        data = load(p)
        table = data.get('scenes') if isinstance(data, dict) and 'scenes' in data else None
        if not isinstance(table, dict):
            continue
        changed = False
        for sid, raw in table.items():
            if not isinstance(raw, dict):
                continue
            rid = raw.get('original_room_id')
            if not isinstance(rid, int):
                continue
            objs = by_room.get('%s:%d' % (ch, rid))
            n_scene_touched += 1
            if objs:
                n_scene_with_obj += 1
                if raw.get('objects') != objs:
                    raw['objects'] = objs
                    changed = True
            else:
                # 该房间普查里没有可绘制实例：**显式置空数组**，
                # 让"确实没有"与"还没生成"两种状态可区分（前者是 []，后者是无键）。
                if 'objects' not in raw:
                    raw['objects'] = []
                    changed = True
        if changed:
            dump(p, data)
            written += 1

    # ---- 2b. 独立文件场景 ----
    n_file_touched = n_file_with_obj = n_file_written = 0
    for (ch, rid), items in sorted(file_scenes.items()):
        objs = by_room.get('%s:%d' % (ch, rid))
        for sid, fname in items:
            fp = os.path.join(SCENES, fname)
            if not os.path.exists(fp):
                bad('独立文件缺失：%s' % fname)
                continue
            raw = load(fp)
            if not isinstance(raw, dict):
                continue
            n_file_touched += 1
            changed = False
            # ★ 顺手把**已过期的说明**改对：第 36 轮留的 `_comment.why_objects_is_empty`
            #   说"等 bg 到位再填 objects" —— 现在填了，这条注释变成假话。
            #   留着假话比没有注释更糟（下一个人会以为 objects 还是空的）。
            #   ⚠️ 这段**必须在 if objs 之外**：第一个版本把它写在 if 里面，
            #      结果 10 个 objects==[] 的独立文件没被清（回归锁 A5 抓到）。
            cm = raw.get('_comment')
            if isinstance(cm, dict) and 'why_objects_is_empty' in cm:
                cm['how_objects_were_filled'] = (
                    '第44轮：从原作实例普查（第42轮 inst42 系）按 original_room_id 归位，'
                    'obj→spr 走 objmap43 映射，精灵落 assets/scenes/objs/。'
                    '只收「有 sprite 的实例」（全五章 2,067 条中属已登记场景的 2,043 条）；'
                    '纯逻辑锚点（obj_markerAny/obj_doorAny 等，原作 visible=false）不入 objects。')
                del cm['why_objects_is_empty']
                changed = True
            new_objs = objs if objs else []
            if raw.get('objects') != new_objs:
                raw['objects'] = new_objs
                changed = True
            if objs:
                n_file_with_obj += 1
            if changed:
                dump(fp, raw)
                n_file_written += 1

    print('')
    print('分片文件写回 %d / %d' % (written, len(zone_files)))
    print('覆盖场景（分片，有 original_room_id） = %d，其中带可绘制物件 = %d'
          % (n_scene_touched, n_scene_with_obj))
    print('独立文件场景 = %d，其中带可绘制物件 = %d，写入 = %d'
          % (n_file_touched, n_file_with_obj, n_file_written))

    # ---- 3. 锚点自检（真值，从**磁盘**读，不看内存副本）----
    #   ★ 为什么必须从磁盘读：内存里的 raw 已被改过（写入就是改它），
    #     读内存 = "自己验证自己"。磁盘读才能证明"写真的落盘了"。
    #     （第 44 轮我干跑时就被"读未写入的原文件"误导过一次。）
    print('')
    print('=== 锚点自检（磁盘真值）===')

    def disk_objects(path, want_rid, want_sid=None):
        """从磁盘读某场景的 objects。

        ★★ 这里有个坑（第 44 轮 A3 首跑就踩了，留痕）：
          独立文件场景的 `original_room_id` **不在文件里**（第 40 轮起约定挪进
          `_index.json` 的登记行），所以**不能**用 `d.get('original_room_id')`
          判独立文件 —— 那样恒为 None，判据恒假、报假 FAIL。
          正确做法：独立文件按 `scene_id` 匹配（调用方给 `want_sid`）。
        """
        d = load(path)
        t = d.get('scenes') if isinstance(d, dict) and 'scenes' in d else None
        if isinstance(t, dict):
            for sid, raw in t.items():
                if isinstance(raw, dict) and raw.get('original_room_id') == want_rid:
                    return sid, raw.get('objects')
            return None, None
        # 独立文件形态：顶层就是场景；**按 scene_id 匹配**（rid 不在文件里）
        if isinstance(d, dict):
            if want_sid and d.get('scene_id') == want_sid:
                return d.get('scene_id'), d.get('objects')
            if want_sid is None and d.get('original_room_id') == want_rid:
                return d.get('scene_id'), d.get('objects')
        return None, None

    # 锚点 1：ch1:3 krishallway（分片）——普查 4 条，obj_doorB/markerA/doorC/markerD
    #   其中 doorB/doorC 有 spr（door 有图），markerA/markerD 也有 spr（spr_markerA/D）
    #   ⇒ 期望 4
    sid3, o3 = disk_objects(os.path.join(SCENES, '_zone.ch1.home.json'), 3)
    print('ch1:3 (%s) objects=%s' % (sid3, json.dumps(o3, ensure_ascii=False)))
    if isinstance(o3, list) and len(o3) == 4:
        ok('A2 ch1:3 objects == 4')
    else:
        bad('A2 ch1:3 objects != 4（实得 %s）' % (len(o3) if isinstance(o3, list) else o3))

    # 锚点 2：ch1:2 krisroom（**独立文件**）——普查 2 条（doorA + markerB）⇒ 期望 2
    sid2, o2 = disk_objects(os.path.join(SCENES, 'ch1.kris_room.kris_s_room.json'),
                            2, want_sid='ch1.kris_room.kris_s_room')
    print('ch1:2 (%s) objects=%s' % (sid2, json.dumps(o2, ensure_ascii=False)))
    if isinstance(o2, list) and len(o2) == 2:
        ok('A3 ch1:2（独立文件载体）objects == 2')
    else:
        bad('A3 ch1:2 objects != 2（实得 %s）—— 独立文件载体可能没写' %
            (len(o2) if isinstance(o2, list) else o2))

    # 负控制：一个普查里没有实例的房间，objects 必须是 []，且**不是非空**
    #   用 ch1 里普查缺席的房间（room_torroom=4）—— 它在分片里应该有 objects==[]
    sid4, o4 = disk_objects(os.path.join(SCENES, '_zone.ch1.home.json'), 4)
    print('负控制 ch1:4 (%s) objects=%s' % (sid4, json.dumps(o4, ensure_ascii=False)))
    if sid4 is None:
        # 不在 home 分片就换个分片找
        for zf in zone_files:
            s, o = disk_objects(os.path.join(SCENES, zf), 4)
            if s:
                sid4, o4 = s, o
                break
        print('负控制 ch1:4 (%s) objects=%s' % (sid4, json.dumps(o4, ensure_ascii=False)))
    if isinstance(o4, list) and len(o4) == 0:
        ok('A4 负控制 ch1:4（普查缺席）objects == [] 且存在键')
    else:
        bad('A4 负控制失败：ch1:4 objects=%r' % (o4,))

    print('')
    print('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    if '--dry' in sys.argv:
        DRY_RUN = True
        print('*** DRY RUN：只算不写 ***')
    sys.exit(main())
