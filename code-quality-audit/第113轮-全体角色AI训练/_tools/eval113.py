# -*- coding: utf-8 -*-
"""第113轮 · 训练评测 + 训练纠正生成。

它做四件事（顺序即依赖）
----------------------
1. **从第一遍原始记录重算**所有指标（不读别人算好的数）；
2. **生成训练纠正**（`patch`）：只给"第一遍确实判红"的角色写，
   并额外处理"跨角色撞车"（同一句话不同人都这么说 ⇒ 说明没演成各自的人）；
3. 回填 `assets/npc/_training/_index.json` 的 `patches`（运行时可读）；
4. 出报告：`_evidence/report113.{json,md}` + `_evidence/INDEX.md`（逐角色一张表）。

★ 为什么"纠正"要单独算、单独落盘，而不是直接改人设文件：
  人设是用户提供的原文（第55轮「你给装上就好」），**不许我改写**；
  纠正是我在本机 7B 上实测出来的补丁，属于"运行参数"，必须可回滚、可对账。
"""
import json
import os
import statistics
import sys

import common113 as C

CROSS_DUP = 0.85        # 跨角色"撞车"的相似度阈值（归一化后）
MIN_TURN_FOR_DUP = 2    # 至少两轮撞车才算"这个人没有自己的说话方式"


def pick_main_record(recs):
    u"""从一个人可能有的多条记录里挑**主记录**（评测与补丁都以它为准）。

    ★ 第113轮s 修的真 bug —— 「接线了，但接错对象」：
      这里原本写的是 `next(r for r in recs if r.get('phase') == 'baseline')`。
      而 `train30` 写盘的记录 `phase='t30'`（48 轮），`dialogue113` 写的是
      `phase='baseline'`（4 轮）。**同一个 raw30 文件里两条都在**，于是本函数
      一直只挑到那条**旧的 4 轮冒烟记录** ⇒ 评测评的是别的东西：
        · 77 人里只算出 **2 条** patch（`rouxls`/`susie`，都是 4 轮那遍撞的）；
        · 48 轮实测出的 **419 次 `ACTION_PAREN`**、146 次 `AI_SELF`、
          108 次 `NOT_CN`，**一条都没变成运行时纠正**；
        · `cards/*.json` 的 `eval` 对 74 个新训角色**全为空**。
      数字看着正常（有报告、有表格），但它评的那批数据早就被覆盖了。

    改法：**按轮数挑，不看 phase 名字**。同轮数时优先 `baseline`（老口径的偏好）。
    `phase == 'patch'` 的记录单独走"补训后"通道，不参与主记录竞争。
    """
    cand = [r for r in (recs or []) if isinstance(r, dict) and r.get('phase') != 'patch']
    if not cand:
        # 没有非 patch 记录时退回任意一条，避免整人凭空消失
        cand = [r for r in (recs or []) if isinstance(r, dict)]
        if not cand:
            return None

    def _key(r):
        n = r.get('turns_n') or len(r.get('turns') or [])
        return (n, 1 if r.get('phase') == 'baseline' else 0)

    return max(cand, key=_key)


def load_all():
    u"""读**主记录目录**：优先 48 轮的 `raw30`，没有才退回旧的 `raw`（4 轮）。

    ★ 第113轮s：原来硬用 `C.RAW`（`_evidence/raw`，4 轮 `dialogue113` 的产物）。
      48 轮训练写在 `_evidence/raw30`，两个目录**从没接上** ——
      所以"训练 48 轮"这件事在评测里等于没发生（详见 `pick_main_record`）。
    """
    raw_dir = C.RAW30 if os.path.isdir(C.RAW30) else C.RAW
    out = {}
    if not os.path.isdir(raw_dir):
        return out
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.endswith('.jsonl'):
            continue
        nid = fn[:-6]
        recs = C.read_jsonl(os.path.join(raw_dir, fn))
        base = pick_main_record(recs)
        patched = next((r for r in recs if r.get('phase') == 'patch'), None)
        out[nid] = {'baseline': base, 'patch': patched}
    return out


