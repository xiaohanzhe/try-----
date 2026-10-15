# -*- coding: utf-8 -*-
"""
第115轮 · 记忆改动复检（recheck115mem）

铁律：**先补详版、再压速查**；压完必做两件事 ——
① 指针章节真的存在；② **逐令牌回验**（把删掉/挪走的可检索令牌逐个去 速查本 ∪ 详版 里找一次）。

判据（每条都配负控制或正控）：
  P1 速查本 `js_len ≤ 10000`（真口径 = **UTF-16 码元数**，NOT utf-8 字节数）
  P2 详版里 `## §115` 真在（本轮新补的那一节）
  P3 速查本里 `## 21.` 真在，且**指向** §115
  P4 ★ 逐令牌回验：令牌集必须落在「速查本 ∪ 详版」里（**宽式命中**：`§` 可选 / 允许等价写法）
  P5 ★ 负控制：塞一个**故意不存在**的令牌 ⇒ P4 的判据函数必须报红
  P6 ★ 恒真自检：本文件所有 `ck()` 的第二实参不得是字面量 `True`（AST）
  P7 两个记忆文件都在盘、无 BOM、无 U+FFFD
"""
import ast
import io
import os
import sys

MEM = os.path.join(r'c:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c',
                   '.workbuddy', 'memory')
QUICK = os.path.join(MEM, 'MEMORY.md')
FULL = os.path.join(MEM, '参考-契约与历轮（详版）.md')

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


def js_len(t):
    """真口径：JS 字符串长度 = UTF-16 码元数。"""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in t)


def read(p):
    return io.open(p, 'rb').read().decode('utf-8')


# ---- P4 的判据函数（P5 负控制要单独再喂一次）----
# 令牌集合：本轮新增/挪动的可检索锚点。**宽式**：`§` 可选 —— 别重复踩"判据太窄"的误报。
TOKENS = [
    '§115', '§114', 'HTTP_PROXY', 'ProxyHandler', 'DETACHED_PROCESS', '11434', '54715', '10061',
    'ralsei:v4', 'qwen2.5:7b', 'num_ctx 8192', 'prompt_eval_count', '2394', '6136', 'slot print_timing',
    'ralsei_persona', 'PERSONA_FALLBACK', '_OOC_PATTERNS', '_RETRY_NUDGE', 'clean_ai_reply',
    'chat_with_ai', 'AI_REPLY_MAX_CHARS', 'ollama-persona-audit',
    '那边引力', '先把他的事接住', '判法只有一条', '对，豆豆', 'V0', 'V2', 'V5',
    'probe115ab', 'guard115', 'accept115_live', 'accept115_focus', 'mutate115', 'check115',
    'K3', '16000', '4768', '9940', '2/4', '1/4',
    '_K3_MAX_BYTES', 'A4', '_K3_MAX_BYTES', 'check75c', '105 套件',
]


def missing(tokens, haystack):
    return [t for t in tokens if t.replace(u'§', u'') not in haystack.replace(u'§', u'')]


def main():
    say('第115轮 · 记忆改动复检（recheck115mem）')
    q = read(QUICK)
    f = read(FULL)
    both = q + "\n" + f

    say('\n=== P1 · 体积（真口径 = UTF-16 码元数）===')
    jq, jf = js_len(q), js_len(f)
    say('  速查本 js_len = %d / 10000（余量 %d）' % (jq, 10000 - jq))
    say('  详版   js_len = %d' % jf)
    ck('P1 速查本 js_len ≤ 10000', jq <= 10000, 'js_len=%d' % jq)
    ck('P1b 口径自证：js_len == len(encode utf-16-le)//2',
       jq == len(q.encode('utf-16-le')) // 2)

    say('\n=== P2/P3 · 指针章节 ===')
    ck('P2 详版里有 `## §115`', '## §115' in f)
    ck('P3 速查本里有 `## 21.`', '## 21.' in q)
    ck('P3b 速查本 §21 指向 `§115`', '§115' in q.split('## 21.')[1].split('## ')[0])

    say('\n=== P4 · ★ 逐令牌回验（速查本 ∪ 详版）===')
    miss = missing(TOKENS, both)
    say('  令牌 %d 个，缺失 %d 个' % (len(TOKENS), len(miss)))
    ck('P4 全部令牌都能在「速查本 ∪ 详版」里找到', not miss, '缺=%r' % (miss,))

    say('\n=== P5 · ★ 负控制：判据必须真的会报红 ===')
    fake = missing(['绝不存在令牌XYZ123'], both)
    ck('P5 塞一个不存在的令牌 ⇒ 判据函数报红', len(fake) == 1, 'fake=%r' % (fake,))
    ck('P5b 正控制：真实存在的令牌不报红', not missing(['ralsei:v4'], both))

    say('\n=== P6 · 恒真自检（AST）===')
    tree = ast.parse(read(os.path.abspath(__file__)))
    bad = [nd.lineno for nd in ast.walk(tree)
           if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
           and nd.func.id == 'ck' and len(nd.args) >= 2
           and isinstance(nd.args[1], ast.Constant) and nd.args[1].value is True]
    ck('P6 没有 `ck(..., True)` 恒真判据', not bad, '行号=%r' % (bad,))

    say('\n=== P7 · 文件完整性 ===')
    for nm, p in (('速查本', QUICK), ('详版', FULL)):
        raw = io.open(p, 'rb').read()
        t = raw.decode('utf-8')
        ck('P7 %s 在盘、无 BOM、无 U+FFFD' % nm,
           not raw.startswith(b'\xef\xbb\xbf') and '\ufffd' not in t,
           nm)

    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (S['n'], S['f']))
    return 0 if S['f'] == 0 else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _e:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_e,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            ev = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              '_evidence')
            if not os.path.isdir(ev):
                os.makedirs(ev)
            with io.open(os.path.join(ev, 'recheck115mem_out.txt'), 'w',
                         encoding='utf-8', newline='') as fh:
                fh.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
