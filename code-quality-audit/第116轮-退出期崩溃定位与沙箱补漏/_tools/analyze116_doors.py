# -*- coding: utf-8 -*-
u"""analyze116_doors.py —— 读 `probe116_<tag>.csv` + `_paint.csv` ⇒ 出判定。

★ 为什么把判定从探针里**拆出来**（第116轮踩到）：
  探针 stdout 走 `| tail` 时，整条管道被 SIGTERM 掐掉 ⇒ `tail` 从不 flush
  ⇒ **零输出**，可 `_evidence/` 里 CSV 明明写全了。⇒ 判定**只读落盘数据**，
  这样"取证"与"结论"解耦，任何一次跑完都能事后复算（也方便复检）。
  （同类坑：`vault_guard` 的 0 文件快照自称"一致 ✓"。）

跑法
----
  C:\\Python311\\python.exe "...\\_tools\\analyze116_doors.py" doors_pre3 doors_post
"""
import csv
import io
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec116')

LETTERS = 'ABCD'


def _load(tag):
    p = os.path.join(OUT, 'probe116_%s.csv' % tag)
    if not os.path.exists(p):
        return None, None
    with io.open(p, encoding='utf-8', newline='') as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
        cols = rd.fieldnames
    pp = os.path.join(OUT, 'probe116_%s_paint.csv' % tag)
    paints = []
    if os.path.exists(pp):
        with io.open(pp, encoding='utf-8', newline='') as fh:
            paints = list(csv.DictReader(fh))
    return rows, (paints, cols)


def _f(r, k):
    v = r.get(k)
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(r, k):
    v = _f(r, k)
    return None if v is None else int(v)


