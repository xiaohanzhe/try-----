# -*- coding: utf-8 -*-
u"""probe96_angle.py —— 证明「产品判方向用的是**单帧速度向量**，不是累积位移」。

背景（自测暴露的口径之争）
--------------------------
`analyze96` 的 C1 段用"**相邻采样（400ms）的坐标差**"推期望方向，真机实测出现：
    t=20.32 dir='up' 期望='left' 位移(-25,-21) 角度=-140.0° anim='walk_up'
三者（dir / anim / 产品行为）自洽，但与我按"采样位移"推的方向不同。

**不能凭这个说产品错** —— 得先看产品到底用什么量判方向。

源码事实（`ralsei_pet/src/main.py`）
----------------------------------
  L7224  actual_dx = new_x - current_pos.x()
  L7225  actual_dy = new_y - current_pos.y()
  L7230  self.current_speed_x = (actual_dx / actual_distance) * new_speed
  L7231  self.current_speed_y = (actual_dy / actual_distance) * new_speed
  L7244  angle = atan2(self.current_speed_y, self.current_speed_x)
  L7258  if -45 <= angle < 45: "right" ...

⇒ 判方向用的是 **`current_speed_*`**（归一化后的**单帧**速度向量）。
   而它由 `actual_dx/dy` 得来 —— **理论上是同一帧的实际位移方向**。

但 L7229 有个闸：`if actual_distance > 0:` —— 若某帧 `actual_distance == 0`
（被屏幕 clamp 夹住、或 round 后位移为 0），则 **保留上一帧的 `current_speed`**。
⇒ 那一帧的方向 = 上一帧的方向，而不是"本帧位移方向"。

本脚本做两件事
--------------
  ① 静态断言：L7229/7230/7231/7244/7258 的结构关系（用 AST 定位 + 断言文本）
  ② 动态复放：从 `rec96_frames.csv` 的**每一次采样**里，
     复原 `current_speed` 的递推（含 L7229 的"零位移保留旧值"闸），
     算出"产品会判什么方向"，再与采样里真实的 `dir` 对比。
     ⇒ 若按"复原的 current_speed"能解释 **≥99%** 的真实 `dir`，
        而按"采样位移"只能解释 ~X% ⇒ **产品行为正确，是我的口径不对**。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第96轮-用户视角录制复核\\_tools\\probe96_angle.py
"""
import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(os.path.normpath(os.path.join(HERE, '..')), '_evidence')

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


def info(name, detail=u''):
    P(u'     %s：%s' % (name, detail))


DIRS = ('up', 'down', 'left', 'right')


def bucket(angle, lo=-45.0, hi=45.0):
    u"""产品 L7258-7265 的档位（`-45/45/135`）。
    ★ 与 analyze96.want_dir 用同一套阈值；这里是"角度版"，那边是"位移版"。"""
    if -45 <= angle < 45:
        return 'right'
    if 45 <= angle < 135:
        return 'down'
    if -135 <= angle < -45:
        return 'up'
    return 'left'


