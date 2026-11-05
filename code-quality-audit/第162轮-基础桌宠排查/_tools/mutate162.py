# -*- coding: utf-8 -*-
"""第162轮 · 破坏性验证：每条判据都得能"该红的时候红"。

做法：逐条把产品改坏 → 跑 `check162.py` → 断言**恰好**指定的那几条判据变红 →
按字节还原（sha1 核对）→ 下一条。

两条纪律写在代码里：
  · `Z1` 收口：全部还原后重跑，必须 30/0 全绿；
  · `Z2` 字节级还原：每个文件的 sha1 与改前一致（不是"看起来一样"）；
  · `M9` 是**无害变异**（只动注释字面量）—— 一条都不许红，专治"没破坏也报红"。
"""
import io
import os
import re
import sys
import shutil
import hashlib
import subprocess

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
MEM = os.path.join(PET, 'modules', 'memory_system.py')
CHECK = os.path.join(HERE, 'check162.py')
TMP = r'D:\_tmp\mutate162'
PY = sys.executable


def sha1(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def read(p):
    return io.open(p, 'r', encoding='utf-8', newline='').read()


def write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def run_check():
    r = subprocess.run([PY, CHECK], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, cwd=HERE)
    out = r.stdout.decode('utf-8', 'replace')
    fails = []
    for line in out.splitlines():
        if line.startswith('[FAIL]'):
            body = line[len('[FAIL]'):].strip()
            fails.append(body.split()[0] if body else '?')
    return fails, out


MUT = [
    (MAIN, u'    cx = int(pos_x) + int(old_w) // 2\n    return cx - int(new_w) // 2, '
           u'int(pos_y) + int(old_h) - int(new_h)',
     u'    cx = int(pos_x) + int(old_w) // 2\n    cy = int(pos_y) + int(old_h) // 2\n'
     u'    return cx - int(new_w) // 2, cy - int(new_h) // 2',
     ('A3', 'A4', 'A5', 'A6'), u'M1 锚点改回"保中心"'),
    (MAIN, u'+ target_height - self.height())',
     u'+ target_height // 2 - self.height() // 2)',
     ('B4',), u'M2 拖拽补偿退回"半高差"'),
    (MAIN, u'        try:\n            return int(self._taskbar_top_y())\n        except Exception as e:\n'
           u'            _log.debug("main 防御性异常（已忽略）: %s", e)\n'
           u'            return self._desktop_floor_y()',
     u'        try:\n            return int(self._desktop_floor_y())\n        except Exception as e:\n'
     u'            _log.debug("main 防御性异常（已忽略）: %s", e)\n'
     u'            return self._desktop_floor_y()',
     ('C2', 'C3', 'C6'), u'M3 地面退回整屏底'),
    (MAIN, u'                    # 第162轮：实心地面 = 任务栏上沿（不是整屏底），否则落地即被任务栏压住\n'
           u'                    _floor_y = self._desktop_ground_y()',
     u'                    _floor_y = self._desktop_floor_y()',
     ('C5', 'C6'), u'M4 重力落地退回整屏底'),
    (MAIN, u'        if getattr(self, \'_is_thrown\', False):',
     u'        if getattr(self, \'_is_thrown\', False) and not hasattr(self, \'_fall_land_y\'):',
     ('C7',), u'M5 甩飞落点退回"只算一次"'),
    (MEM, u"            return os.path.join(base, 'memory.json')",
     u"            return ''",
     ('D2', 'D3'), u'M6 回落位置算不出来（退化成"写失败就丢"）'),
    (MEM, u'                self._write_memory_atomic(self.memory_file, data)',
     u'                self._write_memory_atomic(self._fallback_memory_file(), data)',
     ('D1', 'D3'), u'M7 主落点永远不写（能写也搬走）'),
    (MAIN, u'        menu.addSeparator()\n        quit_action = QAction("退出 Ralsei", self)',
     u'        menu.addSeparator()\n        quit_action = QAction("走啦", self)',
     ('E1',), u'M8 菜单项改名（退出口不见了）'),
    (MAIN, u'纯函数（零 Qt），所以 `check162` 能直接喂数字断言，不用起窗口。',
     u'纯函数（零 Qt）——回归可以直接喂数字。',
     (), u'M9 无害变异：只改注释字面量'),
]


def main():
    if not os.path.isdir(TMP):
        os.makedirs(TMP, exist_ok=True)
    maps = {MAIN: u'_main.bak', MEM: u'_mem.bak'}
    before = {}
    for p, name in maps.items():
        shutil.copy2(p, os.path.join(TMP, name))
        before[p] = sha1(p)

    fails0, out0 = run_check()
    print('[BASE] check162 改前 = %d 条失败（应为 0）' % len(fails0))
    if fails0:
        print(out0[-2000:])
        return 2

    bad = 0
    for path, old, new, expect, title in MUT:
        src = read(path)
        # ★ 产品文件是 CRLF（main.py / memory_system.py 全篇），多行锚点写的是 `\n`
        #   ⇒ 不归一会整片 MISS（第162轮实测：M1/M3/M4/M6/M9 全没匹配上）。
        if u'\r\n' in src:
            old = old.replace(u'\n', u'\r\n')
            new = new.replace(u'\n', u'\r\n')
        if old not in src:
            print('[MISS] %s —— 锚点没匹配上（先改脚本）' % title)
            bad += 1
            continue
        write(path, src.replace(old, new, 1))
        try:
            fails, out = run_check()
        finally:
            for p, name in maps.items():
                if sha1(p) != before[p]:
                    shutil.copy2(os.path.join(TMP, name), p)
        got = set(fails)
        want = set(expect)
        ok = (got == want)
        print(u'%s %-26s 期望=%s 实得=%s' % (
            u'[PASS]' if ok else u'[FAIL]', title,
            ','.join(sorted(want)) or u'(一条都不红)', ','.join(sorted(got)) or u'(无)'))
        if not ok:
            bad += 1
            print(out[-1500:])

    # Z1/Z2
    left, out = run_check()
    ok1 = (len(left) == 0)
    print(u'%s Z1 收口：还原后 30 条全绿（实得失败 %d）' % (
        u'[PASS]' if ok1 else u'[FAIL]', len(left)))
    if not ok1:
        print(out[-1500:])
        bad += 1
    ok2 = all(sha1(p) == before[p] for p in maps)
    print(u'%s Z2 字节级还原：两个文件 sha1 与改前一致' % (u'[PASS]' if ok2 else u'[FAIL]'))
    if not ok2:
        bad += 1

    print(u'\n合计：%d 条不符合预期' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
