# -*- coding: utf-8 -*-
u"""第190轮 · `assets/faces/` 独立核验（不信 build_faces190 的闸，另开一条路重算）。

★★ 为什么要有这个脚本
--------------------
`build_faces190.py` 的闸② 是"落盘文件读回 == 源图"。它能抓保存损失，但**抓不到
"manifest 的 file 字段指错了源"** —— 因为它比的是自己内存里那一对 (src, out)。
⇒ 这里改成**只读仓库产物 + 只读原始素材**，重新推导源路径，一路比到底：

  L1  仓库 png  == 中间裁切件（D:\\_tmp190\\cropped\\hy\\*.png / OneShot portraits）
  L2  仓库 png  == **从原始整页 png 现场重裁**（跨过中间产物这一环，端到端）
      ★ L2 才是真独立：中间件被人动过、或页序变了，L1 绿 L2 红。

用法
----
    python verify_faces190.py            # L1 全量 + L2 抽 12 条
    python verify_faces190.py --l2all     # L2 也全量（慢一点，但更硬）
"""
import io
import json
import os
import random
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
FACES = os.path.join(REPO, 'ralsei_pet', 'assets', 'faces')
MF = os.path.join(FACES, 'manifest.json')

HY_CROP = u'D:\\_tmp190\\cropped\\hy'
HY_CROP_MF = os.path.join(HY_CROP, '_manifest.json')
HY_PAGES = u'D:\\_tmp190\\hy_export_pages190\\pages'
OS_DIR = u'E:\\项目文件夹\\xnbcli（oneshot)\\unpacked\\the_world_machine\\portraits'

#: 与 build_faces190 的 HY_ROLE 反向对应（id → 角色名）。**独立写一份**，
#: 故意不复用 —— 复用就变成"同一个假设验两遍"，抓不到映射错误。
ID2ROLE = {
    'hy_ceroba_ketsukane': 'ceroba',
    'hy_chujin_ketsukane': 'chujin',
    'hy_starlo': 'starlo',
    'hy_mooch': 'mooch',
    'hy_moray': 'moray',
    'hy_ace': 'ace',
    'hy_axis': 'axis',
    'hy_ed': 'ed',
}


def rgba_bytes(p):
    im = Image.open(p)
    im.load()
    return im.convert('RGBA')


def page_file(page):
    """页号 → 整页 png 路径（UTMT 导出的命名是 pXXX.png，宽度补零见下）。"""
    for cand in ('p%03d.png' % page, 'p%d.png' % page, 'p%04d.png' % page):
        p = os.path.join(HY_PAGES, cand)
        if os.path.isfile(p):
            return p
    return None


def main():
    l2all = '--l2all' in sys.argv[1:]
    if not os.path.isfile(MF):
        print(u'[停手] 缺 manifest：%s' % MF)
        return 2
    man = json.load(io.open(MF, encoding='utf-8'))
    crop = json.load(io.open(HY_CROP_MF, encoding='utf-8'))
    print(u'[输入] 仓库 manifest %d 条 / 裁切清单 %d 条' % (len(man), len(crop)))

    # 裁切清单建索引：(name, frame) -> 条目
    cidx = {}
    for c in crop:
        cidx[(c['name'], c['frame'])] = c

    ok1 = bad1 = 0
    l1_missing = []
    paired = []      # 供 L2 抽样的 (manifest 条目, 裁切条目)
    for m in man:
        dst = os.path.join(FACES, m['file'].replace('/', os.sep))
        if not os.path.isfile(dst):
            l1_missing.append(m['file'])
            continue
        if m['kind'] == 'expression':
            role = ID2ROLE.get(m['id'])
            src = os.path.join(HY_CROP, cidx[('spr_portrait_%s_%s' % (role, m['emotion']),
                                              m['frame'])]['file'])
            paired.append((m, cidx[('spr_portrait_%s_%s' % (role, m['emotion']), m['frame'])]))
        else:
            src = os.path.join(OS_DIR, '%s.png' % m['emotion'])
        if not os.path.isfile(src):
            l1_missing.append(u'源缺失 ' + src)
            continue
        a, b = rgba_bytes(dst), rgba_bytes(src)
        if a.size != b.size:
            bad1 += 1
            print(u'[L1报红] 尺寸 %s %s vs %s' % (m['file'], a.size, b.size))
        elif a.tobytes() != b.tobytes():
            bad1 += 1
            print(u'[L1报红] 像素 %s' % m['file'])
        else:
            ok1 += 1

    print(u'')
    print(u'[L1] 仓库 == 中间裁切件')
    print(u'   %s  一致 %d / 不一致 %d / 缺 %d %s'
          % (u'OK' if (not bad1 and not l1_missing) else u'报红',
             ok1, bad1, len(l1_missing), l1_missing[:3]))

    # ── L2：从原始整页现场重裁 ─────────────────────────────────
    sample = paired if l2all else random.Random(190).sample(paired, min(12, len(paired)))
    ok2 = bad2 = 0
    bad2_detail = []
    for m, c in sample:
        pf = page_file(c['page'])
        if pf is None:
            bad2_detail.append((m['file'], u'页缺失 p%s' % c['page']))
            continue
        x, y, w, h = c['rect']
        pg = rgba_bytes(pf)
        if x < 0 or y < 0 or x + w > pg.size[0] or y + h > pg.size[1]:
            bad2_detail.append((m['file'], u'rect 越页界'))
            continue
        recrop = pg.crop((x, y, x + w, y + h))
        dst = rgba_bytes(os.path.join(FACES, m['file'].replace('/', os.sep)))
        if recrop.size != dst.size:
            bad2_detail.append((m['file'], u'尺寸 %s vs %s' % (recrop.size, dst.size)))
        elif recrop.tobytes() != dst.tobytes():
            bad2_detail.append((m['file'], u'像素不同'))
        else:
            ok2 += 1
    for d in bad2_detail:
        print(u'[L2报红] %s  %s' % d)

    print(u'[L2] 仓库 == 从整页现场重裁（%s）' % (u'全量' if l2all else u'抽 12 条'))
    print(u'   %s  一致 %d / 不一致 %d'
          % (u'OK' if not bad2_detail else u'报红', ok2, len(bad2_detail)))

    # ── L3：原样保真的"负控制" —— 证明上面的比法真能分辨 ─────────
    #    拿一条产物，人为改 1 像素，用同一套比法 ⇒ 必须报不同
    #    （否则"全部一致"可能只是比法恒真）
    if ok1:
        p = os.path.join(FACES, man[0]['file'].replace('/', os.sep))
        a = rgba_bytes(p)
        b = a.copy()
        b.putpixel((0, 0), ((a.getpixel((0, 0))[0] + 1) % 256,
                            a.getpixel((0, 0))[1],
                            a.getpixel((0, 0))[2],
                            a.getpixel((0, 0))[3]))
        same = (a.tobytes() == b.tobytes())
        print(u'[L3] 负控制：改 1 像素后仍判"相同"? ⇒ %s'
              % (u'居然相同（比法失效，前面全绿不算数）' if same else u'判为不同 OK'))

    print(u'')
    if bad1 or l1_missing or bad2_detail:
        print(u'[报红] 独立核验未过 ⇒ 不许当成功')
        return 6
    print(u'[全部通过] L1 + L2 两层独立路径全部一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
