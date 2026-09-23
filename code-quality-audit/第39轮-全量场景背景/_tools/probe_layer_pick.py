# -*- coding: utf-8 -*-
"""量化"取第一个 bg_sprite 层"是否有选错层的风险（只读）。"""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_common as C

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
EV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_evidence')
man = json.load(io.open(os.path.join(EV, '真背景导出清单.json'), encoding='utf-8'))
rooms = C.load_rooms()
inv = C.load_assets(rooms)


def area(ch, nm):
    if nm in (inv.get(ch) or {}):
        w, h = inv[ch][nm][1]
        return w * h
    return 0


print('=' * 78)
print('A. 真背景房间里"有几个 bg_sprite 层"')
print('=' * 78)
multi = []
for r in man['rows']:
    ch, rid = r['chapter'], r['room_id']
    room = (rooms.get(ch) or {}).get(rid) or {}
    bgs = [ly.get('bg_sprite') for ly in (room.get('layers') or [])
           if ly.get('bg_sprite') and ly.get('bg_sprite') != 'UndertaleSprite']
    r['_nbglayer'] = len(bgs)
    r['_bgs'] = bgs
    if len(bgs) > 1:
        multi.append(r)
print('   真背景场景 %d 个；其中房间有 >1 个 bg 层的 = %d' % (len(man['rows']), len(multi)))
for r in multi[:12]:
    print('   %-44s 层数=%d 取到=%s' % (r['scene_id'], r['_nbglayer'], r['asset']))
    for b in r['_bgs']:
        print('        %-34s 面积=%9d  %s' % (b, area(r['chapter'], b),
                                              '← 本次取此' if b == r['asset'] else ''))

print('')
print('=' * 78)
print('B. 本次取到的层 vs 该房间最大 bg 层：取小了的有多少')
print('=' * 78)
small = []
for r in man['rows']:
    a_used = area(r['chapter'], r['asset'])
    a_max = max([area(r['chapter'], b) for b in r['_bgs']] or [0])
    if a_max and a_used < a_max:
        small.append((a_used / float(a_max), r, a_used, a_max))
small.sort()
print('   取到的不是最大层 的场景 = %d / %d' % (len(small), len(man['rows'])))
for ratio, r, au, am in small[:15]:
    print('   %.2f  %-44s 取 %-30s(%d) 最大 %s' % (
        ratio, r['scene_id'], r['asset'], au,
        [b for b in r['_bgs'] if area(r['chapter'], b) == am]))

print('')
print('=' * 78)
print('C. 取到的层宽 / 房间宽 < 0.5 的（疑似"大号装饰"而非整幅背景）')
print('=' * 78)
narrow = [r for r in man['rows']
          if r.get('room_w') and r['src_dims'][0] / float(r['room_w']) < 0.5]
print('   共 %d 个：' % len(narrow))
for r in narrow:
    print('   %-44s 素材 %sx%s 房间 %sx%s 素材名 %s' % (
        r['scene_id'], r['src_dims'][0], r['src_dims'][1],
        r.get('room_w'), r.get('room_h'), r['asset']))
