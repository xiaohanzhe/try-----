# -*- coding: utf-8 -*-
"""第133轮 · 把第132轮那 3 条真泄漏样本喂进**事件台词链**，看闸装在哪一段才真的落进被测分支。

要回答三件事（都靠产品真源函数，不抄第二份）：
  1. 3 条真泄漏，经 `first_sentence(raw, 24)` 截断之后，`looks_like_meta_leak` 还认不认？
     —— 若截断后都认不出来，说明"事件链 24 字上限"本身就是一道事实上的护栏；
  2. 闸装在 `strip_action_parentheticals` **之前** vs **之后**，差别在哪条样本上体现？
     —— 形态③（括注自评）正好是括号，位置选错就等于没装；
  3. 42 条真机事件回复（本轮新采）过新闸会不会被误伤（假阳控制）。

只读 + 纯函数调用，不发请求。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(ROUND, '_evidence')
PET = os.path.join(ROOT, 'ralsei_pet')
LIVE131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                       '_evidence', 'live7_131.jsonl')
EV133 = os.path.join(EV, 'event133.jsonl')

for p in (os.path.join(PET, 'modules'),):
    if p not in sys.path:
        sys.path.insert(0, p)
import event_speech as ES                  # noqa: E402

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def rows(path):
    out = []
    with io.open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    say('第133轮 · 泄漏样本在事件链上的落点')
    live = rows(LIVE131)
    leaks = [r for r in live if ES.looks_like_meta_leak(r.get('reply') or '')]
    say('[分母] 第131轮样本 %d 条，其中 looks_like_meta_leak=True 的 %d 条'
        % (len(live), len(leaks)))
    if not leaks:
        say('[ABORT] 没有真泄漏样本 ⇒ 正控制无从谈起')
        return 3

    say('\n=== ① 截断到 24 字之后，闸还认不认 ===')
    keep = 0
    for r in leaks:
        raw = r['reply']
        first = ES.first_sentence(raw, ES.EVENT_MAX_CHARS)
        hit = ES.looks_like_meta_leak(first)
        keep += 1 if hit else 0
        say('  [%s/%s #%s] 截断后命中 = %s' % (r.get('arm'), r.get('qid'),
                                            r.get('sample'), hit))
        say('     first → %s' % first.replace('\n', ' ⏎ '))
    say('  截断后仍命中 %d/%d' % (keep, len(leaks)))

    say('\n=== ② 闸的位置：剥括号前 vs 剥括号后 ===')
    say('  %-14s %-8s %-8s %-10s %s' % ('样本', '剥前', '剥后', '剥后文本', '含义'))
    for r in leaks:
        raw = r['reply']
        first = ES.first_sentence(raw, ES.EVENT_MAX_CHARS)
        before = ES.looks_like_meta_leak(first)
        stripped = ES.strip_action_parentheticals(first)
        after = ES.looks_like_meta_leak(stripped)
        if before and after:
            mean = '两处都能拦'
        elif before and not after:
            mean = '★只有剥前能拦（剥完泄漏段被删掉/改形）'
        elif after and not before:
            mean = '只有剥后能拦'
        else:
            mean = '都拦不到'
        say('  %-14s %-8s %-8s %-10s %s' % (
            '%s/%s#%s' % (r.get('arm'), r.get('qid'), r.get('sample')),
            before, after, (stripped or '<空>')[:18], mean))

    say('\n=== ③ 假阳控制：本轮 42 条真机事件回复过新闸 ===')
    ev_rows = rows(EV133)
    fp = []
    for r in ev_rows:
        for field in ('raw', 'first', 'final'):
            t = r.get(field) or ''
            if t and ES.looks_like_meta_leak(t):
                fp.append((r['kind'], r['sample'], field, t))
    say('  样本 %d 条 × 3 段（raw/first/final）= %d 个断言位，命中 %d 个'
        % (len(ev_rows), len(ev_rows) * 3, len(fp)))
    for x in fp:
        say('    [假阳] %s #%s %s → %s' % x)
    say('  ★ 另有 %d 条"现在的 guard_reaction 放行、加闸后会被拦"的差异位：'
        % sum(1 for r in ev_rows
              if (r.get('first') or '') and not ES.looks_like_meta_leak(r.get('first') or '')
              and (r.get('final') or '') == (r.get('first') or '')))

    with io.open(os.path.join(EV, 'leak_landing133.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps({'n_live': len(live), 'n_leaks': len(leaks),
                            'truncated_hits': keep,
                            'event_rows': len(ev_rows), 'fp': len(fp)},
                           ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:          # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'scan133_probe_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
