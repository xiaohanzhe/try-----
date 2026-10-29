# -*- coding: utf-8 -*-
"""三款可读物**正文**：把 key -> 文本 的多语言表整理成可交付数据。

数据怎么来的（一句话）：`readable_text.csx` 扫全量字节码，找
`Push(String "obj_readable_xxx_N")` 之后 12 条指令内的第一个字符串常量 —— 那就是正文。
实测 UT 里正文放在 **`gml_Script_textdata_en` / `_ja` / `textdata_cn` 三张表**里，
键完全一致（614 / 614 / 614）；`obj_readable_roomX_Alarm_0` 里另有一份 555 键的表。

★ 中文版是**字间带空格**的排版（`我 正 在 ..`），直接拿去渲染会很难看。
  所以给两个字段：`cn` 保留原样（保真）、`cn_tight` 只去掉汉字之间的空格（渲染用）。
  去掉多少有判据守着（`check_readables115 R5`：两者只差空白，别的一个字都不许差）。

用法
----
    python readables115.py
产物
----
    _evidence/readables115.json / .txt
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')

KEYS = ['ut', 'uty', 'outertale']
CJK = u'\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
CJK_PUNCT = u'，。！？、；：）】」』…—'
# 行尾标点里的全角空格也算排版空白
TIGHT_RULES = [
    re.compile(u'(?<=[' + CJK + u'])[ \\u3000]+(?=[' + CJK + u'])'),
    re.compile(u'(?<=[' + CJK + u'])[ \\u3000]+(?=[' + re.escape(CJK_PUNCT) + u'])'),
    re.compile(u'(?<=[（【「『])[ \\u3000]+(?=[' + CJK + u'])'),
]


def lang_of(code):
    if 'textdata_cn' in code:
        return 'cn'
    if 'textdata_ja' in code:
        return 'ja'
    if 'textdata_en' in code:
        return 'en'
    return 'obj'


def tight(s):
    for r in TIGHT_RULES:
        s = r.sub(u'', s)
    return s


def main():
    out, lines = {}, [u'三款可读物正文（key -> 文本）', u'']
    for key in KEYS:
        p = os.path.join(RAW, key, 'readable_text.json')
        d = json.load(io.open(p, encoding='utf-8'))
        table = collections.defaultdict(dict)
        src_of = collections.defaultdict(set)
        conflicts = rejected = 0
        for it in d['items']:
            lg = lang_of(it['code'])
            # ★ 有的条目后面跟的不是正文、而是**下一个键名**（obj_readable_xxx_N）。
            #   实测 outertale 4 处、ut 0 处；不滤掉就会把键名当正文（冲突数会露馅）。
            if it['text'].startswith('obj_readable'):
                rejected += 1
                continue
            cur = table[it['name']]
            if lg in cur and cur[lg] != it['text']:
                conflicts += 1
            cur.setdefault(lg, it['text'])
            src_of[it['name']].add(lg)

        keys_out = {}
        for name, langs in table.items():
            rec = {'en': langs.get('en'), 'ja': langs.get('ja'), 'cn': langs.get('cn'),
                   'obj_table': langs.get('obj'), 'src': sorted(src_of[name])}
            if rec['cn']:
                rec['cn_tight'] = tight(rec['cn'])
            keys_out[name] = rec

        per_lang = collections.Counter()
        for name, rec in keys_out.items():
            for lg in ('en', 'ja', 'cn', 'obj_table'):
                if rec.get(lg):
                    per_lang[lg] += 1

        markers = collections.Counter()
        for name, rec in keys_out.items():
            s = rec.get('en') or ''
            for m in (u'^1', u'^2', u'%', u'&', u'/'):
                markers[m] += s.count(m)

        out[key] = {
            'source': 'raw/%s/readable_text.json（readable_text.csx 导出）' % key,
            'n_named': d['n_named'],
            'n_unmatched': d['n_unmatched'],
            'n_keys': len(keys_out),
            'n_by_lang': dict(per_lang),
            'n_conflicts': conflicts,
            'n_rejected_nametext': rejected,
            'markers_en': dict(markers),
            'keys': keys_out,
        }
        lines.append(u'[%s] 名字 %d / 配上正文 %d / 没配上 %d => 不同 key %d'
                     % (key, d['n_named'], d['n_items'], d['n_unmatched'], len(keys_out)))
        lines.append(u'      按语言：%s；同键冲突 %d；剔掉"后面跟的是下一个键名" %d 条'
                     % (u' · '.join(u'%s %d' % (k, v) for k, v in sorted(per_lang.items())),
                        conflicts, rejected))
        if markers:
            lines.append(u'      标记出现次数（en）：%s'
                         % u' · '.join(u'%s %d' % (k, v) for k, v in markers.most_common()))
        samples = [(n, r) for n, r in keys_out.items() if r.get('cn')][:3]
        for n, r in samples:
            lines.append(u'      %s' % n)
            lines.append(u'        en: %s' % (r.get('en') or u'')[:78])
            lines.append(u'        cn: %s' % r['cn_tight'][:78])
        lines.append(u'')

    txt = u'\n'.join(lines) + u'\n'
    with io.open(os.path.join(EV, 'readables115.json'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
        f.write(u'\n')
    with io.open(os.path.join(EV, 'readables115.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)
    sys.stdout.write(txt)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
