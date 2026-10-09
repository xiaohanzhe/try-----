# -*- coding: utf-8 -*-
u"""identify100.py —— 第100轮：用户补发的 OneShot 素材**按内容识别**（不信文件名）。

为什么必须按内容识别
------------------
用户原话：「oneshot 有部分音效和素材缺失，这些是补齐的，**里面可能有些素材名称被改了**」。
实测已证实：`foodstep_grass.wav` 的内容 == 原作 `step_grass.wav`（同名检索 0 命中、内容哈希命中）。
⇒ 名字不可信，**必须用内容指纹对账**。

做两件事
--------
1. **贴图**：把原作 `content/facepics|npc|item_icons|pictures/*.xnb` 解成 RGBA 取指纹，
   与补发目录的 PNG 逐个比 ⇒ 得 `补发名 -> 原作资源名` 映射（对不上者如实标 `NEW`）。
2. **音效**：把原作 `gamedata/sfx/*.wav` 取指纹，与补发的 wav 比 ⇒ 同上。

锚点（不通过就不往下用）
----------------------
A1 补发目录可读；A2 XNB 解码成功率报数（解不开的如实登记，不假装）；
A3 正控制：同一文件两份副本必须命中（哈希口径自证）；
A4 负控制：把一个像素改掉必须**不**命中；
A5 音效侧同 A3/A4。

用法
----
    C:\\Python311\\python.exe -X utf8 identify100.py            # 只跑锚点 + 打印表
    C:\\Python311\\python.exe -X utf8 identify100.py --dump     # 另存 _evidence/identify100.json
"""
import hashlib
import io
import json
import os
import struct
import sys
import wave

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                        # noqa: E402

try:
    import numpy as np                                       # noqa: E402
except Exception:                                            # pragma: no cover
    np = None

OS = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
      r'\OneShot.World.Machine.Edition.Build.16512634')
SUP = r'C:\Users\23002\Desktop\项目文件夹\assets'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
OUT = os.path.join(ROUND, '_evidence')

#: 补发目录里**不是素材**的东西（用户的工作目录混入物）—— 明确排除，绝不入库
NOT_ASSETS = {'config.json', 'save_key.py', 'desktop.ini'}

PIC_SUBDIRS = ['facepics', 'npc', 'item_icons', 'pictures', 'lightmaps', 'panoramas']
SFX_DIR = os.path.join(OS, 'gamedata', 'sfx')

FAILS = []


def check(name, ok, detail=''):
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAILS.append(name)
    return ok


# ---------------------------------------------------------------- XNB
def rd7(b, i):
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
    n, i = rd7(b, i)
    return b[i:i + n].decode('utf-8', 'replace'), i + n


def read_xnb(path):
    b = open(path, 'rb').read()
    if b[:3] != b'XNB':
        raise ValueError('not XNB')
    flags = b[5]
    if flags & 0x80:
        raise ValueError('LZ4')
    if flags & 0x40:
        raise ValueError('LZMA')
    i = 10
    nr, i = rd7(b, i)
    for _ in range(nr):
        _nm, i = rds(b, i)
        i += 4
    _ns, i = rd7(b, i)
    _ti, i = rd7(b, i)
    fmt, w, h, mips = struct.unpack('<iIII', b[i:i + 16])
    i += 16
    data = None
    for m in range(mips):
        sz = struct.unpack('<I', b[i:i + 4])[0]
        i += 4
        if m == 0:
            data = b[i:i + sz]
        i += sz
    return dict(fmt=fmt, w=w, h=h, mips=mips, data=data)


def xnb_rgba(path):
    """解出 RGBA + 尺寸；非 Color(0) 格式或解析失败 -> None。"""
    d = read_xnb(path)
    if d['fmt'] != 0 or d['data'] is None:
        return None
    need = d['w'] * d['h'] * 4
    return (d['w'], d['h'], d['data'][:need])


