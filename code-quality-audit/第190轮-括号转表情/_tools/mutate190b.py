# -*- coding: utf-8 -*-
"""第190轮（续三）· 变异测试：每一种"把口径改坏"的写法，都必须被 `check190b` 抓到。

为什么变异要**落在真文件上**（而不是只调纯函数）
------------------------------------------------
`check190b` 的 B/C 两段读的是磁盘上的 7 份人设与 `_personas.json`，
纯函数级的负控制（脚本里的 D 段）证明不了"接在真文件上还灵"。
⇒ 每个变异都：备份原文 → 写坏 → 跑判据 → **整文件还原并核对 sha1**。

纪律（本项目踩过的坑，逐条对应）
--------------------------------
* 每条变异都断言 **红的条数 > 0 且 < 17**（第178轮 M3：改出语法错 ⇒ 一条 `[FAIL]` 都
  打不出来，rc=1 却"红项为空"，看着抓到了、其实什么都没证明）。
* 每条变异都写明**期望红哪几条**，实测不符就停下来看是判据错还是夹具错。
* 双跑幂等：整个脚本跑两遍，第二遍的结论必须一模一样。

用法
----
    python mutate190b.py            # 跑全部并打印汇总
    python mutate190b.py --keep     # 出错时不还原（默认一定还原）
"""
import hashlib
import io
import os
import re
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CHECK = os.path.join(HERE, 'check190b.py')
PERSONA = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', 'persona')
NP_PY = os.path.join(REPO, 'ralsei_pet', 'modules', 'npc_persona.py')
IDX_JSON = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', '_personas.json')
PY = sys.executable
BACKUP = r'D:\_tmp\mutate190b'
TOTAL = 17

NEW_A = u'"人设里提到的口头禅、习惯说法，那只是你说话的味道，不是每句话都要交的任务。"'
NEW_B = u'"先看当下在聊什么：话到那儿了自然带出来，没到就一句都不带，不用硬凑。"'


def lf(b):
    return b.replace(b'\r\n', b'\n')


def sha(b):
    return hashlib.sha1(b).hexdigest()


def run_check():
    """跑一次判据，返回 (rc, 红项列表, 原文)。"""
    r = subprocess.run([PY, CHECK], capture_output=True, cwd=REPO)
    out = r.stdout.decode('utf-8', 'replace')
    red = re.findall(r'^\[FAIL\] (\S+?)[\s（]', out, re.M)
    return r.returncode, red, out


def mutate(path, old, new, label, expect, must_hit=True):
    """在 `path` 上做一次字节级替换 → 跑判据 → 还原并核 sha1。"""
    raw = open(path, 'rb').read()
    before = sha(raw)
    # ★ 锚点两侧都按 LF 归一找位置，实际替换按字节做（源文件是 CRLF/LF 混合）
    if lf(raw).count(old.encode('utf-8')) != 1:
        print('  [夹具无效] %s：锚点在 %s 里出现 %d 次（要求恰好 1 次）'
              % (label, os.path.basename(path), lf(raw).count(old.encode('utf-8'))))
        return False
    # 用「LF 归一后替换，再按原分布还原行尾」的方式写回去：只替换一段不含换行的文本，
    # 所以直接对原始字节做同样替换即可。
    if raw.count(old.encode('utf-8')) == 1:
        payload = raw.replace(old.encode('utf-8'), new.encode('utf-8'))
    else:
        # 该片段跨越了 CRLF（极少见）：退化到 LF 归一替换，之后仍能还原（见 finally）
        payload = lf(raw).replace(old.encode('utf-8'), new.encode('utf-8'))
    ok = True
    try:
        with io.open(path, 'wb') as fh:
            fh.write(payload)
        rc, red, out = run_check()
        got = set(red)
        n_red = len(red)
        if must_hit:
            hit = [e for e in expect if e in got]
            if rc == 0 or not hit or n_red == 0 or n_red >= TOTAL:
                ok = False
                print('  [未按预期] %-46s rc=%d 红=%d 期望含 %r 实得 %r'
                      % (label, rc, n_red, expect, sorted(got)))
            else:
                print('  [抓到] %-46s 红=%d %r' % (label, n_red, sorted(got)))
        else:
            if rc != 0:
                ok = False
                print('  [误红] %-46s 红=%r' % (label, sorted(got)))
            else:
                print('  [无害] %-46s 全绿（符合预期）' % label)
    finally:
        with io.open(path, 'wb') as fh:
            fh.write(raw)
        assert sha(open(path, 'rb').read()) == before, '%s 还原失败！' % path
    return ok


