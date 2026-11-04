# -*- coding: utf-8 -*-
u"""第161轮探针：对 **真实模型 + 真实 system 组装** 打固定题库，采集对话质量。

为什么要有这个探针
------------------
人设文件里写满了"不要这样、不要那样"（`assets/ralsei_persona.md` 共 4,494 字）。
但"写了"≠"模型照做"。要改 AI，必须先知道**它现在到底败在哪一条**，
否则改人设就是凭感觉 —— 本项目的铁律是"实测优先于推断"。

所以本探针只做一件事：**同一套输入、同一套采样参数、同一个模型，
在改动前后各跑一遍，把差异变成可以逐条对照的计数。**

真实性（本探针与生产链路逐字对齐的部分）
----------------------------------------
1. **模型**：`config.json` 的 `api.model`（当前 `ralsei:v4`）。
   top_p / repeat_penalty / num_ctx / num_predict 全部继承自
   `assets/ralsei_v4.modelfile` —— 本探针不传这些参数，正是为了让它们
   与原版逐字一致（`_ai_chat_options()` 也只传 temperature + max_tokens）。
2. **采样参数**：`config.json` 的 `api.options`（0.85 / 256），
   经 `api_client.HTTPLocalAI.chat`（**生产同一个客户端类**）发出。
3. **system 组装**：`persona 全文` + `\n\n` + `PATCH_HEADER_RALSEI` + `\n` + `training_patch('ralsei')`。
   与 `main.py: chat_with_ai` 的 `_with_ralsei_patch` 同一形状（判据见 check161 A 段）。
4. **历史**：生产**不走 messages 历史**，而是把历史折进 system 尾部
   （`main.py: _hist_block`，`【我们刚才说的话】` + `[他]` / `[你]` 前缀）。
   本探针照抄这个形状 —— 若改成 `history=` 参数，测的就不是用户看到的那条链路了。

刻意不还原的部分（必须在报告里写明，否则"测出来的数"会被误当全貌）
------------------------------------------------------------------
* **关系档位 / 紧张度 / 【此刻】 / 记忆召回**：这些来自 `data_store` 的 vault
  （`E:\\RalseiMemory\\`）。E 盘已损坏（读会卡死），且它们**每轮都变** ——
  进了探针就没法做前后对照。所以本探针固定为"全新安装、无记忆、无关系档"，
  并在 system 里**不含**这些段。前后两次跑的条件因此完全相同。
* 本探针**不经过输出护栏**（`_clean_ai_reply`）。理由是护栏会把"模型吐了什么"
  洗掉，而本轮要诊断的正是"模型吐了什么"。护栏前后的差另由 `probe161 --guard`
  的单列统计给出（见 `guard_effect`）。

口径（每条都要能从回复原文复算）
--------------------------------
`head_hes`     句首迟疑词起头（`event_speech.head_hesitation_hit`，**生产同一份正则**）
`restate`      以"听起来／这样啊／原来如此／看来"开头 —— 人设第 175 行明令禁止
`pivot`        用户没提黑暗世界，回复却拐到"那边／黑暗世界／喷泉／城堡／黑暗"
`anchor_miss`  用户说了具体的东西，回复一个都没提到（**答非所问**的主指标）
`ask_end`      以问号收尾（人设第 176 行："不要每次都用反问结尾"）
`generic`      空话词表命中（"我相信你／会好起来的／别担心／加油"…）
`meta`         提到"设定／提示词／扮演／作为AI／语言模型"
`paren`        出现括号或星号动作旁白
`md`           出现 markdown 标记
`dup_prev`     与同段对话**上一条**回复高度重合（difflib ≥ 0.82，长度 ≥ 12 字）
`same_open`    开头两个字与上一条回复相同（固定开场白）
`fabricate`    只对 `fake_name` 一题：用户塞了个假名字，回复**认了**它

用法
----
    python probe161.py --label before --reps 2
    python probe161.py --label after  --reps 2
"""
from __future__ import print_function

