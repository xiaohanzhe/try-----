# -*- coding: utf-8 -*-
"""零依赖 PNG 解码 → 统计「非透明像素占比 / 颜色数」，回答**一个具体问题**：

    「这个 sprite 画出来到底有没有东西？」

用途（第68轮提交前核验）：判定 ch2~ch5 被过滤掉的 `obj_marker*` 到底是
「invisible 定位锚点」还是「本该显示的装饰」—— 以及同一批里哪些是**真可见装饰**。

★★ 铁律：**先设对照组**再下结论（"能从源码/已知真值拿的，别靠猜"）。
本脚本第一步就是校准：3 个**已知真值**必须成立，否则直接报错退出 ——
判据不过的探针，输出再"好看"也不可信。

零依赖实现（`zlib` + `struct`，手解 IHDR/IDAT + 5 种 filter 反滤波）：
  故意不用 PIL —— 本仓回归不许依赖"用后即删的临时区/外部盘"，
  而 PIL 未必在解释器里；这段代码 ~60 行、可审计、无第三方。

EOL/编码：输出 UTF-8；落盘用 `\\n`。
"""
import io
import os
import re
import struct
import sys
import zlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
EV = os.path.join(ROOT, 'code-quality-audit', '第68轮-可交互道具实例补采', '_evidence')
SRC_ROOT = r'E:\Download\_tmp\dr_out'          # 仅作"补充数据源"，缺失时跳过（见 §3）
CHDIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows', 'ch3': 'chapter3_windows',
         'ch4': 'chapter4_windows', 'ch5': 'chapter5_windows'}

LINES = []


def w(s=''):
    print(s)
    LINES.append(str(s))


# ---------------------------------------------------------------------------
#  PNG 解码（零依赖）
# ---------------------------------------------------------------------------
def read_png(path):
    """→ dict(w,h,ct,px) 或 None。只支持 bit-depth 8 / interlace 0（本仓素材全部如此）。"""
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
    except Exception:
        return None
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    pos, idat, w_, h_, bd, ct = 8, b'', None, None, None, None
    while pos + 8 <= len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w_, h_, bd, ct = struct.unpack('>IIBB', chunk[:10])
        elif typ == b'IDAT':
            idat += chunk
        elif typ == b'IEND':
            break
        pos += 12 + ln
    if w_ is None or ct is None or bd != 8:
        return None
    try:
        raw = zlib.decompress(idat)
    except Exception:
        return None
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ct, 1)
    bpp = max(1, nch)
    stride = w_ * nch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _y in range(h_):
        if p >= len(raw):
            break
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if len(line) < stride:
            line += bytearray(stride - len(line))
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out += line
        prev = line
    return {'w': w_, 'h': h_, 'ct': ct, 'px': bytes(out)}


def stats(path):
    """→ dict(w,h,ratio,ncolors) 或 None。`ratio` = alpha>0 的像素比例。"""
    d = read_png(path)
    if not d:
        return None
    w_, h_, ct, px = d['w'], d['h'], d['ct'], d['px']
    n = w_ * h_
    if ct == 6:
        op = sum(1 for a in px[3::4] if a > 0)
        cols = set(px[i * 4:i * 4 + 3] for i in range(n) if px[i * 4 + 3] > 0)
    elif ct == 2:
        op = n
        cols = set(px[i * 3:i * 3 + 3] for i in range(n))
    elif ct == 4:
        op = sum(1 for a in px[1::2] if a > 0)
        cols = set(px[i * 2] for i in range(n) if px[i * 2 + 1] > 0)
    else:                                   # 0 灰度 / 3 调色板（本仓未见）
        op = n
        cols = set(px[:n])
    return {'w': w_, 'h': h_, 'ratio': op / float(n or 1), 'ncolors': len(cols)}


def find_src(spr):
    """E 盘素材里找首帧；找不到返回 None（**不报错** —— 外部盘缺失是已知风险）。"""
    if not os.path.isdir(SRC_ROOT):
        return None
    for ch in ('ch2', 'ch3', 'ch4', 'ch5', 'ch1'):
        f = os.path.join(SRC_ROOT, CHDIR[ch], 'Sprites', '%s_0.png' % spr)
        if os.path.isfile(f):
            return ch, f
    return None


def resolve(spr):
    """优先仓库内 `objs/`（可长期复跑）；否则回退 E 盘素材。"""
    f = os.path.join(OBJS, '%s_0.png' % spr)
    if os.path.isfile(f):
        return 'objs', f
    r = find_src(spr)
    if r:
        return 'src:%s' % r[0], r[1]
    return None, None


