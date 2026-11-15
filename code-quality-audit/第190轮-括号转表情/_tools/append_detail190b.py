# -*- coding: utf-8 -*-
u"""第190轮（下半）· 往记忆**详版**追加 §194（append-only，绝不重写整个文件）。

★ 为什么需要这一节：速查本已经写了「190 表情按原样」，而 `recheck95mem.py` 的
  **E2** 要求速查本里每个新令牌都能在详版自证 —— `out is im` 只写在速查本里，
  E2 当场报红。规范解法是**把真源写进详版**（速查本只是摘要），不是把令牌改掉。

★ 追加前查撞号：本轮末章应为 193。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = os.path.abspath(os.path.join(u'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本',
                                 '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md'))

BODY = u"""
---

## 194. 第190轮（下半）· 用户裁定「按原样」⇒ ink 作废 + 两处判据缺陷（2026-11-15）

### 194.1 裁定：一个像素都不改

用户看完「原作原样 / ink / line」三行对照图后：**`ok，按原样来就好`**

⇒ `build_faces190.py` 默认 `MODE = 'original'`，只换目录/文件名，**像素零改动**。
`ink`（黑→透明、白反相黑线）/ `line`（黑→透明、白线保留）降级成 `--mode` 可选。

**采纳理由（不是"省事"）**：任何色度变换都是「我替原作做决定」，与项目口径
「一切根据原作」冲突。副作用（黑底成黑牌、白线在浅底看不见）属于 **UI 排版要解决的
问题，不该由改素材来兜**。

★ **作废旧结论**：§193.7 里那套「转换＝亮度→alpha」「闸② 亮度守恒」「黑砖去掉成功」
全部作废。现在落地的是黑砖 —— 用户要的就是这个。

### 194.2 ★★★ 缺陷一：闸② 差点写成 `out is im` 的恒假判据

`original` 模式下 `out = im`（同一对象），所以

```python
if im.tobytes() != out.tobytes():     # ← 恒假：同一个对象比自己
    g2_bad.append((fn, 'pixels-differ'))
```

**这道闸等于不存在**。这正是记忆铁律里那条「**恒真/恒假判据比不写还危险**」——
它每次都会绿，而且绿得让人安心。

正解：**读回落盘文件再比**

```python
back = Image.open(os.path.join(d, fn)).convert('RGBA')
if im.tobytes() != back.tobytes():
    g2_bad.append((fn, 'pixels-differ'))
```

这样顺带能抓 PNG 保存的位深/调色板损失（原地比根本发现不了）。
另配**负控制**：拿一张产物改 1 个像素，用同一套比法必须判"不同"，否则判据失效。

### 194.3 ★★★ 缺陷二：20 个 OneShot 文件全叫 `portrait.png`，而五道闸全绿

```python
os_plan.append((OS_MAP[base], 'portrait', os.path.join(OS_DIR, fn)))
#                               ^^^^^^^^^ 第二格本该是文件名 base，却塞了 kind 字面量
```

后果：20 个角色目录里全叫 `portrait.png`；manifest 的 `emotion` 退化成 `'portrait'`；
**人名信息丢失，无法从 manifest 反推源文件**。

★★★ **闸 ①③④ 全部照样绿**：磁盘数 190 == manifest 190、每张都能打开且尺寸对、
21 个 id 全在 —— 一个都没抓到。抓到它的是**独立核验 L1**，因为"源路径推不出来"。

⇒ 修：第二格改回 `base`。**新增闸⑤**把这类静默退化永久钉住：

* `emotion` 不得等于 kind 字面量（`'portrait'` / `'expression'`）
* 同一 id 下文件名不得重复（防互相覆盖）

### 194.4 独立核验 `verify_faces190.py`：三层，L2 才是真独立

五道闸是"自己验自己"（比的是自己内存里那一对 src/out）。另开一条**只读**路径，
并且**独立写一份 `ID2ROLE` 映射**（故意不 import build 脚本的 —— 复用就变成
"同一个假设验两遍"）。

| 层 | 判据 | 结果 |
|---|---|---|
| L1 | 仓库 png == 中间裁切件（全量 190） | 190 / 不一致 0 / 缺 0 |
| L2 | 仓库 png == **从原始整页现场重裁**（跨过中间产物） | 164 / 不一致 0 |
| L3 | 负控制：改 1 像素必须判"不同" | 判为不同 OK |

★ L1 只能抓到"映射错、源缺失"，**抓不到中间件本身被动过**；L2 从 `D:\\_tmp190\\
hy_export_pages190\\pages\\pXXX.png` 按 rect 现场 `crop` 一遍，页序变了 / 裁切脚本
改坏了都会红。

### 194.5 ★★★ 原样落地后才发现：黄魂肖像本身就是**三套底色**

只看 `opaque_pct` 会误判成两档（把"前景是黑"和"背景是黑"混为一谈），必须同时测
**前景像素平均亮度**与**白线占前景比例**：

