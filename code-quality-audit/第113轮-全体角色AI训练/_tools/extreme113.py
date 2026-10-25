# -*- coding: utf-8 -*-
"""第113轮g：把「性格过火」变成可测量的东西（v2，修掉 v1 判据过宽）。

用户口径（2026-10-25 逐字）：
  「不要过度突出个人特点，要不然会显得过于暴躁，过于柔弱等等后果，**要和正常人一样**」

v1 栽在哪（原始输出留档）：
  v1 的复合判据是「任一分量 > P90」。而 `apol`(道歉) 与 `multi`(连续重复标点) 的 P90
  都撞到地板值 0 ⇒ **出现一次就判过火**（正常人也会说一句「抱歉」）⇒ 判据过宽，
  `ot_alphys` 嫌疑率 1.00 里混着大量误伤。
  ⇒ v2 改为**有语义的软上限**（下表每一条都能一句话解释），并把它显式打印出来接受复查。

数据口径（v2 新增）：
  同一角色若有多条语料（不同批次/不同 prompt 版本），**只取 `started_at` 最新的一条**，
  否则会把旧版本的毛病算到新版本头上（本批 asgore 84 轮 / berdly 66 轮就是叠了两批）。

★★ 这不是硬闸，是体检表。真要做闸得先用这份分布说话，而不是拍一个阈值上去。
"""

import io
import json
import glob
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
EV = os.path.join(HERE, '..', '_evidence')
# ★★★ 第113轮g 更正：本目录下有**两批**语料，别只看一批就下结论 ——
#   `raw/`    = 每人 **4 轮** × **77 人**（第113轮第一遍，10-24 凌晨，早期 schema）
#   `raw30/`  = 每人 **36 轮** × 目前 **48 人**（升级版，10-24 16:11 之后）
#   两批都扫，同角色按 `started_at` 取最新的一条 ⇒ 覆盖 77 人且每人用最佳证据。
RAW_DIRS = [
    (os.path.join(EV, 'raw'), 'raw(4轮/人)'),
    (os.path.join(EV, 'raw30'), 'raw30(36轮/人)'),
]
OUT = os.path.join(EV, 'extreme113.json')

RE_EXCL = re.compile(r'[!！]')
RE_MULTI = re.compile(r'([!！?？])\1+')
#: ★ 6+ 而不是 4+：`Howdy`(5) / `NICO`(4) 这类名字与缩写不是「吼」，
#:   用 4+ 会把正常英文词也算成整段大写（v2 首跑：P90=0.143 而上限 0 ⇒ 人人判红）。
RE_CAPS = re.compile(r'[A-Z]{6,}')
RE_SENT = re.compile(r'[。！？!?；;\n]+')

#: ★ 不放裸「太」：`不太确定` / `不像` 里那个「太」是**减弱**语气，不是强调。
#:   v2 首跑就是被它误伤（正控制 5 条正常台词判红 1 条 ⇒ 鉴别力 FAIL）。
#:   漏掉「太累了」这类单字强调是可接受的代价 —— 本表是体检表，宁可漏报不可误报。
EMPH = ('超级', '真的', '绝对', '根本', '简直', '完全', '特别',
        '非常', '极其', '死活', '压根', '到底', '偏偏', '非要', '太过')
APOL = ('对不起', '抱歉', '我错了', '我不该', '是我不好', '别生气',
        '我没事', '算了', '都怪我', '不好意思')

#: 软上限：**每一条都能一句话解释**，且是「正常人偶尔会碰、系统性地超就是演过头」的位置。
#: 数值按「每句」或「每轮」计，见 `unit`。
SOFT_CAP = {
    'excl': (0.75, '每句', '每句都带感叹号 = 靠吼叫撑情绪；正常人只在真激动时用'),
    'multi': (1.0, '每轮', '一轮里最多一处「！！」；再多就是漫画式夸张'),
    'caps': (0.5, '每句', '每两句最多一个 6+ 字母的大写词；成片大写 = 一直在吼'),
    'emph': (0.5, '每句', '每两句最多一次「超级/绝对/根本」；句句加码 = 用强度冒充性格'),
    'ellip': (1.5, '每句', '每句最多一个半「……」；通篇省略号 = 柔弱/欲言又止演过头'),
    'apol': (0.5, '每句', '每两句最多一次道歉；句句自责 = 过度卑微'),
}


