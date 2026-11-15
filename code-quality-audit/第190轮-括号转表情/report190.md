# 第190轮 · 括号转表情（表情/动作素材普查与还原）

> 用户口径（2026-11-15，本轮四条）
> 1. `不不不，全做，现在一视同仁，不再是主体为ralsei的项目了`
> 2. `反正在原作的解包里应该有全套的，你看一下，都做，没有的也不用改动`
> 3. `我记得你不是在E盘有解包后的文件吗`
> 4. `那齐全的就正常做，没有的不动就好，记住，一定要验证哦`
> 5. **（关键质疑）`有没有可能有些原版头像就是没颜色只是黑白呢`**

---

## 1. 摘要

| 项 | 结论 |
|---|---|
| 用户那句质疑 | **成立，而且直接命中我的判据缺陷**（详见 §3） |
| 自写 QOI 解码器 | **整条路走不通，已废弃**（详见 §4.1） |
| 真正的还原入口 | **UTMT 整页导出** `TextureWorker.GetEmbeddedTexture()`，黄魂 **117/117 页全成功** |
| 颜色有没有丢 | **没有**。黄魂 98/117 页真彩色；UT 的 Undyne 脸 4 色、Mettaton 脸 5 色 |
| 有一批图确实是黑白 | **是**。UT 结局字幕脸族、Flowey 脸、黄魂整族 `spr_portrait_*`（详见 §3 实证） |
| 本轮产品代码改动 | **零**（`ralsei_pet/` 一个字节没动） |
| 状态 | 素材普查完成，还原管线打通；**待用户裁定黄魂肖像怎么处置**（§7） |

---

## 2. 素材覆盖普查（76 人，按包内 sprite 名单匹配）

| 作品 | 人数 | A（带情绪名的肖像） | B（face 族） | C（只有口型/通讯录） | D（无） |
|---|---|---|---|---|---|
| Deltarune | 15 | 0 | 12 | 0 | 3（flowery / gerson / mike） |
| Undertale | 14 | 0 | 8 | 0 | 6 |
| Undertale Yellow | 15 | **8** | 2 | 2 | 3 |
| OneShot | 21 | 0 | 1 | 7 | 13 |
| OuterTale | 11 | 0 | 8 | 0 | 3 |
| **合计** | **76** | **8** | **31** | **9** | **28** |

★ 普查脚本 `survey190.py`（v2）。**v1 有严重误报**：把 `face/ch3` 整个目录算给每个 Deltarune 角色
⇒ 人人 800+ 张。v2 改为**按 sprite 名单名字匹配**才算对。

---

## 3. ★★★ 用户质疑的实证答复：有些原版图**本来就没有颜色**

### 3.1 这条质疑打穿了什么

我原先的排除闸是：

> 裁出的图 **颜色数 ≤ 2 ⇒ 蒙版 ⇒ 解码失败**

这条闸的**隐含前提是"原版头像一定有颜色"**。若原作本来就画了单色图，这条闸就会把
**正确的单色图判成解码失败** —— 正是记忆里的「**判据过窄 = 误报**」（第159轮）。

### 3.2 实证：确实有一批原版图是单色

| 图 | 尺寸 | 唯一色 | 构成 | 判定 |
|---|---|---|---|---|
| 黄魂 `p083` | 2048² | **2** | 纯白 `(255,255,255,255)` 占 19.2% + 全透明 80.8% | **遮罩/剪影**，原作就是这样 |
| UT `spr_face_undyne0..8` | 45×38 | **2** | 黑 72% + 白 28%，100% 不透明 | **结局字幕黑白小头像**（不是战斗脸） |
| UT `spr_floweyface_l` | 42×26 | **2** | 白线稿 | 原作单色 |
| UT `spr_vulkinface` | 27×18 | **2** | 白块 | 原作单色 |
| UT `spr_asgore_face0` | — | **2** | 白剪影 + 黑底 | 原作单色 |
| 黄魂 `spr_portrait_*` 整族（124 个） | 110×106 | **2~3** | 黑底 72% + 白线 28%，**零透明** | 见 §3.3 |

★★ **判据修正（已写进 `color190.py` docstring）**：颜色数**不能**单独当"解码是否成功"的判据。
改成组合量 + 肉眼：

