# -*- coding: utf-8 -*-
"""第200轮 · 外来角色本体帧挑选器（默认**预演**，`--write` 才落盘）

与 `pick191.py` 同一套约定，区别只在**素材来源**：191 从原始 Deltarune 素材库挑，
本工具从仓库内已抽好的 `assets/sprites/{ut,hy,ot,os}` 挑。

为什么仍然逐条手写映射（第191轮教训）
------------------------------------
自动按 token 匹配会把 `spr_dw_castle_queen_room_traffic_light` 当成 queen。
本轮实测同类坑三处，全是"名字像但不是一个东西"：
  * `ut_gaster` 只有 `spr_gasterblaster_*`（**弹幕骷髅头**，不是 Gaster）；
  * `ut_mettaton` 只有 `spr_mettatonb_0`（**盒子形态**，画出来是个黑箱子）；
  * `hy_bowll` 只有 `spr_bowll_body_normal_0`（**一个没有眼睛的碗**）。
这三条如实进 `no_art`，不画。

另有两条**看着有、其实不能用**：
  * `ut_chara` 的候选里混着 `spr_f_mainchar*`——放大看是**黄发、紫条纹衫**的
    女性主角，与 Chara（褐发、黄绿条纹衫）不是同一套；只取 `spr_chara*`。
    ⇒ `ut_frisk` 因此进 `no_art`（仓库里**只有女性版**，无中性版，选了就是替角色定性别）。
  * `os_shepherd` 的 `contacts_shepherd.png` 是一张**混合表**：第 0 行是牧羊人，
    第 1~3 行是**羊**。只取第 0 行。

OneShot（`os_*`）是**格子表**，不是单张立绘
------------------------------------------
`os_ling/contacts_ling.png` 恰好是 30x50——正是 120x200 表的**一格**，这是
"格 = 画布/4"的实证。本轮按 4x4 切，行序 `down/left/right/up` 由三条独立证据定：
狐形角色 `os_rue` 第 1 行尾巴在右（⇒朝左）、第 2 行尾巴在左（⇒朝右），
人类角色 `os_niko`/`os_kip` 第 1 行鼻尖朝左、第 2 行朝右。三条一致。

用法
----
    python pick200.py            # 预演：只报告
    python pick200.py --write    # 真切/复制 + 写清单
"""
from __future__ import print_function

import collections
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PRODUCT = os.path.join(ROOT, 'ralsei_pet')
SPR = os.path.join(PRODUCT, 'assets', 'sprites')
DEST_ROOT = os.path.join(SPR, 'dr')
MANIFEST = os.path.join(DEST_ROOT, '_npc_frames.json')
EVI = os.path.join(ROUND, '_evidence')

MAX_FRAMES_PER_DIR = 4

#: 方向记号 → 归一化方向名（落仓后一律 `<dir>_<i>.png`）
D1 = {'d': 'down', 'l': 'left', 'r': 'right', 'u': 'up'}
D_W = {'down': 'down', 'left': 'left', 'right': 'right', 'up': 'up'}
DIR_CAP = {'Down': 'down', 'Left': 'left', 'Right': 'right', 'Up': 'up'}
#: OneShot 4x4 表的行序（由狐尾朝向 + 两人鼻尖朝向三条证据定，见模块说明）
R4 = {'down': 0, 'left': 1, 'right': 2, 'up': 3}

