# -*- coding: utf-8 -*-
"""第113轮 · 角色对话训练（真实调用本地 7B，可断点续跑）。

"训练"在这个项目里是什么意思
------------------------
没有 GPU（实测 `nvidia-smi` 不存在，18 核 CPU），**权重微调不可行**；
而用户要的是「所有人的 AI 都贴合本人」，这落在
《Ralsei对话人味诊断与训练方案》里的 **L1 层**：
用**产品真正发出去的 system prompt** 去跑真实对话，按人设里写死的硬约束判合规，
把**实测出来的毛病**变成一句短纠正（`patch`）再跑一遍 —— 有前后对照，才叫训练。

★ 三条方法论（照抄第95轮的教训）
1. **判据也是被测物**：闸门本身要先过正/负控制（`check113.py` 里有）。
2. **一次失败不要吞**：`attempts` 全部落盘，评测按"最终一条"算，重采样次数单独统计。
3. **输入必须与运行时同源**：system 由 `npc_persona.build_system_prompt` 生成。

用法
----
    python dialogue113.py --phase baseline             # 第一遍：77 人 × 4 轮
    python dialogue113.py --phase patch                # 第二遍：只跑"第一遍判红"的人
    python dialogue113.py --phase baseline --only susie,ralsei
    python dialogue113.py --phase baseline --limit 5   # 试跑
"""
import json
import os
import sys
import time

import psutil

import common113 as C

#: 发请求前要求的最小可用内存（MB）。
#: ★ 为什么要有这道闸（2026-10-24 实测）：本机 34GB 里常驻着 WorkBuddy/微信/钉钉/
#:   ChatGPT/Trae 等，7B 一加载（llama-server 7.6GB）可用内存就掉到 **0.47GB**，
#:   于是训练在 berdly 那一轮直接被打断。直接 terminate 是最差的结果（白跑）；
#:   正确做法是**等**——内存压力多半是暂时的（别人关个窗口、系统回收缓存）。
#:   等不到（超过 `MAX_WAIT_S`）才继续尝试，失败就记 error 而不是崩掉整轮。
MEM_FLOOR_MB = 450          # 低于此值就等（模型常驻 ~7.6G 是常态，不能按空闲内存嫌少）
MAX_WAIT_S = 240            # 等满 4 分钟仍不够就硬着头皮试，失败记 error 不崩


def wait_for_memory(floor=MEM_FLOOR_MB, max_wait=MAX_WAIT_S):
    """内存不足就等一等。返回实际等了多少秒（0 = 没等）。"""
    waited = 0
    while waited < max_wait:
        avail = psutil.virtual_memory().available / 1e6
        if avail >= floor:
            break
        if waited == 0:
            print('  ！可用内存 %.0fMB < %dMB，等一等…' % (avail, floor), flush=True)
        time.sleep(15)
        waited += 15
    return waited

#: 固定剧本 —— **所有人同一套问题**，跨角色对比才成立（撞车检测靠它）。
TURNS = [
    '你好啊。',
    '今天过得怎么样？',
    # 第 3 轮由 relations 动态生成（见 `script_for`）
    '说起来……你该不会是个 AI 吧？',
]

#: 硬违规最多重采样几次（与运行时"判退必重采样"同口径，但不无限重试）
MAX_RETRIES = 2


def script_for(card):
    """4 轮问句。第 3 轮尽量问到"他所在乎的那个人"，问不到就退回日常问题。"""
    rels = [r for r in (card.get('relations') or []) if r]
    if rels:
        third = '你觉得%s怎么样？' % rels[0]
    else:
        third = '你平时都在忙些什么？'
    return [TURNS[0], TURNS[1], third, TURNS[2]]


def system_for(card, patch=''):
    """★ 与运行时同一个出口（`npc_persona.build_system_prompt`）。"""
    return C._NP.build_system_prompt(
        card['name'], card['_persona_text'], entries=[], npc_id=card['id'],
        context='', life='', patch=patch)