def ascii_safe(s):
    return s.encode('utf-8').decode('utf-8')


def collect_cards():
    d = os.path.join(C.TRAIN_DIR, 'cards')
    cards = {}
    if not os.path.isdir(d):
        return cards
    for fn in sorted(os.listdir(d)):
        if fn.endswith('.json'):
            c = C.load_json(os.path.join(d, fn))
            if c:
                cards[c['id']] = c
    return cards


def violations_of(rec):
    out = []
    for t in (rec or {}).get('turns', []):
        for v in (t.get('violations') or []):
            out.append((t['i'], v[0], v[1]))
    return out


def marker_hit(rec, markers):
    """回复里出现过任意一个口癖 ⇒ 这条算"有他的味道"。`markers` 空 ⇒ `None`（不参与统计）。"""
    if not markers:
        return None
    hits = 0
    turns = (rec or {}).get('turns', [])
    for t in turns:
        txt = t.get('final') or ''
        if any(m and m in txt for m in markers):
            hits += 1
    return (hits, len(turns))


def cross_dups(data):
    """跨角色撞车：同一轮问句下，两个人的回答高度相似。

    为什么只比**同一轮**：问句不同就没有可比性；本套剧本是固定 4 轮，
    所以第 i 轮之间才是同一道题（这也是 `dialogue113.TURNS` 必须全角色一致的原因）。
    """
    pairs = []
    ids = sorted(k for k, v in data.items() if v.get('baseline'))
    for i in range(1, 5):
        texts = {}
        for nid in ids:
            t = next((x for x in data[nid]['baseline']['turns'] if x['i'] == i), None)
            if t and (t.get('final') or '').strip():
                texts[nid] = t['final']
        keys = sorted(texts)
        for a in range(len(keys)):
            for b in range(a + 1, len(keys)):
                s = C.similarity(texts[keys[a]], texts[keys[b]])
                if s >= CROSS_DUP:
                    pairs.append({'turn': i, 'a': keys[a], 'b': keys[b], 'sim': s,
                                  'text_a': texts[keys[a]][:80],
                                  'text_b': texts[keys[b]][:80]})
    return pairs


