# -*- coding: utf-8 -*-
"""对照实验 v2 —— 修正 v1 的设计缺陷。

v1 的问题（如实记录）：
  - 4 次调用每次都换了新的 system 内容 → 没有一次真正命中缓存 → 全部是冷启动
  - 跑了 13 分钟，得到的是"冷启动成本"而不是"位置效应"
  - 结论行 `倍数 = 1.0×` 是**无意义的**（两侧都在冷态，比的是同一件事）

v2 的设计（关键修正）：
  - **先用若干次请求把前缀喂热**（重复同一 system，让缓存稳定）；
  - 然后**只发布一个"变化量"**（改 system 末尾的一小段），量这一次的首字；
  - 再做**第二个变化**，再量。
  - 两次变化的**唯一区别 = 变化段的位置**（靠前 / 末尾），其余全同。

并且把"冷启动"单独留作对照组，明确它是成本上限。
"""
import io
import json
import os
import time
import urllib.request

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   'cache_position_ab2.txt')
HOST = 'http://127.0.0.1:11434'
MODEL = 'qwen2.5:7b-instruct-q4_K_M'

lines = []


def w(s=''):
    lines.append(s)
    print(s, flush=True)


def read(p):
    if not os.path.exists(p):
        return ''
    with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.read().strip()


persona = read(os.path.join(PET, 'assets', 'ralsei_persona.md'))
FIXED_MID = read(os.path.join(PET, 'assets', 'ralsei_worldview.md'))[:2200]
USER = '事情一桩接一桩的，感觉喘不过气。'


def call(sys_txt, num_predict=16):
    msgs = [{'role': 'system', 'content': sys_txt},
            {'role': 'user', 'content': USER}]
    body = json.dumps({'model': MODEL, 'messages': msgs, 'stream': False,
                       'options': {'num_predict': num_predict, 'temperature': 0.85}}).encode()
    req = urllib.request.Request(HOST + '/api/chat', data=body,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1200) as r:
        d = json.loads(r.read().decode())
    return {
        'prompt_tokens': d.get('prompt_eval_count'),
        'ttf_s': round((d.get('prompt_eval_duration') or 0) / 1e9, 3),
        'wall_s': round(time.time() - t0, 2),
    }


w('模型 = %s' % MODEL)
w('persona=%d chars  fixed_mid=%d chars' % (len(persona), len(FIXED_MID)))
w()
w('★ v2 修正：先把前缀喂热，再只改一个变化段，量"改一次"的代价')
w()

# ---- 场景 A：变化段在【靠前】 ----
SYS_A_BASE = persona + '\n\n' + '【此刻】现在是傍晚，窗外下着小雨。' + '\n\n' + FIXED_MID
SYS_A_CHANGED = persona + '\n\n' + '【此刻】现在是夜里，雨停了。' + '\n\n' + FIXED_MID

# ---- 场景 B：变化段在【末尾】 ----
SYS_B_BASE = persona + '\n\n' + FIXED_MID + '\n\n' + '【此刻】现在是傍晚，窗外下着小雨。'
SYS_B_CHANGED = persona + '\n\n' + FIXED_MID + '\n\n' + '【此刻】现在是夜里，雨停了。'

w('--- 场景 A：变化段【靠前】（persona 之后紧跟【此刻】）---')
r = call(SYS_A_BASE); w('  喂热 1：首字=%8.3fs' % r['ttf_s'])
r = call(SYS_A_BASE); w('  喂热 2：首字=%8.3fs' % r['ttf_s'])
r = call(SYS_A_BASE); w('  喂热 3：首字=%8.3fs  (prompt=%s)' % (r['ttf_s'], r['prompt_tokens']))
a_changed = call(SYS_A_CHANGED)
w('  ★ 改成 B（只在靠前那段变）：首字=%8.3fs' % a_changed['ttf_s'])
w()

w('--- 场景 B：变化段【末尾】---')
r = call(SYS_B_BASE); w('  喂热 1：首字=%8.3fs' % r['ttf_s'])
r = call(SYS_B_BASE); w('  喂热 2：首字=%8.3fs' % r['ttf_s'])
r = call(SYS_B_BASE); w('  喂热 3：首字=%8.3fs  (prompt=%s)' % (r['ttf_s'], r['prompt_tokens']))
b_changed = call(SYS_B_CHANGED)
w('  ★ 改成 B（只在末尾那段变）：首字=%8.3fs' % b_changed['ttf_s'])
w()

w('=' * 70)
w('=== 结论 ===')
w()
w('变化段靠前：改一次 → 首字 %.3fs' % a_changed['ttf_s'])
w('变化段末尾：改一次 → 首字 %.3fs' % b_changed['ttf_s'])
if b_changed['ttf_s'] > 0:
    w('倍数 = %.1f×（靠前 / 末尾）' % (a_changed['ttf_s'] / b_changed['ttf_s']))
w()
w('注：本机是纯 CPU（无 GPU 加速），冷启动成本量级见上方"喂热 1"的数值。')

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
w()
w('WROTE ' + OUT)