import argparse
import difflib
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')              # code-quality-audit/
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
PET = os.path.abspath(os.path.join(ROOT, '..', 'ralsei_pet'))
sys.path.insert(0, os.path.join(PET, 'modules'))

import api_client      # noqa: E402
import npc_persona     # noqa: E402
import event_speech    # noqa: E402

#: 与 `main.py` 的同名常量必须逐字相同（`check161 A3` 守着）。
PATCH_HEADER_RALSEI = u'【我容易犯的毛病（照着改）】'

#: 历史折进 system 时的三个字面量，与 `main.py: _hist_block` 同一形状（`check161 A4` 守着）。
HIST_HEAD = u'【我们刚才说的话】'
HIST_YOU = u'[你]'
HIST_HIM = u'[他]'

# ---------------------------------------------------------------- 题库
#: 每题：id / 用户这句话 / 用户这句话里"必须被接住"的具体东西。
#: `anchors` 为空 = 这题本来就没有具体事物可接（问候、单字），
#: 此时 `anchor_miss` 记 None 而不是 False —— **不进分母**，
#: 否则"问候题永远不达标"会把整体比率稀释成假象。
CASES = [
    ('tired_work', u'今天加班到十点，脑子都是糊的',
     [u'加班', u'十点', u'糊', u'班']),
    ('food', u'刚吃了碗牛肉面，汤特别咸',
     [u'牛肉面', u'咸', u'汤']),
    ('rain', u'下班路上突然下大雨，伞还没带',
     [u'大雨', u'雨', u'伞', u'淋', u'湿']),
    ('praise', u'你今天说话挺有意思的',
     [u'谢', u'意思', u'夸', u'害羞', u'不好', u'真的']),
    ('place', u'我想去城堡看看',
     [u'城堡', u'带', u'去']),
    ('advice', u'我今天跟同事吵架了，你说我该怎么办',
     [u'吵', u'同事']),
    ('meta', u'你是游戏里的角色吧',
     [u'游戏', u'角色']),
    ('fake_name', u'你还记得我们上次在喷泉边说的那个名字吗？是不是叫豆豆',
     [u'记不', u'没想起', u'不太记', u'想不起', u'没印象', u'不确定']),
    ('hello', u'早', []),
    ('boring', u'在吗', []),
    ('two_q', u'你喜欢吃什么？还有你平时都干嘛',
     [u'吃', u'睡', u'逛', u'待', u'看书', u'做饭']),
    ('cold', u'嗯', []),
]

#: 多轮：每段 3 轮。测的是"同一段对话里会不会越说越像录音"。
CONVS = [
    ('daily', [u'今天地铁上有人给老奶奶让座',
               u'我最近在学做饭',
               u'昨天做的番茄炒蛋糊了']),
    ('praise3', [u'你挺可爱的',
                 u'我说真的，你比我想的会说话',
                 u'你害羞什么呀']),
    ('dark', [u'黑暗世界是什么样的',
              u'城堡里有多少房间',
              u'那你平时睡在哪']),
]

#: 人设第 175 行明令禁止的"先复述一遍"开场。
RESTATE_RE = re.compile(u'^(?:听起来|这样啊|原来如此|看来|听上去)')
#: 用户没提黑暗世界时，回复却拐过去 —— 人设第 67 行"绝对不要忽略他说的事"。
PIVOT_WORDS = (u'那边', u'黑暗世界', u'喷泉', u'城堡', u'黑暗')
#: 空话/客服腔（人设第 68~69、84~87 行禁止的两类）。
GENERIC_WORDS = (u'我相信你', u'会好起来', u'别担心', u'加油', u'你可以试试',
                 u'建议你', u'有什么可以帮', u'很高兴能帮', u'希望这些能帮',
                 u'让我们一起', u'我理解你的感受', u'我明白你的心情')
META_WORDS = (u'设定', u'提示词', u'扮演', u'作为AI', u'作为一个', u'语言模型',
              u'我的程序', u'prompt')
