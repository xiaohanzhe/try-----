# -*- coding: utf-8 -*-
"""第140轮破坏性负控制：把本轮每一条"真守卫"逐个拆掉，`check140` 必须报红。

纪律（沿用第139轮）：
  · 备份放在内存里，`finally` 一律还原；
  · 还原后必须**重新全绿**（否则等于不知道自己是把什么改坏的）；
  · 每个用例都断言"**具体哪一条判据**红了"，不是只看"退出码非零"
    —— 退出码非零也可能是因为语法错（那是夹具坏了，不是判据抓到了）。
  · 锚点必须唯一：`count(old) == 1` 才动手，否则 abort（防 `replace(...,1)` 改错地方）。
"""
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
NP_PY = os.path.join(PET, 'modules', 'npc_persona.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
CARD_JSON = os.path.join(PET, 'assets', 'npc', '_training', 'cards', 'ralsei.json')
CHECK = os.path.join(HERE, 'check140.py')

PY = sys.executable


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _lf(t):
    """★★ 锚点必须先在 **LF 归一化**的文本上匹配。

    `main.py` 工作区是 CRLF（`git show HEAD:` 里是 LF —— 仓库侧被归一化过，
    两边看到的字节不一样）。第一版直接拿 `'...\\n'` 当锚点，`count()` 是 0，
    报"锚点不唯一" —— 看起来像判据问题，其实是夹具问题。
    """
    return t.replace(u'\r\n', u'\n')


def _eol_of(t):
    return u'\r\n' if u'\r\n' in t else u'\n'


def _write(p, t, eol=u'\n'):
    t = _lf(t).replace(u'\n', eol)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _run():
    p = subprocess.run([PY, CHECK], cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def _fails(out):
    return [l.strip() for l in out.splitlines() if l.strip().startswith('[FAIL]')]


# (名字, 文件, [(旧串, 新串), ...], 期望报红的判据前缀)
CASES = [
    (u'M1 结算层不读卡（直接返回兜底）', NP_PY,
     [(u"    try:\n        got = training_length_policy(npc_id)\n        if got:\n"
       u"            return min(int(got[0]), cap), int(got[1])\n",
       u"    try:\n        got = None\n        if got:\n"
       u"            return min(int(got[0]), cap), int(got[1])\n")],
     [u'C1', u'D1']),

    (u'M2 卡片规格与兜底同值（200→220，等于卡片不起作用）', CARD_JSON,
     [(u'"max_chars": 200', u'"max_chars": 220')],
     [u'A1', u'C1', u'D1']),

    (u'M3 `type(x) is int` 退回 `isinstance`（`true` 被当成 1）', NP_PY,
     [(u'if type(chars) is int and type(sents) is int and chars > 0 and sents > 0:',
       u'if isinstance(chars, int) and isinstance(sents, int) and chars > 0 and sents > 0:')],
     [u'B5']),

    (u'M4 卡片可以**放宽**兜底（min → max）', NP_PY,
     [(u'            return min(int(got[0]), cap), int(got[1])',
       u'            return max(int(got[0]), cap), int(got[1])')],
     [u'C3']),

    (u'M5 加载层不再读 `max_sentences`（字段彻底不碰）', NP_PY,
     [(u"            sents = lp.get('max_sentences')", u"            sents = 3")],
     [u'E3']),

    (u'M6 偷偷把句数额度接进截断（`_max_sent` 参与比较/截断）', MAIN_PY,
     [(u'            if len(t) > max_chars:\n',
       u'            if _max_sent and len(t.split(u\'。\')) > _max_sent + 1:\n'
       u'                t = u\'。\'.join(t.split(u\'。\')[:_max_sent]) + u\'。\'\n'
       u'            if len(t) > max_chars:\n')],
     [u'E1', u'D2']),

    (u'M6b 句数额度被**当实参**传出去（哪怕只是传、不改行为）', MAIN_PY,
     [(u'            if len(t) > max_chars:\n',
       u'            _ = str(_max_sent)\n'
       u'            if len(t) > max_chars:\n')],
     [u'E1', u'E2']),

    (u'M7 把兜底常量改成 200（改常量冒充"接了卡片"）', MAIN_PY,
     [(u'    AI_REPLY_MAX_CHARS = 220', u'    AI_REPLY_MAX_CHARS = 200')],
     [u'F1']),
]


def main():
    rc, out = _run()
    if rc != 0:
        print(u'✗ 起点就不绿，先修 check140 再来跑变异')
        print(out[-2000:])
        return 1
    print(u'起点：check140 全绿（%s）' % out.strip().splitlines()[-1])

    bad = []
    for name, path, edits, expect in CASES:
        raw = _read(path)
        eol = _eol_of(raw)
        orig = _lf(raw)
        try:
            cur = orig
            ok_anchor = True
            for old, new in edits:
                if cur.count(old) != 1:
                    print(u'✗ %s：锚点不唯一（%d 处）—— 夹具问题，不算判据通过'
                          % (name, cur.count(old)))
                    ok_anchor = False
                    break
                cur = cur.replace(old, new)
            if not ok_anchor:
                bad.append((name, u'锚点不唯一'))
                continue
            _write(path, cur, eol)
            rc2, out2 = _run()
            fails = _fails(out2)
            hit = [e for e in expect if any(f.startswith(u'[FAIL] ' + e) for f in fails)]
            missed = [e for e in expect if e not in hit]
            if rc2 != 0 and not missed and fails:
                print(u'✓ %s ⇒ %s（报红 %d 条，命中 %r）'
                      % (name, 'RED', len(fails), hit))
            else:
                print(u'✗ %s ⇒ 没按预期报红：rc=%d 未命中=%r 实际 FAIL=%r'
                      % (name, rc2, missed, fails[:4]))
                bad.append((name, u'未命中 %r' % (missed,)))
        finally:
            _write(path, orig, eol)

    # 还原后必须重新全绿
    rc3, out3 = _run()
    print(u'')
    print(u'还原后：rc=%d %s' % (rc3, out3.strip().splitlines()[-1]))
    if rc3 != 0:
        bad.append((u'还原后仍红', u''))

    print(u'')
    print(u'=== mutate140：%d 用例 / %d 不合格 ===' % (len(CASES), len(bad)))
    for n, why in bad:
        print(u'  ✗ %s %s' % (n, why))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
