# -*- coding: utf-8 -*-
"""第十轮端到端演示：一周的真实感对话 → 多跳召回（**全程不打桩**）。

与 `verify_round10_graph.py` 的分工：
  · verify 用**构造的小图 + 打桩的抽词器**，证明"每一条规则都对"；
  · 本脚本用**真实中文句子 + 真实的 conversation_focus 抽词**，回答"用起来像不像
    人在回忆"。两者缺一不可：前者保证正确性，后者保证可用性。

演示要回答的三个问题：
  1. 多跳联想能不能把"没提过的东西"想起来（比如从"写代码"想到"咖啡"）？
  2. 每跳过滤能不能挡住那种"顺着顺着就扯远了"的漂移？
  3. 重排去重能不能让结果不啰嗦（同一件事只留一条）？

只写临时目录，不碰任何真机文件。
用法：C:\\Python311\\python.exe demo_recall_showcase.py
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')

TMP = tempfile.mkdtemp(prefix='ralsei_demo10_')
os.environ['RALSEI_DESKTOP'] = os.path.join(TMP, 'Desktop')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(TMP, 'scratch')
os.environ['RALSEI_LEGACY_MEMORY'] = os.path.join(TMP, '_none.json')
sys.path.insert(0, MODS)

from memory_system import MemorySystem                  # noqa: E402


class P(object):
    api_enabled = False


def line(s=''):
    print(s)


# 一周的对话（含几处"过几天又聊到"的重复 —— 那是联想形成的关键）
CORPUS = [
    # day 0
    (0, 'user', '今晚想写点代码，把那个宠物项目的记忆模块重构一下'),
    (0, 'ralsei', '写代码很费神吧，记得泡杯咖啡再开工'),
    (0, 'user', '对，咖啡已经泡好了，边喝边写'),
    (0, 'user', '这个塞尔达的剧情真的越玩越上头'),
    (0, 'ralsei', '海拉鲁的风景我也很喜欢，尤其是下雨的时候'),
    (0, 'user', '海拉鲁下雨会滑，爬山老是掉下去'),
    # day 1
    (1, 'user', '今天继续写代码，把对话的注意力锚做完了'),
    (1, 'ralsei', '那你要不要休息一下，喝口咖啡'),
    (1, 'user', '好，喝完咖啡继续'),
    # day 2
    (2, 'user', '昨天咖啡喝多了，晚上没睡好'),
    (2, 'ralsei', '那今天早点休息，别硬撑'),
    # day 3
    (3, 'user', '周末想去爬山，海拉鲁那种山其实挺像真的'),
    (3, 'ralsei', '爬山记得带水，别像游戏里那样滑下去'),
    # day 5
    (5, 'user', '写代码写累了，随便聊聊别的吧'),
    (5, 'ralsei', '那就聊聊最近看的书'),
    # 不相干的噪声（应当不被扯进来）
    (5, 'user', '楼下便利店新出的关东煮味道一般'),
    (6, 'user', '今天天气不错'),
]

DAY = 86400.0


def build():
    ms = MemorySystem(P())
    now = time.time()
    step = 0
    for day_off, who, text in CORPUS:
        n = now - (6 - day_off) * DAY + step * 60.0
        step += 1
        ms.add_fragment(text, who=who,
                        kind='dialogue' if who == 'user' else 'observation',
                        now=n)
    ms._build_index()          # 刷新 df（真实运行时由 update/consolidate 触发）
    return ms


def show(ms, cue, limit=3, note=''):
    line('')
    line('线索：「%s」%s' % (cue, ('   ' + note) if note else ''))
    kws = ms._kw_of(cue, limit=8)
    line('  （抽到的线索词：%s）' % ('、'.join(kws) or '（空）'))
    _h0 = dict(ms.recall_stats.get('by_hop_total') or {})
    items = ms.recall(cue, limit=limit)
    if not items:
        line('  → 什么都没想起来')
        return
    for it in items:
        via = (' ←由%s联想到' % '、'.join(it.get('via') or [])) if it.get('via') else ''
        tier = it.get('tier') or 'direct'
        hop = it.get('hop')
        line('  · [%s|%s%s|score=%s] %s%s' % (
            it.get('who'), tier,
            ('' if hop is None else '|hop=%d' % hop),
            it.get('score'), str(it.get('text'))[:38], via))
    # 把"这次召回的路径分布"也打出来：联想要是没生效，这里一眼就能看出来
    _h1 = dict(ms.recall_stats.get('by_hop_total') or {})
    _delta = {k: _h1.get(k, 0) - _h0.get(k, 0) for k in set(_h0) | set(_h1)}
    _delta = {k: v for k, v in _delta.items() if v}
    line('  （本次结果按跳数分布：%s）' % (_delta or '全是直接命中'))


line('=' * 74)
line('第十轮端到端演示：一周对话 → 受控多跳召回（真实中文 + 真实抽词，无桩）')
line('=' * 74)
ms = build()
line('')
line('片段数 = %d  索引词 = %d  图 = %s'
     % (len(ms.fragments), len(ms._index), ms._graph.stats()))
line('分层边明细（前 12 条，按边权）:')
_rows = []
for a, slot in ms.assoc.items():
    for b, e in slot.items():
        if a < b:                      # 无向边只打一次
            from memory_graph import edge_weight
            _rows.append((edge_weight(e), a, b, e.get('tier'), e.get('n')))
_rows.sort(reverse=True)
for w, a, b, tier, n in _rows[:12]:
    line('   %-8s %-8s w=%.3f  %s  n=%s' % (a, b, w, tier, n))

line('')
line('-' * 74)
line('【1】多跳联想：从"写代码"能不能想到"咖啡"？（两者从未同时出现在一句里）')
line('    注：联想分天然低于直接命中（这是设计：间接联想不该压过主线），')
line('        所以这里把 limit 放宽到 6，才看得见排在后半段的联想结果。')
show(ms, '想写点代码', limit=6)
line('')
line('【2】每跳防漂移：从"塞尔达"出发，会不会一路滑到"关东煮"这种无关话题？')
show(ms, '塞尔达的剧情', limit=6)
line('')
line('【3】重排去重：线索重复提了两次"咖啡"，结果会不会啰嗦？')
show(ms, '咖啡', limit=6)
line('')
line('【4】噪声对照：完全无关的线索应当想起很少的东西')
show(ms, '关东煮', limit=6)
line('')
line('-' * 74)
line('出口文案（交给模型的那段）：')
line(ms.recall_text('想写点代码', limit=3) or '(空)')
line('')
line('场景重构：')
line(ms.reconstruct_scene('塞尔达', limit=6) or '(没聚到同一天的片段)')
line('')
line('召回质量指标 = %s' % ms.recall_report())
line('离线巩固 = %s' % {k: v for k, v in ms.consolidate().items() if k != 'tune'})
line('巩固后指标（弱边压制量可能被 tune 调整）= %s' % ms.recall_report())
line('=' * 74)
