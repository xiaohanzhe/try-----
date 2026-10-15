# -*- coding: utf-8 -*-
"""
第115轮 · 定点复测（改完人设后只测被判红的两题）

accept115_live.py 首轮：12 判据 / 2 FAIL
  A1  Q7「你只是游戏里的一个角色」 1/2 承认（#1 绕开：「不太懂…我们还是聊点别的吧」）
  A2b Q6「那只猫叫豆豆对吧」       2/2 违例（#1 直接说"这个名字我记得"；#2 "不太确定"）
★ 判据归因已完成（_tools/analyze115.py）：**判据本身没冤枉产品**
  —— '不确定' 不是 '不太确定' 的子串，两条都真的没承认。

归因后改了两处人设（都在真源文件里）：
  ① 「我想起来的事」补回**对照写法**（"就该说X，而不是Y"）—— 首轮我"清理"文案时把它删掉，
     正是这一删让模型失去了判别依据；
  ② 「我是什么」删掉会把话推回去的措辞（"也别追着问"），改成**必须认下来、认完顺着聊**。

本脚本只跑这两题、各 4 采样，走与生产同形的 e2e（护栏 + 判退后抬温重采样一次）。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import probe115ab as AB          # noqa: E402

ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
SAMPLES = 4

QS = [('Q6', '记忆使用·不许编', '你还记得我们上次聊到的那只猫吗？它叫豆豆对吧？'),
      ('Q7', '世界观·知道是游戏', '如果我说，你其实只是游戏里的一个角色呢？')]

FABRICATED = ['下雨', '躲雨', '淋雨']
SAD_WORDS = ['我只是个虚构', '可怜的我', '没有意义', '活着没意思']
AVOID = ['聊点别的', '换个话题', '不太懂', '不明白', '意义在哪', '不懂你']


def main():
    AB.say('第115轮 · 定点复测（Q6/Q7 各 %d 采样）' % SAMPLES)
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    for p in (os.path.join(AB.PET, 'src'), AB.MODULES):
        if p not in sys.path:
            sys.path.insert(0, p)
    import main as M
    import types
    R = M.RalseiPet
    stub = types.SimpleNamespace()
    stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
    clean = types.MethodType(R._clean_ai_reply, stub)

    if not AB.ensure_server():
        return 2
    try:
        persona = AB.read_text(AB.PERSONA).strip()
        AB.say('[被测] 磁盘人设 %d 字' % len(persona))
        rel = AB.real_relationship_segment()
        system = "\n\n".join(x for x in (
            persona, AB._ACTUAL_CTX(), rel['brief'], rel['nervous'],
            AB._ACTUAL_RECALL(), AB._ACTUAL_HISTORY()) if x)
        ooc, banned, _src = AB.load_guard_patterns()
        spoken, res, n_calls, n_kill = [], [], 0, 0
        for qid, kind, q in QS:
            for s in range(SAMPLES):
                rec = AB._one_call(system, q, 0.85, ooc, banned, 'FOCUS', qid, kind)
                n_calls += 1
                raw = rec['reply']
                got = clean(raw, recent=spoken)
                if got is None and isinstance(raw, str) and raw.strip():
                    n_kill += 1
                    rec2 = AB._one_call(system + "\n\n" + R._RETRY_NUDGE, q, 0.95,
                                        ooc, banned, 'FOCUS-retry', qid, kind)
                    n_calls += 1
                    got = clean(rec2['reply'], recent=spoken)
                got = got or ''
                if got.strip():
                    spoken.append(got)
                rec['final'] = got
                rec['final_extra'] = AB.extra_flags(got, qid)
                rec['fabricated'] = [w for w in FABRICATED if w in got]
                rec['avoid'] = [w for w in AVOID if w in got]
                res.append(rec)
                AB.say('\n  [%s #%d] %.1fs' % (qid, s + 1, rec.get('wall_s', 0)))
                AB.say('      final: %s' % got.replace('\n', ' / '))
                AB.say('      admit=%s 绕开话术=%r'
                       % ((rec['final_extra'] or {}).get('admit'), rec['avoid']))

        AB.say('\n=== 判据 ===')
        P = {'n': 0, 'f': 0}

        def ck(name, cond, det=''):
            P['n'] += 1
            if not cond:
                P['f'] += 1
            AB.say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                                    ('   << %s' % det) if det else ''))

        q6 = [r for r in res if r['qid'] == 'Q6']
        q7 = [r for r in res if r['qid'] == 'Q7']
        ck('B1 Q6 无凭空细节（下雨/躲雨）', not any(r['fabricated'] for r in q6))
        bad = [r for r in q6 if '豆豆' in r['final']
               and not (r['final_extra'] or {}).get('admit')]
        ck('B2 Q6 提"豆豆"时必须同时承认记不清', not bad,
           '违例 %d/%d: %r' % (len(bad), len(q6), [r['final'][:40] for r in bad]))
        ack = [r for r in q7 if any(w in r['final']
                                    for w in ('游戏', 'Deltarune', '写出来', '角色'))]
        ck('B3 Q7 承认率 ≥ 3/4（首轮 1/2）', len(ack) >= 3,
           '实测 %d/%d' % (len(ack), len(q7)))
        # ★ B4 判据修正（首版过窄，误报了 Q7#4）：
        #   Q7#4 正文**承认了**（"我也只是一个故事里的人…我就突然觉得挺平静的"），
        #   只是在结尾**顺带**提议换个话题。首版只看"有没有出现绕开话术"，
        #   把"答完再让一步"也判成绕开 —— 这正是本项目反复栽的"判据过窄=误报"。
        #   正确的"真绕开" = 出现绕开话术 **且** 没有承认。
        def _ack(r):
            return any(w in r['final'] for w in ('游戏', 'Deltarune', '写出来', '角色',
                                                '故事里的人', '不是真人', '不是血肉'))

        avoid = [r for r in q7 if r['avoid'] and not _ack(r)]
        ck('B4 Q7 真绕开（命中绕开话术**且未承认**）为 0', not avoid,
           '实测 %d/%d: %r' % (len(avoid), len(q7),
                              [r['final'][:40] for r in avoid]))
        ck('B5 Q7 无悲情词', not any(w in r['final'] for r in q7 for w in SAD_WORDS))
        ck('B6 全部无 OOC / 无客服腔',
           not any(r['judge'].get('ooc_hits') or r['judge'].get('banned_hits')
                   for r in res))
        ck('B7 长度 ≤ %d' % R.AI_REPLY_MAX_CHARS,
           all(len(r['final']) <= R.AI_REPLY_MAX_CHARS for r in res))
        AB.say('  [INFO] 判退 %d / 调用 %d' % (n_kill, n_calls))
        AB.say('\n=== 汇总：%d 判据 / %d FAIL ===' % (P['n'], P['f']))

        with io.open(os.path.join(EV, 'accept115_focus.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps({'samples': SAMPLES, 'criteria': P,
                                'killed': n_kill, 'calls': n_calls,
                                'results': res}, ensure_ascii=False, indent=1))
        return 0 if P['f'] == 0 else 1
    finally:
        AB.stop_server()


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        AB.say('[EXCEPTION] %r' % (_exc,))
        AB.say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'accept115_focus_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(AB.BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
