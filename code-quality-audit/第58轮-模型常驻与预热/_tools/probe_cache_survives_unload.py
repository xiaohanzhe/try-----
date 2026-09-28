# -*- coding: utf-8 -*-
"""第58轮：**模型卸载会不会把 KV 前缀缓存一起抹掉** —— 裁定 ① 的全部依据。

第57轮只在报告里断言过"卸载 ⇒ 前缀缓存全丢"（依据是官方文档"默认 5 分钟卸载"），
**没有直接实测**。本轮补上，因为它决定 keep_alive 值不值得接线。

设计（四段，自带正/负控制）：
  S1  冷：卸载状态下，发真实 persona 前缀   ⇒ 期望 prompt_eval **大**（几十秒）
  S2  热：立刻同前缀再发一次                ⇒ 期望 prompt_eval **≈0**（证明"热"可读出来）
  S3  keep_alive=0 显式卸载
  S4  卸载后再发**同一个前缀**              ⇒ 若 prompt_eval 回到"大" ⇒ **缓存随卸载丢失**
  S5  再发一次做收尾（应当又是"热"）

判据只有两个，且必须成对：
  · S2.prompt_eval **≪** S1.prompt_eval   （否则"热"这个概念在本机不成立，S4 无从判）
  · S4.prompt_eval **≈** S1.prompt_eval   （这才是"卸载抹掉缓存"的直接证据）
  ⚠️ 只看 S4 一个数会误判：它也可能因为别的原因变大（例如 CPU 被抢占）。
     所以 S1/S2 是它的**基准与正控制**，S5 是收尾对照。
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = 'http://127.0.0.1:11434'
MODEL = 'ralsei:v4'
RT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
RDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(RDIR, '_evidence')
PERSONA = os.path.join(RT, 'ralsei_pet', 'assets', 'ralsei_persona.md')
HOT_MS_PER_TOKEN = 5.0          # 第57轮的冷/热分界（冷 27~29，热 0.04~1.2）

_LOG = []


def say(s=''):
    print(s)
    _LOG.append(s)


def native(system, keep_alive, num_predict=1, user='嗯。', timeout=420):
    body = {'model': MODEL, 'stream': False,
            'messages': ([{'role': 'system', 'content': system}] if system else [])
                        + [{'role': 'user', 'content': user}],
            'keep_alive': keep_alive, 'options': {'num_predict': num_predict,
                                                  'temperature': 0.0}}
    req = urllib.request.Request(BASE + '/api/chat',
                                 data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        return {'_err': 'HTTP %s %s' % (e.code, e.read()[:200])}
    except Exception as e:                                        # noqa: BLE001
        return {'_err': repr(e)}
    j['_wall_s'] = time.time() - t0
    j['_pe_s'] = (j.get('prompt_eval_duration') or 0) / 1e9
    j['_ld_s'] = (j.get('load_duration') or 0) / 1e9
    j['_ev_s'] = (j.get('eval_duration') or 0) / 1e9
    j['_pe_tok'] = j.get('prompt_eval_count') or 0
    j['_ms_per_tok'] = (j['_pe_s'] * 1000.0 / j['_pe_tok']) if j['_pe_tok'] else None
    return j


say('=' * 74)
say('第58轮：卸载是否抹掉 KV 前缀缓存   %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
say('=' * 74)

persona = io.open(PERSONA, encoding='utf-8').read()
say('人设 = %s（%d 字符 / %d 字节）' % (os.path.basename(PERSONA),
                                        len(persona), len(persona.encode('utf-8'))))

R = {}


def step(tag, system, keep_alive, note=''):
    j = native(system, keep_alive)
    if '_err' in j:
        say('  %-28s !! %s' % (tag, j['_err']))
        R[tag] = j
        return j
    say('  %-28s wall=%6.2fs  load=%5.2fs  **prompt_eval=%7.2fs / %5d tok = %s ms/tok**'
        '  decode=%5.2fs  %s'
        % (tag, j['_wall_s'], j['_ld_s'], j['_pe_s'], j['_pe_tok'],
           ('%.3f' % j['_ms_per_tok']) if j['_ms_per_tok'] else '?',
           j['_ev_s'], note))
    R[tag] = {k: j[k] for k in ('_wall_s', '_ld_s', '_pe_s', '_pe_tok',
                                '_ms_per_tok', '_ev_s')}
    return j


say()
say('先把模型卸干净（keep_alive=0），确保 S1 是**真冷**')
native(None, 0)
time.sleep(2)
say()
say('--- 主序列（每条都用 turn 的 persona 前缀）---')
s1 = step('S1 冷（首次喂入）', persona, '10m')
s2 = step('S2 热（立刻重发同前缀）', persona, '10m', '← 正控制：必须显著变快')
say('  S3 保持 keep_alive=10m，但显式卸载')
native(None, 0)
time.sleep(2)
s4 = step('S4 卸载后重发同前缀', persona, '10m', '← 判据：回到"冷"则缓存丢失')
s5 = step('S5 再发一次', persona, '10m')

say()
say('=' * 74)
say('判定')
say('=' * 74)
ok = True


def chk(name, cond, detail):
    global ok
    ok = ok and bool(cond)
    say('  [%s] %-46s %s' % ('PASS' if cond else 'FAIL', name, detail))


pe1 = (R.get('S1 冷（首次喂入）') or {}).get('_pe_s')
pe2 = (R.get('S2 热（立刻重发同前缀）') or {}).get('_pe_s')
pe4 = (R.get('S4 卸载后重发同前缀') or {}).get('_pe_s')
pe5 = (R.get('S5 再发一次') or {}).get('_pe_s')

chk('SC1 S1 是真冷（>10s）', pe1 and pe1 > 10.0, 'prompt_eval=%s s' % pe1)
chk('SC2 热档显著更快（热 < 冷/10）', pe1 and pe2 is not None and pe2 < pe1 / 10.0,
    '热 %.3fs vs 冷 %.2fs ⇒ 快 %.0f 倍' % (pe2 or -1, pe1 or -1,
                                          (pe1 / pe2) if (pe2 and pe1) else 0))
chk('SC3 ★卸载后回到冷（S4 ≈ S1，差 < 25%）',
    pe1 and pe4 is not None and abs(pe4 - pe1) / pe1 < 0.25,
    'S4 %.2fs vs S1 %.2fs（差 %s）'
    % (pe4 or -1, pe1 or -1,
       ('%.0f%%' % (abs(pe4 - pe1) / pe1 * 100)) if (pe1 and pe4) else '?'))
chk('SC4 收尾再发又变热（S5 ≪ S1）', pe1 and pe5 is not None and pe5 < pe1 / 5.0,
    'S5 %.3fs' % (pe5 if pe5 is not None else -1))

say()
if ok and pe4 and pe1 and pe2 is not None and pe2 < pe1 / 10.0:
    say('  ⇒ 结论：**模型一卸载，前缀缓存就整体不可用** —— 同一个前缀要重算一遍')
    say('     （%.2fs → %.3fs → 卸载 → %.2fs）。keep_alive 因此**直接命中**这个代价。'
        % (pe1, pe2, pe4))
else:
    say('  ⇒ 结论未确立 ⇒ 不许据此改产品代码（先查判据/环境）')

io.open(os.path.join(EVID, 'cache_survives_unload.json'), 'w',
        encoding='utf-8').write(json.dumps(
            {'persona_bytes': len(persona.encode('utf-8')),
             'hot_ms_per_token_line': HOT_MS_PER_TOKEN,
             'steps': R, 'all_pass': ok}, ensure_ascii=False, indent=2))
io.open(os.path.join(EVID, 'cache_survives_unload.log'), 'w',
        encoding='utf-8').write('\n'.join(_LOG) + '\n')
say()
say('[写入] %s' % os.path.join(EVID, 'cache_survives_unload.json'))
