# -*- coding: utf-8 -*-
"""第131轮 · 真机 7 题复测 —— 第130轮补回来的那四节，到底有没有用？

背景：第130轮把第115轮丢在 worktree 里的人设四节取回来了，但**没有重发过请求**
（报告 §7 遗留第 3 条）。本轮补这一刀：同一个模型、同一批问题、同一段尾部，
只变 system 里的人设正文 —— 比的是「四节在不在」。

两臂：
  before = `git show edae364^:ralsei_pet/assets/ralsei_persona.md`
           （第130轮之前，7 节 / 3,606 字符；快照落 `_evidence/persona_before130.md`）
  after  = 磁盘现值（11 节 / 4,494 字符）

★ 复用第115轮的探针模块（`probe115ab`）而不是另抄一份：
  HTTP（含 ProxyHandler({}) 绕开本机代理）、护栏两张表（产品真源）、
  关系段/紧张段（`modules/relationship.py` 真源）、`judge()`、`extra_flags()`
  全部走同一份实现 —— 判据不许两处各写一遍。

★ 设计上的两处刻意安排（写下来，免得下一轮的人以为是随手写的）：
  1. **题序交错**：按题循环、两臂交替（偶数题 before→after，奇数题 after→before），
     抵消"跑得越久越热/越飘"的单调漂移；不是一臂跑完再跑另一臂。
  2. **先热身两条**（丢弃不计），避免把冷启动的差异化成绩算到人设头上。

只读产品文件 + 发本机 HTTP；产物全落 `code-quality-audit/第131轮-真机7题复测/`。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
T115 = os.path.join(ROOT, 'code-quality-audit', '第115轮-AI人味训练', '_tools')
BASE_COMMIT = 'edae364^'          # 第130轮之前那一版（人设 7 节）
SAMPLES = int(os.environ.get('S131_SAMPLES', '3'))
WARMUP = 2

if not os.path.isdir(EV):
    os.makedirs(EV)
if T115 not in sys.path:
    sys.path.insert(0, T115)
import probe115ab as AB           # noqa: E402

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def read_text(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def persona_before():
    """第130轮之前的人设原文 —— 从 git 取，不是凭记忆重建。"""
    import subprocess
    r = subprocess.run(['git', 'show', '%s:ralsei_pet/assets/ralsei_persona.md' % BASE_COMMIT],
                       cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git show 失败：%s' % r.stderr.decode('utf-8', 'replace')[:300])
    return r.stdout.decode('utf-8')


# ---------------------------------------------------------------- 判读旗标
# SIDE / PUSHBACK / ADMIT 三个沿用第115轮的既有实现（同一份口径，不另抄）；
# 本轮的 Q5/Q6 还需要三个新旗标，就地补，并且**都有题目编号作为上下文**。
VAGUE_COMFORT = ('不要放弃', '继续努力', '加油', '别灰心', '振作')
# Q7 的正向行为：把"我是被写出来的角色"这层说破（不悲情、不解释存在意义）
#   ★ 试跑一次才发现必须先有这个旗标：before 组的 Q7 是"整句躲开"
#     （「你说的是坏消息吧…那件事具体是怎么样的？」），产品护栏当然不会报红 ——
#     用 OOC 命中数去量"它到底认不认"，等于**用空集证明没问题**。
ROLE_ACK = ('游戏', '角色', '写出来', '被写')
# Q5 的病灶之一（分节原文：「别把同一个问题问回去」）—— 只作观察量，不做结论。
ASKS_WHERE = ('是哪儿', '在哪儿', '哪个地方', '什么地方', '哪里')


def flags(reply, qid):
    ex = dict(AB.extra_flags(reply, qid))       # side / pushback / admit（115 的口径）
    t = reply or ''
    ex['vague'] = any(w in t for w in VAGUE_COMFORT)   # Q5 的病灶：把地名当空气，回一句鼓励
    ex['place'] = '城堡镇' in t                        # Q5 的正确行为：接住他说的那个地方
    # Q6 的病灶：他问"是不是叫豆豆"，回复直接把名字认下来（ADMIT 缺席时才算编）
    ex['confab'] = ('豆豆' in t) and (not ex['admit'])
    ex['role_ack'] = any(w in t for w in ROLE_ACK)     # Q7：承认这层身份
    ex['asks_where'] = any(w in t for w in ASKS_WHERE)  # Q5：把问题问回去（观察量）
    return ex


def one_call(system, q, qid, kind, arm, sample, idx, ooc, banned):
    t0 = time.time()
    try:
        r = AB.post('/api/chat', {
            'model': AB.MODEL, 'stream': False,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': q}],
            'options': {'num_ctx': AB.NUM_CTX, 'num_predict': AB.NUM_PREDICT,
                        'temperature': AB.TEMP_BASE, 'top_p': 0.92,
                        'repeat_penalty': 1.15}})
        msg = (r.get('message') or {}).get('content', '') or ''
        rec = {'arm': arm, 'qid': qid, 'kind': kind, 'q': q, 'sample': sample,
               'idx': idx, 'reply': msg,
               'prompt_eval_count': r.get('prompt_eval_count'),
               'eval_count': r.get('eval_count'),
               'total_s': round((r.get('total_duration') or 0) / 1e9, 2),
               'wall_s': round(time.time() - t0, 2),
               'judge': AB.judge(msg, ooc, banned)}
    except Exception as exc:                     # noqa: BLE001
        rec = {'arm': arm, 'qid': qid, 'kind': kind, 'q': q, 'sample': sample,
               'idx': idx, 'reply': '', 'error': repr(exc),
               'wall_s': round(time.time() - t0, 2),
               'judge': {'empty': True}}
    rec['extra'] = flags(rec['reply'], qid)
    return rec


def main():
    say('第131轮 · 真机 7 题复测（第130轮补回的四节有没有用）')
    say('  REPO    = %s' % ROOT)
    say('  PERSONA = %s' % PERSONA)
    say('  基线     = %s（第130轮之前）' % BASE_COMMIT)

    cur = read_text(PERSONA).strip()
    old = persona_before().strip()
    with io.open(os.path.join(EV, 'persona_before130.md'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(persona_before())

    # ★ 分母闸 + A/B 先断言"两臂真的不同"
    say('\n[自证] after  = %d 字符 / %d 节' % (len(cur), cur.count('\n—— ') + 1))
    say('[自证] before = %d 字符 / %d 节' % (len(old), old.count('\n—— ') + 1))
    say('[自证] 两臂正文不同 = %s（必须 True）' % (cur != old))
    if cur == old:
        say('[ABORT] 两臂人设正文相同 ⇒ 这轮 A/B 没有意义')
        return 3
    for s in ('我是什么', '他说话的时候，先把他的事接住',
              '他说要去一个地方的时候', '我想起来的事'):
        say('  before 含「%s」= %s    after 含 = %s'
            % (s, ('—— ' + s) in old, ('—— ' + s) in cur))

    if not AB.ensure_server():
        return 2
    try:
        rel = AB.real_relationship_segment()
        tail = "\n\n".join(x for x in (AB._ACTUAL_CTX(), rel['brief'], rel['nervous'],
                                       AB._ACTUAL_RECALL(), AB._ACTUAL_HISTORY()) if x)
        ooc, banned, src = AB.load_guard_patterns()
        say('[真源] 关系段 %s' % rel['source'])
        say('[真源] 护栏两张表 %s（OOC=%d BANNED=%d）' % (src, len(ooc), len(banned)))

        systems = {'before': old, 'after': cur}
        for k in ('before', 'after'):
            say('  system[%s] = %d 字符（含尾部 %d）'
                % (k, len(systems[k]) + 2 + len(tail), len(tail)))

        # ---- 热身（丢弃）----
        say('\n=== 热身 %d 条（不计入结果）===' % WARMUP)
        for i in range(WARMUP):
            t0 = time.time()
            AB.post('/api/chat', {'model': AB.MODEL, 'stream': False,
                                  'messages': [{'role': 'system', 'content': cur + "\n\n" + tail},
                                               {'role': 'user', 'content': '你好'}],
                                  'options': {'num_ctx': AB.NUM_CTX, 'num_predict': 32,
                                              'temperature': 0.0}})
            say('  热身 #%d  %.1fs' % (i + 1, time.time() - t0))

        # ---- 正式：题序交错，两臂交替 ----
        say('\n=== 正式：7 题 × 2 臂 × %d 采样（题序交错）===' % SAMPLES)
        rows = []
        idx = 0
        for qi, (qid, kind, q) in enumerate(AB.QUESTIONS):
            order = ('before', 'after') if qi % 2 == 0 else ('after', 'before')
            for arm in order:
                system = systems[arm] + "\n\n" + tail
                for s in range(SAMPLES):
                    idx += 1
                    rec = one_call(system, q, qid, kind, arm, s + 1, idx, ooc, banned)
                    rows.append(rec)
                    say('  #%02d [%s/%s %s #%d] %.1fs pec=%s eval=%s'
                        % (idx, arm, qid, kind, s + 1, rec.get('wall_s', 0),
                           rec.get('prompt_eval_count'), rec.get('eval_count')))
                    say('      → %s' % (rec['reply'] or '<空>').replace('\n', ' / '))

        # ---- 汇总 ----
        say('\n=== 汇总（机械可复核；n=%d/题/臂）===' % SAMPLES)
        FIELDS = ('side', 'pushback', 'admit', 'vague', 'place', 'confab',
                  'role_ack', 'asks_where')
        head = '  %-9s %-6s ' % ('arm', 'qid') + ' '.join('%-8s' % f for f in FIELDS) + ' 字数'
        say(head)
        summ = {}
        for arm in ('before', 'after'):
            for qid, _k, _q in AB.QUESTIONS:
                rs = [r for r in rows if r['arm'] == arm and r['qid'] == qid]
                cells = []
                for f in FIELDS:
                    n = sum(1 for r in rs if (r.get('extra') or {}).get(f))
                    cells.append('%d/%d' % (n, len(rs)))
                chars = sum(r['judge'].get('chars', 0) for r in rs) / max(1, len(rs))
                say('  %-9s %-6s ' % (arm, qid) + ' '.join('%-8s' % c for c in cells)
                    + ' %.0f' % chars)
                summ.setdefault(arm, {})[qid] = {
                    'n': len(rs),
                    'flags': {f: sum(1 for r in rs if (r.get('extra') or {}).get(f))
                              for f in FIELDS},
                    'ooc': sum(1 for r in rs if r['judge'].get('ooc_hits')),
                    'banned': sum(1 for r in rs if r['judge'].get('banned_hits')),
                    'md': sum(1 for r in rs if r['judge'].get('md_marks')),
                    'mean_chars': round(chars, 1),
                }

        say('\n  ★ 三题的方向（before → after；↑=该出现，↓=不该出现）:')
        for qid, label, field, want in (('Q5', '寻路', 'place', '↑'),
                                        ('Q5', '寻路', 'vague', '↓'),
                                        ('Q6', '记忆·不许编', 'confab', '↓'),
                                        ('Q6', '记忆·不许编', 'admit', '↑'),
                                        ('Q7', '世界观·知道是游戏', 'role_ack', '↑'),
                                        ('Q7', '世界观·知道是游戏', 'ooc', '↓')):
            b = summ['before'][qid]['flags'].get(field, 0)
            a = summ['after'][qid]['flags'].get(field, 0)
            mark = ''
            if want == '↑' and a > b:
                mark = '  ← 变好'
            elif want == '↓' and a < b:
                mark = '  ← 变好'
            elif a == b:
                mark = '  （没动）'
            else:
                mark = '  ← 变差'
            say('    %s %-12s %-10s%s %d/%d → %d/%d%s'
                % (qid, label, field, want, b, summ['before'][qid]['n'],
                   a, summ['after'][qid]['n'], mark))

        with io.open(os.path.join(EV, 'live7_131.jsonl'), 'w',
                     encoding='utf-8', newline='') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        out = {'base_commit': BASE_COMMIT, 'samples': SAMPLES,
               'persona_after_chars': len(cur), 'persona_before_chars': len(old),
               'model': AB.MODEL, 'num_ctx': AB.NUM_CTX, 'num_predict': AB.NUM_PREDICT,
               'temperature': AB.TEMP_BASE, 'tail_chars': len(tail),
               'guard_src': src, 'ooc_n': len(ooc), 'banned_n': len(banned),
               'summary': summ, 'n_rows': len(rows)}
        with io.open(os.path.join(EV, 'live7_131_summary.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
        say('\n[落盘] live7_131.jsonl（%d 条） / live7_131_summary.json' % len(rows))
    finally:
        AB.stop_server()
    return 0


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:      # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'probe131_live7_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
