# -*- coding: utf-8 -*-
"""第142轮 · 破坏性负控制：每条关键判据都必须在被破坏时**变红**。

本轮不改产品代码，所以"破坏"打在三处：卡片数据、人设文本、训练链路源码。
每一处都断言**指定**判据报红 —— 红错了（红的是别的 ID）也算失败，
那说明判据之间互相顶替、归因不清。

★ 锚点全用单行片段（避免 CRLF/LF 混写）；文件按 `newline=''` 读写，**不改 EOL**。
★ 每处破坏 `finally` 还原，并用 sha1 核对确实恢复原样。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
TRAIN = os.path.join(PET, 'assets', 'npc', '_training')
CARDS_DIR = os.path.join(TRAIN, 'cards')
PERSONA_DIR = os.path.join(PET, 'assets', 'npc', 'persona')
COMMON_PY = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                         '_tools', 'common113.py')
EV_JSON = os.path.join(ROUND, '_evidence', 'lead142b.json')
CHECK = os.path.join(HERE, 'check142.py')
PY = sys.executable

LEAD = u'一次最多两三句，短一点，像随口说出来的。'

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def _sha1(p):
    return hashlib.sha1(_read(p).encode('utf-8')).hexdigest()


def _run_check():
    r = subprocess.run([PY, CHECK], capture_output=True)
    out = r.stdout.decode('utf-8', 'replace')
    fails = re.findall(u'^\\[FAIL\\] (\\S+)', out, re.M)
    return r.returncode, fails, out


class Mut(object):
    def __init__(self, path, label):
        self.path = path
        self.label = label
        self.before = None
        self.sha = None

    def __enter__(self):
        self.before = _read(self.path)
        self.sha = _sha1(self.path)
        return self

    def apply(self, old, new, expect_n=1):
        n = self.before.count(old)
        if n != expect_n:
            raise AssertionError(u'%s: 锚点出现 %d 次（应为 %d）: %r'
                                 % (self.label, n, expect_n, old[:50]))
        _write(self.path, self.before.replace(old, new, 1))
        return n

    def write(self, s):
        _write(self.path, s)

    def __exit__(self, *a):
        _write(self.path, self.before)
        assert _sha1(self.path) == self.sha, u'%s: 还原后 sha1 不符！' % self.label
        return False


def case(idx, label, expect):
    rc, fails, out = _run_check()
    got = sorted(set(fails))
    ok = (rc == 1) and all(e in fails for e in expect)
    print(u'  → check142 退出码 %d · 红了 %d 条：%s' % (rc, len(got), u','.join(got)))
    check(u'%s %s' % (idx, label), ok, u'期望红 %r' % (expect,))
    if not ok:
        print(u'----- 输出尾部 -----')
        print(u'\n'.join(out.strip().splitlines()[-14:]))


def main():
    print(u'=== 基线：不破坏时必须全绿 ===')
    rc0, fails0, out0 = _run_check()
    n_pass = len(re.findall(u'^\\[PASS\\] ', out0, re.M))
    print(u'  退出码 %d · PASS=%d · FAIL=%d' % (rc0, n_pass, len(fails0)))
    check(u'M0 基线全绿（18 PASS / 0 FAIL）', rc0 == 0 and not fails0 and n_pass == 18)
    print(u'')

    print(u'=== 破坏 1：把 asgore 的 ① 删掉（模拟"批量删一条"）===')
    with Mut(os.path.join(CARDS_DIR, 'asgore.json'), 'M1') as m:
        m.apply(LEAD, u'')
        case(u'M1', u'少一条 ① → C1(仍 38 条) + A4(三份不一致) 必须红',
             [u'C1', u'A4'])

    print(u'')
    print(u'=== 破坏 2：给 ralsei 塞回 ①（模拟"回滚第139轮"）===')
    with Mut(os.path.join(CARDS_DIR, 'ralsei.json'), 'M2') as m:
        old = m.before
        # 在最外层 patch 字符串末尾追加，保证 JSON 仍然合法
        d = json.loads(old)
        d['patch'] = (d.get('patch') or u'') + u' ' + LEAD
        m.write(json.dumps(d, ensure_ascii=False, indent=1))
        case(u'M2', u'ralsei 又带 ① → C2(不含①) + C1(38 条) + A4 必须红',
             [u'C1', u'C2'])

    print(u'')
    print(u'=== 破坏 3：把人设那句改成 1~3 句（模拟"规格冲突消失"）===')
    with Mut(os.path.join(PERSONA_DIR, 'asgore.txt'), 'M3') as m:
        m.apply(u'一次开口通常 1~2 句', u'一次开口通常 1~3 句')
        case(u'M3', u'人设改 1~3 → A1(只有 1 种写法) + A2(写的是 1~2) 必须红',
             [u'A1', u'A2'])

    print(u'')
    print(u'=== 破坏 4：把 TOO_LONG 的触发条件从字数改成句数 ===')
    with Mut(COMMON_PY, 'M4') as m:
        m.apply(u'    if len(t) > MAX_CHARS:', u'    if n_sent > 3:')
        case(u'M4', u'触发改为句数 → B1 必须红', [u'B1'])

    print(u'')
    print(u'=== 破坏 5：把 TOO_LONG 提到优先级第 1 位 ===')
    with Mut(COMMON_PY, 'M5') as m:
        m.apply(u"'MARKDOWN', 'AI_SELF', 'SLAVE', 'NOT_CN', 'ACTION_PAREN', 'META',",
                u"'TOO_LONG', 'MARKDOWN', 'AI_SELF', 'SLAVE', 'NOT_CN', "
                u"'ACTION_PAREN', 'META',")
        case(u'M5', u'顺序改了 → B2(第 7 位) 必须红', [u'B2'])

    print(u'')
    print(u'=== 破坏 6：抹掉 common113 里的订正注释 ===')
    with Mut(COMMON_PY, 'M6') as m:
        m.apply(u'第142轮订正', u'第999轮订正')
        case(u'M6', u'注释被抹 → C4 必须红', [u'C4'])

    print(u'')
    print(u'=== 破坏 7：伪造语料结论（把一个人的 over200 改成 0）===')
    with Mut(EV_JSON, 'M7') as m:
        d = json.loads(m.before)
        hit = [r for r in d.get('rows') or []
               if r.get('lead') and r.get('over200', 0) > 0]
        if not hit:
            check(u'M7 证据锚点可用', False, u'没有可伪造的行')
        else:
            hit[0]['over200'] = 0
            m.write(json.dumps(d, ensure_ascii=False, indent=1))
            case(u'M7', u'伪造"带 ① 但不超长" → B4(100%) 必须红', [u'B4'])

    print(u'')
    print(u'=== 收口 ===')
    rc1, fails1, out1 = _run_check()
    n_pass1 = len(re.findall(u'^\\[PASS\\] ', out1, re.M))
    check(u'M8 七处破坏全部还原后回到基线（18 PASS / 0 FAIL）',
          rc1 == 0 and not fails1 and n_pass1 == 18,
          u'PASS=%d FAIL=%d' % (n_pass1, len(fails1)))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
