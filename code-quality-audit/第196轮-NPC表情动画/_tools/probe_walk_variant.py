# -*- coding: utf-8 -*-
"""第196轮探针 4：原作 overworld 的**情绪行走图变体**覆盖度。

为什么换这个口径
----------------
探针 3 证明「独立情绪动画帧」这条路很窄：18 个有立绘的角色里只有 10 个
命中，且**没有一个**六情绪齐全 —— 因为原作大部分"哈哈大笑/大哭"是
**cutscene 整图**（画布尺寸完全不同，塞进小窗必然跳）。

而原作在 overworld（= 桌面这个场地）里表现情绪，靠的是**换一套行走图**：
  `spr_susie_walk_down_dw_unhappy`   不高兴
  `spr_noelle_walk_down_sad_dw_0`    难过
  `spr_berdly_walk_left_mad_dw`      生气
这套图的画布尺寸与常驻走路图**同族**（原作自己就是这么渲染的），所以：
  ① 不会跳尺寸  ② 天然带四个朝向  ③ 站着不动时取第 0 帧就是"表情站姿"

本脚本按「角色 × 情绪 × 朝向」数这套变体有多少，作为能否落地的唯一依据。
"""
import io
import json
import os
import re
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
GAME = os.path.abspath(os.path.join(REPO, '..', 'deltarune'))
MANIFEST = os.path.join(PET, 'assets', 'sprites', 'dr', '_npc_frames.json')
DR = os.path.join(PET, 'assets', 'sprites', 'dr')

#: 立绘 id → 原作文件名里的 token。★ 手工映射，**不靠猜**：
#: 已经用探针证实 `susiedark` 在原作里就是 `susie` 的 dark 目录，
#: 文件名仍写 `susie`；其余同理。
TOKEN = {
    'susiedark': 'susie',
    'addison_tea': 'addison',
}

#: 情绪 → 文件名里的"变体词"。★ 全是**原作自己的命名**，不是我编的。
EMO_WORDS = [
    ('sad', r'unhappy|_sad|sad_'),
    ('angry', r'_mad|mad_|angry|annoy'),
    ('happy', r'_happy|happy_|smile|laugh'),
    ('surprised', r'surpris|shock'),
    ('hurt', r'hurt'),
]

DIRS = ['down', 'left', 'right', 'up']

WALK = re.compile(r'walk', re.I)


def png_hw(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(26)
        if len(head) < 26 or head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        w, h = struct.unpack('>II', head[16:24])
        return int(w), int(h)
    except Exception:
        return None


def dir_of(fn):
    s = fn.lower()
    for d in DIRS:
        if re.search(r'(?:^|_)%s(?:_|\.|$)' % d, s):
            return d
    if re.search(r'(?:^|_)dw(?:_|\.|$)', s):
        return 'down'
    if re.search(r'(?:^|_)lw(?:_|\.|$)', s):
        return 'left'
    if re.search(r'(?:^|_)rw(?:_|\.|$)', s):
        return 'right'
    if re.search(r'(?:^|_)uw(?:_|\.|$)', s):
        return 'up'
    return None


def walk_pngs(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.png'):
                out.append(os.path.join(dp, f))
    return out


def main():
    print('=' * 88)
    print('第196轮探针 4 · 原作 overworld 情绪行走图变体覆盖度')
    print('=' * 88)

    with io.open(MANIFEST, 'r', encoding='utf-8') as f:
        man = json.load(f)
    chars = man.get('characters') or {}
    all_png = walk_pngs(GAME)
    print('原作 png %d 张\n' % len(all_png))

    summary = {}
    print('%-12s %-9s %s' % ('角色', '基线', '  '.join('%-22s' % e for e, _ in EMO_WORDS)))
    print('-' * 100)
    for cid in sorted(chars):
        tok = TOKEN.get(cid, cid)
        tok_re = re.compile(r'(?<![a-z])%s(?![a-z])' % re.escape(tok), re.I)
        fr = (chars[cid].get('frames') or {})
        d0 = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        b = png_hw(os.path.join(DR, cid, fr[d0][0]['f'])) if d0 else None

        cell = []
        detail = {}
        for emo, pat in EMO_WORDS:
            hits = defaultdict(list)
            for p in all_png:
                fn = os.path.basename(p)
                if not tok_re.search(fn):
                    continue
                if not re.search(pat, fn, re.I):
                    continue
                s = png_hw(p)
                if not s:
                    continue
                # 只认与基线同族的（高度差 ≤2）
                if b and abs(s[1] - b[1]) > 2:
                    continue
                dd = dir_of(fn) or '?'
                hits[dd].append((fn, '%dx%d' % s, bool(WALK.search(fn))))
            detail[emo] = {k: [{'f': a, 'size': b2, 'walk': c}
                               for a, b2, c in v] for k, v in hits.items()}
            nd = len([k for k in hits if k in DIRS])
            n = sum(len(v) for v in hits.values())
            cell.append('%-22s' % ('%d帧/%d向' % (n, nd) if n else '—'))
        summary[cid] = {'base': ('%dx%d' % b) if b else None, 'emo': detail}
        print('%-12s %-9s %s' % (cid, ('%dx%d' % b) if b else '?', '  '.join(cell)))

    # ---- 明细 ----
    print('\n' + '=' * 88)
    print('明细（只列有帧的；`W`=走动帧 `S`=站姿帧）')
    print('=' * 88)
    for cid in sorted(summary):
        e = summary[cid]['emo']
        if not any(e[k] for k, _ in EMO_WORDS):
            continue
        print('\n### %s' % cid)
        for emo, _ in EMO_WORDS:
            h = e.get(emo) or {}
            if not h:
                continue
            print('  [%s]' % emo)
            for dd in sorted(h):
                v = h[dd]
                print('    %-6s %d帧 %s' % (dd, len(v), ' '.join(
                    '%s%s' % ('W' if x['walk'] else 'S', x['size']) for x in v[:6])))

    # ---- 能覆盖多少 ----
    print('\n' + '=' * 88)
    print('结论')
    print('=' * 88)
    n_any = sum(1 for c in summary if any(summary[c]['emo'][k] for k, _ in EMO_WORDS))
    print('至少一个情绪可用：%d / %d' % (n_any, len(summary)))
    for emo, _ in EMO_WORDS:
        cs = [c for c in summary if summary[c]['emo'].get(emo)]
        print('  %-10s 角色数=%d  %s' % (emo, len(cs), ', '.join(sorted(cs))))

    ev = os.path.join(ROUND, '_evidence', 'anim_walkvariant_probe.json')
    try:
        with io.open(ev, 'w', encoding='utf-8') as f:
            f.write(json.dumps(summary, ensure_ascii=False, indent=1))
        print('\n[证据] %s' % ev)
    except Exception as e:
        print('[WARN] %s' % e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
