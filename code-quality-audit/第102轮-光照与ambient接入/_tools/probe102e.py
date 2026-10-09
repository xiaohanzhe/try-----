# -*- coding: utf-8 -*-
u"""probe102e.py —— 第102轮侦察 5：证伪/证真「`mapColors` 是不是小地图颜色」。

 Q1 `oneshot_map_colors.json` 全文（只有 2,868 字节）
 Q2 `oneshot_minimap_info.json` / `oneshot_minimap_nodes.json` 结构
 Q3 `OneShotMG.exe` 里 `mapColors` / `minimap` 的用法线索
 Q4 `autotiles/black.xnb` 解出来到底是什么（不透明黑？还是暗色纹理？）
 Q5 交叉：map2（尼可的家，瓦片基本铺满）与 map20（basement，1575 块黑）各自的底色
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
GD = os.path.join(o.OSD, 'gamedata')


def j(n):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(os.path.join(GD, n), encoding='utf-8', newline='').read()))


print('=' * 78)
print('Q1 oneshot_map_colors.json 全文')
print('=' * 78)
raw = io.open(os.path.join(GD, 'oneshot_map_colors.json'), encoding='utf-8', newline='').read()
print(raw[:1200])
print('  ... [全文 %d 字节]' % len(raw))
d = j('oneshot_map_colors.json')
print('  顶层键 =', list(d.keys()))
c0 = d['mapColors']
print('  mapColors 条目数 =', len(c0))
print('  前 6 条 =', json.dumps(c0[:6], ensure_ascii=False))

print()
print('=' * 78)
print('Q2 minimap 两个 json')
print('=' * 78)
for n in ['oneshot_minimap_info.json', 'oneshot_minimap_nodes.json']:
    dd = j(n)
    print('--- %s  顶层键 = %s' % (n, list(dd.keys())))
    s = json.dumps(dd, ensure_ascii=False)
    print('   %s' % s[:600])
    print('   [全文 %d 字节]' % len(s))
    for k, v in dd.items():
        if isinstance(v, list) and v:
            print('   %s[0] = %s' % (k, json.dumps(v[0], ensure_ascii=False)[:300]))

print()
print('=' * 78)
print('Q3 OneShotMG.exe 里的线索')
print('=' * 78)
exe = open(os.path.join(o.OSD, 'OneShotMG.exe'), 'rb').read()
strs = set()
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){3,}', exe):
    try:
        strs.add(m.group().decode('utf-16-le'))
    except Exception:
        pass
for k in ['mapColors', 'map_colors', 'minimap', 'Minimap', 'MiniMap',
          'mapNames', 'map_names', 'color']:
    v = sorted(x for x in strs if k in x)
    print('   %-14s %d 条 %s' % (k, len(v), v[:5]))

print()
print('=' * 78)
print('Q4 autotiles/black.xnb / blank.xnb 解出来是什么')
print('=' * 78)
for name in ['black', 'blank', 'blank2']:
    tsx = os.path.join(GD, 'autotiles', name + '.tsx')
    if not os.path.isfile(tsx):
        print('   %s.tsx 不存在' % name)
        continue
    t = o.parse_tsx(tsx)
    ip = o.resolve_img(os.path.dirname(tsx), t['img'])
    im = o.xnb_rgba(ip) if ip else None
    if im is None:
        print('   %-8s img=%s  解码失败' % (name, t['img']))
        continue
    px = list(im.getdata())
    cc = collections.Counter(px)
    print('   %-8s img=%-34s size=%s 颜色种类=%d 前3=%s'
          % (name, t['img'], im.size, len(cc), cc.most_common(3)))

print()
print('=' * 78)
print('Q5 交叉：几个房间的底色 vs 瓦片铺满度')
print('=' * 78)
colors = o.load_map_colors()
for n in (2, 20, 63, 8, 67, 103, 165, 10):
    m = o.parse_map(os.path.join(o.MAPS, 'map%d.tmx' % n))
    tot = sum(len(g) for _, g in m['layers'])
    nz = sum(sum(1 for g in g if g > 0) for _, g in m['layers'])
    print('   map%-4d 底色=%-22s 瓦片 %d/%d (%.0f%%)'
          % (n, colors.get(n, 'None'), nz, tot, 100.0 * nz / tot))
