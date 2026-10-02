#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第75轮 · check75b 的**鉴别力体检**（篡改 → 判据必须报红 → 逐字节还原）。

为什么必须有这个文件
--------------------
第62~70轮反复栽在同一处：**判据自己恒真/过窄**，产品其实没错，却报绿（或反过来报假红）。
`check75b` 有 58 条判据，其中大量是"照抄原作"这类**结构性**断言 ——
如果不做篡改体检，"判据是不是在真守"根本无从知道。

做法（**用后即还原**）
----------------------
对每个目标文件：① 记 sha256 → ② 打一处语义篡改 → ③ 跑对应判据、**必须报红** →
④ 从内存原样写回 → ⑤ 复核 sha256 与原件一致。任何一步不对，本脚本自己报红。

★ 篡改的是**产品/证据文件**（team_hp.py 与 gml 转储），所以必须严格还原。
★ 与 `tamper75.py` 同源纪律：替换串用 `str` 再 `.encode('utf-8')`
  （直接用 `bytes` 字面量会因转义不命中 —— 第75轮已踩过一次）。
"""

import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
PET = os.path.join(ROOT, 'ralsei_pet')
GML = os.path.join(ROOT, 'code-quality-audit',
                   '第48轮-道具与背包系统', '_evidence', 'gml')
PY = sys.executable
CHECK = os.path.join(HERE, 'check75b.py')

TEAM = os.path.join(PET, 'modules', 'team_hp.py')
HEAL_SPELL = os.path.join(GML, 'gml_GlobalScript_scr_healitemspell.gml')
SAVEPOINT = os.path.join(GML, 'gml_Object_obj_savepoint_Other_10.gml')

OK = 0
BAD = 0


def _sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def _read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def _run_check():
    """跑 check75b，返回 stdout 文本。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([PY, CHECK], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=env)
    return r.stdout.decode('utf-8', 'replace')


def _case(desc, path, old, new, expect_fail):
    """一处篡改：改 → 跑 → 期望 `expect_fail` 出现在输出里 → 还原 → 复核 hash。"""
    global OK, BAD
    before_hash = _sha(path)
    src = _read(path)
    if old not in src:
        print('[BAD ] %s —— 夹具**没命中**（替换串不存在，夹具失效）' % desc)
        BAD += 1
        return
    mutated = src.replace(old, new, 1)
    if mutated == src:
        print('[BAD ] %s —— 替换后无变化（夹具失效）' % desc)
        BAD += 1
        return
    _write(path, mutated)
    try:
        out = _run_check()
        hit = expect_fail in out
        # 还原
        _write(path, src)
        after_hash = _sha(path)
        if after_hash != before_hash:
            print('[BAD ] %s —— **还原失败**（hash 不一致！）' % desc)
            BAD += 1
            return
        # 再跑一次，必须回到全绿（确认还原真的干净）
        back = _run_check()
        restored_green = ('FAIL=0' in back)
        if hit and restored_green:
            print('[ OK ] %s —— 判据报红 ✓  且已逐字节还原 ✓' % desc)
            OK += 1
        else:
            print('[BAD ] %s —— 报红=%s（期望命中 %r）／还原后全绿=%s'
                  % (desc, hit, expect_fail, restored_green))
            BAD += 1
    except Exception as e:
        _write(path, src)
        print('[BAD ] %s —— 异常：%s' % (desc, e))
        BAD += 1


def main():
    print('check75b 鉴别力体检（篡改 → 报红 → 还原）')
    print('=' * 66)

    # ---- 1. 复活量 ceil → 整除（B1b 必须报红）----
    _case('篡改 team_hp 复活量为整除（int 代替 math.ceil）',
          TEAM,
          'return int(math.ceil(m * REVIVE_RATIO))',
          'return int(m * REVIVE_RATIO)',
          '[FAIL] B1b')

    # ---- 2. 治疗封顶 → 不封顶（B2 必须报红）----
    _case('篡改 team_hp heal 不封顶（去掉 clamp）',
          TEAM,
          'after = clamp_hp(before + amt, m)',
          'after = before + amt',
          '[FAIL] B2 治疗封顶')

    # ---- 3. 满血信号 → 静默吞掉（B2d 必须报红）----
    _case('篡改 team_hp 满血时静默返回（full_before 置 False）',
          TEAM,
          '            return HpResult(char_id, before, before, m, 0, True, False)',
          '            return HpResult(char_id, before, before, m, 0, False, False)',
          '[FAIL] B2d')

    # ---- 4. 掉血下钳 → 允许负血（B3 必须报红）----
    _case('篡改 team_hp damage 下钳 0（去掉 clamp）',
          TEAM,
          'after = clamp_hp(before - amt, m)',
          'after = before - amt',
          '[FAIL] B3 掉血下钳')

    # ---- 5. 复活只对死人 → 对活人也生效（B4 必须报红）----
    _case('篡改 team_hp revive 对活人也生效（去掉 before>HP_MIN 守卫）',
          TEAM,
          '        if before > HP_MIN:\n'
          '            return HpResult(char_id, before, before, m, 0, before >= m, False)',
          '        if False:\n'
          '            return HpResult(char_id, before, before, m, 0, before >= m, False)',
          '[FAIL] B4 给活人复活')

    # ---- 6. restore_all 只回没满的 → 全量覆盖（B5c 必须报红）----
    _case('篡改 restore_all 对满血者也报 ok=True',
          TEAM,
          '                out.append(HpResult(c, self._hp[c], self._hp[c], self._max[c],\n'
          '                                    0, True, False))',
          '                out.append(HpResult(c, self._hp[c], self._hp[c], self._max[c],\n'
          '                                    0, True, True))',
          '[FAIL] B5c')

    # ---- 7. from_stats 被兜底污染（B6 必须报红）----
    _case('篡改 from_stats 用 DEFAULT_MAX_HP 覆盖外部数据',
          TEAM,
          "        ids = [c for c in (members or SLOT_ORDER) if c in stats]",
          "        stats = dict((k, dict(DEFAULT_MAX_HP.items())) for k in stats)\n"
          "        ids = [c for c in (members or SLOT_ORDER) if c in stats]",
          '[FAIL] B6 from_stats')

    # ---- 8. 证据侧：把 savepoint 的 `hp[i] < maxhp[i]` 改成 `<=`（A5 必须报红）----
    _case('篡改 GML 转储 savepoint 判据 < → <=',
          SAVEPOINT,
          'if (global.hp[i] < global.maxhp[i])',
          'if (global.hp[i] <= global.maxhp[i])',
          '[FAIL] A5 存档点锚点')

    # ---- 9. 证据侧：把满血信号 specialmessage=3 删掉（A3 必须报红）----
    _case('篡改 GML 转储 healitemspell 删掉 specialmessage = 3',
          HEAL_SPELL,
          '                specialmessage = 3;',
          '                specialmessage = 0;',
          '[FAIL] A3 满血信号锚点')

    # ---- 10. 接线台账说谎（C3b 必须报红）----
    _case('篡改 WIRING wired=True（虚报已接线）',
          TEAM,
          "    'wired': False,",
          "    'wired': True,",
          '[FAIL] C3b')

    print('=' * 66)
    print('tamper75b：OK=%d BAD=%d' % (OK, BAD))
    return 0 if BAD == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
