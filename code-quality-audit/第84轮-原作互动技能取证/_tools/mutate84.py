# -*- coding: utf-8 -*-
u"""第84轮 · check84 关键判据的鉴别力体检（破坏 → 必须报红 → 还原）。

★ 背景（第84轮两次自我纠错）：
  初版把 `self.soul` 误当 `SoulState`，于是：
    ① 在附身入口写了 `soul.clear_keys()` —— **真 AttributeError**（`self.soul` 是 `SoulOverlay`，
       它没这个方法），被 except 吞掉 ⇒ 「补了 control_clear(2)」其实没补；
    ② 在失焦处把本来**合法**的 `soul.release_all()` 改成 `soul.state.clear_keys()`，
       并误称原写法是 bug（`SoulOverlay` 确有 `release_all`）。
  本体检用来证明：check84 现在**真能**把 ① 这种写法抓红。

破坏项：
  D1）附身入口 `soul.release_all()` → `soul.clear_keys()`（应被抓红）
  D2）附身入口整段清键调用删掉（应被抓红）
跑完必还原，还原后必须 FAIL=0。
"""
from __future__ import print_function
import io, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)                        # code-quality-audit/第84轮...
ROOT = os.path.dirname(os.path.dirname(ROUND))        # ★ 仓库根 = try - 副本
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
CHECK = os.path.join(ROUND, '_tools', 'check84.py')

orig = io.open(MAIN, 'r', encoding='utf-8', newline='').read()


def run_check():
    p = subprocess.run([sys.executable, CHECK], capture_output=True,
                       cwd=os.path.dirname(CHECK))
    out = (p.stdout or b'').decode('utf-8', 'replace')
    m = re.search(r'=== .*?PASS=(\d+) FAIL=(\d+)', out)
    fails = [ln for ln in out.splitlines() if '[FAIL]' in ln]
    return (m.group(1) if m else '?', m.group(2) if m else '?', fails)


def write(txt):
    with io.open(MAIN, 'w', encoding='utf-8', newline='') as fh:
        fh.write(txt)


ANCHOR = u'                    soul.release_all()\n'
ALT = u'                    pass  # MUT\n'
BAD = u'                    soul.clear_keys()\n'

ok1 = ok2 = False
try:
    print(u'[0] 原样：', run_check()[:2])

    # D1：把正确的 `soul.release_all()` 换成会静默失败的 `soul.clear_keys()`
    m1 = orig.replace(ANCHOR, BAD)
    assert m1 != orig, u'D1 没生效（锚点 `soul.release_all()` 未命中）'
    write(m1)
    p, f, fails = run_check()
    print(u'[D1] `soul.release_all()` → `soul.clear_keys()` ⇒ PASS=%s FAIL=%s' % (p, f))
    for ln in fails:
        print(u'    ', ln.strip()[:120])
    ok1 = (f != '0' and any(u'control_clear' in ln for ln in fails))

    # D2：整段删掉（模拟"根本没补这条"）
    m2 = orig.replace(ANCHOR, ALT)
    assert m2 != orig, u'D2 没生效'
    write(m2)
    p2, f2, fails2 = run_check()
    print(u'[D2] 删掉清键调用 ⇒ PASS=%s FAIL=%s' % (p2, f2))
    for ln in fails2:
        print(u'    ', ln.strip()[:120])
    ok2 = (f2 != '0' and any(u'control_clear' in ln for ln in fails2))
finally:
    write(orig)
    p3, f3, fails3 = run_check()
    print(u'[还原] PASS=%s FAIL=%s' % (p3, f3))
    for ln in fails3:
        print(u'    ', ln.strip()[:120])

print()
print(u'体检结论：D1命中=%s  D2命中=%s  还原后零FAIL=%s'
      % (ok1, ok2, f3 == '0'))
sys.exit(0 if (ok1 and ok2 and f3 == '0') else 1)
