# -*- coding: utf-8 -*-
"""第196轮探针 2：命中样例**逐条看一眼**，确认不是假命中、且能当真动画用。

三个必查项（都是本项目踩过的坑）：
① 假命中：`happy` 命中 `unhappy`（sad 的写法）；`cry` 命中 `crystal`
② 同 token 串味：`susie` 命中 `susiedark` 的文件 ⇒ 两个角色的数字一模一样
③ **尺寸/基线**：走路帧是紧凑循环（同尺寸、同基线）；cutscene 帧大小随意，
   如果两者混进同一个窗口，NPC 一笑就会「跳一下 + 变形」

只用文件名与 PNG 头（IHDR 里的宽高）判断，不解码像素。
"""
import io
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
GAME = os.path.abspath(os.path.join(REPO, '..', 'deltarune'))
MANIFEST = os.path.join(PET, 'assets', 'sprites', 'dr', '_npc_frames.json')
DR = os.path.join(PET, 'assets', 'sprites', 'dr')

EMO = {'laugh': r'laugh', 'cry': r'cry(?!stal)', 'sad': r'(?<!un)sad|_sad_|_sad\b',
       'surprised': r'surpris|shock', 'angry': r'angry|_mad_|_mad\b'}


def png_size(path):
    """只读 IHDR，不 Decode。返回 (w, h) 或 None。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(26)
        if len(head) < 26 or head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        w, h = struct.unpack('>II', head[16:24])
        return int(w), int(h)
    except Exception:
        return None


def walk_pngs(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.png'):
                out.append(os.path.join(dp, f))
    return out


def main():
    print('=' * 78)
    print('第196轮探针 2 · 命中样例与尺寸一致性')
    print('=' * 78)

    with io.open(MANIFEST, 'r', encoding='utf-8') as f:
        man = json.load(f)
    ch = man.get('characters') or {}

    # ---- 走路帧尺寸基线（产品当前能画的）----
    print('\n[A] 走路帧尺寸（产品当前渲染用的）')
    for cid in ('susie', 'noelle', 'lancer', 'berdly', 'kris'):
        e = (ch.get(cid) or {}).get('frames') or {}
        for d in ('down',):
            fr = e.get(d) or []
            sizes = []
            for it in fr:
                p = os.path.join(DR, cid, it['f'])
                s = png_size(p)
                sizes.append(('%dx%d' % s) if s else '?')
            print('  %-8s %-5s %-2d帧  %s' % (cid, d, len(fr), ' '.join(sizes)))

    # ---- 逐角色样例 ----
    all_png = walk_pngs(GAME)
    print('\n[B] 情绪帧样例（按角色 + 关键词，最多 3 条，带尺寸）')
    for cid in ('susie', 'noelle', 'lancer', 'toriel', 'berdly', 'gerson', 'kris'):
        tok = re.compile(r'(?<![a-z])%s(?![a-z])' % re.escape(cid), re.I)
        print('  --- %s' % cid)
        for k, pat in EMO.items():
            hit = []
            for p in all_png:
                fn = os.path.basename(p)
                if not tok.search(fn):
                    continue
                if not re.search(pat, fn, re.I):
                    continue
                s = png_size(p)
                hit.append((fn, s))
            if not hit:
                continue
            show = hit[:3]
            print('    %-10s n=%-4d %s' % (
                k, len(hit),
                ' | '.join('%s(%s)' % (n, ('%dx%d' % s) if s else '?')
                           for n, s in show)))

    # ---- 同 token 串味检查 ----
    print('\n[C] token 串味检查（`susie` 会不会吃到 `susiedark` 的文件）')
    for a, b in (('susie', 'susiedark'), ('kris', 'krisdark')):
        ra = re.compile(r'(?<![a-z])%s(?![a-z])' % a, re.I)
        n_a = sum(1 for p in all_png if ra.search(os.path.basename(p)))
        n_both = 0
        for p in all_png:
            fn = os.path.basename(p)
            if ra.search(fn) and re.search(r'(?<![a-z])%s(?![a-z])' % b, fn, re.I):
                n_both += 1
        print('  %-10s 命中 %-5d  其中同时含 %-10s 的 %d' % (a, n_a, b, n_both))

    # ---- 目录归属 ----
    print('\n[D] 命中帧落在哪些目录（章节归属，决定该不该混用）')
    from collections import Counter
    c = Counter()
    for p in all_png:
        fn = os.path.basename(p)
        if re.search(r'susie', fn, re.I) and re.search(r'laugh|happy', fn, re.I):
            rel = os.path.relpath(p, GAME)
            c[os.path.dirname(rel)] += 1
    for k, v in c.most_common(12):
        print('  %-40s %d' % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())
