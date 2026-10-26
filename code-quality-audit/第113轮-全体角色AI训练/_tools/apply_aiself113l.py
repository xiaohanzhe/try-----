# -*- coding: utf-8 -*-
"""第113轮l：把 `AI_SELF` 的通用纠正句回填到训练产物（只给**有实测证据**的人）。

设计要点（每一条都对应踩过的坑）：

★ 1. **只在有证据的人身上写**。证据 = `_evidence/raw30/*.jsonl` 里训练当时记下的
   `AI_SELF` 违规。不是"我觉得他会有毛病"。这条口径 `check113 D6` 已经守着。
★ 2. **两个副本一起写**：`patches`（运行时真源，`training_patch()` 读）与
   `cards[nid]['patch']`（`cards113.py` 重建索引时会从 `patches` 回写的那一份）。
   只写一处 ⇒ 下次重建索引，两份就不一致了，而且没人报错。
★ 3. **写盘前先证明能原样读回来**。`_index.json` 是 800 行的产物文件，
   随手 `json.dump` 一遍会把整份文件的格式重排（`ensure_ascii` / 缩进 /
   行尾），diff 变成"全文件重写"，审阅时看不出真正改了哪几条。
   所以先做**往返自证**：`dumps(loads(原文)) == 原文`，不等就中止。
★ 4. 行尾/BOM 原样保留（`newline=''`）。

用法：
    python apply_aiself113l.py [--dry]
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common113 as C  # noqa: E402

EVID = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
RAW30 = os.path.join(EVID, 'raw30')
INDEX = os.path.normpath(os.path.join(
    HERE, '..', '..', '..', 'ralsei_pet', 'assets', 'npc', '_training', '_index.json'))


def read_jsonl(path):
    out = []
    with io.open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def evidence_ids():
    """有 `AI_SELF` 实测证据的角色（全扫所有记录，不看 `turns_n`）。"""
    got = set()
    for fn in sorted(os.listdir(RAW30)):
        if not fn.endswith('.jsonl'):
            continue
        for rec in read_jsonl(os.path.join(RAW30, fn)):
            nid = rec.get('id') or fn[:-6]
            for t in rec.get('turns') or []:
                if any(c == 'AI_SELF' for c, _ in (t.get('violations') or [])):
                    got.add(nid)
                    break
    return got


def main(argv):
    dry = '--dry' in argv
    revert = '--revert' in argv
    raw = io.open(INDEX, 'r', encoding='utf-8', newline='').read()

    # --- 往返自证：不通过就不许写盘（否则整份文件被重排，看不出真正改了什么）
    data = json.loads(raw)
    again = json.dumps(data, ensure_ascii=False, indent=1)
    if again != raw.rstrip('\n'):
        print('[中止] JSON 往返不自洽：dump 出来的文本与原文不同。')
        print('       原文 %d 字符，重排后 %d 字符。' % (len(raw), len(again)))
        # 只报差异位置，别打印全文
        for i in range(min(len(raw), len(again))):
            if raw[i] != again[i]:
                print('       首个差异在第 %d 字符：%r vs %r'
                      % (i, raw[max(0, i - 30):i + 30], again[max(0, i - 30):i + 30]))
                break
        return 2
    print('[OK] JSON 往返自洽（indent=1 / ensure_ascii=False 能原样还原）')

    ids = sorted(evidence_ids())
    print('[OK] 有 AI_SELF 实测证据：%d 人' % len(ids))
    if not ids:
        return 3

    patches = data.setdefault('patches', {})
    cards = data.get('cards') or {}

    # ---------------------------------------------------------------- 撤销
    # ★ 为什么整个撤销：A/B 实测证明这类纠正句不但无效，还会把「提示词/AI」的词
    #   激活（反向交替对照：不加 3/12 含禁词，加了 8/12）。详见
    #   `common113.AI_SELF_PATCH` 上方那段结论。
    if revert:
        gone = [n for n, p in list(patches.items()) if p == C.AI_SELF_PATCH]
        for n in gone:
            patches.pop(n, None)
            if n in cards and cards[n].get('patch') == C.AI_SELF_PATCH:
                cards[n]['patch'] = ''
        print('[撤销] %d 人：%s' % (len(gone), ','.join(sorted(gone))))
        left = [n for n, p in patches.items() if C.AI_SELF_PATCH in p]
        print('       仍有残留：%s' % (','.join(sorted(left)) or '无'))
        out = json.dumps(data, ensure_ascii=False, indent=1)
        if raw.endswith('\n'):
            out += '\n'
        if dry:
            print('[dry] 不写盘。剩余 patches = %d' % len(patches))
            return 0
        with io.open(INDEX, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        print('[写盘] 剩余 patches = %d' % len(patches))
        return 0 if not left else 5

    added, kept, missing_card = [], [], []
    for nid in ids:
        if nid in patches:
            kept.append(nid)
            continue
        patches[nid] = C.AI_SELF_PATCH
        added.append(nid)
        if nid in cards:
            cards[nid]['patch'] = C.AI_SELF_PATCH
        else:
            # 卡片里没有这个人 ⇒ 运行时 `training_patch` 仍读得到（它只读 patches），
            # 但记一笔，别假装一致。
            missing_card.append(nid)

    print('   新写 %d 人：%s' % (len(added), ','.join(added)))
    print('   已有纠正句、未动 %d 人：%s' % (len(kept), ','.join(kept)))
    if missing_card:
        print('   !! cards 里找不到：%s' % ','.join(missing_card))

    # 已有纠正句的人也把 cards 副本补齐（只补齐，不改文本）
    for nid, p in patches.items():
        if nid in cards and cards[nid].get('patch') != p:
            cards[nid]['patch'] = p

    n = len(C.AI_SELF_PATCH)
    print('   纠正句 %d 字（check113 D6b 上限 160）' % n)
    if C._AI_RE.search(C.AI_SELF_PATCH):
        print('[中止] 纠正句自己被 _AI_RE 命中：%r' % C._AI_RE.search(C.AI_SELF_PATCH).group(0))
        return 4

    out = json.dumps(data, ensure_ascii=False, indent=1)
    if raw.endswith('\n'):
        out += '\n'
    if dry:
        print('[dry] 不写盘。总 patches = %d' % len(patches))
        return 0
    with io.open(INDEX, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('[写盘] %s（%d 字符）' % (INDEX, len(out)))
    print('       总 patches = %d' % len(patches))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
