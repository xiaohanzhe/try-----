# -*- coding: utf-8 -*-
"""第141轮 · 破坏性负控制：每条关键判据都必须在被破坏时**变红**。

只看 `check141` 全绿是不够的 —— 全绿也可能是"判据恒真"。
这里对产品源码/证据文件做 6 处定向破坏，每一处都**必须**让**指定**的那条判据报红；
红错了（红的是别的 ID）也算失败：说明判据之间互相顶替，归因不清。

★ 破坏锚点全用"单行片段"，避免 CRLF / LF 混在一起（第140轮 `mutate140` M6 的坑）。
★ 文件读写用 `newline=''` + 按原 EOL 还原，**绝不改行尾**。
★ 每处破坏后 `finally` 还原；结束时用 sha1 核对"确实恢复原样"。
"""
import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
EV_JSON = os.path.join(ROUND, '_evidence', 'sentence_len141b_lang.json')
CHECK = os.path.join(HERE, 'check141.py')
PY = sys.executable

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
    """对某个文件做一处破坏，退出时无条件还原。"""

    def __init__(self, path, label):
        self.path = path
        self.label = label
        self.before = None
        self.sha = None

    def __enter__(self):
        self.before = _read(self.path)
        self.sha = _sha1(self.path)
        return self

    def apply(self, old, new):
        """单行片段替换；返回替换处数（必须恰 1 处）。"""
        n = self.before.count(old)
        if n != 1:
            raise AssertionError(u'%s: 锚点出现 %d 次（应为 1）: %r'
                                 % (self.label, n, old[:60]))
        _write(self.path, self.before.replace(old, new, 1))
        return n

    def apply_eol(self, old_lines, new_lines):
        """多行片段替换（锚点里带 \\n）；按原 EOL 归一后再还原。"""
        crlf = u'\r\n' in self.before
        t = self.before.replace(u'\r\n', u'\n')
        n = t.count(old_lines)
        if n != 1:
            raise AssertionError(u'%s: 多行锚点出现 %d 次（应为 1）' % (self.label, n))
        t = t.replace(old_lines, new_lines, 1)
        if crlf:
            t = t.replace(u'\n', u'\r\n')
        _write(self.path, t)
        return n

    def __exit__(self, *a):
        _write(self.path, self.before)
        assert _sha1(self.path) == self.sha, u'%s: 还原后 sha1 不符！' % self.label
        return False


def case(idx, label, expect):
    """跑一处已生效的破坏，断言 expect 里每个 ID 都红了。"""
    rc, fails, out = _run_check()
    got = sorted(set(fails))
    ok = (rc == 1) and all(e in fails for e in expect)
    print(u'  → check141 退出码 %d · 红了 %d 条：%s' % (rc, len(got), u','.join(got)))
    check(u'%s %s' % (idx, label), ok, u'期望红 %r' % (expect,))
    if not ok:
        print(u'----- 输出尾部 -----')
        print(u'\n'.join(out.strip().splitlines()[-12:]))


def main():
    print(u'=== 基线：不破坏时必须全绿 ===')
    rc0, fails0, out0 = _run_check()
    n_pass = len(re.findall(u'^\\[PASS\\] ', out0, re.M))
    print(u'  退出码 %d · PASS=%d · FAIL=%d' % (rc0, n_pass, len(fails0)))
    check(u'M0 基线全绿（30 PASS / 0 FAIL）', rc0 == 0 and not fails0 and n_pass == 30)
    print(u'')

    print(u'=== 破坏 1：往 `_OOC_RES` 里塞裸 `扮演`（被语料否决的候选）===')
    with Mut(ES_PY, 'M1') as m:
        m.apply(u"re.compile(u'设定.{0,4}扮演')",
                u"re.compile(u'设定.{0,4}扮演'), re.compile(u'扮演')")
        case(u'M1', u'塞裸 `扮演` → B1(只 1 条) + B6(berdly 被误杀) 必须红',
             [u'B1', u'B6'])

    print(u'')
    print(u'=== 破坏 2：把正则换成被否决的 `(不是|并非).{0,6}真实存在` ===')
    with Mut(ES_PY, 'M2') as m:
        m.apply(u"re.compile(u'设定.{0,4}扮演')",
                u"re.compile(u'(不是|并非).{0,6}真实存在')")
        case(u'M2', u'换成 `…真实存在` → B2(换掉了) + B5(ralsei 漏) + B6(alphys/lancer 误杀) 必须红'
             u'；B4 仍绿（ceroba 那条同样含"真实存在"，被新正则接住）',
             [u'B2', u'B5', u'B6'])

    print(u'')
    print(u'=== 破坏 3：拿掉 `_OOC_RES` 的循环（只剩子串表）===')
    with Mut(ES_PY, 'M3') as m:
        m.apply_eol(u"    for r in _OOC_RES:\n        if r.search(text):\n"
                    u"            return True\n", u'')
        case(u'M3', u'删正则循环 → B4/B5(正控制漏掉) + B10(循环缺一) 必须红',
             [u'B4', u'B5', u'B10'])

    print(u'')
    print(u'=== 破坏 4：`_SENTENCE_ENDS` 去掉 `…`（把两套标点合并）===')
    with Mut(ES_PY, 'M4') as m:
        m.apply(u'_SENTENCE_ENDS = u\'\u3002\uff01\uff1f!?\\n\u2026\'',
                u'_SENTENCE_ENDS = u\'\u3002\uff01\uff1f!?\\n\'')
        case(u'M4', u'切点尺去掉省略号 → C2 必须红', [u'C2'])

    print(u'')
    print(u'=== 破坏 5：往 main.py 加一个 `MAX_SENTENCES = 3` 常量 ===')
    with Mut(MAIN_PY, 'M5') as m:
        _write(MAIN_PY, m.before + u'\nMAX_SENTENCES = 3\n')
        case(u'M5', u'加全大写单句闸常量 → C1 必须红', [u'C1'])

    print(u'')
    print(u'=== 破坏 6：把证据里的 en 层 P90 改成 100（伪造"没有污染"）===')
    with Mut(EV_JSON, 'M6') as m:
        t = m.before.replace(u'"p90": 323', u'"p90": 100')
        if t == m.before:
            check(u'M6 证据锚点可用', False, u'"p90": 323 没找到')
        else:
            _write(EV_JSON, t)
            case(u'M6', u'伪造英文层 P90 → A3 必须红', [u'A3'])

    print(u'')
    print(u'=== 收口 ===')
    rc1, fails1, out1 = _run_check()
    n_pass1 = len(re.findall(u'^\\[PASS\\] ', out1, re.M))
    check(u'M7 六处破坏全部还原后回到基线（30 PASS / 0 FAIL）',
          rc1 == 0 and not fails1 and n_pass1 == 30,
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