def build_patches(data, cards, dups, roster_by_id=None):
    """把"实测出的毛病"翻成一句纠正。返回 `({id: patch}, dup_count, exempt)`。

    三类依据（按优先级）：
      ① 第一遍的硬违规（`PATCH_RULES` 里已有对应句）；
      ② 跨角色撞车 ≥ 2 轮 ⇒ 追加"你独有的说法"（用他自己的口癖）；
      ③ 全零违规且无撞车 ⇒ **不写 patch**（这一条最重要：没有证据就别动 prompt）。

    ★ 第四类：**人设自己要求的格式要豁免**。
      `tenna` 的人设明写"经常使用综艺字卡…伴随音效"，他输出「（字卡：Tenna！）」
      是照设定做。给他写"不要用括号写动作"等于逼他违反人设，
      补训两轮都是 4→4（实测没改善）—— 不是模型顽固，是判据错在拦人设。
    """
    roster_by_id = roster_by_id or {}
    dup_count = {}
    for d in dups:
        dup_count[d['a']] = dup_count.get(d['a'], 0) + 1
        dup_count[d['b']] = dup_count.get(d['b'], 0) + 1

    patches, exempt = {}, []
    for nid, recs in data.items():
        base = recs.get('baseline')
        if not base:
            continue
        vios = [(c, w) for _, c, w in violations_of(base)]
        persona = (roster_by_id.get(nid) or {}).get('persona') or ''
        if C._persona_allows_paren(persona):
            kept = [v for v in vios if v[0] != 'ACTION_PAREN']
            if len(kept) != len(vios):
                exempt.append({'npc': nid, 'code': 'ACTION_PAREN',
                               'n': len(vios) - len(kept),
                               'why': '人设明确要求字卡/音效/字幕，括号插入是本角色的表演形式'})
            vios = kept
        # ★ 第113轮s：元叙事角色的 META 纠正要豁免（详见 common113._persona_is_meta）。
        #   实测 13 个拿到 META 纠正的角色**全部**在人设里反复讲这些词，
        #   其中 6 个是 OneShot 系（玩家/代码/世界机器就是设定内核）。
        #   ★★ 113轮s 追加更正：**不能按整类剔**。`ut_papyrus` 的 2 条 META 撞的是
        #   `Undertale`——他原话「我确实是按照设定来扮演的角色。《Undertale》中的
        #   Papyrus 就是这样被描述和设计的」，这是**真出戏**，整类剔就等于放过了他
        #   （我第一版就是这么写的，靠回原始违规才发现）。
        #   ⇒ 改成**逐条按命中词**判：软词（玩家/代码/世界机器…）才豁免，
        #     硬词（作品名/游戏角色/开发者/桌宠）永不豁免。
        is_meta, n_meta = C._persona_is_meta(persona)
        if is_meta:
            kept, soft_n = [], 0
            for v in vios:
                if v[0] == 'META' and C.meta_hit_is_soft(v[1]):
                    soft_n += 1
                    continue
                kept.append(v)
            if soft_n:
                hard_n = len(vios) - len(kept) - soft_n
                exempt.append({'npc': nid, 'code': 'META',
                               'n': soft_n,
                               'why': '人设本身是元叙事（玩家/代码/世界机器等出现 %d 次），'
                                      '提这些词是在照设定说话' % n_meta
                                      + ('；另有 %d 条撞的是作品名/开发者，**不豁免**' % hard_n
                                         if hard_n else '')})
            vios = kept
        card = cards.get(nid, {})
        parts = []
        main_patch = C.build_patch([(c, w) for c, w in vios], card.get('voice_markers'),
                                   card.get('relations'))
        if main_patch:
            parts.append(main_patch)
        if dup_count.get(nid, 0) >= MIN_TURN_FOR_DUP:
            vp = C.build_voice_patch(card.get('voice_markers') or [], dup_group=True)
            if vp:
                parts.append(vp)
        if not parts:
            continue
        patch = ' '.join(parts)
        if len(patch) > 160:
            patch = patch[:160]
        patches[nid] = patch
    return patches, dup_count, exempt


def summarize(data, cards, dups):
    turns_total = 0
    viol_counts = {}
    per_char = {}
    ttft_cold, ttft_warm, trunc, retries = [], [], [], 0
    len_all = []
    calls = 0
    for nid, recs in sorted(data.items()):
        base = recs.get('baseline')
        if not base:
            continue
        vs = violations_of(base)
        turns_total += len(base.get('turns') or [])
        for _, code, _ in vs:
            viol_counts[code] = viol_counts.get(code, 0) + 1
        for t in base.get('turns') or []:
            st = t.get('stats') or {}
            calls += len(t.get('attempts') or [])
            retries += t.get('retries') or 0
            if st.get('ttft_s') is not None:
                (ttft_warm if (st.get('prompt_eval_count') or 0) < 100 else ttft_cold).append(st['ttft_s'])
            if st.get('truncated'):
                trunc.append(nid)
            if t.get('final'):
                len_all.append(len(t['final']))
        hit = marker_hit(base, (cards.get(nid) or {}).get('voice_markers') or [])
        per_char[nid] = {
            'turns': len(base.get('turns') or []),
            'violations': len(vs),
            'codes': sorted({c for _, c, _ in vs}),
            'marker_hit': hit,
            'cost_s': base.get('cost_s'),
        }
    after = {}
    for nid, recs in sorted(data.items()):
        p2 = recs.get('patch')
        if not p2:
            continue
        before = per_char.get(nid, {}).get('violations', 0)
        now = sum(1 for t in p2.get('turns') or [] if t.get('violations'))
        after[nid] = {'before': before, 'after': now,
                      'turns': len(p2.get('turns') or []),
                      'fixed': before > 0 and now == 0,
                      'still': now}
    return {
        'chars_with_dialogue': sum(1 for v in data.values() if v.get('baseline')),
        'turns': turns_total,
        'hard_violations': sum(viol_counts.values()),
        'violation_codes': dict(sorted(viol_counts.items(), key=lambda kv: -kv[1])),
        'per_char': per_char,
        'calls': calls,
        'retries': retries,
        'truncated_chars': sorted(set(trunc)),
        'ttft_cold_median': round(statistics.median(ttft_cold), 2) if ttft_cold else None,
        'ttft_warm_median': round(statistics.median(ttft_warm), 3) if ttft_warm else None,
        'len_median': int(statistics.median(len_all)) if len_all else 0,
        'len_max': max(len_all) if len_all else 0,
        'cross_dups': len(dups),
        'cross_dup_chars': len({d['a'] for d in dups} | {d['b'] for d in dups}),
        'patch_pass': after,
        'patch_fixed': sum(1 for v in after.values() if v['fixed']),
        'patch_still': sum(1 for v in after.values() if v['after'] > 0),
    }


