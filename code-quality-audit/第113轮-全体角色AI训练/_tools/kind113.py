# -*- coding: utf-8 -*-
"""第113轮h · 角色档位普查：谁不需要「活人感」

## 用户口径（2026-10-25 逐字）
  「像是 oneshot 里很多没被制御的机器人不必要要求活人感」
  「别只顾着三人啊，这三人当示例然后再推进到其他人身上即可」

⇒ 性格校准那 4 句（「你大多数时候就是普通人在聊天」）**不能无差别套给机器人**。
  机器人按"普通人在聊天"演，反而会失真（机器不该寒暄、不该有社交焦虑）。
  但也**不是放开演极端** —— 用户上一条口径「要和正常人一样」的另一半是"别过火"。

## 这份脚本只做**候选**，不做决定
档位最终写在 `assets/npc/_kinds.json`（显式登记，默认 human）。理由：
  · 正则猜"是不是机器人"必然误伤（`ut_mettaton` 是机器人偶像、`os_the_world_machine`
    是机器但不是"角色"，`spamton` 是个人类化的程序……边界全靠人判）；
  · 但人判也需要**证据集中在眼前**，所以这里把命中的词和原文一并打出来。

★ 判据只管"疑似非人"，命中不等于就是非人。**漏判比误判代价小**：
  误判成 machine ⇒ 一个本来该有人味的角色变得机械；漏判 ⇒ 继续按 human 演，
  和现在一样。所以阈值取**保守**（要求多个不同证据词）。
"""

import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PERSONA_DIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
OUT = os.path.join(ROUND, '_evidence', 'kind113.json')

#: 强证据：只有非人角色的人设才会这么写。
STRONG = ('机器人', '机械体', '仿生', '未被制御', '未被控制', '型号', '本机',
          '我的程序', '程序所规定', '不是人类', '不是人', '人造', '终端机')
#: 弱证据：真人也可能提到，只用来加权。
WEAK = ('机械', '程序', '系统', '电路', '齿轮', '金属', '故障', '核心',
        '充电', '传感器', '协议', '运行', '代码')

#: 标题里出现这些 ⇒ 几乎可以确定（人设在【角色身份】第一句就交代了物种）
NAME_HINTS = ('bot', 'machine', 'robot', 'guardener', 'axis')

MIN_STRONG = 2   #: 至少 2 个不同的强证据词才算"疑似"


def scan(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        t = f.read()
    head = t[:1200]          # 【角色身份】段：物种通常在第一段就说了
    s_hit = [w for w in STRONG if w in t]
    w_hit = [w for w in WEAK if w in t]
    return {
        'strong': s_hit,
        'weak_n': len(w_hit),
        'weak': w_hit[:6],
        'head': head.replace('\r\n', ' ').replace('\n', ' ')[:150],
    }


def main(argv):
    files = sorted(fn for fn in os.listdir(PERSONA_DIR) if fn.endswith('.txt'))
    cand, rest = [], []
    for fn in files:
        nid = fn[:-4]
        r = scan(os.path.join(PERSONA_DIR, fn))
        r['id'] = nid
        sev = len(r['strong'])
        if sev >= MIN_STRONG:
            r['score'] = sev * 2 + r['weak_n']
            cand.append(r)
        else:
            rest.append((nid, sev, r['weak_n']))

    cand.sort(key=lambda r: -r['score'])
    print('人设 %d 份；**疑似非人** %d 个（强证据 ≥%d 个不同词）'
          % (len(files), len(cand), MIN_STRONG))
    print()
    print('  %-20s %-4s %-4s %s' % ('角色', '强', '弱', '命中的强证据词'))
    for r in cand:
        print('  %-20s %-4d %-4d %s' % (r['id'], len(r['strong']), r['weak_n'],
                                        '/'.join(r['strong'])))
        print('      %s' % r['head'][:110])

    print()
    print('── 边缘：只有 1 个强证据词的（**没进候选**，列出来给人工扫一眼）')
    edge = [(n, s, w) for n, s, w in rest if s == 1]
    for n, s, w in edge:
        print('  %-20s 强=1 弱=%d' % (n, w))
    if not edge:
        print('  （无）')

    with io.open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'min_strong': MIN_STRONG,
                   'candidates': [{k: v for k, v in r.items()} for r in cand],
                   'edge_strong1': [n for n, _s, _w in edge]},
                  f, ensure_ascii=False, indent=1)
    print('\n落盘（候选，不是决定）：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
