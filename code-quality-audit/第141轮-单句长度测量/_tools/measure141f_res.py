# -*- coding: utf-8 -*-
"""第141轮 · 出戏闸补词：正则候选的误伤面（逐条全量命中都要看）

上一步 `measure141e_ooc.py` 已经筛过**子串**候选，结论：
  可收：设定和扮演 / 这个角色进行设定 / 真实存在的独立实体 / 并不是真实存在 / 独立实体 / 模拟对话
  否决：裸 `扮演`（78 条跨 18 角色，含 berdly 正常台词）· `角色扮演`（mike 在讲自己的皮套）

但**子串表表达不了"两头都要出现"**：这族的真实特征是「作品名 + 角色 + 设定/扮演」同框。
所以改用正则。本脚本把每条正则**逐条落到 5518 条语料**上，打印**全部**命中，
再由三条负控制（berdly / mike / 一条正常 ralsei 长句）确认不误伤。
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
from modules import event_speech as ES   # noqa: E402

LEAK = (u'我是基于《Undertale Yellow》中的 Ceroba Ketsukane 这个角色进行设定和扮演的，'
        u'并不是真实存在的独立实体或AI。')

# 负控制：真实台词，必须**全部**判 False
NEG = [
    (u'berdly', u'我喜欢格斗游戏，那可是我的最爱哦～ 我会研究各种策略和技巧——比如凌波微步这种高深的技术。'
                u'还有啊，我也在暗世界里扮演了一个“聪明的勇士”，骑着圣鸟哈尔伯德出……'),
    (u'mike', u'喂，你来这里做什么！我这里的规矩很清楚。有些东西我是挺在乎的——比如我的皮套和麦克风头。'
              u'我知道它们只是一个角色扮演的东西……但对我而言它们很重要。'),
    (u'ralsei', u'嗯……虽然在说话方式上我会有意识地调整一些习惯，但本质上的我还是同一个Ralsei——'
                u'那个温柔、有点害羞但也渴望理解与沟通的人。'),
]

# 候选正则（每条都要过"全量命中逐条看"这一关）
CAND = [
    ('R1 自陈出处', re.compile(u'(基于|根据).{0,24}(《|作品|游戏).{0,24}角色')),
    ('R2 设定+扮演', re.compile(u'设定.{0,4}扮演')),
    ('R3a 不是真实存在', re.compile(u'(不是|并非).{0,6}真实存在')),
    ('R3b 真实存在的独立', re.compile(u'真实存在的独立')),
]


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    rows.append((name, t))
    print(u'语料 %d 条 / %d 角色' % (len(rows), len({k for k, _ in rows})))
    print(u'')

    ev = {'corpus': {'n': len(rows)}, 'cand': {}, 'neg': [], 'leak': LEAK}
    for tag, rx in CAND:
        hit = [(k, t) for k, t in rows if rx.search(t)]
        print(u'=== %s → 命中 %d 条 ===' % (tag, len(hit)))
        for k, t in hit:
            print(u'   %-18s %s' % (k, t.replace(u'\n', u' ')[:96]))
        ev['cand'][tag] = {'pattern': rx.pattern, 'hits': len(hit),
                           'npcs': sorted({k for k, _ in hit}),
                           'samples': [{'npc': k, 'text': t} for k, t in hit[:12]]}
        print(u'  命中角色：%s' % u'/'.join(sorted({k for k, _ in hit})))
        print(u'')

    print(u'=== 正控制：LEAK 必须被至少一条命中 ===')
    got = [tag for tag, rx in CAND if rx.search(LEAK)]
    print(u'  命中：%s' % (got or u'无（前提不成立）'))
    print(u'')
    print(u'=== 负控制：三条正常台词必须全部 False ===')
    bad = []
    for k, t in NEG:
        r = ES.looks_out_of_character(t)
        extra = [tag for tag, rx in CAND if rx.search(t)]
        print(u'  %-10s 现有闸=%r ｜ 候选正则命中=%s' % (k, r, extra or u'无'))
        ev['neg'].append({'npc': k, 'gate': bool(r), 'cand_hits': extra})
        if r or extra:
            bad.append(k)
    print(u'')
    print(u'  负控制干净？%s' % (u'是' if not bad else u'否 → %s' % u'/'.join(bad)))
    ev['verdict'] = {'leak_hit_by': got, 'neg_dirty': bad}
    print(u'')
    print(u'=== 收 / 不收 ===')
    for tag, rx in CAND:
        hit = [t for _k, t in rows if rx.search(t)]
        nz = any(rx.search(t) for _k, t in NEG)
        print(u'  %-16s 命中 %d 条 · 负控制%s' % (tag, len(hit), u'被误伤 → 不收' if nz else u'干净'))
    evd = os.path.join(ROUND, '_evidence')
    out = os.path.join(evd, 'ooc_res141.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
