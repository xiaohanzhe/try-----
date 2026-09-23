# -*- coding: utf-8 -*-
"""事实核查：87 锚点背景的真实状态（映射表 vs 磁盘 vs JSON 注释）。只读。"""
import io, os, sys, json, struct

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
BG = os.path.join(SCENES, 'bg')
MAP = os.path.join(REPO, 'code-quality-audit', '第37轮-原作素材反编译', '_evidence',
                   'scene_bg_mapping_final.json')


def dims(p):
    try:
        with open(p, 'rb') as f:
            h = f.read(24)
        if len(h) < 24 or h[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        return struct.unpack('>II', h[16:24])
    except Exception:
        return None


m = json.load(open(MAP, encoding='utf-8'))
rows = m['rows']
print('映射表 total=%s ok=%s exists=%s miss=%s err=%s copy=%s tile=%s'
      % (m['total'], m['ok'], m['exists'], m['miss'], m['err'], m['copied'], m['composed']))
print('meta: min_real_bg=%s canvas_width=%s' % (m.get('min_real_bg'), m.get('canvas_width')))

print('\n' + '=' * 76)
print('A. 9 个"房间自带真背景"的锚点')
print('=' * 76)
used = {}
for r in rows:
    used.setdefault(r['asset'], []).append(r['scene_id'])
real = [r for r in rows if r['how'] == 'room.bg_layer']
for r in real:
    p = os.path.join(BG, r['file'])
    print('  %-44s asset=%-42s disk=%s dims=%s' % (
        r['scene_id'], r['asset'], os.path.isfile(p), dims(p) if os.path.isfile(p) else '-'))

print('\n' + '=' * 76)
print('B. bg/ 目录里是否有"孤儿"文件（未被任何 row 引用）')
print('=' * 76)
referenced = set(r['file'] for r in rows if r.get('file'))
on_disk = set(os.listdir(BG))
print('  bg/ 项数 = %d，映射表引用 %d' % (len(on_disk), len(referenced)))
print('  孤儿 = %s' % sorted(on_disk - referenced))
print('  缺失 = %s' % sorted(referenced - on_disk))

print('\n' + '=' * 76)
print('C. 被复用的素材（同一 asset 供多个场景 = 近似档的特征）')
print('=' * 76)
for a, sids in sorted(used.items(), key=lambda kv: -len(kv[1]))[:10]:
    print('  %-46s %3d 个场景' % (a, len(sids)))

print('\n' + '=' * 76)
print('D. 锚点 JSON 里的 _comment 是否已过期（第37轮无法覆写）')
print('=' * 76)
stale = 0
checked = 0
for r in rows[:6]:
    p = os.path.join(SCENES, r['scene_id'] + '.json')
    if not os.path.isfile(p):
        print('  !! 缺 %s' % p)
        continue
    d = json.load(open(p, encoding='utf-8'))
    cm = d.get('_comment') or {}
    txt = str(cm.get('why_bg_is_a_placeholder', ''))
    checked += 1
    if '尚不存在' in txt:
        stale += 1
    print('  %-42s bg=%-40s 注释说"尚不存在"=%s' % (
        r['scene_id'], d.get('bg'), '尚不存在' in txt))
print('  ...（抽查 %d 个，其中注释过期 %d 个）' % (checked, stale))

print('\n' + '=' * 76)
print('E. 分片 JSON 的原始格式（缩进 / EOL / BOM）')
print('=' * 76)
z = os.path.join(SCENES, '_zone.ch1.card_castle.json')
raw = open(z, 'rb').read()
print('  文件 = %s  %d B' % (os.path.basename(z), len(raw)))
print('  前 3 字节 = %s（BOM? %s）' % (raw[:3], raw[:3] == b'\xef\xbb\xbf'))
print('  CRLF 计数 = %d，LF 总数 = %d' % (raw.count(b'\r\n'), raw.count(b'\n')))
print('  前 200 字节 repr = %r' % raw[:200])