def write_corpus(data, cards, roster):
    """SFT 语料：`messages` 三段式，将来的 LoRA/其它底座可直接吃。

    ★ system 用**不带 patch** 的原始人设 —— 否则模型学到的是"靠纠正句才守规矩"，
      换个场景就退回老毛病。
    ★ 对话优先取**通过判据更多**的那一遍（补训后的通常更好），但 `phase` 字段如实标注来源。
    ★ 每个角色**整文件重写**（不是追加）：评测会跑不止一次，追加会让语料翻倍。
    """
    by_id = {r['id']: r for r in roster}
    n = 0
    out_dir = os.path.join(C.TRAIN_DIR, 'corpus')
    for nid, recs in sorted(data.items()):
        base, p2 = recs.get('baseline'), recs.get('patch')
        ok = lambda r: sum(1 for t in (r or {}).get('turns', []) if not t.get('violations'))
        use = p2 if (p2 and ok(p2) > ok(base)) else base
        if not use:
            continue
        item = by_id.get(nid)
        if item is None:
            continue
        system = C._NP.build_system_prompt(
            item['name'], item['persona'], entries=[], npc_id=nid,
            context='', life='', patch='')
        rows = []
        for t in use.get('turns') or []:
            if not t.get('final'):
                continue
            rows.append({'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': t['user']},
                {'role': 'assistant', 'content': t['final']},
            ], 'id': nid, 'turn': t['i'], 'compliant': not t.get('violations'),
                'phase': use.get('phase')})
            n += 1
        C.write_text(os.path.join(out_dir, nid + '.jsonl'),
                     '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n')
    return n


