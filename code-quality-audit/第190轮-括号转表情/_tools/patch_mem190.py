# -*- coding: utf-8 -*-
u"""第190轮 · 往记忆速查本里加本轮两条结论（**净增必须 <= 0**）。

★★★ 为什么是"净增 <= 0"而不是"不超上限"
----------------------------------------
`recheck95mem.py` 两条硬闸同时卡住：

  · **E1**：速查本体积相对 HEAD **净减或持平**（两侧归一到 LF 后比）
    ⇒ HEAD 9867，我第一版写成 10001（Δ=+134）→ **FAIL**
  · **A1**：注入上限按**原始字符数（含 CRLF）** 判（与注入器同口径）
    ⇒ 上限 10000，原始底数 9932，实际余量只有 68

**两条闸合起来的真实含义：每轮只能等量替换，不能净增。**
⇒ 本版改成"**改造已有行 + 等价压缩**"，不再新增独立条目。

★ 另外：写回必须**保留 CRLF**。第一版用 `newline=''` 配合默认读（universal newlines），
  把整份 69 个 CRLF 全变成 LF，等于**顺手改了全文 EOL**（记忆「保持原 EOL」铁律）。
  本版用二进制读写，只做字节级替换。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = os.path.abspath(os.path.join(u'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本',
                                 '.workbuddy', 'memory', 'MEMORY.md'))
#: E1 口径：LF 归一的字符数不得超过 HEAD（9867）
LIMIT_LF = 9867
#: A1 口径：含 CRLF 的字符数不得超过 10000
LIMIT_RAW = 10000

# ── ① 改造已有行（不新增条目）─────────────────────────────────────
EDITS = [
    # (a) 环境小标题：九坑 → 十坑，并把"E 盘坏点伪装成代码错"塞进去
    (u'## 1. 环境 ★★ **九坑速查：处置全文见详版 §168.1**',
     u'## 1. 环境 ★★ **十坑（§168.1）**：+ ★★★ **UTMT `In page error`/0xC0000006 ＝ E 盘坏点**'
     u'（非代码错）⇒ 用 D 盘副本'),

    # (b) 判据行：把"颜色数≤2 ⇒ 解码失败"这个新反例挂到 159 那条上
    (u'**判据过窄=误报**（159）；',
     u'**判据过窄=误报**（159；**190 颜色数≤2 判解码失败是错的**——原版确有纯黑白图）；'),
]

# ── ② 等价压缩（语义不变，只删冗余叙述）──────────────────────────
CUTS = [
    (u'⇒插 `_pick_by_pos`（候选≥2＋有坐标＋**命中1条**）+6。',
     u'⇒插 `_pick_by_pos`（候选≥2＋有坐标＋**命中1条**）。'),
    (u'真身是变体＋`when_src` 精确相等⇒**从未被消费**＋与 174 全重合⇒删。2,810→**2,768**。',
     u'变体＋`when_src` 相等⇒从未消费＋与 174 全重合。2,810→**2,768**。'),
    (u'⇒「无代码」**错**（`CreationCode` 恒 null 见 §173）。',
     u'⇒「无代码」**错**。'),
    (u'**2.5D 空间模型（用户四条纠正）**：桌面＝世界的一间房·**整张桌面＝地面**'
     u'（屏幕底边只是"最近处"·似 Oneshot）·窗口＝**悬空的板**（顶面可站、底下可穿过、'
     u'**非实心柱**）·**桌面＝场地不是家**。★★ 裁定（`BBA`）：可站矩形＝DWM 扩展边框／'
     u'遮挡按屏幕 Y 排序／出边缘＝真掉。**已满足（§180）**。',
     u'**2.5D 模型（用户四条纠正）**：桌面＝世界的一间房·**整张桌面＝地面**'
     u'（底边只是"最近处"·似 Oneshot）·窗口＝**悬空的板**（顶面可站、可穿过、非实心柱）·'
     u'**桌面＝场地不是家**。★★ 裁定（`BBA`）：可站矩形＝DWM 扩展边框／遮挡按屏幕 Y／'
     u'出边缘＝真掉（§180 已满足）。'),
    (u'**187（§189）违规率归因**：24.22%＝895/3696 轮。★★★「第 4 段越聊越崩」**假象**'
     u'（探测三问固定 `i=42/43/44` 共 231 轮全在第 4 段，命中 `AI_SELF` 是**设计预期**；'
     u'剔后 18.7→**23.4%** 平的）。★★ `REPEAT`＝招牌台词⇒**裁定算缺陷·判据不动**；',
     u'**187（§189）违规率 24.22%（895/3696）**。★★★「第 4 段越聊越崩」**假象**'
     u'（探测三问固定 `i=42/43/44`＝231 轮全在第 4 段；剔后 18.7→**23.4%** 平）。'
     u'★★ `REPEAT`＝招牌台词（**裁定算缺陷**）；'),
]


def measure(raw):
    """返回 (LF 归一字符数, 含 CRLF 字符数)。"""
    s = raw.decode('utf-8')
    return len(s.replace(u'\r\n', u'\n')), len(s)


def main():
    raw = io.open(P, 'rb').read()
    lf0, raw0 = measure(raw)
    print(u'[底数] LF=%d  含CRLF=%d' % (lf0, raw0))

    s = raw.decode('utf-8')
    for old, new in CUTS + EDITS:
        c = s.count(old)
        if c != 1:
            print(u'[报红] 锚点不唯一/未命中 count=%d：%s…' % (c, old[:24]))
            return 3
        s = s.replace(old, new)

    out = s.encode('utf-8')
    lf1, raw1 = measure(out)
    print(u'[体积] LF %d → %d (Δ%+d, 限 %d)' % (lf0, lf1, lf1 - lf0, LIMIT_LF))
    print(u'[体积] 含CRLF %d → %d (Δ%+d, 限 %d)' % (raw0, raw1, raw1 - raw0, LIMIT_RAW))

    # ★ E1 是"净减或持平"，不是"不超上限"——必须两闸都过才落盘
    bad = []
    if lf1 > LIMIT_LF:
        bad.append(u'E1 LF %d > %d' % (lf1, LIMIT_LF))
    if raw1 > LIMIT_RAW:
        bad.append(u'A1 含CRLF %d > %d' % (raw1, LIMIT_RAW))
    if bad:
        print(u'[报红] %s ⇒ 不写入' % ' / '.join(bad))
        return 4

    # ★ 保留 CRLF：直接写回字节串（读时没做换行归一，所以 CRLF 原样在）
    with io.open(P, 'wb') as fh:
        fh.write(out)
    print(u'[写入] %s' % P)

    # ★ 自检：CRLF 个数不变（证明没顺手改 EOL）
    n0 = raw.count(b'\r\n')
    n1 = out.count(b'\r\n')
    print(u'[EOL] CRLF %d → %d %s' % (n0, n1, u'OK' if n0 == n1 else u'[报红] 变了！'))
    return 0 if n0 == n1 else 5


if __name__ == '__main__':
    sys.exit(main())