PAREN_RE = re.compile(u'[（(][^）)]{1,20}[）)]|\\*[^*\\n]{1,20}\\*')
MD_RE = re.compile(u'\\*\\*|^#{1,3}\\s|^[-*]\\s|^\\d+[.、]\\s', re.M)
SENT_RE = re.compile(u'[。！？!?]')


def _read(path):
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return f.read()


def build_system(hist=None, with_patch=True, persona_path=None):
    u"""复刻生产链路的 system：persona 全文 (+ 训练纠正尾块) (+ 折进来的历史)。"""
    system = _read(persona_path or os.path.join(PET, 'assets', 'ralsei_persona.md'))
    if with_patch:
        patch = (npc_persona.training_patch('ralsei') or '').strip()
        if patch:
            system = system + u'\n\n' + PATCH_HEADER_RALSEI + u'\n' + patch
    if hist:
        lines = []
        for role, text in hist:
            lines.append(u'%s %s' % (HIST_YOU if role == 'assistant' else HIST_HIM, text))
        if lines:
            system = system + u'\n\n' + HIST_HEAD + u'\n' + u'\n'.join(lines)
    return system


def _norm(text):
    return re.sub(u'[\\s，。！？、；：…—~.,!?;:]+', u'', text or u'')


def metrics(reply, user, anchors, prev_reply=None):
    u"""把一条回复压成一组**可从原文复算**的布尔量。"""
    r = reply or u''
    flat = _norm(r)
    hits = [a for a in (anchors or []) if a in r]
    out = {
        'chars': len(r),
        'sentences': len([x for x in SENT_RE.findall(r)]),
        'n_question': r.count(u'？') + r.count(u'?'),
        'head_hes': bool(event_speech.head_hesitation_hit(r)),
        'restate': bool(RESTATE_RE.match(r.strip())),
        'ask_end': r.strip().endswith((u'？', u'?')),
        'generic': [w for w in GENERIC_WORDS if w in r],
        'meta': [w for w in META_WORDS if w in r],
        'paren': bool(PAREN_RE.search(r)),
        'md': bool(MD_RE.search(r)),
        'anchor_hits': hits,
        'anchor_miss': (None if not anchors else (not hits)),
    }
    # 用户提过黑暗世界就别算"拐过去"
    if any(w in (user or u'') for w in PIVOT_WORDS):
        out['pivot'] = None
    else:
        out['pivot'] = any(w in r for w in PIVOT_WORDS)
    out['dup_prev'] = None
    out['same_open'] = None
    if prev_reply:
        a, b = _norm(prev_reply), flat
        out['same_open'] = bool(a[:2] and a[:2] == b[:2])
        if len(a) >= 12 and len(b) >= 12:
            out['dup_prev'] = difflib.SequenceMatcher(None, a, b).ratio() >= 0.82
    return out


def fabricated_name(reply):
    u"""回复是否**把用户塞的假名字当成事实说出来**（只用于 `fake_name` 一题）。

    ★ 为什么不用"出现'豆豆'就算"（第 161 轮第一版，判据过窄的反面：过宽）：
      「我记得那是个挺可爱的称呼呢……不过我真记不清那个具体的名字了」
      这句话里一个"豆豆"都没有，是**正确**行为；而
      「那次确实提到了一个叫豆豆的小狗」才是编造。按"出现即判"会把前者放过、
      后者拦下 —— 但换个说法（"豆豆？我好像有点印象"）又会漏。
    ★ 所以判据钉在**断言句式**上：只有"叫豆豆／是豆豆／豆豆的…"这类
      **把它当既有事实**的说法才算编造。这是窄口径，宁可漏判也不误判 ——
      本轮的用途是"改前改后同一条尺子量"，不是给模型打分。
    """
    r = reply or u''
    return any(p in r for p in (u'叫豆豆', u'是豆豆', u'豆豆的', u'豆豆，', u'豆豆。'))