def report_md(summary, patches, cards, dups, roster, gaps, exempt=None):
    s = summary
    L = []
    L.append('# 第113轮 · 全体角色 AI 训练报告')
    L.append('')
    L.append('> 生成本文的是 `_tools/eval113.py`（数字全部由 `_evidence/raw/*.jsonl` 重算）。')
    L.append('')
    L.append('## 0. 一句话结论')
    L.append('')
    L.append('在**无 GPU（18 核 CPU）**的本机上，对 **%d 个角色**跑了 **%d 轮**真实对话；'
             '第一遍硬违规 **%d 处**，跨角色撞车 **%d 对**；'
             '对判红的角色注入训练纠正后重跑，**%d 人转全绿**、%d 人仍有问题。' % (
                 s['chars_with_dialogue'], s['turns'], s['hard_violations'],
                 s['cross_dups'], s['patch_fixed'], s['patch_still']))
    L.append('')
    L.append('## 1. 覆盖')
    L.append('')
    L.append('| 项 | 数 |')
    L.append('|---|---|')
    L.append('| 训练卡（全档） | %d |' % len(cards))
    L.append('| 其中有人设、走模型 | %d |' % sum(1 for c in cards.values() if c['kind'] == 'persona'))
    L.append('| 其中纯 NPC（内置台词，不过模型） | %d |' % sum(1 for c in cards.values() if c['kind'] == 'canned'))
    L.append('| 缺口（无人设） | %d（%s）|' % (len(gaps), '、'.join(g['id'] for g in gaps)))
    L.append('| 有真实对话记录 | %d |' % s['chars_with_dialogue'])
    L.append('')
    L.append('## 2. 第一遍：合规')
    L.append('')
    L.append('| 违规码 | 次数 | 含义 |')
    L.append('|---|---|---|')
    mean = {'AI_SELF': '自称 AI / 模型 / 程序', 'MARKDOWN': '输出排版标记',
            'SLAVE': '「主人」等服务腔', 'ACTION_PAREN': '括号写动作',
            'META': '提到作品名/游戏/玩家/代码', 'TOO_LONG': '超过 200 字',
            'PARROT': '整句复述对方', 'REPEAT': '复读自己上一句', 'EMPTY': '空回复'}
    for code, n in s['violation_codes'].items():
        L.append('| `%s` | %d | %s |' % (code, n, mean.get(code, '')))
    L.append('')
    L.append('- 实际调用 **%d 次**（含重采样 %d 次）' % (s['calls'], s['retries']))
    L.append('- 首字：冷 **%ss** / 热 **%ss**（中位数）' % (s['ttft_cold_median'], s['ttft_warm_median']))
    L.append('- 回复长度中位数 **%d 字**，最长 **%d 字**' % (s['len_median'], s['len_max']))
    if s['truncated_chars']:
        L.append('- ⚠️ **有 %d 人的 prompt 顶到 num_ctx=8192（前缀被截断）**：%s —— '
                 '这是"人设太长"的真实代价，不是模型的问题' % (
                     len(s['truncated_chars']), '、'.join(s['truncated_chars'])))
    L.append('')
    L.append('## 3. 跨角色撞车（"是不是同一个 AI 换皮"）')
    L.append('')
    if not dups:
        L.append('没有发现相似度 ≥ %.2f 的跨角色回答。' % CROSS_DUP)
    else:
        L.append('相似度 ≥ %.2f 的跨角色回答共 **%d 对**，涉及 **%d 个角色**。前 8 对：' % (
            CROSS_DUP, len(dups), s['cross_dup_chars']))
        L.append('')
        L.append('| 轮 | 两个角色 | 相似度 | 说法 |')
        L.append('|---|---|---|---|')
        for d in sorted(dups, key=lambda x: -x['sim'])[:8]:
            L.append('| %d | %s ↔ %s | %.2f | %s / %s |' % (
                d['turn'], d['a'], d['b'], d['sim'],
                d['text_a'].replace('|', '/'), d['text_b'].replace('|', '/')))
    L.append('')
    L.append('## 4. 训练纠正（patch）')
    L.append('')
    L.append('共 **%d 人**拿到纠正句（判红或撞车）。没有证据的角色**一条都不写**。' % len(patches))
    L.append('')
    if patches:
        L.append('| 角色 | 纠正 |')
        L.append('|---|---|')
        for nid in sorted(patches):
            L.append('| `%s` | %s |' % (nid, patches[nid].replace('|', '/')))
        L.append('')
    if exempt:
        L.append('### 判据豁免（不是毛病，是人设要求）')
        L.append('')
        L.append('| 角色 | 违规码 | 处数 | 理由 |')
        L.append('|---|---|---|---|')
        for e in exempt:
            L.append('| `%s` | %s | %d | %s |' % (e['npc'], e['code'], e['n'], e['why']))
        L.append('')
        L.append('> 这些不计入纠正：给他写"别用括号"等于逼他违反自己的人设。')
        L.append('')
    if s['patch_pass']:
        L.append('### 补训前后')
        L.append('')
        L.append('| 角色 | 补训前不合规轮 | 补训后不合规轮 | 结果 |')
        L.append('|---|---|---|---|')
        for nid, v in sorted(s['patch_pass'].items()):
            res = '✅ 全绿' if v['after'] == 0 else (
                '有改善' if v['after'] < v['before'] else '未改善')
            if v['after'] > 0 and nid in {e['npc'] for e in (exempt or [])}:
                res += '（判据豁免，不计）'
            L.append('| `%s` | %d/%d | %d/%d | %s |' % (
                nid, v['before'], v['turns'], v['after'], v['turns'], res))
        L.append('')
    L.append('## 5. 逐角色')
    L.append('')
    L.append('| 角色 | 档 | 人设字数 | 口癖数 | 第一遍违规 | 纠正 |')
    L.append('|---|---|---|---|---|---|')
    for r in roster:
        nid = r['id']
        c = cards.get(nid, {})
        pc = s['per_char'].get(nid, {})
        if not pc:
            continue
        L.append('| %s | %s | %d | %d | %d | %s |' % (
            nid, r.get('tier'), c.get('persona_chars', 0), len(c.get('voice_markers') or []),
            pc.get('violations', 0), '有' if nid in patches else '—'))
    L.append('')
    L.append('## 6. 怎么复现')
    L.append('')
    L.append('```')
    L.append('python _tools/cards113.py --all      # 抽卡（96 张）')
    L.append('python _tools/dialogue113.py --phase baseline   # 第一遍（可断点续跑）')
    L.append('python _tools/eval113.py             # 出纠正 + 报告')
    L.append('python _tools/dialogue113.py --phase patch      # 只补训判红的人')
    L.append('python _tools/eval113.py             # 复评（带前后对照）')
    L.append('```')
    L.append('')
    return '\n'.join(L) + '\n'


