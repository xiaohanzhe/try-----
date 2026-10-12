# -*- coding: utf-8 -*-
"""第111轮 · 素材提取（**可复现**）。

用户口径：「**这些素材我再发一遍，以后记住，任何素材都从这里找**」。

本脚本从**原作安装目录**提取本轮用到的两类素材，落进仓库
`ralsei_pet/assets/scenes/objs/`。**只读原作、只写仓库**，不改原作。

素材清单（#47 Niko 的家彩蛋）
---------------------------
| 用途 | 原作来源 | 提取方式 | 落点 |
|------|----------|----------|------|
| 爆炸特效（三角符文） | Deltarune `chapter1_windows/data.win` 的 `spr_realisticexplosion`（17 帧，71×100） | UTMT CLI `load <data> -s dump_explo.csx` | `spr_realisticexplosion_0..16.png` |
| Niko 光门 | OneShot `content/npc/door_portal.xnb`（192×128） | 自写 XNB(Texture2D) 解析 | `niko_door_portal.png` |
| 光门射线 | OneShot `content/npc/portal_rays.xnb`（64×384） | 同上 | `niko_portal_rays.png` |
| 蓝色闪光 | OneShot `content/npc/sparkle_blue1.xnb`（64×64） | 同上 | `niko_sparkle_blue1.png` |
| 红色闪光 | OneShot `content/npc/sparkle_red1.xnb`（64×64） | 同上 | `niko_sparkle_red1.png` |

★ **为什么 Deltarune 用 UTMT、OneShot 用自写解析器**
  · Deltarune 是 GameMaker `data.win`（自定义二进制）⇒ 用社区标准工具 UTMT 最稳
    （`UndertaleModCli.exe`，只认 `load <data> -s <script.csx>`，**stdout 必须落文件**）。
  · OneShot 是 MonoGame **XNB**（`XNA Framework Content`，未压缩 Texture2D）⇒
    **格式极简**（头 10 字节 + 7-bit 读取器数 + NUL 终止读取器名 + 4 字节 + 16 字节
    `fmt/w/h/mips` + 4 字节 `dlen` + BGRA 像素），自写 30 行解析器即可，**不必装 XNB 工具**。
    ★ 踩坑记录（本轮实测）：
      - 读取器名是**空终止字符串**（前 1 字节的 `0x01` 是"读取器个数"**7-bit**，不是长度）；
      - 名称后到对象之间**固定还有 4 字节**（`sharedResourceCount` 的值），
        漏掉它会把 `width` 读成 `height`（本轮连错三次才定位）；
      - 整型是**小端**，但 `fmt=0` 时前 4 字节是 `00 00 00 00` ⇒ 只看第 1 字节会误判成大端。

用法
----
    C:\\Python311\\python.exe extract111.py            # 只打印计划
    C:\\Python311\\python.exe extract111.py --run      # 真提取
"""
import io
import os
import shutil
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')

DR_DIR = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密\DELTARUNE_183049\DELTARUNE'
DR_DATA = os.path.join(DR_DIR, 'chapter1_windows', 'data.win')
OS_DIR = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
          r'\OneShot.World.Machine.Edition.Build.16512634\content')
OS_NPC = os.path.join(OS_DIR, 'npc')

UTMT = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
TMP = r'E:\Download\_tmp\extract111'

RUN = '--run' in sys.argv


# ----------------------------------------------------------------- XNB 解析
def _r7(b, p):
    r = 0
    s = 0
    while True:
        x = b[p]
        p += 1
        r |= (x & 0x7F) << s
        if not (x & 0x80):
            return r, p
        s += 7


def _nts(b, p):
    e = b.index(b'\x00', p)
    return b[p:e].decode('utf-8', 'replace'), e + 1


def xnb_texture(path):
    """返回 (w, h, rgba_bytes) 或 None。"""
    b = open(path, 'rb').read()
    if b[:3] != b'XNB':
        return None
    # 头 = 'XNB'(3) + platform(1) + version(1) + flags(1) + fileSize(4) = 10 字节
    flags = b[5]
    p = 10
    if flags & 0x80:
        raise NotImplementedError('压缩 XNB（本脚本只做未压缩）')
    nreaders, p = _r7(b, p)
    rtypes = []
    for _ in range(nreaders):
        t, p = _nts(b, p)
        rtypes.append(t)
    nshared, p = _r7(b, p)
    if not rtypes or 'Texture2D' not in rtypes[0]:
        return None
    p += 4                     # ★ 名称后固定 4 字节（sharedResourceCount 值）
    fmt, w, h, mips = struct.unpack_from('<iiii', b, p)
    p += 16
    if fmt != 0:
        return None            # 只处理 SurfaceFormat.Color
    dlen = struct.unpack_from('<i', b, p)[0]
    p += 4
    data = b[p:p + dlen]
    out = bytearray(len(data))
    for i in range(w * h):
        o = i * 4
        out[o] = data[o + 2]       # R <- BGRX 的第 3 字节
        out[o + 1] = data[o + 1]
        out[o + 2] = data[o]
        out[o + 3] = data[o + 3]
    return w, h, bytes(out)


