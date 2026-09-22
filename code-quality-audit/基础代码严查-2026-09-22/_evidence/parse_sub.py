# -*- coding: utf-8 -*-
"""GEN8 子表解析 v2：带健全性校验，绝不写出畸形数据。

v1 事故留档（2026-09-22，第 32 轮）：
  我对 GE8 的 string 长度字段做了错误假设 —— 某些名字前 4 字节被当成 u32 长度，
  读到 40 亿级别的值，`json.dumps` 于是产出 **4.29 GB 的 ROOM.json**。
  ⇒ 铁律：**任何来自二进制的长度/偏移量都必须先做上界校验**；
     解析结果落盘前必须做**体量合理性断言**（本表行数 × 单行上限）。

校验规则：
  · string 长度 > MAX_STR(512) ⇒ 该字段判为「布局不符」，放弃该项，不猜。
  · 指针必须落在 chunk 内 [0, size] ⇒ 否则放弃该项。
  · 结果 JSON 落盘前断言 size < 8 MB。
"""
import os
import struct
import json
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密\DELTARUNE_183049\DELTARUNE'
MAX_STR = 512
MAX_JSON = 8 * 1024 * 1024


def find_chunk(buf, tag):
    p = 8
    target = tag.encode('latin1')
    while True:
        i = buf.find(target, p)
        if i < 0:
            return None
        size = struct.unpack_from('<I', buf, i + 4)[0]
        if 0 <= size <= len(buf) and i + 8 + size <= len(buf):
            return i, size
        p = i + 1


class R:
    def __init__(self, buf, pos=0, limit=None):
        self.b = buf
        self.p = pos
        self.limit = limit if limit is not None else len(buf)

    def ok(self, n):
        return self.p + n <= self.limit

    def u32(self):
        if not self.ok(4):
            raise EOFError('u32 out of chunk')
        v = struct.unpack_from('<I', self.b, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        if not self.ok(4):
            raise EOFError('i32 out of chunk')
        v = struct.unpack_from('<i', self.b, self.p)[0]
        self.p += 4
        return v

    def string(self):
        n = self.u32()
        if n > MAX_STR:
            raise ValueError('implausible string len=%d' % n)
        if not self.ok(n):
            raise EOFError('string body out of chunk')
        s = self.b[self.p:self.p + n]
        self.p += n
        try:
            return s.decode('utf-8')
        except UnicodeDecodeError:
            return s.decode('utf-8', 'replace')


def ptr_table(buf, off, size):
    lim = off + 8 + size
    r = R(buf, off + 8, lim)
    n = r.u32()
    if n > 200000:
        raise ValueError('implausible count=%d' % n)
    ptrs = [r.u32() for _ in range(n)]
    return r.p, ptrs, lim


def parse_names(buf, off, size):
    """只取「每项第一个 string」= 名字。安全、够用。"""
    base, ptrs, lim = ptr_table(buf, off, size)
    res = []
    bad = 0
    for p in ptrs:
        try:
            res.append(R(buf, base + p, lim).string())
        except Exception:
            bad += 1
            res.append(None)
    return {'names': res, 'bad': bad}


def parse_sprt(buf, off, size):
    base, ptrs, lim = ptr_table(buf, off, size)
    res = []
    bad = 0
    for p in ptrs:
        try:
            q = R(buf, base + p, lim)
            name = q.string()
            w = q.u32(); h = q.u32()
            q.i32(); q.i32(); q.i32(); q.i32()
            q.u32(); q.u32()
            ox = q.i32(); oy = q.i32()
            ntex = q.u32()
            if ntex > 2000:
                raise ValueError('implausible ntex=%d' % ntex)
            for _ in range(ntex):
                q.u32()
            res.append({'name': name, 'w': w, 'h': h, 'frames': ntex,
                        'ox': ox, 'oy': oy})
        except Exception:
            bad += 1
    return {'rows': res, 'bad': bad}


def parse_objt(buf, off, size):
    base, ptrs, lim = ptr_table(buf, off, size)
    res = []
    bad = 0
    for p in ptrs:
        try:
            q = R(buf, base + p, lim)
            name = q.string()
            spr = q.i32(); vis = q.i32(); solid = q.i32(); depth = q.i32()
            q.i32(); parent = q.i32(); q.i32()
            res.append({'name': name, 'sprite': spr, 'visible': vis,
                        'solid': solid, 'depth': depth, 'parent': parent})
        except Exception:
            bad += 1
    return {'rows': res, 'bad': bad}


def parse_strg(buf, off, size):
    base, ptrs, lim = ptr_table(buf, off, size)
    res = []
    bad = 0
    for p in ptrs:
        try:
            res.append(R(buf, base + p, lim).string())
        except Exception:
            bad += 1
    return {'rows': res, 'bad': bad}


PARSERS = {'SPRT': parse_sprt, 'OBJT': parse_objt, 'STRG': parse_strg,
           'ROOM': parse_names, 'BGND': parse_names, 'FONT': parse_names,
           'SCPT': parse_names, 'FUNC': parse_names, 'TPAG': parse_names}


def main():
    tag = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        DATA, 'chapter1_windows', 'data.win')
    buf = open(path, 'rb').read()
    loc = find_chunk(buf, tag)
    if not loc:
        print('chunk %s not found' % tag)
        return 1
    off, size = loc
    print('%s @%d size=%d' % (tag, off, size), flush=True)
    out = PARSERS[tag](buf, off, size)
    print('rows=%d bad=%d' % (len(out.get('rows', out.get('names', []))), out['bad']),
          flush=True)
    dst = os.path.join(HERE, tag + '.json')
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    data = txt.encode('utf-8', 'backslashreplace')
    assert len(data) < MAX_JSON, 'JSON too big: %d B — 解析布局可疑，拒绝落盘' % len(data)
    with open(dst, 'wb') as f:
        f.write(data)
    print('wrote:', dst, len(data), 'B', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
