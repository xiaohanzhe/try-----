# -*- coding: utf-8 -*-
"""第143轮 · 破坏性负控制（`mutate143.py`）：把改动拆干净，`check143` 必须报红。

## 为什么要做

"判据通过"不等于"判据能抓" —— 第85/124/136 轮的教训都在这。所以对每一个改动点
做一次**定点破坏**，只破坏一处、跑一次 `check143`、看**指定的那条判据**是否红，
然后从字节备份还原并用 sha1 核对。

## 七个破坏（每个都指定"应该谁红"）

| # | 破坏 | 应该红 |
|---|---|---|
| M1 | `.` 那行改回中文句号（`t.rfind('。', …)`） | `B3`（`. 不参与`）+ `C2`（硬截回到 61） |
| M2 | 删掉小数点守卫的 `while` 回退 | `B5`（守卫不在）+ `C5`（切在 `3.` 后） |
| M3 | 把 `…` 塞进 `for sep` 元组 | `B4`（刻意不含 `…`） |
| M4 | 事件链 `_SENTENCE_ENDS` 去掉 `…` | `B6` |
| M5 | 删掉注释里的「第143轮」 | `D1` |
| M6 | 段里再复制一份 `for sep in (...)` | `B2`（恰好 1 处） |
| M7 | 删掉 `if _dot > cut: cut = _dot` 两行 | `B3` + `C2` |

## 判据

* 每个破坏后：**指定的那条**必须出现在 `[FAIL]` 列表里；
* 每个破坏后：`PASS+FAIL` 总数不许变成 0（防止"脚本直接崩了就当成红了"）；
* 还原后：sha1 必须与备份**逐字节**相同，且 `check143` 回到 0 FAIL。
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
ES = os.path.join(PET, 'modules', 'event_speech.py')
CHECK = os.path.join(HERE, 'check143.py')
PY = sys.executable

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=u''):
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
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def _run_check():
    r = subprocess.run([PY, CHECK], cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    fails = []
    for ln in out.split(u'\n'):
        if ln.startswith(u'[FAIL]'):
            fails.append(ln[6:].strip())
    tot = out.count(u'[PASS]') + out.count(u'[FAIL]')
    return fails, tot, out


def _mutate(tag, path, old, new, expect):
    print(u'')
    print(u'--- %s ---' % tag)
    bak = path + u'.bak143'
    shutil.copy2(path, bak)
    sha0 = _sha1(path)
    src = _read(path)
    # ★ 第143轮踩到：`main.py` 是 **CRLF**，多行夹具按 `\n` 写就一处都匹配不上
    #   （M2/M7 首跑就是这样"夹具 0 处"）。这里两种换行都试，并打印命中的是哪种 ——
    #   静默回退会让"换了换行也照样过"这件事不可见。
    eol = u'\n'
    if src.count(old) != 1:
        alt = old.replace(u'\n', u'\r\n')
        if src.count(alt) == 1:
            old, new, eol = alt, new.replace(u'\n', u'\r\n'), u'\r\n'
    if src.count(old) != 1:
        check(u'%s 夹具：目标片段在源码里恰好 1 处' % tag, False,
              u'实际 %d 处' % src.count(old))
        os.remove(bak)
        return
    check(u'%s 夹具：目标片段在源码里恰好 1 处（换行=%s）'
          % (tag, u'CRLF' if eol == u'\r\n' else u'LF'), True)
    _write(path, src.replace(old, new, 1))
    fails, tot, out = _run_check()
    check(u'%s 破坏后 `check143` 确实跑了（PASS+FAIL > 0）' % tag, tot > 0,
          u'条数=%d' % tot)
    hit = [e for e in expect if any(e in f for f in fails)]
    miss = [e for e in expect if not any(e in f for f in fails)]
    check(u'%s 指定的判据全部报红（%s）' % (tag, u' / '.join(expect)),
          not miss, u'没红：%s' % (u', '.join(miss) or u'无'))
    print(u'    破坏后 FAIL：%s' % (u' | '.join(fails) or u'（无）'))
    _write(path, _read(bak))
    os.remove(bak)
    check(u'%s 还原后 sha1 与备份逐字节相同' % tag, _sha1(path) == sha0)


def main():
    print(u'=== 第143轮破坏性负控制 ===')

    _mutate(u'M1 把 `.` 改回中文句号', MAIN,
            u"                _dot = t.rfind('.', 0, max_chars)",
            u"                _dot = t.rfind('\u3002', 0, max_chars)",
            [u'B3', u'C2'])
    _mutate(u'M2 删掉小数点守卫（`while` 回退）', MAIN,
            u"                while _dot > 0 and _dot + 1 < len(t) and t[_dot + 1].isdigit():\n"
            u"                    _dot = t.rfind('.', 0, _dot)\n",
            u'',
            [u'B5', u'C5'])
    _mutate(u'M3 把 `…` 塞进切点元组', MAIN,
            u"                for sep in ('\u3002', '\uff01', '\uff1f', '!', '?', '\\n'):",
            u"                for sep in ('\u3002', '\uff01', '\uff1f', '!', '?', '\\n', '\u2026'):",
            [u'B4'])
    _mutate(u'M4 事件链 `_SENTENCE_ENDS` 去掉 `…`', ES,
            u"_SENTENCE_ENDS = u'\u3002\uff01\uff1f!?\\n\u2026'",
            u"_SENTENCE_ENDS = u'\u3002\uff01\uff1f!?\\n'",
            [u'B6'])
    _mutate(u'M5 删掉注释里的「第143轮」', MAIN,
            u'\u2605\u2605\u2605 \u7b2c143\u8f6e\uff1a\u5207\u70b9\u96c6\u8865 ASCII',
            u'\u2605\u2605\u2605 \u5207\u70b9\u96c6\u8865 ASCII',
            [u'D1'])
    _mutate(u'M6 段里再复制一份 `for sep in (...)`', MAIN,
            u"                for sep in ('\u3002', '\uff01', '\uff1f', '!', '?', '\\n'):",
            u"                for sep in ('\u3002', '\uff01', '\uff1f', '!', '?', '\\n'):\n"
            u"                    pass\n"
            u"                for sep in ('\u3002', '\uff01', '\uff1f', '!', '?', '\\n'):",
            [u'B2'])
    _mutate(u'M7 删掉 `if _dot > cut` 两行（算了但不用）', MAIN,
            u"                if _dot > cut:\n                    cut = _dot\n",
            u'',
            [u'B3', u'C2'])

    print(u'')
    print(u'=== 收口 ===')
    fails, tot, out = _run_check()
    check(u'全部还原后 `check143` 回到 0 FAIL', not fails,
          u'FAIL %d 条' % len(fails))
    check(u'全量可跑通（PASS+FAIL > 0）', tot > 0, u'条数=%d' % tot)

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
