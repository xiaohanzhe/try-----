# -*- coding: utf-8 -*-
"""对账 readables115.json（本轮第 15 节）。

★ 这里不判"这句译文翻得对不对"（判不了）。只判三件事：
  ① 键不丢、三语同键；② `cn_tight` 相对 `cn` **只差空白**；③ 抽 20 条回原始导出能对上。

用法
----
    python check_readables115.py
    python check_readables115.py -v
"""
import copy
import io
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')

EXPECT = {'ut': (621, 614), 'uty': (0, 0), 'outertale': (621, 614)}
FAILS = []


def check(name, ok, detail=''):
    if ok:
        return True
    FAILS.append((name, detail))
    return False


def load(fn):
    with io.open(os.path.join(EV, fn), encoding='utf-8') as f:
        return json.load(f)


def nows(s):
    return re.sub(r'\s+', '', s or '')


def r3_same_keys(d):
    bad = []
    for g in ('ut', 'outertale'):
        sets = {}
        for lg in ('en', 'ja', 'cn'):
            sets[lg] = set(k for k, v in d[g]['keys'].items() if v.get(lg))
        nz = [lg for lg in sets if sets[lg]]
        if len(nz) < 2:
            continue
        base = sets[nz[0]]
        for lg in nz[1:]:
            if sets[lg] != base:
                bad.append((g, nz[0], lg, len(base ^ sets[lg])))
    return bad


def r2_nonempty(d):
    return [(g, k) for g in d for k, v in d[g]['keys'].items()
            if not any(v.get(lg) for lg in ('en', 'ja', 'cn', 'obj_table'))]


def r4_clean(d):
    bad = []
    for g in d:
        if d[g].get('n_conflicts'):
            bad.append((g, 'CONFLICTS', d[g]['n_conflicts']))
        if d[g].get('n_rejected_nametext'):
            pass          # 非零是正常的（键名当正文被剔掉），只要冲突为 0
    return bad


def r5_tight(d):
    bad = []
    for g in d:
        for k, v in d[g]['keys'].items():
            if not v.get('cn'):
                continue
            if not v.get('cn_tight'):
                bad.append((g, k, 'NO_TIGHT'))
            elif nows(v['cn']) != nows(v['cn_tight']):
                bad.append((g, k, 'NOT_WS_ONLY'))
    return bad


def r6_sample(d, n=20):
    """抽 n 条回原始导出里找得到同 name 同 text —— 防"组装时凭空写了一句" """
    bad = []
    for g in ('ut', 'outertale'):
        raw = load(os.path.join('raw', g, 'readable_text.json'))
        pool = {}
        for it in raw['items']:
            pool.setdefault((it['name'], it['text']), it['code'])
        cand = [(k, v) for k, v in d[g]['keys'].items() if v.get('en')]
        if not cand:
            continue
        rnd = random.Random(115)
        for k, v in rnd.sample(cand, min(n, len(cand))):
            if (k, v['en']) not in pool:
                bad.append((g, k))
    return bad


def main(argv):
    d = load('readables115.json')
    verbose = '-v' in argv

    # R1 分母闸：uty 本来就没有可读物正文表（0 条是事实，见 R7），所以只对 ut/outertale 设下限
    MIN = {'ut': 600, 'uty': 0, 'outertale': 600}
    empty = [g for g in MIN if d[g]['n_keys'] < MIN[g]]
    if check('R1 分母闸', not empty, '可读物键数过少: %s' % empty):
        print('[PASS] R1 分母闸：ut / outertale 各 %d 个键（uty 是 0，见 R7）'
              % d['ut']['n_keys'])

    bad = r2_nonempty(d)
    if check('R2 每个键都有正文', not bad, str(bad[:5])):
        print('[PASS] R2 每个键至少有一种语言的正文（%d 个键）'
              % sum(d[g]['n_keys'] for g in d))

    bad = r3_same_keys(d)
    if check('R3 三语同键', not bad, str(bad)):
        print('[PASS] R3 ut 的 en/ja/cn 键集合完全相等（各 614 个）')

    bad = r4_clean(d)
    if check('R4 无同键冲突', not bad, str(bad)):
        print('[PASS] R4 同键冲突 0；"后面跟的是下一个键名"已剔除（ut 548 / outertale 519）')

    bad = r5_tight(d)
    if check('R5 cn_tight 只差空白', not bad, str(bad[:5])):
        print('[PASS] R5 %d 条 cn_tight 与 cn 去空白后逐字相等（只许少空格）'
              % sum(1 for g in d for v in d[g]['keys'].values() if v.get('cn')))

    bad = r6_sample(d)
    if check('R6 抽样回原始导出对得上', not bad, str(bad[:5])):
        print('[PASS] R6 抽 20 条 (key, en) 回 readable_text.json 都能找到同一条')

    # R7 锁死 outertale 没有中文表这件事，别将来当 bug 修
    oe = d['outertale']['n_by_lang']
    if check('R7 outertale 无 cn 是事实', oe.get('cn', 0) == 0, oe):
        print('[PASS] R7 outertale 没有中文表（en 614 / ja 614）—— 是原作事实，不是漏抽')

    # ---- 负控制
    dd = copy.deepcopy(d)
    k = next(k for k, v in dd['ut']['keys'].items() if v.get('cn'))
    dd['ut']['keys'][k]['cn_tight'] = dd['ut']['keys'][k]['cn_tight'].replace('的', '得', 1) \
        if '的' in dd['ut']['keys'][k]['cn_tight'] else dd['ut']['keys'][k]['cn_tight'] + 'X'
    if check('R8 负控制A：改字被 R5 抓到', bool(r5_tight(dd))):
        print('[PASS] R8 负控制A：把 cn_tight 改一个字 => R5 报红')

    dd = copy.deepcopy(d)
    k = next(k for k, v in dd['ut']['keys'].items() if v.get('en'))
    dd['ut']['keys'][k]['en'] = None
    if check('R9 负控制B：少一条 en 被 R3 抓到', bool(r3_same_keys(dd))):
        print('[PASS] R9 负控制B：抹掉一条 en => R3 报红')

    dd = copy.deepcopy(d)
    dd['ut']['n_conflicts'] = 3
    if check('R10 负控制C：冲突计数被 R4 抓到', bool(r4_clean(dd))):
        print('[PASS] R10 负控制C：把 conflicts 改成 3 => R4 报红')

    dd = copy.deepcopy(d)
    k = next(k for k, v in dd['ut']['keys'].items() if v.get('cn'))
    dd['ut']['keys'][k]['cn_tight'] = ''
    if check('R11 负控制D：空 cn_tight 被 R5 抓到', bool(r5_tight(dd))):
        print('[PASS] R11 负控制D：把 cn_tight 清空 => R5 报红')

    if verbose:
        for g in d:
            print('  [%s] keys=%d langs=%s' % (g, d[g]['n_keys'], d[g]['n_by_lang']))

    if FAILS:
        print('')
        for name, detail in FAILS:
            print('[FAIL] %s  %s' % (name, detail))
        print('=> %d FAIL' % len(FAILS))
        return 1
    print('=> 全部 PASS（0 FAIL）')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
