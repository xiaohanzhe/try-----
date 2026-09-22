# -*- coding: utf-8 -*-
"""7B 首字延迟（TTF）实测 —— 用产品真实 persona，prompt 完整不裁剪。

第 30 轮：用户口径
  - 要 7B 是为了「贴合人物 + 不出 bug」=> 质量优先
  - 「prompt 尽量完整」=> 绝不裁剪 system
  - 「1~3s」= 首字延迟（TTF），不是整句

对照口径与 ttf_measure.txt（4B）严格一致，便于横向比较。
"""
import io
import json
import os
import sys
import time
import urllib.request

HOST = 'http://127.0.0.1:11434'
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
WORLDVIEW = os.path.join(PET, 'assets', 'ralsei_worldview.md')
OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence', 'ttf_measure_7b.txt')


def read(p):
    if not os.path.exists(p):
        return ''
    with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.read().strip()


def measure(model, system_text, user_text, chat_history=None, tag='', num_predict=40):
    msgs = []
    if system_text:
        msgs.append({'role': 'system', 'content': system_text})
    for h in (chat_history or []):
        msgs.append(h)
    msgs.append({'role': 'user', 'content': user_text})
    body = json.dumps({
        'model': model,
        'messages': msgs,
        'stream': False,
        'options': {'num_predict': num_predict, 'temperature': 0.85},
    }).encode('utf-8')
    req = urllib.request.Request(HOST + '/api/chat', data=body,
                                headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode('utf-8'))
    wall = time.time() - t0
    pt = d.get('prompt_eval_count') or 0
    pe = (d.get('prompt_eval_duration') or 0) / 1e9
    ot = d.get('eval_count') or 0
    ev = (d.get('eval_duration') or 0) / 1e9
    return {
        'tag': tag,
        'prompt_tokens': pt,
        'prompt_eval_s': round(pe, 3),
        'out_tokens': ot,
        'eval_s': round(ev, 3),
        'tok_per_s': round(ot / ev, 2) if ev > 0 else None,
        'wall_s': round(wall, 3),
        'reply': (d.get('message') or {}).get('content', ''),
    }


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else 'qwen2.5:7b-instruct-q4_K_M'
    persona = read(PERSONA)
    worldview = read(WORLDVIEW)
    full_system = persona + '\n\n' + worldview if worldview else persona

    lines = []
    lines.append('模型 = %s' % model)
    lines.append('persona chars = %d' % len(persona))
    lines.append('worldview chars = %d' % len(worldview))
    lines.append('完整 system chars = %d（未裁剪）' % len(full_system))
    lines.append('')

    user_text = '今天有点累，事情一桩接一桩的，感觉喘不过气。'

    cases = [
        ('短system', '你是一个桌面上的角色，用简短的口语回答。', user_text, None),
        ('完整prompt(冷)', full_system, user_text, None),
        ('完整prompt+历史', full_system, user_text, [
            {'role': 'user', 'content': '你在做什么呢？'},
            {'role': 'assistant', 'content': '我在整理一些旧东西……有点走神了。'},
            {'role': 'user', 'content': '听起来你也有心事。'},
            {'role': 'assistant', 'content': '嗯，算是有吧。不过说出来好像也没那么重。'},
        ]),
    ]

    results = []
    for tag, sys_txt, usr, hist in cases:
        try:
            res = measure(model, sys_txt, usr, hist, tag)
            results.append(res)
            lines.append('=== 场景：%s ===' % tag)
            lines.append(json.dumps(res, ensure_ascii=False, indent=2))
            lines.append('')
        except Exception as e:
            lines.append('=== 场景：%s ===' % tag)
            lines.append('ERR %s: %s' % (type(e).__name__, e))
            lines.append('')

    lines.append('=' * 64)
    lines.append('=== TTF（首字延迟）汇总 —— 用户门槛 1~3s ===')
    lines.append('')
    lines.append('| 场景 | prompt tokens | **首字延迟** | 生成 tok/s | 整句 |')
    lines.append('|---|---|---|---|---|')
    for r in results:
        verdict = '[OK]' if r['prompt_eval_s'] <= 3.0 else '[OVER]'
        lines.append('| %s | %d | **%.2fs** %s | %s | %.2fs |' % (
            r['tag'], r['prompt_tokens'], r['prompt_eval_s'], verdict,
            r['tok_per_s'], r['eval_s']))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print('\nWROTE', OUT)


if __name__ == '__main__':
    main()