| 现象 | 结论 |
|---|---|
| 彩条/色块噪声 | 解码真的错了 |
| 轮廓清晰的单色角色 | **原版就是单色，旧判据错了** |
| 噪声也"颜色很多"，蒙版与正确单色图都是 1~2 色 | **颜色数区分不了上面两者** |

所以额外算三项结构量（对"噪声 vs 真实图形"敏感）：

- `opaque%` 不透明像素占比 —— 蒙版/噪声常接近 0 或 100
- `flat%` 水平相邻同色率 —— 真实像素画是大片平涂（通常 > 70%），噪声接近 0
- `comp` 4-邻域连通块数 —— 真实图形是少数大块，噪声是海量碎片

### 3.3 黄魂肖像的实测分布（这一条最反直觉）

按角色统计「彩色帧 / 总帧」：

| 角色 | 彩色帧/总帧 | 角色 | 彩色帧/总帧 |
|---|---|---|---|
| ace | 6/6 | alphys | **0/3** |
| chujin | 13/13 | asgore | **0/12** |
| fchujin | 18/18 | axis | **0/9** |
| kanako | 22/22 | **ceroba** | **0/57** |
| mooch | 15/15 | moray | **0/12** |
| ed | 2/8 | starlo | **0/44** |

★ 我肉眼确认过 8 张（`kanako_neutral` / `mooch_normal` / `ace_normal` / `chujin_sad_eye_smirk` /
`ceroba_neutral` / `starlo_normal` / `moray_normal` / `asgore_regular`）：**8 张全是黑底白线稿**。
所谓"3 色"只是比"2 色"多了一个近黑像素，**没有任何肤色/头发色/衣服色**。

★ 关键结构证据：这些肖像格是 **100% 不透明、黑占 72%**。正常对话头像是**透明底**、贴到对话框上；
**不透明 + 纯黑底 = 剪影/线稿层**，不是成品彩色肖像。

★ `p060` 整页有 449 色、45.7% 不透明 ⇒ **同一页的其它坐标确实有彩色内容**
（`(1664,896)`、`(1536,896)` 两格是**彩色小人**：红发 Ceroba、蓝衣角色、戴帽橙发 —— 但那是
**大地图行走图**约 25×52，不是 110×106 的对话肖像）。

★ 包里**只有一套** portrait 家族（`spr_portrait` 124 个），**没有**第二个彩色变体。
（`grep -i ceroba` 全量确认。）

⇒ **结论：黄魂 `game.droid` 里 `spr_portrait_*` 的像素就是黑白线稿。**
游戏是不是在运行时给它上色，本轮**未验证**（代码反汇编那条路没通，见 §4.3）。

---

## 4. 工具链真相（本轮踩完的坑，全部可复现）

### 4.1 ★★★ 自写 QOI 解码器：整条路走不通，已废弃

已确认的事实（这些仍是对的）：

- 黄魂 117 页 = **34 张 PNG 块 + 84 个 `BZh`(bzip2) 块**；UTMT 报 `embedded=117`，对得上
- `BZh` 解压后是 GameMaker QOI 容器，**12 字节头**已由 `dataLen` 字段实证：
  - `64×64` 页：`b'fioq@\x00@\x00\xac\x18\x00\x00'` ⇒ 解压 6328 B = **12 + 6316**
  - `2048×2048` 页：`\x0b\xd7\x06\x00` = 448267 ⇒ 解压 448279 = **12 + 448267**

但**为什么放弃**：
对 `page#0`（64×64，需 4096 px）**暴力试起点 0~19**：

```
start= 0 出  4096/4096 px，用   493/6328 B，透明 4091
start=12 出  4096/4096 px，用   483/6316 B，透明 3973
start=19 出  4096/4096 px，用   503/6309 B，透明 3973
```

⇒ **任何起点都能"解满"但都只吃 ~500 字节**。这不是起点问题，是 **op 映射/结构假设整体不成立**
（大量 `0xC0|n` 被当成 RUN，瞬间耗尽像素）。宽容解码出的整页是**彩条噪声**（肉眼已否定）。

### 4.2 ★★★ 正确入口：UTMT 整页导出（**已跑通**）

`probe_api190.csx` 反射出来的真实 API（**别再猜**）：

