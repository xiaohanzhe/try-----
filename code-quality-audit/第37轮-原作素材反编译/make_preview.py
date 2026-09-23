# -*- coding: utf-8 -*-
"""
第37轮：生成场景背景预览页 + 做完整性/多样性自检。

产物：
  code-quality-audit/第37轮-原作素材反编译/场景背景预览.html
  code-quality-audit/第37轮-原作素材反编译/_evidence/背景自检.txt
"""
import json, os, struct, hashlib, collections, html

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
BG = os.path.join(SCENES, 'bg')
ROUND = os.path.join(REPO, 'code-quality-audit', '第37轮-原作素材反编译')
EVID = os.path.join(ROUND, '_evidence')
MAPJ = os.path.join(EVID, 'scene_bg_mapping.json')

HOW_COLOR = {
    'room.bg_layer':    ('#1a7f37', '#dafbe1'),   # 绿：房间自带真背景
    'room.asset_layer': ('#1a7f37', '#dafbe1'),
    'override':         ('#9a6700', '#fff8c5'),   # 黄：手工指定
    'area_table':       ('#9a6700', '#fff8c5'),   # 黄：区域代表素材
    'chapter_fallback': ('#bc4c00', '#fff1e5'),   # 橙：章节兜底
    'MISS':             ('#cf222e', '#ffebe9'),   # 红：没配上
    'FAIL':             ('#cf222e', '#ffebe9'),
}


def png_dims(p):
    with open(p, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def main():
    man = json.load(open(MAPJ, encoding='utf-8'))
    rows = man['rows']

    # ---------- 自检 ----------
    lines = []
    lines.append('=== 场景背景自检 ===')
    lines.append('总场景 %d  ok=%d  miss=%d' % (man['total'], man['ok'], man['miss']))
    lines.append('')

    idx = json.load(open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    lines.append('=== 逐场景文件核验 ===')
    bad = []
    dims = {}
    hashes = collections.Counter()
    total_bytes = 0
    for r in rows:
        sid = r['scene_id']
        fn = sid.replace('.', '_') + '.png'
        p = os.path.join(BG, fn)
        if not os.path.exists(p):
            bad.append((sid, 'FILE MISSING'))
            lines.append('  [MISS] %-46s %s' % (sid, fn))
            continue
        dm = png_dims(p)
        if not dm:
            bad.append((sid, 'NOT PNG'))
            lines.append('  [BAD ] %-46s 非 PNG' % sid)
            continue
        sz = os.path.getsize(p)
        total_bytes += sz
        dims[sid] = dm
        h = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
        hashes[h] += 1
        lines.append('  [ OK ] %-46s %4dx%-5d %8.1f KB  %-18s %s'
                     % (sid, dm[0], dm[1], sz / 1024, r.get('asset'), r.get('how')))

    lines.append('')
    lines.append('=== 汇总 ===')
    lines.append('文件齐全: %d / %d' % (len(dims), len(rows)))
    lines.append('异常: %d' % len(bad))
    lines.append('总体积: %.1f MB' % (total_bytes / 1048576))
    lines.append('')
    lines.append('=== how 分布 ===')
    howc = collections.Counter(r.get('how') for r in rows)
    for k, v in howc.most_common():
        lines.append('  %-20s %d' % (k, v))
    lines.append('')
    lines.append('=== 图片去重（同图复用）===')
    dup = [(h, c) for h, c in hashes.items() if c > 1]
    lines.append('唯一图片 %d 张；被复用的哈希 %d 组' % (len(hashes), len(dup)))
    # 找出复用最多的
    reuse = collections.Counter()
    for r in rows:
        sid = r['scene_id']
        p = os.path.join(BG, sid.replace('.', '_') + '.png')
        if os.path.exists(p):
            reuse[hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]] += 1
    top = reuse.most_common(8)
    lines.append('复用最多的图片:')
    for h, c in top:
        who = [r['scene_id'] for r in rows
               if os.path.exists(os.path.join(BG, r['scene_id'].replace('.', '_') + '.png'))
               and hashlib.sha256(open(os.path.join(BG, r['scene_id'].replace('.', '_') + '.png'), 'rb').read()).hexdigest()[:16] == h]
        lines.append('  x%-3d %s  -> %s' % (c, h, ', '.join(who[:4]) + (' …' if len(who) > 4 else '')))

    os.makedirs(EVID, exist_ok=True)
    open(os.path.join(EVID, '背景自检.txt'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:40]))

    # ---------- 预览页 ----------
    by_ch = collections.OrderedDict()
    for r in rows:
        by_ch.setdefault(r['chapter'], []).append(r)

    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Deltarune 场景背景预览（第37轮）</title>
