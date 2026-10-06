# -*- coding: utf-8 -*-
u"""selftest96.py —— 对 `analyze96.py` 的**判据自测**（A/B：有缺陷必报红）。

为什么必须做
------------
本项目的头号方法论铁律：**判据也是被测物**。
第95轮就栽在"判据过宽 ⇒ 修复前的源码也能全绿"上（`_angle_chains` 首版按"跨度最大"
只挑一条链，恰好挑中正确的那条 ⇒ A 侧 25 PASS、E 段一条没红）。

这个自测做的是**同一件事的反面**：喂进**已知缺陷形态**的合成数据，
看 `analyze96.py` 的对应判据**是不是真的报红**。

A/B 两侧
--------
  A 侧（有缺陷）：把真实数据改造出 4 种已知病的形态：
     A1 站桩      —— 把某段走路帧的坐标改成"原地不动"（第92轮指纹）
     A2 朝向反向  —— 把某段帧的 `dir` 整体翻面（第95轮缺陷 B 的形态）
     A3 静止残留  —— 把静止段末帧的 anim 改成 walk_*（F35-4 的形态）
     A4 越界      —— 把某帧坐标改到屏幕外 99999
  B 侧（无缺陷）：原始未改造的数据。
判据：**A 侧必须报红对应条目；B 侧该条目必须绿。**
若 A 侧也绿 ⇒ 判据是"看着在守其实没守"（恒真/过宽）⇒ 自测失败。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第96轮-用户视角录制复核\\_tools\\selftest96.py
"""
import io
import importlib.util
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')

# ---- 导入 analyze96 的判据函数（不跑 main）----
_spec = importlib.util.spec_from_file_location('A96', os.path.join(HERE, 'analyze96.py'))
A96 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A96)

_P = []
_N = [0]
_BAD = [0]


def P(s=''):
    _P.append(s)


def check(ok, name, detail=u''):
    _N[0] += 1
    if not ok:
        _BAD[0] += 1
    P(u'[%s] %s%s' % (u'PASS' if ok else u'FAIL', name,
                      (u'  —— ' + detail) if detail else u''))
    return bool(ok)


def run_criteria(frames, geo=(2560, 1600)):
    u"""跑一遍判据（B/C/D），把每条判据的 PASS/FAIL 收成 dict。
    ★ 数据源是 `frames.csv` 等间隔采样（自测时我把它改造出各种病）。"""
    out = {}
    for tag, fn in (('B', A96.sec_b), ('C', A96.sec_c), ('D', A96.sec_d)):
        n0, b0 = A96._N[0], A96._BAD[0]
        A96._P.clear()
        fn(frames)
        out[tag] = (A96._N[0] - n0, A96._BAD[0] - b0, list(A96._P))
    return out


