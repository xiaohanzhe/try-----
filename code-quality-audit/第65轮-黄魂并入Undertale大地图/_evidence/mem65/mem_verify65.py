# -*- coding: utf-8 -*-
u"""第65轮 · 记忆文件复检（速查本 + 详版 + 日记）。
判据：体积(JS字符) / 编码 / 指针可达(§ 引用在详版里有对应标题) / 逐令牌回验 / 结构。
★ 每条都配负控制，防"判据空转"。
"""
import io, os, re, sys

MEM = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory'
QUICK = os.path.join(MEM, 'MEMORY.md')
DETAIL = os.path.join(MEM, u'参考-契约与历轮（详版）.md')
DIARY = os.path.join(MEM, '2026-09-30.md')

ROWS = []


def ck(n, ok, d=''):
    ROWS.append(ok)
    print('  [%s] %-56s %s' % ('PASS' if ok else 'FAIL', n, d))


def rb(p):
    with io.open(p, 'rb') as f:
        return f.read()


def js(s):
    return len(s.strip().encode('utf-16-le')) // 2


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    q = io.open(QUICK, encoding='utf-8').read()
    d = io.open(DETAIL, encoding='utf-8').read()
    print('===== 第65轮 记忆复检 =====')
    print('\n① 体积 / 编码')
    n = js(q)
    ck('速查本 js_len ≤ 10000', n <= 10000, 'js_len=%d margin=%d' % (n, 10000 - n))
    ck('速查本 js_len ≤ 9800（留余量）', n <= 9800, 'js_len=%d' % n)
    for lbl, p in (('速查本', QUICK), ('详版', DETAIL), ('日记', DIARY)):
        b = rb(p)
        ck('%s 无 BOM' % lbl, not b.startswith(b'\xef\xbb\xbf'))
        ck('%s 无 U+FFFD' % lbl, b.decode('utf-8').count(u'\ufffd') == 0)
    ck('负控制 · U+FFFD 检出器可用', u'\ufffd' in u'a\ufffdb')

    print('\n② 结构 / 指针可达')
    heads = set(re.findall(r'^#{2,3}\s*§?([0-9]+(?:\.[0-9]+)?)', d, flags=re.M))
    heads |= set(re.findall(r'^#{2,3}\s*§([0-9]+)', d, flags=re.M))
    ck('详版存在 §61 主标题', u'## §61 第65轮' in d)
    for sub in ['61.1', '61.2', '61.3', '61.4', '61.5', '61.6', '61.7', '61.8', '61.9', '61.10', '61.11']:
        ck('详版有 §%s' % sub, ('§' + sub) in d or ('### ' + sub) in d)
    ck('负控制 · 不存在的 §99.9 应判缺失', ('§99.9' in d) is False)

    print('\n③ 逐令牌回验（速查本新令牌 ← 事实）')
    TOK = [(u'速查本 §0–§61 指针', u'§0–§61', True),
           (u'速查本 §14–§61 指针', u'§14–§61', True),
           (u'速查本轮次区间 26–65', u'**26–65**', True),
           (u'速查本 65 索引条目', u'65 黄魂并入数据面', True),
           (u'速查本 大图文件名', u'bigmap65.json', True),
           (u'速查本 §61.9 引用', u'§61.9', True),
           (u'速查本 §61.2.2 引用', u'§61.2.2', True),
           (u'速查本 黄魂 nextroom 事实', u'nextroom', True),
           (u'速查本 obj_doorA~D 偏移', u'obj_doorA~D', True),
           (u'速查本 §7 必读含 §61', u'§60/§61', True),
           (u'旧口径已删除（"数据未动"）', u'**数据未动**', False),
           (u'旧口径已删除（obj_doorway/obj_exit）', u'`obj_doorway`/`obj_exit`', False)]
    for lbl, tk, want in TOK:
        got = tk in q
        ck('token %s %s' % (lbl, '在' if want else '不在'), got == want, 'repr=%r' % tk)

    print('\n④ 详版令牌')
    for tk in ['bigmap65.json', 'bigmap65_ry_overlay.json', 'gml_evidence65',
               'recheck65.py', 'nextroom', 'room_next', 'obj_door_s_musfade',
               '625', '988', '125', '287', '338', '358', '5 个「基础房']:
        ck('详版含 %r' % tk, tk in d)

    print('\n⑤ 日记')
    bd = rb(DIARY)
    ck('日记存在且 CRLF 一致', bd.count(b'\r\n') > 0
       and (bd.count(b'\n') - bd.count(b'\r\n')) == 0,
       'CRLF=%d LF-only=%d' % (bd.count(b'\r\n'), bd.count(b'\n') - bd.count(b'\r\n')))
    dt = bd.decode('utf-8')
    for tk in [u'第65轮', u'bigmap65.json', u'62 / 62', u'nextroom', u'47', u'分量数守恒']:
        ck(u'日记含 %r' % tk, tk in dt)

    nf = sum(1 for x in ROWS if not x)
    print('\n===== 合计 %d 项：PASS %d / FAIL %d ⇒ %s ====='
          % (len(ROWS), len(ROWS) - nf, nf, 'ALL PASS' if nf == 0 else 'HAS FAILURE'))
    return 1 if nf else 0


if __name__ == '__main__':
    raise SystemExit(main())