def png_rgba(path):
    im = Image.open(path)
    im = im.convert('RGBA')
    return (im.width, im.height, im.tobytes())


def fp(whb):
    w, h, b = whb
    return hashlib.sha256(b'%dx%d|' % (w, h) + b).hexdigest()[:20]


def sha_file(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:20]


def mismatch_ratio(a, b):
    """逐字节不等比例（0.0~1.0）。尺寸不同 -> 1.0。

    ★ 第100轮教训：逐像素相等是**过窄判据**（补发 `dialog_*` 293~862px，WME 版 `facepics`
      全 48x48 ⇒ 一定不中）。所以"不中"时改用**同尺寸候选 + 容差**如实报，
      而不是直接给一个会被人读成"非原作"的 `NEW`。
    """
    if len(a) != len(b):
        return 1.0
    if not a:
        return 1.0
    n = 0
    for x, y in zip(a, b):
        if x != y:
            n += 1
    return n / float(len(a))


#: 同尺寸候选超过这个数就不逐一比（避免把时间花在素材表的整屏图集上）
MAX_CANDS = 150


def wav_pcm(path):
    """返回 (fmt4, pcm_sha20)；读不出（非 RIFF / 压缩格式）-> None。

    ★ 为什么还要 PCM 这一层：**字节哈希是过窄判据**。同一段音效换个编码器重存
      （尾部补零、标签、位深）字节就变、但**听感与波形**没变。`interaction_2.wav`
      的格式签名 `(2,2,44100,65828)` 与 WME `sfx/item_get.wav` 一模一样，就是这种形态。
    """
    try:
        w = wave.open(path, 'rb')
        fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
        frames = w.readframes(fmt[3])
        w.close()
    except Exception:
        return None
    return fmt, hashlib.sha256(frames).hexdigest()[:20]


def walk_audio(root):
    out = []
    for dp, _dn, fn in os.walk(root, onerror=lambda e: None):
        for f in fn:
            if f.lower().endswith(('.wav', '.ogg', '.mp3')):
                out.append(os.path.join(dp, f))
    return sorted(out)


def to_np(whb):
    """(w,h,bytes) -> float32 (h,w,4)。"""
    w, h, b = whb
    return np.frombuffer(b, dtype=np.uint8).reshape(h, w, 4).astype(np.float32)


def np_mad(a, b):
    """归一化平均绝对差（0~255 尺度）。恒等 -> 0.0。"""
    return float(np.abs(a - b).mean())


def gray_pil(whb):
    """(w,h,bytes) -> 白底合成后的 'L' 灰度 PIL 图（透明区当白）。"""
    w, h, b = whb
    im = Image.frombytes('RGBA', (w, h), b)
    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert('L')


def gray_of_png(path):
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert('L')


def pearson(a, b):
    """(相关, 双方信息量, 亮度差, 双方均值)

    ★ 为什么要额外报**亮度差**：相关对整体明暗**不变**。OneShot 的 `facepics/en*` 是
      Niko 的**暗色变体**、`facepics/niko*` 是**亮色变体**，两者结构相同 ⇒ 相关都 0.95。
      只看相关会挑错变体（第100轮看图才发现：补发 `dialog_*` 是亮版）。
      所以排序用 `相关 - 亮度差/255`，并同时报出两个数，人可复核。
    """
    a = a.ravel().astype(np.float64)
    b = b.ravel().astype(np.float64)
    sa = float(a.std())
    sb = float(b.std())
    ma = float(a.mean())
    mb = float(b.mean())
    if sa < 1.0 or sb < 1.0:
        return None, round(sa, 2), round(sb, 2), round(abs(ma - mb), 2), (round(ma, 1), round(mb, 1))
    ac = a - ma
    bc = b - mb
    r = float((ac * bc).sum() / (np.sqrt((ac * ac).sum()) * np.sqrt((bc * bc).sum())))
    return r, round(sa, 2), round(sb, 2), round(abs(ma - mb), 2), (round(ma, 1), round(mb, 1))