def report(tag):
    rows, extra = _load(tag)
    out = [u'=' * 72, u'# probe116_doors 判定  tag=%s' % tag]
    if not rows:
        out.append(u'  ✗ 没有 CSV：%s' % (os.path.join(OUT,
                   'probe116_%s.csv' % tag),))
        return u'\n'.join(out) + u'\n'
    paints, cols = extra
    n = len(rows)
    dur = _f(rows[-1], 't') or 0.0
    out.append(u'  采样 n=%d  时长=%.1f s  ⇒ %.1f Hz' % (n, dur, n / max(1e-9, dur)))
    out.append(u'  列 = %r' % (cols,))

    def _srt(vals, lim=None):
        u"""类型安全去重排序。

        ★★★ 与 `probe116_doors._srt` 同因（第116轮踩到）：`c_above_tb` 是
          `int | ''` 混型，`sorted(set(...))` 直接 `TypeError`
          ⇒ 分析器**整段崩掉、一个结论都不输出**（"判据崩掉比报红更糟"）。
        """
        uniq = {}
        for v in vals:
            uniq.setdefault((type(v).__name__, repr(v)), v)
        out = [uniq[k] for k in sorted(uniq)]
        return out[:lim] if lim else out

    def _set(k, lim=12):
        return _srt((r.get(k) for r in rows), lim)

    for k, nm in (('nd', u'门清单长度'), ('desk', u'桌面场景'),
                  ('cvis', u'画布 isVisible'), ('opqbg', u'opaque_bg'),
                  ('last_drawn', u'last_drawn(0=一扇门都没画)'),
                  ('soul', u'灵魂可见'), ('soulxy', u'灵魂位置'),
                  ('c_above_tb', u'画布在任务栏之上')):
        out.append(u'  %s 取值集合 = %s' % (nm, _set(k)))

    # ---- 1. 逐门 alpha 是否随"宠物↔门"的屏幕像素间距变化 ----
    out.append(u'')
    out.append(u'[1] 渐显是否接到"宠物"（决定性判据）')
    # ★★★ 先做**存在性点名**：某扇门的列整批缺 ⇒ **必须报红**，不许静默跳过。
    #   第116轮踩过：门 C/D 换贴图后探针字母表失效 ⇒ 列全空，而分析器只是
    #   "跳过该门" ⇒ 报告里 C/D 一行都没有、看上去像"没问题"。
    #   ⇒ 「判据崩掉」比「判据报红」更糟，这里改成显式 FAIL 行。
    _missing = [L for L in LETTERS
                if not any(('a' + L) in r and r.get('a' + L) not in ('', None)
                           for r in rows)]
    if _missing:
        out.append(u'  ✗✗✗ 缺列：%s —— 这些门的 alpha **根本没采到**'
                   u'（多半是探针的"贴图名→字母"表失效了，例如门换了贴图）'
                   u'⇒ 本段对它们**无法给结论**，视为失败。' % (','.join(_missing),))
    for L in LETTERS:
        pairs = []
        for r in rows:
            a = _f(r, 'a' + L)
            pet = r.get('pet') or ''
            if a is None or not pet:
                continue
            try:
                px, py, pw, ph = [int(v) for v in pet.split(';')]
                x, y = _i(r, 'x' + L), _i(r, 'y' + L)
                dw, dh = _i(r, 'w' + L), _i(r, 'h' + L)
            except Exception:
                continue
            if None in (x, y, dw, dh):
                continue
            gx = max(x - (px + pw), px - (x + dw), 0)
            gy = max(y - (py + ph), py - (y + dh), 0)
            pairs.append(((gx * gx + gy * gy) ** 0.5, a))
        if not pairs:
            continue
        g = np.array([p[0] for p in pairs], dtype=float)
        al = np.array([p[1] for p in pairs], dtype=float)
        out.append(u'  门%s  间距 min=%.0f max=%.0f 极差=%.0f px | alpha '
                   u'min=%.3f max=%.3f 极差=%.3f'
                   % (L, g.min(), g.max(), g.max() - g.min(),
                      al.min(), al.max(), al.max() - al.min()))
        if g.max() - g.min() > 50:
            near = al[g <= 220]
            far = al[g >= 700]
            if len(near) and len(far):
                dn, df = float(np.median(near)), float(np.median(far))
                out.append(u'      贴门(≤220px) alpha 中位=%.3f (n=%d)  远离'
                           u'(≥700px) 中位=%.3f (n=%d)  ⇒ %s'
                           % (dn, len(near), df, len(far),
                              u'★ 随距离渐变（已接通）'
                              if abs(dn - df) > 0.05
                              else u'✗ 恒定 ⇒ 渐显**没接到宠物**'))
            else:
                out.append(u'      ⚠ 未覆盖两端 ⇒ 不作结论')

    # ---- 2. 内省：逐帧画了什么 ----
    out.append(u'')
    out.append(u'[2] 内省（产品原生帧率，零混叠）')
    if not paints:
        out.append(u'  ✗ 没有 _paint.csv（内省没挂上？）')
    else:
        durs = [float(r['t']) for r in paints]
        gaps = [durs[j] - durs[j - 1] for j in range(1, len(durs))]
        out.append(u'  paintEvent 次数=%d  期间=%.1f s  ⇒ %.1f 次/s'
                   % (len(paints), durs[-1] if durs else 0,
                      len(paints) / max(1e-9, durs[-1] if durs else 1)))
        if gaps:
            ga = np.array(gaps, dtype=float)
            out.append(u'  帧间隔：中位 %.4f s  最大 %.4f s'
                       % (float(np.median(ga)), float(ga.max())))
        for k in ('doors_len', 'cvis', 'opqbg', 'tra'):
            out.append(u'  %s 取值集合 = %s'
                       % (k, sorted(set(r.get(k) for r in paints))[:8]))
        lds = sorted(set(r.get('last_drawn') for r in paints))
        out.append(u'  last_drawn 取值集合 = %s  （0 ⇒ 这一帧**一扇门都没画**）'
                   % (lds[:12],))
        zero = [r for r in paints if r.get('last_drawn') == '0']
        out.append(u'  last_drawn==0 的帧数 = %d / %d' % (len(zero), len(paints)))
        if zero:
            out.append(u'    前 5 帧 t = %s'
                       % ([round(float(r['t']), 2) for r in zero[:5]],))
        cvis = sorted(set(r.get('cvis') for r in paints))
        out.append(u'  画布可见 取值集合 = %s' % (cvis[:6],))
        trs = sorted(set(r.get('tra') for r in paints))
        out.append(u'  过渡遮罩 alpha 取值集合 = %s' % (trs[:8],))
        psd = sorted(set(r.get('psd_n') for r in paints))
        out.append(u'  _paint_screen_doors 返回扇数 取值集合 = %s' % (psd[:8],))
        als = sorted(set(r.get('alphas') for r in paints))
        out.append(u'  逐帧 alpha 元组**种数** = %d  ⇒ %s'
                   % (len(als), u'恒定' if len(als) == 1 else u'在变'))
        for a in als[:6]:
            out.append(u'      %s' % (a,))

    # ---- 3. 像素（粗校验） ----
    out.append(u'')
    out.append(u'[3] 像素粗校验（门矩形内"纯黑比"）')
    for L in ('B', 'D'):
        v = [_f(r, 'b' + L) for r in rows]
        v = [x for x in v if x is not None]
        if not v:
            continue
        a = np.array(v, dtype=float)
        thr = 0.5 * (float(a.min()) + float(a.max()))
        z = int(np.sum(np.abs(np.diff((a > thr).astype(int))) > 0))
        out.append(u'  门%s 纯黑比 min=%.3f max=%.3f 中位=%.3f 过零=%d'
                   % (L, a.min(), a.max(), float(np.median(a)), z))
        out.append(u'      纯黑比 <0.5 的采样数 = %d / %d'
                   % (int((a < 0.5).sum()), len(a)))

    # ---- 4. 结论 ----
    out.append(u'')
    out.append(u'[4] 结论')
    # ★ 以**内省**的 alpha 元组为准（它不经过"贴图名→字母"表 ⇒ 天然免疫改名）。
    #   元组顺序 = `desk_doors.SIDE_LETTERS` 过滤后的顺序 = (上A, 下B, 左C, 右D)。
    seq = []
    for r in (paints or []):
        s = (r.get('alphas') or u'').strip(u'"')
        if not s:
            continue
        try:
            seq.append(tuple(float(x) for x in s.strip(u'()').split(u',')))
        except ValueError:
            continue
    if seq:
        names = (u'上A', u'下B', u'左C', u'右D')
        for i, nm in enumerate(names):
            v = [a[i] for a in seq if len(a) > i]
            if not v:
                continue
            out.append(u'  内省 %s alpha  min=%.4f max=%.4f 极差=%.4f'
                       % (nm, min(v), max(v), max(v) - min(v)))
        c = [a[2] for a in seq if len(a) > 2]
        d = [a[3] for a in seq if len(a) > 3]
        a0 = [a[0] for a in seq]
        b0 = [a[1] for a in seq]
        if c and d:
            if max(c) - min(c) < 1e-6 and max(d) - min(d) < 1e-6:
                out.append(u'  ⇒ 门 C/D 的 alpha **恒定** ⇒ 渐显仍然没生效（或宠物没走到门边）')
            else:
                out.append(u'  ⇒ 门 C/D 的 alpha **随位置变化** ⇒ 渐显已接通')
        if max(a0) - min(a0) < 1e-6 and max(b0) - min(b0) < 1e-6:
            out.append(u'  ⇒ 门 A/B 的 alpha 恒定 1.0 ⇒ 用户口径「oneshot 和 niko '
                       u'的家不变」被保住')
    if paints:
        lds = set(r.get('last_drawn') for r in paints)
        if '0' in lds:
            out.append(u'  ⇒ ⚠ 存在"一扇门都没画"的帧 ⇒ **门上屏是断续的**（闪的候选）')
        else:
            out.append(u'  ⇒ 每一帧都画出了门（>=4）⇒ **门自身不闪**；'
                       u'若有闪烁只能来自遮挡物（任务栏/气泡/对话框）')
    return u'\n'.join(out) + u'\n'


def main():
    tags = sys.argv[1:] or ['doors_pre3']
    txt = []
    for t in tags:
        txt.append(report(t))
    s = u'\n'.join(txt)
    p = os.path.join(OUT, 'analyze116_doors.txt')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(s)
    sys.stdout.write(s.encode('utf-8', 'replace').decode('utf-8', 'replace'))
    try:
        sys.stdout.write(u'\n[analyze116_doors] 已落盘 %s\n' % p)
    except Exception:
        pass


if __name__ == '__main__':
    main()
