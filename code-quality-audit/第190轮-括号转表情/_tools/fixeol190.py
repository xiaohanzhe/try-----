# -*- coding: utf-8 -*-
"""第190轮 · 把 7 份人设的行尾按**改前实测的分布**恢复（写盘 / 幂等）。

事故经过
--------
本轮改 `asgore / lancer / ot_kidd / ut_monster_kid / ot_muffet / ot_sans / ut_sans`
七份人设（口癖从配额改为看场景），用的是行内字符串替换工具 —— 它把**整个文件重写成了 LF**。
这与第189轮 §6.2 是同一个坑（当时只有 asgore 一份，用 `fixeol189.py` 单文件修的）。

为什么必须恢复（不是"能跑就行"）
-------------------------------
`core.autocrlf = true`：仓库存 LF、工作区出 CRLF。所以磁盘上"正文 CRLF + 尾块 LF"
是**签出后的正常形态**。改成全 LF 之后：
  · `sha256 == sha256_lf`（正常应当不同），`_personas.json` 的派生字段口径就乱了；
  · 下次任何人 `git checkout` 一份干净工作区，这两个值又会变回不同
    ⇒ 出现"我没动它、它自己变了"的假回滚（第113轮那条老坑的翻版）。

恢复口径（**按改前实测的分布，不按"看着合理"的公式**）
------------------------------------------------------
改前每份文件的 bare-LF 是**连续落在文件尾部**的（拿未改动的 `susie.txt` 验证过：
bare LF 行号 109~117，正好是尾块那一段）。所以重建规则是：
    **前 (n-1-K) 个分隔符 CRLF，最后 K 个 LF**
K 逐份实测（改前 `\n` 数 - `\r\n` 数）：见 `BARE_LF_TAIL`。
★ 不套用 `fixeol189.py` 的 `body + '\\r\\n\\n' + tail` 公式：那份只有 asgore 一份，
  实测 K=9；本轮七份里 K 有 8/9/10 三种，套公式会把 ot_kidd 那一份额外的一个空行抹掉。

★ 独立自证（不是自我印证）：
  ① `payload` 按 LF 归一后必须**逐字节等于**当前磁盘原文（证明只动了换行符）；
  ② 分隔符总数必须等于 `总行数 - 1`（分母闸，防切片错位静默少一行）；
  ③ 写后回读 == payload。

用法
----
    python fixeol190.py            # 只检查
    python fixeol190.py --write    # 修
"""
import io
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PERSONA = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
BACKUP = r'D:\_tmp\eol190'

#: 改前实测的「尾部 bare-LF 分隔符个数」（= 改前 `\n` 总数 - `\r\n` 总数）。
#: 这些数是**量出来的**，不是按公式算的 —— 换文件请重新量，别照抄。
BARE_LF_TAIL = {
    'asgore': 9,
    'lancer': 9,
    'ot_kidd': 10,
    'ut_monster_kid': 10,
    'ot_muffet': 10,
    'ot_sans': 8,
    'ut_sans': 8,
}


def rebuild(raw, k):
    """把全 LF 的 `raw` 重建成「前 CRLF / 尾 k 个 LF」。返回 (payload, n_seps)。"""
    assert b'\r\n' not in raw, '输入不是全 LF，先人工看一遍（可能是别的工具又动过）'
    lines = raw.split(b'\n')
    assert lines and lines[-1] == b'', '文件必须以换行结尾'
    lines = lines[:-1]                     # 最后一个空串是结尾换行造成的
    n_seps = len(lines) - 1 if len(lines) > 1 else 0
    out = bytearray()
    # 最后那一个分隔符（收尾换行）固定是 LF，所以「前 n_seps 个」里只留 k-1 个 bare-LF
    bare_before = max(0, k - 1)
    for i, ln in enumerate(lines):
        out += ln
        if i < n_seps:
            i_sep = i + 1
            out += b'\n' if i_sep > (n_seps - bare_before) else b'\r\n'
    out += b'\n'
    return bytes(out), n_seps


def main():
    do_write = '--write' in sys.argv
    bad = []
    for tid, k in BARE_LF_TAIL.items():
        path = os.path.join(PERSONA, tid + '.txt')
        raw = open(path, 'rb').read()
        if b'\r\n' in raw:
            print('%-16s 已是混合/CRLF 形态（CRLF=%d）——跳过'
                  % (tid, raw.count(b'\r\n')))
            continue
        payload, n_seps = rebuild(raw, k)
        # ① 只动换行符（独立一侧：右边是磁盘原文）
        if payload.replace(b'\r\n', b'\n') != raw:
            bad.append(tid)
            print('%-16s [停手] LF 归一后仍有差异' % tid)
            continue
        # ② 分隔符总数守恒 + 尾部恰好 k 个 bare-LF（分母闸，防切片错位静默少一行）
        if (payload.count(b'\n') != raw.count(b'\n')
                or payload.count(b'\n') - payload.count(b'\r\n') != k):
            bad.append(tid)
            print('%-16s [停手] 分隔符 %d/%d  CRLF=%d（应 %d）'
                  % (tid, payload.count(b'\n'), raw.count(b'\n'),
                     payload.count(b'\r\n'), raw.count(b'\n') - k))
            continue
        print('%-16s %d B  CRLF=%d  bareLF=%d  K=%d（行 %d）'
              % (tid, len(payload), payload.count(b'\r\n'),
                 payload.count(b'\n') - payload.count(b'\r\n'), k, n_seps + 1))
        if not do_write:
            continue
        if not os.path.isdir(BACKUP):
            os.makedirs(BACKUP)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        shutil.copy2(path, os.path.join(BACKUP, '%s_%s.txt' % (tid, stamp)))
        tmp = path + '.tmp'
        with io.open(tmp, 'wb') as fh:
            fh.write(payload)
        os.replace(tmp, path)
        assert open(path, 'rb').read() == payload, '%s 写后回读不一致' % tid
    print('\n异常 %d 份%s' % (len(bad), '' if do_write else '（dry，加 --write 执行）'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
