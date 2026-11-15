# -*- coding: utf-8 -*-
u"""第190轮（接线）· 速查本补丁（只做等量替换，E1 要求净减或持平）。

★ 三条硬约束（`recheck95mem.py`）：
  E1 相对 HEAD **净减或持平**（LF 归一后比）
  A1 含 CRLF 的原始字符数 ≤ 10000
  E2 新增令牌必须能在详版自证 —— 所以先把内容写进详版 §195 再改这里。

★ 先算后写：不过关一个字节都不落盘。
★ 二进制写回：只做字节级替换，不碰 EOL。
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')

LIMIT_RAW = 10000

EDITS = [
    # ① 190 条瘦身：判据教训已进详版 §194.2/194.3，速查本不必重复占位
    (u'190 瘦身',
     u'⇒须深底板。★★ 闸② `out is im`＝**恒假**；OneShot 名退化却 ①③④ 全绿⇒加闸⑤。',
     u'⇒须深底板。'),

    # ② 新增「190 接线」条目（紧跟 190 条之后）
    (u'插入 190 接线',
     u'\r\n- ★★★ **188/189 护栏两刀（§190/§192）**',
     u'\r\n- ★★★ **190 接线**：`sink` 吐括号→`acts_to_emotion`（**总有值**）→候选链'
     u'**必补 normal/neutral/default/plain**＋`any_face_for`。'
     u'★★ NPC 走 **`add_npc_line`**（非 `add_dialogue`）·Ralsei `_FACE_MAP` 补 short 键。'
     u'★ 缺口：**未删括号不触发**。'
     u'\r\n- ★★★ **188/189 护栏两刀（§190/§192）**'),

    # ③ 169+170 合并（两条都在讲门，详版有全文）
    (u'合并 169+170',
     u'- ★★★ **169（§170）W 门 +102**：`srcRoom` 被无条件清；**90.3% 双盲**≠验收；'
     u'**门字母≠落点字母**⇒marker 按 `branch_letter`。\r\n'
     u'- ★★★ **170（§171）实例级落点**：同房多扇靠 `if(x>…)` 分流⇒`_pick_by_pos`'
     u'（候选≥2＋有坐标＋**命中1条**）。★ **12 条必写 `door_y`**·**重复边不加**。',
     u'- ★★★ **169/170（§170/171）门**：W 门 +102（`srcRoom` 无条件清·**90.3% 双盲**≠验收·'
     u'**门字母≠落点字母**⇒marker 按 `branch_letter`）；实例级落点 `if(x>…)` 分流⇒'
     u'`_pick_by_pos`（候选≥2＋坐标＋**命中1条**）·12 条必写 `door_y`·重复边不加。'),

    # ④ 171+172+173 合并
    (u'合并 171~173',
     u'- ★★★ **171（§172）实例表+25**。★★★ 老 `range_miss` **假**⇒**候选集须同一套**；'
     u'★★★ `obj_doorAny` **自成一族**⇒12 条留档、**不删**。\r\n'
     u'- ★★★ **172（§173）Any 门接线**：目标在**每实例** `PreCreate` 的 `doorRoom`⇒'
     u'「无代码」**错**。★ `_pick_by_pos` **第二拍**（`(x,y)` 一起对）。'
     u'★★★ **173 物化 +820（§175）**：房号**回退 index**；Any **无 sprite**。',
     u'- ★★★ **171~173（§172~175）**：老 `range_miss` **假**⇒**候选集须同一套**；'
     u'`obj_doorAny` **自成一族**（12 条留档不删）；Any 目标在**每实例** `PreCreate.doorRoom`；'
     u'`_pick_by_pos` **第二拍** `(x,y)`；物化 +820（房号**回退 index**·Any **无 sprite**）。'),

    # ⑤ 178+179+181 合并
    (u'合并 178~181',
     u'- ★★★ **178（§180）遮挡按 Y**：窗口**下沿**>脚底⇒在前；无前挡⇒`HWND_TOP`；'
     u'候选只取 `self.floors`。★ **`HWND_TOP==0` 假值**⇒静默插最底。\r\n'
     u'- ★★★ **179（§181）「站谁上面」优先于 Y**：站窗口楼板⇒**无条件**插它之前；'
     u'Y 只对站桌面生效。\r\n'
     u'- ★★★ **181（§183）补 63 条**（2,768→2,831）：六族位移 ±1/±2/**±3**；'
     u'`when_door`=**字母**非 `entrance`；可达 221 不变。',
     u'- ★★★ **178~181（§180~183）**：遮挡按 Y（窗口**下沿**>脚底⇒在前·无前挡⇒`HWND_TOP`·'
     u'**`HWND_TOP==0` 假值**⇒静默插最底）；**「站谁上面」优先于 Y**（站窗口楼板⇒无条件插它前·'
     u'Y 只对站桌面）；181 补 63 条（2,768→2,831·位移 ±1/±2/**±3**·'
     u'`when_door`=**字母**非 `entrance`·可达 221）。'),
]


def lf_len(s):
    return len(s.replace(u'\r\n', u'\n'))


def head_text():
    try:
        b = subprocess.check_output(
            ['git', '-c', 'core.quotepath=false', 'show',
             'HEAD:.workbuddy/memory/MEMORY.md'], cwd=REPO)
        return b.decode('utf-8', 'replace')
    except Exception:  # noqa: BLE001
        return None


def main():
    write = '--write' in sys.argv[1:]
    raw = io.open(MEM, 'rb').read()
    s = raw.decode('utf-8')
    lf0, raw0 = lf_len(s), len(s)
    print(u'[当前] LF %d / 原始 %d / CRLF %d' % (lf0, raw0, s.count(u'\r\n')))

    cur = s
    bad = []
    for tag, old, new in EDITS:
        n = cur.count(old)
        if n != 1:
            bad.append((tag, n))
            print(u'  [锚点] %-14s 命中 %d 次' % (tag, n))
            continue
        print(u'  [改] %-14s ΔLF %+d' % (tag, lf_len(new) - lf_len(old)))
        cur = cur.replace(old, new)

    if bad:
        print(u'[停手] 锚点问题 %r ⇒ 不写' % (bad,))
        return 3

    lf1, raw1 = lf_len(cur), len(cur)
    print(u'')
    print(u'[预计] LF %d → %d (Δ%+d)' % (lf0, lf1, lf1 - lf0))
    print(u'[预计] 原始 %d → %d (Δ%+d)' % (raw0, raw1, raw1 - raw0))

    fail = []
    h = head_text()
    if h is not None:
        hl = lf_len(h)
        print(u'[HEAD] LF %d' % hl)
        if lf1 > hl:
            fail.append(u'E1 相对 HEAD +%d' % (lf1 - hl))
    if raw1 > LIMIT_RAW:
        fail.append(u'A1 原始 %d > %d' % (raw1, LIMIT_RAW))
    if fail:
        print(u'[停手] %s ⇒ 不写' % fail)
        return 4

    if not write:
        print(u'[dry] 过关，加 --write 落盘')
        return 0

    with io.open(MEM, 'wb') as fh:
        fh.write(cur.encode('utf-8'))
    back = io.open(MEM, 'rb').read().decode('utf-8')
    naked = back.count(u'\n') - back.count(u'\r\n')
    print(u'[写回] %d → %d 字节' % (len(raw), len(back.encode('utf-8'))))
    print(u'[EOL] 裸LF %d · CRLF==LF %s · 内容一致 %s'
          % (naked, back.count(u'\r\n') == back.count(u'\n'),
             u'OK' if back == cur else u'报红'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
