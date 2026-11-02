# -*- coding: utf-8 -*-
"""第139轮 · A/B：`patches["ralsei"]` 里那句「一次最多两三句」到底有没有用。

## 为什么要测，而不是直接删

第137轮把 `patches["ralsei"]` 接进主宠 system 时，登记过一条遗留：
它第一句「一次最多两三句，短一点，像随口说出来的。」与 persona「我怎么说」里的
「一次只说 1~3 句，像真人在聊天框里随手打字」**语义重复**，当时写的是「冗余但无害」。

本轮把这句话当成**被测物**，不再当成口味问题：

- `第113轮/_evidence/raw30/ralsei.jsonl`（48 轮真机，**patch 里没有这句**）：
  按"句末标点+换行"切句，**>3 句 40/48**，平均 117 字。
  ⇒ 光靠 persona 那一句，7B 有八成不照做。
- 那句是 `common113.PATCH_RULES['TOO_LONG']` 的产物，**96 位角色人人一条**；
  而 **76 份 NPC 人设里本来就写着「一次开口通常 1~2 句，最长不超过 200 字」**
  ⇒ 这不是 ralsei 一个人的重复，是**训练层在复述人设层已有的规格**。

所以问题不是"读起来重不重"，而是：**这第二次重复，换来了任何可测的差别吗？**
测过才知道。本脚本就是这一刀。

## 两臂（唯一变量＝尾块里有没有那 20 个字）

  no1   = persona 全文 + `PATCH_HEADER_RALSEI` + patch（**去掉**①）
  with1 = persona 全文 + `PATCH_HEADER_RALSEI` + patch（**保留**①，即磁盘现值）

★ `no1` 臂的 patch **必须与 raw30 那次 48 轮真机用的逐字相同** —— 脚本里先断言这一点
  （否则"两臂只差 ①"就是自说自话，可能还差了别的）。断言不过直接 abort。

## 怎么读结果

- 主观察量：**句数 >3 的比例**（口径与 persona「1~3 句」对齐，不是按 200 字符）。
- 次观察量：平均字数、护栏旗标（`judge`）作 sanity —— 两臂护栏命中都不该涨。
- **两臂 system 长度差 ~13 token**（20 字），与第131轮那次 577 token 的差别不同，可以忽略，
  但仍然写进报告，不假装是"干净的内容隔离"。
- 采样温度 0.85 ⇒ 单条波动大，所以**题序交错**（按题循环、两臂交替；奇偶题换向），
  并先热身 2 条丢弃。

只读产品文件 + 发本机 HTTP（`probe115ab` 的那份实现：绕代理、护栏两张表、关系段真源）。
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
INDEX_JSON = os.path.join(PET, 'assets', 'npc', '_training', '_index.json')
RAW30 = os.path.join(ROOT, 'code-quality-audit', u'第113轮-全体角色AI训练',
                     '_evidence', 'raw30', 'ralsei.jsonl')
T115 = os.path.join(ROOT, 'code-quality-audit', u'第115轮-AI人味训练', '_tools')

SAMPLES = int(os.environ.get('S139_SAMPLES', '4'))
WARMUP = 2
#: ① 那句（第113轮 `common113.PATCH_RULES['TOO_LONG']` 的原句）+ 一个分隔空格
LEAD = u'一次最多两三句，短一点，像随口说出来的。 '

for p in (T115, os.path.join(PET, 'src')):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import probe115ab as AB                                        # noqa: E402
import main as M                                               # noqa: E402

END = u'\u3002\uff01\uff1f!?\u2026'
NP = M.npc_persona_mod

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def read_text(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def sents(t):
    """按句末标点 + 换行切句；连续标点归一处。与 `raw30` 那份统计同口径。"""
    t = (t or u'').strip()
    if not t:
        return []
    out = []
    buf = []
    i = 0
    n = len(t)
    while i < n:
        ch = t[i]
        if ch == u'\n':
            s = u''.join(buf).strip()
            if s:
                out.append(s)
            buf = []
            i += 1
            continue
        buf.append(ch)
        if ch in END:
            while i + 1 < n and t[i + 1] in END:
                i += 1
                buf.append(t[i])
            s = u''.join(buf).strip()
            if s:
                out.append(s)
            buf = []
        i += 1
    s = u''.join(buf).strip()
    if s:
        out.append(s)
    return out


def arm_system(persona, patch):
    """**走产品那条路**：临时把 `training_patch` 打成返回指定串，再调产品函数。"""
    orig = NP.training_patch
    try:
        NP.training_patch = lambda *_a, **_k: patch
        return M._with_ralsei_patch(persona)
    finally:
        NP.training_patch = orig


def one_call(system, q, qid, kind, arm, sample, idx, ooc, banned):
    t0 = time.time()
    rec = {'arm': arm, 'qid': qid, 'kind': kind, 'q': q, 'sample': sample, 'idx': idx}
    try:
        r = AB.post('/api/chat', {
            'model': AB.MODEL, 'stream': False,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': q}],
            'options': {'num_ctx': AB.NUM_CTX, 'num_predict': AB.NUM_PREDICT,
                        'temperature': AB.TEMP_BASE, 'top_p': 0.92,
                        'repeat_penalty': 1.15}})
        msg = (r.get('message') or {}).get('content', '') or ''
        rec.update({'reply': msg,
                    'prompt_eval_count': r.get('prompt_eval_count'),
                    'eval_count': r.get('eval_count'),
                    'total_s': round((r.get('total_duration') or 0) / 1e9, 2)})
        rec['judge'] = AB.judge(msg, ooc, banned)
    except Exception as exc:                                   # noqa: BLE001
        rec.update({'reply': '', 'error': repr(exc), 'judge': {'empty': True}})
    rec['wall_s'] = round(time.time() - t0, 2)
    ss = sents(rec['reply'])
    rec['sents'] = len(ss)
    rec['chars'] = len((rec['reply'] or u'').strip())
    return rec


def rate(rows, arm, pred):
    rs = [r for r in rows if r['arm'] == arm]
    return sum(1 for r in rs if pred(r)), len(rs)


def main():
    say(u'第139轮 · A/B：patch 里「一次最多两三句」有没有用')
    say(u'  REPO = %s' % ROOT)
    say(u'  MODEL = %s   num_ctx=%s num_predict=%s temp=%s  n=%d/题/臂'
        % (AB.MODEL, AB.NUM_CTX, AB.NUM_PREDICT, AB.TEMP_BASE, SAMPLES))

    persona = read_text(PERSONA)
    idx = json.loads(read_text(INDEX_JSON))
    patch_with1 = (idx.get('patches') or {}).get('ralsei') or u''
    if not patch_with1.startswith(LEAD):
        say(u'[ABORT] 磁盘上的 patch 不以 ① 开头，本脚本的前提（① 在最前）不成立')
        return 3
    patch_no1 = patch_with1[len(LEAD):].strip()

    # ★★ 自证一：`no1` 与 raw30 那次 48 轮真机用的 patch 是否同一份。
    #   ★ 实测：**差一个空格** —— 磁盘上两句之间是 `。 `（`cards113` 用 ' ' 拼），
    #     raw30 当时是 `。`（旧拼法）。所以这里按"去掉空格后逐字相同"判同一份，
    #     并把这条差异**打出来**（不是悄悄归一化了就算）。
    raw = json.loads(io.open(RAW30, encoding='utf-8').readline())
    raw_patch = (raw.get('patch') or u'').strip()
    _same_raw = patch_no1.replace(u' ', u'') == raw_patch.replace(u' ', u'')
    say(u'\n[自证] no1 与 raw30 当时的 patch 内容相同（忽略空格）：%s' % _same_raw)
    if patch_no1 != raw_patch:
        say(u'[自证] 逐字比较不同，只差空格：%s'
            % (patch_no1.replace(u' ', u'') == raw_patch.replace(u' ', u'')))
        say(u'  no1   = %r' % patch_no1)
        say(u'  raw30 = %r' % raw_patch)
    say(u'[自证] with1 含①=%s   no1 含①=%s' % (LEAD.strip() in patch_with1,
                                              LEAD.strip() in patch_no1))
    if not _same_raw:
        say(u'[ABORT] no1 与 raw30 不是同一份 ⇒ 两臂不止差 ①，结论不可信')
        return 3

    sys_no1 = arm_system(persona, patch_no1)
    sys_with1 = arm_system(persona, patch_with1)
    # ★★ 自证二：把 with1 里那 20 字抠掉，必须**逐字等于** no1（否则两臂不止差 ①）
    say(u'\n[自证] with1 抠掉①后 == no1：%s' % (sys_with1.replace(LEAD, u'', 1) == sys_no1))
    if sys_with1.replace(LEAD, u'', 1) != sys_no1:
        say(u'[ABORT] 两臂不是只差那 20 字')
        return 3
    say(u'[自证] persona=%d 字  patch no1=%d  with1=%d  system %d vs %d'
        % (len(persona), len(patch_no1), len(patch_with1), len(sys_no1), len(sys_with1)))

    if not AB.ensure_server():
        return 2
    try:
        rel = AB.real_relationship_segment()
        tail = u"\n\n".join(x for x in (AB._ACTUAL_CTX(), rel['brief'], rel['nervous'],
                                        AB._ACTUAL_RECALL(), AB._ACTUAL_HISTORY()) if x)
        ooc, banned, src = AB.load_guard_patterns()
        say(u'[真源] 关系段 %s ｜ 护栏 %s（OOC=%d BANNED=%d）｜ 尾部 %d 字'
            % (rel['source'], src, len(ooc), len(banned), len(tail)))

        systems = {'no1': sys_no1 + u'\n\n' + tail,
                   'with1': sys_with1 + u'\n\n' + tail}

        say(u'\n=== 热身 %d 条（丢弃）===' % WARMUP)
        for i in range(WARMUP):
            t0 = time.time()
            AB.post('/api/chat', {'model': AB.MODEL, 'stream': False,
                                  'messages': [{'role': 'system', 'content': systems['with1']},
                                               {'role': 'user', 'content': u'你好'}],
                                  'options': {'num_ctx': AB.NUM_CTX, 'num_predict': 32,
                                              'temperature': 0.0}})
            say(u'  热身 #%d  %.1fs' % (i + 1, time.time() - t0))

        say(u'\n=== 正式：7 题 × 2 臂 × %d 采样（题序交错）===' % SAMPLES)
        rows = []
        nidx = 0
        for qi, (qid, kind, q) in enumerate(AB.QUESTIONS):
            order = ('no1', 'with1') if qi % 2 == 0 else ('with1', 'no1')
            for arm in order:
                for s in range(SAMPLES):
                    nidx += 1
                    rec = one_call(systems[arm], q, qid, kind, arm, s + 1, nidx, ooc, banned)
                    rows.append(rec)
                    say(u'  #%02d [%-6s %s #%d] %5.1fs 句=%d 字=%d'
                        % (nidx, arm, qid, s + 1, rec.get('wall_s', 0),
                           rec['sents'], rec['chars']))
                    say(u'      → %s' % (rec['reply'] or u'<空>').replace(u'\n', u' / '))

        say(u'\n=== 汇总（机械可复核）===')
        for arm in ('no1', 'with1'):
            rs = [r for r in rows if r['arm'] == arm]
            over = sum(1 for r in rs if r['sents'] > 3)
            mean_s = sum(r['sents'] for r in rs) / max(1, len(rs))
            mean_c = sum(r['chars'] for r in rs) / max(1, len(rs))
            empty = sum(1 for r in rs if (r.get('judge') or {}).get('empty'))
            oocn = sum(1 for r in rs if (r.get('judge') or {}).get('ooc_hits'))
            band = sum(1 for r in rs if (r.get('judge') or {}).get('banned_hits'))
            mdn = sum(1 for r in rs if (r.get('judge') or {}).get('md_marks'))
            say(u'  %-6s >3句 %d/%d  平均句数 %.2f  平均 %d 字  '
                u'空=%d OOC=%d BANNED=%d MD=%d'
                % (arm, over, len(rs), mean_s, int(mean_c), empty, oocn, band, mdn))

        # 逐题看方向（样本小，只作参考，不作结论）
        say(u'\n  逐题 >3 句（no1 → with1）:')
        for qid, _k, _q in AB.QUESTIONS:
            a, na = rate([r for r in rows if r['qid'] == qid], 'no1', lambda r: r['sents'] > 3)
            b, nb = rate([r for r in rows if r['qid'] == qid], 'with1', lambda r: r['sents'] > 3)
            say(u'    %s  %d/%d → %d/%d' % (qid, a, na, b, nb))

        with io.open(os.path.join(EV, 'ab139.jsonl'), 'w',
                     encoding='utf-8', newline='') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        def agg(arm):
            rs = [r for r in rows if r['arm'] == arm]
            return {'n': len(rs),
                    'over3': sum(1 for r in rs if r['sents'] > 3),
                    'mean_sents': round(sum(r['sents'] for r in rs) / max(1, len(rs)), 3),
                    'mean_chars': round(sum(r['chars'] for r in rs) / max(1, len(rs)), 1),
                    'empty': sum(1 for r in rs if (r.get('judge') or {}).get('empty')),
                    'ooc': sum(1 for r in rs if (r.get('judge') or {}).get('ooc_hits')),
                    'banned': sum(1 for r in rs if (r.get('judge') or {}).get('banned_hits')),
                    'md': sum(1 for r in rs if (r.get('judge') or {}).get('md_marks'))}

        out = {'samples': SAMPLES, 'model': AB.MODEL, 'num_ctx': AB.NUM_CTX,
               'num_predict': AB.NUM_PREDICT, 'temperature': AB.TEMP_BASE,
               'system_chars': {'no1': len(systems['no1']), 'with1': len(systems['with1'])},
               'patch_chars': {'no1': len(patch_no1), 'with1': len(patch_with1)},
               'tail_chars': len(tail), 'guard_src': src,
               'ab': {'no1': agg('no1'), 'with1': agg('with1')},
               'n_rows': len(rows)}
        with io.open(os.path.join(EV, 'ab139_summary.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
        say(u'\n[落盘] ab139.jsonl（%d 条） / ab139_summary.json' % len(rows))
    finally:
        AB.stop_server()
    return 0


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:                              # noqa: BLE001
        import traceback
        say(u'[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'probe139_ab_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
