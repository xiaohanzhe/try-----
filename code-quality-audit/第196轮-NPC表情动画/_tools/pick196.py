# -*- coding: utf-8 -*-
"""第196轮 · NPC 表情动画素材构建器（默认**预演**，`--write` 才落盘）。

解决什么问题
-----------
第195轮的能力盘点把「NPC 表情配动画」记成缺口，我当时的判断是
「NPC 没有自己的动画素材，只能顶 Ralsei 的身体」——**判断错了**。
用户当场纠正：`每个角色在原作可是都有自己的动画的，为啥要用 ralsei 的啊`。

盘清之后（`_tools/probe_*.py` 四轮探针）事实是这样：
  · 原作解包目录有 34,520 张 PNG，逐角色分章节，Susie 一人 3,314 张；
  · 但**"有动画"≠"能当表情动画用"**：绝大多数是 cutscene 整图
    （`spr_susie_kris_run_right_shocked_0.png` 62×38 —— 一张图画了两个人）
    或另一种画布（`spr_gerson_laugh_0.png` 73×61，而 Gerson 走路帧 67×35）；
  · 真正能塞进小窗的，是**与走路帧同族的那一套** —— 而原作在 overworld 里
    表现情绪本来就是「换一套行走图」（`walk_down_dw_unhappy` / `walk_down_sad_dw` /
    `laugh_dw`），**不是播一段独立动画**；
  · Ralsei 自己的模板里也写着同一套（`walk_down_unhappy` / `walk_left_unhappy`）。

⇒ 本工具做的事：把每个角色**自己那段**行走变体挑出来，归一化命名后复制进仓库，
   生成清单供运行时零猜解地取帧。

为什么是**独立清单**而不是塞进 `_npc_frames.json`
------------------------------------------------
`pick191.py --write` 会**整份重写** `_npc_frames.json`。把表情帧写进去，
下次谁跑一遍 pick191 就全没了，而且不会报错。⇒ 单独一份 `_npc_anims.json`，
两个工具互不覆盖。

三道过滤（每一道都对应上面一种"看起来能用、其实会坏"）
------------------------------------------------------
① **token**：文件名命中该角色；`susiedark`/`addison_tea` 走手工映射
   （原件里它们仍写作 `susie` / `addison`，这是探针实测的，不是猜的）。
② **单人帧**：文件名里不出现**其他**已登记角色的 token
   （双人 cutscene 整图挂到一个人身上，会把另一个人一起画出来）。
③ **同尺寸族**：高度差 ≤2px、宽度 ≤2.0× 该角色正面走路帧
   （画布不同族的帧塞进小窗必跳；侧视本来就更窄，所以只设宽度上限）。

再加一条**同族取帧**：同一个情绪下按「族名」分组，只在**帧数最多的那一族**里取帧
（`spr_x_walk_down_dw_unhappy_0..3` 是一段完整动作；把
`spr_x_hurt_0` 和 `spr_x_hurt_green_0` 拼在一起只会闪）。

用法
----
    python pick196.py                 # 预演：只报告
    python pick196.py --write         # 复制 + 写清单
    python pick196.py --sheet --write # 同时出对照图（人工看图核对）
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PRODUCT = os.path.join(ROOT, 'ralsei_pet')
DEST_ROOT = os.path.join(PRODUCT, 'assets', 'sprites', 'dr')
FRAMES_MANIFEST = os.path.join(DEST_ROOT, '_npc_frames.json')
ANIM_MANIFEST = os.path.join(DEST_ROOT, '_npc_anims.json')
EVID = os.path.join(ROUND, '_evidence')

#: Deltarune 素材库根（**只在制作期用**；运行时只读仓库内的副本）
SRC_ROOT = u'C:/Users/23002/Desktop/项目文件夹/deltarune'

#: 每 (情绪, 朝向) 最多取几帧。★ 4 = 原作 overworld 一段走路循环的长度；
#: 再多只是把变体也搬进来（白占仓库，且看着像卡带）。
MAX_FRAMES = 4

#: 立绘 id → 原作文件名里的 token。★ 手工映射，探针实测：
#: `susiedark` 的立绘在 `assets/sprites/dr/susiedark/`，但原件的文件名仍写 `susie`；
#: `addison_tea` 是 `spr_npc_addison_blue`。
TOKEN = {
    'susiedark': 'susie',
    'addison_tea': 'addison',
}

#: 情绪 → 文件名正则。★ 顺序有意义：`happy` 用了 `(?<!un)`
#: —— `walk_down_unhappy` 是"不高兴"，归进 happy 就是把丧气当开心。
#: ★ `cry` 没有列：全库只有 ElNina/LaNino 小怪和 funnytext 的眼泪，
#:   主角团一个都没有（Ralsei 会哭是原作单独给他的）。
EMOTIONS = [
    ('happy', r'(?<!un)happy|laugh|smile|giggl'),
    ('sad', r'unhappy|(?<!un)sad'),
    ('angry', r'angry|_mad|mad_|annoy'),
    ('surprised', r'surpris|shock|startl'),
    ('hurt', r'hurt|pain|wince'),
]

#: 朝向。
#: ★★★ `dw/lw/rw/uw` **不是方向词** —— 它们是 Deltarune 的"暗世界/光世界"标记
#:   （`dw` = dark world、`lw` = light world）。第196轮踩过：把 `dw` 当 down 之后
#:   `spr_berdly_walk_left_dw_shocked` 被判成"正面"，四向里塞进一张侧脸。
#:   方向记号一律用 pick191 已经核过的那一套（`down/dt/d` / `left/lt/l` …）。
#: ★ 必须按**整 token** 匹配：`_d` 后面跟 `w`（如 `_dw_`）不算 down。
DIR_PAT = [
    ('down', r'(?:^|_)(?:down|dt|d)(?:_|\.|$)'),
    ('left', r'(?:^|_)(?:left|lt|l)(?:_|\.|$)'),
    ('right', r'(?:^|_)(?:right|rt|r)(?:_|\.|$)'),
    ('up', r'(?:^|_)(?:up|ut|u)(?:_|\.|$)'),
]

#: 像素级体检门限（都按**实测分布**定，不拍脑袋；实测见 `probe_alpha196.py`）。
#: ① 走路帧的 `ratio` 全在 0.45~0.73、`gap` 全为 0 ⇒ 人形像素画不会填满 bbox；
#:    贴近 0.85 就是"整块不透明底"（`spr_susie_shocked_lw_0` 那种绿方块）。
MAX_OPAQUE_RATIO = 0.85
#: ② bbox 内部**整列全透明**的最长连续段 ≥3 列 ⇒ 并排两个主体。
MAX_GAP_COLS = 2
#: ③ 实心像素数超过该角色走路帧 1.8 倍 ⇒ 夹带道具（门/盘子/抱着的箱子）。
MAX_AREA_RATIO = 1.8
#: ④ **bbox 宽度**（实心区，不是画布）上限。★ 这一条比"画布宽"有效得多：
#:    `spr_berdly_laugh_dw` 画布 38 宽但实心区只有 27（右边是空白），
#:    `spr_susie_grabsmile` 实心区直接顶到 43 —— 前者是张开翅膀，后者是**抓着东西**。
#:    实测：berdly 1.13× / king 1.36× 属于正常；susie `grabsmile` 1.65×、
#:    `hurt_0` 1.85× 属于夹带。取 1.45 把两类分开。
MAX_BBOX_W_RATIO = 1.45
MIN_BBOX_W_RATIO = 0.45
#: ⑤ bbox **高度**容差。跪/躺/摔会明显变矮：`spr_noelle_kneel_shocked` 的
#:    实心高度只有 38，而基线 46~48 —— 只看画布高度（47）是看不出来的。
BBOX_H_TOL_PX = 3
BBOX_H_TOL_RATIO = 0.12
#: ⑥ **姿势词**黑名单（按整 token 匹配）。这些不是"表情"，是"整个人的状态"
#:    （摔、跪、坐、骑…），挂到站着说话的 NPC 身上会像卡住。
#:    ★ 只收**改变站姿**的词；道具（juice/cake）交给 bbox 宽度去判，
#:      因为 `spr_toriel_juice_talk_mad` 的实心区反而比走路帧**窄**，道具根本不在图里。
POSE_BAD = (
    'fall', 'fell', 'kneel', 'sit', 'sleep', 'sleeping', 'lie', 'liedown',
    'jump', 'hop', 'racing', 'ride', 'dance', 'dead', 'splat', 'spin',
    'roll', 'slide', 'climb', 'crawl', 'wake', 'wakeup',
    # ★ `ground` 单独点名：`spr_susie_hurt_ground_0` 是"倒在地上受伤"，
    #   几何上它站着那么大，语义上是躺着 —— 只能靠词。
    'ground',
)
_POSE_BAD_RE = re.compile(r'(?:^|_)(?:%s)(?:_|$)' % '|'.join(POSE_BAD), re.I)

#: ⑦ **配色一致性**下限。同一个角色的像素画主色是稳定的；"其实画的是别人"
#:    或"掺了纯色底"都会让候选帧里属于本人调色板的像素比例骤降。
#:    实测（`probe_palette196.py` + 逐帧放大核对）：
#:      · `spr_susie_mad_face_up_0`          share 0.000（画的是 **Kris 的背面**）
#:      · `spr_susie_walk_down_shock_*`      share 0.012（深紫发 + 牛仔裤，**不是 Susie**）
#:      · `spr_susie_walk_left_candy_cane_*` share 0.008（拿着巨型拐杖糖 + **亮绿底**）
#:      · `spr_noelle_surprise_left_0`       share 0.319（金发黑裙红领结，**别的角色**）
#:      · `spr_king_laugh_ch1_1`             share 0.414（**举着大斧**的 King）
#:      · `spr_toriel_laugh_*`               0.701（真 Toriel 大笑）✔
#:      · `spr_asgore_flower_surprise_0`     0.831（真 Asgore 惊讶）✔
#:    ⇒ 0.55 正好把两类分开，且不放倒两个真帧。
PALETTE_MIN_SHARE = 0.55
PALETTE_TOPN = 24
PALETTE_BITS = 5


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def png_size(path):
    """读 PNG IHDR 的真尺寸（不信 gms 元数据 —— 见 `_cross_works.json` 的教训）。"""
    with open(path, 'rb') as f:
        head = f.read(16)
        w, h = struct.unpack('>II', f.read(8))
    assert head[:8] == b'\x89PNG\r\n\x1a\n', path
    return int(w), int(h)


#: alpha 阈值：低于此视为透明（像素画有半透明描边，不能直接用 0）
_ALPHA_MIN = 32


def pixel_stats(path):
    """alpha 通道的三个体检量。**只测量**，门限在调用方按实测定。

    :return: `{'ratio','gap','opaque','bw','bh'}` 或 `None`（空白帧）
        · `ratio`  实心像素 / bbox 面积 —— 人形像素画 0.45~0.75；贴近 1 是整块底色
        · `gap`    bbox 内部"整列全透明"的最长连续列数 —— 一个身体不会断开
        · `opaque` 实心像素总数 —— 夹带道具会让它反常变大
    """
    from PIL import Image
    im = Image.open(path)
    im.load()
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    cols = [0] * w
    rows_hit = []
    for y in range(h):
        row_hit = 0
        for x in range(w):
            if px[x, y][3] > _ALPHA_MIN:
                cols[x] += 1
                row_hit += 1
        if row_hit:
            rows_hit.append(y)
    xs = [x for x in range(w) if cols[x]]
    if not xs or not rows_hit:
        return None
    x0, x1 = xs[0], xs[-1]
    y0, y1 = rows_hit[0], rows_hit[-1]
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    opaque = sum(cols[x] for x in range(x0, x1 + 1))
    best = cur = 0
    for x in range(x0, x1 + 1):
        if cols[x] == 0:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return {'ratio': opaque / float(bw * bh), 'gap': best, 'opaque': opaque,
            'bw': bw, 'bh': bh, 'x0': x0, 'y0': y0}


def _quant(rgb):
    """每通道保留高 `8-PALETTE_BITS` 位 —— 像素画的抗锯齿边会被归并到主色。"""
    m = (1 << (8 - PALETTE_BITS)) - 1
    return (rgb[0] & ~m, rgb[1] & ~m, rgb[2] & ~m)


def colors_of(path):
    """实心像素的量化颜色列表。"""
    from PIL import Image
    im = Image.open(path)
    im.load()
    im = im.convert('RGBA')
    px = im.load()
    out = []
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a > _ALPHA_MIN:
                out.append(_quant((r, g, b)))
    return out


def palette_share(pal, cs):
    if not pal or not cs:
        return 0.0
    return sum(1 for c in cs if c in pal) / float(len(cs))


def dir_of(fn):
    s = fn.lower()
    for d, pat in DIR_PAT:
        if re.search(pat, s):
            return d
    return None


def family_of(fn):
    """`spr_x_walk_down_dw_unhappy_3.png` → `spr_x_walk_down_dw_unhappy`。"""
    stem = os.path.splitext(fn)[0]
    return re.sub(r'_\d+$', '', stem)


def index_pngs(src_root):
    out = []
    for dirpath, _dirnames, filenames in os.walk(src_root):
        rel = os.path.relpath(dirpath, src_root).replace('\\', '/')
        for f in filenames:
            if f.lower().endswith('.png'):
                out.append((rel, f, os.path.join(dirpath, f)))
    return out


def load_baseline():
    """从 `_npc_frames.json` 取每个角色的几何基线（高度族 + 宽度上限参照）。

    ★ **不另算一份**：走路帧就是运行时真正画的那一套，拿它当"同族"的尺子，
      才叫"换成同族的另一套图"，而不是拿一个我自己发明的尺寸。
    ★ 同时算 alpha 体检基线（`opaque` / `ratio` / `gap`）—— 判"这张帧是不是
      夹带了道具/底色"要有**这个角色自己的正常值**当参照，不能用全局常数。
    """
    with io.open(FRAMES_MANIFEST, 'r', encoding='utf-8') as f:
        man = json.load(f)
    chars = man.get('characters') or {}
    out = {}
    for cid, e in chars.items():
        fr = (e or {}).get('frames') or {}
        d = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        if not d or not fr.get(d):
            out[cid] = None
            continue
        w, h = png_size(os.path.join(DEST_ROOT, cid, fr[d][0]['f']))
        ss = []
        _cnt = {}
        for row in fr[d][:MAX_FRAMES]:
            p = os.path.join(DEST_ROOT, cid, row['f'])
            s = pixel_stats(p)
            if s:
                ss.append(s)
            for c in colors_of(p):
                _cnt[c] = _cnt.get(c, 0) + 1
        # 调色板：该角色走路帧里出现最多的 N 个颜色
        _top = sorted(_cnt.items(), key=lambda kv: -kv[1])[:PALETTE_TOPN]
        out[cid] = {'w': w, 'h': h, 'dir': d,
                    'kind': (e or {}).get('kind'),
                    'opaque': (int(sum(s['opaque'] for s in ss) / len(ss))
                               if ss else 0),
                    'bw': (max(s['bw'] for s in ss) if ss else w),
                    'bh': (max(s['bh'] for s in ss) if ss else h),
                    'pal': set(k for k, _v in _top)}
    return chars, out


def pick_for(cid, base, pngs, all_tokens):
    """一个角色 → `{情绪: {朝向: [候选...]}}`。"""
    tok = TOKEN.get(cid, cid).lower()
    me_re = re.compile(r'(?<![a-z])%s(?![a-z])' % re.escape(tok), re.I)
    others = [t for t in all_tokens if t != tok]
    oth_re = (re.compile(r'(?<![a-z])(?:%s)(?![a-z])'
                         % '|'.join(re.escape(t) for t in others), re.I)
              if others else None)

    # (情绪, 朝向, 族) → [(序号, 文件名, 绝对路径, w, h)]
    groups = defaultdict(list)
    for rel, fn, path in pngs:
        if not me_re.search(fn):
            continue
        emo = None
        for e, pat in EMOTIONS:
            if re.search(pat, fn, re.I):
                emo = e
                break
        if emo is None:
            continue
        if oth_re is not None and oth_re.search(fn):
            continue                                  # ② 双人帧
        try:
            w, h = png_size(path)
        except Exception:
            continue
        if abs(h - base['h']) > 2:
            continue                                  # ③ 高度族
        if w > 2.0 * base['w']:
            continue                                  # ③ 宽度上限
        # ④ 像素级体检（三类废帧都在这三道里，实测见 probe_alpha196.py）
        try:
            ps = pixel_stats(path)
        except Exception:
            continue
        if ps is None:
            continue
        if ps['ratio'] >= MAX_OPAQUE_RATIO:
            continue                                  # 整块不透明底
        if ps['gap'] > MAX_GAP_COLS:
            continue                                  # 并排两个主体
        if base['opaque'] and ps['opaque'] > MAX_AREA_RATIO * base['opaque']:
            continue                                  # 夹带道具
        if not (MIN_BBOX_W_RATIO * base['bw'] <= ps['bw']
                <= MAX_BBOX_W_RATIO * base['bw']):
            continue                                  # 实心区过宽/过窄
        if abs(ps['bh'] - base['bh']) > max(BBOX_H_TOL_PX,
                                            BBOX_H_TOL_RATIO * base['bh']):
            continue                                  # 跪/躺/摔 ⇒ 变矮
        if _POSE_BAD_RE.search(family_of(fn)):
            continue                                  # 姿势词（非表情）
        # ⑦ 配色一致性（最贵的一条，放最后）
        if base.get('pal') and palette_share(base['pal'], colors_of(path)) < \
                PALETTE_MIN_SHARE:
            continue                                  # 不是这个人 / 掺了纯色底
        dd = dir_of(fn) or 'down'
        m = re.search(r'_(\d+)$', os.path.splitext(fn)[0])
        idx = int(m.group(1)) if m else 0
        # ★ 每条帧自带自己的目录：素材库里既有"平铺族"，也有"目录族"
        #   （`spr_cutscene_27_berdly_walk_right_unhappy/` 下面就平铺 `_0.png`），
        #   拿组键里的目录回推绝对路径会在目录族上拼错（第196轮踩到）。
        groups[(emo, dd, rel, family_of(fn))].append((idx, fn, path, w, h, rel))

    # 每个 (情绪, 朝向) 只留**一族**
    best = {}
    for (emo, dd, rel, fam), items in groups.items():
        items.sort(key=lambda t: t[0])
        score = (
            min(len(items), MAX_FRAMES),        # 帧数越多越像一段动作
            1 if re.search(r'walk', fam, re.I) else 0,   # 优先行走变体
            0 if re.search(r'_old', fam, re.I) else 1,   # 老素材降级
            -len(fam),                          # 名字短的更"主干"
            -len(rel),                          # 目录浅的优先
        )
        cur = best.get((emo, dd))
        if cur is None or score > cur[0]:
            best[(emo, dd)] = (score, fam, items[:MAX_FRAMES])

    out = defaultdict(dict)
    for (emo, dd), (_s, fam, items) in best.items():
        # ★ `src` 用每条帧自己的绝对路径，**不从组键的目录回推**
        out[emo][dd] = [{'f': fn, 'src': path, 'src_name': fn,
                         'src_rel': rel, 'family': fam,
                         'w': w, 'h': h}
                        for (_i, fn, path, w, h, rel) in items]
    return {e: dict(v) for e, v in out.items()}


def build_sheet(result, base, out_path):
    """把每个角色每情绪的首帧贴成对照图（人工看图核对 —— 名字对不代表画对）。"""
    from PIL import Image, ImageDraw
    emos = [e for e, _ in EMOTIONS]
    ids = sorted(result.keys())
    cell_w, cell_h, pad, label_h = 96, 96, 6, 14
    cols = len(emos) + 1
    sheet = Image.new('RGBA',
                      (cols * (cell_w + pad) + pad,
                       len(ids) * (cell_h + pad + label_h) + pad),
                      (30, 30, 36, 255))
    draw = ImageDraw.Draw(sheet)
    for c, e in enumerate(emos):
        draw.text((pad + (c + 1) * (cell_w + pad), 4), e,
                  fill=(255, 220, 140, 255))
    for r, cid in enumerate(ids):
        y = pad + (r + 1) * (cell_h + pad + label_h) - label_h
        draw.text((pad, y), '%s %s' % (cid, (base.get(cid) or {}).get('kind', '')),
                  fill=(200, 220, 255, 255))
        for c, e in enumerate(emos):
            d = (result[cid] or {}).get(e) or {}
            dd = 'down' if 'down' in d else (sorted(d)[0] if d else None)
            x = pad + (c + 1) * (cell_w + pad)
            draw.rectangle([x, y, x + cell_w, y + label_h + cell_h],
                           outline=(70, 70, 82, 255))
            if not dd:
                continue
            it = d[dd][0]
            try:
                im = Image.open(it['src'])
                im.load()
            except Exception:
                draw.text((x + 4, y + label_h + 30), 'FAIL', fill=(255, 0, 0, 255))
                continue
            k = 2
            while k > 1 and (im.width * k > cell_w - 4 or im.height * k > cell_h - 4):
                k -= 1
            im = im.resize((max(1, im.width * k), max(1, im.height * k)),
                           Image.NEAREST)
            if im.width > cell_w - 4 or im.height > cell_h - 4:
                im.thumbnail((cell_w - 4, cell_h - 4), Image.NEAREST)
            # 贴到格子**底部中央**（脚底对齐 —— 与运行时同一条口径）
            px = x + (cell_w - im.width) // 2
            py = y + label_h + cell_h - im.height - 2
            sheet.alpha_composite(im.convert('RGBA'), (px, py))
            draw.text((x + 2, y + label_h + cell_h - 11),
                      '%d帧 %s' % (len(d[dd]), it['family'][:14]),
                      fill=(150, 200, 255, 255))
    sheet.convert('RGB').save(out_path)
    print('对照图 → %s' % out_path)
    return out_path


def main(argv):
    write = '--write' in argv
    want_sheet = '--sheet' in argv

    chars, base = load_baseline()
    all_ids = sorted(chars.keys())
    all_tokens = sorted(set(TOKEN.get(c, c).lower() for c in all_ids))

    if not os.path.isdir(SRC_ROOT):
        print('[FAIL] 素材根不存在：%s' % SRC_ROOT)
        return 2
    pngs = index_pngs(SRC_ROOT)
    print('素材根 %s' % SRC_ROOT)
    print('原作 PNG %d 张；登记角色 %d 人' % (len(pngs), len(all_ids)))
    print('')

    result = {}
    for cid in all_ids:
        b = base.get(cid)
        if not b:
            print('  [--] %-12s 无几何基线（立绘缺失）⇒ 跳过' % cid)
            result[cid] = {}
            continue
        got = pick_for(cid, b, pngs, all_tokens)
        result[cid] = got
        if not got:
            print('  [空] %-12s 基线 %dx%d  原作无同族情绪帧 ⇒ 如实不演'
                  % (cid, b['w'], b['h']))
            continue
        desc = []
        for e, _ in EMOTIONS:
            d = got.get(e) or {}
            if not d:
                continue
            desc.append('%s:%s' % (e, '/'.join('%s%d' % (k, len(v))
                                               for k, v in sorted(d.items()))))
        print('  [OK] %-12s 基线 %dx%d  %s' % (cid, b['w'], b['h'], '  '.join(desc)))

    # ---- 清单 ----
    out_chars = {}
    n_frames = 0
    for cid in all_ids:
        got = result.get(cid) or {}
        if not got:
            continue
        entry = {}
        for e, _ in EMOTIONS:
            d = got.get(e) or {}
            if not d:
                continue
            entry[e] = {}
            for dd, items in sorted(d.items()):
                rows = []
                for i, it in enumerate(items):
                    rows.append({'f': 'anim/%s_%s_%d.png' % (e, dd, i),
                                 'src_name': it['src_name'],
                                 'w': it['w'], 'h': it['h'],
                                 'sha256': sha256_file(it['src'])})
                entry[e][dd] = rows
                n_frames += len(rows)
        out_chars[cid] = entry

    manifest = {
        'schema_version': 1,
        'round': 196,
        'why': ('NPC 表情动画的取帧清单。运行时**只读本文件**，不做任何文件名猜解。'
                '★ 与 `_npc_frames.json` 分开是刻意的：`pick191.py --write` 会整份'
                '重写那个文件，表情帧写进去下次就被冲掉且不报错。'),
        'how': ('由 `code-quality-audit/第196轮-NPC表情动画/_tools/pick196.py` 生成。'
                '取帧口径见该文件头部注释（token / 单人帧 / 同尺寸族 / 同族取帧）。'),
        'src_root': SRC_ROOT,
        'frame_ms': 120,
        'max_frames': MAX_FRAMES,
        'emotions': [e for e, _ in EMOTIONS],
        'note_no_cry': ('`cry` 不在列表里：全库 cry 帧只有 ElNina/LaNino 小怪与 '
                        'funnytext 的眼泪，主角团一个都没有（Ralsei 的 cry 是原作单独给他的）。'
                        'NPC 遇 cry 由调用方退到 `sad`。'),
        'characters': out_chars,
    }

    print('')
    print('可用角色 %d / %d，共 %d 帧' % (len(out_chars), len(all_ids), n_frames))
    miss = [c for c in all_ids if c not in out_chars]
    print('不演（原作无同族情绪帧）：%s' % (', '.join(miss) or '无'))
    for e, _ in EMOTIONS:
        cs = [c for c in out_chars if e in out_chars[c]]
        print('  %-10s 角色 %-2d  %s' % (e, len(cs), ', '.join(cs)))

    if want_sheet:
        if not os.path.isdir(EVID):
            os.makedirs(EVID)
        build_sheet(result, base, os.path.join(EVID, 'sheet196.png'))

    if not write:
        print('')
        print('（预演，未写盘。加 --write 才复制与写清单）')
        return 0

    # ---- 真复制（幂等）----
    for cid, entry in out_chars.items():
        dst = os.path.join(DEST_ROOT, cid, 'anim')
        if os.path.isdir(dst):
            for f in os.listdir(dst):
                if f.lower().endswith('.png'):
                    os.remove(os.path.join(dst, f))
        else:
            os.makedirs(dst)
        for e, dirs in entry.items():
            for dd, rows in dirs.items():
                for i, row in enumerate(rows):
                    src_it = result[cid][e][dd][i]
                    shutil.copy2(src_it['src'], os.path.join(dst, row['f'][5:]))
    # 清掉不再需要的角色目录（幂等：第二次跑结果一致）
    for name in os.listdir(DEST_ROOT):
        p = os.path.join(DEST_ROOT, name, 'anim')
        if os.path.isdir(p) and name not in out_chars:
            for f in os.listdir(p):
                if f.lower().endswith('.png'):
                    os.remove(os.path.join(p, f))
            try:
                os.rmdir(p)
            except OSError:
                pass
    with io.open(ANIM_MANIFEST, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write(u'\n')
    print('')
    print('已写盘：%d 个角色 / %d 张 PNG → %s' % (len(out_chars), n_frames, DEST_ROOT))
    print('清单：%s' % ANIM_MANIFEST)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
