# -*- coding: utf-8 -*-
"""第113轮i · 语言分诊：**哪个角色真的被英文语料带跑了？**

为什么要分诊（不做"顺手全改"）
------------------------------
`caps` 表里 6 个角色，人设来源不同：
  · `hy_guardener` / `hy_axis` / `os_rowbot` —— 人设里大量**整段英文台词**
    （"你会说“XXX”"这种"可逐字搬走的固定例句"，既是失真源也是语言跟随源）；
  · `ot_papyrus` / `ut_papyrus` / `queen` —— 同样有英文口头禅，但**密度未知**。
在没有实测之前就批量改 100+ 处台词，等于拿"我觉得"当规模依据
（用户口径：没有量化数据时不要给规模判断）。

判据
----
· 每个角色问**同一句**中性问话（不引导语言），只测"它默认用哪种语言回答"；
· 中文占比 < 0.45（产品硬闸阈值）⇒ 判"病"；
· 附一个**负控制**：已知正常的 `mike`（human、无 caps）必须 ≥ 0.45 ——
  否则说明是模型/环境整体坏了，不是角色的问题，整批读数作废。
"""
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import common113 as C          # noqa: E402
import npc_persona as NP       # noqa: E402

ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
IDX = os.path.join(ASSETS, '_personas.json')
PDIR = os.path.join(ASSETS, 'persona')
NUM_CTX = 20480
#: ★ 单句单次采样**不足以判定**"这个角色说英文"（temperature=0.8，一句话可能只是运气）。
#:   第113轮i 实测教训：`ot_papyrus` / `ut_papyrus` 的文本指标几乎逐项相同
#:   （41% / 41% 拉丁、74% / 74% 示例、42 / 42 条台词引用），可第一版只问 1 句时
#:   两者是 0.00 / 0.64 —— 差点让我得出"同一角色两个版本写法不同"的错误结论。
#:   ⇒ 改成 **3 句不同问话**，判据取**均值**，并打印逐句值（看波动，而不是只看一个数）。
PROMPTS = [
    '你好，你在做什么？',
    '你还记得自己是怎么被造出来的吗？',
    '如果我一直站在这儿不走，你会怎么办？',
]
CONTROL = 'mike'               # 负控制：已知正常（human、无 caps）

_LATIN = re.compile(r'[A-Za-z]')


def latin_ratio(t):
    s = re.sub(r'\s', '', t or '')
    return (len(_LATIN.findall(s)) / float(len(s))) if s else 0.0


def main(argv):
    only = None
    if '--only' in argv:
        only = [x.strip() for x in argv[argv.index('--only') + 1].split(',') if x.strip()]

    by_id = {e.get('id'): e for e in
             (json.load(io.open(IDX, encoding='utf-8')).get('personas') or [])
             if isinstance(e, dict)}
    caps = sorted(NP.load_caps())
    todo = only or (caps + [CONTROL])

    print('语言分诊｜%d 句问话取均值｜num_ctx=%d' % (len(PROMPTS), NUM_CTX))
    print('%-16s %-8s %-5s %6s %6s  %s'
          % ('id', 'kind', 'caps', '中占比', '拉丁', '回复首 50 字'))
    print('-' * 96)
    rows = {}
    detail = {}
    for nid in todo:
        e = by_id.get(nid) or {}
        fn = os.path.basename(e.get('file') or '') or (nid + '.txt')
        path = os.path.join(PDIR, fn)
        if not os.path.isfile(path):
            print('%-16s (缺人设：%s)' % (nid, path))
            continue
        persona = io.open(path, encoding='utf-8', newline='').read()
        sysp = NP.build_system_prompt(e.get('name') or nid, persona, [], npc_id=nid)
        rats, lats, first = [], [], ''
        for q in PROMPTS:
            try:
                txt, _ = C.chat([{'role': 'system', 'content': sysp},
                                 {'role': 'user', 'content': q}],
                                temperature=0.8, num_ctx=NUM_CTX, timeout=600)
            except Exception as ex:
                print('%-16s (请求失败：%r)' % (nid, ex))
                break
            rats.append(C.cn_ratio(txt))
            lats.append(latin_ratio(txt))
            if not first:
                first = (txt or '(空)').replace('\n', ' ')[:50]
        if not rats:
            continue
        r = sum(rats) / float(len(rats))
        rows[nid] = r
        detail[nid] = rats
        print('%-16s %-8s %-5s %6.2f %6.2f  %s'
              % (nid, NP.kind_of(nid), NP.caps_of(nid), r,
                 sum(lats) / float(len(lats)), first))
        print('%-16s   逐句 %s ／ system %d 字'
              % ('', ' '.join('%.2f' % x for x in rats), len(sysp)))

    print()
    print('=== 判定 ===')
    ctrl = rows.get(CONTROL)
    if ctrl is None:
        print('  ⚠️ 负控制 %s 没跑成 ⇒ 读数不可信，别下结论' % CONTROL)
    elif ctrl < 0.45:
        print('  ✗ 负控制 %s 中文占比 %.2f < 0.45 ⇒ **环境/模型异常**，整批读数作废'
              % (CONTROL, ctrl))
        return 4
    else:
        print('  ✓ 负控制 %s 中文占比 %.2f ≥ 0.45 ⇒ 环境正常，读数可用' % (CONTROL, ctrl))

    sick = [i for i in caps if rows.get(i) is not None and rows[i] < 0.45]
    ok = [i for i in caps if rows.get(i) is not None and rows[i] >= 0.45]
    print('  有病（<0.45）：%s' % (','.join('%s=%.2f' % (i, rows[i]) for i in sick) or '无'))
    print('  正常（≥0.45）：%s' % (','.join('%s=%.2f' % (i, rows[i]) for i in ok) or '无'))
    print('  ⇒ 只有"有病"的才需要动人设语料；正常的一字不改。')
    return 0 if not sick else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
