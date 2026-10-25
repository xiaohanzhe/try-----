# -*- coding: utf-8 -*-
"""第113轮g · 6 人新规则验证批判读

用户口径（2026-10-25 逐字）：
  「不要过度突出个人特点，要不然会显得过于暴躁，过于柔弱等等后果，**要和正常人一样**」

## 判读方法：同角色纵向对照，绝不横比
同一个角色、同一套剧本，把**旧 prompt 那一遍**和**新 prompt 那一遍**（刚跑的 12 轮）并排。
不跨角色比 —— 角色基线差得远（asgore 天生平淡、susie 天生大声），横比只会得出
「susie 说话冲」这种废话，而它恰恰是原作设定。

★ 旧语料 36 轮、新语料 12 轮 ⇒ **旧的一律只取前 12 轮**，否则把「36 轮后段的漂移」
  算进「新规则的效果」，是拿变量比常量。

## 三条行为判据（不看均值，看逐轮）
  1. `over_rate` 过火率：新 ≤ 旧 + 0.05 视为不恶化（12 轮样本，5 个百分点不到 1 轮）
  2. `cn_ratio` 中文占比：语言崩坏的 `hy_*` 必须回到 ≥ 0.45（`gate_reply` 的硬阈值）
  3. 硬违规轮数：新规则不许把模型逼进「话说短了 ⇒ PARROT/EMPTY」这类新坑

## 一条前置判据：新规则确实在 prompt 里
直接拿当前产品代码重算一遍 system，逐句 `in` 一遍新四句（锚点从 `check113g.MUST`
用 AST 取，**不重复维护、也不 import** —— `check113g` 是模块级直接跑的，import 会当场执行）。

★★ 但**不许**拿 `len(system)` 去和语料里的 `system_chars` 比：`system_for` 会注入
   `relation_patch` / `evolution_patch`，这两份卡随训练推进一直在变（实测 toriel
   7761 对 7864，差 103 字纯粹是关系卡更新）。拿长度当判据 ＝ 把「关系卡变了」
   误报成「prompt 没换」。这是本轮抓到的一条**坏判据**，留档在此。

★★★ 数字只是入口。过火与否最后得人读几句 —— 所以脚本会打印每人**最"过火"的 2 轮原文**。
   只信汇总表不看原文，等于让判据替我阅读。

用法：
    python verify113g.py
    python verify113g.py --only mike,asgore
"""

import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common113 as C          # noqa: E402
import dialogue113 as D        # noqa: E402
import extreme113 as X         # noqa: E402

ROUND = os.path.dirname(HERE)
RAW30 = os.path.join(ROUND, '_evidence', 'raw30')
OUT = os.path.join(ROUND, '_evidence', 'verify113g.json')

#: 选角理由（写在代码里，免得下次忘了为什么是这 6 个）
PICKS = {
    'mike': '旧批次 excl=0.31，是「过火」的实证样本',
    'hy_guardener': '旧批次语言崩坏（cn_ratio 低）',
    'hy_axis': '同上，且是 1.00 过火率那批里的',
    'susie': '括号动作对 prompt 规则免疫（probe113g 10/10）',
    'asgore': 'probe113g 三变体全 10/10，最硬的免疫样本',
    'toriel': '对照：基线最稳的一个',
}

HEAD = 12   #: 新批次的轮数；旧语料按同一前缀截断，保证可比


# ---------------------------------------------------------------- 锚点
def rule_anchors():
    """从 `check113g.py` 的 `MUST` 元组取四个锚点（AST，不 import）。

    ★ 为什么不用 import：`check113g.py` 是**模块级直接跑**的回归锁（末尾还有
      `sys.exit`），import 它等于当场把 18 条判据跑一遍并退出进程。
    ★ 为什么不在这里手抄一份：抄一份就会漂 —— 产品侧改了规则，这里还拿旧锚点断言，
      结果是"全绿"，比 FAIL 危险得多。
    """
    path = os.path.join(HERE, 'check113g.py')
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == 'MUST':
                return tuple(e.value for e in node.value.elts
                             if isinstance(e, ast.Constant) and isinstance(e.value, str))
    raise RuntimeError('check113g.py 里找不到 MUST 元组')


