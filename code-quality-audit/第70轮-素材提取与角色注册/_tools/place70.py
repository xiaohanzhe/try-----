# -*- coding: utf-8 -*-
"""第70轮 · 把 26 位新注册 NPC 如实挂进 `_placement.json` 的 `unplaced`。

为什么必须做（不是形式主义）
--------------------------
第56轮的站位表有一条**三表对齐**硬判据（`code-quality-audit/第56轮-NPC站位与游荡/check56.py`）：

    check('D6 站位 ∪ 未安置 == 注册表（一个不少一个不多）', ...)

第70轮把注册表 70 → 96 之后，26 位新人既不在 `placement` 也不在 `unplaced`
⇒ D6 立刻报红（实测 `缺=[26 个 id] 多=[]`）。这不是判据太严，是**真缺口**。

口径（**逐字沿用第66轮对 OneShot / Undertale 那 35 条的处理，不另立一套**）
----------------------------------------------------------------------------
`unplaced` 的既有写法是「**不属于 Deltarune 的任何房间** ⇒ 没有 `obj_npc_*` 站位脚本，
也没有原作坐标可抄 ⇒ 如实挂在"未安置"，**不给他编一个安身之所**」。
黄魂与 Outertale 的角色同理 —— 它们不是 Deltarune 角色，本项目也还没做它们的房间
（`chapters=['undertale_yellow']` / `['outertale']` 只是"未来场景前缀锚"，当前没有对应场景）。

⇒ 本轮**只补 `unplaced` 理由**，不给任何一位编坐标（编了就是假的）。

★ 不新增顶层键
-------------
`check56` 有一条**键集精确相等**的判据（`set(RAW.keys()) == {...}`）
⇒ 本轮只改 `unplaced` 与 `counts` 两个既有键，连"round70"备注都不加；
   本轮的为什么写在**本文件 + 报告 + `_evidence/`** 里。

用法
----
    C:\\Python311\\python.exe -X utf8 place70.py            # dry
    C:\\Python311\\python.exe -X utf8 place70.py --write
"""
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.join(HERE, '..', '..', '..')
EV = os.path.join(ROUND, '_evidence')
N = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')

DO_WRITE = '--write' in sys.argv
FAIL = 0
LINES = []

WORK_CN = {'undertale_yellow': '《Undertale Yellow》', 'outertale': '《Outertale》'}
ROUND_NO = '70'

#: 逐字沿用第66轮的句式（只换作品名与轮次）
TEMPLATE = ('{work} 角色（第{rn}轮注册）：**不属于 Deltarune 的任何房间** '
            '⇒ 没有 `obj_npc_*` 站位脚本，也没有原作坐标可抄 '
            '⇒ 如实挂在"未安置"，不给他编一个安身之所。')


def w(s=''):
    print(s)
    LINES.append(str(s))


def ok(m):
    w('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    w('[FAIL] %s' % m)


def main():
    reg_p = os.path.join(N, '_registry.json')
    pl_p = os.path.join(N, '_placement.json')
    reg = json.loads(io.open(reg_p, 'rb').read().decode('utf-8'))
    reg_ids = [r['id'] for r in reg['npcs']]
    raw = json.loads(io.open(pl_p, 'rb').read().decode('utf-8'))
    unpl = raw['unplaced']
    pl_ids = [x['id'] for x in raw['placement']]

    w('注册表 %d 条 / 站位 %d 条 / 未安置 %d 条' % (len(reg_ids), len(pl_ids), len(unpl)))
    w('')

    already = set(pl_ids) | set(unpl)
    todo = [i for i in reg_ids
            if i not in already and i.split('_')[0] in ('hy', 'ot')]
    unexpected = [i for i in reg_ids if i not in already and i not in todo]
    w('待补进 unplaced（hy_/ot_）= %d 条' % len(todo))
    if unexpected:
        bad('还有既不在 placement 也不在 unplaced 的 id：%s' % unexpected)

    # 只补指定前缀的，且**逐条**要求能在注册表里找到作品
    by_id = {r['id']: r for r in reg['npcs']}
    new = collections.OrderedDict()
    for i in todo:
        chs = by_id[i].get('chapters') or []
        slug = chs[0] if chs else None
        if slug not in WORK_CN:
            bad('%s 的 chapters=%r 不在 %s 里' % (i, chs, sorted(WORK_CN)))
            continue
        new[i] = TEMPLATE.format(work=WORK_CN[slug], rn=ROUND_NO)
    w('')
    for i in list(new)[:3]:
        w('   %-22s :: %s' % (i, new[i]))
    w('   ...（共 %d 条）' % len(new))

    merged = collections.OrderedDict(list(unpl.items()) + list(new.items()))
    counts = collections.OrderedDict(raw['counts'])
    counts['unplaced'] = len(merged)

    w('')
    w('合并后 unplaced = %d 条（%d + %d）' % (len(merged), len(unpl), len(new)))
    w('counts.unplaced: %s → %s' % (raw['counts'].get('unplaced'), counts['unplaced']))

    # ---- 自检：三表对齐 ----
    if set(pl_ids) | set(merged) == set(reg_ids):
        ok('D6 预检：站位 ∪ 未安置 == 注册表（%d 条）' % len(reg_ids))
    else:
        bad('D6 预检失败：缺=%s 多=%s'
            % (sorted(set(reg_ids) - set(pl_ids) - set(merged)),
               sorted((set(pl_ids) | set(merged)) - set(reg_ids))))
    dlt = sorted(i for i in merged if i.split('_')[0] not in ('os', 'ut', 'hy', 'ot'))
    if dlt == ['knight']:
        ok('D7 预检：Deltarune 侧未安置的仍只有 knight（实得 %s）' % dlt)
    else:
        bad('D7 预检失败：Deltarune 侧未安置 = %s（应只有 knight）' % dlt)
    empt = [i for i, v in merged.items() if not (v or '').strip()]
    if not empt:
        ok('理由非空：%d 条全部有解释' % len(merged))
    else:
        bad('理由为空的：%s' % empt)

    if DO_WRITE and not FAIL:
        raw['unplaced'] = merged
        raw['counts'] = counts
        t = json.dumps(raw, ensure_ascii=False, indent=1)
        with io.open(pl_p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(t)
        w('')
        w('★ 已写盘 _placement.json（%d 字节）' % len(t.encode('utf-8')))
        back = json.loads(io.open(pl_p, 'rb').read().decode('utf-8'))
        if len(back['unplaced']) == len(merged) and back['counts'] == counts:
            ok('回读一致：unplaced=%d counts=%s' % (len(back['unplaced']), dict(back['counts'])))
        else:
            bad('回读不一致')
        if set(back.keys()) == set(raw.keys()):
            ok('顶层键集未变（%d 个）' % len(back.keys()))
    elif DO_WRITE:
        w('!! 有 FAIL，未写盘')

    out = os.path.join(EV, 'place70.txt')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(LINES) + '\n')
    w('')
    w('落盘 %s' % out)
    w('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
