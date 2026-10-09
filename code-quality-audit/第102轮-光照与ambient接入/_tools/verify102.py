# -*- coding: utf-8 -*-
u"""verify102.py —— 第102轮的**独立验收**：不看 build/check 的自报，重新读盘复算。

与 `check102.py` 的分工：check 是"以后每轮都要跑的锁"（进 G2），
本脚本是"这一轮交付前的独立复核"，**刻意用另一条代码路径**去算同样的量
（例如亮度用 `ImageStat` 而不是手写加权求和），好让两边互为对方的负控制。

守六件事
--------
 V1 四份证据 JSON 都能 parse，关键计数与登记一致
 V2 ★ 坐标锚点**独立复算**：用 `_room_geometry.json` 的房间几何（不是普查自己的结论）
 V3 ★★ 名单**三方一致**：磁盘 == `ingest102.json` == （普查图集名 − 缺的 1 张）
 V4 ★★ 逐张 sha256 / 尺寸 / 总字节**重新读盘**复算
 V5 ★ 亮度用**另一条路径**（`ImageStat.Stat`）复算，并验证"最暗两张"仍是 103 / 165
 V6 ★ 跨字段/跨文件自洽：五档分类与 `placed`/`opaque` 口径一致；
   且 A 档（"有瓦片却全透明"⇒ 合成退化成单色）独立复算**确实是单色图**
 V7 负控制：把一张图整体调亮 ⇒ V5 的"暗"判定必须翻转（证明判据有鉴别力）
"""
import hashlib
import io
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageStat                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
BGDIR = os.path.join(SCENES, 'bg')
EV = os.path.join(ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence')

PASS = 0
FAILS = []


def check(name, ok, detail=''):
    global PASS
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if ok:
        PASS += 1
    else:
        FAILS.append(name)


def jload(p):
    return json.load(io.open(p, encoding='utf-8'))


def sha16(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]


def png_size(p):
    h = open(p, 'rb').read(33)
    return struct.unpack('>II', h[16:24]) if h[:8] == b'\x89PNG\r\n\x1a\n' else None


def lum_stat(p):
    u"""另一条代码路径：`ImageStat` 的 RGB 均值 → 亮度（Rec.601 权重）。"""
    st = ImageStat.Stat(Image.open(p).convert('RGB'))
    r, g, b = [st.mean[i] for i in range(3)]
    return 0.299 * r + 0.587 * g + 0.114 * b


LIT = jload(os.path.join(EV, 'oneshot_lighting102.json'))
CEN = jload(os.path.join(EV, 'objects_census102.json'))
ING = jload(os.path.join(EV, 'ingest102.json'))
BRI = jload(os.path.join(EV, 'brightness102.json'))
GEO = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']

# ---------------------------------------------------------------- V1
ct = CEN['counts']
v1 = (ct['rooms_with_events'] == 244 and ct['rooms_with_visible_props'] == 189
      and ct['events'] == 11371 and ct['visible'] == 7805
      and ct['invisible_triggers'] == 3397 and ct['tile_graphic'] == 169
      and ct['charset_names'] == 149 and ct['frame_triples'] == 380
      and ct['out_of_bounds'] == 0)
check('V1 ★ 四份证据可解析且关键计数一致（244/189/11371/7805/3397/169/149/380/0）',
      v1, 'counts=%s' % json.dumps(ct, ensure_ascii=False))

# ---------------------------------------------------------------- V2
oob = []
for r in CEN['rooms']:
    g = GEO.get('oneshot:%d' % r['room_id'])
    if not g:
        oob.append((r['room_id'], 'no-geo'))
        continue
    tw, th = g['w'] // 16, g['h'] // 16
    for pr in r['props']:
        if not (0 <= pr['x'] < tw and 0 <= pr['y'] < th):
            oob.append((r['room_id'], pr['name'], pr['x'], pr['y']))
check('V2 ★ 坐标锚点**独立复算**（几何来自 `_room_geometry.json`，非普查自报）：0 越界',
      not oob, '不符 %d %s' % (len(oob), oob[:3]))

# ---------------------------------------------------------------- V3
disk = sorted(f[:-4] for f in os.listdir(PROPS) if f.lower().endswith('.png'))
ing_names = sorted(f['name'] for f in ING['files'])
cen_names = sorted(set(k for k, _v in CEN['names']) - set(CEN['missing_charsets']))
check('V3 ★★ 名单**三方一致**：磁盘 == ingest102 == （普查 149 − 缺 1）',
      disk == ing_names == cen_names == sorted(disk) and len(disk) == 148,
      '磁盘 %d / ingest %d / 普查 %d' % (len(disk), len(ing_names), len(cen_names)))

# ---------------------------------------------------------------- V4
man = {f['name']: f for f in ING['files']}
bad_sha = [n for n in disk if sha16(os.path.join(PROPS, n + '.png')) != man[n]['png_sha256']]
bad_size = [n for n in disk
            if png_size(os.path.join(PROPS, n + '.png')) != (man[n]['w'], man[n]['h'])]
tot = sum(os.path.getsize(os.path.join(PROPS, n + '.png')) for n in disk)
check('V4 ★★ 逐张 sha256 / 尺寸 / 总字节**重新读盘**复算一致',
      not bad_sha and not bad_size and tot == ING['total_bytes'],
      'sha 不符 %d / 尺寸不符 %d / 字节 %d vs %d'
      % (len(bad_sha), len(bad_size), tot, ING['total_bytes']))

# ---------------------------------------------------------------- V5
lums = {n: lum_stat(os.path.join(BGDIR, 'oneshot_map%d.png' % n))
        for n in range(1, 264)
        if os.path.isfile(os.path.join(BGDIR, 'oneshot_map%d.png' % n))}
order = sorted(lums, key=lambda k: lums[k])
mean_all = sum(lums.values()) / len(lums)
check('V5 ★ 亮度用 `ImageStat` 另一条路径复算：263 张、最暗两张仍是 103/165、均亮度 ≈30.75',
      len(lums) == 263 and order[:2] == [103, 165] and abs(mean_all - 30.75) <= 0.5,
      'n=%d 最暗=%s 均=%.3f' % (len(lums), order[:3], mean_all))

# ---------------------------------------------------------------- V6
# ★ 首跑这里写过一条**错判据**：我当成"A 档 ⇒ 均亮度 ≈ 0（全透明）"。
#   实测 map63 的合成图是**单一紫色 (133,65,209)**（均亮度 101.7）——
#   它的瓦片**全透明**，于是合成结果只剩 `oneshot_map_colors.json` 的**底色**。
#   ⇒ 正确的判据是「A 档 = 有瓦片却全透明 ⇒ 合成退化成**单色图**」，与亮度无关。
#   （老教训：判据报红**先怀疑判据**，别急着去改产品。）
rows = BRI['rows']
bad_cls = [r['room_id'] for r in rows
           if ((r['cls'] in 'DE') != (r['opaque'] > 0))
           or (r['cls'] == 'A' and not (r['placed'] > 0 and r['opaque'] == 0))
           or (r['cls'] in 'BC' and r['placed'] != 0)]
check('V6 ★ 五档分类与 `placed`/`opaque` 口径自洽（D/E 必有实心瓦片；A 有瓦片但全透明；'
      'B/C 无瓦片）', not bad_cls, '不符 %d %s' % (len(bad_cls), bad_cls[:3]))

a_rooms = [r['room_id'] for r in rows if r['cls'] == 'A']
uniq = {}
for n in a_rooms:
    p = os.path.join(BGDIR, 'oneshot_map%d.png' % n)
    im = Image.open(p).convert('RGB')
    uniq[n] = len(set(im.getdata()))
check('V6b ★★ A 档（空转）独立复算：确实退化成**单色图**（全图 RGB 唯一）',
      a_rooms and all(uniq[n] == 1 for n in a_rooms),
      'A 档 %s → 颜色数 %s' % (a_rooms, uniq))

check('V6c ★ 登记一致：五档求和 == 263，D=221（有实心瓦片却均亮度 < 90）',
      sum(BRI['classes'].values()) == 263 and BRI['classes'].get('D') == 221,
      str(dict(sorted(BRI['classes'].items()))))

# V6d ★ 与**第101轮**的独立登记对账（跨轮、跨来源的锚点）
import re                                                          # noqa: E402
mf = jload(os.path.join(ROOT, 'code-quality-audit', '第101轮-OneShot背景落盘与场景接线',
                        '_evidence', 'bg_manifest101.json'))
num = set(int(re.search(r'(\d+)', f).group(1)) for f in (mf.get('solid_empty_rooms') or []))
gho = set(int(re.search(r'(\d+)', f).group(1))
          for f in (mf.get('solid_transparent_ghosts') or []))
B_ = set(r['room_id'] for r in rows if r['cls'] == 'B')
C_ = set(r['room_id'] for r in rows if r['cls'] == 'C')
A_ = set(r['room_id'] for r in rows if r['cls'] == 'A')
check('V6d ★★ 与第101轮登记对账：单色空房 13 == B(2)+C(11)；全透明占位 1 == A(1) == {63}',
      num == (B_ | C_) and gho == A_ == {63},
      '13==%d+%d ｜ %s vs %s' % (len(B_), len(C_), sorted(gho), sorted(A_)))

# ---------------------------------------------------------------- V7
im = Image.open(os.path.join(BGDIR, 'oneshot_map103.png')).convert('RGB')
up = im.point(lambda v: min(255, v + 120))
tmp = os.path.join(EV, '_neg102.png')
up.save(tmp)
lu = lum_stat(tmp)
os.remove(tmp)
check('V7 负控制：map103 提亮 +120 后**必须**跌出"暗（<32）"（证明 V5 有鉴别力）',
      lums[103] < 32 <= lu, '%.3f → %.3f' % (lums[103], lu))

print()
print('=' * 70)
print('verify102：PASS=%d FAIL=%d（共 %d 条判据）' % (PASS, len(FAILS), PASS + len(FAILS)))
print('FAIL = %d %s' % (len(FAILS), FAILS))
sys.exit(1 if FAILS else 0)