def main():
    mv = A96.rd(os.path.join(EV, 'rec96_moves.txt'))
    csvt = A96.rd(os.path.join(EV, 'rec96_frames.csv'))
    if not csvt:
        print(u'★ 没有 rec96_frames.csv，先跑 rec96.py')
        return 2
    rows = A96.parse_moves(mv) if mv else []
    frames = A96.parse_csv(csvt)
    P(u'#' * 72)
    P(u'# selftest96 · analyze96 判据自测（A/B：有缺陷必报红）')
    P(u'#' * 72)
    A96._P.clear()
    A96._N[0] = 0
    A96._BAD[0] = 0
    P(u'原始数据：frames %d 行 / moves %d 行' % (len(frames), len(rows)))

    # ---------- B 侧：原始数据 ----------
    P(u'')
    P(u'--- B 侧：原始数据（期望：无明显红）---')
    res_b = run_criteria(frames)
    for tag, (n, b, lines) in sorted(res_b.items()):
        P(u'    %s 段：%d 条判据，%d 条红' % (tag, n, b))
        for ln in lines:
            if ln.startswith('[FAIL]'):
                P(u'      ' + ln)
    b_bad = sum(v[1] for v in res_b.values())
    # ★ B 侧的期望不是"0 条红"，而是"**红条必须被 C2b/C3 的连续段口径解释掉**"：
    #   C 段一条红可能来自 (a) 折返瞬间的单帧滞后 或 (b) 真缺陷。
    #   若红的是 C2/C2b/C3 这类"连续段"判据 ⇒ 说明是真缺陷（要人看）；
    #   若红的是"占比"类 ⇒ 通常是真机噪声。
    check(b_bad == 0, u'S0 B 侧（真实数据）红条 = 0',
          u'实测 %d 条红%s' % (b_bad, u'' if b_bad == 0 else
                             u' ⇒ 逐条核对：见上方 C 段明细'))

    # ---------- A 侧：合成已知缺陷 ----------
    P(u'')
    P(u'--- A 侧：合成缺陷（期望：对应判据必须报红）---')

    # A1 站桩：把走路帧的坐标钉死（等间隔采样下 ⇒ 相邻行坐标相同 = 零位移）
    #   ★ 首版只改 wx/wy，结果 B 段一条没红 —— 因为被钉死的那几行的 anim 未必都是走路
    #     （负控制输入必真落进被测分支：必须先**只挑走路帧**再钉）
    #   ★★ 第96轮修（第二次同类）：首版只钉**连续 8 帧** ⇒ 8/699 = 1.14% < 5% 阈值
    #     ⇒ **夹具不保真、报假绿**。B1b 判的是**占比**，夹具就必须钉出**足够占比**的病。
    #     改为：钉住**全部走路帧里 50% 的帧**（隔一个钉一个）⇒ 零位移占比 ≈50% ⇒ 必报红。
    r1 = [dict(r) for r in frames]
    wi = [i for i, r in enumerate(r1) if A96.WALK.match(r.get('anim') or '')]
    pinned = 0
    if len(wi) >= 8:
        # ★ 对"走路帧坐标"按 50% 比例钉死：每 2 个走路帧钉掉 1 个
        for k, i in enumerate(wi):
            if k % 2:
                continue
            # 钉成"与前一个走路帧相同"⇒ 该帧零位移
            if k == 0:
                r1[i]['wx'] = r1[i]['wx']
                continue
            j = wi[k - 1]
            r1[i]['wx'], r1[i]['wy'] = r1[j]['wx'], r1[j]['wy']
            # 同步把速度向量清零，避免"速度仍在但位置不动"的混合态
            r1[i]['spdx'], r1[i]['spdy'] = 0.0, 0.0
            pinned += 1
    res = run_criteria(r1)
    n1, b1, lines1 = res['B']
    check(b1 >= 1, u'S1 ★★★ 合成"站桩 50% 走路帧"（坐标钉死）⇒ B1b 必须报红',
          u'钉住 %d 个走路帧（共 %d）⇒ 零位移占比 ≈%.0f%%；B 段 %d 条红'
          % (pinned, len(wi), 100.0 * pinned / max(1, len(wi)), b1))
    for ln in lines1:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    # A2 朝向反向：**只翻 `dir`** ⇒ 打穿 C1（dir vs anim）与 C3（dir vs 位移）
    #    ★ 必须只翻 dir、不动 anim：这正是"用户看到两个朝向打架"的形态
    OPP = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
    r2 = [dict(r) for r in frames]
    fi = []
    for i in range(1, len(r2)):
        a, b = r2[i - 1], r2[i]
        if b['dir'] in OPP and a['wx'] is not None and b['wx'] is not None \
                and (a['wx'] != b['wx'] or a['wy'] != b['wy']):
            fi.append(i)
    for i in fi[:max(1, len(fi) // 3)]:
        r2[i]['dir'] = OPP[r2[i]['dir']]
    res = run_criteria(r2)
    n2, b2, lines2 = res['C']
    check(b2 >= 1, u'S2 ★★★ 合成"朝向整体反向（只翻 dir）"⇒ C 段必须报红',
          u'C 段 %d 条红（第95轮缺陷 B 的形态）' % b2)
    for ln in lines2:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    # A2b 精灵朝向反向：**只翻 anim 的方向段** ⇒ 打穿 C1 与 C2
    r2b = [dict(r) for r in frames]
    for r in r2b:
        mm = A96._WALKF.match(r.get('anim') or '')
        if mm:
            r['anim'] = r['anim'].replace('_' + mm.group(1), '_' + OPP[mm.group(1)])
    res = run_criteria(r2b)
    n2b, b2b, lines2b = res['C']
    check(b2b >= 1, u'S2b ★★★ 合成"播的精灵朝向反向（只翻 anim）"⇒ C 段必须报红',
          u'C 段 %d 条红' % b2b)
    for ln in lines2b:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    # A3 静止残留走路：找"≥4s 零位移段"，把末帧 anim 改成 walk_left
    r3 = [dict(r) for r in frames]
    best, cur = None, None
    for i in range(1, len(r3)):
        a, b = r3[i - 1], r3[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        if a['wx'] == b['wx'] and a['wy'] == b['wy'] and a['ww'] == b['ww']:
            cur = cur or [i - 1, i]
            cur[1] = i
        else:
            if cur and (float(r3[cur[1]]['t']) - float(r3[cur[0]]['t'])) >= 4.0:
                best = cur
            cur = None
    if cur and (float(r3[cur[1]]['t']) - float(r3[cur[0]]['t'])) >= 4.0:
        best = cur
    if best:
        r3[best[1]]['anim'] = 'walk_left'
        r3[best[1]]['dir'] = 'left'
    res = run_criteria(r3)
    n3, b3, lines3 = res['D']
    check(b3 >= 1, u'S3 ★★★ 合成"静止段末帧残留走路姿势"⇒ D1 必须报红',
          u'D 段 %d 条红%s' % (b3, u'' if best else u'（★ 没找到 ≥4s 静止段，本条不成立）'))
    for ln in lines3:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    # A4 越界
    f2 = [dict(x) for x in frames]
    if f2:
        f2[len(f2) // 2]['wx'] = 99999
        A96._P.clear()
        A96._N[0] = 0
        A96._BAD[0] = 0
        A96.sec_e(f2, (2560, 1600))
        nb = A96._BAD[0]
        lines4 = list(A96._P)
        check(nb >= 1, u'S4 ★★★ 合成"窗口越界"⇒ E2 必须报红', u'E 段 %d 条红' % nb)
        for ln in lines4:
            if ln.startswith('[FAIL]'):
                P(u'      ' + ln)

    # A5 覆盖度：把目标全挪到正上方 ⇒ [30,60) 扇区 0 帧
    r5 = []
    for r in frames:
        rr = dict(r)
        rr['wx'] = 1000
        rr['wy'] = 1000
        rr['tx'] = 1000
        rr['ty'] = 500
        r5.append(rr)
    A96._P.clear()
    A96._N[0] = 0
    A96._BAD[0] = 0
    A96.sec_a2_target_sectors(r5)
    nb5 = A96._BAD[0]
    check(nb5 >= 1, u'S5 ★★★ 合成"未覆盖 [30,60) 扇区"⇒ A5b 必须报红',
          u'A2 段 %d 条红（这条保证"没测到"不会被当成"没问题"）' % nb5)

    # A6 ★★★ 原缺陷扇区复现：把 [30,60) 扇区内的帧全改成"判 left + 播 walk_left"
    #    这正是第95轮缺陷 B 的**逐帧形态** ⇒ C4 必须报红
    r6 = [dict(r) for r in frames]
    hit = 0
    for i in range(1, len(r6)):
        a, b = r6[i - 1], r6[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        dx = (b['wx'] - a['wx']) if isinstance(b['wx'], int) \
            and isinstance(a['wx'], int) else 0
        dy = (b['wy'] - a['wy']) if isinstance(b['wy'], int) \
            and isinstance(a['wy'], int) else 0
        if dx == 0 and dy == 0:
            continue
        deg = math.degrees(math.atan2(dy, dx))
        if 30.0 <= deg < 60.0:
            b['dir'] = 'left'
            b['anim'] = 'walk_left'
            hit += 1
    res = run_criteria(r6)
    n6, b6, lines6 = res['C']
    check(b6 >= 1 and hit > 0,
          u'S6 ★★★ 合成"缺陷 B 逐帧复现"（[30,60) 内全判 left）⇒ C4 必须报红',
          u'改造 %d 帧；C 段 %d 条红' % (hit, b6))
    for ln in lines6:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    P(u'')
    # ---------- S7 ★★★ 新增：**速度向量**反向（新判据 C2v/C3v 的鉴别力）----------
    #   动机：本轮把主判据从「采样位移」换成了「速度向量」。
    #   ★ 换了判据就必须**重做自测**（记忆铁律：判据也是被测物）。
    #   做法：只翻 `spdx/spdy` 的符号（**不动 `anim`/`dir`**）⇒
    #     新判据 C2v/C3v 必须报红；而"采样位移口径"的 C2（参考项）**不该**报红
    #     —— 这正好证明两者测的**不是同一件事**。
    P(u'--- S7 ★★★ 合成"速度向量反向"（只翻 spdx/spdy，不动 anim/dir）---')
    import copy as _copy
    r7 = _copy.deepcopy(frames)
    hit7 = 0
    for f in r7:
        sx, sy = f.get('spdx'), f.get('spdy')
        if sx is None or sy is None:
            continue
        try:
            if abs(float(sx)) + abs(float(sy)) > 0.3:
                f['spdx'] = -float(sx)
                f['spdy'] = -float(sy)
                hit7 += 1
        except Exception:
            pass
    res7 = run_criteria(r7)
    n7, b7, lines7 = res7['C']
    check(b7 >= 1 and hit7 > 0,
          u'S7 ★★★ 合成"速度向量反向"⇒ C2v/C3v 必须报红',
          u'改造 %d 帧；C 段 %d 条红' % (hit7, b7))
    for ln in lines7:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    P(u'')
    # ---------- S8 ★★ 新增：速度向量**缺失** ⇒ 必须"无法判定"而不是"默认绿" ----------
    #   动机：静默退化是最危险的形态（第93轮 `numScreens()` 被吞的教训）。
    #   做法：清空 `spdx/spdy` ⇒ 新判据必须走"样本不足 ⇒ 报红"分支。
    P(u'--- S8 ★★ 合成"速度向量缺失"（清空 spdx/spdy）⇒ 必须报"无法判定" ---')
    r8 = _copy.deepcopy(frames)
    for f in r8:
        f['spdx'] = None
        f['spdy'] = None
    res8 = run_criteria(r8)
    n8, b8, lines8 = res8['C']
    has_v_fail = any(u'C2v' in ln or u'速度向量' in ln for ln in lines8
                     if ln.startswith('[FAIL]'))
    check(b8 >= 1 and has_v_fail,
          u'S8 ★★ 速度向量缺失 ⇒ C2v/C3v 必须报"无法判定"（不许静默退化成绿）',
          u'C 段 %d 条红，其中含速度向量判据：%s' % (b8, has_v_fail))
    for ln in lines8:
        if ln.startswith('[FAIL]'):
            P(u'      ' + ln)

    P(u'')
    P(u'=' * 72)
    P(u'合计：PASS=%d  FAIL=%d  判据=%d' % (_N[0] - _BAD[0], _BAD[0], _N[0]))
    P(u'=' * 72)
    io.open(os.path.join(EV, 'selftest96.txt'), 'w',
            encoding='utf-8', newline='\n').write(u'\n'.join(_P) + u'\n')
    print(u'\n'.join(_P))
    return 1 if _BAD[0] else 0


if __name__ == '__main__':
    sys.exit(main())
