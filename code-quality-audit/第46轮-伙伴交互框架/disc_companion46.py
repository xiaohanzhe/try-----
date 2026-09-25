# -*- coding: utf-8 -*-
"""第46轮 · 鉴别力体检（对 companion / companion_dialog / companion_roster 做"故意破坏"测试）

铁律：**鉴别力体检必改文件**。只在内存里改参数不算 —— 要真改盘上文件、
跑断言、看它报红，再还原。任何一条"破坏了却不报红"的判据 = 恒真判据 = 必须修。

★ 备份落点：`%TEMP%\\_disc_bak46\\`，**不落工作区**。
  原因（memory 铁律）：备份文件落在 `ralsei_pet/modules/` 下会被 `git add -A`
  当成新文件提交；万一脚本中途崩掉，一个 `<mod>.disc_bak` 就永久留在仓库里
  （本仓库已经有过这种残留：`desktop_interaction.py.discrim_bak`）。
  放临时目录 ⇒ 即使崩了也不会污染仓库。

★ 两个容易自欺的地方（本文件特意防了）：
  1. **破坏手法本身可能失效**（改的位置被紧邻的 `return` 吞掉）⇒ 所以每项都要
     填写"期望命中的断言关键词"，报红了但没命中期望 = 也要当问题看；
  2. 体检跑完必须**再跑一次原始状态**确认全绿，否则可能"改坏了没还原"。
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
VERIFY = os.path.join(REPO, 'code-quality-audit', '第46轮-伙伴交互框架',
                      'verify_companion46.py')
PY = r'C:\Python311\python.exe'
BAK_DIR = os.path.join(tempfile.gettempdir(), '_disc_bak46')

# 每项：(模块文件名, 名字, 要替换的原文, 替换成, 期望"哪些断言报红"的关键词)
CASES = [
    ('companion.py', '破坏1 trace 缓冲长度 25 → 12（假造一个更小的环缓冲）',
     'TRACE_LEN = 25', 'TRACE_LEN = 12', ['B1', 'C5']),
    ('companion.py', '破坏2 跟随滞后基准 12 → 11（差一帧）',
     'FOLLOW_LAG_BASE = 12', 'FOLLOW_LAG_BASE = 11', ['B2', 'C1']),
    ('companion.py', '破坏3 sample_at 改回 "差一帧" 写法（trace[-lag]）',
     '        return self.trace[-(lag + 1)]', '        return self.trace[-lag]',
     ['C6']),
    ('companion.py', '破坏4 交互防抖 5 → 0 帧（不再防抖）',
     'INTERACT_COOLDOWN_FRAMES = 5', 'INTERACT_COOLDOWN_FRAMES = 0', ['B5']),
    ('companion.py', '破坏5 异常路径不解锁（拿锁就再也不还）',
     '        else:\n            self.myinteract = self.MYINTERACT_IDLE\n'
     '            self.bus.release(self)\n        return opened',
     '        else:\n            self.myinteract = self.MYINTERACT_IDLE\n        return opened',
     ['D9b']),
    ('companion_dialog.py', '破坏6 缺 from_id 不再拒（偷偷补一个说话人）',
     "            if not frm:\n                return False, 'missing_from'",
     "            if not frm:\n                frm = 'kris'", ['E2', 'H2']),
    ('companion_dialog.py', '破坏7 format_line 允许裸文本（无前缀直接返回正文）',
     '    if not frm:\n        label = UNKNOWN_SPEAKER',
     '    if not frm:\n        return msg.text', ['F3', 'F6']),
    ('companion_dialog.py', '破坏8 代他人发言检测恒返回空（永远查不出）',
     '    tokens = _name_tokens(name_index)', '    tokens = []', ['G1', 'G2']),
    ('companion_dialog.py', '破坏9 自称混乱检测恒返回空（永远查不出）',
     '    for claim in _SELF_CLAIM:', '    for claim in ():', ['G6', 'G9c']),
    ('companion_dialog.py', '破坏10 DialogueLog 不校验就入库（脏数据进历史）',
     '        if not ok:\n            return self._reject(msg, reason)',
     '        if not ok:\n            ok = True', ['H2']),
    ('companion_roster.py', '破坏11 resolve 找不到时"就近凑"一个伙伴',
     '        sid = self._alias.get(n)\n        if sid is None:\n            return None',
     '        sid = self._alias.get(n)\n        if sid is None:\n'
     '            return next(iter(self._by_id.values()), None)',
     ['I4']),
    ('companion_roster.py', '破坏12 别名冲突时静默覆盖（后者吃掉前者）',
     "        if conflicts:\n            return False, 'alias_conflict:%s' "
     "% ','.join(conflicts)",
     '        if conflicts:\n            pass', ['I1d', 'I1e']),
    ('companion_roster.py', '破坏13 tick 去掉 busy 闸门（允许并发）',
     '        if self._busy:\n            return None',
     '        if False:\n            return None', ['J1']),
    ('companion_roster.py', '破坏14 轮转恒取第一个人（自问自答 / 一人刷屏）',
     # ⚠️ 首版这里改的是 `start = i + 1` → `start = 0`，**完全不报红** ——
     #    不是判据恒真，而是**破坏手法失效**：真正在守"不许自己接自己"的是
     #    下面那句 `if c.speaker_id != self._last_from`，`start` 只影响找起点的
     #    效率。要破坏就得破坏真正的守卫。
     '        n = len(members)\n'
     '        for k in range(n):\n'
     '            c = members[(start + k) % n]\n'
     '            if c.speaker_id != self._last_from:\n'
     '                return c\n'
     '        return None',
     '        n = len(members)\n'
     '        return members[0]',
     ['J2']),
    ('companion_roster.py', '破坏15 去掉反活锁闸门（失败后无限重试）',
     '        if self._fail_count >= MAX_CONSECUTIVE_FAILURES:',
     '        if False:', ['J8b']),
    ('companion_roster.py', '破坏16 FREE 模式也强行跟随（自主行动没了）',
     '        if c.mode not in (FollowMode.FOLLOW, FollowMode.RALLY):\n            continue',
     '        if False:\n            continue', ['K4']),
    ('companion_roster.py', '破坏17 主角不在场也判 FOLLOW（跟一个不存在的人）',
     '    if not leader_present:\n        mode = FollowMode.FREE',
     '    if not leader_present:\n        mode = FollowMode.FOLLOW', ['K7']),
]


def run_verify():
    p = subprocess.run([PY, VERIFY], capture_output=True, text=True,
                       encoding='utf-8', cwd=REPO, errors='replace')
    return p.stdout or ''


def main():
    if not os.path.isdir(BAK_DIR):
        os.makedirs(BAK_DIR)
    srcs = {}
    for name in ('companion.py', 'companion_dialog.py', 'companion_roster.py'):
        p = os.path.join(MODS, name)
        srcs[name] = io.open(p, encoding='utf-8').read()
        shutil.copy2(p, os.path.join(BAK_DIR, name))

    base = run_verify()
    m = re.search(r'RESULT: PASS=(\d+) FAIL=(\d+)', base)
    if not m:
        print('[FATAL] 基线跑不出 RESULT')
        return 1
    print('基线: PASS=%s FAIL=%s' % (m.group(1), m.group(2)))
    if m.group(2) != '0':
        print('[FATAL] 基线不干净，先修好再体检')
        for ln in base.splitlines():
            if ln.startswith('[FAIL]'):
                print('   %s' % ln)
        return 1

    ok = True
    for mod, name, old, new, expect_kw in CASES:
        src = srcs[mod]
        if old not in src:
            print('[SKIP] %s —— 找不到替换锚点（判据可能已漂）' % name)
            ok = False
            continue
        broken = src.replace(old, new, 1)
        if broken == src:
            print('[SKIP] %s —— 替换后内容没变（破坏手法失效）' % name)
            ok = False
            continue
        path = os.path.join(MODS, mod)
        io.open(path, 'w', encoding='utf-8', newline='\n').write(broken)
        out = run_verify()
        fail_lines = [ln for ln in out.splitlines() if ln.startswith('[FAIL]')]
        hit = [kw for kw in expect_kw if any(kw in ln for ln in fail_lines)]
        if fail_lines and hit:
            print('[PASS] %s -> 报红 %d 条，命中期望 %s' % (name, len(fail_lines), hit))
        elif fail_lines:
            print('[WARN] %s -> 报红了（%d 条）但没命中期望 %s' % (name, len(fail_lines), expect_kw))
            for ln in fail_lines[:6]:
                print('        %s' % ln)
            ok = False
        else:
            print('[FAIL] %s -> **完全没有报红** ⇒ 相关判据是恒真判据！' % name)
            ok = False
        io.open(path, 'w', encoding='utf-8', newline='\n').write(src)

    # 最终还原（用备份覆盖，确保和磁盘原始字节一致）+ 复跑确认
    for name in srcs:
        shutil.copy2(os.path.join(BAK_DIR, name), os.path.join(MODS, name))
    final = run_verify()
    m3 = re.search(r'RESULT: PASS=(\d+) FAIL=(\d+)', final)
    print()
    print('还原后: %s' % (m3.group(0) if m3 else '跑不出'))
    if not m3 or m3.group(2) != '0':
        print('[FAIL] 还原后回归未全绿')
        ok = False

    # 逐字节确认还原 = 原始
    diff = []
    for name in srcs:
        cur = io.open(os.path.join(MODS, name), encoding='utf-8').read()
        if cur != srcs[name]:
            diff.append(name)
    print('还原字节一致: %s' % (not diff))
    if diff:
        ok = False

    print('=== 鉴别力体检: %s ===' % ('PASS' if ok else 'HAS ISSUE'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
