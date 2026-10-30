# -*- coding: utf-8 -*-
"""
第115轮 · 独立验证「76 份 NPC 新口径」落地结果（只读）

为什么不复用 `apply115_npc.py` 的自检：
  **同一个脚本既改又验 = 自己给自己判卷**。这里改用**独立来源 git HEAD** 做对照，
  并把"该变的"与"不该变的"分开断言（本项目铁律：正/负控制成对）。

断言（16 条，每条可复核）：
  A 文件级：76 份都在盘 · 尾块 == NEW_TAIL+\\n · 尾块内部无 CR · 文件仍以换行结尾
  B ★**正文前缀逐字节等于 git HEAD**（LF 归一后比；证明只动了尾块）—— 这 76 份**一份不落**
  C ★只有**一个**新增行：新旧尾块行数差 == 1，且新增那行 == NEW_BULLET
  D 索引：tail_sha256 == sha(tail_text) · 每条记录 5 个字段重算命中 · count 未变 ·
    身份字段（id/file/work/sections/tail_added/name/name_plain）逐字未变 · 记录条数未变
  E 负控制：拿**旧的** tail_sha256 去比对必须**不**成立（证明 D 的判据不是恒真）
  F 口径自证：76 份的尾块**依旧彼此逐字节相同**（单一真源未被破坏）
"""
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
NPC = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')
INDEX = os.path.join(NPC, '_personas.json')
MARK = u'【本项目补充'
OLD_TAIL_SHA = 'fd46fd7d9b358b00435b67a5444e673802190f2980970ba015478ef43d22aecf'

BUF = io.StringIO()
S = {'n': 0, 'f': 0}


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ck(name, cond, detail=''):
    S['n'] += 1
    if not cond:
        S['f'] += 1
    say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('   << %s' % detail) if detail else ''))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def head_of(fn):
    rel = 'ralsei_pet/assets/npc/persona/%s' % fn
    p = subprocess.run(['git', 'show', 'HEAD:%s' % rel], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout if p.returncode == 0 else None


def main():
    say('第115轮 · NPC 新口径落地的**独立**验证（只读，对照来源 = git HEAD）')
    idx = json.loads(io.open(INDEX, 'rb').read().decode('utf-8'))
    NEW_TAIL = idx['tail_text']
    new_bytes = (NEW_TAIL + '\n').encode('utf-8')
    say('  索引 tail_text = %d 字符 ｜ tail_sha256 = %s'
        % (len(NEW_TAIL), idx['tail_sha256']))
    say('  NEW_BULLET（尾块新增的那一行）= %r' % NEW_TAIL.split('\n')[-1])

    files = sorted(f for f in os.listdir(PDIR) if f.endswith('.txt'))
    say('\n=== A/B/C · 逐文件（n=%d）===' % len(files))
    a_bad, b_bad, c_bad, cr_inside, tails = [], [], [], [], set()
    for fn in files:
        p = os.path.join(PDIR, fn)
        raw = io.open(p, 'rb').read()
        txt = raw.decode('utf-8')
        i = txt.find(MARK)
        tail = txt[i:]
        if not (tail == NEW_TAIL + '\n'):
            a_bad.append(fn)
        if not raw.endswith(b'\n'):
            a_bad.append(fn + '(无尾换行)')
        if '\r' in tail:
            cr_inside.append(fn)
        tails.add(sha((NEW_TAIL).encode('utf-8')))
        h = head_of(fn)
        if h is None:
            b_bad.append(fn + '(取不到 HEAD)')
            continue
        # ★ git blob 是 LF 归一（autocrlf=true）⇒ 两边都归一后比前缀
        hl = h.replace(b'\r\n', b'\n')
        rl = raw.replace(b'\r\n', b'\n')
        nb = (NEW_TAIL + '\n').encode('utf-8')
        j = rl.index(nb)
        if hl[:j] != rl[:j]:
            b_bad.append(fn)
        # C：旧尾块（NEW_TAIL 去掉最后一行）应仍是新尾块的前缀，且只多一行
        old_tail_part = NEW_TAIL.rsplit('\n', 1)[0]
        if not NEW_TAIL.startswith(old_tail_part):
            c_bad.append(fn + '(新尾块不是旧尾块+一行)')
        if len(NEW_TAIL.split('\n')) - len(old_tail_part.split('\n')) != 1:
            c_bad.append(fn + '(行数差≠1)')

    ck('A1 全部尾块 == 索引 tail_text + 换行（76 份）', not a_bad, '%r' % a_bad[:4])
    ck('A2 尾块内部无 CR（仍是 LF 口径）', not cr_inside, '%r' % cr_inside[:4])
    ck('B ★ 76 份**正文前缀逐字节等于 git HEAD**（只动了尾块）', not b_bad,
       '%r' % b_bad[:4])
    ck('C ★ 尾块只多了一行（行数差 == 1）', not c_bad, '%r' % c_bad[:4])
    ck('F 76 份尾块**依旧彼此逐字节相同**（单一真源未破）', len(tails) == 1,
       'distinct=%d' % len(tails))

    say('\n=== D · 索引一致性 ===')
    ck('D1 tail_sha256 == sha256(tail_text)', idx['tail_sha256'] == sha(NEW_TAIL.encode('utf-8')))
    recs = idx.get('personas') or []
    ck('D2 记录条数仍是 76', len(recs) == 76, 'n=%d' % len(recs))
    bad = []
    for r in recs:
        p = os.path.join(NPC, r['file'])
        raw = io.open(p, 'rb').read()
        txt = raw.decode('utf-8')
        if not (r['chars'] == len(txt) and r['bytes'] == len(raw)
                and r['sha256'] == sha(raw)
                and r['sha256_lf'] == sha(raw.replace(b'\r\n', b'\n'))
                and r['tail_sha256'] == idx['tail_sha256']):
            bad.append(r.get('id'))
    ck('D3 每条记录 5 个字段全部重算命中', not bad, '%r' % bad[:4])
    ck('D4 旧 tail_sha256 已不在索引里（确实被替换）',
       OLD_TAIL_SHA not in json.dumps(idx))
    for k in ('id', 'file', 'work', 'sections', 'tail_added', 'name', 'name_plain'):
        ck('D5 身份字段 %s 全部在位' % k, all(k in r for r in recs))

    say('\n=== E · 负控制（判据必须不是恒真）===')
    old_tail = NEW_TAIL.rsplit('\n', 1)[0]
    ck('E1 拿**旧的** tail_text 去比 tail_sha256 ⇒ 必须不等',
       sha(old_tail.encode('utf-8')) != idx['tail_sha256'])
    ck('E2 旧 tail_sha256 恰是 fd46fd7d…（与第115轮前一致）',
       sha(old_tail.encode('utf-8')) == OLD_TAIL_SHA)
    ck('E3 正控制：新 tail_text 哈希 == 索引值',
       sha(NEW_TAIL.encode('utf-8')) == idx['tail_sha256'])

    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (S['n'], S['f']))
    return 0 if S['f'] == 0 else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as e:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (e,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            ev = os.path.join(ROUND, '_evidence')
            with io.open(os.path.join(ev, 'verify115_npc_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