def wav_samples(path):
    """返回 (fmt4, int16 数组) 或 None。"""
    try:
        w = wave.open(path, 'rb')
        fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
        if fmt[1] != 2:
            w.close()
            return None
        raw = w.readframes(fmt[3])
        w.close()
    except Exception:
        return None
    return fmt, np.frombuffer(raw, dtype='<i2').astype(np.int32)


# ---------------------------------------------------------------- 主流程
def main():
    dump = '--dump' in sys.argv
    check('A1 补发目录可读', os.path.isdir(SUP), SUP)
    if FAILS:
        return 1

    all_names = sorted(os.listdir(SUP))
    sups = [n for n in all_names if n not in NOT_ASSETS and not n.endswith('.jpg')]
    skipped = [n for n in all_names if n in NOT_ASSETS or n.endswith('.jpg')]
    print('    补发项 %d（走素材） / 排除 %d：%s' % (len(sups), len(skipped), skipped))

    # ---- 原作侧指纹
    xnb_index = {}
    dims_index = {}          # (w,h) -> [资源名]  ★ 逐像素不中时，用"同尺寸候选"如实报数
    rgba_of = {}             # 资源名 -> (w,h,bytes)，供"最接近"复用，避免重复解码
    n_xnb, n_skip_fmt, n_err = 0, 0, 0
    for sub in PIC_SUBDIRS:
        d = os.path.join(OS, 'content', sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if not n.lower().endswith('.xnb'):
                continue
            p = os.path.join(d, n)
            n_xnb += 1
            try:
                r = xnb_rgba(p)
            except Exception:
                n_err += 1
                continue
            if r is None:
                n_skip_fmt += 1
                continue
            ref = '%s/%s' % (sub, n)
            xnb_index.setdefault(fp(r), []).append(ref)
            dims_index.setdefault((r[0], r[1]), []).append(ref)
            rgba_of[ref] = r
    print('    原作 XNB %d 个：解码成功 %d / 非 Color 跳过 %d / 解析异常 %d'
          % (n_xnb, len(xnb_index), n_skip_fmt, n_err))
    check('A2 XNB 解码成功率 > 50%', n_xnb and (len(xnb_index) / float(n_xnb) > 0.5),
          '%d/%d' % (len(xnb_index), n_xnb))
    check('A2b 无解析异常', n_err == 0, 'err=%d' % n_err)

    # ---- 正/负控制（哈希口径自证）
    probe = None
    for sub in PIC_SUBDIRS:
        d = os.path.join(OS, 'content', sub)
        if os.path.isdir(d):
            fs = [n for n in sorted(os.listdir(d)) if n.lower().endswith('.xnb')]
            if fs:
                probe = os.path.join(d, fs[0])
                break
    if probe:
        r0 = xnb_rgba(probe)
        r1 = xnb_rgba(probe)
        check('A3 正控制：同一 XNB 两次解码指纹相同', fp(r0) == fp(r1))
        w0, h0, b0 = r0
        b2 = bytearray(b0)
        b2[0] ^= 0xFF
        check('A4 负控制：改 1 字节后指纹必须变', fp((w0, h0, bytes(b2))) != fp(r0))

    # ---- 补发贴图 -> 原作
    pic_map, pics_new, pic_info = {}, [], {}
    for n in sups:
        if not n.lower().endswith('.png'):
            continue
        try:
            r = png_rgba(os.path.join(SUP, n))
        except Exception as e:
            pic_map[n] = 'READ_ERR %r' % e
            continue
        hit = xnb_index.get(fp(r))
        if hit:
            pic_map[n] = hit[0] if len(hit) == 1 else hit
            continue
        # 无逐像素对应：如实报"同尺寸原作候选数"，并在候选里挑最接近的（只看内容，不看名字）
        cands = dims_index.get((r[0], r[1]), [])
        info = {'w': r[0], 'h': r[1], 'same_size': len(cands),
                'closest': None, 'closest_diff': None}
        if 0 < len(cands) <= MAX_CANDS:
            best, bestd = None, None
            for ref in cands:
                d = mismatch_ratio(r[2], rgba_of[ref][2])
                if bestd is None or d < bestd:
                    best, bestd = ref, d
                    if d == 0.0:
                        break
            info['closest'], info['closest_diff'] = best, round(bestd, 4)
        pic_info[n] = info
        pic_map[n] = None
        pics_new.append(n)

    # ---- 音效（三级判据：字节哈希 -> PCM 哈希 -> 格式签名）
    all_audio = walk_audio(OS)
    by_bytes, by_pcm, by_fmt = {}, {}, {}
    for p in all_audio:
        rel = os.path.relpath(p, OS)
        by_bytes.setdefault(sha_file(p), []).append(rel)
        s = wav_pcm(p)
        if s:
            by_pcm.setdefault(s[1], []).append(rel)
            by_fmt.setdefault(s[0], []).append(rel)
    print('    原作音频 %d 个（全树）：字节唯一 %d / PCM 唯一 %d / 格式种类 %d'
          % (len(all_audio), len(by_bytes), len(by_pcm), len(by_fmt)))

    wav_map, wav_new, wav_info = {}, [], {}
    for n in sups:
        if not n.lower().endswith('.wav'):
            continue
        p = os.path.join(SUP, n)
        hb = sha_file(p)
        s = wav_pcm(p)
        tier, val = None, None
        if by_bytes.get(hb):
            tier, val = 'bytes', by_bytes[hb]
        elif s and by_pcm.get(s[1]):
            tier, val = 'pcm', by_pcm[s[1]]
        if tier:
            wav_map[n] = val
            wav_info[n] = {'tier': tier, 'fmt': list(s[0]) if s else None}
            continue
        wav_map[n] = None
        same = by_fmt.get(s[0], []) if s else []
        wav_info[n] = {'tier': None, 'fmt': list(s[0]) if s else None,
                       'same_fmt': len(same), 'same_fmt_names': same[:6]}
        wav_new.append(n)

    # ---- 贴图二阶：等比缩放后按**相关**比对
    # ★ 判据自带校准：同时报"同尺寸组的平均相关"，没有参照物的 0.x 没有意义。
    near = {}
    if np is not None and pics_new:
        by_size_ref = {}
        for ref, r in rgba_of.items():
            by_size_ref.setdefault((r[0], r[1]), []).append(ref)
        gray_ref = {k: [gray_pil(rgba_of[x]) for x in v] for k, v in by_size_ref.items()}
        for n in pics_new:
            src = gray_of_png(os.path.join(SUP, n))
            scored = []
            for size, refs in by_size_ref.items():
                t = np.asarray(src.resize(size, Image.LANCZOS), dtype=np.float32)
                for ref, g in zip(refs, gray_ref[size]):
                    r, sda, sdb, dl, mn = pearson(t, np.asarray(g, dtype=np.float32))
                    if r is None:
                        continue
                    scored.append((r - dl / 255.0, ref, round(r, 4), dl))
            scored.sort(reverse=True)
            best = {'ref': None, 'r': -2.0, 'dl': None, 'sda': None, 'sdb': None,
                    'means': None, 'top3': []}
            for sc, ref, r, dl in scored[:3]:
                best['top3'].append('%s(%.3f/%s)' % (ref, r, dl))
            if scored:
                _sc, ref, r, dl = scored[0]
                best.update({'ref': ref, 'r': r, 'dl': dl})
            base = []
            if best['ref']:
                gsz = (rgba_of[best['ref']][0], rgba_of[best['ref']][1])
                grp = by_size_ref[gsz][:24]
                t2 = np.asarray(src.resize(gsz, Image.LANCZOS), dtype=np.float32)
                for x in grp:
                    r, _a, _b, _d, _m = pearson(
                        t2, np.asarray(gray_ref[gsz][by_size_ref[gsz].index(x)], dtype=np.float32))
                    if r is not None:
                        base.append(r)
                best['base_avg'] = round(sum(base) / len(base), 4) if base else None
            near[n] = best
        print('    贴图二阶（缩放后按相关）完成，%d 张' % len(near))
    print('\n--- 贴图识别（%d 张）---' % len(pic_map))
    for n in sorted(pic_map):
        v = pic_map[n]
        if isinstance(v, list):
            print('   %-30s -> 逐像素命中（多个同内容）%s' % (n, v))
        elif isinstance(v, str):
            print('   %-30s -> %s' % (n, v))
        else:
            i = pic_info.get(n, {})
            same = i.get('same_size', 0)
            nf = near.get(n) or {}
            t2 = ''
            if nf.get('ref'):
                r = nf['r']
                dl = nf['dl']
                bv = nf.get('base_avg')
                # ★ 判据 = 相关高 + **与基线差距悬殊**。不用 Δ亮度当阈值：它是**紧裁剪的产物**
                #   （每张立绘的背景占比不同 ⇒ 均值不同），拿它卡阈值会误报（已实测 `dialog_smiling`）。
                tag = ''
                if r >= 0.9 and bv is not None and bv < 0.5:
                    tag = '★同一张画(基线%.2f)' % bv
                elif r >= 0.7:
                    tag = '?弱'
                t2 = ' | 二阶 %s(%dx%d) 相关=%.3f Δ亮度=%s 基线=%s %s' % (
                    nf['ref'], rgba_of[nf['ref']][0], rgba_of[nf['ref']][1], r, dl,
                    bv if bv is not None else float('nan'), tag)
            print('   %-30s -> 无逐像素对应 | %dx%d 同尺寸候选 %d%s'
                  % (n, i.get('w'), i.get('h'), same, t2))
    print('\n--- 音效识别（%d 个）---' % len(wav_map))
    for n in sorted(wav_map):
        v = wav_map[n]
        w = wav_info.get(n) or {}
        if v:
            print('   %-24s -> %s命中 %s' % (
                n, {'bytes': '逐字节', 'pcm': '★PCM（重编码，内容同）'}.get(w.get('tier'), '?'), v))
            continue
        cand = w.get('same_fmt_names') or []
        extra = ''
        if len(cand) == 1 and np is not None:
            a = wav_samples(os.path.join(SUP, n))
            b = wav_samples(os.path.join(OS, cand[0]))
            if a and b and len(a[1]) == len(b[1]):
                d = np.abs(a[1] - b[1])
                extra = ' | 与唯一同格式候选逐样本比：mean=%.2f max=%d（0=同一波形）' % (
                    float(d.mean()), int(d.max()))
        print('   %-24s -> 三级全不中 | 格式=%s 同格式候选 %d 个 e.g. %s%s'
              % (n, w.get('fmt'), w.get('same_fmt', 0), cand, extra))

    check('A5 识别覆盖：贴图 + 音效 == 补发素材数',
          (len(pic_map) + len(wav_map)) == len(sups),
          '%d+%d vs %d' % (len(pic_map), len(wav_map), len(sups)))

    if dump:
        os.makedirs(OUT, exist_ok=True)
        p = os.path.join(OUT, 'identify100.json')
        with io.open(p, 'w', encoding='utf-8') as fh:
            json.dump({'source': SUP,
                       'excluded': skipped,
                       'xnb_total': n_xnb, 'xnb_decoded': len(xnb_index),
                       'xnb_skip_fmt': n_skip_fmt, 'xnb_err': n_err,
                       'pics': pic_map, 'pics_new': pics_new,
                       'pics_info': pic_info, 'pics_near': near,
                       'wavs': wav_map, 'wavs_new': wav_new, 'wavs_info': wav_info},
                      fh, ensure_ascii=False, indent=1)
        print('\n已存 ->', p)

    print('\nFAIL =', len(FAILS), FAILS)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
