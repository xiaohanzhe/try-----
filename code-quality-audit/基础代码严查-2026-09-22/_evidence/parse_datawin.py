# -*- coding: utf-8 -*-
"""GEN8 data.win 解析器 v3：单遍扫描（避免逐字节×31 标签的重扫被守卫误杀）。

要点：
  · 只做一次 bytes.find 定位各标签，不做 31 次 ×14MB 的逐字节比对。
  · 输出落盘即 flush，避免长任务被截断。
"""
import os
import struct
import json
import sys

DATA = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密\DELTARUNE_183049\DELTARUNE'

TAGS = [b'GEN8', b'OPTN', b'LANG', b'EXTN', b'SONG', b'AGRP', b'SPRT', b'BGND',
        b'PATH', b'SCPT', b'SHDR', b'FONT', b'TMLN', b'OBJT', b'ROOM', b'DAFL',
        b'TPAG', b'CODE', b'VARI', b'FUNC', b'STRG', b'TXTR', b'TGIN', b'ACRV',
        b'UILR', b'EMBI', b'SEQN', b'SPT2', b'AUDO', b'MALI']


def find_chunks(buf):
    """用 bytes.find 定位每个标签，再贪心选出互不重叠、能串起来的链。"""
    cands = []
    for t in TAGS:
        p = 8
        while True:
            i = buf.find(t, p)
            if i < 0:
                break
            if i + 8 <= len(buf):
                size = struct.unpack_from('<I', buf, i + 4)[0]
                if 0 <= size <= len(buf):
                    cands.append((i, t.decode('latin1'), size))
            p = i + 1
    cands.sort()
    # 从 @8 的 GEN8 开始，贪心串链
    chain = []
    pos = 8
    while True:
        nxt = [c for c in cands if c[0] == pos]
        if not nxt:
            nxt = [c for c in cands if c[0] > pos]
            if not nxt:
                break
            chain.append(('gap', nxt[0][0] - pos))
            pos = nxt[0][0]
            continue
        off, tag, size = nxt[0]
        chain.append((off, tag, size))
        pos = off + 8 + size
    return [c for c in chain if c[0] != 'gap']


class R:
    def __init__(self, buf, pos=0):
        self.b = buf
        self.p = pos

    def u32(self):
        v = struct.unpack_from('<I', self.b, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        v = struct.unpack_from('<i', self.b, self.p)[0]
        self.p += 4
        return v

    def string(self):
        n = self.u32()
        s = self.b[self.p:self.p + n]
        self.p += n
        return s.decode('utf-8', 'surrogateescape')


def ptr_table(buf, off):
    r = R(buf, off + 8)
    n = r.u32()
    ptrs = [r.u32() for _ in range(n)]
    base = r.p
    return base, ptrs


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        DATA, 'chapter1_windows', 'data.win')
    buf = open(target, 'rb').read()
    print('parsing:', target, '(%d B)' % len(buf), flush=True)

    chunks = find_chunks(buf)
    print('\n=== chunks ===', flush=True)
    for c in chunks:
        print('  @%-10d %-6s %d' % c, flush=True)

    by_tag = {}
    for c in chunks:
        by_tag[c[1]] = c

    strings = []
    if 'STRG' in by_tag:
        off = by_tag['STRG'][0]
        base, ptrs = ptr_table(buf, off)
        for p in ptrs:
            strings.append(R(buf, base + p).string())
    print('\nstrings:', len(strings), flush=True)

    out = {'source': target, 'chunks': chunks, 'rooms': [], 'sprites': [],
           'objects': [], 'strings': strings}

    def sp_reader(q):
        name = q.string()
        w = q.u32(); h = q.u32()
        q.i32(); q.i32(); q.i32(); q.i32()
        q.u32(); q.u32()
        ox = q.i32(); oy = q.i32()
        ntex = q.u32()
        for _ in range(ntex):
            q.u32()
        return {'name': name, 'w': w, 'h': h, 'frames': ntex, 'ox': ox, 'oy': oy}

    def ob_reader(q):
        name = q.string()
        spr = q.i32(); vis = q.i32(); solid = q.i32(); depth = q.i32()
        q.i32(); parent = q.i32(); q.i32()
        return {'name': name, 'sprite': spr, 'visible': vis, 'solid': solid,
                'depth': depth, 'parent': parent}

    def rm_reader(q):
        name = q.string()
        caption = q.string()
        q.string(); q.string()
        w = q.u32(); h = q.u32()
        speed = q.u32(); persist = q.u32()
        return {'name': name, 'caption': caption, 'w': w, 'h': h, 'speed': speed}

    SPEC = {'SPRT': (sp_reader, 'sprites'), 'OBJT': (ob_reader, 'objects'),
            'ROOM': (rm_reader, 'rooms')}
    for tag, (reader, key) in SPEC.items():
        if tag not in by_tag:
            continue
        try:
            base, ptrs = ptr_table(buf, by_tag[tag][0])
            out[key] = [reader(R(buf, base + p)) for p in ptrs]
        except Exception as e:
            print('%s parse error: %r' % (tag, e), flush=True)

    print('\nrooms: %d | sprites: %d | objects: %d'
          % (len(out['rooms']), len(out['sprites']), len(out['objects'])), flush=True)

    print('\n=== rooms (first 45) ===', flush=True)
    for x in out['rooms'][:45]:
        print('  %-30s %5dx%-5d' % (x['name'], x['w'], x['h']), flush=True)

    rs = [s for s in out['sprites'] if 'ralsei' in s['name'].lower()]
    print('\nralsei sprites: %d' % len(rs), flush=True)
    for s in rs[:30]:
        print('  %-46s %4dx%-4d frames=%d' % (s['name'], s['w'], s['h'], s['frames']), flush=True)

    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datawin_index.json')
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nwrote:', dst, os.path.getsize(dst), 'B', flush=True)


if __name__ == '__main__':
    main()
