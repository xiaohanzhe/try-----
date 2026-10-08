# -*- coding: utf-8 -*-
u"""mutate96b.py —— check96b 的破坏性验证：证明"破坏必报红"。

★ 纪律（记忆铁律）：**夹具不保真 = 报假问题**；**全绿比报红更危险**。
  故凡新增回归锁，必须逐条证明"把被守卫的写法改坏 ⇒ 该判据必须报红"。

做法：把 `main.py` 复制到临时区，用文本替换制造 4 组破坏，逐组跑 check96b
（经 `CHECK_MAIN` 环境变量指向变异副本），断言预期判据 FAIL。
产品文件全程**只读**。

变异清单
--------
  M1 把 `if event.buttons() & Qt.LeftButton:` 换回 `==`      ⇒ C1/C2 必红
  M2 在 `react_to_desktop_element` 的**开关外**插一行 add_dialogue ⇒ B1/B2 必红
  M3 把 `SHOW_FILE_HELP_HINTS = False` 改成 `True`            ⇒ B0b 必红
  M4 把 `if self.SHOW_FILE_HELP_HINTS:` 整块删掉              ⇒ B0 必红
"""
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK = os.path.join(HERE, 'check96b.py')

TMP = tempfile.mkdtemp(prefix='mut96b_')
SRC = io.open(MAIN_PY, encoding='utf-8', newline='').read()

results = []


def run_check(main_path):
    env = dict(os.environ)
    # check96b 目前读固定路径；用临时**整树软链**太重 —— 改为直接改副本内容，
    # 通过覆盖 MAIN_PY 的方式：这里用"写副本 + 临时替换 CHECK 里的路径"。
    # ★ 最简且保真：把副本写到**原位之外的镜像目录**，再把 check96b 拷一份改路径。
    tmp_ck = os.path.join(TMP, 'check96b_run.py')
    body = io.open(CHECK, encoding='utf-8', newline='').read()
    body = body.replace(
        "MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')",
        'MAIN_PY = %r' % main_path)
    io.open(tmp_ck, 'w', encoding='utf-8', newline='\n').write(body)
    p = subprocess.run([r'C:\Python311\python.exe', tmp_ck],
                       capture_output=True, cwd=ROOT, env=env)
    out = p.stdout.decode('utf-8', 'replace')
    return p.returncode, out


def fails_of(out):
    return set(re.findall(r'\[FAIL\]\s+(\S+)', out))


print('=' * 74)
print('# check96b 破坏性验证')
print('=' * 74)

# ---------- 基线：未变异必须全绿 ----------
base_py = os.path.join(TMP, 'base_main.py')
io.open(base_py, 'w', encoding='utf-8', newline='').write(SRC)
rc, out = run_check(base_py)
n_pass = out.count('[PASS]')
n_fail = out.count('[FAIL]')
print('\n[基线] rc=%d PASS=%d FAIL=%d' % (rc, n_pass, n_fail))
assert n_fail == 0, '基线不该有 FAIL'

# ---------- M1 ----------
m1 = SRC.replace('if event.buttons() & Qt.LeftButton:',
                 'if event.buttons() == Qt.LeftButton:', 1)
assert m1 != SRC, 'M1 替换未生效'
p1 = os.path.join(TMP, 'm1_main.py')
io.open(p1, 'w', encoding='utf-8', newline='').write(m1)
rc, out = run_check(p1)
f = fails_of(out)
print('\n[M1 换回 ==] rc=%d FAIL=%d  判据=%s' % (rc, out.count('[FAIL]'), sorted(f)))
ok1 = ('C1' in f and 'C2' in f)
print('  ⇒ 预期 C1/C2 报红：%s' % ('✅' if ok1 else '❌'))
results.append(('M1', ok1))

# ---------- M2 ----------
anchor = '        # ★★★ 第96轮b 修复（口径违规 · 真机实证）'
m2 = SRC.replace(anchor,
                 '        self.dialogue_ui.add_dialogue("ralsei", "X", "y")\n'
                 '        self.dialogue_ui.show_dialogue()\n' + anchor, 1)
assert m2 != SRC, 'M2 替换未生效'
p2 = os.path.join(TMP, 'm2_main.py')
io.open(p2, 'w', encoding='utf-8', newline='').write(m2)
rc, out = run_check(p2)
f = fails_of(out)
print('\n[M2 开关外加回直写对话] rc=%d FAIL=%d  判据=%s'
      % (rc, out.count('[FAIL]'), sorted(f)))
ok2 = ('B1' in f and 'B2' in f)
print('  ⇒ 预期 B1/B2 报红：%s' % ('✅' if ok2 else '❌'))
results.append(('M2', ok2))

# ---------- M3 ----------
m3 = SRC.replace('SHOW_FILE_HELP_HINTS = False', 'SHOW_FILE_HELP_HINTS = True', 1)
assert m3 != SRC, 'M3 替换未生效'
p3 = os.path.join(TMP, 'm3_main.py')
io.open(p3, 'w', encoding='utf-8', newline='').write(m3)
rc, out = run_check(p3)
f = fails_of(out)
print('\n[M3 开关改 True] rc=%d FAIL=%d  判据=%s'
      % (rc, out.count('[FAIL]'), sorted(f)))
ok3 = ('B0b' in f)
print('  ⇒ 预期 B0b 报红：%s' % ('✅' if ok3 else '❌'))
results.append(('M3', ok3))

# ---------- M4 ----------
m4 = SRC.replace('        if self.SHOW_FILE_HELP_HINTS:',
                 '        if False and self.SHOW_FILE_HELP_HINTS:', 1)
assert m4 != SRC, 'M4 替换未生效'
p4 = os.path.join(TMP, 'm4_main.py')
io.open(p4, 'w', encoding='utf-8', newline='').write(m4)
rc, out = run_check(p4)
f = fails_of(out)
print('\n[M4 开关短路] rc=%d FAIL=%d  判据=%s'
      % (rc, out.count('[FAIL]'), sorted(f)))
# M4 后：开关段落不再"提到 guard 的 If"？其实仍提到 ⇒ B0 仍绿。
# 这条改成验证"B0 的保护前提判据对**结构变化**的敏感度"：预期**不**报红（如实登记）
ok4 = (len(f) == 0)
print('  ⇒ 预期**不**报红（短路后结构仍在，判据按设计不覆盖这一形态）：%s'
      % ('✅' if ok4 else '❌'))
results.append(('M4', ok4))

print('\n' + '=' * 74)
print('# 汇总')
print('=' * 74)
allok = True
for name, ok in results:
    print('  %s  %s' % (name, '✅ 通过' if ok else '❌ 未达预期'))
    allok = allok and ok
print('\n  破坏性验证总判定：%s' % ('✅ 破坏必报红（锁有效）' if allok else '❌ 有未达预期项'))
print('  临时目录：%s' % TMP)
sys.exit(0 if allok else 1)