#: ------------------------------------------------------------------
#: 映射表。每条都对应一张我看过的拼版/切格页（`_evidence/sheets*`）。
#:   work  : `assets/sprites/` 下的子目录
#:   kind  : 'walk'（多方向多帧）/ 'stand'（单方向或单帧）
#:   pat   : 文件名模板，`{k}` = 方向记号、`{i}` = 帧序号
#:   dirs  : 方向记号表；`None` 表示该族不分方向（全部记在 down）
#:   grid  : OneShot 格子表 —— `(文件, 格宽, 格高, {方向: 行号}, 每行取几帧)`
#: ------------------------------------------------------------------
MAP = {
    # ---------------- UT（Undertale）----------------
    'ut_alphys': dict(work='ut', kind='walk', pat='spr_alphys_{k}_{i}', dirs=D1),
    'ut_asgore': dict(work='ut', kind='walk', pat='spr_asgore_{k}_{i}', dirs=D1),
    # ★ 只用 `spr_chara*`：候选里的 `spr_f_mainchar*` 是黄发紫条纹衫的**女性主角**
    'ut_chara': dict(work='ut', kind='walk', pat='spr_chara{k}_{i}', dirs=D1),
    # ★ UT 的 flowey 族叫 `spr_floweyfly_*`（fly = 他没腿、飘着），不是 `spr_flowey_*`
    'ut_flowey': dict(work='ut', kind='stand', pat='spr_floweyfly_{i}', dirs=None),
    'ut_muffet': dict(work='ut', kind='stand', pat='spr_muffet_overworld_{i}',
                      dirs=None),
    'ut_napstablook': dict(work='ut', kind='stand',
                           pat='spr_napstablook_{k}_{i}', dirs=D1),
    'ut_papyrus': dict(work='ut', kind='walk', pat='spr_papyrus_{k}_{i}', dirs=D1),
    'ut_sans': dict(work='ut', kind='walk', pat='spr_sans_{k}_{i}', dirs=D1),
    'ut_toriel': dict(work='ut', kind='walk', pat='spr_toriel_{k}_{i}', dirs=D1),
    'ut_undyne': dict(work='ut', kind='walk', pat='spr_undyne_{k}_{i}', dirs=D1),

    # ---------------- OT（OverTale）----------------
    'ot_alphys': dict(work='ot', kind='walk',
                      pat='iocAlphys{K}_{i}', dirs=DIR_CAP),
    'ot_asgore': dict(work='ot', kind='walk', pat='iocAsgore{K}_{i}', dirs=DIR_CAP),
    'ot_asriel_twinkly': dict(work='ot', kind='walk',
                              pat='iocAsriel{K}_{i}', dirs=DIR_CAP),
    'ot_kidd': dict(work='ot', kind='walk', pat='iocKidd{K}_{i}', dirs=DIR_CAP),
    # ★ `_11` 是**品红色变体**（品红像素 127/1642 = 8%，其余 12 帧为 0），跳过
    'ot_mettaton': dict(work='ot', kind='stand',
                        pat='iocMettatonDressIdle_{i}', dirs=None,
                        skip_idx=(11,)),
    'ot_muffet': dict(work='ot', kind='stand', pat='ionFMuffet_{i}', dirs=None),
    'ot_napstablook': dict(work='ot', kind='stand',
                           pat='iocNapstablookBody_{i}', dirs=None),
    'ot_papyrus': dict(work='ot', kind='walk', pat='iocPapyrus{K}_{i}', dirs=DIR_CAP),
    'ot_sans': dict(work='ot', kind='walk', pat='iocSans{K}_{i}', dirs=DIR_CAP),
    'ot_toriel': dict(work='ot', kind='walk', pat='iocToriel{K}_{i}', dirs=DIR_CAP),
    'ot_undyne': dict(work='ot', kind='walk', pat='iocUndyne{K}_{i}', dirs=DIR_CAP),

    # ---------------- HY（Undertale Yellow）----------------
    'hy_ace': dict(work='hy', kind='walk', pat='spr_ace_{k}_walk_{i}', dirs=D_W),
    # ★ axis 的四个方向**都不带 `_walk`**（`spr_axis_left_0.png`），与同目录其它人相反。
    #   我第一版照拼版上 8px 小字抄成 `spr_axis_left_walk_0` —— **拼版上的文件名
    #   当不了凭据，只有 `os.listdir` 算**（这条已记进报告）。
    'hy_axis': dict(work='hy', kind='walk', pat='spr_axis_{k}_{i}', dirs=D_W),
    'hy_ceroba_ketsukane': dict(work='hy', kind='walk',
                                pat='spr_ceroba_{k}_walk_{i}', dirs=D_W),
    'hy_chujin_ketsukane': dict(work='hy', kind='stand',
                                pat='spr_chujin_npc_{i}', dirs=None),
    'hy_clover': dict(work='hy', kind='stand', pat='spr_clover_casual_0', dirs=None),
    # ★ dalv 的五官族**没有 `spr_` 前缀、也没有 `_walk`**（`dalv_down_0.png`）
    'hy_dalv': dict(work='hy', kind='walk', pat='dalv_{k}_{i}', dirs=D_W),
    'hy_ed': dict(work='hy', kind='walk', pat='spr_ed_{k}_walk_{i}', dirs=D_W),
    'hy_flowey': dict(work='hy', kind='stand', pat='spr_flowey_{i}', dirs=None),
    'hy_guardener': dict(work='hy', kind='stand', pat='spr_guardener_body_0',
                         dirs=None),
    'hy_martlet': dict(work='hy', kind='stand', pat='spr_martlet_{k}_talk_{i}',
                       dirs=D_W),
    'hy_mooch': dict(work='hy', kind='walk', pat='spr_mooch_{k}_walk_{i}', dirs=D_W),
    'hy_moray': dict(work='hy', kind='walk', pat='spr_moray_{k}_walk_{i}', dirs=D_W),
    'hy_sousborg': dict(work='hy', kind='stand', pat='spr_sousborg_npc_{i}',
                        dirs=None),
    'hy_starlo': dict(work='hy', kind='walk', pat='spr_starlo_{k}_walk_{i}',
                      dirs=D_W),

    # ---------------- OS（OneShot，4x4 格子表）----------------
    # `(文件, 格宽, 格高, 行号表, 每行帧数)`；行号表缺某个方向 = 该方向不登记
    'os_alula': dict(work='os', kind='walk', grid=(
        'green_npc_alula.png', 24, 32, R4, 4)),
    'os_calamus': dict(work='os', kind='walk', grid=(
        'green_npc_calamus.png', 24, 32, R4, 4)),
    'os_cedric': dict(work='os', kind='walk', grid=(
        'green_npc_cedric.png', 24, 32, R4, 4)),
    'os_george': dict(work='os', kind='walk', grid=(
        'red_npc_george1.png', 24, 32, R4, 4)),
    # ★ kelvin 的 112x80 格里只有第 0 行有内容
    'os_kelvin': dict(work='os', kind='stand', grid=(
        'contacts_kelvin.png', 112, 80, {'down': 0}, 4)),
    'os_kip': dict(work='os', kind='walk', grid=('red_kip.png', 30, 50, R4, 4)),
    'os_lamplighter': dict(work='os', kind='walk', grid=(
        'red_lamplighter.png', 30, 50, R4, 4)),
    'os_ling': dict(work='os', kind='stand', grid=(
        'contacts_ling.png', 30, 50, {'down': 0}, 1)),
    # ★ magpie 只有第 0 列有内容 ⇒ 每方向 1 帧
    'os_magpie': dict(work='os', kind='stand', grid=(
        'green_npc_magpie.png', 24, 32, R4, 1)),
    'os_maize': dict(work='os', kind='stand', grid=(
        'contacts_maize.png', 24, 32, {'down': 0}, 1)),
    'os_mason': dict(work='os', kind='stand', grid=(
        'contacts_mason.png', 30, 50, R4, 1)),
    'os_niko': dict(work='os', kind='walk', grid=('niko.png', 24, 32, R4, 4)),
    'os_prototype': dict(work='os', kind='walk', grid=(
        'blue_npc_prototype.png', 24, 32, R4, 4)),
    # ★ 原始库里有 `blue_npc_prophet.png`，与 `prophetbot` 是同一张（自动匹配
    #   因 `prophetbot` 不含于 `prophet` 而漏掉 —— 本轮补上）
    'os_prophetbot': dict(work='os', kind='walk', grid=(
        'blue_npc_prophet.png', 24, 32, R4, 4)),
    'os_rowbot': dict(work='os', kind='stand', grid=(
        'contacts_rowbot.png', 48, 48, {'down': 0}, 1)),
    'os_rue': dict(work='os', kind='walk', grid=('red_rue.png', 24, 32, R4, 4)),
    # ★ 混合表：第 0 行是牧羊人，第 1~3 行是**羊** ⇒ 只取第 0 行
    'os_shepherd': dict(work='os', kind='stand', grid=(
        'contacts_shepherd.png', 24, 32, {'down': 0}, 4)),
    'os_silver': dict(work='os', kind='walk', grid=(
        'blue_npc_silver.png', 30, 50, R4, 4)),
    'os_watcher': dict(work='os', kind='stand', grid=(
        'contacts_watcher.png', 30, 50, {'down': 0}, 4)),
}

