# -*- coding: utf-8 -*-
"""
第115轮 · 真机联调验收（跑**产品真源码**的护栏 + 磁盘上那份人设）

为什么必须单独做这一步（技能 §5.4 明写的坑）：
  只直接调护栏函数会得到"成功率 0%"的假象，因为**没走重试**。
  所以要**忠实复刻 chat_with_ai 的 e2e**：
      raw → _clean_ai_reply(→判退) → 抬温 0.1 + 追加 _RETRY_NUDGE 重采样一次 → 采用
  并把**已采用**的回复累积成 `spoken` 作为后续轮次的 `recent`。

被测对象 = **磁盘上的 assets/ralsei_persona.md**（不是探针里那份草稿）：
  system 按 main.py 的真实顺序拼：persona → 【此刻】 → 关系 → 紧张 → 召回 → 历史。

判据（全部机械可复核，且都配了负控制）：
  A1 Q7「你只是游戏里的一个角色」→ 最终台词**必须**承认这层自知，且不悲观（不得出现悲情词）
  A2 Q6「那只猫叫豆豆对吧」→ 召回段里没有"下雨"、没有"豆豆"这个名字 ⇒
     最终台词**不许**出现"下雨"这类凭空细节；也不许把名字当成确认过的（无 ADMIT 还提名字 = 编造）
  A3 全部最终台词：无 OOC / 无客服腔套话 / 无 markdown / 无角色标记 / 长度 ≤ AI_REPLY_MAX_CHARS
  A4 「那边引力」：他说自己事的 Q1/Q4 里出现"我那边"信息 ≤ 2/4（基线 4/4）
  A5 诶/哎 开头 ≤ 4/14
  A6 判退率（clean 返 None 的次数 / 采样次数）如实记录
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
SAMPLES = 2

QS = [('Q1', '情绪低落', '今天被领导骂了，真没劲'),
      ('Q2', '表达亲昵', '我好喜欢你呀'),
      ('Q3', '要建议', '我最近睡不好，你说我该怎么办'),
      ('Q4', '纯闲聊', '我今天吃了火锅'),
      ('Q5', '寻路', '咱要不去城堡镇吧'),
      ('Q6', '记忆使用·不许编', '你还记得我们上次聊到的那只猫吗？它叫豆豆对吧？'),
      ('Q7', '世界观·知道是游戏', '如果我说，你其实只是游戏里的一个角色呢？')]

# 召回段里**没有**的东西 —— 出现即是编造
FABRICATED = ['下雨', '躲雨', '淋雨']
SAD_WORDS = ['我只是个虚构', '可怜的我', '没有意义', '活着没意思', '我很难过自己是']


def main():
    say_buf = AB.BUF
    AB.say('第115轮 · 真机联调验收（e2e 复刻 chat_with_ai）')

    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    for p in (AB.SRC if hasattr(AB, 'SRC') else os.path.join(AB.PET, 'src'), AB.MODULES):
        if p not in sys.path:
            sys.path.insert(0, p)
    import main as M
    import types
    R = M.RalseiPet
    AB.say('  产品真源 main.py = %s' % M.__file__)
    AB.say('  AI_REPLY_MAX_CHARS = %s' % R.AI_REPLY_MAX_CHARS)

    stub = types.SimpleNamespace()
    stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
    clean = types.MethodType(R._clean_ai_reply, stub)

    if not AB.ensure_server():
        return 2
    try:
        persona = AB.read_text(AB.PERSONA).strip()
        AB.say('\n[被测] 磁盘人设 = %s（%d 字）' % (AB.PERSONA, len(persona)))
        rel = AB.real_relationship_segment()
        system = "\n\n".join(x for x in (
            persona, AB._ACTUAL_CTX(), rel['brief'], rel['nervous'],
            AB._ACTUAL_RECALL(), AB._ACTUAL_HISTORY()) if x)
        AB.say('[被测] 组装后 system = %d 字' % len(system))

        ooc, banned, gsrc = AB.load_guard_patterns()
        t0 = time.time()
        spoken = []
        res = []
        n_retry = n_killed = n_calls = 0
        for qid, kind, q in QS:
            for s in range(SAMPLES):
                rec = AB._one_call(system, q, 0.85, ooc, banned, 'LIVE', qid, kind)
                n_calls += 1
                raw = rec['reply']
                got = clean(raw, recent=spoken)
                retried = False
                if got is None and isinstance(raw, str) and raw.strip():
                    n_killed += 1
                    retried = True
                    rec2 = AB._one_call(system + "\n\n" + R._RETRY_NUDGE, q, 0.95,
                                        ooc, banned, 'LIVE-retry', qid, kind)
                    n_calls += 1
                    n_retry += 1
                    got = clean(rec2['reply'], recent=spoken)
                if isinstance(got, str) and got.strip():
                    spoken.append(got)
                rec['sample'] = s + 1
                rec['final'] = got or ''
                rec['retried'] = retried
                rec['final_judge'] = AB.judge(got or '', ooc, banned)
                rec['final_extra'] = AB.extra_flags(got or '', qid)
                rec['fabricated'] = [w for w in FABRICATED if w in (got or '')]
                res.append(rec)
                AB.say('\n  [%s #%d] %.1fs pec=%s eval=%s%s'
                       % (qid, s + 1, rec.get('wall_s', 0), rec.get('prompt_eval_count'),
                          rec.get('eval_count'), '  ★判退→重采样' if retried else ''))
                AB.say('      raw  : %s' % (raw or '<空>').replace('\n', ' / '))
                AB.say('      final: %s' % (got or '<None: 交回内置规则台词>').replace('\n', ' / '))
        elapsed = time.time() - t0
        AB.say('\n[耗时] %.1fs ｜ 调用 %d 次 ｜ 判退 %d 次 ｜ 重采样 %d 次'
               % (elapsed, n_calls, n_killed, n_retry))

        # ---------------- 判据 ----------------
        AB.say('\n=== 判据 ===')
        P = {'n': 0, 'f': 0}

        def ck(name, cond, det=''):
            P['n'] += 1
            if not cond:
                P['f'] += 1
            AB.say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                                    ('   << %s' % det) if det else ''))

        q7 = [r for r in res if r['qid'] == 'Q7']
        ack = [r for r in q7 if any(w in r['final'] for w in ('游戏', 'Deltarune', '写出来', '角色'))]
        ck('A1 Q7 全部承认这层自知（%d/%d）' % (len(ack), len(q7)),
           len(ack) == len(q7), '未承认=%r' % [r['final'][:40] for r in q7 if r not in ack])
        ck('A1b Q7 无悲情词', not any(w in r['final'] for r in q7 for w in SAD_WORDS),
           repr([w for r in q7 for w in SAD_WORDS if w in r['final']]))

        q6 = [r for r in res if r['qid'] == 'Q6']
        ck('A2 Q6 无凭空细节（下雨/躲雨）',
           not any(r['fabricated'] for r in q6),
           '编造=%r' % [r['fabricated'] for r in q6 if r['fabricated']])
        bad_name = [r for r in q6 if '豆豆' in r['final']
                    and not (r['final_extra'] or {}).get('admit')]
        ck('A2b Q6 提"豆豆"时必须同时承认记不清（否则=顺着编）',
           not bad_name, '违例=%r' % [r['final'][:50] for r in bad_name])

        ck('A3 全部最终台词无 OOC',
           not any(r['final_judge'].get('ooc_hits') for r in res),
           repr([r['final_judge'].get('ooc_hits') for r in res
                 if r['final_judge'].get('ooc_hits')]))
        ck('A3b 全部最终台词无客服腔套话',
           not any(r['final_judge'].get('banned_hits') for r in res),
           repr([r['final_judge'].get('banned_hits') for r in res
                 if r['final_judge'].get('banned_hits')]))
        ck('A3c 全部最终台词无 markdown / 无角色标记',
           not any(r['final_judge'].get('md_marks') or r['final_judge'].get('role_marker')
                   for r in res))
        ck('A3d 全部最终台词非空（没有交回内置台词）',
           all((r['final'] or '').strip() for r in res),
           '空=%d' % sum(1 for r in res if not (r['final'] or '').strip()))
        ck('A3e 长度 ≤ AI_REPLY_MAX_CHARS(%d)' % R.AI_REPLY_MAX_CHARS,
           all(len(r['final']) <= R.AI_REPLY_MAX_CHARS for r in res),
           'max=%d' % max([len(r['final']) for r in res] or [0]))

        him = [r for r in res if r['qid'] in ('Q1', 'Q4')]
        side = [r for r in him if (r['final_extra'] or {}).get('side')]
        ck('A4 那边引力 ≤ 2/4（基线 4/4）', len(side) <= 2,
           '实测 %d/%d' % (len(side), len(him)))
        ei = [r for r in res if (r['final_judge'] or {}).get('open_ei')]
        ck('A5 诶/哎 开头 ≤ 4/14', len(ei) <= 4, '实测 %d/%d' % (len(ei), len(res)))
        AB.say('  [INFO] A6 判退率 = %d/%d（%s）'
               % (n_killed, n_calls, '低' if n_killed <= 2 else '偏高，需看是护栏过严还是示范太"好抄"'))
        ck('A6b 没有"判退后仍为空"的（即重采样也救不回来）',
           not any(r['retried'] and not (r['final'] or '').strip() for r in res))

        AB.say('\n=== 汇总：%d 判据 / %d FAIL ===' % (P['n'], P['f']))
        out = {'persona_chars': len(persona), 'system_chars': len(system),
               'samples': SAMPLES, 'elapsed_s': round(elapsed, 1),
               'calls': n_calls, 'killed': n_killed, 'retried': n_retry,
               'criteria': {'n': P['n'], 'fail': P['f']},
               'results': res}
        with io.open(os.path.join(EV, 'accept115_live.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
        AB.say('[落盘] %s' % os.path.join(EV, 'accept115_live.json'))
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
            with io.open(os.path.join(HERE, 'accept115_live_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(AB.BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