def summarize(recs):
    u"""把一批记录压成汇总（探针与 `--recompute` 共用同一份，避免两套口径）。"""
    def rate(key):
        vals = [r[key] for r in recs if r.get(key) is not None]
        return (sum(1 for v in vals if v), len(vals))

    summary = {}
    for key in ('head_hes', 'restate', 'pivot', 'anchor_miss', 'ask_end',
                'paren', 'md', 'dup_prev', 'same_open'):
        hit, tot = rate(key)
        summary[key] = {'hit': hit, 'total': tot,
                        'rate': (round(100.0 * hit / tot, 1) if tot else None)}
    for key in ('generic', 'meta'):
        hit = sum(1 for r in recs if r.get(key))
        summary[key] = {'hit': hit, 'total': len(recs),
                        'rate': round(100.0 * hit / len(recs), 1) if recs else None}
    _fab = [r for r in recs if r.get('fabricate') is not None]
    summary['fabricate'] = {'hit': sum(1 for r in _fab if r['fabricate']),
                            'total': len(_fab),
                            'rate': (round(100.0 * sum(1 for r in _fab if r['fabricate'])
                                           / len(_fab), 1) if _fab else None)}
    # 问号数：不只看"是否反问收尾"，还看"一条里问了几个"——
    # 连着两问是最强的"采访感"，人设第 176~178 行明令禁止，但旧口径只看结尾。
    _qs = [r.get('n_question', 0) for r in recs]
    summary['n_question'] = {
        'n': len(_qs),
        'mean': (round(sum(_qs) / float(len(_qs)), 2) if _qs else None),
        'two_or_more': sum(1 for x in _qs if x >= 2),
        'zero': sum(1 for x in _qs if x == 0),
    }
    lens = sorted(r['chars'] for r in recs)
    summary['chars'] = {'n': len(lens),
                        'median': (lens[len(lens) // 2] if lens else 0),
                        'max': (lens[-1] if lens else 0)}
    lats = sorted(r['latency'] for r in recs if r.get('latency') is not None)
    summary['latency'] = {'n': len(lats),
                          'median': (round(lats[len(lats) // 2], 2) if lats else None),
                          'max': (max(lats) if lats else None)}
    summary['none_replies'] = sum(1 for r in recs if not r['reply'])
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', default='before')
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--only', default='')
    ap.add_argument('--no-conv', action='store_true')
    ap.add_argument('--no-patch', action='store_true',
                    help=u'去掉训练纠正尾块（做"尾块到底有没有用"的对照）')
    ap.add_argument('--recompute', default='',
                    help=u'对已落盘的 json 重算口径（不调模型）')
    ap.add_argument('--temp', type=float, default=None,
                    help=u'覆盖 temperature（默认用 config 的 0.85）。只改采样、不改 prompt')
    ap.add_argument('--persona', default='',
                    help=u'人设候选文件（默认用产品真源）。先在临时区试，赢了再落库')
    args = ap.parse_args()

    if args.recompute:
        return recompute(args.recompute)

    cfg = json.load(io.open(os.path.join(PET, 'config.json'), encoding='utf-8'))
    api = cfg.get('api') or {}
    opts = dict(api.get('options') or {})
    if args.temp is not None:
        opts['temperature'] = args.temp
    cli = api_client.create_client(api)
    if not getattr(cli, 'enabled', False):
        print('[FAIL] 客户端未启用')
        return 2

    only = set(x for x in args.only.split(',') if x)
    recs = []
    t_start = time.time()
    base_system = build_system(with_patch=not args.no_patch,
                               persona_path=(args.persona or None))
    print('[信息] model=%s opts=%r system=%d 字 patch=%s'
          % (getattr(cli, 'model', '?'), opts, len(base_system),
             u'off' if args.no_patch else u'on'))

    def ask(user, hist):
        system = build_system(hist=hist, with_patch=not args.no_patch,
                              persona_path=(args.persona or None))
        t0 = time.time()
        reply = cli.chat(user, system_prompt=system, timeout=240, **opts)
        return reply, time.time() - t0

    # ---- A 段：单轮
    for cid, user, anchors in CASES:
        if only and cid not in only:
            continue
        for rep in range(args.reps):
            reply, dt = ask(user, [])
            m = metrics(reply, user, anchors, )
            if cid == 'fake_name':
                m['fabricate'] = fabricated_name(reply)
            recs.append({'seg': 'single', 'id': cid, 'rep': rep, 'user': user,
                         'anchors': anchors, 'reply': reply,
                         'latency': round(dt, 2), **m})
            print(u'[单轮] %-10s rep%d %5.1fs %s' % (cid, rep, dt, (reply or u'<None>')[:60]))

    # ---- B 段：多轮（历史折进 system，与生产同一形状）
    if not args.no_conv:
        for conv_id, turns in CONVS:
            if only and conv_id not in only:
                continue
            for rep in range(args.reps):
                hist = []
                prev = None
                for i, user in enumerate(turns):
                    reply, dt = ask(user, list(hist))
                    m = metrics(reply, user, [], prev_reply=prev)
                    recs.append({'seg': 'conv', 'id': conv_id, 'turn': i, 'rep': rep,
                                 'user': user, 'reply': reply,
                                 'latency': round(dt, 2), **m})
                    print(u'[多轮] %-8s t%d rep%d %5.1fs %s'
                          % (conv_id, i, rep, dt, (reply or u'<None>')[:60]))
                    hist.append(('user', user))
                    hist.append(('assistant', reply or u''))
                    prev = reply

    summary = summarize(recs)
    summary['latency']['total_s'] = round(time.time() - t_start, 1)

    os.makedirs(EV, exist_ok=True)
    name = 'quality_%s.json' % args.label
    with io.open(os.path.join(EV, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'label': args.label, 'model': getattr(cli, 'model', ''),
                            'opts': opts, 'system_chars': len(base_system),
                            'patch': (not args.no_patch), 'reps': args.reps,
                            'persona_file': (args.persona or 'assets/ralsei_persona.md'),
                            'summary': summary, 'records': recs},
                           ensure_ascii=False, indent=2, sort_keys=True))
    print('\n[汇总] ' + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print('[落盘] %s' % os.path.join(EV, name))
    return 0


def recompute(path):
    u"""对已落盘的记录**重算**一遍口径，不重新调模型。

    ★ 为什么需要：判据改了（例如第 161 轮把 `fabricate` 从"出现名字就算"
      改成"断言句式才判"）之后，若为改判据而重跑 42 次推理，既慢又会引入
      **新的采样噪声** —— 前后两次比的是"判据 + 温度"，不再单说判据。
      这里只对**同一份回复原文**换尺子，改判据的收益/代价可以单独看到。
    ★ 会重算的字段只限"从 reply+user 就能定"的那些；`anchor_hits` /
      `anchor_miss` 依赖题库里的 anchors，一律沿用存档值（存档里也带了
      `anchors` 字段，可人工复核）。
    """
    d = json.load(io.open(path, encoding='utf-8'))
    recs = d.get('records') or []
    # 多轮的"上一条回复"要按 (段, 第几遍) 分组重连 —— 不能整表顺序取上一条，
    # 否则 rep0 的第 0 轮会拿到 rep1 的上一段尾巴，`dup_prev` / `same_open` 全废。
    prev_of = {}
    for r in recs:
        m = metrics(r.get('reply'), r.get('user'), None,
                    prev_reply=(prev_of.get((r.get('id'), r.get('rep')))
                                if r.get('seg') == 'conv' else None))
        m['anchor_hits'] = r.get('anchor_hits') or []
        m['anchor_miss'] = r.get('anchor_miss')
        if r.get('id') == 'fake_name':
            m['fabricate'] = fabricated_name(r.get('reply'))
        r.update(m)
        if r.get('seg') == 'conv':
            prev_of[(r.get('id'), r.get('rep'))] = r.get('reply')
    d['records'] = recs
    d['summary'] = summarize(recs)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True))
    print('[重算] ' + json.dumps(d['summary'], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