#: 如实登记"没有可用本体帧"的人 —— **不猜、不编、不拿别的东西顶上**
NO_ART = {
    'ut_gaster': '素材库里只有 `spr_gasterblaster_*`（弹幕骷髅头），没有 Gaster 本体',
    'ut_mettaton': '只有 `spr_mettatonb_0` 盒子形态（黑箱子 + 三个小脸），不是立绘',
    'ut_frisk': '仓库只有 `spr_f_mainchar*`（女性版主角），无中性版；用哪个是替角色定性别',
    'ut_monster_kid': '仓库没有 UT 的怪物小孩；`deltarune/ch4/spr_mkid_*` 是 DT 版，不是同一作品',
    'hy_bowll': '只有 `spr_bowll_body_normal_0`（一个没有眼睛的碗身），画出来是个碗',
    'knight': '原始库有 `spr_roaringknight_*`（咆哮骑士），是否即此 `knight` 需人眼确认，本轮不收',
    'os_the_world_machine': '素材库里搜不到（可能原作就以场景/文字形态出现）',
    'os_the_author': '素材库里搜不到',
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def png_size(path):
    """读 PNG IHDR 真尺寸（不信任何外部元数据）。"""
    with open(path, 'rb') as f:
        head = f.read(24)
    assert head[:8] == b'\x89PNG\r\n\x1a\n', path
    w, h = struct.unpack('>II', head[16:24])
    return int(w), int(h)


def _rx(pat, key=None):
    """把模板编成正则：`{k}`→方向记号，`{i}`→`(\\d+)`。

    ★ 先整体 `re.escape` 再替换占位符 —— 两边用同一套转义，`{` `}` 在 3.7+ 会
      被转义，替换时用 `re.escape('{k}')` 去对，才不会漏。
    """
    s = re.escape(pat)
    if key is not None:
        # `{k}` = 小写记号（d/l/r/u、down…），`{K}` = 首字母大写（Down/Left…）
        for ph in ('{k}', '{K}'):
            s = s.replace(re.escape(ph), re.escape(key))
    return s.replace(re.escape('{i}'), r'(\d+)')


def resolve(spec):
    """解析一个 id → `{方向: [(序号, 源路径, 落仓名, 切格参数|None)]}`。

    `grid` 走切格（落盘时才产出 PNG），其余按文件名模板找。
    """
    work = os.path.join(SPR, spec['work'])
    raw = collections.OrderedDict()          # dir -> [(idx, path)]

    if 'grid' in spec:
        fn, cw, ch, rows, per = spec['grid']
        p = os.path.join(work, fn)
        if not os.path.isfile(p):
            return {}
        out = collections.OrderedDict()
        for d, r in sorted(rows.items()):
            out[d] = [(i, p, '%s_%d.png' % (d, i), (i, r, cw, ch))
                      for i in range(per)]
        return out

    # ★ 拿**去掉扩展名**的名字去对模板（模板里不写 `.png`；第一版漏了这一步，
    #   ut/ot/hy 全军覆没，只有走 `grid` 的 os 侥幸通过）
    names = sorted((f[:-4], os.path.join(work, f))
                   for f in os.listdir(work) if f.lower().endswith('.png'))

    dirs = spec.get('dirs')
    skip = set(spec.get('skip_idx') or ())

    def _take(d, rx):
        for stem, full in names:
            m = re.match('^' + rx + '$', stem)
            if not m:
                continue
            idx = int(m.group(1)) if m.groups() else 0
            if idx in skip:
                continue
            raw.setdefault(d, []).append((idx, full))

    if dirs is None:                 # 该族不分方向 ⇒ 全部记在 down（正面最常用）
        _take('down', _rx(spec['pat']))
    else:
        for k, d in sorted(dirs.items()):
            _take(d, _rx(spec['pat'], k))

    out = collections.OrderedDict()
    for d, items in raw.items():
        items.sort(key=lambda t: t[0])
        out[d] = [(i, p, '%s_%d.png' % (d, n), None)
                  for n, (i, p) in enumerate(items)]
    return out


def main(argv):
    write = '--write' in argv
    # `--force`：允许重写**映射表里的人**（我们的 54 个）。
    # 原班 18 人不在此列，无论如何都不覆盖（B2 那条判据的后台）。
    force = '--force' in argv
    print('映射表 %d 人 · 如实无立绘 %d 人' % (len(MAP), len(NO_ART)))
    print('')

    old = json.loads(io.open(MANIFEST, encoding='utf-8').read())
    keep = dict(old.get('characters') or {})
    print('清单现有 %d 人（dr 原班）——**一个都不动**' % len(keep))

    chars = dict(keep)
    detail = collections.OrderedDict()
    fail = []
    for nid, spec in sorted(MAP.items()):
        got = resolve(spec)
        if not got:
            fail.append(nid)
            print('  [空] %-22s 模板 `%s` 在 %s 里一张都没命中'
                  % (nid, spec.get('pat') or spec.get('grid', ('?',))[0],
                     spec['work']))
            continue
        if nid in keep and not force:
            print('  [跳过] %-22s 清单里已有（不覆盖，`--force` 可重写）' % nid)
            continue
        detail[nid] = (spec, got)
        print('  [OK] %-22s %-6s %s'
              % (nid, spec['kind'],
                 {d: min(len(v), MAX_FRAMES_PER_DIR) for d, v in sorted(got.items())}))

    print('')
    print('本轮可落：%d ／ 空模板：%d ／ 落完共 %d 人'
          % (len(detail), len(fail), len(set(chars) | set(detail))))

    # ---- 建条目 ----
    # ★★ 统一画布：原素材里同一角色同方向的帧**尺寸并不一致**
    #   （`spr_ace_down_walk_*` 实测 22x48 与 23x46 并存 —— UTY 的帧是逐帧紧裁剪的）。
    #   渲染层按"脚底 = 窗口下沿"定位，帧高一变脚底就上下跳。所以这里把**一个人的
    #   所有帧**贴到同一张 (最大宽,最大高) 画布上，**底部对齐、水平居中**。
    #   代价是几像素透明边，换来的是"走起来不抖腿"。
    new_chars = {}
    pads = {}
    for nid, (spec, got) in detail.items():
        entry = {'kind': spec['kind'], 'frames': {}}
        dims = []
        for d, items in sorted(got.items()):
            for i, p, name, cut in items[:MAX_FRAMES_PER_DIR]:
                dims.append((cut[2], cut[3]) if cut else png_size(p))
        CW = max([t[0] for t in dims] or [1])
        CH = max([t[1] for t in dims] or [1])
        pads[nid] = (CW, CH)
        for d, items in sorted(got.items()):
            take = items[:MAX_FRAMES_PER_DIR]
            rows = []
            for i, p, name, cut in take:
                rows.append({'f': name, 'src': p, 'cut': cut, 'w': CW, 'h': CH})
            if len(items) > len(take):
                entry.setdefault('truncated', {})[d] = [len(take), len(items)]
            entry['frames'][d] = rows
        new_chars[nid] = entry

    manifest = {
        'schema_version': 1,
        'round': 200,
        'why': ('NPC 本体的取帧清单。运行时**只读本文件**，不做任何文件名猜解'
                '（素材库有多种命名写法，猜解会画错人）。'),
        'how': ('dr 原班 18 人由 `第191轮-NPC本体/_tools/pick191.py` 生成；'
                '外来 54 人由 `第200轮-外来角色立绘/_tools/pick200.py` 生成。'
                '两张映射表都逐条手写，工具只做存在性校验、切格、复制与归一化命名。'),
        'src_root': SPR,
        'max_frames_per_dir': MAX_FRAMES_PER_DIR,
        'no_art': sorted(set(old.get('no_art') or []) | set(NO_ART)),
        'no_art_reason': dict(NO_ART),
        'characters': chars,
    }
    manifest['characters'].update(new_chars)

    print('')
    print('清单：%d 人（原 %d + 新 %d）· no_art %d 人'
          % (len(manifest['characters']), len(keep), len(new_chars),
             len(manifest['no_art'])))

    if not write:
        print('')
        print('（预演，未写盘。加 --write 才切图/复制/写清单）')
        return 0

    # ---- 落盘（幂等：先清目标目录里的旧帧，再写）----
    from PIL import Image
    if not os.path.isdir(DEST_ROOT):
        os.makedirs(DEST_ROOT)
    n_png = 0
    for nid, entry in new_chars.items():
        dst = os.path.join(DEST_ROOT, nid)
        if os.path.isdir(dst):
            for f in os.listdir(dst):
                if f.lower().endswith('.png'):
                    os.remove(os.path.join(dst, f))
        else:
            os.makedirs(dst)
        for d, rows in entry['frames'].items():
            CW, CH = pads[nid]
            for row in rows:
                cut = row.pop('cut')
                src = row.pop('src')
                out_p = os.path.join(dst, row['f'])
                if cut:
                    i, r, cw, ch = cut
                    im = Image.open(src).convert('RGBA')
                    sub = im.crop((i * cw, r * ch, (i + 1) * cw, (r + 1) * ch))
                else:
                    sub = Image.open(src).convert('RGBA')
                if not cut and sub.size == (CW, CH):
                    sub.close()
                    shutil.copy2(src, out_p)          # 原样搬：与源**逐字节相同**
                elif sub.size == (CW, CH):
                    sub.save(out_p)                   # 切出来的格子，尺寸刚好填满
                else:
                    canvas = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
                    canvas.alpha_composite(sub, ((CW - sub.size[0]) // 2,
                                                 CH - sub.size[1]))   # 底部对齐
                    canvas.save(out_p)
                w, h = png_size(out_p)
                assert (w, h) == (row['w'], row['h']), (out_p, w, h)
                row['sha256'] = sha256_file(out_p)
                n_png += 1

    with io.open(MANIFEST, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write(u'\n')
    print('')
    print('已写盘：%d 人 / %d 张 PNG → %s' % (len(new_chars), n_png, DEST_ROOT))
    print('清单：%s' % MANIFEST)
    if fail:
        print('!! 空模板：%s' % ', '.join(fail))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