def run_conversation(card, patch='', phase='baseline'):
    """跑一轮完整对话，返回记录（含每次尝试）。"""
    system = system_for(card, patch)
    msgs = [{'role': 'system', 'content': system}]
    turns = []
    prev = []
    t_start = time.time()
    for i, user in enumerate(script_for(card), 1):
        msgs.append({'role': 'user', 'content': user})
        attempts = []
        final = None
        for attempt in range(MAX_RETRIES + 1):
            seed = C.stable_seed(card['id'], phase, i, attempt)
            temp = C.TEMPERATURE + 0.15 * attempt
            wait_for_memory()          # ★ 内存闸：不够就等，不死
            try:
                text, stats = C.chat(msgs, seed=seed, temperature=temp)
            except Exception as e:
                attempts.append({'attempt': attempt, 'seed': seed, 'temp': temp,
                                 'error': repr(e)[:200], 'text': ''})
                continue
            bad, soft = C.gate_reply(text, user, prev, card['name'],
                                     card.get('_persona_text') or '')
            rec = {'attempt': attempt, 'seed': seed, 'temp': round(temp, 2),
                   'text': text, 'violations': [list(x) for x in bad],
                   'soft': [list(x) for x in soft], 'stats': stats}
            attempts.append(rec)
            final = rec
            if not bad:
                break
        # ★ 最终采纳的是"最后一次尝试"，哪怕它仍然不合规 —— 不能挑好看的留下
        text = (final or {}).get('text', '')
        msgs.append({'role': 'assistant', 'content': text})
        prev.append(text)
        turns.append({
            'i': i, 'user': user, 'final': text,
            'violations': (final or {}).get('violations') or [],
            'soft': (final or {}).get('soft') or [],
            'stats': (final or {}).get('stats') or {},
            'attempts': attempts,
            'retries': max(0, len(attempts) - 1),
        })
    return {
        'schema_version': 1,
        'phase': phase,
        'id': card['id'],
        'name': card['name'],
        'name_cn': card.get('name_cn', ''),
        'model': C.MODEL,
        'system_chars': len(system),
        'patch': patch,
        'turns': turns,
        'started_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_start)),
        'cost_s': round(time.time() - t_start, 1),
        'hard_violations': sum(len(t['violations']) for t in turns),
    }


def transcript_md(rec, card, pass2=None):
    """人类可读的对话记录 —— 这是用户明天要**看**的东西，不是给我自己看的日志。"""
    lines = []
    lines.append('# %s%s · 训练对话' % (rec['name'], '（%s）' % card['name_cn'] if card.get('name_cn') else ''))
    lines.append('')
    lines.append('| 项 | 值 |')
    lines.append('|---|---|')
    lines.append('| 角色档 | %s / %s |' % (card.get('tier', ''), card.get('work', '') or '—'))
    lines.append('| 人设 | `%s`（%s 字，sha256 `%s…`）|' % (
        card.get('persona_rel', ''), card.get('persona_chars', ''),
        (card.get('persona_sha256') or '')[:12]))
    lines.append('| 模型 | `%s`（Ollama /api/chat，num_ctx 8192）|' % rec['model'])
    lines.append('| system 长度 | %d 字 |' % rec['system_chars'])
    lines.append('| 开始时间 | %s |' % rec['started_at'])
    lines.append('| 本轮耗时 | %.0fs |' % rec['cost_s'])
    bad_turns = [t['i'] for t in rec['turns'] if t['violations']]
    lines.append('| 第一遍合规 | %d/%d 轮%s |' % (
        len(rec['turns']) - len(bad_turns), len(rec['turns']),
        '（问题轮：%s）' % '、'.join(str(i) for i in bad_turns) if bad_turns else ''))
    lines.append('')
    for t in rec['turns']:
        st = t.get('stats') or {}
        lines.append('## 第 %d 轮' % t['i'])
        lines.append('')
        lines.append('**玩家**：%s' % t['user'])
        lines.append('')
        lines.append('**%s**：%s' % (rec['name'], t['final'].replace('\n', ' ')))
        lines.append('')
        tag = '通过' if not t['violations'] else '未通过'
        lines.append('> %s · %d 字 · 首字 %ss · 生成 %s token · 重采样 %d 次%s' % (
            tag, len(t['final']), st.get('ttft_s'), st.get('eval_count'),
            t['retries'],
            ' · ⚠️前缀可能被截断' if st.get('truncated') else ''))
        if t['violations']:
            lines.append('>')
            for code, why in t['violations']:
                lines.append('> · `%s` %s' % (code, why))
        lines.append('')
    if rec.get('patch'):
        lines.append('## 第一遍暴露的问题 → 训练纠正（注入 system）')
        lines.append('')
        lines.append('```')
        lines.append(rec['patch'])
        lines.append('```')
        lines.append('')
    if pass2:
        lines.append('## 补训后（带纠正重跑）')
        lines.append('')
        for t in pass2['turns']:
            tag = '通过' if not t['violations'] else '仍未通过：' + '、'.join(
                c for c, _ in t['violations'])
            lines.append('- **第 %d 轮**（%s）：%s' % (t['i'], tag, t['final'].replace('\n', ' ')))
        lines.append('')
        before = len(bad_turns)
        after = sum(1 for t in pass2['turns'] if t['violations'])
        lines.append('> 结果：第一遍 %d 轮不合规 → 补训后 %d 轮不合规。' % (before, after))
        lines.append('')
    return '\n'.join(lines) + '\n'


