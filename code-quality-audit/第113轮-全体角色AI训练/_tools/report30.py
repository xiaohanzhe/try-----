# -*- coding: utf-8 -*-
"""第113轮b · 30 轮训练汇总报告（可在训练**跑到一半**时执行，看进度用）

输出 `_evidence/report30.md`，包含：
  · 总体：完成人数 / 总轮数 / 总耗时 / 硬违规率
  · 逐角色表：违规轮、口癖命中、记忆回指、态度同质、系统提示长度
  · 四个专项榜单（这是用户点名的四件事）：
      性格（违规轮最多的） / 记忆（回指命中最低的） / 口癖（命中率最低的）
      / 对他人态度（同质对数最多的）
  · 一份"待写纠正句"名单（判红的角色，附具体坏样本）

★ 口径：只取 `turns_n == 目标轮数` 的最后一条记录（试跑留下的短记录不算完成）。
"""
import json
import os
import sys
import time

import common113 as C
import train30 as T

TARGET = 36   # 30 轮基线 + 6 轮剧情记忆（用户 2026-10-24 追加口径）


def load_all(target=TARGET):
    rows = []
    if not os.path.isdir(T.RAW30):
        return rows
    for f in sorted(os.listdir(T.RAW30)):
        if not f.endswith('.jsonl'):
            continue
        best = None
        for r in C.read_jsonl(os.path.join(T.RAW30, f)):
            if isinstance(r, dict) and r.get('turns_n') == target:
                best = r
        if best:
            # ★★★ 判据后算：jsonl 里存着**训练当时**那份 `metrics`。一旦判据改过
            #   （比如回望判定从三态补到四态），读旧 metrics 就会让报告永远停在旧口径上——
            #   2026-10-24 就踩过：补了词表，报告数字纹丝不动，差点当成"改判据没用"。
            #   ⇒ 一律从 `turns` 用**当前** metrics_of 重算；原始数据才是真源。
            best['metrics'] = T.metrics_of(best.get('turns') or [],
                                           best.get('voice_markers') or [])
            rows.append(best)
    return rows


