# -*- coding: utf-8 -*-
"""第196轮 · 变异测试：`check196` 的判据**真的会红**吗。

规矩（本项目第85/129/191轮反复钉的）
------------------------------------
· 每条变异必须让**红数 > 0 且 < 38** —— 只红一两条说明判据太窄，
  红一大片说明打断的是别处（不是被测性质）。
· **必须有一条无害变异红 0**（改注释）—— 否则"红"可能只是文件被动过。
· 每个文件整字节还原并核 sha1（**不许** `replace(old, new, 1)` 这种锚点松的写法）。
· 双跑幂等：跑两遍结果一致。
"""
from __future__ import print_function

import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
CHECK = os.path.join(HERE, 'check196.py')
PY = sys.executable

TOTAL = 38

MUTATIONS = [
    # (标签, 相对 PET 的路径, 原文本, 变异文本, 说明)
    ('M1 表情表里去掉 laugh（回到"死键"状态）',
     'modules/dialogue_ui.py',
     "        'laugh': 'laugh',\n",
     "",
     'D7 必须红'),

    ('M2 恢复 `if char_id: return False`（把 NPC 关在门外）',
     'src/main.py',
     "        if char_id:\n            return self._play_npc_expression_anim(emotion, char_id)\n",
     "        if char_id:\n            return False\n",
     'D2 必须红'),

    ('M3 cry 不再退到 sad（NPC 会去找根本不存在的 cry 素材）',
     'modules/npc_body_render.py',
     "    'cry': 'sad',",
     "    'cry': 'cry',",
     'B2 必须红'),

    ('M4 一次性动画永远不出图（状态写了但屏幕不变）',
     'modules/npc_body_render.py',
     "        st = self._oneshot.get(npc_id)\n        if st is None:\n            return None\n",
     "        st = self._oneshot.get(npc_id)\n        if st is None:\n            return None\n        return None\n",
     'C3/C5 必须红'),

    ('M5 play_once 不真的开演（只回 True）',
     'modules/npc_body_render.py',
     "        self._oneshot[npc_id] = {\n            'emo': cls,\n            'start': int(now_ms),\n            'end': int(now_ms) + n * ANIM_FRAME_MS + hold,\n        }\n",
     "",
     'C3/C4 必须红'),

    ('M6 演完不清状态（人永远卡在表情上）',
     'modules/npc_body_render.py',
     "        if now_ms >= st['end']:\n            self._oneshot.pop(npc_id, None)\n            return None\n",
     "        if now_ms >= st['end']:\n            return None\n",
     'C6 必须红'),

    ('M7 NPC 分支不查渲染层（去调一个不存在的对象）',
     'src/main.py',
     "            layer = self.__dict__.get('_npc_body_layer')\n",
     "            layer = self.__dict__.get('_npc_body_layer_nope')\n",
     'C/D 段必须红（`_play_npc_expression_anim` 永远 False）'),

    ('M8 无害变异：只改注释一个字',
     'modules/npc_body_render.py',
     "#: 表情动画清单（第196轮）。",
     "#: 表情动画清单（第196轮）。 ",
     '必须红 0'),
]


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(65536), b''):
            h.update(c)
    return h.hexdigest()


def run_check():
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    p = subprocess.Popen([PY, CHECK], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, cwd=HERE, env=env)
    out = p.communicate()[0].decode('utf-8', 'replace')
    m = re.search(r'PASS=(\d+) FAIL=(\d+)', out)
    if not m:
        return None, None, out
    return int(m.group(1)), int(m.group(2)), out


def main():
    print('=' * 78)
    print('第196轮变异测试')
    print('=' * 78)
    p0, f0, out0 = run_check()
    if p0 is None:
        print('[FAIL] 基线跑不起来：\n%s' % out0[-2000:])
        return 2
    print('基线：PASS=%d FAIL=%d' % (p0, f0))
    if f0 != 0:
        print('[FAIL] 基线本身就红，先修再变异')
        return 2
    if p0 + f0 != TOTAL:
        print('[FAIL] 基线条数 %d != 声明 %d' % (p0 + f0, TOTAL))
        return 2

    ok = 0
    for label, rel, old, new, expect in MUTATIONS:
        path = os.path.join(PET, rel.replace('/', os.sep))
        raw = io.open(path, 'rb').read()
        before = sha1(path)
        try:
            text = raw.decode('utf-8')
        except Exception as e:
            print('[FAIL] %-46s 读不出源码：%s' % (label, e))
            continue
        # ★★★ 锚点必须按**文件自己的换行符**组装：本项目要求保持原 EOL，
        #   源码是 CRLF。第196轮第一版直接写 `\n`，M1/M2/M7 全部"锚点出现 0 次"
        #   —— 不是变异没意义，是锚点根本没对上（假红）。
        nl = '\r\n' if b'\r\n' in raw else '\n'
        old = old.replace('\n', nl)
        new = new.replace('\n', nl)
        n = text.count(old)
        if n != 1:
            print('[FAIL] %-46s 锚点出现 %d 次（必须恰好 1 次）' % (label, n))
            continue
        io.open(path, 'wb').write(text.replace(old, new).encode('utf-8'))
        try:
            p, f, out = run_check()
        finally:
            io.open(path, 'wb').write(raw)
        if sha1(path) != before:
            print('[FAIL] %-46s 还原后 sha1 不一致（文件已脏）' % label)
            return 3
        if p is None:
            print('[FAIL] %-46s 跑崩了' % label)
            continue
        red = f
        good = (red == 0) if ('红 0' in expect) else (0 < red < TOTAL)
        print('[%s] %-46s 红 %d / %d   (%s)'
              % ('PASS' if good else 'FAIL', label, red, TOTAL, expect))
        if good:
            ok += 1

    print('\n变异 %d / %d 符合预期' % (ok, len(MUTATIONS)))
    return 0 if ok == len(MUTATIONS) else 1


if __name__ == '__main__':
    sys.exit(main())