<style>
:root{--fg:#1f2328;--mut:#656d76;--bd:#d0d7de;--bg:#ffffff;--card:#f6f8fa;}
*{box-sizing:border-box}
body{margin:0;padding:24px 28px;background:var(--bg);color:var(--fg);
     font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--mut);margin-bottom:18px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}
.stat{border:1px solid var(--bd);border-radius:8px;padding:8px 14px;background:var(--card)}
.stat b{font-size:18px;display:block}
h2{font-size:16px;margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--bd)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{border:1px solid var(--bd);border-radius:8px;overflow:hidden;background:var(--card)}
.thumb{height:150px;background:#fff;display:flex;align-items:center;justify-content:center;
       background-image:linear-gradient(45deg,#eee 25%,transparent 25%,transparent 75%,#eee 75%),linear-gradient(45deg,#eee 25%,transparent 25%,transparent 75%,#eee 75%);
       background-size:16px 16px;background-position:0 0,8px 8px}
.thumb img{max-width:100%;max-height:100%;image-rendering:pixelated;display:block}
.meta{padding:8px 10px;font-size:12px;line-height:1.5}
.meta .sid{font-weight:600;word-break:break-all}
.meta .row{color:var(--mut)}
.tag{display:inline-block;padding:1px 6px;border-radius:10px;font-size:11px;
     border:1px solid currentColor;margin-top:3px}
</style></head><body>""")

    parts.append('<h1>Deltarune 场景背景预览</h1>')
    parts.append('<div class="sub">由五章 <code>data.win</code> 反编译的真实素材组装；'
                 '标注 = 素材来源。<b>绿</b>=房间自带真背景，<b>黄</b>=区域代表素材，'
                 '<b>橙</b>=章节兜底，<b>红</b>=未配上。</div>')

    parts.append('<div class="stats">')
    parts.append('<div class="stat"><b>%d</b>场景</div>' % man['total'])
    parts.append('<div class="stat"><b>%d</b>已配背景</div>' % len(dims))
    parts.append('<div class="stat"><b>%d</b>未配上</div>' % man['miss'])
    parts.append('<div class="stat"><b>%.1f MB</b>总体积</div>' % (total_bytes / 1048576))
    parts.append('</div>')

    for ch, rs in by_ch.items():
        parts.append('<h2>%s（%d 个场景）</h2>' % (html.escape(ch), len(rs)))
        parts.append('<div class="grid">')
        for r in rs:
            sid = r['scene_id']
            fn = sid.replace('.', '_') + '.png'
            p = os.path.join(BG, fn)
            how = r.get('how') or '?'
            col, bgc = HOW_COLOR.get(how, ('#656d76', '#f6f8fa'))
            img = ('<img src="../../ralsei_pet/assets/scenes/bg/%s" alt="">' % fn
                   if os.path.exists(p) else '<span style="color:#cf222e">无图</span>')
            dm = dims.get(sid)
            parts.append(
                '<div class="card"><div class="thumb">%s</div><div class="meta">'
                '<div class="sid">%s</div>'
                '<div class="row">%s · %s</div>'
                '<div class="row">room_id=%s</div>'
                '<div class="row">素材 %s%s</div>'
                '<span class="tag" style="color:%s;background:%s">%s</span>'
                '</div></div>' % (
                    img, html.escape(sid),
                    html.escape(str(r.get('chapter'))), html.escape(str(r.get('area'))),
                    html.escape(str(r.get('room_id'))),
                    html.escape(str(r.get('asset'))),
                    (' · ' + str(dm[0]) + 'x' + str(dm[1])) if dm else '',
                    col, bgc, html.escape(how)))
        parts.append('</div>')

    parts.append('</body></html>')
    outp = os.path.join(ROUND, '场景背景预览.html')
    open(outp, 'w', encoding='utf-8').write('\n'.join(parts))
    print()
    print('preview ->', outp)
    print('evidence ->', os.path.join(EVID, '背景自检.txt'))


if __name__ == '__main__':
    main()
