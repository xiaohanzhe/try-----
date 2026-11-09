# -*- coding: utf-8 -*-
u"""第178轮变异：证明 `check178.py` 的每条判据不是摆设。

规矩（与 174/175/176/177 轮同）
------------------------------
  ① **先备份再改**；② 每轮跑完立即恢复并按 sha1 + 全文核对；
  ③ 「红在哪几条」按**实测**记，但必须包含本变异**针对**的那条；
  ④ 备份落 `D:\\_tmp\\mut178\\`（不在工作区）。

★ 锚点在 **LF 视图**里匹配再换回 CRLF（第177轮踩过：源文件是 CRLF，
  锚点按 LF 写会一条都命中不了）。
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
FM_P = os.path.join(REPO, 'ralsei_pet', 'modules', 'floor_manager.py')
MAIN_P = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')
CHECK = os.path.join(HERE, 'check178.py')
BAK = 'D:\\_tmp\\mut178'


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sha(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()


def run_check():
    r = subprocess.run([sys.executable, CHECK], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    codes = []
    for ln in out.splitlines():
        if ln.startswith('[FAIL]'):
            codes.append(ln.split('] ', 1)[1].split(u'    ')[0].strip().split(u' ')[0])
    return r.returncode, codes


def _sub(path, old, new, why=u''):
    s = rd(path)
    lf = s.replace(u'\r\n', u'\n')
    assert old in lf, u'锚点没找到（夹具不保真）: %s %s' % (old[:48], why)
    out = lf.replace(old, new, 1)
    assert out != lf
    return path, out.replace(u'\n', u'\r\n')


# ---------------------------------------------------------------- 变异定义
def m1_unwire():
    u"""把 foot_y 那条分支整段删掉（= 撤回本轮接线，保留纯函数）。"""
    return _sub(FM_P,
                u"        if foot_y is not None and self.underlying_windows:\n"
                u"            anchor, info = pick_insert_after_by_foot_y(foot_y, self.floors)\n"
                u"            self._last_z_pick = info\n"
                u"            return anchor\n", u'', u'unwire')


def m2_z_rule():
    u"""排序键改成 z 序在前（= 退回"谁挡谁由窗口 z 序决定"的老口径）。"""
    return _sub(FM_P,
                u"        key = (bottom, w.get('z_order') or 0)",
                u"        key = (w.get('z_order') or 0, bottom)", u'zrule')


def m3_no_filter():
    u"""把"下沿不在脚底下方就跳过"的条件改成恒假（= 所有窗口都当前挡者）。

    ★ 第一版是**直接删掉那一行 `if`** —— 结果它下面的 `continue`（12 空格）
      没了块头 ⇒ `IndentationError` ⇒ 判据整个崩掉、`[FAIL]` 一条都不打
      （rc=1 但红项为空）⇒ 看着"抓到了"，其实**什么都没证明**。
      变异必须保持语法有效，才是在考判据、不是在考解析器。
    """
    return _sub(FM_P,
                u"        if bottom is None or bottom <= foot_y:",
                u"        if False:  # 变异：不做下沿过滤", u'filter')


def m4_tie_strict():
    u"""`<=` 改成 `<`：下沿齐平也算"窗口在前"。"""
    return _sub(FM_P, u"        if bottom is None or bottom <= foot_y:",
                u"        if bottom is None or bottom < foot_y:", u'tie')


def m5_max():
    u"""取"下沿最大"（= 最远的前挡者，锚点语义反了）。"""
    return _sub(FM_P, u"        if best is None or key < best[0]:",
                u"        if best is None or key > best[0]:", u'max')


def m6_top_to_bottom():
    u"""无前挡者时返回 `HWND_BOTTOM` 而不是 `HWND_TOP`。"""
    return _sub(FM_P,
                u"        return HWND_TOP, {'reason': 'frontmost', 'bottom': None, 'n_front': 0}",
                u"        return HWND_BOTTOM, {'reason': 'frontmost', 'bottom': None, 'n_front': 0}",
                u'top')


def m7_or_fallback():
    u"""`set_window_behind` 改回 `or` 兜底（`HWND_TOP == 0` 会被翻成 BOTTOM）。"""
    return _sub(FM_P,
                u"        insert = HWND_BOTTOM if hwnd_after is None else hwnd_after",
                u"        insert = hwnd_after or HWND_BOTTOM", u'or')


def m8_no_footy_call():
    u"""`_apply_pet_z_order` 不传 `foot_y`（接线断了，跑的还是老口径）。"""
    return _sub(MAIN_P,
                u"            getattr(self, 'current_floor', None), foot_y=foot_y)",
                u"            getattr(self, 'current_floor', None))", u'nofoot')


def m9_all_windows():
    u"""候选改成 `underlying_windows` 全量（把"不成立"的窗口也当遮挡者）。"""
    return _sub(FM_P,
                u"            anchor, info = pick_insert_after_by_foot_y(foot_y, self.floors)",
                u"            anchor, info = pick_insert_after_by_foot_y(foot_y, self.underlying_windows)",
                u'allwin')


def m10_no_guard():
    u"""删掉"窗口表为空就回退"的闸（启动第一拍会把宠物顶到最前）。"""
    return _sub(FM_P,
                u"        if foot_y is not None and self.underlying_windows:",
                u"        if foot_y is not None:", u'guard')


def m11_qrect_bottom():
    u"""下沿改用 `QRect.bottom()`（少 1px ⇒ 脚底=下沿-1 那一格判错）。"""
    return _sub(FM_P,
                u"            return int(rect.top()) + int(rect.height())",
                u"            return int(rect.bottom())", u'qrect')


CASES = [
    (u'M1 删掉 foot_y 分支（撤回接线）', m1_unwire, (u'B2', u'B3', u'B4', u'C1')),
    (u'M2 排序键改成 z 序优先', m2_z_rule, (u'A3', u'A4', u'A5')),
    (u'M3 删掉下沿过滤', m3_no_filter, (u'A2',)),
    (u'M4 齐平也算前挡（<= → <）', m4_tie_strict, (u'A4',)),
    (u'M5 取下沿最大', m5_max, (u'A3', u'A5')),
    (u'M6 无前挡者返回 BOTTOM', m6_top_to_bottom, (u'A1', u'A2')),
    (u'M7 恢复 `or HWND_BOTTOM`', m7_or_fallback, (u'B8', u'D1')),
    (u'M8 `_apply_pet_z_order` 不传 foot_y', m8_no_footy_call, (u'B5',)),
    (u'M9 候选用 underlying_windows', m9_all_windows, (u'B3', u'C2')),
    (u'M10 删掉窗口表回退闸', m10_no_guard, (u'B4', u'C3')),
    (u'M11 下沿用 QRect.bottom()', m11_qrect_bottom, (u'A11',)),
]


def main():
    os.makedirs(BAK, exist_ok=True)
    rc, base = run_check()
    print(u'基线：rc=%d 红项=%r' % (rc, base))
    if rc != 0:
        print(u'★ 基线不绿，先修判据再跑变异。')
        return 2

    hit = 0
    for name, fn, want in CASES:
        p, new = fn()
        before = rd(p)
        h0 = sha(p)
        b = os.path.join(BAK, os.path.basename(p) + '.bak')
        shutil.copy2(p, b)
        try:
            wr(p, new)
            rc, reds = run_check()
            ok = rc != 0 and set(want) <= set(reds)
            hit += 1 if ok else 0
            print(u'%-34s rc=%d 红=%r  期望含%r %s'
                  % (name, rc, reds, list(want), u'✔' if ok else u'✘'))
        finally:
            shutil.copy2(b, p)
        h1 = sha(p)
        assert h1 == h0, u'%s 恢复失败' % p
        assert rd(p) == before, u'%s 字节没还原' % p

    print('')
    print('=' * 70)
    print(u'变异：%d/%d 被抓（且抓的是**针对的那一条**）' % (hit, len(CASES)))
    rc, again = run_check()
    print(u'还原后复跑：rc=%d 红项=%r' % (rc, again))
    print('=' * 70)
    return 0 if hit == len(CASES) and rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
