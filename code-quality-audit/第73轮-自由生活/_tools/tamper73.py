# -*- coding: utf-8 -*-
"""第73轮 · 鉴别力体检（**真改文件**）。

为什么要动真文件
----------------
内存里的负控制只能证明"**函数写对了**"，证明不了"**真文件被改坏时判据会亮**"。
本项目第64轮已经吃过这个亏 ⇒ 一律对着**磁盘上的真文件**动手，改完立刻恢复，
并**逐字节**（sha256）核对恢复成功。

六个破坏点（每个都对准一条判据）
--------------------------------
  T1 `npc_life.TRAIT_WORDS_CN['dark']` 改一个词   → A3 中文词表与契约逐字镜像
  T2 `SEED_SAME_AU_TWIN` 0.55 → 0.9               → A4 初值与契约逐值相等
  T3 `_token_hits` 退回**朴素子串**匹配            → C3 负控制（ash 会命中 afterthrash2）
  T4 把被禁的 `room` 塞回 `TRAIT_TOKENS['quiet']`  → D1 本位令牌"必须在现网命中/不许是禁词"
  T5 契约里 `visitor.status` 改成 `wired`          → check72 E4 + check73 F1（不许跟着翻绿）
  T6 main.py 的 `npc_system_prompt` 去掉 `life=`    → B6/B7/E5（生活块永远进不了 prompt）

用法：`python tamper73.py [--keep]`（`--keep` = 不恢复，调试用）。
"""
from __future__ import print_function

import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE = os.path.join(PET, 'modules', 'npc_life.py')
MAIN = os.path.join(PET, 'src', 'main.py')
CROSS = os.path.join(PET, 'assets', 'npc', '_crossworld.json')
CHECK73 = os.path.join(HERE, 'check73.py')
CHECK72 = os.path.join(ROOT, 'code-quality-audit', '第72轮-跨世界机制', '_tools', 'check72.py')
PY = r'C:\Python311\python.exe'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        h.update(fh.read())
    return h.hexdigest()


