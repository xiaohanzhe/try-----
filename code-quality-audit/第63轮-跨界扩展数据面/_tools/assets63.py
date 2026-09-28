#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第63轮 · 扩展线①：outertale **权威资源表**提取（从 index.js 的 Vite 资产绑定）。

为什么换法子
-----------
第一版按"文件名 = 逻辑名"配对：1066 个 json 里只有 844 命中，`meta.size` 与 PNG
真实尺寸也有 138 条不符 —— 因为 Vite 给文件名加了内容哈希，且**同名逻辑资源有多个**。
⇒ 真源在 `index.js` 里：

    v$=""+new URL("AYAYA-CLoY7mWt.json",import.meta.url).href
    _$=""+new URL("AYAYA-TBKWE3P5.png",import.meta.url).href
    ...
    idcPapyrusAYAYA:new M(new T(_$),new W(v$)),
    idcPapyrusAyoo:new M(new T(H$),new W(N$)),

`idc*` = 具名精灵（**游戏代码里的权威名字**）。本工具：
  S1 建 变量 → 文件名 映射；
  S2 解析 `名字:new M(new T(pngVar),new W(jsonVar))` 与 `名字:new T(imgVar)`；
  S3 **A/B 锚点**：① 每个被引用的变量都必须解析到**磁盘上存在的文件**（应 100%）；
     ② json 与 png 的**逻辑 stem 必须一致**（`AYAYA.json` ↔ `AYAYA.png`）；
     ③ 交叉验证：json 的 `meta.size` 与配对 png 的 IHDR 必须一致（用 S2 的**显式配对**，
        而不是名字猜配对）。
  S4 按名字前缀归类，产出角色清单。

用法：
  python assets63.py --run
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

WWW = u'E:\\Download\\_extract61\\outertale\\www'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
OUT = os.path.join(ROUND, '_evidence')

#: `X$=""+new URL("f.png",import.meta.url).href`
RE_URL = re.compile(u'([A-Za-z0-9_$]+)\\s*=\\s*""\\s*\\+\\s*new URL\\("([^"]+)"')
#: `名字:new M(new T(pngVar),new W(jsonVar))`
RE_M = re.compile(u'([A-Za-z0-9_$]+):new M\\(new T\\(([A-Za-z0-9_$]+)\\),'
                  u'new W\\(([A-Za-z0-9_$]+)\\)\\)')
#: `名字:new T(imgVar)`
RE_T = re.compile(u'([A-Za-z0-9_$]+):new T\\(([A-Za-z0-9_$]+)\\)')
#: `X=new T(varPng)` / `X=new W(varJson)`（变量式构造，后面再结合）
RE_NEWT = re.compile(u'([A-Za-z0-9_$]+)=new T\\(([A-Za-z0-9_$]+)\\)')
RE_NEWW = re.compile(u'([A-Za-z0-9_$]+)=new W\\(([A-Za-z0-9_$]+)\\)')


def js_path():
    js = [f for f in os.listdir(WWW)
          if f.lower().startswith(u'index-') and f.lower().endswith(u'.js')]
    return os.path.join(WWW, js[0])


def png_size(p):
    b = io.open(p, 'rb').read(26)
    if len(b) < 24 or b[:8] != b'\x89PNG\r\n\x1a\n' or b[12:16] != b'IHDR':
        return None
    return (int(b[16:20].hex(), 16), int(b[20:24].hex(), 16))


def logical_stem(fn):
    u"""去掉 Vite 的内容哈希后缀（**8 字符，且可能自带 `-`**）。

    ★ 我第一版用 `rsplit('-',1)[0]` —— 错：`beaker1-6-gF1QmP` / `asteroidfragment-BhME4y-3`
      的哈希里就含 `-`，于是 207 条被误判成"stem 不一致"。判据过窄 = 误报。
    """
    base = os.path.splitext(fn)[0]
    if len(base) > 9 and base[-9] == u'-':
        return base[:-9]
    return base


def first_token(name):
    u"""`iocAlphysDownSadTalk` → 前缀 `ioc` + 首词 `Alphys`。

    判据：前缀 = 开头连续小写；其后第一个 CamelCase 词 = 角色/物件名。
    """
    m = re.match(u'^([a-z]+)([A-Z][a-z0-9]*)', name)
    if m:
        return m.group(1), m.group(2)
    m2 = re.match(u'^([a-z]+)(.*)$', name)
    return (m2.group(1), m2.group(2)) if m2 else (u'(?)', name)