| 组 | 帧 | 不透明 | 前景亮 | 白线占前景 | 形态 |
|---|---|---|---|---|---|
| `hy_axis` / `hy_ceroba_ketsukane` / `hy_chujin_ketsukane` | **79** | 100.0 | 71~88 | 28~34% | 黑底 + 白线（整格黑矩形） |
| `hy_ace` / `hy_mooch` | **21** | 50~62 | 145~175 | 57~69% | 透明底 + 黑剪影带白线 |
| `hy_ed` / `hy_moray` / `hy_starlo` | **64** | 32~45 | **255** | **100%** | 纯白线 + 透明底（**零暗像素**） |

`79 + 21 + 64 = 164`。三套都是从同一批整页直接裁的，**不是处理差异，是原作如此**。

放到桌宠浅色气泡上的后果（`bubble_ctx.png` 实拍确证）：

* 79 帧 ⇒ 一块黑牌，边界明显；
* 21 帧 ⇒ 能看，但和上面观感不一致；
* **64 帧 ⇒ 完全看不见**（纯白线落在浅底上）—— 这是**功能性缺陷**，不是审美问题。

⇒ **素材侧不修**（修了就不叫"原样"）。结论落到 UI：**气泡里的肖像格必须给深色底板**，
三套才都能看清、观感也统一。已向用户提出方案 A（深色圆角底板 `#2A2C33`），待确认。

### 194.6 产品侧接线已摸清，未动一行代码

`modules/event_speech.py:773 strip_action_parentheticals(text)` **只返回字符串**，
被删掉的括号内容**没有任何出口**。接线第一步是加可选 `sink=None`：

```python
def strip_action_parentheticals(text, sink=None):
    ...
    if sink is not None:
        sink.append(被删原片段)
    return t                      # 返回值语义完全不变 ⇒ 既有调用方零影响
```

★ `sink` 必须在**每道子闸真删了东西**时记录，不能函数末尾统一"猜" ——
否则拿到的是猜出来的旁白，不是实际删掉的。

**映射表可以很小**：第188轮那 231 轮实测里被删形态只有 **16 种**
（`（笑）`42 / `（微笑）`39 / `（NYEH HEH HEH!）`19 / `（苦笑）`6 / `（思考片刻）`3 …）
⇒ 关键词匹配够用。匹配不上 ⇒ **只做动作、不换表情**（不猜）。

### 194.7 回归

`code-quality-audit/regress/run_all.py`：**186 套件 / PASS=8222 / FAIL=0**；
仅 `check99` 判 `IDENTICAL*`（真机 log 交错产生空行噪声，剔空行后逐行全等，**未刷基线**）。
⇒ 190 个素材替换没有撞到任何既有判据。

### 194.8 本轮写脚本的三条教训（都是自己踩的）

1. **自检判据别写成"数量不变"**：`patch_mem190b.py` 第一版用「CRLF 数不变」当 EOL 自检，
   而**新增一行必然多一个 CRLF** ⇒ 改对了也报红。正解是**一致性**：
   裸 LF 数 == 0 且 `CRLF 总数 == LF 总数`。
2. **路径层级要按实际目录算**：`_tools/` 上一级是轮次目录、再上一级 `code-quality-audit`、
   再上一级才是仓库根 —— 我用 `'..','..'` 只到了 `code-quality-audit`，脚本直接"日志不存在"。
3. **锚点必须逐字核对**：`174（§176）变体补 51` 被我写成 `174 变体补 51`（漏了章节号），
   命中 0 次；脚本里 assert `count == 1` 才没出现"以为改了其实没改"。
"""


def main():
    if not os.path.isfile(P):
        print(u'[停手] 详版不存在：%s' % P)
        return 2
    s = io.open(P, encoding='utf-8').read()
    if re.search(u'^## 194\\.', s, re.M):
        print(u'[空转] §194 已存在，不重复追加')
        return 0
    head_before = len(s.encode('utf-8'))
    with io.open(P, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(BODY)
    back = io.open(P, encoding='utf-8').read()
    print(u'[写前] %d 字节 → [写后] %d（增量 %d，正文 %d）'
          % (head_before, len(back.encode('utf-8')),
             len(back.encode('utf-8')) - head_before, len(BODY.encode('utf-8'))))
    # 自证：旧内容逐字未变（append-only 的核心约束）
    print(u'[自证] 旧内容逐字未变：%s' % (u'OK' if back.startswith(s) else u'报红'))
    print(u'[自证] §194 存在：%s' % (u'OK' if re.search(u'^## 194\\.', back, re.M) else u'报红'))
    print(u'[自证] 令牌 `out is im` 在详版里：%s'
          % (u'OK' if u'out is im' in back else u'报红'))
    print(u'[自证] 裸 LF 数 %d（本文件一直是纯 LF）' % (back.count(u'\n') - back.count(u'\r\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