```
### TextureWorker methods
  inst   MagickImage GetEmbeddedTexture(UndertaleEmbeddedTexture embeddedTexture)
  inst   Void ExportAsPNG(UndertaleTexturePageItem texPageItem, String filePath, String imageName, Boolean includePadding)
  static Void SaveImageToFile(IMagickImage`1 image, String filePath)

### UndertaleEmbeddedTexture members
  prop UndertaleModLib.Util.GMImage Image
  prop Boolean FormatQOI
  prop Boolean FormatBZ2
```

三条硬事实：

1. **UTMT 0.9.2 用 ImageMagick / Magick.NET，不用 `System.Drawing`**
   ⇒ `using System.Drawing.Imaging;` 直接 **CS0234**，`Bitmap` 根本不存在。
2. **整页导出的现成入口**是 `GetEmbeddedTexture(embedded)` → `MagickImage` → `SaveImageToFile(img, path)`。
3. `TexData` 上直接有 `FormatQOI` / `FormatBZ2` 两个布尔
   ⇒ **哪些页被压缩不用我反推字节，UTMT 已经告诉我们了**（黄魂 83 页 QOI+BZ2，UT 0 页）。

实测结果：

| 作品 | 页数 | 导出成功 | FormatQOI | FormatBZ2 | 彩色页(>2色) |
|---|---|---|---|---|---|
| 黄魂 UTY | 117 | **117** | 83 | 83 | **98** |
| UT | 42 | **42** | 0 | 0 | 见 §3.2 |

### 4.3 ★★ 代码反汇编那条路没通

`dump_code190.csx` 扫 12186 个代码段，**命中 0**。
原因：`c.Instructions.ToString()` 在 UTMT 0.9.2 上取不到 GML 反汇编文本
（异常被 try/catch 吞掉，所有 `txt` 都是空串）。
⇒ "游戏是不是在运行时给肖像上色"这个问题的**代码侧证据本轮没拿到**。

### 4.4 ★★★ E 盘坏点会让 UTMT 伪装成"代码写错了"

实测报错：

```
System.ExecutionEngineException: In page error:
Attempted to access a memory page that is not present, and the system
is unable to load the page.
   at System.Reflection.Internal.MemoryBlock.BinarySearchReference(...)
   ...
   at Microsoft.CodeAnalysis.CSharp.OverloadResolution...
