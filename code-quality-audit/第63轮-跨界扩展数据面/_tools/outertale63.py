#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第63轮 · 扩展线①：outertale 素材/角色精确提取。

设计要点（按项目铁律）
--------------------
1. **能实测就实测、能上锚点就上锚点**：先定"可证伪的锚点"，锚点全命中才往下用。
   - 锚点 A：1066 个 Aseprite `.json` 的 `meta.image` 指向的 `.png` **必须全部存在**
     （若解析对了 ⇒ 100% 命中；若解析错了 ⇒ 立刻大面积 MISS）。
   - 锚点 B：json 里的 `frames[].filename` 应形如 `<stem> <n>.aseprite`（Aseprite 惯例）。
   - 锚点 C：区域名（第61轮 §57.6 已记录）必须能从文件名里复现出来。
2. **"提取成功"≠"提取正确"**：所以锚点 A/B 是"结构自洽"，锚点 C 是"与已记录事实对上"。
3. 零依赖：只用标准库。

用法：
  C:\\Python311\\python.exe -X utf8 outertale63.py --recon
  C:\\Python311\\python.exe -X utf8 outertale63.py --run
"""
import io
import json
import os
import re
import sys

WWW = u'E:\\Download\\_extract61\\outertale\\www'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
OUT = os.path.join(ROUND, '_evidence')

#: 锚点 C：第61轮 §57.6 已记录的区域名（从素材文件名读出的既有事实）
ZONES_KNOWN = [u'town', u'archive', u'foundry', u'frontier', u'aerialis',
               u'core', u'CryptOfTomorrow']
#: 锚点 C'：第61轮 §57.6 已记录的角色名
CHARS_KNOWN = [u'pap', u'toriel', u'undyne', u'Napster', u'DeterminationSans',
               u'krios', u'kittyemu2']


def rd(p):
    return io.open(p, 'rb').read()


def txt(p, enc='utf-8'):
    return rd(p).decode(enc, 'replace')


def survey():
    u"""E1：目录普查（按扩展名分类）。"""
    names = sorted(os.listdir(WWW))
    by_ext = {}
    stems = {}
    for n in names:
        ext = os.path.splitext(n)[1].lower()
        by_ext.setdefault(ext, []).append(n)
        if ext in ('.json', '.png', '.csv'):
            stem = n.rsplit(u'-', 1)[0]
            stems.setdefault(stem, set()).add(ext)
    return names, by_ext, stems


def png_size(p):
    u"""读 PNG 头部 IHDR 的真实宽高（零依赖）。"""
    b = rd(p)[:26]
    if len(b) < 24 or b[:8] != b'\x89PNG\r\n\x1a\n' or b[12:16] != b'IHDR':
        return None
    return (int(b[16:20].hex(), 16), int(b[20:24].hex(), 16))


def pair_check(names):
    u"""锚点 A/B：json ↔ png 的**语义**配对。

    ★ 第一版我按"文件名精确相等 / Aseprite `<name> N.aseprite` 惯例"断言 —— 全 MISS。
      真相：Vite 给文件名加了内容哈希（`AYAYA-<hash>.png`），而 `meta.image` 是**逻辑名**
      （`AYAYA.png`）；导出器把 `frames[].filename` 写成 `"0","1"`。
      ⇒ 换成**语义锚点**：`meta.size` 必须等于同名 PNG 头部 IHDR 的真实尺寸。
      这条能证伪"我配错了 png"，比名字匹配强得多。
    """
    import re as _re
    png_by_stem = {}
    for n in names:
        if n.lower().endswith(u'.png'):
            png_by_stem.setdefault(n.rsplit(u'-', 1)[0], []).append(n)
    ok_img = miss_img = 0
    geom_ok = geom_bad = 0
    bad_geom = []
    stem_bad = []
    j_sizes = 0
    j_meta_ok = 0
    j_frames_ovf = 0
    total_frames = 0
    for n in sorted(names):
        if not n.lower().endswith(u'.json'):
            continue
        j_stem = n.rsplit(u'-', 1)[0]
        try:
            d = json.loads(txt(os.path.join(WWW, n)))
        except Exception:
            miss_img += 1
            continue
        meta = d.get(u'meta') or {}
        img = meta.get(u'image') or u''
        img_stem = os.path.splitext(img)[0]
        if img_stem == j_stem and png_by_stem.get(j_stem):
            ok_img += 1
        else:
            miss_img += 1
            if len(stem_bad) < 8:
                stem_bad.append((n, img, sorted(png_by_stem.get(j_stem) or [])[:2]))
        # 语义锚点：meta.size == PNG IHDR
        sz = meta.get(u'size') or {}
        cand = png_by_stem.get(j_stem) or []
        real = None
        for c in cand:
            real = png_size(os.path.join(WWW, c))
            if real:
                break
        if isinstance(sz.get(u'w'), int) and isinstance(sz.get(u'h'), int) and real:
            j_sizes += 1
            if (sz[u'w'], sz[u'h']) == real:
                geom_ok += 1
            else:
                geom_bad += 1
                if len(bad_geom) < 5:
                    bad_geom.append((n, (sz[u'w'], sz[u'h']), real))
        # 帧必须落在 meta.size 内（几何自洽）
        fr = d.get(u'frames') or []
        for f in fr:
            total_frames += 1
            fo = f.get(u'frame') or {}
            if not (all(isinstance(fo.get(k), int) for k in (u'x', u'y', u'w', u'h'))):
                continue
            if isinstance(sz.get(u'w'), int):
                if fo[u'x'] + fo[u'w'] > sz[u'w'] or fo[u'y'] + fo[u'h'] > sz[u'h']:
                    j_frames_ovf += 1
    return {
        'json_total': ok_img + miss_img,
        'stem_match': ok_img, 'stem_mismatch': miss_img,
        'stem_mismatch_samples': stem_bad,
        'geom_checked': j_sizes, 'geom_ok': geom_ok, 'geom_bad': geom_bad,
        'geom_bad_samples': bad_geom,
        'frames_total': total_frames, 'frames_out_of_bounds': j_frames_ovf,
        'png_stems': len(png_by_stem),
    }


def recon_zones(stems):
    u"""锚点 C：可见区域前缀。"""
    hits = {}
    for z in ZONES_KNOWN:
        zl = z.lower()
        n = sum(1 for s in stems if s.lower().split(u'-')[0].split(u'_')[0] == zl
                or s.lower().startswith(zl))
        hits[z] = n
    return hits


def recon_js():
    u"""侦察 index.js：找可用的角色/区域/场景表。"""
    js = [f for f in os.listdir(WWW)
          if f.lower().startswith(u'index-') and f.lower().endswith(u'.js')]
    if not js:
        return {'found': False}
    p = os.path.join(WWW, js[0])
    raw = rd(p)
    t = raw.decode('utf-8', 'replace')
    out = {'found': True, 'file': js[0], 'bytes': len(raw),
           'lines': t.count(u'\n') + 1}
    probes = {}
    for key in (u'characters', u'character', u'zones', u'zone', u'scenes',
                u'scene', u'spr_', u'assets', u'rooms', u'manifest',
                u'__vite', u'import(', u'from"', u'\u89d2\u8272'):
        probes[key] = t.count(key)
    out['probes'] = probes
    # 角色名在 js 里是否可查（锚点 C'）
    out['chars_in_js'] = {c: t.count(c) for c in CHARS_KNOWN}
    # 找形如 {"name":"xxx",...} 的对象键名样本
    keys = re.findall(u'[{,]"([a-zA-Z_][a-zA-Z0-9_]{2,24})":', t)
    freq = {}
    for k in keys:
        freq[k] = freq.get(k, 0) + 1
    top = sorted(freq.items(), key=lambda kv: -kv[1])[:40]
    out['top_object_keys'] = top
    out['distinct_keys'] = len(freq)
    return out


def stems_stats(stems):
    u"""E4：把 1887 个 stem 按"首词"归类（首词 = 按 - 或 _ 或驼峰前段切）。

    ★ 只统计、不下结论：out ertale 的资源名混了 区域/角色/道具/特效/子弹，
      先用**频次**把"疑似角色/区域"的候选捞出来，再人工（我）判。
    """
    first = {}
    for s in stems:
        t = re.split(u'[-_]', s)[0]
        first[t] = first.get(t, 0) + 1
    top = sorted(first.items(), key=lambda kv: (-kv[1], kv[0]))
    return {'distinct_first': len(first), 'top': top[:120]}


def main():
    if not os.path.isdir(WWW):
        print(u'!! www 不存在：%s' % WWW)
        return 2
    names, by_ext, stems = survey()
    print(u'[E1] 文件 %d 个' % len(names))
    for e in sorted(by_ext, key=lambda k: -len(by_ext[k])):
        print(u'      %-10s %5d' % (e or u'(无扩展名)', len(by_ext[e])))
    print(u'[E1] 去扩展名后的 stem 数 = %d' % len(stems))

    if '--recon' in sys.argv:
        print()
        print(u'[E2 锚点 C] 区域前缀命中：')
        for k, v in recon_zones(stems).items():
            print(u'      %-18s %5d' % (k, v))
        print()
        print(u'[E3 侦察] index.js：')
        r = recon_js()
        for k, v in r.items():
            print(u'      %s = %r' % (k, v))
        return 0

    pc = pair_check(names)
    print()
    print(u'[E2 锚点 A] json=%d；stem==meta.image 且存在同名 png 的 = %d（不符 %d）'
          % (pc['json_total'], pc['stem_match'], pc['stem_mismatch']))
    print(u'[E2 锚点 A2 语义] meta.size 与 PNG IHDR 逐条比对：检查 %d 条，'
          u'一致 %d，不一致 %d'
          % (pc['geom_checked'], pc['geom_ok'], pc['geom_bad']))
    print(u'      不一致样本=%r' % (pc['geom_bad_samples'][:3],))
    print(u'      （另有 %d 条 json 找不到同名 png 或 stem 不符，样本见证据）'
          % pc['stem_mismatch'])
    print(u'[E2 锚点 B] frames 总数=%d，越出 meta.size 边界的帧=%d'
          % (pc['frames_total'], pc['frames_out_of_bounds']))
    print()
    print(u'[E3 锚点 C] 区域前缀命中：')
    zs = recon_zones(stems)
    for k, v in zs.items():
        print(u'      %-18s %5d  %s' % (k, v, u'OK' if v else u'**未命中**'))

    ss = stems_stats(stems)
    print(u'[E4] 首词种类=%d；Top20：' % ss['distinct_first'])
    for k, v in ss['top'][:20]:
        print(u'      %-24s %4d' % (k, v))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    ev = {'e1_by_ext': {k: len(v) for k, v in by_ext.items()},
          'e1_total': len(names), 'e1_stems': len(stems),
          'e2_pair': pc, 'e3_zones': zs,
          'e4_first_token_top': ss['top'], 'e4_distinct_first': ss['distinct_first'],
          'e1_stem_list': sorted(stems)}
    p = os.path.join(OUT, 'outertale63_recon.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
