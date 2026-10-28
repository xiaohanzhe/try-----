# -*- coding: utf-8 -*-
u"""把 bg↔tmx 比对结果拆成三类，回答「到底是几何不一致还是只缺底色层」。"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oneshot_tmx as T

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None

ROUND = os.path.normpath(os.path.join(HERE, '..'))
REPO = os.path.normpath(os.path.join(ROUND, '..', '..'))
BG = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', 'bg')
EV = os.path.join(ROUND, '_evidence', 'bg_vs_tmx114.json')


def base_is_uniform(num):
    u"""PNG 里「渲染为透明」的那些像素是不是同一个颜色（= 底色层）。"""
    p = os.path.join(BG, 'oneshot_map%d.png' % num)
    q = 'D:/_tmp/render_all/map%d.png' % num
    A = np.asarray(Image.open(p).convert('RGBA'))
    B = np.asarray(Image.open(q).convert('RGBA'))
    nb = B[:, :, 3] > 0
    na = A[:, :, 3] > 0
    extra = A[na & ~nb][:, :3]
    if len(extra) == 0:
        return True, 0
    # 唯一颜色数（抽样 5000 点即可）
    step = max(1, len(extra) // 5000)
    uniq = np.unique(extra[::step], axis=0)
    return (len(uniq) <= 2), len(uniq)


def main():
    rows = json.load(io.open(EV, encoding='utf-8'))
    rows = [r for r in rows if 'iou' in r]
    cat = {'same': [], 'basecolor_only': [], 'diff': []}
    for r in rows:
        n = r['map']
        rgb_ok = r['rgb_eq'] >= 0.99
        no_extra_mine = r['only_mine'] == 0
        if rgb_ok and no_extra_mine and r['only_png'] == 0:
            cat['same'].append(n)
        elif rgb_ok and no_extra_mine:
            uni, k = base_is_uniform(n)
            r['base_uniq'] = k
            (cat['basecolor_only'] if uni else cat['diff']).append(n)
        else:
            cat['diff'].append(n)
    print(u'可比对 %d 间：' % len(rows))
    print(u'  A 完全一致（含透明区域也一样）      %3d 间' % len(cat['same']))
    print(u'  B 只差一层底色（补上底色就等于一致）%3d 间' % len(cat['basecolor_only']))
    print(u'  C 真有内容差异                      %3d 间' % len(cat['diff']))
    print(u'\nC 组明细：')
    idx = dict((r['map'], r) for r in rows)
    for n in cat['diff']:
        r = idx[n]
        print(u'   map%-4d rgb同=%.3f 两边都有=%-7d 仅PNG=%-7d 仅渲染=%-7d 底色唯一色=%s'
              % (n, r['rgb_eq'], r['both'], r['only_png'], r['only_mine'],
                 r.get('base_uniq', '-')))
    print(u'\nB 组前 10 间：%s' % cat['basecolor_only'][:10])

    p = os.path.join(ROUND, '_evidence', 'bg_verdict114.json')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'same': cat['same'], 'basecolor_only': cat['basecolor_only'],
                            'diff': cat['diff']}, ensure_ascii=False, indent=1))
    print(u'\n结论 → %s' % p)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
