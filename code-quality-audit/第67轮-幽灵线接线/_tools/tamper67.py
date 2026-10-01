# -*- coding: utf-8 -*-
"""tamper67：`check67` 的**鉴别力体检** —— 逐条篡改真文件 ⇒ 必须报红 ⇒ 逐字节还原。

为什么要它（本项目铁律：**"判据本身也是被测物"**）
------------------------------------------------------------------
一条判据"全绿"不等于"它在守"。只有**把破坏真写进去、并被它抓出来**，才算证明它有鉴别力
（第62/63/64轮各踩过 4 次"判据侧翻车"，见记忆 §4）。

★ 三条纪律
  ① 改前存 sha256、改后**用备份字节还原**并**再核 sha256** —— 不许"改完忘了还原"。
  ② 替换用**字节**（不做文本模式读写）⇒ 行尾（CRLF/LF）与编码一字不动。
  ③ **基线 PASS 数不写死**：只要求"篡改前全绿"，篡改后**PASS 必须下降且报红**。
     （第67轮首版把基线写成 `== 112`，加了 E33/E34 后立刻变成"判据与事实脱节"——
       本项目头号坑，见记忆 §4/§3。改成不变式后，以后加判据不用再动它。）

用法：`C:\\Python311\\python.exe code-quality-audit/第67轮-幽灵线接线/_tools/tamper67.py`
"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))     # 仓库根
# 备份目录：★ 每次新建**唯一目录**（本环境的写入通道会拒改"已存在文件"，
# 复用固定目录会在 `copy2` 时 `PermissionError`）⇒ 用时间戳新建；
# 且落在**仓内 gitignore 的 `_out/`**（不依赖外部盘 —— 铁律）。
BAK = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out',
                   'tamper67_bak_' + time.strftime('%Y%m%d_%H%M%S'))
PY = r'C:\Python311\python.exe'

FILES = {
    'main': os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    'gs': os.path.join(ROOT, 'ralsei_pet', 'modules', 'ghost_system.py'),
    'go': os.path.join(ROOT, 'ralsei_pet', 'modules', 'ghost_overlay.py'),
}

#: `expect` = **首次实测到底被哪几条抓出来**（不是"我觉得应该抓到"）。
#: ★ 判据要求**全部命中**（`all`），不是"命中一条就算过" —— 否则"期望"本身在虚报
#:   （第67轮首版把 E6 / C11 也列了进去，实测它们**不**受该处篡改影响：E6 查的是
#:   "调用点是否在所有早退分支之前"，把调用替换成 `pass` 并不改变位置；C11 查的是
#:   "振幅 ≠ 4.0"，步长 0.1→0.2 后振幅仍 ≠ 4.0）。
CASES = [
    ('1 关掉总开关',            'main', b'GHOST_ENABLED = True', b'GHOST_ENABLED = False', ['E1']),
    ('2 摘掉每帧推进调用',      'main', b'self._ghost_tick(elapsed_time)',
     b'pass  # tampered', ['E4', 'E5']),
    ('3 改暗档常量 0.6→0.5',    'gs', b'GHOST_DIM_ALPHA = 0.6', b'GHOST_DIM_ALPHA = 0.5',
     ['B7', 'C26', 'E14', 'E21']),
    ('4 偷偷把幽灵置顶',        'go', b'Qt.WindowDoesNotAcceptFocus)',
     b'Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint)', ['E8']),
    ('5 往函数里塞 import',     'gs', b'def determination(contact_seconds):',
     b'def determination(contact_seconds):\n    import os', ['A5']),
    ('6 改浮动步长 0.1→0.2',    'gs', b'GHOST_LEVITATE_STEP = 0.1', b'GHOST_LEVITATE_STEP = 0.2',
     ['B8', 'C10']),
    # ---- B5（第74轮追加）：停走式的四类破坏 ----
    # 7 把产品模式偷偷切回"定点距离式"（= B5 整条被静默回退，最像"改一行没事"的那种）
    ('7 产品模式切回定点',      'main', b'GHOST_MODE = ghost_system_mod.MODE_FOLLOW',
     b'GHOST_MODE = ghost_system_mod.MODE_FIXED', ['E19a', 'E21a', 'E35']),
    # 8 停走式步长 0.05→0.5（淡入淡出快 10 倍 —— 只在真机跑一眼才看得出的那种）
    ('8 停走式步长 0.05→0.5',   'gs', b'GHOST_FADE_STEP = 0.05', b'GHOST_FADE_STEP = 0.5',
     ['B5', 'B25', 'C32']),
    # 9 ★ 把"走动"那条**独立**的 if 改成受档位约束（最容易抄错的一处：原文它与档位无关）
    ('9 走动那条被档位约束',    'gs', b'    if moving:\n        return max(0.0, a - st)',
     b'    if moving:\n        return max(0.0, min(c, a - st))', ['C35']),
    # 10 `_follow_to` 写成"每帧 y = 目标值"（浮动被吃掉的坏写法）
    ('10 跟飘吃掉浮动',         'gs', b'            self.y = self.starty + off',
     b'            self.y = self.starty', ['C46', 'E21b']),
]


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def run():
    r = subprocess.run([PY, os.path.join(HERE, 'check67.py')],
                       cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = r.stdout.decode('utf-8', 'replace')
    npass = len(re.findall(r'\[PASS\]', txt))
    fails = re.findall(r'^\[FAIL\] (\S+)', txt, re.M)
    return npass, fails, txt


def main():
    os.makedirs(BAK, exist_ok=True)
    orig = {}
    for k, p in FILES.items():
        orig[k] = sha(p)
        shutil.copy2(p, os.path.join(BAK, k + '.py'))
    print('基线 sha256：')
    for k, p in FILES.items():
        print('  %-5s %s' % (k, orig[k]))

    npass0, fails0, _ = run()
    print('\n未篡改：PASS=%d FAIL=%s' % (npass0, fails0))
    if fails0:
        print('[!] 基线就不是全绿 —— 先查这个，不是鉴别力问题')
        return 2

    allok = True
    for name, key, pat, rep, expect in CASES:
        p = FILES[key]
        raw = io.open(p, 'rb').read()
        if pat not in raw:
            print('[SKIP] %s —— 找不到替换锚点 %r（判据/夹具对不上，按失败处理）' % (name, pat))
            allok = False
            continue
        io.open(p, 'wb').write(raw.replace(pat, rep, 1))
        try:
            npass1, fails1, txt = run()
        finally:
            shutil.copy2(os.path.join(BAK, key + '.py'), p)
        restored = sha(p) == orig[key]
        ids = {f.split()[0] if f else f for f in fails1}
        hit = [e for e in expect if e in ids]
        # ★ 必须**全部**命中（不是"命中一条就过"）—— 否则期望表在虚报。
        okc = all(e in ids for e in expect) and bool(fails1) and npass1 < npass0 and restored
        allok = allok and okc
        print('[%s] %-22s PASS %d→%d  报红=%d  命中期望=%s  还原=%s'
              % ('OK' if okc else 'BAD', name, npass0, npass1, len(fails1),
                 hit or '无', restored))
        if not okc:
            print('     实际报红：%s' % fails1[:8])

    print('\n最终还原核验：')
    for k, p in FILES.items():
        same = sha(p) == orig[k]
        allok = allok and same
        print('  %-5s %s %s' % (k, 'SAME' if same else 'DIFF!!', sha(p)))
    print('\n鉴别力体检：%s' % ('ALL OK' if allok else '有问题'))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