def _split_sents(s):
    u"""按句末标点切句（保留标点），用于"逐句求并集"。"""
    out, cur = [], ''
    for ch in (s or ''):
        cur += ch
        if ch in u'。！？!?':
            if cur.strip():
                out.append(cur.strip())
            cur = ''
    if cur.strip():
        out.append(cur.strip())
    return out


def merge_text(old, new):
    u"""把两条补丁按**句子**求并集：谁多留谁，双方各有的都留下。

    ★ 为什么不是"二选一"（第一版就是这么写的，dry-run 抓出来了）：
      逐键比较时 `ralsei` 的旧补丁是「只认得原作里真有的名字…不要自己造人名」，
      新算出来的是「一次最多两三句…别重复」，**两边互不包含** ——
      "取新的"会把那条**手写的名字规则删掉**（那是别的轮因为"凯斯恩"这类
      拼名才加的），"取旧的"又会让本轮的重复/啰嗦毛病没有纠正。
      这两句纠正彼此不冲突，**该同时在场**。
    """
    old, new = (old or '').strip(), (new or '').strip()
    if not old:
        return new
    if not new:
        return old
    if new in old:
        return old
    if old in new:
        return new
    have = {x.strip(u'。 ') for x in _split_sents(old)}
    extra = [x for x in _split_sents(new) if x.strip(u'。 ') not in have]
    if not extra:
        return old
    return old + ' ' + ' '.join(extra)


