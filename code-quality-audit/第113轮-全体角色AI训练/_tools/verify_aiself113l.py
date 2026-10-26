# -*- coding: utf-8 -*-
"""点验：产品侧 `npc_persona.training_patch()` 真的读得到新纠正句，且没被缓存/路径坑住。

★ 为什么单独点：改的是 JSON，用的是产品代码。只验 JSON 等于"验了半边"——
  路径拼错的经典症状就是 `training_patch()` 静默返回 `''`（它的 `except` 吞掉一切）。
  所以这里正/负成对：拿到的人必须拿到**完全一致**的文本，没证据的人必须仍是 `''`。
"""
import io
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common113 as C  # noqa: E402
from modules import npc_persona as P  # noqa: E402

fails = []


def ok(desc, cond, detail=''):
    print(('  [PASS] ' if cond else '  [FAIL] ') + desc + ('：%s' % detail if detail else ''))
    if not cond:
        fails.append(desc)


idx = json.load(io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc',
                                     '_training', '_index.json'),
                        encoding='utf-8'))
patches = idx.get('patches') or {}
with_patch = sorted(patches)

print('① 有纠正句的 %d 人，产品侧必须原样读到' % len(with_patch))
for nid in with_patch:
    got = P.training_patch(nid)
    ok('%s 读到纠正句' % nid, got == patches[nid],
       '' if got == patches[nid] else '读回 %r…' % (got or ''))

print('② 负控制：没写过的人必须仍是空串（不许串号/串默认值）')
for nid in ('flowery', 'hy_ace', 'knight'):
    got = P.training_patch(nid)
    ok('%s 无纠正句（空串）' % nid, got == '', repr(got))

print('③ 负控制：不存在的 id 也必须空串（不许抛、不许回默认句）')
try:
    got = P.training_patch('__no_such_npc__')
    ok('未知 id 返回空串', got == '', repr(got))
except Exception as e:                     # noqa: BLE001
    ok('未知 id 返回空串', False, '抛了 %r' % (e,))

print('④ 纠正句不许含禁词词根（否则等于把禁词写进 system）')
_old = '你不承认自己是程序或 AI。有人这么问，就照你的性格当成胡话说回去，别解释技术。'
ok('AI_SELF_PATCH 干净', not C.patch_is_clean(C.AI_SELF_PATCH),
   ','.join(C.patch_is_clean(C.AI_SELF_PATCH)))
ok('正控制：旧句**必须**被判红（证明上一条判据会红）',
   bool(C.patch_is_clean(_old)), ','.join(C.patch_is_clean(_old)))
# ★★ 这一条是**实测打脸**留下的记录：我原以为"旧句含 AI/程序 ⇒ `_AI_RE` 必然命中"，
#   正控制当场证明是错的（旧正则要「我是…」，旧句是「自己**是**…」）。
#   后来把 `_AI_RE` 放宽到裸词，旧句才被抓到 —— 所以这里断言它**现在**会命中，
#   并反过来说明：**只靠"整句正则"是抓不到这种写法的**。
ok('旧句现在会被 `_AI_RE` 命中（裸词已纳入；旧正则抓不到它）',
   C._AI_RE.search(_old) is not None,
   (C._AI_RE.search(_old).group(0) if C._AI_RE.search(_old) else '没命中'))
ok('负控制：不含禁词的普通句不许被命中',
   C._AI_RE.search('今天的风有点凉，你冷不冷？') is None)

print('⑤ 决策落地：**生产线不再产出** AI_SELF 纠正句')
bp = C.build_patch([('AI_SELF', 'x')], [], [])
ok('build_patch 对 AI_SELF 不产出任何句子', bp == '', repr(bp[:40]))
ok('负控制：别的违规码仍然正常产出（证明上一条不是"整个 build_patch 坏了"）',
   C.build_patch([('MARKDOWN', 'x')], [], []) != '')
ok('PATCH_RULES 里没有 AI_SELF', 'AI_SELF' not in C.PATCH_RULES)

print('\n%s：%d 项失败' % ('FAIL' if fails else 'PASS', len(fails)))
sys.exit(1 if fails else 0)
