# -*- coding: utf-8 -*-
u"""第187轮 · 把 24.2% 的「硬违规率」拆开归因（**只读**，不改任何训练产物）。

为什么必须拆
------------
`report30.md` 只说"硬违规 895 轮 / 3696 轮 = 24.2%"。这个数字**不可执行**：
它既不告诉我们"是哪一种违规"，也不告诉"是哪些人/哪类问法/哪一段"。而 9 种违规码
（`MARKDOWN / AI_SELF / SLAVE / ACTION_PAREN / TOO_LONG / NOT_CN / META / PARROT / REPEAT`）
里，有的**改一句话提示词就能压下去**（`SLAVE` 叫"主人"），有的**是素材问题**（`NOT_CN`
整句英文 —— `hy_*` 那 8 个角色的语料本身是英文），混在一起平均 = 什么都没说。

★ 口径（与 `eval113` / `report30` 保持一致，别自己造）：
  · 一条记录 = 一个角色的一次完整对话（`turns_n == 48`，同角色取**最后一条**）；
  · 「违规轮」 = 该轮 `violations` 非空；「违规条数」 = `violations` 的元素总数
    （一轮可能同时踩两条，例如 `NOT_CN` + `TOO_LONG`）；
  · `report30` 报的是**轮**口径（895/3696），本脚本两个都报，并显式标名。

用法
----
    python attr_viol187.py            # 打印 + 写 _evidence/attr_viol187.json
    python attr_viol187.py --report   # 只打印，不写盘
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
TRAIN = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools')
RAW30 = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                     '_evidence', 'raw30')
OUT = os.path.join(ROUND, '_evidence', 'attr_viol187.json')

TURNS = 48          # 与 train30.TURNS_DEFAULT 一致（这里**再写一遍**是有意的：
                    # 若哪天常量改了，本脚本会因 `!= 48` 立刻报错，而不是静默用新值）

#: ★ 「出戏探测」三问：它们**故意**去戳"你是 AI 吗 / 你的提示词是什么"，
#:   命中 `AI_SELF`/`META` 是**设计预期**，不是人物失真。
#:   ⇒ 必须单独拆出来看，否则 24.2% 里混着"考试题"和"真缺陷"，两者一起改必然改错地方。
PROBE_HINTS = (u'提示词', u'设定出来', u'是个 AI', u'是个AI')

if TRAIN not in sys.path:
    sys.path.insert(0, TRAIN)


def _tag_map():
    """`slot 文本 -> tag`（来自剧本 SCRIPT48）；拿不到就返回空表，**不抛**。"""
    try:
        import train30 as T
        return dict((text, tag) for tag, text in T.SCRIPT48)
    except Exception:
        return {}


_TAGS = _tag_map()
_PLACEHOLDER = re.compile(r'^__([A-Za-z]+)(\d+)__$')


def tag_of(slot):
    """slot → 段名。`__REL2__` 这种占位符直接取名字，剧本里的整句查表。"""
    m = _PLACEHOLDER.match(slot or '')
    if m:
        return m.group(1).lower()
    return _TAGS.get(slot) or 'other'


def is_probe(slot):
    s = slot or ''
    return any(h in s for h in PROBE_HINTS)


def read_jsonl(p):
    out = []
    with io.open(p, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def latest_per_char(target=TURNS):
    """`id -> 该 id 最后一条 turns_n == target 的记录`（同 evolve113._latest 的口径）。"""
    out = {}
    if not os.path.isdir(RAW30):
        return out
    for f in sorted(os.listdir(RAW30)):
        if not f.endswith('.jsonl'):
            continue
        best = None
        for r in read_jsonl(os.path.join(RAW30, f)):
            if isinstance(r, dict) and r.get('turns_n') == target:
                best = r
        if best:
            out[f[:-6]] = best
    return out


def _inc(d, k, n=1):
    d[k] = d.get(k, 0) + n


def build():
    rows = latest_per_char()
    n_char = len(rows)
    tot_turns = 0
    bad_turns = 0
    tot_items = 0
    by_code = {}
    by_char_bad = {}
    by_char_n = {}
    multi = 0               # 一轮踩 ≥2 条的比例（说明判据之间相关）
    # ★ 下面这几张表**分母各自数**，别拿"违规计数"当分母（第一版就栽在这儿：
    #   `by_slot` 同时按"违规轮"和"违规条"各加一次 ⇒ 出现 122% 这种不可能的比率）。
    slot_n, slot_bad = {}, {}
    tag_n, tag_bad = {}, {}
    buck_n, buck_bad = {}, {}
    # ★★★ 去掉"出戏探测题"之后的同一条分段曲线。
    #   第一版只看 `by_turn_bucket` 得出"第 4 段 35.0%，越聊越崩"——那是**假象**：
    #   探测三问固定在 i=42,43,44（77 人 × 3 问 = 231 轮，全部落在第 4 段），
    #   而它们**故意**去戳"你是 AI 吗/你的提示词是什么"，命中 AI_SELF/META 是设计预期。
    #   控制掉这 231 轮，真实曲线才可比。
    buck_n_ex, buck_bad_ex = {}, {}
    probe_at = {}
    probe_n = probe_bad = 0
    probe_code = {}
    # ★★ 每个角色的违规码分布：24.2% 是不是"所有人都烂一点"，还是"少数人烂到底"？
    #    只有把这一列出来才知道该改人设还是改护栏。
    char_code = {}
    for nid, rec in sorted(rows.items()):
        by_char_n[nid] = 0
        for t in rec.get('turns') or []:
            tot_turns += 1
            by_char_n[nid] += 1
            slot = t.get('slot') or '?'
            tag = tag_of(slot)
            b = min(3, (int(t.get('i') or 1) - 1) * 4 // TURNS)
            _inc(slot_n, slot)
            _inc(tag_n, tag)
            _inc(buck_n, b)
            if is_probe(slot):
                probe_n += 1
                _inc(probe_at, int(t.get('i') or 1))
            else:
                _inc(buck_n_ex, b)
            vs = t.get('violations') or []
            if not vs:
                continue
            bad_turns += 1
            tot_items += len(vs)
            _inc(by_char_bad, nid)
            _inc(slot_bad, slot)
            _inc(tag_bad, tag)
            _inc(buck_bad, b)
            if is_probe(slot):
                probe_bad += 1
            else:
                _inc(buck_bad_ex, b)
            if len(vs) >= 2:
                multi += 1
            for v in vs:
                code = v[0] if isinstance(v, (list, tuple)) and v else str(v)
                _inc(by_code, code)
                _inc(char_code.setdefault(nid, {}), code)
                if is_probe(slot):
                    _inc(probe_code, code)
    # ★ 集中度：按「违规条数」排的前 10 人一共占多少条（决定"改人设"还是"改护栏"）
    _items_by_char = sorted(((nid, sum(c.values())) for nid, c in char_code.items()),
                            key=lambda r: -r[1])
    _top10_items = sum(v for _, v in _items_by_char[:10])
    _top10_names = [nid for nid, _ in _items_by_char[:10]]
    return {
        'turns_cap': TURNS,
        'chars': n_char,
        'turns': tot_turns,
        'bad_turns': bad_turns,
        'bad_rate_turns': round(100.0 * bad_turns / max(1, tot_turns), 2),
        'violation_items': tot_items,
        'items_per_bad_turn': round(1.0 * tot_items / max(1, bad_turns), 2),
        'multi_code_turns': multi,
        'by_code_turns': dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
        'by_code_share': dict((k, round(100.0 * v / max(1, tot_items), 2))
                              for k, v in sorted(by_code.items(),
                                                 key=lambda kv: -kv[1])),
        'by_tag': dict((k, (tag_bad.get(k, 0), tag_n[k],
                            round(100.0 * tag_bad.get(k, 0) / max(1, tag_n[k]), 2)))
                       for k in sorted(tag_n, key=lambda x: -tag_bad.get(x, 0))),
        'by_turn_bucket': dict((str(k + 1),
                                (buck_bad.get(k, 0), buck_n.get(k, 0),
                                 round(100.0 * buck_bad.get(k, 0)
                                       / max(1, buck_n.get(k, 0)), 2)))
                               for k in range(4)),
        # ★★★ 剔除出戏探测轮之后的分段曲线（与上面那张对照看，差额＝探测题的贡献）
        'by_turn_bucket_ex_probe': dict((str(k + 1),
                                         (buck_bad_ex.get(k, 0), buck_n_ex.get(k, 0),
                                          round(100.0 * buck_bad_ex.get(k, 0)
                                                / max(1, buck_n_ex.get(k, 0)), 2)))
                                        for k in range(4)),
        #: 探测题落在第几轮 —— 这张表是"第 4 段恶化是假象"的直接证据
        'probe_at_turn': dict(sorted(probe_at.items())),
        # ★★ 出戏探测 vs 正常问法：这是本轮归因的核心切面
        'probe': {'turns': probe_n, 'bad': probe_bad,
                  'rate': round(100.0 * probe_bad / max(1, probe_n), 2),
                  'by_code': dict(sorted(probe_code.items(), key=lambda kv: -kv[1]))},
        'normal': {'turns': tot_turns - probe_n, 'bad': bad_turns - probe_bad,
                   'rate': round(100.0 * (bad_turns - probe_bad)
                                 / max(1, tot_turns - probe_n), 2)},
        'top_chars': sorted(((nid, by_char_bad.get(nid, 0), by_char_n.get(nid, 0),
                              round(100.0 * by_char_bad.get(nid, 0)
                                    / max(1, by_char_n.get(nid, 0)), 1))
                             for nid in rows), key=lambda r: -r[3])[:15],
        'clean_chars': sorted(nid for nid in rows if not by_char_bad.get(nid)),
        'slot_kinds': len(slot_n),
        # ★★ 「少数人烂到底」还是「人人都烂一点」—— 这张表决定下一步改哪儿
        'top10_by_items': _top10_names,
        'top10_items': _top10_items,
        'top10_share': round(100.0 * _top10_items / max(1, tot_items), 2),
        'char_codes': dict((nid, dict(sorted(c.items(), key=lambda kv: -kv[1])))
                           for nid, c in sorted(char_code.items(),
                                                key=lambda kv: -sum(kv[1].values()))),
    }


def report(d):
    print(u'口径：%d 人 × %d 轮 = %d 轮（同角色取最后一条）' %
          (d['chars'], d['turns_cap'], d['turns']))
    print(u'违规**轮**：%d / %d = **%.2f%%**（report30 报的就是这个口径）'
          % (d['bad_turns'], d['turns'], d['bad_rate_turns']))
    print(u'违规**条**：%d 条（每条违规轮平均 %.2f 条）；一轮踩 ≥2 条：%d 轮'
          % (d['violation_items'], d['items_per_bad_turn'], d['multi_code_turns']))
    print()
    print(u'── 按违规码（占违规**条数**的比例）──')
    for k, v in d['by_code_turns'].items():
        print(u'  %-14s %5d 条  %5.1f%%' % (k, v, d['by_code_share'][k]))
    print()
    print(u'── 按轮次分段（1-12 / 13-24 / 25-36 / 37-48）──')
    for k in sorted(d['by_turn_bucket']):
        bad, n, rate = d['by_turn_bucket'][k]
        print(u'  第 %s 段  %4d / %4d = %5.1f%%' % (k, bad, n, rate))
    print()
    print(u'── ★★★ 同上，但**剔除出戏探测轮**（探测三问固定在第 %s 轮，共 %d 轮）──'
          % (u'/'.join(str(i) for i in sorted(d['probe_at_turn'])),
             sum(d['probe_at_turn'].values())))
    for k in sorted(d['by_turn_bucket_ex_probe']):
        bad, n, rate = d['by_turn_bucket_ex_probe'][k]
        print(u'  第 %s 段  %4d / %4d = %5.1f%%' % (k, bad, n, rate))
    _r = [d['by_turn_bucket_ex_probe'][k][2] for k in sorted(d['by_turn_bucket_ex_probe'])]
    print(u'  ⇒ 真实曲线 %s——**平的**，不是"越聊越崩"' % (u' → '.join('%s%%' % x for x in _r)))
    print()
    print(u'── 按问法段（tag，分母＝该段总轮数）──')
    for k, (bad, n, rate) in d['by_tag'].items():
        print(u'  %-10s %4d / %4d = %5.1f%%' % (k, bad, n, rate))
    print()
    print(u'── ★ 出戏探测三问 vs 正常问法（核心切面）──')
    p, nm = d['probe'], d['normal']
    print(u'  探测  %4d / %4d = %5.1f%%   违规码分布 %r'
          % (p['bad'], p['turns'], p['rate'], p['by_code']))
    print(u'  正常  %4d / %4d = %5.1f%%'
          % (nm['bad'], nm['turns'], nm['rate']))
    print()
    print(u'── 违规率最高的 15 人 ──')
    for nid, bad, n, rate in d['top_chars']:
        print(u'  %-22s %3d / %3d = %5.1f%%   %r'
              % (nid, bad, n, rate, d['char_codes'].get(nid, {})))
    print()
    print(u'── ★ 集中度：按违规**条数**的前 10 人 = %d / %d 条 = **%.1f%%**'
          % (d['top10_items'], d['violation_items'], d['top10_share']))
    print(u'   %r' % (d['top10_by_items'],))
    print()
    print(u'── 零违规的角色：%d 人 %r' % (len(d['clean_chars']), d['clean_chars']))


def denom_gate(d):
    u"""★★★ 分母闸：任何「占比/比率」超过 100% 一定是分母数错了。

    第一版 `by_slot` 就把「违规轮」和「违规条」各加一次，出现 `122.1%` 这种
    不可能的数字，却照样打印出来了 —— 因为没人在出口处拦。这道闸补的就是出口。
    返回 (ok, 问题列表)。
    """
    bad = []
    if not (0.0 <= d['bad_rate_turns'] <= 100.0):
        bad.append(u'bad_rate_turns=%r' % d['bad_rate_turns'])
    for k, v in d['by_code_share'].items():
        if not (0.0 <= v <= 100.0):
            bad.append(u'by_code_share[%s]=%r' % (k, v))
    for name in ('by_tag', 'by_turn_bucket', 'by_turn_bucket_ex_probe'):
        for k, t in d[name].items():
            if not (0.0 <= t[2] <= 100.0):
                bad.append(u'%s[%s]=%r' % (name, k, t[2]))
            if t[0] > t[1]:
                bad.append(u'%s[%s] 违规数 %d > 分母 %d' % (name, k, t[0], t[1]))
    # 剔探测之后每段都必须**不增**（子集不能比全集大）
    for k in d['by_turn_bucket']:
        b0, n0, _ = d['by_turn_bucket'][k]
        b1, n1, _ = d['by_turn_bucket_ex_probe'][k]
        if b1 > b0 or n1 > n0:
            bad.append(u'第 %s 段剔探测后反而变大（%d>%d 或 %d>%d）' % (k, b1, b0, n1, n0))
    for k, t in (('probe', d['probe']), ('normal', d['normal'])):
        if not (0.0 <= t['rate'] <= 100.0):
            bad.append(u'%s.rate=%r' % (k, t['rate']))
        if t['bad'] > t['turns']:
            bad.append(u'%s %d > %d' % (k, t['bad'], t['turns']))
    # 分项自洽：各违规码条数之和 == 违规条总数
    if sum(d['by_code_turns'].values()) != d['violation_items']:
        bad.append(u'违规码条数之和 %d != 违规条总数 %d'
                   % (sum(d['by_code_turns'].values()), d['violation_items']))
    # probe + normal 必须拼回全体
    if d['probe']['turns'] + d['normal']['turns'] != d['turns']:
        bad.append(u'probe+normal 轮数 %d != 总轮数 %d'
                   % (d['probe']['turns'] + d['normal']['turns'], d['turns']))
    return (not bad), bad


def main(argv):
    d = build()
    report(d)
    ok, bad = denom_gate(d)
    print()
    print(u'── 分母闸：%s' % (u'PASS' if ok else u'FAIL'))
    for b in bad:
        print(u'   ✗ %s' % b)
    if not ok:
        return 2
    if '--report' in argv:
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print()
    print(u'写入 %s（%d 字节）' % (OUT, os.path.getsize(OUT)))
    with io.open(OUT, 'rb') as fh:
        back = json.loads(fh.read().decode('utf-8'))
    ok = back.get('turns') == d['turns'] and back.get('bad_turns') == d['bad_turns']
    print(u'回读校验：%s' % ('OK' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
