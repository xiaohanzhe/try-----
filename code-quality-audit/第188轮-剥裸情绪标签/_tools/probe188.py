# -*- coding: utf-8 -*-
u"""第188轮 · 取证脚本：戊闸（裸情绪标签）**改前 / 改后**逐轮对照。

## 为什么要有这个脚本

`check188.py` 的 E 段只钉"改后残留 ≤ 250 轮"。**改前那 312 轮**如果只写在注释里，
下一轮谁也无法复算。所以这里把两版行为都跑一遍，落成 JSON 留档。

## "改前"怎么复现（不改产品代码）

戊闸 `_kill_bare_label` 读的是模块级 `_BARE_LABEL_RE`。把它临时换成一个
**永不匹配**的正则 `(?!)`，戊闸就退化成 no-op ⇒ 等价于第187轮的三道闸版本。
跑完必须还原（`finally`），否则同一进程里后续判据会误判。

★ 这同时是一条**负控制**：如果换了 `(?!)` 之后残留数没回到 312，说明
  "改前 312" 这个基线本身不成立，本轮的效果数字就是假的。

## 输出

`_evidence/after188.json`。字段：

    total        419               带 `ACTION_PAREN` 的轮数
    before_left  312 / before_turns  三道闸版本仍残留括号的轮
    after_left   243 / after_turns   四道闸版本仍残留括号的轮
    killed_forms 戊闸实际删掉的括号内容 top 40（含次数）
    still_forms  改后仍残留的括号内容 top 40（含次数）—— 就是 B/C/D 族的盘子

用法（幂等，直接覆盖）：
    C:/Python311/python.exe probe188.py
"""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
RAW30 = os.path.join(REPO, 'code-quality-audit', u'第113轮-全体角色AI训练',
                     '_evidence', 'raw30')
OUT = os.path.join(ROUND, '_evidence', 'after188.json')

sys.path.insert(0, MODS)
import event_speech as E                       # noqa: E402

PAREN = re.compile(u'[（(][^（（））]{1,200}[)）]')


def latest(path, target=48):
    u"""取该 jsonl 里 `turns_n == 48` 的最后一条记录（与 check188 同一取法）。"""
    best = None
    for line in io.open(path, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict) and r.get('turns_n') == target:
            best = r
    return best


def collect():
    u"""返回 [(轮 id, 原文)] —— 只要带 `ACTION_PAREN` 的轮。"""
    rows = []
    for f in sorted(os.listdir(RAW30)):
        if not f.endswith('.jsonl'):
            continue
        rec = latest(os.path.join(RAW30, f))
        if not rec:
            continue
        for i, t in enumerate(rec.get('turns') or []):
            if not any(v[0] == 'ACTION_PAREN' for v in (t.get('violations') or [])):
                continue
            rows.append((u'%s#%d' % (f[:-6], i), t.get('final') or u''))
    return rows


def run(raws):
    u"""逐条跑一遍当前护栏，返回 (残留轮数, 残留括号内容 Counter)。"""
    left = 0
    forms = Counter()
    for _, txt in raws:
        out = E.strip_action_parentheticals(txt)
        hit = PAREN.findall(out)
        if hit:
            left += 1
            forms.update(hit)
    return left, forms


def main():
    if not os.path.isdir(RAW30):
        print(u'语料目录不在：%s' % RAW30)
        return 2
    raws = collect()
    total = len(raws)

    _orig = E._BARE_LABEL_RE
    _orig_voice = E._rescue_voice
    try:
        E._BARE_LABEL_RE = re.compile(u'(?!)')      # 永不匹配 ⇒ 戊闸退化成 no-op
        # ★★ 第189轮追加：己闸（发声直出）也必须一起禁掉，否则"改前"里混进了
        #    189 轮的效果（实测会从 312 掉到 300），基线就串味了。
        E._rescue_voice = lambda m: m.group(0)
        before_left, _ = run(raws)
        before_outs = dict((k, E.strip_action_parentheticals(v)) for k, v in raws)
    finally:
        E._BARE_LABEL_RE = _orig                    # ★ 必须还原
        E._rescue_voice = _orig_voice

    after_left, still = run(raws)
    after_outs = dict((k, E.strip_action_parentheticals(v)) for k, v in raws)

    killed = Counter()
    for k, txt in raws:
        gone = Counter(PAREN.findall(before_outs[k])) - Counter(PAREN.findall(after_outs[k]))
        killed.update(gone)

    d = {
        'total': total,
        'before_left': before_left,
        'after_left': after_left,
        'killed_n': before_left - after_left,
        'killed_forms': [[u, c] for u, c in killed.most_common(40)],
        'still_forms': [[u, c] for u, c in still.most_common(40)],
    }

    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2))

    print(u'带 ACTION_PAREN 的轮：%d' % total)
    print(u'改前（第187轮那三道闸）残留：%d 轮' % before_left)
    print(u'现在（五道闸：己/丁/甲/丙/戊）残留：%d 轮' % after_left)
    print(u'合计消掉：%d 轮' % (before_left - after_left))
    print(u'戊闸实际删掉的括号内容 top10：')
    for u_, c in killed.most_common(10):
        print(u'  %-16s %d' % (u_, c))
    print(u'改后仍残留 top10（B/C/D 族的盘子）：')
    for u_, c in still.most_common(10):
        print(u'  %-40s %d' % (u_, c))
    print(u'→ %s' % OUT)

    # ★ 负控制自带：换回 no-op 必须回到 312，否则"改前"这个基线不成立。
    if before_left != 312:
        print(u'[!] 改前基线不是 312（实测 %d）—— 语料或护栏变了，'
              u'报告里的对照数字必须重写' % before_left)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
