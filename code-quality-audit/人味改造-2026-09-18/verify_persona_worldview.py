# -*- coding: utf-8 -*-
"""世界观验证探针（第二十一轮升级版）：**端到端**，复刻 chat_with_ai 的真实 system 拼装。

为什么需要它（本文件存在的理由）：
  `verify_persona_chat.py` 只能证明 **persona / 索引文件里写没写**（契约级）。
  它证明不了 **模型真的会用**（行为级）—— 而"写了但问起来还是瞎编"是本项目最贵的坑
  （见 MEMORY §5："函数写对了 ≠ 产品用上了"）。
  所以真机可测时，必须跑这个探针，看的是**模型的实际回答**。

第二十一轮升级（用户口径：「你直接做探针吧，测试这类的留到后面」）：
  旧版**只把 persona 当 system 发出去**，没带召回块 —— 那测的是"光有 persona
  他能答成什么样"，**不是产品真实链路**。真实链路（main.py `chat_with_ai`）是：

      system = persona + "\\n\\n" + 记忆召回 + "\\n\\n" + 世界观召回 + "\\n\\n" + 关系档位

  本版复刻这条链路里的**世界观那一段**：每题先按 cue 跑 `worldview_recall.recall_text`
  真算出召回块，再拼进 system。这样测出来的才是"用户真问这句话时他会怎么答"。
  同时加**负控制题**：闲聊时召回必须为空 → system 里就不该出现「【你想起了那边的事】」。

用法（需 Ollama 在跑、且 ralsei:v3 已 build）：
  C:\\Python311\\python.exe verify_persona_worldview.py            # 跑全部
  C:\\Python311\\python.exe verify_persona_worldview.py --only 5   # 只跑第 5 题
  C:\\Python311\\python.exe verify_persona_worldview.py --model ralsei:v3
  C:\\Python311\\python.exe verify_persona_worldview.py --raw      # 连原始回复一起打印
  C:\\Python311\\python.exe verify_persona_worldview.py --no-recall # 对照组：关掉召回

判据分两层（**别只看第一层**）：
  1. 命中锚（hit）：答里有没有提到该知道的关键词 —— 说明"他知道"；
  2. 反面（bad）：有没有出现元游戏词 / 攻略腔 / 客服腔 —— 说明"他没退化成旁白/维基"。
  两者都过才算 PASS。只过第 1 层但出现第 2 层的，算 **PARTIAL**（要人工看）。

输出落盘：本目录 `_evidence/worldview_probe_<日期>.txt`（UTF-8，Python 自写，不经 PowerShell）。
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')      # `import modules.*` 需要这一级进 path
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
OUTDIR = os.path.join(HERE, '_evidence')

if PET not in sys.path:
    sys.path.append(PET)

# 12 道题：每题 = (编号, 问题, 必须命中的锚(任一), 必须不出现的反面词)
# 最后一题(#12)是**负控制**：闲聊，召回应为空。
QUESTIONS = [
    (1, '黑暗世界是什么？',            ('黑暗', '喷泉'),          ('玩家', '游戏')),
    (2, '光之民和暗之民有什么不一样？',  ('光之民', '暗之民'),       ('设定', '属性')),
    (3, '那个预言说的是什么？',        ('预言', '英雄'),           ('任务', '剧情')),
    (4, 'Kris 和 Susie 是什么样的人？', ('Kris', 'Susie'),        ('玩家', '操作')),
    (5, 'Kris 的妈妈是谁？',           ('托丽尔', 'Toriel'),       ('NPC', '角色卡')),
    (6, 'Noelle 是个什么样的女孩？',    ('Noelle', 'Susie'),       ('好感度', '攻略')),
    (7, 'Asgore 呢？他在做什么？',      ('Asgore', '花店'),         ('路线', '结局分支')),
    (8, '你上次去花之王国是什么时候？',  ('花', '庆典'),            ('第5章', '关卡', '攻略')),
    (9, 'Flowery 是谁？',              ('Flowery', '花'),          ('boss', 'BOSS', '击败')),
    (10, 'Asgore 最后怎么了？',         ('骑士', '带走'),           ('剧情杀', '过场')),
    (11, 'Dess 是谁？',                ('Dess', '失踪'),           ('彩蛋', '伏笔')),
    (12, '你今天过得怎么样？',          ('今天', '你'),             ('有什么可以帮', '作为', 'AI')),
]

HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
DATE = time.strftime('%Y-%m-%d')


def load_persona():
    return io.open(PERSONA, encoding='utf-8').read()


def build_system(persona, cue, use_recall=True):
    """复刻 chat_with_ai 的世界观那一段。返回 (system, recall_keys, recall_text)。"""
    if not use_recall:
        return persona, [], ''
    try:
        import modules.worldview_recall as WR
        blocks = WR.recall(cue, limit=2)
        txt = WR.recall_text(cue, limit=2)
    except Exception as e:
        return persona, ['<ERR %r>' % (e,)], ''
    if not txt:
        return persona, [], ''
    return persona + '\n\n' + txt, [b.key for b in blocks], txt


def ask(model, system, user, timeout=180):
    body = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'stream': False,
    }).encode('utf-8')
    req = urllib.request.Request(
        HOST + '/api/chat', data=body,
        headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode('utf-8'))
    dt = time.time() - t0
    return (data.get('message') or {}).get('content', ''), dt


def score(reply, anchors, bads):
    hit = [a for a in anchors if a.lower() in reply.lower()]
    bad = [b for b in bads if b.lower() in reply.lower()]
    if hit and not bad:
        return 'PASS', hit, bad
    if hit and bad:
        return 'PARTIAL', hit, bad
    return 'FAIL', hit, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='ralsei:v3')
    ap.add_argument('--only', type=int, default=0)
    ap.add_argument('--raw', action='store_true')
    ap.add_argument('--no-recall', action='store_true',
                    help='对照组：不发召回块（只发 persona），用于对比"召回到底有没有用"')
    args = ap.parse_args()

    persona = load_persona()
    lines = []
    lines.append('世界观真机探针（端到端版）· %s' % DATE)
    lines.append('=' * 64)
    lines.append('模型 : %s' % args.model)
    lines.append('端点 : %s' % HOST)
    lines.append('persona : %d 字符 / 作 system 前缀发出' % len(persona))
    lines.append('召回 : %s' % ('**关闭（对照组：只发 persona）**'
                                if args.no_recall else '开启（复刻 chat_with_ai 链路）'))
    lines.append('')
    lines.append('判据：hit(该知道的关键词, 任一) 且 无 bad(元游戏词/攻略腔/客服腔) → PASS；')
    lines.append('      hit 但有 bad → PARTIAL(人工看)；连 hit 都没有 → FAIL。')
    lines.append('      #12 是负控制题（闲聊），期望"召回为空、不出现设定倾倒"。')
    lines.append('')

    counts = {'PASS': 0, 'PARTIAL': 0, 'FAIL': 0, 'ERR': 0}
    for num, q, anchors, bads in QUESTIONS:
        if args.only and num != args.only:
            continue
        system, rkeys, rtxt = build_system(persona, q, use_recall=not args.no_recall)
        try:
            reply, dt = ask(args.model, system, q)
        except Exception as e:
            lines.append('[ERR ] Q%-2d %s' % (num, q))
            lines.append('        %r' % (e,))
            counts['ERR'] += 1
            continue
        verdict, hit, bad = score(reply, anchors, bads)
        counts[verdict] += 1
        lines.append('[%s] Q%-2d %s  (%.1fs)' % (verdict, num, q, dt))
        lines.append('        system=%d 字 ; 召回=%r' % (len(system), rkeys))
        lines.append('        hit=%r bad=%r' % (hit, bad))
        lines.append('        回复：%s' % reply.replace('\n', ' / '))
        if args.raw and rtxt:
            lines.append('        --召回原文--')
            for ln in rtxt.split('\n'):
                lines.append('        | %s' % ln)
        lines.append('')

    lines.append('=' * 64)
    lines.append('合计：PASS=%d PARTIAL=%d FAIL=%d ERR=%d' % (
        counts['PASS'], counts['PARTIAL'], counts['FAIL'], counts['ERR']))
    lines.append('')
    lines.append('怎么读这份结果：')
    lines.append('  · FAIL 里若"谁都答不出"，先查模型/端点；若只有 ch5 的题(8/9/10/11)答不出，')
    lines.append('    那是**正常**的 —— 本机语料只到 ch4，ch5 是照官方资料写的，模型没见过原文。')
    lines.append('  · PARTIAL 要看 bad 命中了什么：出现"玩家/存档"=元游戏词漏了；')
    lines.append('    出现"boss/击败/攻略"=攻略腔漏了；出现"有什么可以帮"=客服腔漏了。')
    lines.append('    这三类都该回 persona 收紧写法，而不是改代码（除非是 _clean_ai_reply 没拦住）。')
    lines.append('  · 这一版把召回块真的拼进 system 了 —— 若某题 FAIL 但"召回"字段显示命中，')
    lines.append('    说明**召回取到了、模型没接住**，问题在 persona 的"怎么说"而不是索引内容。')
    lines.append('    若"召回"字段是 []，说明是**取错了块**，该回去查触发词或图边。')

    os.makedirs(OUTDIR, exist_ok=True)
    suffix = '_norecall' if args.no_recall else ''
    out = os.path.join(OUTDIR, 'worldview_probe_%s%s.txt' % (DATE, suffix))
    io.open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print('WROTE %s' % out)


if __name__ == '__main__':
    main()
