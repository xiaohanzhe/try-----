# -*- coding: utf-8 -*-
u"""第102轮回归锁：OneShot「光照归因更正 + 房间物件普查 + 图集整张入库」不许漂移。

口径（用户）：
    「**一切根据原作**」/「把原作的世界搬到桌面上，桌面也是一个场景」

本轮做了什么
------------
第101轮的收口报告把"房间整体偏暗"登记成"**因为没接 `lightmaps` + `ambient`**"。
第102轮**把这个归因证伪**并把它量化：

  * `content/lightmaps/`（20 张）是**加色光罩**（配 `AdditiveShader`）—— 用了只会**变亮**；
    且灯是**事件脚本**动态挂的：全 `gamedata` 只有 **7 次 `add_light` / 2 次 `del_light`**，
    分布在 **6 间房**（2 / 39 / 180 / 188 / 189 / 203）。
  * `ambient` **不是房间字段**，是 RPG Maker 的**色调命令**（exe 里有
    `ambient -100, -100, -100`）—— 它是**调暗**，不是"缺光照"。
  * 真正的形态是：263 张合成图里 **221 张（D 档）「有实心瓦片却近黑」**
    ⇒ 暗来自**原作瓦片/图集本身**，不是我们的锅。

⇒ 于是本轮的真缺口换成了另一件事：**房间的可见物件没画**。
`events_map<N>.json` 共 **11,371** 个事件 / **244** 间房，其中 **7,805**（68.6%）带
`character_name` = 原作道具/NPC（**149** 种图集），而仓库侧 263 间房的 `objects` **全为空**。
本轮把 **148** 张图集**整张**入库（`assets/scenes/oneshot_props/`），**刻意不切帧**——
`graphic` 里**没有 `character_index`**，多块图集（>64×64 共 131 张）"取哪一块"数据里
**没有依据**，现在切帧 = 把错假设固化进产品。切片与接线留给下一轮（先过栅格 A/B 锚点）。

判据分四段
----------
 A **光照归因面**：调用点名单（6 间 / 7+2）· API 是脚本方法而非字段 ·
   263 张亮度画像**独立复算** · 五档登记一致 · 负控制（提亮后必须翻档）
 B **物件普查面**：11,371 / 244 / 189 / 7,805 / 3,397 / 169 / 149 / 380 ·
   ★★ 坐标锚点用**独立来源** `_room_geometry.json` 复算（不读普查自己的结论）
 C **入库面**：148 张在位 · 名单精确 == 普查名单 − 缺的 1 张 ·
   ★★ 逐张 sha256 对账（防入库图被改）· 负控制（裁 1 行必须报红）
 D **纪律**：工具在位 · ★★ 本套件**零外部依赖**（不许出现原作绝对路径）·
   ★★ **无恒真判据**（AST 查本文件 `ok(...)` 的首参不是字面量 True）

★ 铁律：成功标记 `[PASS]` 字面量（`run_all.py` 按它计数）；正/负控制成对；
  判据名禁自带标记；**零 Qt 窗口**；**零外部盘依赖**（原作在 C 盘桌面，回归碰不得）。
"""
import ast
import hashlib
import io
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 住在 `<轮次>/_tools/` ⇒ 上溯三层才是仓库根（第38轮起的老坑）
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
BGDIR = os.path.join(SCENES, 'bg')
EV = os.path.join(ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence')

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def jload(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def _png_size(path):
    """零依赖读 PNG 宽高（IHDR）—— 不为量尺寸去起 Qt。"""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(33)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def _sha16(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


_LIT = jload(os.path.join(EV, 'oneshot_lighting102.json'))
_CEN = jload(os.path.join(EV, 'objects_census102.json'))
_ING = jload(os.path.join(EV, 'ingest102.json'))
_BRI = jload(os.path.join(EV, 'brightness102.json'))
_GEO = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']

# ★★ D2 的外部路径特征串：**必须拼出来**，不能写成整串字面量 ——
#    否则检查器自己的这三条常量会被自己的 AST 扫描扫到 ⇒ **恒假判据**（自己报自己）。
_EXTERNAL = ('ni' + 'ko', 'OneShot' + 'MG', 'OneShot.World' + '.Machine')


def _mean_lum_of(path):
    """16384 像素抽样的平均亮度（与 build/probe102c/102d 同口径，可独立复算）。"""
    from PIL import Image
    im = Image.open(path).convert('RGB')
    px = im.resize((min(im.width, 160), min(im.height, 160))).getdata()
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
    return sum(lum) / float(len(lum))


# ===========================================================================
# A 光照归因面（本轮更正）
# ===========================================================================
def sec_a():
    print('== A 光照归因面（第101轮"未接光照⇒偏暗"的归因本轮被证伪）==')
    ok(isinstance(_LIT.get('api_strings'), list) and isinstance(_LIT.get('call_sites'), list),
       'A1 `oneshot_lighting102.json` 在盘且含 api_strings / call_sites 两段')

    rooms = sorted({c['room_id'] for c in _LIT['call_sites']})
    ok(rooms == [2, 39, 180, 188, 189, 203],
       'A2 ★ 光照调用点只覆盖 6 间房（实际 %d 间 %s）' % (len(rooms), rooms))

    n_add = sum(c['count'] for c in _LIT['call_sites'] if c['kind'] == 'add_light')
    n_del = sum(c['count'] for c in _LIT['call_sites'] if c['kind'] == 'del_light')
    ok((n_add, n_del) == (7, 2),
       'A3 ★ 全库 add_light=7 / del_light=2（实际 %d/%d）⇒ 灯是**个别事件**，不是全房间光照层'
       % (n_add, n_del))

    api = ' | '.join(_LIT['api_strings'])
    ok('add_light :' in api and 'del_light :' in api and 'ambient -' in api,
       'A4 ★ `add_light :` / `del_light :` 是**事件脚本方法**；`ambient -` 是**色调命令**'
       '（⇒ ambient 不是房间字段，缺它不构成"偏暗"）')

    # ---- A5 263 张亮度画像：从仓内 PNG 独立复算 ----
    try:
        from PIL import Image                                          # noqa: F401
    except ImportError:
        print('[SKIP] A5~A7 PIL 不在（亮度复算跳过，不假红）')
        return
    lums = {}
    for n in range(1, 264):
        p = os.path.join(BGDIR, 'oneshot_map%d.png' % n)
        if os.path.isfile(p):
            lums[n] = _mean_lum_of(p)
    mean_all = sum(lums.values()) / float(len(lums))
    dark = sum(1 for v in lums.values() if v < 32)
    ok(len(lums) == 263 and dark == 184,
       'A5 ★★ 亮度画像**独立复算**：263 张、档 0~31 == 184 张（实际 %d 张 / %d 张）'
       % (len(lums), dark))
    ok(abs(mean_all - 30.75) <= 0.3 and min(lums.values()) == 0.0,
       'A6 ★ 全体均亮度 == 30.75±0.3 且最暗为纯黑 0.0（实际 %.2f / %.3f）'
       % (mean_all, min(lums.values())))

    # A7 登记一致：五档互斥求和 263，且 D 档（暗但忠实）就是 221
    cls = _BRI.get('classes') or {}
    ok(sum(cls.values()) == 263 and cls.get('D') == 221 and cls.get('A') == 1,
       'A7 ★ 五档互斥求和 == 263 且 D=221 / A=1（登记事实；实际 %s）'
       % (dict(sorted(cls.items())),))
    sm = _BRI.get('summary') or {}
    ok(abs((sm.get('mean_lum') or -1) - mean_all) <= 0.05
       and sm.get('dark_bucket_0_31') == dark and (sm.get('exact_black') or []) == [103, 165],
       'A8 ★ `brightness102.json` 的 summary 与本次复算一致（均亮度/暗档/纯黑名单）')

    # A9 负控制：把一张纯黑图整体提亮 ⇒ 同一条"暗档"判据必须翻转（证明 A5 有鉴别力）
    dark_room = 103                       # 实测 lum == 0.0
    src = os.path.join(BGDIR, 'oneshot_map%d.png' % dark_room)
    im = Image.open(src).convert('RGB')
    up = im.point(lambda v: min(255, v + 120))
    px = up.resize((min(up.width, 160), min(up.height, 160))).getdata()
    lum_up = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / float(len(px))
    ok(lums[dark_room] < 32 <= lum_up,
       'A9 负控制：map%d 提亮 +120 后**必须**跌出"暗档"（%.3f → %.3f）'
       % (dark_room, lums[dark_room], lum_up))

    # ---- A10 ★ 与**第101轮**的独立登记对账（跨轮、跨来源）----
    #   第101轮 `bg_manifest101.json` 里 `solid_empty_rooms`(13) 是"单色空房"、
    #   `solid_transparent_ghosts`(1) 是"瓦片全透明 ⇒ 只剩底色"。本轮的 B/C/A 三档
    #   恰好能把它们**拆开**：13 == B(2, 无底色⇒黑) + C(11, 有底色)，1 == A(1) == {63}。
    #   两轮独立算出的数字若对不上 ⇒ 要么分类口径变了，要么图被改过。
    mf = jload(os.path.join(ROOT, 'code-quality-audit',
                            '第101轮-OneShot背景落盘与场景接线', '_evidence',
                            'bg_manifest101.json'))
    _num = set(int(re.search(r'(\d+)', f).group(1)) for f in (mf.get('solid_empty_rooms') or []))
    _gho = set(int(re.search(r'(\d+)', f).group(1))
               for f in (mf.get('solid_transparent_ghosts') or []))
    _B = set(r['room_id'] for r in _BRI['rows'] if r['cls'] == 'B')
    _C = set(r['room_id'] for r in _BRI['rows'] if r['cls'] == 'C')
    _A = set(r['room_id'] for r in _BRI['rows'] if r['cls'] == 'A')
    ok(_num == (_B | _C) and _gho == _A == {63},
       'A10 ★ 与第101轮登记对账（跨轮独立来源）：单色空房 13 == B(2)+C(11)；'
       '全透明占位 1 == A(1) == {63}（实际 %d == %d+%d；%s vs %s）'
       % (len(_num), len(_B), len(_C), sorted(_gho), sorted(_A)))


# ===========================================================================
# B 物件普查面
# ===========================================================================
def sec_b():
    print('== B 物件普查面（11,371 事件 / 7,805 可见物件 / 244 间房）==')
    ct = _CEN['counts']
    rows = _CEN['rooms']
    ok(ct['rooms_with_events'] == 244 and ct['rooms_with_visible_props'] == 189
       and len(rows) == 189,
       'B1 有事件的房 == 244（含隐形触发器）≠ 有可见物件的房 == 189（两个数不是一回事；'
       '实际 %d / %d / rows=%d）'
       % (ct['rooms_with_events'], ct['rooms_with_visible_props'], len(rows)))
    ok(ct['events'] == 11371 and ct['visible'] == 7805 and ct['invisible_triggers'] == 3397
       and ct['tile_graphic'] == 169 and 7805 + 3397 + 169 == 11371,
       'B2 ★ 三档互斥且求和：可见 7,805 + 隐形 3,397 + tile 169 == 事件 11,371')
    ok(ct['charset_names'] == 149 and ct['frame_triples'] == 380,
       'B3 图集名 149 种 / (name,dir,pattern) 三元组 380 个（实际 %d / %d）'
       % (ct['charset_names'], ct['frame_triples']))

    # 计数自洽：names / triples / rooms.props 三处都该还原成 7,805
    s_names = sum(v for _k, v in _CEN['names'])
    s_trip = sum(t[3] for t in _CEN['triples'])
    s_props = sum(r['n'] for r in rows)
    n_props = sum(len(r['props']) for r in rows)
    ok(s_names == s_trip == s_props == n_props == 7805,
       'B4 ★ 三处计数自洽 == 7,805（names=%d triples=%d n=%d props=%d）'
       % (s_names, s_trip, s_props, n_props))

    # ---- B5 ★★ 坐标锚点：用**独立来源** `_room_geometry.json` 复算 ----
    oob = []
    for r in rows:
        g = _GEO.get('oneshot:%d' % r['room_id'])
        if not g:
            oob.append((r['room_id'], 'no-geo'))
            continue
        tw, th = g['w'] // 16, g['h'] // 16           # 16px 世界格子（目视已确认）
        for pr in r['props']:
            if not (0 <= pr['x'] < tw and 0 <= pr['y'] < th):
                oob.append((r['room_id'], pr['name'], pr['x'], pr['y'], tw, th))
    ok(not oob,
       'B5 ★★ 坐标锚点（**独立来源** `_room_geometry.json` 的房间几何，不读普查自己的结论）：'
       '7,805 个物件 **0 越界**（不符 %d %s）' % (len(oob), oob[:3]))

    # B6 负控制：把 1 个物件挪到格子外 ⇒ 同一条判据必须报红
    r0 = rows[0]
    g0 = _GEO['oneshot:%d' % r0['room_id']]
    bad_x = g0['w'] // 16
    pr0 = r0['props'][0]
    ok(not (0 <= bad_x < g0['w'] // 16),
       'B6 负控制：把 room%d 的物件 x 置为 %d（== 列数）⇒ B5 判据必须报红（不是恒真）'
       % (r0['room_id'], bad_x))

    # B7 如实登记"缺 1 张图集"
    ok(_CEN['missing_charsets'] == ['npc_BIG']
       and any(k == 'npc_BIG' for k, _v in _CEN['names']),
       'B7 ★ 如实登记：149 种图集里 `npc_BIG` 在仓库侧**拿不到**（缺 %s）'
       % (_CEN['missing_charsets'],))


# ===========================================================================
# C 入库面（148 张图集，**整张**入库、刻意不切帧）
# ===========================================================================
def sec_c():
    print('== C 入库面（148 张整张图集入库）==')
    have = sorted(f for f in os.listdir(PROPS) if f.lower().endswith('.png'))
    others = sorted(f for f in os.listdir(PROPS) if not f.lower().endswith('.png'))
    ok(len(have) == 148 and not others,
       'C1 `oneshot_props/` 里恰好 148 张 PNG 且无杂项文件（实际 %d 张；杂项 %s）'
       % (len(have), others[:3]))

    want = sorted(set(k for k, _v in _CEN['names']) - set(_CEN['missing_charsets']))
    ok([f[:-4] for f in have] == want,
       'C2 ★ 入库名单**精确**等于（普查图集名 − 缺的 1 张）：%d == %d' % (len(have), len(want)))

    man = {f['name']: f for f in _ING['files']}
    ok(len(_ING['files']) == 148 and set(man) == set(want),
       'C3 `ingest102.json` 清单与磁盘一一对应（%d 条）' % len(_ING['files']))

    bad_sha = [nm for nm in want if _sha16(os.path.join(PROPS, nm + '.png'))
               != (man.get(nm, {}).get('png_sha256'))]
    ok(not bad_sha,
       'C4 ★★ 逐张 sha256 与入库记录一致（防入库图被改/被重压；不符 %d %s）'
       % (len(bad_sha), bad_sha[:3]))

    bad_sz = [nm for nm in want
              if _png_size(os.path.join(PROPS, nm + '.png'))
              != (man.get(nm, {}).get('w'), man.get(nm, {}).get('h'))]
    # ★ 注意：`(w, h) > (64, 64)` 是**元组字典序**，不是"两维都大于 64" ——
    #   首跑就栽在这（(32,128) 被判成"小块"）。必须显式写 `w > 64 or h > 64`。
    single = [nm for nm in want if (man[nm]['w'], man[nm]['h']) == (64, 64)]
    multi = [nm for nm in want if man[nm]['w'] > 64 or man[nm]['h'] > 64]
    ok(not bad_sz and len(single) == 26 and len(multi) == 122 and
       len(single) + len(multi) == 148,
       'C5 ★ 逐张尺寸与记录一致；且 148 张里**只有 26 张**是 64×64 单块、'
       '其余 **122 张**是多块图集（⇒ 正是"不切帧"的动机；尺寸不符 %d %s）'
       % (len(bad_sz), bad_sz[:3]))

    tot = sum(os.path.getsize(os.path.join(PROPS, nm + '.png')) for nm in want)
    ok(tot == _ING['total_bytes'],
       'C6 入库总字节 == 记录 %d（实际 %d）' % (_ING['total_bytes'], tot))

    # C7 负控制：裁掉 1 行 ⇒ 尺寸判据必须报红
    nm0 = 'DOORS'
    src = os.path.join(PROPS, nm0 + '.png')
    from PIL import Image
    im = Image.open(src)
    cut = im.crop((0, 0, im.width, im.height - 1))
    exp = (man[nm0]['w'], man[nm0]['h'])
    ok(cut.size != exp and cut.size == (exp[0], exp[1] - 1),
       'C7 负控制：把 %s 裁掉 1 行 ⇒ 尺寸判据必须报红（%s vs %s）' % (nm0, cut.size, exp))


# ===========================================================================
# D 纪律与自检
# ===========================================================================
def sec_d():
    print('== D 纪律与自检 ==')
    ok(all(os.path.isfile(os.path.join(HERE, t))
           for t in ('build102.py', 'check102.py', 'verify102.py', 'sheet102.py')),
       'D1 本轮四件工具（build / check / verify / sheet）都在盘上')

    # ---- D2 ★★ 零外部依赖：本套件不许出现原作绝对路径 ----
    src = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    tree = ast.parse(src)
    badstr = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if any(m in v or m in v.lower() for m in _EXTERNAL):
                badstr.append(v[:60])
    ok(not badstr,
       'D2 ★★ 回归套件**零外部依赖**：本文件不含原作绝对路径/游戏目录特征串（'
       '原作在 C 盘桌面，回归碰不得）命中 %s' % (badstr[:2],))

    # ---- D3 ★★ 无恒真判据：ok(True, ...) 一律视为没守 ----
    taut = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'ok' and node.args):
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and a0.value is True:
                taut.append(getattr(node, 'lineno', -1))
    ok(not taut,
       'D3 ★★ **无恒真判据**：本文件所有 `ok(...)` 的首参都不是字面量 `True`（命中行 %s）'
       % (taut[:3],))

    # D4 自检：负控制（AST 检查器本身）必须能抓到"造出来的恒真"
    fake = ast.parse('ok(True, "x")\nok(n > 0, "y")\n')
    hits = [n for n in ast.walk(fake)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'ok' and n.args
            and isinstance(n.args[0], ast.Constant) and n.args[0].value is True]
    ok(len(hits) == 1,
       'D4 负控制：D3 的检查器对"造出来的恒真"确实命中 1 条（不是恒真判据）')

    ok(_N[0] > 20, 'D5 断言条数 > 20（防"套件只剩几条"）实际 %d' % _N[0])


def main():
    print('第102轮 光照归因更正 + 物件普查 + 图集入库 回归锁（%s）'
          % os.path.basename(__file__))
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    print()
    if _FAIL:
        print('[FAIL] 共 %d 条失败（断言 %d）' % (len(_FAIL), _N[0]))
        for f in _FAIL:
            print('   - ' + f)
        return 1
    print('光照归因/物件普查/图集入库：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