def main():
    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    for p in (NP_PY, IDX_JSON):
        with io.open(os.path.join(BACKUP, '%s_%s.bak' % (os.path.basename(p), stamp)), 'wb') as fh:
            fh.write(open(p, 'rb').read())

    print('=' * 78)
    print('基线：改动前必须全绿')
    print('=' * 78)
    rc, red, _ = run_check()
    print('  rc=%d 红=%r' % (rc, sorted(red)))

    results = []
    print()
    print('=' * 78)
    print('M 变异（每条都要红，且红的是**针对的那一条**）')
    print('=' * 78)

    results.append(mutate(NP_PY, NEW_A, u'', 'M1 删掉新句 A（应 A1 红）', ['A1']))
    results.append(mutate(NP_PY, NEW_B, u'', 'M2 删掉新句 B（应 A1 红）', ['A1']))
    # M3 把新句追加到 SPEAK_RULES 末尾 ⇒ PERSONA_TONE_HUMAN 不再是后缀。
    # ★ 锚点必须唯一：那四句在文件里出现**两次**（`SPEAK_RULES` 与 `PERSONA_TONE_HUMAN`
    #   逐字相同），只取末句会命中 2 处、变异等于没做（M3 第一版就是"夹具无效"）。
    #   带上紧随其后的分节注释，才唯一落在 `SPEAK_RULES` 那一份上。
    results.append(mutate(
        NP_PY,
        u'"比如普通的一句：嗯，我知道了。那我先去看看。"\n)\n\n\n# ----'
        u'------------------------------------------------------------ 角色档位',
        u'"比如普通的一句：嗯，我知道了。那我先去看看。"\n'
        u'    "人设里提到的口头禅、习惯说法，那只是你说话的味道，不是每句话都要交的任务。"\n'
        u')\n\n\n# ---------------------------------------------------------------- 角色档位',
        'M3 新句挪到后缀之后（应 A2 红）', ['A2']))
    results.append(mutate(NP_PY, u'不是每句话都要交的任务。', u'过度，不是每句话都要交的任务。',
                          'M4 新句里塞极端词（应 A3 红）', ['A3']))
    results.append(mutate(NP_PY, u'不是每句话都要交的任务。', u'“Howdy”不是每句话都要交的任务。',
                          'M5 新句里塞逐字例句（应 A4 红）', ['A4']))
    results.append(mutate(os.path.join(PERSONA, 'ot_kidd.txt'), u'没有配额：话头到了就有',
                          u'——十次里一两次，没有配额：话头到了就有',
                          'M6 塞回精确配额（应 B1 红）', ['B1']))
    results.append(mutate(os.path.join(PERSONA, 'ut_monster_kid.txt'), u'· 你的“Yo!”没有配额',
                          u'· 不要忘记“Yo!”。你的“Yo!”没有配额',
                          'M7 塞回强化语（应 B2 红）', ['B2']))
    results.append(mutate(os.path.join(PERSONA, 'lancer.txt'), u'不是每句都带。',
                          u'。', 'M8 删掉 lancer 的行为上限（应 B3 红）', ['B3']))
    results.append(mutate(os.path.join(PERSONA, 'ot_kidd.txt'), u'比如：“嗯，好啊。”“那我们现在去吗？”',
                          u'比如：“Yo! 我们走吧。”', 'M9 中性正例换回口癖例句（应 B4 红）', ['B4']))
    results.append(mutate(IDX_JSON, u'"chars": 9349', u'"chars": 9399',
                          'M10 索引 chars 与磁盘脱钩（应 C1 红）', ['C1']))

    print()
    print('=' * 78)
    print('N 无害变异（**不该**红：证明判据不是"看什么都红"）')
    print('=' * 78)
    # ★ 第一版拿"人设里加两个字"当无害变异 —— 实测红 C1，而那是**正确**的：
    #   改了人设字节却没重算 `_personas.json`，两层登记必然打架。
    #   无害变异要挑"判据的论域之外"：这里改 `npc_persona.py` 的一条注释。
    results.append(mutate(NP_PY, u'#: 说话方式约束（**所有 NPC 共用一份**',
                          u'#: 说话方式约束（**所有 NPC 共用同一份**',
                          'N1 改一条注释（论域外，不该红）', [], must_hit=False))

    print()
    print('=' * 78)
    print('汇总：%d/%d 符合预期' % (sum(1 for r in results if r), len(results)))
    if not all(results):
        print('★ 有不符合预期的变异 —— 先判断是判据错、还是夹具错（别直接放宽判据）')
    print('=' * 78)
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