def measure(text):
    t = text or ''
    n_sent = max(1, len(RE_SENT.findall(t)))
    return {
        'excl': round(len(RE_EXCL.findall(t)) / float(n_sent), 3),
        'multi': len(RE_MULTI.findall(t)),
        'caps': round(len(RE_CAPS.findall(t)) / float(n_sent), 3),
        'emph': round(sum(t.count(w) for w in EMPH) / float(n_sent), 3),
        'ellip': round((t.count('……') + t.count('...')) / float(n_sent), 3),
        'apol': round(sum(t.count(w) for w in APOL) / float(n_sent), 3),
    }


def percentile(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round((len(s) - 1) * p))))
    return s[k]


def pick_latest(files):
    """同一 id 多条语料只留 started_at 最新的那条（避免混版本）。
    返回 best: id -> ((started_at, fp), (dict, fp))；dropped: [(id, 丢弃的, 保留的)]"""
    best = {}
    dropped = []
    for fp in files:
        with io.open(fp, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                cid = d.get('id') or os.path.basename(fp)[:-6]
                cur = (d.get('started_at') or '', fp)
                if cid not in best:
                    best[cid] = (cur, (d, fp))
                    continue
                prev = best[cid][0]
                if cur[0] >= prev[0]:
                    dropped.append((cid, prev[0], cur[0]))
                    best[cid] = (cur, (d, fp))
                else:
                    dropped.append((cid, cur[0], prev[0]))
    return best, dropped


def main():
    files = []
    for d, label in RAW_DIRS:
        got = sorted(glob.glob(os.path.join(d, '*.jsonl')))
        files.extend(got)
        print('  源 %-16s %3d 个文件' % (label, len(got)))
    if not files:
        print('!! 没有语料：%s' % [d for d, _ in RAW_DIRS])
        return 2
    print('合计语料文件 %d 个' % len(files))
    best, dropped = pick_latest(files)
    print('→ 去重后角色 %d 个（同角色多条只留 `started_at` 最新的一条，丢弃 %d 条）'
          % (len(best), len(dropped)))
    for cid, old, new in dropped[:6]:
        print('   丢弃 %-16s %s（保留 %s）' % (cid, old, new))

    print('\n软上限表（可复查：每个数值都对应一句解释）')
    print('  %-6s %-6s %-6s %s' % ('分量', '上限', '单位', '为什么是这个位置'))
    for k, (cap, unit, why) in SOFT_CAP.items():
        print('  %-6s %-6s %-6s %s' % (k, cap, unit, why))

    per_char, all_rows = {}, []
    for cid, (_key, (d, fp)) in best.items():
        # ★★★ 批次标记：`metrics.lang` 是第113轮后续才加的字段 ⇒
        #   有它 = 新 prompt（含「用简体中文说话」「每句话本身也要短」等条款）；
        #   没有它 = 旧 prompt。**两批的 system_chars 实测差数百字，不能混着下结论。**
        m0 = d.get('metrics') or {}
        has_lang = m0.get('lang') is not None
        ts = []
        for t in d.get('turns') or []:
            txt = t.get('final') or ''
            if not txt.strip():
                continue
            m = measure(txt)
            m['i'] = t.get('i')
            ts.append(m)
            all_rows.append(m)
        if ts:
            per_char[cid] = {'name': d.get('name_cn') or d.get('name'), 'turns': ts,
                             'has_lang': has_lang,
                             'system_chars': d.get('system_chars'),
                             'started_at': d.get('started_at')}

    if not all_rows:
        print('!! 没有有效轮次 —— 度量无从谈起')
        return 2
    print('\n有效角色 %d / 有效轮次 %d' % (len(per_char), len(all_rows)))

    p90 = {k: percentile([r[k] for r in all_rows], 0.90) for k in SOFT_CAP}
    print('\n全体 P90（相对离群参考，与软上限互为印证）')
    print('  %-6s %-8s %-8s' % ('分量', 'P90', '软上限'))
    for k in SOFT_CAP:
        print('  %-6s %-8s %-8s' % (k, p90[k], SOFT_CAP[k][0]))

    rows = []
    for cid, rec in per_char.items():
        ts = rec['turns']
        n = len(ts)
        avg = {k: round(sum(t[k] for t in ts) / float(n), 3) for k in SOFT_CAP}
        over, worst = 0, {}
        for t in ts:
            hit = [k for k in SOFT_CAP if t[k] > SOFT_CAP[k][0]]
            if hit:
                over += 1
                for k in hit:
                    worst[k] = worst.get(k, 0) + 1
        rows.append({'id': cid, 'name': rec['name'], 'turns': n, 'avg': avg,
                     'over_turns': over, 'over_rate': round(over / float(n), 3),
                     'worst': worst, 'has_lang': rec['has_lang'],
                     'system_chars': rec['system_chars'],
                     'started_at': rec['started_at']})

    new_rows = [r for r in rows if r['has_lang']]
    old_rows = [r for r in rows if not r['has_lang']]
    print('\n★★★ 批次拆分（`metrics.lang` 是第113轮后续才加的字段 ⇒ 有它=新 prompt）')
    print('  新 prompt：%d 个角色' % len(new_rows))
    print('  旧 prompt：%d 个角色（**别拿这批下当前结论**，它没有中文/短句那几条规则）'
          % len(old_rows))
    for label, rs in (('新', new_rows), ('旧', old_rows)):
        sc = [r['system_chars'] for r in rs if r['system_chars']]
        if sc:
            print('  %s批次 system_chars 范围 %d~%d' % (label, min(sc), max(sc)))

    header = ('  %-20s %-5s %-7s %-6s %-6s %-6s %-6s %-6s %s'
              % ('角色', '轮', '过火率', 'excl', 'multi', 'caps', 'emph', 'ellip',
                 'apol / 主因'))

    def dump(title, rs):
        print('\n%s' % title)
        if not rs:
            print('  （空）')
            return
        rs = sorted(rs, key=lambda r: -r['over_rate'])
        print(header)
        for r in rs:
            a = r['avg']
            cause = max(r['worst'].items(), key=lambda kv: kv[1])[0] if r['worst'] else '-'
            print('  %-20s %-5d %5.2f   %5.2f  %5.2f  %5.2f  %5.2f  %5.2f  %5.2f  %s'
                  % (r['id'], r['turns'], r['over_rate'], a['excl'], a['multi'],
                     a['caps'], a['emph'], a['ellip'], a['apol'], cause))

    dump('★ 新 prompt 批次（含中文/短句规则）—— **这才代表当前表现**', new_rows)
    dump('旧 prompt 批次（仅供参考，不能据此下结论）', old_rows)

    # ---- 鉴别力自证：负控制（两个极端）+ 正控制（正常句）----
    print('\n===== 鉴别力自证 =====')
    rage = '你到底想干什么！！！我受够了！每次都这样！根本没人听我说话！！'
    meek = '对不起……都是我的错……我不该说话的……对不起对不起……算了，我没事……'
    normal = '今天有点累。我先歇会儿，等下再说。'
    ok = True
    for label, sample, must in (('暴怒样本', rage, True), ('柔弱样本', meek, True),
                                ('正常样本', normal, False)):
        m = measure(sample)
        hit = [k for k in SOFT_CAP if m[k] > SOFT_CAP[k][0]]
        print('  %-6s excl=%.2f multi=%d caps=%.2f emph=%.2f ellip=%.2f apol=%.2f ⇒ %s'
              % (label, m['excl'], int(m['multi']), m['caps'], m['emph'],
                 m['ellip'], m['apol'], hit or '（无）'))
        if bool(hit) != must:
            ok = False
            print('     !! 期望 %s，实际 %s' % ('判红' if must else '不判红',
                                              '判红' if hit else '不判红'))
    # 正控制：正常台词批量喂进去必须几乎不判红（防「上限过紧 ⇒ 人人过火」）
    normal_batch = ['今天有点累。我先歇会儿，等下再说。',
                    '嗯，好啊。你说的那个我也想过。',
                    '外面在下雨。你带伞了吗？',
                    '我明白了。那我明天再来一趟。',
                    '这个我不太确定，得问问别人。']
    nb_over = sum(1 for s in normal_batch
                  if any(measure(s)[k] > SOFT_CAP[k][0] for k in SOFT_CAP))
    print('  正控制：%d 条正常台词里判红 %d 条（应为 0）' % (len(normal_batch), nb_over))
    if nb_over:
        ok = False
    print('  鉴别力结论：%s' % ('PASS' if ok else 'FAIL —— 度量不可信，结论作废'))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'soft_cap': {k: v[0] for k, v in SOFT_CAP.items()},
                   'soft_cap_note': {k: {'unit': v[1], 'why': v[2]}
                                     for k, v in SOFT_CAP.items()},
                   'p90': p90, 'rows': rows, 'files': len(files),
                   'chars': len(per_char), 'turns': len(all_rows),
                   'dropped_old_batches': len(dropped),
                   'selfcheck': {'rage': measure(rage), 'meek': measure(meek),
                                 'normal': measure(normal),
                                 'normal_batch_over': nb_over}},
                  f, ensure_ascii=False, indent=1)
    print('\n落盘：%s' % OUT)
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
