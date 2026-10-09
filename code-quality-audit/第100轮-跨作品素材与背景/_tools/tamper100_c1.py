# -*- coding: utf-8 -*-
u"""tamper100_c1.py —— 第100轮：`check71` C1 改判据后的**破坏式自证**。

为什么必须有这一步
------------------
C1 从「数字相等」改成「无孤儿」是**放宽**判据 ⇒ 放宽最怕变成"什么都能过"。
所以做**双向**验证：
  M+  往 `assets/sprites/os/` 塞一个**白名单之外**的文件 ⇒ C1 **必须报红**（证明仍有鉴别力）
  M-  删掉它 ⇒ C1 **必须恢复绿**（证明报红是它引起的，不是别的噪声）

纪律：不碰别的套件；跑完必须把探针删掉并把目录数还原成 81（**用 os.listdir 查磁盘**，
不靠"我以为删了"）；任一步失败立即清理并如实报 FAIL。
"""
import hashlib
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))          # 仓库根（_tools 往上 4 级）
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
PROBE_DIR = os.path.join(SPR, 'os')
PROBE = os.path.join(PROBE_DIR, '_stray100_probe.png')
SEED = os.path.join(PROBE_DIR, 'clovers.png')              # 拿现成 PNG 当探针，避免手写字节
RUN = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
PY = r'C:\Python311\python.exe'
FAILS = []


def check(name, ok, detail=''):
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAILS.append(name)
    return ok


def run71():
    """跑单套件；**逐条判据要从 `_out/check71.txt` 读**。

    ★ 踩过：`run_all.py --only` 的 stdout **只打汇总表**，套件自己的 `[PASS]/[FAIL]` 行
      被收进 `_out/check71.txt` ⇒ 在 stdout 里找 `C1 ` 恒为「无」，会把自己写坏。
    """
    p = subprocess.run([PY, '-X', 'utf8', RUN, '--only', 'check71'],
                       cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    t = p.stdout.decode('utf-8', 'replace')
    m = re.search(r'合计：PASS=(\d+) FAIL=(\d+)', t)
    outp = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'check71.txt')
    body = io.open(outp, encoding='utf-8', newline='').read() if os.path.isfile(outp) else ''
    c1 = [l for l in body.split('\n') if 'C1 ' in l]
    return (int(m.group(1)), int(m.group(2))) if m else (None, None), c1, t


def cleanup():
    if os.path.isfile(PROBE):
        os.remove(PROBE)


def main():
    check('A0 探针路径当前不存在', not os.path.isfile(PROBE))
    n0 = len(os.listdir(PROBE_DIR))
    check('A1 起始目录数 == 81', n0 == 81, '实际 %d' % n0)

    (p0, f0), c10, _ = run71()
    check('A2 起始：check71 FAIL=0', f0 == 0, 'PASS=%s FAIL=%s' % (p0, f0))

    try:
        import shutil
        shutil.copyfile(SEED, PROBE)
        check('B0 探针已落盘', os.path.isfile(PROBE))
        n1 = len(os.listdir(PROBE_DIR))
        check('B1 目录数 81 -> 82', n1 == 82, '实际 %d' % n1)
        (p1, f1), c11, t1 = run71()
        hit = bool(c11) and 'FAIL' in c11[0] and '_stray100_probe.png' in c11[0]
        check('B2 ★ 白名单外的文件 ⇒ C1 必须报红', f1 == 1 and hit,
              'FAIL=%s C1=%s' % (f1, (c11[0].strip()[:150] if c11 else '(无 C1 行)')))
    finally:
        cleanup()

    check('C0 探针已清理', not os.path.isfile(PROBE))
    n2 = len(os.listdir(PROBE_DIR))
    check('C1 目录数还原 82 -> 81', n2 == 81, '实际 %d' % n2)
    (p2, f2), c12, _ = run71()
    check('C2 ★ 删掉后 C1 必须恢复绿', f2 == 0 and bool(c12) and 'PASS' in c12[0],
          'FAIL=%s C1=%s' % (f2, (c12[0].strip()[:150] if c12 else '(无)')))

    print('\nTAMPER100_C1 =', 'PASS' if not FAILS else ('FAIL ' + str(FAILS)))
    return 0 if not FAILS else 1


if __name__ == '__main__':
    sys.exit(main())
