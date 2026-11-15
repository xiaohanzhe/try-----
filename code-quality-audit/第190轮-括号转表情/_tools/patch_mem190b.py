# -*- coding: utf-8 -*-
u"""第190轮 · 速查本补丁（「表情按原样」+ 两条判据教训）。

★★ 两条硬闸（`recheck95mem.py` 的 E1 与 A1）
------------------------------------------
  E1  速查本相对 HEAD 必须**净减或持平**（LF 归一后比）
  A1  按**含 CRLF 的原始字符数**判上限 10000
⇒ 每轮只能**等量替换**：要么压掉等长旧文字，要么别写。

★★★ 为什么"先算后写"
------------------
第一版（第190轮上一半）是"先写后打印体积"，写完才发现 10268 超限，只能回滚。
这里改成：全部替换在内存里做完 → 算 LF 体积和原始体积 → 任一不过关就 return，
**一个字节都不落盘**。

★ 二进制读写，只做字节级替换 ⇒ 不碰 EOL（上一轮用 `newline=''` 把 69 个 CRLF
  顺手全变 LF 过）。

用法：python patch_mem190b.py [--write]
    不带 --write = 只算不写（dry）。
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')

LIMIT_LF = 9862       # HEAD 的 LF 体积（E1 基准，不许变多）
LIMIT_RAW = 10000     # A1 硬上限（含 CRLF）

# ── 替换清单：(说明, old, new) ───────────────────────────────────
# 每条都必须**恰好命中一次**（count==1），否则报错不写 —— 中文长串手改最容易
# 撞上"锚点不匹配"却以为改成功了。
EDITS = [
    # ① 插入本轮新条目（放在"护栏两刀"之前，同一小节内）
    (u'插入 190 条',
     u'- ★★★ **188/189 护栏两刀（§190/§192）**',
     u'- ★★★ **190 表情按原样**：`assets/faces/` 190 图/29 id，**零像素改**；'
     u'黄魂**三套底**（黑底 79／黑剪影 21／**纯白 64⇒浅底看不见**）⇒须深底板。'
     u'★★ 闸② `out is im`＝**恒假**；OneShot 名退化却 ①③④ 全绿⇒加闸⑤。'
     u'\r\n- ★★★ **188/189 护栏两刀（§190/§192）**'),

    # ② 压 164 R1（已裁定、已落地，细节在详版）
    (u'压 164 R1',
     u'**164 R1 🟢**：分段跳跃（`_try_segment`）；**D2 🟢撤销**（`z` 是绘制偏移非封顶·§164.7）。',
     u'**164 R1 🟢**：分段跳跃；**D2 撤销**（`z` 非封顶·§164.7）。'),

    # ③ 压 164 R2（"抽板/挪板/甩飞/空中落空"四个词合成"抽板/挪板/甩飞/落空"）
    (u'压 164 R2',
     u'**客观**（抽板/挪板/甩飞/空中落空）⇒如实掉；够不着⇒**不去＋求助**。'
     u'｜**165 更正**：`_base`=**242.4**<320 ⇒ 助跑上限**生效**，"惰性"作废。',
     u'**客观**（抽板/挪板/甩飞/落空）⇒如实掉；够不着⇒**不去＋求助**。'
     u'｜**165 更正**：`_base`=**242.4**<320 ⇒ 助跑上限**生效**。'),

    # ④ 压口径澄清（"动记忆门槛"→"门槛"，"逐令牌回验"→"回验"）
    (u'压口径 81/96',
     u'**★★★ 口径澄清（81/96）**：「记忆不要随便修改」＝**角色记忆**（`data_store`）'
     u'非助手记忆⇒**助手记忆该记就记**；动记忆门槛：'
     u'**实证超限/被要求＋先补详版＋逐令牌回验＋守恒**；★★ **`check95 A2` 硬闸**（≤10000）。',
     u'**★★★ 口径（81/96）**：「记忆不要随便修改」＝**角色记忆**非助手记忆'
     u'⇒助手记忆该记就记；门槛：超限/被要求＋先补详版＋回验＋守恒；★★ `check95 A2` 硬闸（≤10000）。'),

    # ⑤ 压 174（去掉反引号与"不按…去重"的冗余介词）
    (u'压 174',
     u'★★★ **174（§176）变体补 51**：`Horz 42`／`Vert 9`（仅 ch5）；`Modespecific` 零实例⇒不补。'
     u'★★★ **按实例落边、不按 (源,目标) 去重**（吞 **9 扇**⇒走错房）；可达不变。',
     u'★★★ **174（§176）变体补 51**：Horz 42／Vert 9（仅 ch5）；`Modespecific` 零实例不补。'
     u'★★★ **按实例落边不去重**（吞 9 扇）；可达不变。'),

    # ⑥ 压 176（"删 172 那 42 条误标边"的因果已由前文交代）
    (u'压 176',
     u'★★★ **176（§178）删 172 那 42 条误标边**：变体＋`when_src` 相等⇒从未消费＋与 174 全重合。'
     u'2,810→**2,768**。★★ **老锁改法＝引账不调数**。',
     u'★★★ **176（§178）删 42 条误标边**：从未消费＋与 174 全重合。'
     u'2,810→**2,768**。★★ **改老锁＝引账不调数**。'),

    # ⑦ 压 183
    (u'压 183',
     u'★★★ **183（§185）删 7122 边**：2,831→**2,830**（原作 1/50 分支，182 已承租）。'
     u'★★★ `match()` **零差异**。**老锁引账**；`moss` 见 184。',
     u'★★★ **183（§185）删 7122 边**：2,831→2,830（1/50 分支 182 已承租）。'
     u'★★★ `match()` **零差异**。`moss` 见 184。'),

    # ⑧ 压 186
    (u'压 186',
     u'★★ 两类根因＝**无出口物件**／**条件表达不了**；★★★ `when_prev` **缺席即不匹配**'
     u'⇒兜底另立无它的规则＋priority **升序**。',
     u'★★ 根因＝无出口物件／条件表达不了；★★★ `when_prev` **缺席即不匹配**'
     u'⇒兜底另立规则＋priority **升序**。'),

    # ⑨ 压 178（"会静默插最底"→"⇒静默插最底"）
    (u'压 178',
     u'★ **`HWND_TOP==0` 假值**会静默插最底。',
     u'★ **`HWND_TOP==0` 假值**⇒静默插最底。'),

    # ⑩ 压连通图那条
    (u'压 117 连通图',
     u'★★★「可信优先」被推翻⇒可信层＝锚点/校验，禁裁剪。'
     u'★★ 入口＝`room_area1` 非 `room_start`；outertale 只按 `original_room_id`；UTY 禁改 `KINDS`。',
     u'★★★「可信优先」被推翻⇒可信层＝锚点/校验·禁裁剪。'
     u'★★ 入口＝`room_area1` 非 `room_start`；outertale 按 `original_room_id`；UTY 禁改 `KINDS`。'),

    # ⑪ 压 181（去掉加粗，数字不变）
    (u'压 181',
     u'★★★ **181（§183）补 63 条**（2,768→**2,831**）：',
     u'★★★ **181（§183）补 63 条**（2,768→2,831）：'),

    # ⑫ 压 179（去掉引号）
    (u'压 179',
     u'站窗口楼板⇒**无条件**插它之前；Y 只对"站桌面"生效。',
     u'站窗口楼板⇒**无条件**插它之前；Y 只对站桌面生效。'),

    # ⑬ 压 170（"⇒插 `_pick_by_pos`" 的"插"字多余）
    (u'压 170',
     u'分流⇒插 `_pick_by_pos`（候选≥2＋有坐标＋**命中1条**）',
     u'分流⇒`_pick_by_pos`（候选≥2＋有坐标＋**命中1条**）'),
]


def lf_len(s):
    return len(s.replace(u'\r\n', u'\n'))


def head_text():
    """取 HEAD 版本的速查本（E1 的基准必须来自 git，不是我记的数）。"""
    try:
        b = subprocess.check_output(
            ['git', '-c', 'core.quotepath=false', 'show',
             'HEAD:.workbuddy/memory/MEMORY.md'], cwd=REPO)
        return b.decode('utf-8', 'replace')
    except Exception as e:  # noqa: BLE001
        print(u'[警告] 取 HEAD 失败（%s），E1 用内置基准 %d' % (type(e).__name__, LIMIT_LF))
        return None


def main():
    write = '--write' in sys.argv[1:]
    raw = io.open(MEM, 'rb').read()
    s = raw.decode('utf-8')
    lf0, raw0 = lf_len(s), len(s)
    print(u'[当前] LF %d / 原始(含CRLF) %d / 字节 %d / CRLF %d'
          % (lf0, raw0, len(raw), s.count(u'\r\n')))

    cur = s
    bad = []
    for tag, old, new in EDITS:
        n = cur.count(old)
        if n != 1:
            bad.append((tag, n))
            print(u'  [锚点] %-14s 命中 %d 次 %s' % (tag, n, u'<-- 必须恰好 1 次' if n != 1 else u''))
            continue
        d = lf_len(new) - lf_len(old)
        cur = cur.replace(old, new)
        print(u'  [改] %-14s ΔLF %+d' % (tag, d))

    if bad:
        print(u'[停手] %d 条锚点不唯一/未命中 ⇒ 一个字节都不写' % len(bad))
        return 3

    lf1, raw1 = lf_len(cur), len(cur)
    print(u'')
    print(u'[预计] LF %d → %d  (Δ%+d)' % (lf0, lf1, lf1 - lf0))
    print(u'[预计] 原始 %d → %d  (Δ%+d)' % (raw0, raw1, raw1 - raw0))

    fail = []
    if lf1 > LIMIT_LF:
        fail.append(u'E1 LF %d > %d（必须净减或持平）' % (lf1, LIMIT_LF))
    if raw1 > LIMIT_RAW:
        fail.append(u'A1 原始 %d > %d' % (raw1, LIMIT_RAW))
    h = head_text()
    if h is not None:
        hl = lf_len(h)
        print(u'[HEAD] LF %d（git 实测）' % hl)
        if lf1 > hl:
            fail.append(u'E1 相对 HEAD 增加了 %+d' % (lf1 - hl))
    if fail:
        print(u'[停手] 未过关：')
        for f in fail:
            print(u'   - ' + f)
        print(u'   ⇒ 一个字节都不写')
        return 4

    if not write:
        print(u'[dry] 全部过关，加 --write 才落盘')
        return 0

    # ★ 二进制写回：只做字节级替换，EOL 保持原样
    with io.open(MEM, 'wb') as fh:
        fh.write(cur.encode('utf-8'))
    back = io.open(MEM, 'rb').read().decode('utf-8')
    print(u'[写回] 字节 %d → %d' % (len(raw), len(back.encode('utf-8'))))
    # ★★ EOL 判据：不能写"CRLF 数量不变" —— **新增一行必然多一个 CRLF**，
    #    第一版这么写就成了"改对了也报红"的坏判据。正确的口径是**一致性**：
    #    全文裸 LF 数为 0，且 CRLF 总数 == LF 总数。
    naked_lf = back.count(u'\n') - back.count(u'\r\n')
    print(u'[EOL] CRLF %d → %d（新增行自带，属预期）· 裸LF %d · CRLF==LF：%s'
          % (s.count(u'\r\n'), back.count(u'\r\n'), naked_lf,
             u'OK' if (naked_lf == 0 and back.count(u'\r\n') == back.count(u'\n'))
             else u'报红'))
    print(u'[自证] 内容 == 计划内容：%s' % (u'OK' if back == cur else u'报红'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