def main(argv):
    target = int(argv[argv.index('--turns') + 1]) if '--turns' in argv else TARGET
    rows = load_all(target)
    roster, gaps = C.load_roster()
    total_people = len(roster)

    if not rows:
        print('还没有任何完成的 %d 轮记录' % target)
        return 1

    tot_turns = sum(len(r['turns']) for r in rows)
    tot_cost = sum(r['cost_s'] for r in rows)
    bad_turns = sum(r['metrics']['violation_turns'] for r in rows)
    dup_pairs = sum(r['metrics']['attitude_dup'] for r in rows)
    all_pairs = sum(len(r['metrics']['attitude_pairs']) for r in rows)

    # 逐角色
    rows.sort(key=lambda r: -r['metrics']['violation_turns'])
    L = []
    L.append('# 第113轮b · 每人 %d 轮训练报告' % target)
    L.append('')
    L.append('> 生成时间：%s（可在训练进行中反复跑，数字是**已完成**部分）'
             % time.strftime('%Y-%m-%d %H:%M'))
    L.append('')
    L.append('## 总体')
    L.append('')
    L.append('| 项 | 值 |')
    L.append('|---|---|')
    L.append('| 已完成 | **%d / %d 人**（缺口 %d 人：`knight`） |'
             % (len(rows), total_people, len(gaps)))
    L.append('| 总轮数 | **%d 轮**（每人 %d 轮） |' % (tot_turns, target))
    L.append('| 总耗时 | %.1f 小时 |' % (tot_cost / 3600))
    L.append('| 硬违规 | %d 轮 / %d 轮 = **%.1f%%** |'
             % (bad_turns, tot_turns, 100.0 * bad_turns / max(1, tot_turns)))
    L.append('| 对他人态度同质 | **%d 组 / %d 组** |' % (dup_pairs, all_pairs))
    L.append('')

    # 四个专项
    def worst(key, n=8, reverse=True):
        return sorted(rows, key=key, reverse=reverse)[:n]

    L.append('## ① 性格 / 出戏（违规轮最多的）')
    L.append('')
    L.append('| 角色 | 违规轮 | 主要违规 | 口癖命中 |')
    L.append('|---|---|---|---|')
    for r in worst(lambda r: r['metrics']['violation_turns']):
        if not r['metrics']['violation_turns']:
            break
        codes = {}
        for t in r['turns']:
            for c, _ in t['violations']:
                codes[c] = codes.get(c, 0) + 1
        top = '、'.join('%s×%d' % (k, v) for k, v in
                        sorted(codes.items(), key=lambda x: -x[1])[:3])
        L.append('| `%s` %s | %d/%d | %s | %d 轮 |' % (
            r['id'], r['name'], r['metrics']['violation_turns'], target, top,
            r['metrics']['marker_turns']))
    L.append('')

    L.append('## ② 记忆（引用前文原话后，答对的比例越低越差）')
    L.append('')
    L.append('| 角色 | 5轮→13轮 | 3轮→14轮 | 记得开场问题 |')
    L.append('|---|---|---|---|')
    for r in sorted(rows, key=lambda r: r['metrics']['memory']['mem1_from5']['rate'])[:10]:
        m = r['metrics']['memory']
        L.append('| `%s` %s | %.0f%% | %.0f%% | %s |' % (
            r['id'], r['name'], m['mem1_from5']['rate'] * 100,
            m['mem2_from3']['rate'] * 100,
            '是' if m['mem3_intro']['hit'] else '**否**'))
    L.append('')
    L.append('> 注：这是**参考指标**（角色可能用代词回答），不当判据。'
             '命中算法 = 从原话里取 2~4 字实词，看回答里有没有。')
    L.append('')

    # ②b 剧情记忆（用户追加口径）
    L.append('## ②b 剧情记忆：用剧情提问，看他是不是**在回忆**（而不是正在经历）')
    L.append('')
    L.append('问法全部带过去时锚点（「那会儿」「那时候」「之后」「回到那天」），'
             '素材取自**该角色自己的原作场景**（`exemplars` 的 cue），不编剧情。')
    L.append('')
    tot_lb = sum((r['metrics'].get('plot_states') or {}).get('lookback', 0) for r in rows)
    tot_mx = sum((r['metrics'].get('plot_states') or {}).get('mixed', 0) for r in rows)
    tot_im = sum((r['metrics'].get('plot_states') or {}).get('immersed', 0) for r in rows)
    tot_un = sum((r['metrics'].get('plot_states') or {}).get('unmarked', 0) for r in rows)
    tot_pl = tot_lb + tot_mx + tot_im + tot_un
    L.append('**全场**：回望 **%d** / 混合 %d / 沉浸 **%d** / 无锚点 %d（共 %d 轮剧情问答）'
             '⇒ 回望率 **%.0f%%**'
             % (tot_lb, tot_mx, tot_im, tot_un, tot_pl, 100.0 * tot_lb / max(1, tot_pl)))
    L.append('')
    L.append('> 四态口径（`retro_of`）：**回望**=有回忆词无进行时词／**混合**=两者都有／'
             '**沉浸**=真出现进行时锚点（正在·此刻·眼下）／**无锚点**=两者都没有。')
    L.append('> 「无锚点」**不等于坏**：只是没把"当时/那会儿"写出来，得人眼看过才算数，'
             '所以下面把它和"沉浸"一起抽样。')
    L.append('')
    L.append('| 角色 | 回望 | 混合 | 沉浸 | 无锚点 | 接住 cue |')
    L.append('|---|---|---|---|---|---|')
    srt = sorted(rows, key=lambda r: (r['metrics'].get('plot_states') or {}).get('lookback', 0))
    for r in srt[:12]:
        ps = r['metrics'].get('plot_states') or {}
        L.append('| `%s` %s | %d | %d | **%d** | %d | %d/%d |' % (
            r['id'], r['name'], ps.get('lookback', 0), ps.get('mixed', 0),
            ps.get('immersed', 0), ps.get('unmarked', 0),
            r['metrics'].get('plot_relevant', 0),
            r['metrics'].get('plot_rel_n', len(r['metrics'].get('plot') or []))))
    L.append('')
    # 抽"沉浸"和"无锚点"两类样本 —— 比数字更能说明问题
    for want, title in (('immersed', '**沉浸样本（这就是要修的样子：文字落在进行时）**'),
                        ('unmarked', '**无锚点样本（没写回忆词，需要人眼判是否仍在回忆）**')):
        samples = [(r['id'], p) for r in rows for p in (r['metrics'].get('plot') or [])
                   if p['state'] == want]
        L.append(title)
        L.append('')
        if not samples:
            L.append('（无）')
            L.append('')
            continue
        for nid, p in samples[:3]:
            L.append('- `%s` 问：%s' % (nid, p['user']))
            L.append('  - 答：%s' % p['final'])
        L.append('')

    # ②c 语言（第113轮续）：先说"能不能用"，再说"像不像"
    L.append('## ②c 语言：他到底在不在说中文')
    L.append('')
    low_lang = [r for r in rows
                if (r['metrics'].get('lang') or {}).get('avg_cn', 1.0) < 0.6]
    L.append('**中文占比低于 0.6 的角色：%d / %d 人**' % (len(low_lang), len(rows)))
    L.append('')
    if low_lang:
        L.append('| 角色 | 中文占比 | 中文 <0.6 的轮数 |')
        L.append('|---|---|---|')
        for r in sorted(low_lang, key=lambda r: (r['metrics'].get('lang') or {}).get('avg_cn', 0)):
            lg = r['metrics'].get('lang') or {}
            L.append('| `%s` %s | **%.2f** | %d/%d |' % (
                r['id'], r['name'], lg.get('avg_cn', 0), lg.get('low_turns', 0), target))
        L.append('')
        L.append('> 这不是"风格差异"：中文用户看到整段英文，等于**这个角色不可用**。'
                 '根因是 system 里**从来没有"用中文说话"这一条**（`SPEAK_RULES` 第113轮补上），'
                 '而这些角色的人设原文里大段引用英文台词，模型顺着台词的语言走了。')
        L.append('')
    else:
        L.append('（全部在说中文）')
        L.append('')

    L.append('## ③ 口癖（人设登记的口头禅有没有自然冒出来）')
    L.append('')
    L.append('| 角色 | 命中轮数 | 登记的口癖 |')
    L.append('|---|---|---|')
    lol = [r for r in rows if r.get('voice_markers')]
    for r in sorted(lol, key=lambda r: r['metrics']['marker_turns_rate'])[:10]:
        L.append('| `%s` %s | %d/%d（%.0f%%） | %s |' % (
            r['id'], r['name'], r['metrics']['marker_turns'], target,
            r['metrics']['marker_turns_rate'] * 100,
            '、'.join(r['voice_markers'][:6])))
    L.append('')
    L.append('> 有登记口癖的角色共 **%d** 人；没登记的口癖角色不在此表（不硬凑）。'
             % len(lol))
    L.append('')

    L.append('## ④ 对他人态度（同一角色对不同人是否一个腔调）')
    L.append('')
    L.append('| 角色 | 雷同组 | 最高相似度 |')
    L.append('|---|---|---|')
    bad = [r for r in rows if r['metrics']['attitude_pairs']]
    for r in sorted(rows, key=lambda r: -(r['metrics']['attitude_dup']
                                          or max([p['ratio'] for p in r['metrics']['attitude_pairs']] or [0])))[:10]:
        ps = r['metrics']['attitude_pairs']
        if not ps:
            continue
        L.append('| `%s` %s | %d/%d | %.2f |' % (
            r['id'], r['name'], r['metrics']['attitude_dup'], len(ps),
            max(p['ratio'] for p in ps)))
    L.append('')

    # 待写纠正句
    L.append('## 待写纠正句名单（下阶段用）')
    L.append('')
    need = [r for r in rows if r['metrics']['violation_turns'] > 0]
    L.append('共 **%d 人**判红。每人附一条最典型的坏样本：' % len(need))
    L.append('')
    for r in need[:40]:
        bad_t = next(t for t in r['turns'] if t['violations'])
        code = bad_t['violations'][0][0]
        L.append('- `%s`（%s，%d/%d 轮，主码 `%s`）' % (
            r['id'], r['name'], r['metrics']['violation_turns'], target, code))
        L.append('  - 玩家：%s' % bad_t['user'][:50])
        L.append('  - 他答：%s' % (bad_t['final'] or '')[:80])
        L.append('')
    if not need:
        L.append('（全部零违规）')
        L.append('')

    L.append('## 产物在哪')
    L.append('')
    L.append('| 想看什么 | 打开 |')
    L.append('|---|---|')
    L.append('| 某个角色的 30 轮完整对话 | `_evidence/transcripts30/<角色id>.md` |')
    L.append('| 原始记录（含每次重采样） | `_evidence/raw30/<角色id>.jsonl` |')
    L.append('| 训练日志 | `_evidence/train30.log` |')
    L.append('')

    out = os.path.join(T.EVID, 'report30.md')
    C.write_text(out, '\n'.join(L) + '\n')
    print('已写：%s' % out)
    print('已完成 %d/%d 人 · %d 轮 · 违规 %.1f%% · 同质 %d/%d'
          % (len(rows), total_people, tot_turns,
             100.0 * bad_turns / max(1, tot_turns), dup_pairs, all_pairs))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