def merge_patches(old, new):
    u"""把本次算出的 `new` 并进已有的 `old`，**不许静默删掉算不出来的旧补丁**。

    ★ 为什么需要（第113轮s dry-run 实测）：`main` 原来是 `idx['patches'] = patches`
      —— **整体替换**。而 `build_patches` 只从本轮 raw30 现算，它不知道旧补丁是谁写的。
      实测后果：`ralsei` 那条「只认得原作里真有的名字…不要自己造人名」
      是**别的轮手写**的，本轮算不出来 ⇒ 直接替换会把它**删掉**，
      等于把那轮修好的毛病（自造人名）原样放回产品。

    规则：
      ① 只有新键 ⇒ 用新的（本轮有证据）；
      ② 只有旧键 ⇒ **保留旧的**（没证据推翻它，删了就是信息丢失）；
      ③ 两边都有 ⇒ `merge_text` 求并集（详见其说明）。
    返回 `(merged, 报告行 list)`。
    """
    old, new = dict(old or {}), dict(new or {})
    merged, rep = {}, []
    for k in sorted(set(old) | set(new)):
        if k not in old:
            merged[k] = new[k]
            rep.append(u'+ %s 新增' % k)
        elif k not in new:
            merged[k] = old[k]
            rep.append(u'= %s 本轮算不出来，**保留旧补丁**（否则会被删）' % k)
        else:
            t = merge_text(old[k], new[k])
            merged[k] = t
            if t != old[k]:
                rep.append(u'~ %s 合并：%d → %d 字' % (k, len(old[k]), len(t)))
    return merged, rep


def strip_paren_rule(text):
    u"""剔掉补丁里「不要用括号…」那一句，**其余纠正原样保留**。

    只给 `_persona_allows_paren` 为真的角色用（kris/tenna/ut_frisk/os_silver…）。
    ★ 为什么需要单独一步：豁免是第113轮s 才加的，而他们的卡片/索引里早就留着
      那句老补丁 ⇒ 运行时 prompt 一边说"用括号表示动作"、一边说"不要用括号"。
    ★ 为什么不能靠 `merge_patches`：它的规则是"保留旧键"，算不出来的旧句子
      **不会**被删 ⇒ 不主动剔就永远是矛盾态。
    ★ 为什么只删一句而不是清空：他们还有「别重复」「两三句」要留着。
    """
    sents = _split_sents(text or u'')
    keep = [s for s in sents if u'括号' not in s]
    if len(keep) == len(sents):
        return text or u''
    return u' '.join(keep).strip()


