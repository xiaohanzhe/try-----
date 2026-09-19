# -*- coding: utf-8 -*-
"""第二十二轮 · 鉴别力体检：M 组 + A12c 的每条锁，**破坏后必须变红**。

为什么要单独做这一步（本项目铁律）：
  "回归锁必须有鉴别力（两侧同值＝没测）"，而且**恒真判据比不写还危险**。
  本组新增的 M1/M2/C17 尤其危险 —— 它们全是"阈值比较"，
  一旦把比较写反（`>` 写成 `>=` 之类）或比较对象取错，就会**永远绿**。
  所以每条锁都必须配一个**专属破坏场景**，跑完确认它确实变红。

做法：把被测文件复制到临时目录 → 施加定点破坏 → 跑套件 → 看**目标锁是否 FAIL**。
      全部通过则打印 PASS，任一"破坏了还不红"则打印 NOT-DISCRIMINATING。
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
PY = r'C:\Python311\python.exe'

# ⚠️ 这三个全局**必须在 `run_suite_against` 之前定义** ——
#    它俩被函数体引用。第一版写在函数后面，于是函数里读 `SUITE` 抛 NameError，
#    而那个异常被 `check` 的调用链吞掉，表现为"M5 破坏了也不红"（假结论，
#    差点让我把一条**本来有鉴别力**的锁删掉/改写）。定义顺序在 Python 里是硬约束。
MAIN = io.open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
PERSONA = io.open(os.path.join(PET, 'assets', 'ralsei_persona.md'),
                  encoding='utf-8').read()
SUITE = io.open(os.path.join(HERE, 'verify_persona_chat.py'),
                encoding='utf-8').read()
assert 'LONG_IN' in SUITE, '套件里找不到 LONG_IN —— 下面的 M5 体检会失去意义'


def run_suite_against(main_src=None, persona_src=None, suite_src=None):
    """把（可选的）破坏版文件放进临时验收目录，跑套件，返回 (rc, 输出)。"""
    tmp = tempfile.mkdtemp(prefix='disc_')
    try:
        # 复制整个仓库里套件需要的最小结构：ralsei_pet + audit 脚本
        dst_pet = os.path.join(tmp, 'ralsei_pet')
        shutil.copytree(PET, dst_pet,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        dst_audit = os.path.join(tmp, 'code-quality-audit', '人味改造-2026-09-18')
        os.makedirs(dst_audit)
        for f in ('verify_persona_chat.py',):
            # ⚠️ 三元方向的坑（踩过一次）：条件为真时要写 **`suite_src`（破坏版）**，
            #    而不是 `SUITE`（原版）。第一版写成 `SUITE if ... else 原文件`，
            #    于是"传了破坏版 → 写进去的却是原版" → M5 怎么都不红，
            #    看起来像"这条锁没鉴别力"，实为**夹具把破坏吃掉了**。
            #    体检脚本自己必须先证明"破坏真的落到了被测文件上"。
            src = suite_src if (f == 'verify_persona_chat.py'
                                and suite_src is not None) else io.open(
                os.path.join(HERE, f), encoding='utf-8').read()
            assert src, '写入的套件内容为空'
            if suite_src is not None and f == 'verify_persona_chat.py':
                assert src == suite_src, '破坏版没被真正写入（夹具 bug）'
            io.open(os.path.join(dst_audit, f), 'w', encoding='utf-8').write(src)

        if main_src is not None:
            io.open(os.path.join(dst_pet, 'src', 'main.py'), 'w',
                    encoding='utf-8').write(main_src)
        if persona_src is not None:
            io.open(os.path.join(dst_pet, 'assets', 'ralsei_persona.md'), 'w',
                    encoding='utf-8').write(persona_src)

        p = subprocess.run([PY, os.path.join(dst_audit, 'verify_persona_chat.py')],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=300, cwd=tmp)
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def failed_locks(out):
    return set(re.findall(r'^\[FAIL\] (\S+)', out, re.M))


results = []


def check(tag, target, main_src=None, persona_src=None, suite_src=None):
    rc, out = run_suite_against(main_src, persona_src, suite_src)
    got = failed_locks(out)
    hit = any(g.startswith(target) for g in got)
    results.append((tag, target, hit, sorted(got)[:6]))
    print('%-6s %-52s -> %s' % (' 红OK' if hit else ' 没红!', tag,
                                ('命中 %s' % target) if hit else
                                ('只红了 %r' % (sorted(got)[:6],))))


# ---- 基线（不破坏）：应当全绿 ----
rc, out = run_suite_against()
print('基线（未破坏）rc=%d  FAIL 数=%d' % (rc, len(failed_locks(out))))
print('-' * 78)

# ---- M1 破坏：把上限改回旧的 150（低于实测常态 214）----
check('M1 上限改回 150',
      'M1',
      main_src=MAIN.replace('AI_REPLY_MAX_CHARS = 220',
                            'AI_REPLY_MAX_CHARS = 150', 1))

# ---- M2 破坏：把上限改成 400（高于物理上限 348，闸门形同虚设）----
check('M2 上限调到 400（超出物理上限）',
      'M2',
      main_src=MAIN.replace('AI_REPLY_MAX_CHARS = 220',
                            'AI_REPLY_MAX_CHARS = 400', 1))

# ---- M2 破坏 二：阈值贴地（60 字，远低于 50% 下限）----
check('M2 上限压到 60（低于 50% 下限）',
      'M2',
      main_src=MAIN.replace('AI_REPLY_MAX_CHARS = 220',
                            'AI_REPLY_MAX_CHARS = 60', 1))

# ---- M3 破坏：把上限设成 99999 → "不设防"（跑飞也不拦）----
check('M3 上限设成 99999（不设防）',
      'M3',
      main_src=MAIN.replace('AI_REPLY_MAX_CHARS = 220',
                            'AI_REPLY_MAX_CHARS = 99999', 1))

# ---- M5 破坏：把 C17 的输入改短 → C17 退化成"输出==输入"的恒真断言 ----
# ⚠️ 第一次写这条时踩了坑：我传的是 main_src=MAIN（**未改动**），
#    那根本没有破坏任何东西，于是"M5 没红"—— 差点误判成"M5 没鉴别力"。
#    这正是本文件要防的同型错误：**破坏动作本身必须是真的破坏**。
_suite_short = SUITE.replace(
    "LONG_IN = '唔……' + '这是一段很长的独白，用来测试超长截断。' * 12",
    "LONG_IN = '唔……很短的一句。'")
assert _suite_short != SUITE, 'M5 的破坏没生效：套件里换不动 LONG_IN 的定义'
check('M5 C17 输入被改短（C17 将恒真）',
      'M5', main_src=MAIN, suite_src=_suite_short)

# ---- A12c 破坏：把篇幅约束从规则区整段搬到碎片区**之后** ----
# 判据是"约束必须在碎片之前"。所以破坏 = 把规则区那份删掉、在碎片区后面补一份。
# ⚠️ 踩坑记录：第一版只删了「我怎么说」里那一处，但「我知道的世界」节里
#    还有一处 `都别一口气倒完`（variant "一次只讲一小截"）—— 锚命中原文，
#    断言照样绿。**破坏必须把锚清干净**，否则测的是"还有没有别处留着"。
_A12C_PARA = ('要说"那边"的事、或者我自己的事，也别一口气倒完 —— 挑最想说的那一两处讲，\n'
              '剩下的留到下次。越是熟的事越容易越说越多，最后变成在念一段说明。\n')
assert _A12C_PARA in PERSONA, 'A12c 破坏锚找不到（persona 被改过？）'
_p_bad = PERSONA.replace(_A12C_PARA, '')
_p_bad = _p_bad.replace('别一口气倒完', '别讲太久')      # 清干净其余出现，防假绿
_p_bad = _p_bad + '\n要说"那边"的事，也别一口气倒完。\n'
assert '都别一口气倒完' not in _p_bad, 'A12c 破坏没清干净锚'
check('A12c 篇幅约束被移到碎片区之后',
      'A12c', main_src=MAIN, persona_src=_p_bad)

# ---- A12c 破坏 二：整条删掉 ----
check('A12c 篇幅约束整条删除',
      'A12c',
      main_src=MAIN, persona_src=PERSONA.replace('别一口气倒完', '别说太久'))

print('-' * 78)
bad = [r for r in results if not r[2]]
print('鉴别力体检：%d/%d 条锁"一破坏就变红"' % (len(results) - len(bad), len(results)))
if bad:
    print('以下锁**没有鉴别力**（破坏了也不红，等于没测）：')
    for tag, tgt, _h, got in bad:
        print('  - %s（目标 %s，实际红了 %r）' % (tag, tgt, got))
    sys.exit(1)
print('全部通过。')
