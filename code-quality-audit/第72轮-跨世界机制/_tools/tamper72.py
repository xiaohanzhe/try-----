# -*- coding: utf-8 -*-
"""第72轮 · 鉴别力体检：**真的把破坏写进文件**，看 check72 会不会报红。

为什么不能只用 check72 里的"内存负控制"
----------------------------------------
`check72` 的 A4n/C14 是把内存对象改一改，证明**内核函数**有鉴别力。
但那只证明"函数写对了" —— **没有**证明"真文件被人改坏时，判据会亮"。
本项目铁律：**改断言/护栏 → 鉴别力体检必须改文件**。
所以这里对着**磁盘上的真文件**动手，**包括代码文件 `npc_system.py`**。

四种破坏（每条对应一条独立判据，互不代偿）
------------------------------------------
    T1 `_registry.json`: 把 `ut_toriel` 的档位抬成 `all`      -> A4 必须报红（全域只有 Niko）
    T2 `_registry.json`: 把 `os_niko` 的档位降成 `non_dark`   -> A2/A3 必须报红
    T3 `npc_system.py` : 把 `chapters` 判空**挪到**跨作品分支之前 -> B5 必须报红（顺序）
    T4 `_crossworld.json`: 把 `twin_groups` 也记成 `wired`     -> E1 必须报红（诚实话）

★★ T3 是改**核心代码文件** ⇒ 恢复必须可证：
   备份原文（内存 + sha256）→ 改 → 跑 → **逐字节写回** → 复核 sha256 与原件相等。
   本项目已有"改坏了忘记恢复"的先例风险，所以把 sha256 比对写进结论。

用法：C:\\Python311\\python.exe tamper72.py
落盘：`_evidence/tamper72_report.json`
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
AUD = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
CROSS = os.path.join(PET, 'assets', 'npc', '_crossworld.json')
NPSYS = os.path.join(PET, 'modules', 'npc_system.py')
CHECK72 = os.path.join(HERE, 'check72.py')
PY = r'C:\Python311\python.exe'

NO_CH_IF = ("    if not npc.chapters:\n"
            "        return GateResult(False, REASON_NO_CHAPTERS,"
            " '%s 没有登记任何暗世界' % npc.name_cn)\n")


def run_check():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([PY, CHECK72], capture_output=True, cwd=ROOT, env=env,
                       timeout=300)
    out = (p.stdout or b'').decode('utf-8', 'replace')
    fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith('[FAIL]')]
    return p.returncode, fails, out


def fail_names(fails):
    """取 `[FAIL] A4 …` 里的判据名（第 1 个空格前的 token）。
    ★ 必须**精确等于**期望名：`startswith('A4')` 会把 `A4n` 也算命中。"""
    return [f.split(']', 1)[-1].strip().split(' ')[0] for f in fails]


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


# --- 破坏器：输入原文(bytes) → 输出改后(bytes)，并返回说明 -------------------
def mk_json_patch(path, mutate, desc):
    def _fn():
        raw = io.open(path, 'rb').read()
        d = json.loads(raw.decode('utf-8'))
        mutate(d)
        new = json.dumps(d, ensure_ascii=False, indent=1).encode('utf-8') + b'\n'
        return raw, new, desc
    return _fn


def t1():
    def m(d):
        for n in d['npcs']:
            if n['id'] == 'ut_toriel':
                n['roam_scope'] = 'all'
    return mk_json_patch(REG, m, 'ut_toriel 档位 non_dark -> all') ()


def t2():
    def m(d):
        for n in d['npcs']:
            if n['id'] == 'os_niko':
                n['roam_scope'] = 'non_dark'
    return mk_json_patch(REG, m, 'os_niko 档位 all -> non_dark') ()


def t3():
    """★ 改代码：把 `chapters` 判空挪到跨作品分支之前（顺序反了）。"""
    raw = io.open(NPSYS, 'rb').read()
    txt = raw.decode('utf-8')
    anchor = '    ch = scene_chapter(scene_id)\n'
    if NO_CH_IF not in txt or anchor not in txt:
        raise AssertionError('t3 锚点找不到（代码已变，请先核对锚点再体检）')
    if txt.count(NO_CH_IF) != 1:
        raise AssertionError('t3 锚点不唯一（出现 %d 次）' % txt.count(NO_CH_IF))
    new = txt.replace(anchor, NO_CH_IF + anchor, 1)     # 先插一份到前面
    # 再删掉原来那一份（此时共 2 份，删第 2 份）
    idx_first = new.find(NO_CH_IF)
    idx_second = new.find(NO_CH_IF, idx_first + 1)
    if idx_second < 0:
        raise AssertionError('t3 插入后找不到第二份，锚点逻辑需复核')
    new = new[:idx_second] + new[idx_second + len(NO_CH_IF):]
    return raw, new.encode('utf-8'), 'npc_system.py: chapters 判空挪到跨作品分支之前'


def t4():
    def m(d):
        d['wiring']['wired'] = ['roam', 'twin_groups']
    return mk_json_patch(CROSS, m, 'twin_groups 被谎记成 wired') ()


CASES = [
    ('T1', 'A4', REG, t1),
    ('T2', 'A2', REG, t2),
    ('T3', 'B5', NPSYS, t3),
    ('T4', 'E1', CROSS, t4),
]


def main():
    backups = {}
    for p in (REG, CROSS, NPSYS):
        backups[p] = io.open(p, 'rb').read()

    report = {'round': 72, 'why': '鉴别力体检必须改文件（内存负控制只证明"函数写对了"）',
              'cases': []}
    rc0, f0, _ = run_check()
    print('基线：rc=%d FAIL=%d' % (rc0, len(f0)))
    report['baseline'] = {'rc': rc0, 'fails': f0}
    ok_all = (rc0 == 0 and not f0)

    for tag, expect, path, fn in CASES:
        raw, new, desc = fn()
        with io.open(path, 'wb') as fh:
            fh.write(new)
        rc, fails, _ = run_check()
        names = fail_names(fails)
        hit = [f for f, n in zip(fails, names) if n == expect]
        good = bool(hit)
        ok_all = ok_all and good
        print('  %s %-46s -> rc=%d 报红=%s  %s'
              % (tag, desc[:46], rc, ('是' if hit else '否'),
                 ('OK' if good else '!! 未报红')))
        if hit:
            print('       %s' % hit[0][:112])
        report['cases'].append({'tag': tag, 'file': os.path.relpath(path, ROOT),
                                'tamper': desc, 'expect': expect, 'rc': rc,
                                'detected': good,
                                'fail_line': hit[0][:200] if hit else None})
        with io.open(path, 'wb') as fh:          # 立刻恢复
            fh.write(backups[path])

    # 恢复复核：逐字节
    restored = {}
    for p in (REG, CROSS, NPSYS):
        now = io.open(p, 'rb').read()
        restored[os.path.relpath(p, ROOT)] = {
            'sha_before': sha(backups[p]), 'sha_after': sha(now),
            'identical': now == backups[p]}
    print('恢复复核：%s' % json.dumps(
        dict((k, v['identical']) for k, v in restored.items()), ensure_ascii=False))
    rc_f, f_f, _ = run_check()
    print('恢复后：rc=%d FAIL=%d' % (rc_f, len(f_f)))
    same = all(v['identical'] for v in restored.values())
    ok_all = ok_all and rc_f == 0 and not f_f and same
    report['restore'] = restored
    report['after_restore'] = {'rc': rc_f, 'fails': f_f}
    report['verdict'] = 'ALL_DETECTED' if ok_all else 'SOMETHING_WRONG'
    print('== 结论 = %s ==' % report['verdict'])

    ev = os.path.join(AUD, '_evidence')
    if not os.path.isdir(ev):
        os.makedirs(ev)
    dst = os.path.join(ev, 'tamper72_report.json')
    with io.open(dst, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=1))
    print('-> %s' % dst)
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