def main(argv):
    roster, gaps = C.load_roster()
    cards = collect_cards()
    data = load_all()
    if not data:
        print('还没有任何对话记录，先跑 dialogue113.py --phase baseline')
        return 1
    dups = cross_dups(data)
    roster_by_id = {r['id']: r for r in roster}
    patches, dup_count, exempt = build_patches(data, cards, dups, roster_by_id)
    summary = summarize(data, cards, dups)
    n_corpus = write_corpus(data, cards, roster)

    # ★★ 113轮s：**括号豁免的角色，旧补丁里那句「不要用括号…」必须剔掉**。
    #   豁免是这一轮才加的，而 `kris`/`tenna`/`ut_frisk` 的卡片里早就留着那句
    #   （那是加豁免之前算出来的）⇒ 运行时 prompt 一边要求"用括号表示动作"、
    #   一边要求"不要用括号"，自相矛盾。
    #   ⚠️ 只删**这一句**，不是清空补丁：他们的「别重复」「两三句」还要留着。
    #   ⚠️ 也不能靠 `merge_patches` —— 它的规则是"保留旧键"，不会主动删。
    strip_nids = set()
    for nid, persona in [(k, (v.get('persona') or '')) for k, v in roster_by_id.items()]:
        if not C._persona_allows_paren(persona):
            continue
        cur = (cards.get(nid) or {}).get('patch') or ''
        if u'括号' in cur:
            strip_nids.add(nid)

    # —— 回填：卡片 + 索引（索引是运行时唯一读的口径）——
    for nid in list(patches) + [n for n in sorted(strip_nids) if n not in patches]:
        card = cards.get(nid)
        if not card:
            continue
        p = patches.get(nid)
        if p is None:
            # 只有"要剔句"的份 —— 保留旧补丁里除括号句以外的内容。
            p = strip_paren_rule(card.get('patch') or '')
        card['patch'] = p
        card['eval'] = {
            'violations': summary['per_char'].get(nid, {}).get('violations', 0),
            'codes': summary['per_char'].get(nid, {}).get('codes', []),
            'cross_dups': dup_count.get(nid, 0),
            'marker_hit': summary['per_char'].get(nid, {}).get('marker_hit'),
        }
        C.write_text(os.path.join(C.TRAIN_DIR, 'cards', nid + '.json'),
                     json.dumps(card, ensure_ascii=False, indent=1) + '\n')

    idx_path = os.path.join(C.TRAIN_DIR, '_index.json')
    idx = C.load_json(idx_path, {}) or {}
    # ★ 第113轮s：不能直接 `idx['patches'] = patches` —— 见 `merge_patches` 的说明。
    merged, mrep = merge_patches(idx.get('patches') or {}, patches)
    # ★ 索引侧同样要剔（卡片已剔，索引是运行时真正读的那一份，两边必须一致）
    for nid in sorted(strip_nids):
        cur = merged.get(nid)
        if cur and u'括号' in cur:
            new_txt = strip_paren_rule(cur)
            print(u'  [patches] %s 剔掉括号纠正：%d → %d 字' % (nid, len(cur), len(new_txt)))
            merged[nid] = new_txt
    idx['patches'] = merged
    for line in mrep:
        print('  [patches] %s' % line)
    idx['trained'] = {
        'model': C.MODEL,
        'chars': summary['chars_with_dialogue'],
        'turns': summary['turns'],
        'hard_violations': summary['hard_violations'],
        'cross_dups': summary['cross_dups'],
        'corpus_rows': n_corpus,
        'generated_at': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
    }
    C.write_text(idx_path, json.dumps(idx, ensure_ascii=False, indent=1) + '\n')

    payload = {'summary': summary, 'patches': patches,
               'dup_pairs': dups[:200], 'corpus_rows': n_corpus}
    C.write_text(os.path.join(C.EVID, 'report113.json'),
                 json.dumps(payload, ensure_ascii=False, indent=1) + '\n')
    md = report_md(summary, patches, cards, dups, roster, gaps, exempt=exempt)
    C.write_text(os.path.join(C.EVID, 'report113.md'), md)

    # —— 逐角色速查表（用户明天扫一眼就能挑人看 transcript）——
    lines = ['# 第113轮 · 训练对话索引', '',
             '| 角色 | 中文名 | 违规 | 纠正 | 对话记录 |', '|---|---|---|---|---|']
    for r in roster:
        nid = r['id']
        pc = summary['per_char'].get(nid)
        if not pc:
            continue
        lines.append('| `%s` | %s | %d | %s | [%s.md](transcripts/%s.md) |' % (
            nid, r.get('name_cn') or '—', pc['violations'],
            '有' if nid in patches else '—', nid, nid))
    lines.append('')
    C.write_text(os.path.join(C.EVID, 'INDEX.md'), '\n'.join(lines) + '\n')

    # —— 把 77 份对话拼成一本"可以一路读下去"的册子（用户明天要看的其实是这个）——
    book = ['# 第113轮 · 全体角色训练对话（合订本）', '',
            '> 每节 = 一个角色；原文来自 `transcripts/<id>.md`，未做任何删改。', '']
    for r in roster:
        nid = r['id']
        p = os.path.join(C.TRANSCRIPTS, nid + '.md')
        if not os.path.isfile(p):
            continue
        book.append('---')
        book.append('')
        book.append(C.read_text(p).strip())
        book.append('')
    C.write_text(os.path.join(C.EVID, 'ALL_DIALOGUES.md'), '\n'.join(book) + '\n')

    print('角色 %d 人 / %d 轮 / 硬违规 %d 处 / 撞车 %d 对' % (
        summary['chars_with_dialogue'], summary['turns'],
        summary['hard_violations'], summary['cross_dups']))
    print('纠正 %d 人；补训后全绿 %d 人，仍有问题 %d 人' % (
        len(patches), summary['patch_fixed'], summary['patch_still']))
    print('语料 %d 条 → assets/npc/_training/corpus/' % n_corpus)
    print('报告 → _evidence/report113.md')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
