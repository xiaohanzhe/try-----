# -*- coding: utf-8 -*-
"""OneShot（MonoGame）`.xnb` -> PNG 最小解析器。

XNB 格式（本项目只用得上 Texture2D）：
  'XNB' + platform(1) + version(1) + flags(1) + fileSize(4, LE)
  flags: 0x01=HiDef, 0x80=LZ4, 0x40=LZMA（本次实测 OneShot 全是 0x00 = 未压缩）
  content = 7bit(len) 读取器数 + 每个读取器名(7bit 长度 + UTF8)
            + 7bit 共享资源数 + 主对象(7bit 类型索引 + 数据)
  Texture2D 数据 = format(int32) + width(uint32) + height(uint32) + mipCount(uint32)
                   + 每个 mip: size(uint32) + bytes
"""
import io
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                   # noqa: E402

C = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
     r'\OneShot.World.Machine.Edition.Build.16512634\content')
OUT = r'E:\Download\_tmp\xnb_out'
os.makedirs(OUT, exist_ok=True)


def rd7(b, i):
    """7-bit encoded int（.NET BinaryReader.Read7BitEncodedInt）。"""
    r = 0
    s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not (x & 0x80):
            return r, i
        s += 7


def rds(b, i):
    """7-bit 长度前缀的 UTF-8 字符串。"""
    n, i = rd7(b, i)
    return b[i:i + n].decode('utf-8', 'replace'), i + n


def read_xnb(path):
    b = open(path, 'rb').read()
    if b[:3] != b'XNB':
        raise ValueError('不是 XNB')
    platform = b[3:4]
    ver, flags = b[4], b[5]
    fsize = struct.unpack('<I', b[6:10])[0]
    i = 10
    if flags & 0x80:
        raise ValueError('LZ4 压缩，本脚本未实现')
    if flags & 0x40:
        raise ValueError('LZMA 压缩，本脚本未实现')
    nreaders, i = rd7(b, i)
    readers = []
    for _ in range(nreaders):
        nm, i = rds(b, i)
        readers.append(nm)
        _ver, i = struct.unpack('<i', b[i:i + 4])[0], i + 4
    nshared, i = rd7(b, i)
    typeidx, i = rd7(b, i)
    fmt, w, h, mips = struct.unpack('<iIII', b[i:i + 16])
    i += 16
    data = None
    for m in range(mips):
        sz = struct.unpack('<I', b[i:i + 4])[0]
        i += 4
        if m == 0:
            data = b[i:i + sz]
        i += sz
    return dict(platform=platform, ver=ver, flags=flags, size=fsize,
                readers=readers, fmt=fmt, w=w, h=h, mips=mips, data=data)


FMT = {0: 'Color', 1: 'Bgr565', 2: 'Bgra5551', 3: 'Bgra4444', 4: 'Dxt1',
       5: 'Dxt3', 6: 'Dxt5', 7: 'NormalizedByte2', 8: 'NormalizedByte4',
       9: 'Rgba1010102', 10: 'Rg32', 11: 'Rgba64', 12: 'Alpha8',
       13: 'Single', 14: 'Vector2', 15: 'Vector4', 16: 'HalfSingle',
       17: 'HalfVector2', 18: 'HalfVector4', 19: 'HdrBlendable',
       20: 'ColorBgraEXT', 21: 'ColorSrgbEXT'}

TARGETS = [
    r'npc\DOORS.xnb', r'npc\DOORS2.xnb', r'npc\door_automatic.xnb',
    r'npc\door_light.xnb', r'npc\door_portal.xnb', r'npc\tv_door.xnb',
    r'npc\countdown_door.xnb', r'facepics\niko.xnb', r'pictures\b0.xnb',
]

for rel in TARGETS:
    p = os.path.join(C, rel)
    print('=' * 70)
    print(rel, os.path.getsize(p) if os.path.isfile(p) else 'MISSING')
    if not os.path.isfile(p):
        continue
    try:
        d = read_xnb(p)
    except Exception as e:
        print('   解析失败:', repr(e))
        continue
    print('   platform=%r ver=%d flags=0x%02x %dx%d mips=%d fmt=%s(%d)'
          % (d['platform'], d['ver'], d['flags'], d['w'], d['h'], d['mips'],
             FMT.get(d['fmt'], '?'), d['fmt']))
    print('   readers=%s' % (d['readers'][:3],))
    if d['fmt'] != 0 or d['data'] is None:
        print('   （非 Color 格式，跳过导出）')
        continue
    img = Image.frombytes('RGBA', (d['w'], d['h']), d['data'][:d['w'] * d['h'] * 4])
    name = os.path.splitext(os.path.basename(rel))[0] + '.png'
    img.save(os.path.join(OUT, name))
    print('   已导出 ->', os.path.join(OUT, name))
