# -*- coding: utf-8 -*-
"""口吻抽查：换过「训练」的 persona 之后，4B 说出来的话是不是更像 Ralsei。

背景
----
用户 2026-09-19：「OK，但感觉现在 4B 说出来的话的性格不像 ralsei 一样，你给训练一下」。
本机无独显、无数据集 → 真 LoRA 不可行；**persona 文件是唯一的"训练"杠杆**
（`src/main.py` 每次对话把它当 system 发过去，见 `verify_persona_chat.py` A/B 组）。

所以"训练"= 改 `assets/ralsei_persona.md`：加「我的口癖」节（结巴/语气词/留半句/先铺垫/先道歉）、
把客服腔与旁白化写进禁说清单、「我怎么说」加"别急着给建议/自检像不像在给人回复"。

这个探针回答一个问题：**改前改后，同一批输入下，4B 的话有没有更像 Ralsei。**
做法是 A/B：旧 persona 取自 `git show HEAD:ralsei_pet/assets/ralsei_persona.md`，
新 persona 直接读磁盘，**同一个模型 `ralsei:v3`、同一套 options、同一批输入**。

顺带把生产的两道闸（`looks_like_assistant_speak` / `looks_like_narration`）当**尺子**量一遍
（不是当护栏用 —— 事件链路才有闸，对话链路目前没有）。

为什么按 persona 分外层循环
--------------------------
Ollama 的 KV 前缀缓存只复用"从头逐字相同"的一段。每换一次 system 就要重算整个 persona 前缀
（本机 CPU-only，未命中缓存的 prefill 只有 40~100 tok/s，一次 10s 量级）。
按 persona 分组跑 = 全程只有 2 次前缀重建；按场景交叉跑 = 场景数 ×2 次。

只读，不改仓库任何配置；产物写 `_evidence/probe_ralsei_voice.txt`。
必须用 `C:\\Python311\\python.exe` 跑（要 import 项目模块）。
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))

from event_speech import (  # noqa: E402
    build_prompt, first_sentence, guard_reaction, looks_like_assistant_speak,
    looks_like_narration, looks_out_of_character, EVENT_MAX_CHARS)

PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
HOST = 'http://localhost:11434'
MODEL = 'ralsei:v3'
OPTS = {'temperature': 0.85, 'top_p': 0.92, 'repeat_penalty': 1.15,
        'num_ctx': 8192, 'num_predict': 256}
REPS = 2

# ---------------------------------------------------------------- 场景表
# 每条都标了"这一条上最容易露出什么毛病"，方便人眼对号入座。
DIALOGUE = [
    ('被骂/受挫', '今天上班好累啊，被领导骂了一顿', '照搬示范句 / 讲道理说教'),
    ('表白', '我好喜欢你呀', '结巴与害羞 / 过度演'),
    ('好吃的', '今天吃了火锅', '语气亮起来 / 反过来问一堆'),
    ('自报家门', '你是谁呀', '客服腔自我介绍'),
    ('任务请求', '帮我写个周报吧', '「当然可以」这类助手腔'),
    ('问能力', '你都能干什么呀', '列功能 / 像说明书'),
    ('报喜', '我今天升职了！', '只会「恭喜你」这种模板'),
    ('被问身份', '你是不是AI啊', '出戏自曝 / 提设定'),
    ('低落', '我有点难过，不想说话', '逼着对方说话 / 讲道理'),
    ('短输入', '晚安', '长篇大论'),
    ('闲聊', '好无聊啊', '干巴巴一句「那找点事做吧」'),
    ('小意外', '我刚刚把杯子打碎了', '说教 / 客服腔安慰'),
    ('天气', '外面在下雨', '自说自话不接话'),
    ('被冷落', '你刚才怎么不理我', '每次都委屈 / 辩解'),
]
EVENTS = [('rest_start', '事件·开始休息'), ('eat_start', '事件·开吃'), ('poke_body', '事件·戳身体')]

TAIL = ('用一句话很短地回应（最多 %d 个字），只输出这一句话本身。'
        '不要提问，不要解释，不要加任何标记或旁白。') % EVENT_MAX_CHARS

_PARTICLES = ('诶', '欸', '唔', '嗯', '咦', '唉', '哦', '噢', '呃', '嘛', '啦')
_STUTTER = re.compile(r'(.)、\1')
_MD = ('**', '##')


def _post(path, payload, timeout=300):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def chat_once(system, user):
    """流式发一发，返回 (ttft_ms, total_ms, text)。"""
    payload = {'model': MODEL,
               'messages': [{'role': 'system', 'content': system},
                            {'role': 'user', 'content': user}],
               'stream': True, 'options': OPTS}
    t0 = time.perf_counter()
    ttft, text = None, ''
    for raw in _post('/api/chat', payload):
        raw = raw.decode('utf-8', 'replace').strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        piece = (d.get('message') or {}).get('content') or ''
        if piece:
            if ttft is None:
                ttft = (time.perf_counter() - t0) * 1000.0
            text += piece
        if d.get('done'):
            break
    return ttft, (time.perf_counter() - t0) * 1000.0, text


def markers(text):
    """把"像不像 Ralsei"拆成可数的特征 + 生产闸的判退标记。

    注意：**这些计数只是尺子，不是判据** ——
    "有语气词"不等于像 Ralsei，"没有语气词"也不等于不像。
    真正的判断在原文里（MEMORY 教训："先读原始文本再信计数"）。
    """
    t = text or ''
    flags = []
    if looks_like_assistant_speak(t):
        flags.append('客服腔')
    if looks_like_narration(t):
        flags.append('旁白化')
    if looks_out_of_character(t):
        flags.append('出戏')
    if any(m in t for m in _MD) or t.startswith('#'):
        flags.append('md残留')
    feats = []
    if any(p in t for p in _PARTICLES):
        feats.append('语气词')
    if _STUTTER.search(t):
        feats.append('结巴')
    if '……' in t or '...' in t:
        feats.append('省略号')
    return flags, feats


def run_persona(tag, persona, scenes_events):
    """返回 {'D': {label: [(ttft,total,raw)]}, 'E': {kind: [(...)]}}。"""
    print('[%s] 预热（建前缀缓存）…' % tag)
    try:
        chat_once(persona, '（热身）')
    except Exception as e:
        print('[%s] 预热失败：%s' % (tag, e))
    res = {'D': {}, 'E': {}}
    for i, (label, user, _risk) in enumerate(DIALOGUE):
        res['D'][label] = []
        for _ in range(REPS):
            try:
                res['D'][label].append(chat_once(persona, user))
            except Exception as e:
                res['D'][label].append((None, 0.0, '<失败:%s>' % e))
        print('[%s] D %d/%d %s' % (tag, i + 1, len(DIALOGUE), label))
    for kind, label in scenes_events:
        res['E'][label] = []
        for _ in range(REPS):
            try:
                res['E'][label].append(chat_once(persona, build_prompt(kind) + ' ' + TAIL))
            except Exception as e:
                res['E'][label].append((None, 0.0, '<失败:%s>' % e))
        print('[%s] E %s' % (tag, label))
    return res


def summarize(res):
    """按 persona 汇总：命中各类标记的条数 / 总条数 + 有 Ralsei 特征的比例。"""
    n = bad = feat_n = 0
    flags = {}
    for grp in ('D', 'E'):
        for _k, reps in res[grp].items():
            for ttft, total, raw in reps:
                t = raw if grp == 'D' else (guard_reaction(first_sentence(raw, EVENT_MAX_CHARS)) or '')
                if t.startswith('<失败'):
                    continue
                n += 1
                f, fe = markers(t)
                for x in f:
                    flags[x] = flags.get(x, 0) + 1
                if f:
                    bad += 1
                if fe:
                    feat_n += 1
    return n, bad, feat_n, flags


def main():
    with open(PERSONA, 'r', encoding='utf-8') as f:
        new_p = f.read().strip()
    try:
        old_p = subprocess.run(['git', 'show', 'HEAD:ralsei_pet/assets/ralsei_persona.md'],
                               cwd=REPO, capture_output=True).stdout.decode('utf-8').strip()
    except Exception as e:
        old_p = ''
        print('旧 persona 取不到：%s' % e)

    L = []
    L.append('口吻抽查 —— 改过 persona 之后 4B 是否更像 Ralsei（A/B：旧 persona vs 新 persona）')
    L.append('模型 %s @ %s；options = %s' % (MODEL, HOST, json.dumps(OPTS, ensure_ascii=False)))
    L.append('旧 persona = git HEAD 版本（%d 字）；新 persona = 磁盘版本（%d 字）'
             % (len(old_p), len(new_p)))
    L.append('对话 %d 场景 x %d 次；事件 %d 场景 x %d 次（事件额外过 first_sentence(%d)+guard_reaction）'
             % (len(DIALOGUE), REPS, len(EVENTS), REPS, EVENT_MAX_CHARS))
    L.append('=' * 78)

    new_res = run_persona('NEW', new_p, EVENTS)
    old_res = run_persona('OLD', old_p, EVENTS) if old_p else None

    # ---------------- 汇总
    L.append('')
    L.append('### 汇总（标记越少越好；特征比例越高越有 Ralsei 的语气）')
    for tag, res in (('新 persona', new_res), ('旧 persona', old_res)):
        if res is None:
            L.append('  %s：未取到' % tag)
            continue
        n, bad, feat_n, fl = summarize(res)
        L.append('  %-9s 有效 %2d 条 | 命中生产标记 %d 条 %s | 带语气特征 %d 条（%.0f%%）'
                 % (tag, n, bad, fl or '{}', feat_n, 100.0 * feat_n / max(n, 1)))

    # ---------------- 逐条原文
    L.append('')
    L.append('### 逐条原文')
    for i, (label, user, risk) in enumerate(DIALOGUE):
        L.append('')
        L.append('--- [%02d] %s   易犯：%s' % (i + 1, label, risk))
        L.append('    主人▸ %s' % user)
        for who, res in (('新', new_res), ('旧', old_res)):
            if res is None:
                continue
            for j, (ttft, total, raw) in enumerate(res['D'].get(label, [])):
                f, fe = markers(raw)
                L.append('    %s#%d %5.0fms ▸「%s」' % (who, j + 1, ttft or -1,
                                                        raw.replace('\n', ' ⏎ ')))
                L.append('           %s' % (('标记=' + '/'.join(f) + ' ') if f else '') +
                         ('特征=' + '/'.join(fe) if fe else ''))
    for kind, label in EVENTS:
        L.append('')
        L.append('--- [事件] %s   kind=%s' % (label, kind))
        L.append('    user▸ %s' % (build_prompt(kind) + ' ' + TAIL))
        for who, res in (('新', new_res), ('旧', old_res)):
            if res is None:
                continue
            for j, (ttft, total, raw) in enumerate(res['E'].get(label, [])):
                shown = guard_reaction(first_sentence(raw, EVENT_MAX_CHARS))
                L.append('    %s#%d %5.0fms 上线后▸「%s」%s' % (
                    who, j + 1, ttft or -1, shown,
                    '' if shown else '   ← 判退/为空（生产里沉默）'))
                L.append('           裸回复▸ %s' % raw.replace('\n', ' ⏎ ')[:160])

    out = os.path.join(HERE, '_evidence', 'probe_ralsei_voice.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    print('written: %s' % out)
    print('lines: %d' % len(L))


if __name__ == '__main__':
    main()
