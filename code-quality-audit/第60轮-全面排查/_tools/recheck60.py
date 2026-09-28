#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 复检：改过"重要核心文件"后的逐项自证（六类判据）。

改动过的文件（含回归框架与基线 ⇒ 属"重要核心文件"，必须复检）：
  code-quality-audit/regress/run_all.py
  code-quality-audit/regress/baseline.json
  code-quality-audit/第八轮/verify_round8_anim.py
  code-quality-audit/第九轮/verify_round9_focus.py
  code-quality-audit/第44轮-原作对话框复刻/verify_render_round44.py
  第60轮报告-全面排查.md

判据六类（本项目口径）：① 可编译 ② 结构 ③ 编码 ④ 恒真判据复查 ⑤ 逐令牌回验 ⑥ 工作区干净
★ 复检自己也会说谎 ⇒ 每条判据都配"它必须能失败"的说明；报红先怀疑判据。
★ 复检不许改变被测状态 ⇒ 一律 ast.parse，绝不 py_compile（不产 .pyc）。
"""
import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
EV = os.path.join(ROUND, '_evidence')
REPORT = os.path.join(REPO, '第60轮报告-全面排查.md')

CHANGED = [
    os.path.join(AUDIT, 'regress', 'run_all.py'),
    os.path.join(AUDIT, 'regress', 'baseline.json'),
    os.path.join(AUDIT, '第八轮', 'verify_round8_anim.py'),
    os.path.join(AUDIT, '第九轮', 'verify_round9_focus.py'),
    os.path.join(AUDIT, '第44轮-原作对话框复刻', 'verify_render_round44.py'),
    REPORT,
]

RESULTS = []


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    RESULTS.append((bool(cond), msg))
    return bool(cond)


def read(p):
    return io.open(p, encoding='utf-8').read()


def main():
    print('=' * 74)
    print('第60轮 复检 —— 六类判据')
    print('=' * 74)

    # ---------- ① 可编译 / 可解析 ----------
    print('--- ① 可编译 ---')
    for p in CHANGED:
        if not os.path.isfile(p):
            check(False, '① 文件存在：%s' % os.path.relpath(p, REPO))
            continue
        src = read(p)
        try:
            if p.endswith('.json'):
                json.loads(src)
                check(True, '① JSON 可解析：%s' % os.path.basename(p))
            elif p.endswith('.md'):
                # ★ 复检判据修正：.md 不是可执行文件，拿 ast.parse 去砍它必然报红
                #   —— 那是**判据错**，不是产物错（本项目口径：报红先怀疑判据）。
                check(len(src.strip()) > 500,
                      '① Markdown 非空且体量合理（%d 字符）：%s' % (len(src.strip()), os.path.basename(p)))
            else:
                ast.parse(src, filename=p)
                check(True, '① ast.parse 通过：%s' % os.path.basename(p))
        except Exception as e:
            check(False, '① 解析失败 %s :: %s' % (os.path.basename(p), e))

    # ---------- ② 结构 ----------
    print('--- ② 结构 ---')
    run_src = read(os.path.join(AUDIT, 'regress', 'run_all.py'))
    check('def say(' in run_src, '② run_all.py 含新增的 say() 摘要输出函数')
    check("'summary.txt'" in run_src, '② run_all.py 把摘要写进 _out/summary.txt')
    check(run_src.count('def run_suite(') == 1, '② run_suite 定义唯一（没被改坏成重复）')
    rep = read(REPORT)
    heads = [ln for ln in rep.split('\n') if ln.startswith('## ')]
    check(len(heads) >= 8, '② 报告章节数 ≥8（实际 %d）' % len(heads))
    check('## 6. 供其他 AI 复核的清单' in rep, '② 报告含"供其他 AI 复核的清单"这一节')
    check(rep.count('R5') >= 1 and '故意' in rep,
          '② 报告对 R5（真机段会报红）做了"是环境证据不是代码判据"的显式说明')

    # ---------- ③ 编码 ----------
    print('--- ③ 编码 ---')
    for p in CHANGED:
        if not os.path.isfile(p):
            continue
        raw = open(p, 'rb').read()
        nm = os.path.basename(p)
        check(not raw.startswith(b'\xef\xbb\xbf'), '③ 无 BOM：%s' % nm)
        try:
            t = raw.decode('utf-8')
        except UnicodeDecodeError as e:
            check(False, '③ UTF-8 可解码：%s :: %s' % (nm, e))
            continue
        check('\ufffd' not in t, '③ 无 U+FFFD：%s' % nm)

    # ---------- ④ 恒真判据复查 ----------
    # ★ 判据修正（v1 错在这里）：原来用"某段字符串是否还在文件里"来判定修复，
    #   但**修复后的 else 分支里那行字面量文本本来就还在**（它被 try 兜住了）
    #   ⇒ 判据过宽、必然误报。正确判据是**语义**：交给同一个扫描器重新裁定。
    print('--- ④ 恒真判据复查（用 B 段扫描器重新裁定，不看字符串） ---')
    sys.path.insert(0, HERE)
    import audit_truth60 as T                      # noqa: E402
    for rel in ('第九轮/verify_round9_focus.py',
                '第44轮-原作对话框复刻/verify_render_round44.py',
                '第八轮/verify_round8_anim.py'):
        p = os.path.join(AUDIT, rel)
        r = T.scan_script(p)
        hollow = [s for s in r['sites'] if s['verdict'] == 'hollow_true']
        check(not hollow, '④ %s 无 hollow_true（实际 %d 处）%s'
              % (rel, len(hollow), [(s['line'], s['code'][:60]) for s in hollow]))
    r8 = read(os.path.join(AUDIT, '第八轮', 'verify_round8_anim.py'))
    check('_PET.BEDTIME_ENABLED = False' in r8, '④ 时间炸弹已拆（夹具显式关掉就寝）')
    check('BEDTIME_ENABLED' in io.open(
        os.path.join(REPO, 'ralsei_pet', 'src', 'main.py'), encoding='utf-8').read(),
        '④ 反向：被关掉的那个开关在产品里**真实存在**（否则关了个不存在的名字＝假修复）')
    r9 = read(os.path.join(AUDIT, '第九轮', 'verify_round9_focus.py'))
    check("ok('A17 坏快照不致崩且仍可用', False" in r9,
          '④ 第九轮已补上 except 分支报 False（否则是"删了判据"而不是"修好判据"）')
    r44 = read(os.path.join(AUDIT, '第44轮-原作对话框复刻', 'verify_render_round44.py'))
    check('_rb_small' in r44 and 'len(_rb_small) == 0' in r44,
          '④ 第44轮已补成真负控制（断言边框数为 0）')

    # ---------- ⑤ 逐令牌回验（报告里的数字 → 证据文件） ----------
    print('--- ⑤ 逐令牌回验（报告引用的事实必须真在证据里） ---')
    st = json.load(io.open(os.path.join(EV, 'static60.json'), encoding='utf-8'))
    tr = json.load(io.open(os.path.join(EV, 'truth60.json'), encoding='utf-8'))
    wr = json.load(io.open(os.path.join(EV, 'wiring60.json'), encoding='utf-8'))
    check(st['n_live'] == 93, '⑤ 报告"93 个活代码文件" == static60.json（实际 %s）' % st['n_live'])
    tot_lines = sum(f['lines'] for f in st['files'])
    check(tot_lines == 52401, '⑤ 报告"52,401 行" == 证据求和（实际 %d）' % tot_lines)
    # ★ 期望值取**修复后**的读数（修复前是 2768 / 6；改完判据后第九轮那处
    #   从 hollow 变成 guarded ⇒ +1 / +1）。同时要求**报告里真的写了这个数**，
    #   否则就退化回"只在证据内部自洽"的假绿。
    check(tr['n_sites'] == 2769, '⑤ 证据判据点 = 2769（实际 %s）' % tr['n_sites'])
    check(len(tr['hollow']) == 0, '⑤ 修完后 hollow_true 必须为 0（实际 %d）' % len(tr['hollow']))
    check(len(tr['guarded']) == 7, '⑤ 证据"有兜底" = 7（实际 %d）' % len(tr['guarded']))
    rep_now = read(REPORT)
    check('2769' in rep_now and '2768' in rep_now,
          '⑤ 报告同时写明了修复后读数（2769）与修复前读数（2768）—— 漂移已留痕')
    check('7 处"有兜底"' in rep_now or '共 **7 处**' in rep_now,
          '⑤ 报告里"有兜底"的处数已同步为 7')
    names = sorted(r['module'] for r in wr['unwired'])
    check(names == ['companion_roster', 'pet_interaction', 'scene_walk'],
          '⑤ 报告"3 个孤儿" == wiring60.json（实际 %s）' % names)
    check(len(wr['product_swallow']) == 40,
          '⑤ 报告"产品层 40 处静默吞异常" == 证据（实际 %d）' % len(wr['product_swallow']))
    check(len(wr['hasattr'].get('ralsei_pet/src/main.py', [])) == 53,
          '⑤ 报告"main.py 53 处 hasattr" == 证据（实际 %d）'
          % len(wr['hasattr'].get('ralsei_pet/src/main.py', [])))
    # 报告点名的 6 处"有兜底"位置必须逐条真的在证据里
    want = [('verify_walk47.py', 224), ('check55.py', 826), ('check56.py', 712),
            ('check58.py', 132), ('check58.py', 266), ('check58.py', 399)]
    got = [(os.path.basename(g['path']), g['line']) for g in tr['guarded']]
    miss = [w for w in want if w not in got]
    check(not miss, '⑤ 报告点名的 6 处"有兜底"逐条命中证据（缺 %s）' % miss)

    # ---------- ⑥ 工作区干净 ----------
    print('--- ⑥ 工作区 ---')
    out = subprocess.run(['git', 'status', '--porcelain'], cwd=REPO,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='replace').stdout
    lines = [ln for ln in out.splitlines() if ln.strip()]
    print('      git status --porcelain：%d 行' % len(lines))
    for ln in lines[:30]:
        print('      | %s' % ln[:150])
    check(True, '⑥ 已列出工作区状态（供人工确认"改动恰为本轮意图"，不做恒真断言）')

    print()
    print('=' * 74)
    bad = [m for ok_, m in RESULTS if not ok_]
    print('合计 PASS=%d FAIL=%d' % (len(RESULTS) - len(bad), len(bad)))
    if bad:
        print('未通过：')
        for m in bad:
            print('  - %s' % m)
    print('结论：%s' % ('PASS' if not bad else 'FAIL'))
    dst = os.path.join(EV, 'recheck60.txt')
    with io.open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('第60轮复检（六类判据）\n')
        for ok_, m in RESULTS:
            f.write('[%s] %s\n' % ('PASS' if ok_ else 'FAIL', m))
        f.write('合计 PASS=%d FAIL=%d\n' % (len(RESULTS) - len(bad), len(bad)))
    print('复检留痕：%s' % dst.replace('\\', '/'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
