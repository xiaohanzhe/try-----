# -*- coding: utf-8 -*-
"""第196轮探针 6：**最终可用集**（三道过滤全开），逐角色逐情绪逐朝向结算。

三道过滤
--------
① token 命中该角色（`susiedark`→`susie` 这类手工映射）
② 文件名里**不出现其他已登记角色**的 token（双人 cutscene 整图不能用）
③ 与走路帧同尺寸族：高度差 ≤2px；宽度 ≤2.0× 该角色正面走路帧宽度
   （侧视本来就更窄，所以只设上限不设下限）

输出：能落地的 (角色, 情绪, 朝向) → 帧列表，直接就是 NPC 动画清单的雏形。
**本脚本不写产品文件**，只落 `_evidence/`。
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

TOKEN = {'susiedark': 'susie', 'addison_tea': 'addison'}

EMO_WORDS = [
    ('happy', r'(?<!un)happy|laugh|smile|giggl'),
    ('sad', r'unhappy|(?<!un)sad'),
    ('angry', r'angry|_mad|mad_|annoy'),
    ('surprised', r'surpris|shock|startl'),
    ('hurt', r'hurt|pain|wince'),
]

#: 朝向判定。★ `dw/lw/rw/uw` 是 DR 的"暗世界"后缀，不是方向词，
#: 但出现在**方向槽位**时等价于 down/left/right/up。
DIR_PAT = [
    ('down', r'(?:^|_)down(?:_|\.|$)|(?:^|_)dw(?:_|\.|$)'),
    ('left', r'(?:^|_)left(?:_|\.|$)|(?:^|_)lw(?:_|\.|$)'),
    ('right', r'(?:^|_)right(?:_|\.|$)|(?:^|_)rw(?:_|\.|$)'),
    ('up', r'(?:^|_)up(?:_|\.|$)|(?:^|_)uw(?:_|\.|$)'),
]


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
    for d, pat in DIR_PAT:
        if re.search(pat, s):
            return d
    return None


def main():
    with io.open(MANIFEST, 'r', encoding='utf-8') as f:
        man = json.load(f)
    chars = man.get('characters') or {}
    all_ids = sorted(chars.keys())

    all_png = []
    for dp, _dn, fn in os.walk(GAME):
        for f in fn:
            if f.lower().endswith('.png'):
                all_png.append(os.path.join(dp, f))

    # 全部角色 token（含别名）——用于"双人帧"判定
    all_toks = set()
    for c in all_ids:
        all_toks.add(TOKEN.get(c, c).lower())

    out = {}
    for cid in all_ids:
        tok = TOKEN.get(cid, cid).lower()
        fr = (chars[cid].get('frames') or {})
        d0 = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        b = png_hw(os.path.join(DR, cid, fr[d0][0]['f'])) if d0 else None
        if not b:
            out[cid] = {'base': None, 'anims': {}}
            continue

        me_re = re.compile(r'(?<![a-z])%s(?![a-z])' % re.escape(tok), re.I)
        others = [t for t in all_toks if t != tok]
        oth_re = re.compile(
            r'(?<![a-z])(?:%s)(?![a-z])' % '|'.join(re.escape(t) for t in others),
            re.I) if others else None

        anims = defaultdict(lambda: defaultdict(list))
        for p in all_png:
            fn = os.path.basename(p)
            if not me_re.search(fn):
                continue
            emo = None
            for e, pat in EMO_WORDS:
                if re.search(pat, fn, re.I):
                    emo = e
                    break
            if emo is None:
                continue
            if oth_re is not None and oth_re.search(fn):
                continue                                   # ② 双人帧
            s = png_hw(p)
            if not s:
                continue
            if abs(s[1] - b[1]) > 2:
                continue                                   # ③ 高度族
            if s[0] > 2.0 * b[0]:
                continue                                   # ③ 宽度上限
            dd = dir_of(fn) or 'down'                      # 无方向词 ⇒ 按正面
            anims[emo][dd].append({'f': fn, 'w': s[0], 'h': s[1]})
        # 去重（同一文件名可能在多个章节目录）
        for e in anims:
            for d in anims[e]:
                seen, keep = set(), []
                for it in anims[e][d]:
                    if it['f'] in seen:
                        continue
                    seen.add(it['f'])
                    keep.append(it)
                anims[e][d] = keep
        out[cid] = {'base': '%dx%d' % b, 'anims': {e: dict(v) for e, v in anims.items()}}

    # ---- 报表 ----
    print('=' * 92)
    print('第196轮探针 6 · 最终可用集（三道过滤全开）')
    print('=' * 92)
    hdr = '%-12s %-9s ' % ('角色', '基线') + '  '.join('%-17s' % e for e, _ in EMO_WORDS)
    print(hdr)
    print('-' * 100)
    for cid in all_ids:
        r = out[cid]
        cells = []
        for e, _ in EMO_WORDS:
            a = (r['anims'] or {}).get(e) or {}
            n = sum(len(v) for v in a.values())
            nd = len(a)
            cells.append('%-17s' % ('%d帧/%d向' % (n, nd) if n else '—'))
        print('%-12s %-9s %s' % (cid, r['base'] or '?', '  '.join(cells)))

    print('\n' + '=' * 92)
    print('逐角色明细（方向 → 帧数，样例文件名）')
    print('=' * 92)
    for cid in all_ids:
        a = (out[cid]['anims'] or {})
        if not a:
            continue
        print('\n### %s  基线 %s' % (cid, out[cid]['base']))
        for e, _ in EMO_WORDS:
            d = a.get(e) or {}
            if not d:
                continue
            print('  [%s]' % e)
            for dd in ('down', 'left', 'right', 'up'):
                v = d.get(dd) or []
                if not v:
                    continue
                print('    %-6s %-2d帧  %s%s' % (
                    dd, len(v),
                    ' '.join('%dx%d' % (x['w'], x['h']) for x in v[:4]),
                    '' if len(v) <= 4 else ' …'))
                print('           %s' % ', '.join(x['f'] for x in v[:3]))

    # ---- 汇总 ----
    print('\n' + '=' * 92)
    print('汇总')
    print('=' * 92)
    tot = 0
    for e, _ in EMO_WORDS:
        cs = [c for c in all_ids if ((out[c]['anims'] or {}).get(e))]
        n = sum(sum(len(v) for v in ((out[c]['anims'] or {}).get(e) or {}).values())
                for c in all_ids)
        tot += n
        print('  %-10s 角色 %-2d 帧 %-4d  %s' % (e, len(cs), n, ', '.join(cs)))
    any_c = [c for c in all_ids if (out[c]['anims'])]
    print('\n有任一情绪的：%d / %d' % (len(any_c), len(all_ids)))
    print('一个都没有的：%s' % ', '.join(c for c in all_ids if not out[c]['anims']))
    print('总帧数：%d' % tot)

    ev = os.path.join(ROUND, '_evidence', 'anim_final_set.json')
    try:
        with io.open(ev, 'w', encoding='utf-8') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
        print('\n[证据] %s' % ev)
    except Exception as e:
        print('[WARN] %s' % e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