```

- rc = **3221225478**（0xC0000602 FailFast），日志里**只有这一句**
- 看着像"csx 编译失败"，实际是**磁盘页读不出来**（发生在加载 Magick.NET 元数据时）
- E 盘原件 md5 逐一核对 **213 个文件全 OK** ⇒ 属于**偶发**读坏
- 同一份 csx 改从 **D 盘副本**跑 ⇒ rc=0，**117/117 页全导出成功**

★★ 处置：新增 `utmtpath190.py`，所有脚本统一改成**优先 D 盘副本**
（`D:\_tmp190\utmt\`），E 盘原件只当兜底。

### 4.5 ★★ `Type.GetType("System.Drawing.Bitmap, System.Drawing")` 会当场猝死

在 .NET 10 + Roslyn 脚本下它走 `RuntimeAssembly.GetTypeCore`，
直接 **FailFast 0xC0000006**，`try/catch` 拦不住。
⇒ 探测程序集要用**纯托管遍历**（`AppDomain.CurrentDomain.GetAssemblies()` + `GetTypes()`）。

---

## 5. 本轮新增工具（全部在 `_tools/`）

| 脚本 | 作用 | 状态 |
|---|---|---|
| `utmtpath190.py` | UTMT 路径统一解析（优先 D 盘副本） | 新 |
| `utmtrun190.py` | 通用 UTMT 跑手：纯 ASCII 工作目录 + `__OUTDIR__` 替换 + 环境变量清单 | 新 |
| `probe_api190.csx` | 反射探测 UTMT 导出 API 与 `TexData` 成员 | 新 |
| `export_pages190.csx` | 整页导出（走 `GetEmbeddedTexture`），产物 `pages/pNNN.png` + `pages.tsv` | 新 |
| `pages190.py` | 整页导出驱动（旧版，已由 `utmtrun190.py` 取代） | 新 |
| `color190.py` | **颜色+结构四量统计**，修正旧判据 | 新 |
| `pagemap190.py` | `页 → sprite 名` 双向可查（防"看到彩色页就以为肖像有颜色"） | 新 |
| `crop190b.py` | 按 UV 从整页裁切，**三道闸**：UV 越界 / 全透明 / 张数对不上 | 新（v2） |
| `dump_uv190.csx` | 导 `sprite → 页号 + UV 矩形` | 沿用 |
| `dump_code190.csx` | 尝试导含 `portrait` 的代码段（**失败**，见 §4.3） | 新 |
| `qoi190.py` | 自写 QOI 解码器 | **废弃留档** |
| `crop190.py` | v1 切页裁切 | **废弃留档** |

### 5.1 `crop190b.py` 的三道闸

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

实测：黄魂 **219/219**、UT **574/574** 全部通过。

---

## 6. 素材现状分级（按"能不能直接用于表情"）

### 6.1 可直接用（真彩色，已验证）

| 来源 | 数量 | 依据 |
|---|---|---|
| **OneShot 肖像** | **26 张 / 覆盖 21 人别名** | `E:\项目文件夹\xnbcli（oneshot)\unpacked\the_world_machine\portraits`，424×276，451~5668 色，100% 不透明 |
| UT 彩色脸族 | `spr_undyneb_face2` 3~4 色、`spr_mettface1` 4~5 色、`spr_sansb_face` 4~5 色、`spr_asgore_brandish` 最多 18 色 | 整页裁切 + 肉眼确认 |

### 6.2 有素材但**只有黑白**（如实登记，不造假）

| 来源 | 说明 |
|---|---|
| 黄魂 `spr_portrait_*` 全族 124 个 / 12 角色 | 黑底白线稿，无任何彩色（§3.3） |
| UT `spr_face_undyne0..8` 等 45×38 族 | 结局字幕黑白小头像 |
| UT `spr_floweyface_l` / `spr_vulkinface` / `spr_asgore_face0` | 原作单色 |
| 黄魂 14 张 2 色页 + 5 张退化页（1×1、64×64 渐变条） | 遮罩/图集占位 |

### 6.3 无素材

28 人 D 级（flowery / gerson / mike 等）⇒ 按用户口径 **不动**。

---

## 7. 待用户裁定（一个决定影响 8 个角色）

黄魂 `spr_portrait_*` 是**黑白线稿**这件事，三个走法：

| 走法 | 说明 | 代价 |
|---|---|---|
| **A（推荐，符合"没有的不动"）** | 黄魂肖像**先不动**，登记为"有素材但无颜色"；先做 OneShot 21 人 + UT 彩色脸族 | 黄魂 8 人暂时没有表情 |
| B | 把黑白线稿**直接当表情图用** | 风格突兀，和白彩素材混在一起 |
| C | 继续挖"游戏是不是运行时上色" | 未知，可能挖不出来 |

★ 我给的默认：**A**。理由：用户口径是"齐全的就正常做，没有的不动"，黑白线稿不算"齐全"；
且它和我旧判据的冲突已经在 §3 澄清，不存在"我为了省事跳过"的动机。

---

## 8. 复算命令

```bash
cd code-quality-audit/第190轮-括号转表情/_tools

# ① 先建 D 盘 UTMT 副本（避开 E 盘坏点）
#    见 utmtpath190.py 的 CANDIDATES

# ② 探测 API（确认 ImageMagick + FormatQOI/FormatBZ2）
python utmtrun190.py --pkg D:/_wb_tmp/dw_ut/uty/game.droid --tag hy \
       --csx probe_api190.csx --ev api --want api_probe.txt

# ③ 整页导出（黄魂 117 页 / UT 42 页）
python utmtrun190.py --pkg D:/_wb_tmp/dw_ut/uty/game.droid --tag hy \
       --csx export_pages190.csx --ev pages --want pages.tsv

# ④ 颜色+结构四量统计（验证"有没有丢色"）
python color190.py --tag hy --top 0

# ⑤ 页 → sprite 双向查（防"彩色页 ≠ 我的角色有颜色"）
python pagemap190.py --tag hy

# ⑥ 按 UV 裁切（三道闸）
python crop190b.py --tag hy
python crop190b.py --tag ut
```
