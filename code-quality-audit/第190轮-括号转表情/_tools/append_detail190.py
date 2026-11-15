# -*- coding: utf-8 -*-
u"""第190轮 · 往记忆**详版**追加 §193（append-only，绝不重写整个文件）。

为什么用脚本而不是 Edit
-----------------------
详版近 1 MB、近千行；任何"整文件重写"都可能把编码/EOL/结构搞坏。
本脚本只做 `open('a')` 追加，不读回、不改已有内容。

★ 追加前先查末尾章节号，确认不会撞号（本轮末章应为 192.10）。
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

## 193. 第190轮 · 括号转表情：素材普查与贴图还原（2026-11-15）

> 本轮**零产品代码改动**（`ralsei_pet/` 一字节没动）。全部在
> `code-quality-audit/第190轮-括号转表情/`（`report190.md` + `_tools/` + `_evidence/`）。

### 193.1 ★★★ 用户一问推翻了我的一条判据

用户原话：**`有没有可能有些原版头像就是没颜色只是黑白呢`**

我原来的排除闸：**「裁出的图颜色数 ≤ 2 ⇒ 蒙版 ⇒ 解码失败」**。
这条闸的隐含前提是"原版头像一定有颜色"。一旦原作本来就有单色图，
它就会把**正确的单色图判成解码失败** —— 正是「**判据过窄 = 误报**」（第159轮）。

**实证（全部肉眼确认，不是统计推断）**：

| 图 | 尺寸 | 唯一色 | 构成 | 结论 |
|---|---|---|---|---|
| 黄魂 `p083` | 2048² | 2 | 纯白 19.2% + 全透明 80.8% | 遮罩/剪影，原作如此 |
| UT `spr_face_undyne0..8` | 45×38 | 2 | 黑 72% + 白 28%、100% 不透明 | **结局字幕**黑白小头像 |
| UT `spr_floweyface_l` | 42×26 | 2 | 白线稿 | 原作单色 |
| UT `spr_vulkinface` | 27×18 | 2 | 白块 | 原作单色 |
| UT `spr_asgore_face0` | — | 2 | 白剪影 + 黑底 | 原作单色 |
| 黄魂 `spr_portrait_*` 全族 124 个 | 110×106 | 2~3 | 黑底 72% + 白线 28%、**零透明** | 线稿层（见 §193.5） |

#### 判据修正（已落进 `color190.py` 的 docstring）

| 现象 | 结论 |
|---|---|
| 彩条/色块噪声 | 解码真的错了 |
| 轮廓清晰的单色角色 | **原版就是单色，旧判据错了** |
| 噪声也"颜色很多"；蒙版与正确单色图都是 1~2 色 | **颜色数区分不了上面两者** |

⇒ 必须配三项结构量（对"噪声 vs 真实图形"敏感）：

- `opaque%` 不透明像素占比（蒙版/噪声常接近 0 或 100）
- `flat%` 水平相邻同色率（真实像素画大片平涂，通常 > 70%；噪声接近 0）
- `comp` 4-邻域连通块数（真实图形少数大块；噪声海量碎片）

★★ 再加一条最硬的：**存成 PNG 让肉眼确认**。"看起来对不对"最终只能由人判，
指标只用来决定"先看哪几张"。

### 193.2 ★★★ 自写 QOI 解码器：整条路作废

**仍然成立的事实**：
- 黄魂 117 页 = **34 张 PNG 块 + 84 个 `BZh`(bzip2) 块**，与 UTMT 报的 `embedded=117` 对得上
- `BZh` 解压后是 GameMaker QOI 容器，**12 字节头**由 `dataLen` 字段实证：
  `64×64` 页 `b'fioq@\\x00@\\x00\\xac\\x18\\x00\\x00'` ⇒ 6328 B = 12 + 6316；
  `2048×2048` 页 `\\x0b\\xd7\\x06\\x00` = 448267 ⇒ 448279 = 12 + 448267

**作废理由**：对 `page#0`（64×64，需 4096 px）暴力试起点 0~19：

```
start= 0 出 4096/4096 px，用  493/6328 B，透明 4091
start=12 出 4096/4096 px，用  483/6316 B，透明 3973
start=19 出 4096/4096 px，用  503/6309 B，透明 3973
```

**任何起点都"解满"但只吃 ~500 字节** ⇒ 不是起点问题，是 **op 映射/结构假设整体不成立**
（大量 `0xC0|n` 被当成 RUN，瞬间耗尽像素）。宽容解码出图是**彩条噪声**（肉眼已否定）。

⇒ `qoi190.py` 留档作废，别再捡起来。

### 193.3 ★★★ 正确入口：UTMT 整页导出（反射出来的真 API）

`probe_api190.csx` 输出（**别再猜**）：

```
### TextureWorker
inst   MagickImage GetEmbeddedTexture(UndertaleEmbeddedTexture embeddedTexture)
inst   Void ExportAsPNG(UndertaleTexturePageItem, String, String, Boolean includePadding)
static Void SaveImageToFile(IMagickImage`1 image, String filePath)

### UndertaleEmbeddedTexture
prop UndertaleModLib.Util.GMImage Image      ← TexData 上
prop Boolean FormatQOI                        ← UTMT 自己知道哪些页压缩了
prop Boolean FormatBZ2
```

三条硬事实：

1. **UTMT 0.9.2 用 ImageMagick / Magick.NET，不用 `System.Drawing`**
   ⇒ `using System.Drawing.Imaging;` 直接 **CS0234**，`Bitmap` 根本不存在。
2. 整页导出 = `GetEmbeddedTexture(tex)` → `MagickImage` → `TextureWorker.SaveImageToFile`。
3. `FormatQOI` / `FormatBZ2` 直接给答案（黄魂 83 页 QOI+BZ2；UT 42 页全 0）。

**实测**：黄魂 **117/117 成功、0 失败**，其中 **98 页 >2 色**；
UT 42/42 成功；颜色**没有丢**（`spr_undyneb_face2` 3~4 色、`spr_mettface1` 4~5 色）。

### 193.4 ★★★ E 盘坏点会伪装成"代码写错了"

```
System.ExecutionEngineException: In page error:
Attempted to access a memory page that is not present, and the system
is unable to load the page.
   at System.Reflection.Internal.MemoryBlock.BinarySearchReference(...)
   at Microsoft.CodeAnalysis.CSharp.OverloadResolution...
```

- rc = **3221225478**（0xC0000602 FailFast），日志里**只有这一句**
- 发生在 Roslyn 加载 Magick.NET 元数据时 ⇒ 看着像 csx 编译失败，**实际是磁盘页读不出来**
- E 盘原件 md5 逐一核对 **213 个文件全 OK** ⇒ 属于**偶发**读坏
- 同一份 csx 改从 **D 盘副本**跑 ⇒ rc=0、**117/117 页全导出成功**

**处置**：新增 `utmtpath190.py`，三处脚本统一改**优先 D 盘副本**
（`D:\\_tmp190\\utmt\\`），E 盘原件只当兜底；
`mkutmt190.py` 负责复制 + **逐字节校验**（实测 359 文件一致）。

★★ 这个坑的可怕之处：**报错文本完全不提磁盘**，而且 `try/catch` 拦不住
（FailFast 直接杀进程）⇒ 极易误判成"我的 C# 语法错了"，从而在错误方向改半天。

### 193.5 ★★★ 黄魂肖像：数据里就是黑白线稿

按角色统计「彩色帧 / 总帧」：

| 角色 | 彩色帧/总帧 | 角色 | 彩色帧/总帧 |
|---|---|---|---|
| ace | 6/6 | alphys | **0/3** |
| chujin | 13/13 | asgore | **0/12** |
| fchujin | 18/18 | axis | **0/9** |
| kanako | 22/22 | **ceroba** | **0/57** |
| mooch | 15/15 | moray | **0/12** |
| ed | 2/8 | starlo | **0/44** |

肉眼确认 8 张（kanako_neutral / mooch_normal / ace_normal / chujin_sad_eye_smirk /
ceroba_neutral / starlo_normal / moray_normal / asgore_regular）：**全部黑底白线稿**。
"3 色"只比"2 色"多一个近黑像素，**没有任何肤色/头发色/衣服色**。

**三条补充证据**：

1. 肖像格 **100% 不透明、黑占 72%**。正常对话头像是**透明底**、贴到对话框上；
   **不透明 + 纯黑底 = 剪影/线稿层**，不是成品彩色肖像。
2. `p060` 整页 449 色、45.7% 不透明 ⇒ **同页其它坐标确有彩色**
   （`(1664,896)`、`(1536,896)` 两格是彩色小人：红发 Ceroba、蓝衣角色、戴帽橙发 ——
   但那是**大地图行走图**约 25×52，不是 110×106 的对话肖像）。
3. 包里**只有一套** portrait 家族（`spr_portrait` 124 个），**没有**第二个彩色变体
   （`grep -i ceroba` 全量确认）。

⇒ **结论：黄魂 `game.droid` 里 `spr_portrait_*` 的像素就是黑白线稿。**

★ **未验证**：游戏是否在运行时给它上色。
`dump_code190.csx` 扫 12186 个代码段**命中 0** —— `c.Instructions.ToString()` 在
UTMT 0.9.2 上取不到 GML 反汇编（异常被 try/catch 吞，`txt` 全是空串）。
⇒ 代码侧证据本轮**没拿到**，这个可能性留着。

### 193.6 素材现状分级（76 人）

**可用（真彩色，已验证）**

| 来源 | 数量 | 依据 |
|---|---|---|
| **OneShot 肖像** | **26 张 / 覆盖 21 人别名** | `E:\\项目文件夹\\xnbcli（oneshot)\\unpacked\\the_world_machine\\portraits`，424×276，451~5668 色，100% 不透明 |
| UT 彩色脸族 | `spr_undyneb_face2` 3~4 色、`spr_mettface1` 4~5 色、`spr_sansb_face` 4~5 色、`spr_asgore_brandish` 最多 18 色 | 整页裁切 + 肉眼 |

**有素材但只有黑白（如实登记，不造假）**：黄魂 `spr_portrait_*` 全族；
UT 结局字幕脸族 45×38；`spr_floweyface_l` / `spr_vulkinface` / `spr_asgore_face0`；
黄魂 14 张 2 色页 + 5 张退化页（1×1、64×64 渐变条）。

**无素材**：28 人 D 级（flowery / gerson / mike 等）⇒ 按用户口径**不动**。

### 193.7 本轮新增工具清单

| 脚本 | 作用 |
|---|---|
| `utmtpath190.py` | UTMT 路径统一解析（优先 D 盘副本） |
| `utmtrun190.py` | 通用跑手：纯 ASCII 工作目录 + `__OUTDIR__` 替换 + `--list` 走环境变量 |
| `mkutmt190.py` | 复制 UTMT 到 D 盘 + **逐字节校验**（含"先清空目标前确认在 D:\\_tmp190 下"防手滑） |
| `probe_api190.csx` | 反射探测导出 API 与 `TexData` 成员 |
| `export_pages190.csx` | 整页导出（`GetEmbeddedTexture`）→ `pages/pNNN.png` + `pages.tsv` |
| `color190.py` | 颜色 + 结构四量统计（**判据修正的落地处**） |
| `pagemap190.py` | `页 → sprite 名` 双向可查 |
| `crop190b.py` | 按 UV 裁切，**三道闸** |
| `dump_code190.csx` | 尝试导含 `portrait` 的代码段（**失败**，见 §193.5 末） |
| `patch_mem190.py` | 速查本补丁（**先算后写**） |

作废留档：`qoi190.py`、`crop190.py`。

#### `crop190b.py` 三道闸（照抄，别删）

```python
# ★ 闸①：UV 矩形必须真的落在页内，越界就是 UV 表或页序错了
if r['sx'] < 0 or r['sy'] < 0 or r['sx'] + r['sw'] > W or r['sy'] + r['sh'] > H:
    bad_size.append(...)
# ★ 闸②：裁出来必须**不是全透明**（全透明说明 UV 指了一片空白 ⇒ 表错了）
if n_op == 0:
    blank.append(...)
# ★ 闸③：裁出张数必须等于 UV 数据行数（否则就是有行被跳过了）
if written != len(uv):
    print('[报红] 张数对不上 ⇒ 不许当成功')
```

实测：黄魂 **219/219**、UT **574/574** 全过。

### 193.8 ★ 本轮三个"写脚本"的教训

1. **`Type.GetType("System.Drawing.Bitmap, System.Drawing")` 会当场猝死**
   —— .NET 10 + Roslyn 脚本下走 `RuntimeAssembly.GetTypeCore`，直接
   **FailFast 0xC0000006**，`try/catch` 拦不住。探测程序集只能用纯托管遍历。
2. **改记忆要"先算后写"**：第一版 `patch_mem190.py` 是"先写再打印体积"，
   写完 **10268** 才发现超 10000 上限，还得手工回滚。改成先在内存算、不过关一个字节都不落盘。
3. **中文长行手工 Edit 极易 anchor 不匹配**：本轮连撞两次
   （`用户裁定` vs 实际 `裁定`；188 段落已被上一轮压缩过）。
   ⇒ 改脚本 + 跑 `difflib` 逐行核对，比肉眼可靠。

### 193.9 待用户裁定（一个决定影响 8 个角色）

| 走法 | 说明 |
|---|---|
| **A（默认，符合"没有的不动"）** | 黄魂肖像先不动，登记"有素材但无颜色"；先做 OneShot 21 人 + UT 彩色脸族 |
| B | 黑白线稿直接当表情图用（风格突兀） |
| C | 继续挖"游戏是否运行时上色"（未知，可能挖不出来） |
"""


def main():
    if not os.path.isfile(P):
        print(u'[停手] 详版不存在：%s' % P)
        return 2
    s = io.open(P, encoding='utf-8').read()
    # ★ 撞号检查：必须没有 193 已经存在
    if re.search(u'^## 193\\.', s, re.M):
        print(u'[停手] 详版里已有 §193，拒绝重复追加')
        return 3
    n0 = len(s)
    with io.open(P, 'a', encoding='utf-8', newline='') as fh:
        fh.write(BODY)
    s2 = io.open(P, encoding='utf-8').read()
    print(u'[体积] %d → %d  Δ=%+d' % (n0, len(s2), len(s2) - n0))
    # ★ 追加后必须真的读得到 §193，否则"写了"是假的
    if u'## 193.' not in s2:
        print(u'[报红] 追加后读不到 §193')
        return 4
    print(u'[ok] %s' % P)
    return 0


if __name__ == '__main__':
    sys.exit(main())
