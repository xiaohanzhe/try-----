# -*- coding: utf-8 -*-
"""第191轮 · NPC 本体素材挑选器（默认为**预演**，`--write` 才落盘）。

它解决一件事：把「Deltarune 素材库里哪个族是这个角色的本体帧」这件事，从
**运行时猜文件名**变成**一张人工核对的显式映射表**。

为什么必须显式（第191轮实测教训）
--------------------------------
素材库里同一角色的族有几十个（`spr_gerson_*` 148 个族），自动按 token 匹配会
把 `spr_dw_castle_queen_room_traffic_light` 当成 queen 的立绘、把
`spr_pebble`（地上的石头）当成「puzzlemaster」。**猜错不会报错，只会画错人。**
⇒ 本表逐条手写，工具只负责：① 存在性校验；② 复制并**归一化命名**；
③ 生成清单（含尺寸/sha256），供运行时零猜解地取帧。

归一化命名的意义：原库有 `spr_x_walk_down_dw_3.png`、`spr_x_dt_0.png`、
`dalv_down_0.png` 三种写法，落仓后一律叫 `<dir>_<i>.png` ⇒ 渲染层不做格式判断。

用法
----
    python pick191.py            # 预演：只报告，不写盘
    python pick191.py --write    # 真复制 + 写清单
    python pick191.py --probe    # 只列候选（不复制），用于补表
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PRODUCT = os.path.join(ROOT, 'ralsei_pet')
DEST_ROOT = os.path.join(PRODUCT, 'assets', 'sprites', 'dr')
MANIFEST = os.path.join(DEST_ROOT, '_npc_frames.json')
PLACEMENT = os.path.join(PRODUCT, 'assets', 'npc', '_placement.json')

#: Deltarune 素材库根（**只在制作期用**；运行时只读仓库内的副本）
SRC_ROOT = u'C:/Users/23002/Desktop/项目文件夹/deltarune'

#: 每个方向最多取几帧。★ 为什么是 4：原作 overworld 走路就是 4 帧一轮
#: （`spr_*_walk_*` 的帧数普遍是 4 的整数倍，16 帧是"4 姿势 × 4 变体"）。
#: 取前 4 帧一定覆盖完整步态；取全部只是把变体也搬进来，白占仓库。
MAX_FRAMES_PER_DIR = 4

#: 方向写法。★ `dt/lt/rt/ut` 是 Deltarune ch3+ 的写法（lancer 就这一套）。
DIR_ALIASES = {
    'down': ('down', '_d', 'Down', 'dt', '_dt'),
    'left': ('left', '_l', 'Left', 'lt', '_lt'),
    'right': ('right', '_r', 'Right', 'rt', '_rt'),
    'up': ('up', '_u', 'Up', 'ut', '_ut'),
}

#: ------------------------------------------------------------------
#: 映射表：npc_id → 规格
#:   kind  : 'walk'（四方向多帧）/ 'stand'（每方向 1 帧）
#:   sets  : [(世界, 素材子目录, 族名模板)]  世界 ∈ dark/light/any
#:           族名模板里的 `{}` 由方向记号填入；**不留 `{}` 的表示该族不分方向**
#: ------------------------------------------------------------------
MAP = {
    # ---- 有四方向走路族（与 `_placement.json` 的 mode 无关，走路帧也能当站立）----
    'susie': dict(kind='walk', sets=[
        ('dark', 'susie/dark', 'spr_susie_walk_{}_dw'),
        ('light', 'susie/light', 'spr_susie_walk_{}_lw')]),
    'noelle': dict(kind='walk', sets=[
        ('dark', 'noelle/dark', 'spr_noelle_walk_{}_dw'),
        ('light', 'noelle/light', 'spr_noelle_walk_{}_lw')]),
    'berdly': dict(kind='walk', sets=[
        ('dark', 'berdly/dark', 'spr_berdly_walk_{}_dw'),
        ('light', 'berdly/light', 'spr_berdly_walk_{}_lw')]),
    'kris': dict(kind='walk', sets=[
        ('any', 'kris', 'spr_kris_walk_{}_church')]),
    'toriel': dict(kind='walk', sets=[
        ('any', 'lighter/torielch34', 'spr_toriel_walk_{}_church')]),
    'asgore': dict(kind='walk', sets=[
        ('any', 'lighter/asgore34', 'spr_asgore_walk_{}_housekeeper')]),
    'queen': dict(kind='walk', sets=[
        ('any', 'boss/queen', 'spr_queen_walk_{}')]),
    'rudy': dict(kind='walk', sets=[
        ('any', 'lighter/rudy', 'spr_rudy_walk_{}')]),
    # ---- 只有站立/单向帧 ----
    # `dt/lt/rt/ut` 是 Deltarune ch3+ 的方向写法（本表 DIR_ALIASES 已覆盖）
    'lancer': dict(kind='stand', sets=[
        ('any', 'boss/lancer34', 'spr_lancer_{}')]),
    'king': dict(kind='stand', sets=[
        ('any', 'boss/king', 'spr_king_left')]),
    'rouxls': dict(kind='stand', sets=[
        ('any', 'boss/rouxls34', 'spr_rouxls_handstogether')]),
    'tenna': dict(kind='stand', sets=[
        ('any', 'boss/tenna', 'spr_board_npc_tenna')]),
    # ⚠️ 原写 `spr_mike_med`（对照图里是只黑白猫）⇒ 改 `spr_mike_l`（44x86 直立像）
    'mike': dict(kind='stand', sets=[
        ('any', 'boss/mike', 'spr_mike_l')]),
    # ⚠️ 原来写的是 `spr_npc_addison_stand` —— 对照图显示那是**店招框**，不是人。
    'addison_tea': dict(kind='stand', sets=[
        ('any', 'npc', 'spr_npc_addison_blue')]),
    'rabbits': dict(kind='stand', sets=[
        ('any', 'npc', 'spr_npc_rabbitkid')]),
    'hammerguy': dict(kind='stand', sets=[
        ('any', 'npc', 'spr_hammerguy')]),
    # ⚠️ 原写 `spr_gerson_battle_overworld`（对照图里像个蘑菇杂物）⇒ 改 `spr_gerson_idle`
    'gerson': dict(kind='stand', sets=[
        ('any', 'boss/gerson', 'spr_gerson_idle')]),
    'susiedark': dict(kind='stand', sets=[
        ('dark', 'susie/dark', 'spr_susie_walk_down_dw')]),
    # ---- 下面这些人本轮**没有找到本体帧**（如实登记，不猜、不编）----
    # `spamton`：只有 cutscene/battle 素材，没有 overworld 本体帧
    # `catti`：只有头像（`face/ch4/spr_face_catti_*`）与家人素材，没有她本人
    # `doubter` / `flowery` / `police`：素材库里搜不到（可能原作就以物件形态出现）
    # `puzzlemaster1/2`：原作是墙上机关，不是可站立的角色
    # 招牌/垃圾桶/店面/房间锚点见 `NOT_A_PERSON`
}

#: 明确"这个 id 不是人"（招牌/垃圾桶/店面/房间锚点）—— 本轮不画本体，
#: 也不动 `_placement.json`（用户裁定：先留着并登记）。
NOT_A_PERSON = (
    'sign', 'dumpster', 'wrapper', 'zapper', 'mansion_room', 'npc_room',
    'castle_cafe', 'conbini',
)


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


def index_bank(src_root):
    """`{族名: [帧绝对路径...]}` —— 目录族与平铺族都收。

    ★ 只收**同一目录内**的族：不同目录同名族（ch3 与 ch4 都有）不能混，
      否则帧序列会串章（同一角色的两个章节版本外观不同）。
      实现：族键 = `(相对目录, 族名)`。
    """
    bank = {}
    for dirpath, dirnames, filenames in os.walk(src_root):
        pngs = [f for f in filenames if f.lower().endswith('.png')]
        if not pngs:
            continue
        rel = os.path.relpath(dirpath, src_root).replace('\\', '/')
        base = os.path.basename(dirpath)
        # ① 目录族：目录名 = 族名，里面平铺 `_0.._n`
        frames = []
        for f in pngs:
            m = re.match(r'^(.*?)[_ ]?(\d+)\.png$', f, re.I)
            if m and m.group(1) == base:
                frames.append((int(m.group(2)), os.path.join(dirpath, f)))
        if frames:
            bank[(rel, base)] = [p for _, p in sorted(frames)]
        # ② 平铺族：文件 `族名_序号.png` 直接躺在 `rel` 里
        flat = {}
        for f in pngs:
            m = re.match(r'^(.*?)_(\d+)\.png$', f, re.I)
            if m:
                flat.setdefault(m.group(1), []).append(
                    (int(m.group(2)), os.path.join(dirpath, f)))
        for name, items in flat.items():
            if (rel, name) not in bank:
                bank[(rel, name)] = [p for _, p in sorted(items)]
    return bank


def find_family(bank, rel_dir, name):
    """在**指定子树**里找族；返回帧列表或 `None`。

    `rel_dir` 可以是 `susie/dark` 这种精确目录，也可以是 `ch4` / `npc` 这种
    需要下钻的父目录（素材库里 ch4 是平铺的，npc 下面还分 ch1..ch4）。
    """
    rel_dir = rel_dir.replace('\\', '/').strip('/')
    hits = []
    for (rel, fam), frames in bank.items():
        if fam != name:
            continue
        if rel == rel_dir or rel.startswith(rel_dir + '/'):
            hits.append((len(rel), frames))
    if not hits:
        return None
    # 取路径最浅的那个（同章多版本时优先顶层）
    hits.sort(key=lambda t: t[0])
    return hits[0][1]


def resolve(bank, spec):
    """把一个 id 的规格解析成 `{方向: [帧路径...]}`。失败 → `{}`。"""
    out = {}
    for world, rel, tmpl in spec['sets']:
        if '{}' in tmpl:
            for d, toks in DIR_ALIASES.items():
                if d in out:
                    continue
                for tok in toks:
                    name = tmpl.format(tok)
                    fr = find_family(bank, rel, name)
                    if fr:
                        out[d] = fr
                        break
        else:
            fr = find_family(bank, rel, tmpl)
            if fr:
                # 不分方向的族：全部记在 down（正面朝向最常用）
                out.setdefault('down', fr)
    return out


def build_sheet(detail, out_path):
    """把每个角色的**首帧**贴成一张对照图（人工核对用）。

    ★ 为什么必须有这一步：映射表是**手写**的，写错不会报错，只会画错人。
      自动挑族试过一次（`spr_dw_castle_queen_room_traffic_light` 被当成 queen），
      所以最终把关是"看图"，不是"看名字"。
    """
    from PIL import Image, ImageDraw
    cell_w, cell_h, pad, label_h = 120, 120, 8, 16
    cols = 6
    n = len(detail)
    rows = (n + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * (cell_w + pad) + pad,
                               rows * (cell_h + pad + label_h) + pad),
                      (32, 32, 38, 255))
    draw = ImageDraw.Draw(sheet)
    for i, nid in enumerate(sorted(detail)):
        spec, got = detail[nid]
        d = 'down' if 'down' in got else sorted(got)[0]
        path = got[d][0]
        x = pad + (i % cols) * (cell_w + pad)
        y = pad + (i // cols) * (cell_h + pad + label_h)
        draw.text((x, y), '%s' % nid, fill=(230, 230, 235, 255))
        draw.rectangle([x, y + label_h, x + cell_w, y + label_h + cell_h],
                       outline=(90, 90, 100, 255))
        try:
            im = Image.open(path)
            im.load()
        except Exception as e:
            draw.text((x + 4, y + label_h + 40), 'LOAD FAIL', fill=(255, 0, 0, 255))
            print('   !! 读不出 %s (%s): %s' % (nid, path, e))
            continue
        # 2 倍最近邻（像素风不糊），超出格子再按比例缩
        k = 2
        while k > 1 and (im.width * k > cell_w - 4 or im.height * k > cell_h - 4):
            k -= 1
        im = im.resize((max(1, im.width * k), max(1, im.height * k)),
                       Image.NEAREST)
        if im.width > cell_w - 4 or im.height > cell_h - 4:
            im.thumbnail((cell_w - 4, cell_h - 4), Image.NEAREST)
        # 贴到格子底部中央（脚底对齐 —— 与运行时同一条口径）
        px = x + (cell_w - im.width) // 2
        py = y + label_h + cell_h - im.height - 2
        sheet.alpha_composite(im.convert('RGBA'), (px, py))
        draw.text((x + 2, y + label_h + cell_h - 12),
                  '%dx%d' % (im.width, im.height), fill=(150, 200, 255, 255))
    sheet.convert('RGB').save(out_path)
    print('对照图 → %s' % out_path)
    return out_path


def main(argv):
    write = '--write' in argv
    probe = '--probe' in argv
    bank = index_bank(SRC_ROOT)
    print('素材族索引：%d 个（根 = %s）' % (len(bank), SRC_ROOT))
    print('')

    book = json.load(io.open(PLACEMENT, encoding='utf-8'))
    station = collections_ids = [p['id'] for p in book['placement'] if p.get('scene')]
    station = sorted(set(collections_ids))
    print('站位 id：%d 个（映射表覆盖 %d）' % (len(station), len(MAP)))

    ok, no_art = [], []
    detail = {}
    for nid in station:
        spec = MAP.get(nid)
        if spec is None:
            no_art.append(nid)
            continue
        got = resolve(bank, spec)
        if not got:
            no_art.append(nid)
            print('  [空] %-16s 表里指定了族但**一个都没找到** ⇒ 表过时了' % nid)
            continue
        detail[nid] = (spec, got)
        ok.append(nid)
        dirs = {d: min(len(v), MAX_FRAMES_PER_DIR) for d, v in sorted(got.items())}
        print('  [OK] %-16s %-6s %s' % (nid, spec['kind'], dirs))

    print('')
    print('配到素材：%d ／ 未配到：%d' % (len(ok), len(no_art)))
    print('未配到：%s' % ', '.join(no_art))

    # ---- 清单 ----
    chars = {}
    for nid in ok:
        spec, got = detail[nid]
        entry = {'kind': spec['kind'], 'frames': {}}
        for d, files in sorted(got.items()):
            take = files[:MAX_FRAMES_PER_DIR]
            rows = []
            for i, p in enumerate(take):
                w, h = png_size(p)
                rows.append({'f': '%s_%d.png' % (d, i), 'src': p,
                             'w': w, 'h': h, 'sha256': sha256_file(p)})
            if len(files) > len(take):
                # 缺口**写进清单**，不要在工具里静默截断
                entry.setdefault('truncated', {})[d] = [len(take), len(files)]
            entry['frames'][d] = rows
        chars[nid] = entry

    manifest = {
        'schema_version': 1,
        'round': 191,
        'why': ('NPC 本体的取帧清单。运行时**只读本文件**，不做任何文件名猜解'
                '（素材库有三种命名写法，猜解会画错人）。'),
        'how': ('由 `code-quality-audit/第191轮-NPC本体/_tools/pick191.py` 生成；'
                '映射表逐条手写，工具只做存在性校验与复制。'),
        'src_root': SRC_ROOT,
        'max_frames_per_dir': MAX_FRAMES_PER_DIR,
        'not_a_person': list(NOT_A_PERSON),
        'no_art': no_art,
        'characters': chars,
    }

    if not write:
        print('')
        print('（预演，未写盘。加 --write 才复制与写清单）')
        print('将落盘：%d 个角色 → %s' % (len(chars), DEST_ROOT))
        if '--sheet' in argv:
            build_sheet(detail,
                        os.path.join(HERE, '..', '_evidence', 'sheet191.png'))
        return 0

    # ---- 真复制（幂等：先清目标目录里的旧帧，再拷）----
    if not os.path.isdir(DEST_ROOT):
        os.makedirs(DEST_ROOT)
    for nid, entry in chars.items():
        dst = os.path.join(DEST_ROOT, nid)
        if os.path.isdir(dst):
            for f in os.listdir(dst):
                if f.lower().endswith('.png'):
                    os.remove(os.path.join(dst, f))
        else:
            os.makedirs(dst)
        for d, rows in entry['frames'].items():
            for row in rows:
                shutil.copy2(row['src'], os.path.join(dst, row['f']))
                del row['src']      # 清单里不写外部绝对路径（运行时不该依赖它）
    with io.open(MANIFEST, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write(u'\n')
    n_png = sum(len(r) for c in chars.values() for r in c['frames'].values())
    print('')
    print('已写盘：%d 个角色 / %d 张 PNG → %s' % (len(chars), n_png, DEST_ROOT))
    print('清单：%s' % MANIFEST)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
