# -*- coding: utf-8 -*-
u"""第179轮变异：证明 `check179.py` 的每条判据不是摆设。

★ 本轮变异的目标是**第178轮那条口径**：把"站在谁上面优先"拆掉，
  判据必须立刻报红。

规矩同 174~178 轮：先备份、跑完 sha1 + 全文双核还原、备份落 `D:\\_tmp\\mut179\\`；
锚点在 **LF 视图**里匹配再换回 CRLF（源文件是 CRLF）。
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
CHECK = os.path.join(HERE, 'check179.py')
BAK = 'D:\\_tmp\\mut179'


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


def _sub(old, new, why=u''):
    s = rd(FM_P)
    lf = s.replace(u'\r\n', u'\n')
    assert old in lf, u'锚点没找到（夹具不保真）: %s %s' % (old[:48], why)
    out = lf.replace(old, new, 1)
    assert out != lf
    return FM_P, out.replace(u'\n', u'\r\n')


_BRANCH = (u"            if _stand_alive:\n"
           u"                self._last_z_pick = {'reason': 'standing_floor', 'bottom': None,\n"
           u"                                     'n_front': 0}\n"
           u"                return _stand\n")


def m1_drop_branch():
    u"""整段拆掉"站在谁上面优先"（= 退回第178轮的口径）。"""
    return _sub(_BRANCH, u'', u'drop')


def m2_after_y():
    u"""把这条分支挪到 Y 规则**之后**（顺序反了 ⇒ 永远轮不到它）。"""
    s = rd(FM_P).replace(u'\r\n', u'\n')
    assert _BRANCH in s
    body = (u"            anchor, info = pick_insert_after_by_foot_y(foot_y, self.floors)\n"
            u"            self._last_z_pick = info\n"
            u"            return anchor\n")
    assert body in s
    s2 = s.replace(_BRANCH, u'', 1)
    s2 = s2.replace(body, body + _BRANCH, 1)
    assert s2 != s
    return FM_P, s2.replace(u'\n', u'\r\n')


def m3_no_iswin():
    u"""站楼板分支不校验句柄（失效句柄直接返回）。"""
    return _sub(u"            if _stand_alive:", u"            if _stand:", u'iswin')


def m4_desktop_also():
    u"""站在桌面也强行插到 WorkerW（= Y 排序彻底失效）。"""
    return _sub(u"            anchor, info = pick_insert_after_by_foot_y(foot_y, self.floors)",
                u"            anchor, info = self._workerw_or_bottom(), {'reason': 'x', 'bottom': None, 'n_front': 0}",
                u'desktop')


def m5_no_docstring():
    u"""docstring 里那条修正说明被删（B3 应该抓住）。"""
    return _sub(u"        ★★★ 第179轮修正（第178轮的自伤）：**\"站在谁上面\"优先于 Y 排序**。",
                u"        ★★★ 修正：", u'doc')


#: ★★★ M1 的期望里**不许**写 `A5`：`A5` 判的是"所站窗口句柄已失效 ⇒ 不许直接返回"，
#:     与"这条分支存不存在"无关 —— 分支拆掉后 `_stand` 仍是失效句柄、`IsWindow` 照样失败、
#:     照样落到 Y 规则 ⇒ `A5` **不红是对的**。把与变异无关的判据塞进期望，
#:     等于要求变异去改变它不该改变的东西（同第176轮 M5 那次）。
#:     M1 真正该抓的是 `A1/A3`（站 A 上必须是 A）＋`B1`（结构顺序）＋`C1`（端到端）。
CASES = [
    (u'M1 拆掉"站在谁上面"分支', m1_drop_branch, (u'A1', u'A3', u'B1', u'C1')),
    (u'M2 分支挪到 Y 规则之后', m2_after_y, (u'B1', u'A1')),
    (u'M3 站楼板分支不校验句柄', m3_no_iswin, (u'A5',)),
    (u'M4 站桌面也强行回落 WorkerW', m4_desktop_also, (u'A2', u'A4')),
    (u'M5 删掉 docstring 那条修正说明', m5_no_docstring, (u'B3',)),
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
        assert sha(p) == h0, u'%s 恢复失败' % p
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