def main():
    p = js_path()
    t = io.open(p, 'rb').read().decode('utf-8', 'replace')
    print(u'[S0] %s  %d 字节' % (os.path.basename(p), len(t)))

    url_map = {}
    for var, fn in RE_URL.findall(t):
        url_map.setdefault(var, fn)
    print(u'[S1] URL 变量 %d 个' % len(url_map))

    present = set(os.listdir(WWW))
    pairs = []          # (name, pngVar, jsonVar)
    singles = []        # (name, imgVar)
    for m in RE_M.finditer(t):
        pairs.append((m.group(1), m.group(2), m.group(3)))
    names_in_M = set(x[0] for x in pairs)
    for m in RE_T.finditer(t):
        if m.group(1) not in names_in_M:
            singles.append((m.group(1), m.group(2)))
    print(u'[S2] 具名精灵（图+图集）=%d；仅图=%d' % (len(pairs), len(singles)))

    # 锚点 ①：每个引用变量必须解析到**磁盘存在的文件**
    unres = []
    miss_file = []
    recs = []
    for name, pv, jv in pairs:
        fp = url_map.get(pv)
        fj = url_map.get(jv)
        if not fp or not fj:
            unres.append((name, pv, jv))
            continue
        if fp not in present or fj not in present:
            miss_file.append((name, fp, fj))
            continue
        recs.append((name, fp, fj))
    print()
    print(u'[S3 锚点①] 变量无法解析 %d 条；解析到但磁盘缺失 %d 条'
          % (len(unres), len(miss_file)))
    print(u'          样本 unres=%r' % (unres[:3],))
    print(u'          样本 miss =%r' % (miss_file[:3],))

    # 锚点 ②：json 与 png 的逻辑 stem 一致
    bad_stem = [(n, fp, fj) for n, fp, fj in recs
                if logical_stem(fp) != logical_stem(fj)]
    print(u'[S3 锚点②] 逻辑 stem 不一致 %d / %d' % (len(bad_stem), len(recs)))
    print(u'          样本=%r' % (bad_stem[:3],))

    # 锚点 ③：json.meta.size == 配对 png 的 IHDR（**显式配对**，非名字猜）
    gok = gbad = 0
    gs = []
    for n, fp, fj in recs:
        try:
            d = json.loads(io.open(os.path.join(WWW, fj), 'rb')
                           .read().decode('utf-8'))
        except Exception:
            continue
        sz = (d.get(u'meta') or {}).get(u'size') or {}
        real = png_size(os.path.join(WWW, fp))
        if not real or not isinstance(sz.get(u'w'), int):
            continue
        if (sz[u'w'], sz[u'h']) == real:
            gok += 1
        else:
            gbad += 1
            if len(gs) < 6:
                gs.append((n, fj, (sz[u'w'], sz[u'h']), real))
    print(u'[S3 锚点③] meta.size == 配对 png IHDR：一致 %d，不一致 %d'
          % (gok, gbad))
    print(u'          不一致样本=%r' % (gs,))

    # S4：按名字前缀归类（`idcPapyrusAYAYA` → 前缀 idc，族 = ?）
    pref = Counter()
    for n, _, _ in recs:
        m = re.match(u'^([a-z]+)', n)
        pref[m.group(1) if m else u'(?)'] += 1
    print()
    print(u'[S4] 名字小写前缀 Top：%r' % (pref.most_common(12),))
    by_pref = defaultdict(list)
    for n, _, _ in recs:
        m = re.match(u'^([a-z]+)', n)
        by_pref[m.group(1) if m else u'(?)'].append(n)
    print()
    print(u'[S4] 每个前缀的样本（判断它到底代表什么）：')
    for k, v in pref.most_common(12):
        print(u'      %-5s %4d  %r' % (k, v, v and sorted(by_pref[k])[:8]))

    # S5：按 (前缀, 首词) 抽"实体"（角色/物件），只统计不下结论
    ent = defaultdict(list)
    for n, _, _ in recs:
        pfx, tok = first_token(n)
        ent[(pfx, tok)].append(n)
    ent_count = Counter()
    for (pfx, tok), v in ent.items():
        ent_count[(pfx, tok)] = len(v)
    print()
    print(u'[S5] 各家族里"贴图数最多"的实体 Top（数量≈戏份）：')
    for (pfx, tok), c in ent_count.most_common(28):
        print(u'      %-5s %-18s %4d   %r'
              % (pfx, tok, c, sorted(ent[(pfx, tok)])[:3]))

    # S6：角色判定（**可证伪的判据**）：同一词元出现在 ≥2 个"角色族"里。
    #     理由：道具/背景只会在一个族里出现；角色必然跨"光世界/战斗/立绘"。
    CHAR_FAMS = (u'ioc', u'ibc', u'idc')
    fam_of = defaultdict(set)
    cnt_of = defaultdict(int)
    for n, _, _ in recs:
        pfx, tok = first_token(n)
        if pfx in CHAR_FAMS:
            fam_of[tok].add(pfx)
            cnt_of[tok] += 1
    chars = {tok: {'fams': sorted(f), 'sprites': cnt_of[tok]}
             for tok, f in fam_of.items() if len(f) >= 2}
    lone = {tok: {'fams': sorted(f), 'sprites': cnt_of[tok]}
            for tok, f in fam_of.items() if len(f) == 1}
    print()
    print(u'[S6] ★ 跨 ≥2 个角色族的词元 = 角色，共 %d 个：' % len(chars))
    for tok, v in sorted(chars.items(), key=lambda kv: -kv[1]['sprites'])[:30]:
        print(u'      %-14s 贴图 %3d  族=%r' % (tok, v['sprites'], v['fams']))
    print(u'[S6] 负控制：只出现在**单一**族里的词元 %d 个（多为道具/部位/单场景角色）：'
          % len(lone))
    print(u'      %r' % (sorted(lone, key=lambda k: -lone[k]['sprites'])[:16],))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    art = {
        'source': os.path.basename(p),
        'named_sprite_count': len(recs),
        'image_only_count': len(singles),
        'anchors': {'url_vars': len(url_map), 'unresolved': len(unres),
                    'missing_on_disk': len(miss_file),
                    'stem_mismatch': len(bad_stem),
                    'stem_mismatch_samples': bad_stem,
                    'geom_ok': gok, 'geom_bad': gbad,
                    'geom_bad_samples': gs},
        'name_prefix_top': pref.most_common(30),
        'name_samples_by_prefix': {k: sorted(v) for k, v in by_pref.items()},
        'entities_top': [[k[0], k[1], c] for k, c in ent_count.most_common(200)],
        'characters_multi_family': chars,
        'single_family': lone,
        'named': [{'name': n, 'png': fp, 'json': fj} for n, fp, fj in recs],
        'image_only': [{'name': n, 'png': url_map.get(v)}
                       for n, v in singles if url_map.get(v) in present],
    }
    op = os.path.join(OUT, 'outertale63_assets.json')
    with io.open(op, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(art, ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
