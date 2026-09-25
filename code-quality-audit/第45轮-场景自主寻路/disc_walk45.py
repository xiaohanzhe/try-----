# -*- coding: utf-8 -*-
"""第45轮 · 鉴别力体检（对 scene_walk / verify_walk45 的判据做"故意破坏"测试）

铁律：**鉴别力体检必改文件**。只在内存里改参数不算 —— 要真改盘上文件、
跑断言、看它报红，再还原。任何一条"破坏了却不报红"的判据 = 恒真判据 = 必须修。

★ 本版更新（第 45 轮收尾）：把原「破坏2 SAFETY_PAD=0」**撤掉**了。
  原因不是判据恒真，而是**破坏手法已失效**：修完 `simplify_collinear` 保行走、
  首尾插入、`_nearest_free_visible` 三处后，`SAFETY_PAD` 已**不再是防穿模的
  必要防线**（实测五章 2376 组：pad=3 与 pad=0 的穿模数都是 0）。
  ⇒ 它现在的唯一作用是"让走位离墙远一点（观感）"，没有判据能守住它。
  换成两个**对应本轮真 bug** 的破坏：首尾替换改回、去掉保行走简化。
"""
import os
import re
import shutil
import subprocess
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MOD = os.path.join(REPO, 'ralsei_pet', 'modules', 'scene_walk.py')
VERIFY = os.path.join(REPO, 'code-quality-audit', '第45轮-场景自主寻路', 'verify_walk45.py')
PY = r'C:\Python311\python.exe'
BAK = MOD + '.disc_bak'

# 每项：(名字, 要替换的原文, 替换成, 期望"哪些断言报红"的关键词)
CASES = [
    ('破坏1 主bbox高度改成 38（回到错误语义）',
     'PLAYER_BBOX_H = 13', 'PLAYER_BBOX_H = 38',
     ['C5', 'C6b']),
    ('破坏2 首尾由"插入"改回"替换"（抹掉已验证的起终点->格心短段）',
     '    pts = [(sx, sy)] + pts + [(gx, gy)]',
     '    pts[0] = (sx, sy)\n    pts[-1] = (gx, gy)',
     ['G2', 'G3']),
    ('破坏3 blocks_at 恒返回 False（穿墙也不报）',
     '    bx = anchor_x + off_x\n    by = anchor_y + off_y',
     '    bx = anchor_x + off_x\n    by = anchor_y + off_y\n    return False',
     ['C4a', 'C5b']),
    ('破坏4 A* 找不到路时返回穿墙直线（不返回 None）',
     "    if cells is None:\n        out['reason'] = 'A* 找不到通路（障碍把目标隔开了）'\n        return out",
     '    if cells is None:\n        cells = [s, g]',
     ['D7', 'D8']),
    ('破坏5 平滑不再回退（直接返回 chaikin 结果）',
     '    if bailed or len(out) < 2:\n        return list(points)\n    return out',
     '    return smoothed',
     ['E13d', 'E13e']),
    ('破坏6 简化不再校验可走性（回到"按共线性删点"的旧行为）',
     '    pts = simplify_collinear(pts, align=step * 0.35, obstacles=obstacles,\n                             bbox_w=bbox_w, bbox_h=bbox_h, step=step)',
     '    pts = simplify_collinear(pts, align=step * 0.35)',
     # ★ 实测只有 G4 能抓到（ch5#64）：G 段"每间房 1 组"的随机采样恰好漏过，
     #   这正是 G4"深度判据"存在的理由。
     ['G4']),
]


def run_verify():
    p = subprocess.run([PY, VERIFY], capture_output=True, text=True, encoding='utf-8',
                       cwd=REPO, errors='replace')
    return p.stdout or ''


def main():
    src = open(MOD, encoding='utf-8').read()
    shutil.copy2(MOD, BAK)
    base = run_verify()
    m = re.search(r'RESULT: PASS=(\d+) FAIL=(\d+)', base)
    if not m:
        print('[FATAL] 基线跑不出 RESULT')
        return 1
    base_pass, base_fail = int(m.group(1)), int(m.group(2))
    print('基线: PASS=%d FAIL=%d' % (base_pass, base_fail))
    if base_fail != 0:
        print('[FATAL] 基线不干净，先修好再体检')
        return 1

    ok = True
    for name, old, new, expect_kw in CASES:
        if old not in src:
            print('[SKIP] %s —— 找不到替换锚点（判据可能已漂）' % name)
            ok = False
            continue
        broken = src.replace(old, new, 1)
        open(MOD, 'w', encoding='utf-8', newline='\n').write(broken)
        out = run_verify()
        m2 = re.search(r'RESULT: PASS=(\d+) FAIL=(\d+)', out)
        fails = m2.group(2) if m2 else '?'
        # 收集 FAIL 行
        fail_lines = [ln for ln in out.splitlines() if ln.startswith('[FAIL]')]
        hit = [kw for kw in expect_kw if any(kw in ln for ln in fail_lines)]
        got = 'FAIL=%s' % fails
        if fail_lines and hit:
            print('[PASS] %s -> 报红 %d 条，命中期望 %s' % (name, len(fail_lines), hit))
        elif fail_lines:
            print('[WARN] %s -> 报红了（%d 条）但没命中期望关键词 %s' % (name, len(fail_lines), expect_kw))
            for ln in fail_lines[:6]:
                print('        %s' % ln)
        else:
            print('[FAIL] %s -> **完全没有报红** ⇒ 相关判据是恒真判据！' % name)
            ok = False
        # 还原
        open(MOD, 'w', encoding='utf-8', newline='\n').write(src)

    # 最终还原 + 复跑确认
    shutil.copy2(BAK, MOD)
    os.remove(BAK)
    final = run_verify()
    m3 = re.search(r'RESULT: PASS=(\d+) FAIL=(\d+)', final)
    print()
    print('还原后: %s' % (m3.group(0) if m3 else '跑不出'))
    if not m3 or m3.group(2) != '0':
        print('[FAIL] 还原后回归未全绿')
        ok = False
    print('=== 鉴别力体检: %s ===' % ('PASS' if ok else 'HAS ISSUE'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