def read_text(p):
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def write_text(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def run_check(script):
    r = subprocess.run([PY, script], cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    fails = [l for l in out.split('\n') if l.startswith('[FAIL]')]
    return r.returncode, fails


NAIVE_MATCHER = '''def _token_hits(token, text):
    """（体检临时版：朴素子串）"""
    if not token:
        return False
    return token in (text or '').lower()
'''


def _tamper_matcher(src):
    """把 `_token_hits` 的函数体换成朴素子串版（保留签名与后面的代码）。"""
    i = src.find('def _token_hits(')
    if i < 0:
        return None
    j = src.find('\ndef ', i + 5)
    if j < 0:
        j = len(src)
    return src[:i] + NAIVE_MATCHER + src[j:]


TASKS = [
    ('T1', 'npc_life.TRAIT_WORDS_CN 的 dark 改一个词 ⇒ A3 镜像判据报红',
     LIFE, lambda s: s.replace("'dark': ('黑', '暗',", "'dark': ('乌漆嘛黑', '暗',", 1),
     None),
    ('T2', 'L.SEED_SAME_AU_TWIN 0.55 → 0.9 ⇒ A4 逐值相等报红',
     LIFE, lambda s: s.replace('SEED_SAME_AU_TWIN = 0.55', 'SEED_SAME_AU_TWIN = 0.9', 1),
     None),
    ('T3', '`_token_hits` 退回朴素子串 ⇒ C3 负控制报红（ash 命中 afterthrash2）',
     LIFE, _tamper_matcher, None),
    ('T4', '把禁词 `room` 塞回 `TRAIT_TOKENS[quiet]` ⇒ D1/D3 报红',
     LIFE, lambda s: s.replace("'quiet': ('home', 'house', 'forest'",
                               "'quiet': ('home', 'house', 'room', 'forest'", 1),
     None),
    ('T5', '契约里 `visitor.status` 改成 wired ⇒ 诚实判据报红（不许跟着翻绿）',
     CROSS, lambda s: s.replace('"visitor": {\n    "status": "spec_only"',
                                '"visitor": {\n    "status": "wired"', 1),
     CHECK72),
    ('T6', 'main.py 的 `npc_system_prompt` 去掉 `life=` ⇒ 端到端生活块断线报红',
     MAIN, lambda s: s.replace("            npc.name, persona, entries, npc_id, "
                               "self._build_npc_context(npc_id),\n"
                               "            life=self._npc_life_blocks(npc_id))",
                               "            npc.name, persona, entries, npc_id, "
                               "self._build_npc_context(npc_id))", 1),
     None),
]


def main():
    keep = '--keep' in sys.argv
    targets = {LIFE, MAIN, CROSS}
    before = {p: sha(p) for p in targets}
    print('---- 体检开始（真改文件）----')
    for p, h in before.items():
        print('  before %-14s %s' % (os.path.basename(p), h[:16]))

    results = []
    ok_all = True
    for tid, desc, path, mut, also in TASKS:
        orig = read_text(path)
        new = mut(orig)
        if new is None or new == orig:
            print('[FAIL] %s 夹具**没改进去**（锚点没命中）%s' % (tid, desc))
            results.append((tid, desc, 'FIXTURE_MISS', -1, None))
            ok_all = False
            continue
        write_text(path, new)
        try:
            rc, fails = run_check(CHECK73)
            rc2 = 0
            if also:
                rc2, _ = run_check(also)
            hit = (rc != 0) or (also and rc2 != 0)
            print('%s %s rc=%d%s' % ('[PASS]' if hit else '[FAIL]', desc, rc,
                                     (' rc72=%d' % rc2) if also else ''))
            for l in fails[:4]:
                print('        %s' % l[:150])
            # ★ 落 rc 时把"第二套判据"的 rc 一并带上：T5 靠 check72 报红，
            #   只记 check73 的 rc=0 会让证据自我矛盾（看着像漏检）。
            results.append((tid, desc, 'DETECTED' if hit else 'MISSED', rc,
                            rc2 if also else None))
            ok_all = ok_all and hit
        finally:
            if not keep:
                write_text(path, orig)

    print('')
    print('---- 恢复核对（sha256 逐字节）----')
    for p, h in before.items():
        now = sha(p)
        same = (now == h)
        print('  %s %-14s %s' % ('[OK]  ' if same else '[FAIL]',
                                 os.path.basename(p), now[:16]))
        ok_all = ok_all and same

    if not keep:
        rc, _ = run_check(CHECK73)
        print('  恢复后复跑 check73 rc=%d' % rc)
        ok_all = ok_all and (rc == 0)

    print('')
    print('==== ALL_DETECTED=%s ====' % ok_all)
    # 落盘证据（与 tamper71 / tamper72 同形）
    ev = os.path.join(HERE, '..', '_evidence')
    try:
        if not os.path.isdir(ev):
            os.makedirs(ev)
        rep = {'round': 73, 'all_detected': bool(ok_all),
               'tasks': [{'id': t, 'desc': d, 'result': r, 'rc': rc,
                          'rc_alt': ra,
                          'rc_alt_suite': ('check72' if ra is not None else '')}
                         for (t, d, r, rc, ra) in results],
               'sha256_before': before,
               'sha256_after': {p: sha(p) for p in targets},
               'restored_byte_exact': all(sha(p) == h for p, h in before.items())}
        with io.open(os.path.join(ev, 'tamper73_report.json'), 'w',
                     encoding='utf-8', newline='\n') as fh:
            import json as _json
            _json.dump(rep, fh, ensure_ascii=False, indent=1)
            fh.write('\n')
        print('-> _evidence/tamper73_report.json')
    except Exception as e:
        print('!! 报告落盘失败: %r' % (e,))
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