def write_png(path, w, h, rgba):
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload
                + struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    png += chunk(b'IEND', b'')
    open(path, 'wb').write(png)


# ----------------------------------------------------------------- UTMT 脚本
CSX = u'''using System;
using System.IO;
using UndertaleModLib.Util;

EnsureDataLoaded();
string dir = Path.GetDirectoryName(FilePath);
string outdir = Path.Combine(dir, "fx_spr");
Directory.CreateDirectory(outdir);
int n = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (UndertaleSprite s in Data.Sprites)
    {
        if (s.Name.Content != "spr_realisticexplosion") continue;
        Console.WriteLine("FOUND " + s.Name.Content + " w=" + s.Width
                          + " h=" + s.Height + " frames=" + s.Textures.Count);
        for (int i = 0; i < s.Textures.Count; i++)
        {
            var te = s.Textures[i];
            if (te == null || te.Texture == null) continue;
            worker.ExportAsPNG(te.Texture,
                Path.Combine(outdir, s.Name.Content + "_" + i + ".png"), null, false);
            n = n + 1;
        }
    }
}
Console.WriteLine("EXPORTED " + n);
'''


def extract_deltarune():
    if not os.path.isfile(DR_DATA):
        print('SKIP Deltarune：data.win 不在 %s' % DR_DATA)
        return []
    # ★ 先跑一次 UTMT 到**副本**（绝不改原作）：把 data.win 复制到临时区，
    #   脚本里 `Path.GetDirectoryName(FilePath)` 决定导出目录 ⇒ 导出落在副本旁边。
    #   ★ 直接对原作跑 UTMT 会往原作目录写 `fx_spr/`（污染用户游戏目录），所以必须用副本。
    made = []
    if not RUN:
        print('  （预览模式；--run 会复制 data.win 到临时区后调 UTMT 导出）')
        return []
    os.makedirs(TMP, exist_ok=True)
    local_data = os.path.join(TMP, 'data.win')
    if os.path.getsize(local_data) != os.path.getsize(DR_DATA) if os.path.isfile(local_data) else True:
        shutil.copyfile(DR_DATA, local_data)
    csx = os.path.join(TMP, 'dump_explo.csx')
    io.open(csx, 'w', encoding='utf-8').write(CSX)
    log = os.path.join(TMP, 'utmt.log')
    with io.open(log, 'wb') as fh:
        subprocess.run([UTMT, 'load', local_data, '-s', csx],
                       stdout=fh, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL,
                       cwd=os.path.dirname(UTMT))
    fx = os.path.join(TMP, 'fx_spr')
    for i in range(17):
        s = os.path.join(fx, 'spr_realisticexplosion_%d.png' % i)
        if os.path.isfile(s):
            made.append(s)
    return made


def main():
    print('== 第111轮素材提取 ==')
    print('仓库落点: %s' % OBJS)
    if not RUN:
        print('（预览模式；加 --run 真提取）')

    # 1) Deltarune 爆炸 17 帧
    fx = extract_deltarune()
    print('爆炸帧: %d 个' % len(fx))
    if RUN:
        for i, s in enumerate(fx):
            shutil.copyfile(s, os.path.join(OBJS, 'spr_realisticexplosion_%d.png' % i))

    # 2) OneShot（XNB 自解析）
    pairs = [('door_portal', 'niko_door_portal.png', (192, 128)),
             ('portal_rays', 'niko_portal_rays.png', (64, 384)),
             ('sparkle_blue1', 'niko_sparkle_blue1.png', (64, 64)),
             ('sparkle_red1', 'niko_sparkle_red1.png', (64, 64))]
    for base, out, exp in pairs:
        src = os.path.join(OS_NPC, base + '.xnb')
        if not os.path.isfile(src):
            print('SKIP %s（不在盘）' % src)
            continue
        r = xnb_texture(src)
        if r is None:
            print('SKIP %s（非 Texture2D/Color）' % base)
            continue
        w, h, rgba = r
        flag = 'OK' if (w, h) == exp else 'SIZE-MISMATCH exp=%r' % (exp,)
        print('%-16s %dx%d alpha_extrema=%r  %s'
              % (base, w, h, (min(rgba[3::4]), max(rgba[3::4])), flag))
        if RUN:
            write_png(os.path.join(OBJS, out), w, h, rgba)

    if RUN:
        print('\n落盘后 objs 目录共 %d 个文件' % len(os.listdir(OBJS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
