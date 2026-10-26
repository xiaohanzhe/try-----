# -*- coding: utf-8 -*-
"""全量人读：所有章 × 四种活动，把"模型真正会读到的候选地名字符串"打出来。

★ 为什么要这个脚本：6 个样本一条都看不出问题 —— 第113轮j 的 5 个真错误、
  第113轮k 的 3 个真错误（`车站` 误译 / `系统与演出` 调试房 / `c asgore` 单字母）
  全是**扫全部**扫出来的。只跑单点断言必然漏。
"""
import ast
import io
import json
import logging
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
IDX = os.path.join(PET, 'assets', 'scenes', '_index.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_life as L                                    # noqa: E402

WANT = ('_scene_place_label', '_activity_label', '_activity_chapter', '_activity_places')
_SRC = io.open(MAIN, encoding='utf-8', newline='').read()
_NS = {'npc_life_mod': L, '_log': logging.getLogger('survey_act113k_labels')}
for node in ast.parse(_SRC).body:
    if isinstance(node, ast.ClassDef):
        for fn in node.body:
            if isinstance(fn, ast.FunctionDef) and fn.name in WANT:
                exec(compile(textwrap.dedent(ast.get_source_segment(_SRC, fn)),
                             '<%s>' % fn.name, 'exec'), _NS)

IDXMAP = {}
_id = json.loads(io.open(IDX, encoding='utf-8').read())
for _cid, ch in _id['chapters'].items():
    for _aid, ar in (ch.get('areas') or {}).items():
        for sid, sc in (ar.get('scenes') or {}).items():
            IDXMAP[sid] = (str(ch.get('name') or ''), str(ar.get('name') or ''),
                           str(sc.get('name') or ''), bool(sc.get('name_derived')),
                           str(sc.get('name_raw') or ''))


class Stub(object):
    npc_life_mod = L

    def _scene_label_map(self):
        return IDXMAP

    def _scene_place_label(self, sid, with_chapter=True):
        return _NS['_scene_place_label'](self, sid, with_chapter=with_chapter)

    def _activity_label(self, sid, core, hits):
        return _NS['_activity_label'](self, sid, core, hits)

    def _activity_places(self, kind, chapter):
        return _NS['_activity_places'](self, kind, chapter)


def main():
    st = Stub()
    chapters = sorted({s.split('.')[0] for s in IDXMAP})
    for chap in chapters:
        print('== %s' % chap)
        for kind in L.ACTIVITY_KINDS:
            places = st._activity_places(kind, chap)
            if not places:
                print('   %-4s 0' % kind)
                continue
            print('   %-4s %d  %s' % (kind, len(places),
                                      '、'.join(lbl for _s, lbl in places)))
    print()
    print('--- 汇总 ---')
    tot = {}
    for kind in L.ACTIVITY_KINDS:
        tot[kind] = sum(len(st._activity_places(kind, c)) for c in chapters)
    print('全部章合计（去重后）= %r' % tot)
    return 0


if __name__ == '__main__':
    sys.exit(main())