# ---------------------------------------------------------------- 语料
def load_recs(nid):
    """该角色在 raw30 下的全部记录（可能多条：不同批次 / 不同 prompt）。"""
    path = os.path.join(RAW30, nid + '.jsonl')
    if not os.path.isfile(path):
        return []
    recs = [r for r in C.read_jsonl(path) if isinstance(r, dict)]
    recs.sort(key=lambda r: r.get('started_at') or '')
    return recs


def has_lang(rec):
    """`metrics.lang` 是第113轮后续才加的字段 ⇒ 有它＝新 prompt。"""
    return ((rec.get('metrics') or {}).get('lang') is not None)


def n_turns(rec):
    return len([t for t in (rec.get('turns') or [])
                if (t.get('final') or '').strip()])


def pick_new(recs):
    """挑出**本次验证批**那一条：轮数恰好 == `HEAD` 且是新 prompt，取最新。

    ★★★ 为什么不能只靠 `metrics.lang`（本轮踩到）：`asgore` / `berdly` 这类角色
      早在今天早些时候就按 48 轮跑过一遍（也是新 prompt、也有 lang），
      只按 lang 取最新，会把它那条 **48 轮**记录当成"本次 12 轮验证批"，
      再和旧记录的前 12 轮对比 ⇒ 硬违规 +48 轮的天量假红。
      轮数是这次批次的结构性指纹，用它比时间戳可靠（时间戳是随时相变的绝对值）。
    """
    cand = [r for r in recs if has_lang(r) and n_turns(r) == HEAD]
    return cand[-1] if cand else None


def pick_old(recs, exclude):
    """对照用的旧记录：最新的一条**不是**本次验证批的记录。"""
    old = None
    for r in recs:
        if r is exclude:
            continue
        if n_turns(r) >= 1:
            old = r
    return old


def rec_stats(rec, limit=None):
    """逐轮度量。`limit` 用于把旧语料截到与新语料同样的轮数前缀。"""
    turns = [t for t in (rec.get('turns') or [])
             if (t.get('final') or '').strip()]
    if limit:
        turns = turns[:limit]
    if not turns:
        return None
    rows, hard, retries = [], 0, 0
    for t in turns:
        txt = t.get('final') or ''
        m = X.measure(txt)
        m['hit'] = [k for k in X.SOFT_CAP if m[k] > X.SOFT_CAP[k][0]]
        m['i'] = t.get('i')
        m['chars'] = len(txt)
        m['cn'] = round(C.cn_ratio(txt), 3)
        m['paren'] = 1 if C._PAREN_RE.search(txt) else 0
        m['text'] = txt
        rows.append(m)
        if t.get('violations'):
            hard += 1
        retries += int(t.get('retries') or 0)

    n = len(rows)
    over = sum(1 for r in rows if r['hit'])
    return {
        'n': n,
        'over_turns': over,
        'over_rate': round(over / float(n), 3),
        'avg': {k: round(sum(r[k] for r in rows) / float(n), 3) for k in X.SOFT_CAP},
        'cn_rate': round(sum(r['cn'] for r in rows) / float(n), 3),
        'cn_min': min(r['cn'] for r in rows),
        'paren_turns': sum(r['paren'] for r in rows),
        'chars_avg': int(round(sum(r['chars'] for r in rows) / float(n))),
        'hard_turns': hard,
        'retries': retries,
        'rows': rows,
        'system_chars': rec.get('system_chars'),
        'started_at': rec.get('started_at'),
        'new_prompt': has_lang(rec),
    }


def system_text_now(nid, patch=''):
    """用当前产品代码重算该角色的 system 全文。

    ★★ 只回答一个问题：**当前代码产出的 prompt 里有没有新四句**。
       `len()` 不能当判据（见文件头注）。
    """
    roster, _gaps = C.load_roster()
    by_id = {c['id']: c for c in roster}
    card = D.load_card(nid, by_id)
    if not card:
        return None
    return D.system_for(card, patch)