# ---------------------------------------------------------------------------
#  §0 校准：3 个已知真值（不过就退出，不产出任何结论）
# ---------------------------------------------------------------------------
FAIL = 0


def check(name, cond, detail=''):
    global FAIL
    if cond:
        w('[PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        w('[FAIL] %s %s' % (name, detail))


def main():
    w('=== §0 校准：对照组（仓库内 3 个已知真值）===')
    cal = {}
    for spr in ('spr_savepoint', 'spr_markerX', 'spr_eventsmall'):
        src, f = resolve(spr)
        s = stats(f) if f else None
        cal[spr] = s
        w('  %-16s src=%-10s %s' % (spr, src, s))
    # 真值 1：存档点是**真可见物** ⇒ 必须有非透明像素（且不是 100% 的一整块）
    check('C1 spr_savepoint 可见', bool(cal['spr_savepoint'])
          and 0.05 < cal['spr_savepoint']['ratio'] < 0.95,
          '非透明=%.1f%%' % (cal['spr_savepoint']['ratio'] * 100 if cal['spr_savepoint'] else -1))
    # 真值 2：ch1 一直在画的 markerX 也**有内容**（否则第44轮产物里它不该存在）
    check('C2 spr_markerX 有内容', bool(cal['spr_markerX'])
          and cal['spr_markerX']['ratio'] > 0.05,
          '非透明=%.1f%%' % (cal['spr_markerX']['ratio'] * 100 if cal['spr_markerX'] else -1))
    # 真值 3：eventsmall 是一整块实心（9×9 全不透明）—— 反向对照，防"解码器恒报某值"
    check('C3 spr_eventsmall 实心', bool(cal['spr_eventsmall'])
          and cal['spr_eventsmall']['ratio'] > 0.99,
          '非透明=%.1f%%' % (cal['spr_eventsmall']['ratio'] * 100 if cal['spr_eventsmall'] else -1))
    if FAIL:
        w('')
        w('!! 校准未过 ⇒ **不产出任何结论**（判据不过的探针输出不可信）')
        return 1

    # -----------------------------------------------------------------------
    #  §1 ch2~5 被过滤掉的 marker 系（"不画才对"的论据）
    # -----------------------------------------------------------------------
    w('')
    w('=== §1 ch2~ch5 被过滤的 marker 系（判定：实心色块 ⇒ 不画才对）===')
    for spr in ['spr_markerS', 'spr_markerU', 'spr_markerV', 'spr_markerT', 'spr_markerR',
                'spr_markerAny', 'spr_doorAny', 'spr_solid_charmarker', 'spr_climbmarker',
                'spr_debug_40x40', 'spr_pxwhite', 'spr_whitepixel']:
        src, f = resolve(spr)
        s = stats(f) if f else None
        if not s:
            w('  %-26s *** 源不可达（E 盘素材缺失？）***' % spr)
            continue
        w('  %-26s [%s] %3dx%-3d 非透明=%5.1f%%  色数=%-4d'
          % (spr, src, s['w'], s['h'], s['ratio'] * 100, s['ncolors']))

    # -----------------------------------------------------------------------
    #  §2 同一批里的**真可见装饰**（"该补"的清单）
    # -----------------------------------------------------------------------
    w('')
    w('=== §2 同批暴露的"真可见装饰"（判定：有内容、非纯色 ⇒ 应补采）===')
    for spr in ['spr_dw_mansion_door_closed', 'spr_mansion_doorframe_left_side',
                'spr_bg_city_trashcan', 'spr_bg_city_trash_bag', 'spr_dw_ch3_b3bs_trashcan',
                'spr_castle_shop_new', 'spr_fusuma_back_small', 'spr_kris_plat_idle',
                'spr_shadowplatform_table', 'spr_manhole', 'spr_dw_puzzlecloset_door_open',
                'spr_dw_church_stairs', 'spr_dtrans_lightpillar', 'spr_dw_castle_tv_door_mike']:
        src, f = resolve(spr)
        s = stats(f) if f else None
        if not s:
            w('  %-30s *** 源不可达 ***' % spr)
            continue
        w('  %-30s [%s] %3dx%-3d 非透明=%5.1f%%  色数=%-4d'
          % (spr, src, s['w'], s['h'], s['ratio'] * 100, s['ncolors']))

    out = os.path.join(EV, 'alpha_probe68.txt')
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(LINES) + '\n')
    w('')
    w('落盘 %s (%d B)' % (out, os.path.getsize(out)))
    w('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