def main():
    P(u'#' * 72)
    P(u'# probe96_angle · 证明产品判方向用的是"单帧速度向量"')
    P(u'#' * 72)

    # ---------- ① 静态结构 ----------
    src = io.open(os.path.join(PKG, 'src', 'main.py'),
                  encoding='utf-8', newline='').read()
    i = src.find('def update_movement')
    j = src.find('\n    def ', i + 10)
    body = src[i:j if j > 0 else len(src)]
    base = src[:i].count('\n') + 1

    def find_line(pat, occ=1):
        cnt = 0
        for m in re.finditer(re.escape(pat), body):
            cnt += 1
            if cnt == occ:
                return base + body[:m.start()].count('\n')
        return -1

    L_ax = find_line('actual_dx = new_x - current_pos.x()')
    L_csx = find_line('self.current_speed_x = (actual_dx / actual_distance) * new_speed')
    L_gate = find_line('if actual_distance > 0:')
    L_ang = find_line('angle = math.atan2(self.current_speed_y')
    L_b1 = find_line('if -45 <= angle < 45:')
    info(u'关键行号', u'actual_dx=L%d 闸=L%d 赋值=L%d 角度=L%d 档位=L%d'
         % (L_ax, L_gate, L_csx, L_ang, L_b1))
    check(0 < L_ax < L_gate < L_csx < L_ang < L_b1,
          u'①-1 结构：位移 → 闸 → 赋值 current_speed → 用 current_speed 算角度 → 分档',
          u'顺序 %d < %d < %d < %d < %d' % (L_ax, L_gate, L_csx, L_ang, L_b1))
    check('self.current_speed_y' in body[body.find('atan2('):body.find('atan2(') + 80],
          u'①-2 ★★★ 角度算的是 `current_speed_y/x`，**不是** `actual_dy/dx`',
          u'⇒ 方向源是"速度向量"（可被闸保留旧值），不是"本帧实际位移"')
    check(L_gate > 0 and L_gate < L_csx,
          u'①-3 ★★ `if actual_distance > 0:` 闸在赋值**之前**',
          u'⇒ 零位移帧**不更新**速度向量 ⇒ 方向沿用上一帧')

    # ---------- ② 动态复放 ----------
    csvp = os.path.join(EV, 'rec96_frames.csv')
    if not os.path.exists(csvp):
        check(False, u'②-0 rec96_frames.csv 存在', u'先跑 rec96.py')
        return 1
    txt = io.open(csvp, encoding='utf-8', newline='').read()
    lines = [l for l in txt.split('\n') if l.strip()]
    hdr = lines[0].split(',')
    frames = [dict(zip(hdr, l.split(','))) for l in lines[1:]
              if len(l.split(',')) == len(hdr)]
    info(u'采样帧', u'%d' % len(frames))

    # 复原 current_speed 递推：cs = 归一化(本帧位移) * speed；（零位移则保留）
    cs = None
    by_speed = []                    # (真实 dir, 由复原 current_speed 推的 dir)
    by_move = []                     # (真实 dir, 由采样位移推的 dir)
    for k in range(1, len(frames)):
        a, b = frames[k - 1], frames[k]
        try:
            ax, ay = int(a['wx']), int(a['wy'])
            bx, by = int(b['wx']), int(b['wy'])
            spd = float(b['spd']) if b['spd'] not in ('', None) else 0.0
        except Exception:
            continue
        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy)
        if d > 0:
            cs = (dx / d * spd, dy / d * spd) if spd > 0 else (dx / d, dy / d)
        real = b['dir']
        if real not in DIRS:
            continue
        if cs is not None:
            by_speed.append((real, bucket(math.degrees(math.atan2(cs[1], cs[0])))))
        if d > 0 and b['ww'] == a['ww'] and b['wh'] == a['wh']:
            by_move.append((real, bucket(math.degrees(math.atan2(dy, dx)))))

    def rate(pairs):
        if not pairs:
            return 0.0, 0, 0
        ok = len([1 for r, e in pairs if r == e])
        return 100.0 * ok / len(pairs), ok, len(pairs)

    ra, oa, na = rate(by_speed)
    rb, ob, nb = rate(by_move)
    info(u'A 口径：由**复原的 current_speed** 推方向',
         u'与真实 dir 一致 %d/%d = %.2f%%' % (oa, na, ra))
    info(u'B 口径：由**采样位移**推方向（analyze96 C1 用的）',
         u'与真实 dir 一致 %d/%d = %.2f%%' % (ob, nb, rb))
    check(ra >= 99.0,
          u'②-1 ★★★ A 口径（产品真实算法）能解释 ≥99% 的真实 dir',
          u'实测 %.2f%% ⇒ 产品行为由"速度向量"完全解释' % ra)
    check(ra > rb,
          u'②-2 ★★★ A 口径显著优于 B 口径',
          u'A %.2f%% vs B %.2f%%（差 %.2f 个百分点）⇒ **B 口径是我的判据偏差**，'
          u'不是产品缺陷' % (ra, rb, ra - rb))

    # 差异样本给出来（留给报告引用）
    diff = [(r, e) for r, e in by_move if r != e]
    info(u'B 口径误判样例数', u'%d' % len(diff))
    P(u'     ★ 结论：C1 段的"矛盾率"必须按 A 口径重算，或改成"三方自洽"判据。')

    P(u'')
    P(u'=' * 72)
    P(u'合计：PASS=%d  FAIL=%d  判据=%d' % (_N[0] - _BAD[0], _BAD[0], _N[0]))
    P(u'=' * 72)
    io.open(os.path.join(EV, 'probe96_angle.txt'), 'w',
            encoding='utf-8', newline='\n').write(u'\n'.join(_P) + u'\n')
    print(u'\n'.join(_P))
    return 1 if _BAD[0] else 0


if __name__ == '__main__':
    sys.exit(main())