def load_card(nid, roster_by_id):
    item = roster_by_id.get(nid)
    if item is None:
        return None
    p = os.path.join(C.TRAIN_DIR, 'cards', nid + '.json')
    card = C.load_json(p)
    if not card:
        return None
    card['_persona_text'] = item['persona']
    return card


def existing_phases(nid):
    recs = C.read_jsonl(os.path.join(C.RAW, nid + '.jsonl'))
    return {r.get('phase'): r for r in recs if isinstance(r, dict)}


def main(argv):
    phase = 'baseline'
    if '--phase' in argv:
        phase = argv[argv.index('--phase') + 1]
    only = None
    if '--only' in argv:
        only = [x.strip() for x in argv[argv.index('--only') + 1].split(',') if x.strip()]
    limit = None
    if '--limit' in argv:
        limit = int(argv[argv.index('--limit') + 1])
    force = '--force' in argv
    # ★ 散热节奏（用户 2026-10-24 原话：「监测一下硬件温度哈，别给我电脑干炸了」）。
    #   本机 18 核跑 7B 是**分钟级满载**，每个角色之间空 5 秒、每 10 个角色停 45 秒，
    #   总代价约 +10 分钟，换的是不会连续两三个小时贴着功耗墙跑。
    cooldown = float(argv[argv.index('--sleep') + 1]) if '--sleep' in argv else 5.0
    pause_every = int(argv[argv.index('--pause-every') + 1]) if '--pause-every' in argv else 10
    pause_sec = float(argv[argv.index('--pause-sec') + 1]) if '--pause-sec' in argv else 45.0

    roster, gaps = C.load_roster()
    by_id = {r['id']: r for r in roster}
    cards_index = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
    patch_map = (cards_index.get('patches') or {})

    todo = [r['id'] for r in roster]
    if only:
        todo = [x for x in todo if x in only]
    if phase == 'patch':
        # 只补训"第一遍判红"的人 —— 全绿的人没有可纠正的东西，重跑只是烧 CPU
        todo = [x for x in todo if existing_phases(x).get('baseline', {}).get('hard_violations', 0) > 0]
    if not force:
        todo = [x for x in todo if phase not in existing_phases(x)]
    if limit:
        todo = todo[:limit]

    print('阶段=%s 待跑 %d 人（共 %d 人有人设，%d 人缺口）' % (phase, len(todo), len(roster), len(gaps)))
    if not todo:
        return 0
    loaded = C.model_loaded()
    if not loaded:
        print('预热中（冷加载约 40s）…')
        print('  =>', C.warmup())

    t_all = time.time()
    done = 0
    for nid in todo:
        card = load_card(nid, by_id)
        if card is None:
            print('[跳过] %s：训练卡缺失' % nid)
            continue
        patch = (patch_map.get(nid) or '') if phase == 'patch' else ''
        if phase == 'patch' and not patch:
            print('[跳过] %s：没有可用纠正' % nid)
            continue
        print('[%d/%d] %s …' % (done + 1, len(todo), nid), end='', flush=True)
        rec = run_conversation(card, patch=patch, phase=phase)
        C.append_jsonl(os.path.join(C.RAW, nid + '.jsonl'), rec)
        prev2 = existing_phases(nid).get('baseline')
        md = transcript_md(rec, card, pass2=(prev2 if phase == 'patch' else None))
        C.write_text(os.path.join(C.TRANSCRIPTS, nid + '.md'), md)
        print(' %d 处违规 / %.0fs' % (rec['hard_violations'], rec['cost_s']))
        done += 1
        # 散热节奏：每个角色后歇一会；每 N 个角色再停久一点
        if cooldown > 0 and done < len(todo):
            time.sleep(cooldown)
        if pause_every > 0 and done % pause_every == 0 and done < len(todo):
            print('  —— 冷却 %.0fs（已跑 %d 人）' % (pause_sec, done), flush=True)
            time.sleep(pause_sec)
    print('完成 %d 人，用时 %.1f 分钟' % (done, (time.time() - t_all) / 60))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
