# -*- coding: utf-8 -*-
"""W1-3 A/B 行为对照：搬移前 vs 搬移后，跑同一条 e2e 流程，比行为轨迹。

铁律（本项目踩过，代价很贵）：**先断言 A ≠ B**。
  取"旧版本"若拿错了（例如拿了已提交的新版本），A == B，探针就退化成
  "自己跟自己比"，结论必然"没差别"**而且非常像真的**。所以：
    · 两份 main.py 的 md5 必须不同，否则直接 SystemExit；
    · 两份的 e2e 轨迹若逐字相同，要**进一步核查**这是不是"探针根本没生效"
      （假通过），而不是"行为真的等价"。

做法：把搬移前的 main.py 放回一个**临时目录**的同名位置，用同一份 e2e 驱动它。
e2e 里 `import main` 由 sys.path 决定，所以只要目录结构同构即可。
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
E2E = os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_w1_3_e2e.py')
OLD_MAIN = os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', '_evidence', 'w1_3_main_before.py')
CUR_MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')


def md5(p):
    with io.open(p, 'rb') as fh:
        return hashlib.md5(fh.read()).hexdigest()


def run_e2e(proj_root, tag):
    iso = tempfile.mkdtemp(prefix='w13_ab_%s_' % tag)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['RALSEI_MEMORY_DIR'] = os.path.join(iso, 'RalseiMemory')
    env['RALSEI_PROJECT_ROOT'] = proj_root
    p = subprocess.run([r'C:\Python311\python.exe', E2E],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env, cwd=os.getcwd())
    t = p.stdout.decode('utf-8', 'replace')
    io.open(r'E:\Download\_tmp\w13_ab_%s.txt' % tag, 'w', encoding='utf-8',
            newline='\n').write(t)
    return t, p.returncode


def trace(t):
    """只留行为轨迹行（[PASS]/[FAIL]/合计），去掉时间戳与 Qt 噪声。"""
    out = []
    for ln in t.split('\n'):
        if '[PASS]' in ln or '[FAIL]' in ln or ln.startswith('合计'):
            out.append(ln.strip())
    return out


def main():
    m_old, m_cur = md5(OLD_MAIN), md5(CUR_MAIN)
    print('旧版 main.py md5 = %s' % m_old)
    print('当前 main.py md5 = %s' % m_cur)
    if m_old == m_cur:
        print('[FATAL] 两份 main.py 相同 —— A/B 退化为自己跟自己比，拒绝出结论')
        return 2
    print('[ OK ] 两份 main.py 不同（A ≠ B 成立）')
    print()

    # A：当前（已搬移）
    ta, ea = run_e2e(ROOT, 'cur')
    # B：搬移前 —— 把旧 main.py 放回原位置（备份现场，跑完还原）
    backup = CUR_MAIN + '.ab_backup'
    shutil.copy2(CUR_MAIN, backup)
    try:
        shutil.copy2(OLD_MAIN, CUR_MAIN)
        assert md5(CUR_MAIN) == m_old, '回填失败'
        tb, eb = run_e2e(ROOT, 'old')
    finally:
        shutil.copy2(backup, CUR_MAIN)
        os.remove(backup)
    assert md5(CUR_MAIN) == m_cur, '现场还原失败！'

    A, B = trace(ta), trace(tb)
    print('A(搬移后) 轨迹 %d 行, exit=%d' % (len(A), ea))
    print('B(搬移前) 轨迹 %d 行, exit=%d' % (len(B), eb))
    print()

    # 防"探针没生效"：两份轨迹都必须是"有内容且过了若干断言"的
    if len(A) < 20 or len(B) < 20:
        print('[FATAL] 轨迹行数过少（A=%d B=%d）—— 探针可能没真正跑起来，拒绝出结论'
              % (len(A), len(B)))
        return 2

    if A == B:
        print('[ OK ] 搬移前后行为轨迹**逐行一致**（%d 行）' % len(A))
        io.open(r'E:\Download\_tmp\w1_3_ab_result.txt', 'w', encoding='utf-8',
                newline='\n').write(
            '旧版 md5 = %s\n当前 md5 = %s\nA(搬移后) %d 行 trace, exit=%d\n'
            'B(搬移前) %d 行 trace, exit=%d\n结论: 逐行一致\n\n--- trace ---\n%s\n'
            % (m_old, m_cur, len(A), ea, len(B), eb, '\n'.join(A)))
        return 0

    print('[DIFF] 行为轨迹有差异：')
    import difflib
    for ln in difflib.unified_diff(B, A, fromfile='before', tofile='after', lineterm='', n=2):
        print('  ' + ln)
    return 1


if __name__ == '__main__':
    sys.exit(main())
