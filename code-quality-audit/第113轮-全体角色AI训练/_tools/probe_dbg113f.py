# -*- coding: utf-8 -*-
"""定位挂死：小规模（1 角色 1 变体 2 轮）+ faulthandler 定时 dump 栈。"""
import faulthandler
import os
import sys
import time

HERE = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第113轮-全体角色AI训练\_tools'
sys.path.insert(0, HERE)

import common113 as C      # noqa: E402
import dialogue113 as D    # noqa: E402
import train30 as T        # noqa: E402

# ★ 每 45 秒把当前线程栈打到 stderr —— 挂死时能直接看到卡在哪一行
faulthandler.dump_traceback_later(45, repeat=True, exit=False)


def step(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


step('开始')
roster, _ = C.load_roster()
step('roster=%d' % len(roster))
by_id = {r['id']: r for r in roster}
card = D.load_card('susie', by_id)
step('card ok, persona=%d' % len(card['_persona_text']))
system = D.system_for(card, '')
step('system=%d' % len(system))

msgs = [{'role': 'system', 'content': system}]
turns = []
for i in (1, 2):
    user = T.fill_dynamic(card, turns, i, T.SCRIPT30[i - 1])
    step('第%d轮 fill_dynamic -> %r' % (i, user[:30]))
    msgs.append({'role': 'user', 'content': user})
    seed = C.stable_seed(card['id'], 'dbg113f', i, 0)
    step('第%d轮 seed=%s' % (i, seed))
    w = D.wait_for_memory()
    step('第%d轮 wait_for_memory 等了 %ss' % (i, w))
    t0 = time.time()
    step('第%d轮 即将调用 chat（num_ctx=20480）…' % i)
    try:
        text, st = C.chat(msgs, seed=seed, temperature=C.TEMPERATURE,
                          num_ctx=20480, num_predict=T.PREDICT30, timeout=120)
        step('第%d轮 chat 回来 %.0fs  %r' % (i, time.time() - t0, (text or '')[:60]))
        step('   stats=%s' % {k: st.get(k) for k in ('ttft_s', 'eval_count', 'truncated')})
    except Exception as e:
        step('第%d轮 chat 抛异常 %.0fs: %r' % (i, time.time() - t0, e))
        break
    msgs.append({'role': 'assistant', 'content': text})
    turns.append({'i': i, 'final': text})

faulthandler.cancel_dump_traceback_later()
step('结束，成功 %d 轮' % len(turns))
