# -*- coding: utf-8 -*-
u"""生成 `assets/npc/_seek.json`（「他想去找谁」登记表，第113轮p）。

数据源：`_evidence/raw30/*.jsonl` 里每人**已跑完的最高轮数**那一份记录
（48 轮优先，没跑完就回落 36 轮）。

口径见 `npc_seek` 文件头：
  · 主指标 = **主动提起**（问句没点名、回答里提到他）—— 行为频次；
  · 修正   = 关系段里**明说**"想见/陪着"（抬）/ "躲着/受不了/闹翻"（降）。

★ 名字 → npc_id 只认 `_registry.json`（`name` 精确、其次忽略大小写、再次 `name_cn`）。
  解析不到的一律**丢弃并登记到 `unresolved`**，不硬猜 ——
  `relations` 里混着非人条目（`时间` / `母亲` / `萤火虫` / `Dunes 的居民`），
  猜错等于把 A 的偏好挂到 B 头上。

用法
----
    python gen_seek113p.py            # 写 _seek.json
    python gen_seek113p.py --dry      # 只打印统计，不写盘
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
RAW = os.path.join(ROUND, '_evidence', 'raw30')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
OUT = os.path.join(PET, 'assets', 'npc', '_seek.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_seek as S                                        # noqa: E402


def read_jsonl(path):
    out = []
    try:
        with io.open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        return []
    return out


#: 作品前缀：同名角色在多部作品里各有一条登记（`toriel` / `ot_toriel` / `ut_toriel`）。
#: ★ 必须先按**同作品**消歧，否则 `asgore` 的 Toriel 会被挂到 `ot_toriel`（实测踩过）。
WORK_PREFIXES = ('hy_', 'os_', 'ot_', 'ut_')


def split_prefix(nid):
    s = str(nid or '')
    for p in WORK_PREFIXES:
        if s.startswith(p):
            return p, s[len(p):]
    return '', s


def registry_maps():
    """→ `(by_name, by_lower, by_cn, cn_of, ids)`。

    三个索引的值都是**候选 id 列表**（同名可能有多条，交由 `pick_id` 消歧）。
    """
    d = json.loads(io.open(REG, encoding='utf-8').read())
    by_name, by_lower, by_cn, cn_of, ids = {}, {}, {}, {}, set()
    for r in (d.get('npcs') or []):
        if not isinstance(r, dict):
            continue
        nid, nm = r.get('id'), r.get('name')
        if not nid:
            continue
        ids.add(nid)
        if not nm:
            continue
        by_name.setdefault(nm, []).append(nid)
        by_lower.setdefault(str(nm).lower(), []).append(nid)
        if r.get('name_cn'):
            by_cn.setdefault(str(r['name_cn']), []).append(nid)
            cn_of[nm] = str(r['name_cn'])
    return by_name, by_lower, by_cn, cn_of, ids


def _dedup(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def pick_id(nm, src_id, by_name, by_lower, by_cn, ids):
    """名字 → npc_id，**按作品前缀消歧**。→ `(id 或 None, 原因)`。

    ★ 为什么必须消歧（实测踩过）：`asgore`（Deltarune）提到 Toriel，
      第一版直接命中 `ot_toriel`（Outertale 版），把偏好挂到了另一个人身上。
    ★ 规则（宁可丢弃也不猜）：
      1. 候选里优先**与源角色同前缀**的；源角色无前缀时优先**无前缀**的
         （即 Deltarune 本体那一条）；
      2. 优先档里**恰好一个** ⇒ 采用；
      3. 优先档为空 ⇒ 退回全部候选，**恰好一个**才采用；
      4. 仍多个 / 零个 ⇒ `None`（登记到 `unresolved`，交人工看）。
    """
    cand = _dedup((by_name.get(nm) or []) + (by_lower.get(str(nm).lower()) or [])
                  + (by_cn.get(str(nm)) or []))
    cand = [c for c in cand if c in ids]
    if not cand:
        # ★ 第三档：**登记名以该名字开头**（`Chujin` → `hy_chujin_ketsukane`，
        #   登记名是 `Chujin Ketsukane`）。只在名字够长（≥5 字）时启用 ——
        #   短名字（`Kan`、`Al`）前缀匹配几乎必然误伤。
        if len(str(nm)) >= 5:
            low = str(nm).lower()
            for nm2, lst in by_name.items():
                if str(nm2).lower() == low:
                    continue
                if str(nm2).lower().startswith(low):
                    cand.extend(lst)
            cand = _dedup([c for c in cand if c in ids])
    if not cand:
        return None, 'unknown'
    if len(cand) == 1:
        return cand[0], 'ok'
    p, _ = split_prefix(src_id)
    same = [c for c in cand if split_prefix(c)[0] == p]
    if len(same) == 1:
        return same[0], 'ok'
    if not same and not p:
        return None, 'ambiguous'
    return None, 'ambiguous'


def best_record(recs):
    """同一人的多条记录里取**最高轮数**那条（同轮数取开始时间更晚的）。"""
    best = None
    for r in recs:
        if not isinstance(r, dict):
            continue
        key = (r.get('turns_n') or 0, str(r.get('started_at') or ''))
        if best is None or key >= (best.get('turns_n') or 0, str(best.get('started_at') or '')):
            best = r
    return best


def main(argv):
    dry = '--dry' in argv
    by_name, by_lower, by_cn, cn_of, ids = registry_maps()
    unresolved = {}
    seek = {}
    per_char = []
    turns_seen = {}

    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith('.jsonl'):
            continue
        nid = fn[:-6]
        rec = best_record(read_jsonl(os.path.join(RAW, fn)))
        if not rec:
            continue
        turns_seen[nid] = rec.get('turns_n')

        rels = [n for n in (rec.get('relations') or ()) if n]
        aliases = {}
        for n in rels:
            al = [n]
            c = cn_of.get(n)
            if c:
                al.append(c)
            aliases[n] = al

        def _id_of(nm, _nid=nid):
            got, why = pick_id(nm, _nid, by_name, by_lower, by_cn, ids)
            if got:
                return got
            unresolved.setdefault(_nid, []).append(
                nm if why == 'unknown' else u'%s（%s）' % (nm, why))
            return None

        rows = S.rows_of(rec, aliases=aliases, id_of=_id_of)
        keep = {}
        for k, v in rows.items():
            if k in ids and k != nid:
                keep[k] = v
        if not keep:
            continue
        seek[nid] = {k: keep[k] for k in sorted(keep, key=lambda x: (-keep[x]['w'], x))}
        per_char.append((nid, rec.get('turns_n'), len(keep)))

    doc = {
        'version': 1,
        'about': u'「他想去找谁」—— 来自角色自己在训练对话里主动提起的人',
        'source': 'code-quality-audit/第113轮-全体角色AI训练/_evidence/raw30/*.jsonl',
        'method': (u'主指标=主动提起（问句未点名、回答里提到他，按 name/name_cn 匹配）；'
                   u'修正=关系段里明说「想见/陪着」(抬) 与「躲着/受不了/闹翻」(降)。'
                   u'这是**行为频次代理**，不是"他明确说过想见谁"。'),
        'formula': ('w = (1 + %g*min(mention,%d)) * (1 + %g*min(pos,%d))'
                    ' * %g**min(neg,%d)，钳在 [%g,%g]'
                    % (S.MENTION_STEP, S.MENTION_CAP, S.UP_STEP, S.UP_CAP,
                       S.DOWN_STEP, S.DOWN_CAP, S.W_MIN, S.W_MAX)),
        'schema': {'w': u'权重，乘在熟络度上', 'mention': u'主动提起的次数',
                   'pos': u'明说"想见/陪着"的句数', 'neg': u'明说"躲着/受不了"的句数',
                   'why': u'原句片段（可复核）'},
        'unresolved_names': {k: sorted(set(v)) for k, v in sorted(unresolved.items())},
        'seek': {k: seek[k] for k in sorted(seek)},
    }

    n_char, n_item = S.summarize(doc)
    print(u'角色 %d 人 / 条目 %d 条' % (n_char, n_item))
    dist = {}
    for v in turns_seen.values():
        dist[str(v)] = dist.get(str(v), 0) + 1
    print(u'轮数分布:', dict(sorted(dist.items())))
    print(u'解析不到的名字（不硬猜，已丢弃）:')
    for k, v in doc['unresolved_names'].items():
        print(u'   %-20s %s' % (k, u'、'.join(v)))
    print()
    print(u'样例（前 8 人）:')
    for nid, tn, cnt in per_char[:8]:
        items = [u'%s=%.2f' % (w, v['w']) for w, v in
                 list(seek[nid].items())[:4]]
        print(u'   %-20s %d 轮  %d 条  %s' % (nid, tn, cnt, u' '.join(items)))

    if dry:
        print(u'\n--dry：未写盘')
        return 0
    with io.open(OUT, 'w', encoding='utf-8', newline=u'\n') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False))
        f.write(u'\n')
    print(u'\n已写：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
