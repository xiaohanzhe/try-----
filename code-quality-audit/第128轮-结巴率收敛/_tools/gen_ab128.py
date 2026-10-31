# -*- coding: utf-8 -*-
"""第128轮：把**原始采样结果**收进仓库（`_evidence/raw/`），并落一份元数据。

为什么不用"汇总数字"进仓库：`check128` 的 C/F 段是**从原文重算**的 ——
只信模型吐出来的那 150 条原始回复，不信我手写的一张统计表。
（本项目教训：「判据互证≠独立验证」，两张表同源错就一起绿。）

输入（临时区，用后即删）：
  `sample_c.json`      = 改前（persona 旧 + brief 旧），50 条
  `arm_pnew_bold.jsonl` = 只改人设（旧版，带引号），50 条
  `arm_pnew_bnew.jsonl` = 两处都改（旧版，带引号），50 条
  `arm_pnew_bnew2.jsonl` = 两处都改（**最终发布版人设**，去掉那对引号之后复跑），50 条
输出：
  `_evidence/raw/{base,pnew_bold,pnew_bnew,pnew_bnew2}.jsonl`
  `_evidence/ab128.json`  （模型/参数/输入清单/目标率/护栏函数名）

★ 为什么要第 4 臂：`pnew_bnew` 那一臂测的是**带引号**的人设，而为了修训练卡
  抽取器的垃圾口癖（`"嗯"`/`"诶"` 被当成 voice_markers），最终发布版把引号去掉了
  （9,992 → 9,983 B，语义不变）。**报告里的数字必须以最终版为准** ——
  不许拿没测过的文本报数，所以补了这一臂。
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
TMP = r"D:\_tmp128"


def _w_jsonl(path, rows):
    io.open(path, 'w', encoding='utf-8', newline='\n').write(
        u''.join(json.dumps(r, ensure_ascii=False) + u'\n' for r in rows))


def main():
    if not os.path.isdir(RAW):
        os.makedirs(RAW)
    # base：sample_c.json 是 {"rows":[{user,reply,...}]}
    j = json.loads(io.open(os.path.join(TMP, 'sample_c.json'), encoding='utf-8').read())
    base_rows = [{'user': r['user'], 'reply': r['reply']} for r in j['rows'] if r.get('reply')]
    _w_jsonl(os.path.join(RAW, 'base.jsonl'), base_rows)
    for arm in ('pnew_bold', 'pnew_bnew', 'pnew_bnew2'):
        rows = []
        for line in io.open(os.path.join(TMP, 'arm_%s.jsonl' % arm), encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            rows.append({'user': o['user'], 'reply': o['reply']})
        _w_jsonl(os.path.join(RAW, '%s.jsonl' % arm), rows)
    inputs = [r['user'] for r in base_rows]
    meta = {
        'round': 128,
        'model': 'ralsei:v4',
        'params': {'temperature': 0.85, 'max_tokens': 256, 'stream': False,
                   'endpoint': 'http://127.0.0.1:11434/v1/chat/completions'},
        'trust': 0.156301,
        'stage': 'distrust',
        'system': 'assets/ralsei_persona.md 全文 + relationship.nervous_brief(trust, "chat")',
        'arms': {
            'base': {'persona': 'old', 'brief': 'old'},
            'pnew_bold': {'persona': 'new', 'brief': 'old'},
            'pnew_bnew': {'persona': 'new(quoted)', 'brief': 'new'},
            'pnew_bnew2': {'persona': 'new(final, 无引号)', 'brief': 'new',
                           'note': u'最终发布版；报告数字以本臂为准'},
        },
        'metric': {
            'head_pure': u'句首纯迟疑词（嗯诶哦呃唔），修前的主指标',
            'head_excl': u'句首感叹词（哎呀/哎/啊/唉）—— 属正常语气，只登记不判红',
            'head_visible': u'经 event_speech.strip_head_hesitation 之后仍有句首迟疑的比例（用户可见）',
        },
        'guard': 'modules/event_speech.strip_head_hesitation',
        'target': 0.02,
        'inputs': inputs,
        'note': u'同一批 50 条输入、同一模型同一参数；只换 persona/brief 两个变量',
    }
    io.open(os.path.join(EV, 'ab128.json'), 'w', encoding='utf-8', newline='\n').write(
        json.dumps(meta, ensure_ascii=False, indent=1))
    print('WROTE', os.path.join(EV, 'ab128.json'))
    for fn in sorted(os.listdir(RAW)):
        print('  raw/%s  %d 行' % (fn, sum(1 for _ in io.open(os.path.join(RAW, fn), encoding='utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