def worst_turns(st, k=2):
    """挑「判红分量最多」的 k 轮，供人读原文。"""
    cand = [r for r in st['rows'] if r['hit']]
    cand.sort(key=lambda r: (-len(r['hit']), r['i'] if r['i'] is not None else 0))
    return cand[:k]


def _slim(st):
    if not st:
        return None
    d = dict(st)
    d.pop('rows', None)   # 原文不进 JSON（体积），要看原文跑标准输出
    return d


# ---------------------------------------------------------------- 主流程
def main(argv):
    only = None
    if '--only' in argv:
        i = argv.index('--only')
        if i + 1 < len(argv):
            only = [x.strip() for x in argv[i + 1].split(',') if x.strip()]
    ids = only or list(PICKS)
    anchors = rule_anchors()

    print('第113轮g 验证批判读｜同角色纵向对照（旧 prompt 前 %d 轮 vs 新 prompt %d 轮）'
          % (HEAD, HEAD))
    print('语料目录：%s' % RAW30)
    print('新规则锚点 %d 条（取自 check113g.MUST）：%s' % (len(anchors), ' / '.join(anchors)))

    results, verdicts = {}, []
    for nid in ids:
        recs = load_recs(nid)
        if not recs:
            print('\n[%s] 没有语料' % nid)
            verdicts.append((nid, 'SKIP', '无语料'))
            continue

        new_rec = pick_new(recs)
        if new_rec is None:
            print('\n[%s] 没有「%d 轮 + 新 prompt」的记录 ⇒ 本次验证批还没落盘，跳过'
                  % (nid, HEAD))
            verdicts.append((nid, 'SKIP', '本次验证批未落盘（现有 %d 条记录，轮数 %s）'
                             % (len(recs), [n_turns(r) for r in recs])))
            continue
        old_rec = pick_old(recs, new_rec)
        new = rec_stats(new_rec)
        old = rec_stats(old_rec, limit=HEAD) if old_rec else None
        results[nid] = {'why': PICKS.get(nid, ''), 'old': _slim(old), 'new': _slim(new)}
        if new is None:
            print('\n[%s] 最新记录没有有效轮次' % nid)
            verdicts.append((nid, 'SKIP', '无有效轮次'))
            continue
        # ★ 再兜一道：万一挑出来的仍是旧 prompt，拿它当「新」判会得出
        #   「新规则毫无变化」的假结论。
        if not new['new_prompt']:
            print('\n[%s] 最新记录 `metrics.lang` 为空 ⇒ 仍是旧 prompt（新批次未落盘），跳过'
                  % nid)
            verdicts.append((nid, 'SKIP', '最新记录仍是旧 prompt'))
            continue

        print('\n' + '=' * 78)
        print('[%s] %s' % (nid, PICKS.get(nid, '')))
        print('  新记录 %s  %d 轮  system_chars=%s'
              % (new['started_at'], new['n'], new['system_chars']))
        if old:
            print('  旧记录 %s  %d 轮  system_chars=%s（只取前 %d 轮参与对照）'
                  % (old['started_at'], n_turns(old_rec), old['system_chars'], old['n']))
        else:
            print('  旧记录：无（该角色只有这一条，无法纵向对照）')

        head = ('  %-5s %-4s %-6s %-6s %-6s %-6s %-6s %-6s %-6s %-6s %-5s %-6s %-6s'
                % ('版本', '轮', '过火率', 'excl', 'multi', 'caps', 'emph', 'ellip',
                   'apol', '中占比', '字数', '括号', '硬违规'))
        print(head)
        for label, st in (('旧', old), ('新', new)):
            if not st:
                continue
            a = st['avg']
            print('  %-5s %-4d %5.2f  %5.2f  %5.2f  %5.2f  %5.2f  %5.2f  %5.2f  %5.2f  %5d  %d/%d  %d/%d'
                  % (label, st['n'], st['over_rate'], a['excl'], a['multi'], a['caps'],
                     a['emph'], a['ellip'], a['apol'], st['cn_rate'], st['chars_avg'],
                     st['paren_turns'], st['n'], st['hard_turns'], st['n']))

        # ---- 前置判据：新四句真在 prompt 里 ----
        checks = []
        try:
            sys_txt = system_text_now(nid, (new_rec.get('patch') or ''))
        except Exception as e:      # 重算失败不许当通过
            sys_txt = None
            print('  (重算 system 失败：%r)' % (e,))
        if sys_txt is None:
            checks.append(('当前代码 prompt 含新四句', False, '重算失败，无法确认'))
        else:
            miss = [s for s in anchors if s not in sys_txt]
            checks.append(('当前代码 prompt 含新四句（%d 条）' % len(anchors),
                           not miss, ('缺：%s' % '|'.join(miss)) if miss else '齐'))
            # 信息行：与语料长度对照**不作判据**（关系卡会变），只打印备查
            print('  prompt 长度：语料记 %s ／ 当前重算 %d（差值来自 relation/evolution 卡'
                  '更新，**不作判据**）' % (new['system_chars'], len(sys_txt)))

        # ---- 行为判据 ----
        if old:
            d_over = new['over_rate'] - old['over_rate']
            checks.append(('过火率不恶化（新 ≤ 旧+0.05）', d_over <= 0.05,
                           '%+.2f（%.2f → %.2f）'
                           % (d_over, old['over_rate'], new['over_rate'])))
            d_cn = new['cn_rate'] - old['cn_rate']
            checks.append(('中文占比不恶化（≥ 旧-0.05）', d_cn >= -0.05,
                           '%+.2f（%.2f → %.2f，最低单轮 %.2f）'
                           % (d_cn, old['cn_rate'], new['cn_rate'], new['cn_min'])))
            d_hard = new['hard_turns'] - old['hard_turns']
            checks.append(('硬违规轮数不增加', d_hard <= 0, '%+d 轮' % d_hard))
        else:
            checks.append(('中文占比达标（≥0.45）', new['cn_rate'] >= 0.45,
                           '%.2f' % new['cn_rate']))

        ok_all = True
        for name, ok, detail in checks:
            print('    [%s] %-28s %s' % ('PASS' if ok else 'FAIL', name, detail))
            ok_all = ok_all and ok
        verdicts.append((nid, 'PASS' if ok_all else 'FAIL', ''))

        # ---- 原文（数字只是入口）----
        wt = worst_turns(new)
        if wt:
            print('  最「过火」的 %d 轮原文：' % len(wt))
            for r in wt:
                print('    #%s [%s] %s' % (r['i'], ','.join(r['hit']), r['text'][:70]))
        else:
            print('  没有任何一轮触碰软上限 —— 新批次逐轮读数全在线内。')

    # ---- 汇总 ----
    print('\n' + '=' * 78)
    print('汇总')
    print('  %-16s %-6s %s' % ('角色', '判定', '备注'))
    npass = nfail = nskip = 0
    for nid, st, why in verdicts:
        if st == 'PASS':
            npass += 1
        elif st == 'SKIP':
            nskip += 1
        else:
            nfail += 1
        print('  %-16s %-6s %s' % (nid, st, why))
    # ★ SKIP 不算通过。全 SKIP 时若打印「N/N 通过」，就是拿「没测」冒充「测绿」。
    print('\n结论：PASS %d / FAIL %d / SKIP %d' % (npass, nfail, nskip))
    if nfail:
        print('⇒ 有 %d 项不达标，**不要**开全量。' % nfail)
    elif nskip == len(verdicts):
        print('⇒ 全部跳过：新批次语料还没落盘，什么都判断不了。')
    else:
        print('⇒ 已判读的角色全部达标。')

    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'head': HEAD, 'anchors': list(anchors),
                   'verdicts': [{'id': a, 'verdict': b, 'why': c}
                                for a, b, c in verdicts],
                   'rows': results}, f, ensure_ascii=False, indent=1)
    print('落盘：%s' % OUT)
    if nfail:
        return 3
    return 4 if nskip == len(verdicts) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
