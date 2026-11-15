# 第190轮 · 括号转表情（表情/动作素材普查与还原）

> 用户口径（2026-11-15，本轮八条）
> 1. `不不不，全做，现在一视同仁，不再是主体为ralsei的项目了`
> 2. `反正在原作的解包里应该有全套的，你看一下，都做，没有的也不用改动`
> 3. `我记得你不是在E盘有解包后的文件吗`
> 4. `那齐全的就正常做，没有的不动就好，记住，一定要验证哦`
> 5. **（关键质疑）`有没有可能有些原版头像就是没颜色只是黑白呢`**
> 6. **（看到三版对照后裁定）`ok，按原样来就好`** ⇒ 素材**一个像素不改**
> 7. **（头像底板）`一句话，尽量按贴近原作即可`** ⇒ 纯黑 `#000000`（§9.1）
> 8. **（情绪映射）`还有，难匹配也得匹配，后期微调就好`** ⇒ 永远给一个值，兜底 `neutral`（§10.3）

---

## 1. 摘要

| 项 | 结论 |
|---|---|
| 用户那句质疑 | **成立，而且直接命中我的判据缺陷**（详见 §3） |
| 自写 QOI 解码器 | **整条路走不通，已废弃**（详见 §4.1） |
| 真正的还原入口 | **UTMT 整页导出** `TextureWorker.GetEmbeddedTexture()`，黄魂 **117/117 页全成功** |
| 颜色有没有丢 | **没有**。黄魂 98/117 页真彩色；UT 的 Undyne 脸 4 色、Mettaton 脸 5 色 |
| 有一批图确实是黑白 | **是**。UT 结局字幕脸族、Flowey 脸、黄魂整族 `spr_portrait_*`（详见 §3 实证） |
| 落地形态 | **`original` 按原样**，改像素的 `ink`/`line` 降级为可选（§7.1） |
| 落地规模 | `assets/faces/` **190 文件 / 29 个 id**（expression 164 + portrait 26），五道闸 + 两层独立核验全绿（§7.3–7.5） |
| 新发现的真 bug | 20 个 OneShot 文件全被写成 `portrait.png`（信息丢失），已修 + 加闸⑤钉住（§7.5） |
| 底板裁定 | 用户 `一句话，尽量按贴近原作即可` ⇒ **纯黑** `#000000`（§9.1） |
| 产品侧接线 | **已落地**：sink 吐括号 → 情绪映射 → 别名链 → 按角色取图；NPC 一视同仁；38 条套件全绿（§10） |
| 状态 | 素材 + 接线都完成；一个已知缺口如实登记（未删括号不触发表情，§10.7） |

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

### 3.4 ★★★ C 方案（查"游戏是否运行时上色"）**已闭环：不着色**

用户 2026-11-15 裁定 `C，不行就B` ⇒ 先把 C 挖到底。**挖到了，答案是"不变色"。**

**第一步：修好反编译**（上一版 `dump_code190.csx` 失败的原因）

上一版用 `c.Instructions.ToString()`，在 UTMT 0.9.2 上 `Instructions` 不是带 ToString 反汇编的链表
⇒ 拿到的是类型名 ⇒ **12186 段全部命中 0**，而且异常被 try/catch 吞掉，看起来"跑成功了"。
★ 教训复述：**判据恒空 = 恒真的反面**。0 命中必须先怀疑"我根本没取到文本"。

正确姿势抄自 UTMT 自带 `Scripts/Resource Exporters/ExportSpecificCode.csx`：

```csharp
var ctx = new UndertaleModLib.Decompiler.GlobalDecompileContext(Data);
var st  = Data.ToolInfo.DecompilerSettings;
string gml = new Underanalyzer.Decompiler.DecompileContext(ctx, code, st).DecompileToString();
```

`scan_code190.csx` 实测（黄魂）：

| 指标 | 值 |
|---|---|
| 代码段总数 | **12186** |
| 子代码段跳过 | 1189（`ParentEntry != null`，不能单独反编译） |
| 实际反编译 | **10997** |
| 反编译失败 | **0** |
| 提到 `portrait` 的段 | **258** |
| 提到 `image_blend`/`draw_sprite_ext` 的段 | 1712 |
| 提到 shader/surface 的段 | 255 |
| 耗时 | **1 s** |

**第二步：看绘制代码**（`gml_Object_obj_dialogue_battle_Draw_64`）：

```gml
var portrait_y_disjoint = yy + (sprite_get_height(prt[message_current]) / 3) + 28;
draw_sprite_ext(prt[message_current], prt_animate, portrait_xx, portrait_y_disjoint,
                0.5, 0.5, 0, c_white, 1);        // ← 颜色参数写死 c_white
```

- 颜色参数 = **`c_white`（纯白 = 不着色、不染色）**
- 缩放 **0.5**（110×106 的肖像在屏上只有 55×53 —— 所以是小尺寸线稿图标，不是大立绘）
- 同一段里 `color == true` / `message_col` 那套是**文字**变色，跟肖像无关（别误读）

**第三步：穷举确认**（把所有画肖像的调用都抓出来数）

| 代码段 | 颜色参数 | 次数 |
|---|---|---|
| `obj_dialogue_postfight_flowey` | `c_white` | 3 |
| `obj_dialogue` | `c_white` | 3 |
| `obj_dialogue_battle` | `c_white` | 2 |
| `obj_dialogue_nongui` | `c_white` | 2 |
| `obj_dialogue_battle_asgore` | `c_white` | 2 |
| `obj_dialogue_flowey_ending` | `c_white` | 2 |
| `cutscene_dialogue_chujin` | `c_white` | 3 |
| `battle_dummy_training_parent` | `c_white` | 1 |
| `quote_battle_ffstarlo` | `c_white` | 1 |
| **合计** | **全部 `c_white`** | **19** |

⇒ **19/19 处全是不着色。黄魂在原作里就是黑白线稿肖像。**

★★ 这条反而把 B 方案的性质改了：B 不是"画质降级的退路"，而是**忠于原作**的走法
（对齐项目口径「一切根据原作」）。

★ 仍未知（不影响结论）：`spr_portrait_*` 为什么不带色（美术风格 / 制作流程），
以及游戏是否在别处对这些 sprite 做了整屏调色 —— 但**对话绘制这条主路径已经确证不着色**。


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

### 4.3 代码反汇编：第一版失败，第二版成功

**第一版 `dump_code190.csx` 失败**：扫 12186 个代码段**命中 0**。
原因：`c.Instructions.ToString()` 在 UTMT 0.9.2 上取不到 GML 反汇编文本
（异常被 try/catch 吞掉，所有 `txt` 都是空串）。

**第二版 `scan_code190.csx` 成功**：改用 UTMT 自带脚本的正确姿势
（`new Underanalyzer.Decompiler.DecompileContext(ctx, code, st).DecompileToString()`），
**10997 段反编译、0 失败、1 秒跑完、命中 portrait 258 段**。
据此拿到 §3.4 的决定性证据。

★ 这两版放在一起就是一条通用教训：**"0 命中"必须先当成"我没取到数据"来处理**，
先证明分母（反编译成功了多少段）≠ 0，再谈命中率。

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

## 7. 裁定结果：**C 已闭环（不着色）⇒ 走 B ⇒ 落地形态「按原样」**

用户 2026-11-15：`C，不行就B` → 看完三种变体对照图 → **`ok，按原样来就好`**

| 走法 | 结论 |
|---|---|
| C（挖运行时上色） | **已闭环**：19/19 处绘制全用 `c_white`，原作不着色（§3.4） |
| **B（黑白线稿直接当表情图）** | **采用**。而且不是退路 —— 原作就是黑白，走 B 才忠于「一切根据原作」 |
| A（黄魂先不动） | 作废 |
| B 的落地形态 | **`original`：一个像素都不改**，直接用原作裁出的像素 |

### 7.1 为什么不转换（三版对照后用户拍板）

我原本默认做 `ink` 变换（黑→透明、白线反相成黑线），理由是"浅色气泡上能看清"。三种形态摆在用户面前后，他选了最保守的一种：

| 变体 | 处理 | 观感 |
|---|---|---|
| **`original`（用户选定）** | **不改**，原像素 | 与游戏内完全一致，不依赖气泡底色 |
| `ink`（我原默认） | 黑→透明，白反相为黑 | 浅底清楚，但角色变剪影，且**已经不是原作观感** |
| `line` | 黑→透明，白线保留 | 保留原作观感，浅底看不见 |

★ 选 `original` 的实质理由：**任何色度变换都是"我替原作做决定"**，与项目口径「一切根据原作」冲突。副作用（黑底/看不见）属于 **UI 排版要解决的问题，不该由改素材来兜**。

### 7.2 ★★★ 原样落地后的新发现：黄魂肖像**本身就是三套底色**

改完 `original` 再出图才发现，`spr_portrait_*` 并不是同一套东西。只看 `opaque_pct` 会误判成两档，把"前景是黑"和"背景是黑"混为一谈，所以补测了**前景像素平均亮度**与**白线占前景比例**：

| 组 | 帧 | 不透明 | 前景亮 | 白线占前景 | 形态 |
|---|---|---|---|---|---|
| `hy_axis` / `hy_ceroba_ketsukane` / `hy_chujin_ketsukane` | **79** | 100.0 | 71~88 | 28~34% | **黑底 + 白线**（整格黑矩形，白线只占 1/3） |
| `hy_ace` / `hy_mooch` | **21** | 50~62 | 145~175 | 57~69% | **透明底 + 黑填充带白线**（剪影质感，两种颜色都看得见） |
| `hy_ed` / `hy_moray` / `hy_starlo` | **64** | 32~45 | **255** | **100%** | **纯白线 + 透明底**（前景**一个暗像素都没有**） |

`79 + 21 + 64 = 164`，三套都是从我同一批整页直接裁的，**不是处理差异，是原作本身如此**。

后果很具体（用 `bubble_ctx.png` 实测过）：

- 79 帧贴浅色气泡 ⇒ **一块黑牌**，边界明显、突兀；
- 21 帧贴浅色气泡 ⇒ 黑剪影 + 白边，勉强能看，但和第一组观感不一致；
- **64 帧贴浅色气泡 ⇒ 什么也看不见**（纯白线落在浅底上）—— 这是**功能性缺陷**，不是审美问题。

⇒ **素材侧不修**（修了就偏离用户裁定的「按原样」）。结论落到 UI：**气泡里的肖像格必须给深色底板**，三套素材才都能看清、观感也统一。这一条作为待确认项列入 §9。

### 7.3 B 已落地：`ralsei_pet/assets/faces/`（190 个文件 / 29 个 id）

脚本 `build_faces190.py`（默认 `MODE='original'`），产物在 `ralsei_pet/assets/faces/`：

| 类别 | id 数 | 文件数 | 说明 |
|---|---|---|---|
| `expression`（能驱动情绪） | **8** | **164** | 黄魂 91 种情绪 × 帧。ace 6 / axis 9 / ceroba 28 / chujin 8 / ed 4 / mooch 8 / moray 6 / starlo 22 |
| `portrait`（只能当身份卡） | **21** | **26** | OneShot 424×276 彩绘整图（含背景、100% 不透明） |
| **合计** | **29** | **190** | manifest 在 `assets/faces/manifest.json`，逐条带 `variant: original` |

**五道闸（全绿）**：

| 闸 | 判据 | 结果 |
|---|---|---|
| ① | 磁盘文件数 == manifest 条目数 | 190 / 190 |
| ② | **原样保真**：落盘文件**读回**后逐像素 == 源图 | 抽检 164 张，不一致 **0** |
| ③ | 每个产物都能重新打开、尺寸与 manifest 一致 | 不一致 **0** |
| ④ | 黄魂 8 个 id 全在；OneShot 21 个 id 全在 | 8/8 · 21/21 |
| ⑤ | `emotion` 不得退化成 kind 字面量；同 id 下文件名不得重复 | 问题 **0** |

**闸② 的负控制**：人为改 1 像素 ⇒ 能抓出。不做负控制就不知道这道闸是不是恒真。

★ **闸② 差点写成恒假判据**：第一版是 `im.tobytes() != out.tobytes()`，而 `MODE=='original'` 时 `out` 就是 `im` 本身 ⇒ **同一对象比自己，永远相等**，这道闸等于不存在。改成**读回落盘文件**再比，顺带能抓 PNG 保存的位深/调色板损失。

★ **闸② 更早还写错过一次（ink 时代）**：`to_ink` 的 alpha 是连续值 `L`，闸却用 `a > 0` 数"不透明" ⇒ 必然比 `L>=128` 多，报 15 张假红。教训：**闸的判据必须和被测实现同口径**。

### 7.4 ★★ 独立核验 `verify_faces190.py`（不信上面那五道闸）

五道闸是"自己验自己"（比的是自己内存里那一对 src/out）。另开一条路，**只读仓库产物 + 只读原始素材**，独立写一份 `ID2ROLE` 映射（故意不复用 build 脚本的，复用就变成同一假设验两遍）：

| 层 | 判据 | 结果 |
|---|---|---|
| L1 | 仓库 png == 中间裁切件（全量 190） | 一致 **190** / 不一致 **0** / 缺 **0** |
| L2 | 仓库 png == **从原始整页现场重裁**（跨过中间产物，端到端 164） | 一致 **164** / 不一致 **0** |
| L3 | 负控制：改 1 像素后必须判"不同" | 判为不同 **OK** |

★ L2 才是真独立：中间件被人动过、或页序变了，L1 绿 L2 会红。

### 7.5 ★★ 这一版抓到的真 bug：20 个 OneShot 文件全叫 `portrait.png`

`os_plan.append((OS_MAP[base], 'portrait', ...))` —— 第二格本该放**文件名 base**，却塞了 kind 字面量。后果：

- 20 个角色目录里全叫 `portrait.png`；
- manifest 的 `emotion` 字段退化成 `'portrait'`，**人名信息丢失**；
- 五道闸里 **①③④ 全部照样绿**（文件数对、能打开、id 全在）—— 只有独立核验 L1 因为"源路径推不出来"才炸出来。

⇒ 修：第二格改回 `base`；并**新增闸⑤**把这类静默退化永久钉住（`emotion` 不得等于 kind、同 id 下文件名不得重复）。

### 7.6 如实跳过

55 帧有肖像但项目里没有对应 id —— `kanako` / `asgore` / `alphys` / `fchujin`
（黄魂里的 asgore/alphys 与项目 `ut_asgore`/`ot_alphys` 不是同一个角色，不许硬挂）。
按用户口径「没有的不动」，这 55 帧**不进 assets**，但已如实登记在 manifest 之外的本报告里。



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

# ⑦ 落进仓库 assets/faces（默认 original，五道闸）
python build_faces190.py --dry     # 先看计划表
python build_faces190.py           # 正式落盘

# ⑧ 独立核验（L1 全量 + L2 从整页重裁 + L3 负控制）
python verify_faces190.py
python verify_faces190.py --l2all  # L2 全量，最硬

# ⑨ 用户预览图（落 D:\_tmp190\preview，不进仓库）
python preview190.py
```

---

## 9. 底板裁定（已定）

### 9.1 气泡里的肖像格用**纯黑底板** —— 用户已裁定

**这不是要不要改素材的问题，素材保持原样不动**。是 UI 排版问题，起因是 §7.2 那个实测：

| 组 | 帧 | 贴浅色气泡的实际后果 |
|---|---|---|
| 黑底白线（axis / ceroba / chujin） | 79 | 一块黑牌，边界明显 |
| 透明底黑剪影（ace / mooch） | 21 | 能看，但和上面观感不一致 |
| **纯白线透明底（ed / moray / starlo）** | **64** | **完全看不见** |

用户 2026-11-15 裁定：**`一句话，尽量按贴近原作即可`** ⇒ **纯黑底板**（方案 B）。

理由不只是"贴近原作"：UT/DR 的表情框本来就是**黑底 + 白边 + 方角**，
而黑底同时解决三套底色 —— 79 帧的黑矩形融进底板、64 帧的白线清晰、21 帧的剪影正常。
落地见 §10.6（就是一行 CSS）。


### 9.2 产品侧接线的改造点（**已落地，详见 §10**）

`modules/event_speech.py:773 strip_action_parentheticals(text)` 原本**只返回删完后的字符串**，
被删掉的括号内容**没有任何出口** ⇒ 加可选 `sink`（返回值语义不变，对既有调用方零影响）。
实现在 §10.2。

~~匹配不上的只做动作、不换表情~~ —— **这条已作废**：用户后来补了一句
`还有，难匹配也得匹配，后期微调就好` ⇒ 改成**永远给一个表情**，兜底 `neutral`（§10.3）。

**为什么词表可以很小**：第188轮那 231 轮实测里，被删的括号形态只有 **16 种**
（`（笑）`42 次 / `（微笑）`39 / `（NYEH HEH HEH!）`19 / `（苦笑）`6 / `（思考片刻）`3 …）
⇒ 关键词匹配足够，不需要大词表。

### 9.3 本轮回归

`code-quality-audit/regress/run_all.py`：**187 套件 / PASS=8260 / FAIL=0**，
只有 `check99` 判 `IDENTICAL*`（真机 log 交错产生的空行噪声，剔空行后逐行全等，**未刷基线**）。
⇒ 190 个素材替换 + 产品侧接线**没有**撞坏任何既有判据。

★★★ **中途真撞了一次，记在这里**（`check188`/`check189` 双红）：己闸要"不删也记一笔"，
第一版我把 `_ANY_PAREN_RE.sub` 的回调从模块级 `_rescue_voice` 包成了函数内闭包
`_rescue_voice_note`。行为是对的，但**名字变了**：

- `check189 D3` 明写「`_rescue_voice` 是**模块级**函数（不是函数内闭包 —— 判据与打桩都靠它）」
- `check188 D3` / `check189 D2` 按 `_subs` 里的**回调名**判闸序
- `_tools/probe188.py` 靠 monkeypatch `E._rescue_voice` 关闸做对照

⇒ 三处静默失效。**修法不是改老锁**（那三处都是第189轮真场景下锁住的口径），
而是**把名字还回去**：用例**先 `finditer` 扫一遍记账、再裸 `_ANY_PAREN_RE.sub(_rescue_voice, text)`**。
语义与顺序一字不变（己闸仍第一个跑、仍不删内容），`sink` 也照样拿到
`（NYEH HEH HEH!）` 这条信号（`check190 A5` 钉住）。

★ 六个套件（`dialog_turn52` / `check132` / `check133` / `check182` / `check185` / `check186`）
判 DIFF 的原因全是**回显值变了**：我在 `main.py` 加了几行 import 与一个方法 ⇒ 它们的
`idx(commit)=16`、`掷骰@7332`、导入清单这类**打印出来的行号/列表**跟着漂。
断言本身 `PASS`，按口径 `--only <id> --update` 重建基线（**判据一条没动**）。

---

## 10. 产品侧接线（**已落地**）

用户两条补充口径：
- 头像底板：`一句话，尽量按贴近原作即可` ⇒ **纯黑**
- 映射策略：`难匹配也得匹配，后期微调就好` ⇒ **永远有值，不许空着**

### 10.1 整条链（四段，每段都能单独验）

```
台词「（苦笑）算了」
   │  event_speech.strip_action_parentheticals(text, sink=acts)
   ▼  acts = ['苦笑']                      ← ① 删掉的必须**吐出来**
   │  event_speech.acts_to_emotion(acts)
   ▼  emo = 'sad'                          ← ② **永远有值**（兜底 neutral）
   │  main._clean_ai_reply ⇒ self._pending_face_emotion
   │  dialogue_ui.show_dialogue / NPC 分支 pop_pending_face_emotion()
   ▼  dialogue_ui._char_face_candidates('sad')
   │     = ['sad','big_sad','downer','sorrowful','disappointed','mourning','normal','neutral','default','plain']
   │  sprite_loader.get_face_for(char_id, name) 逐级试
   ▼  贴到 face_label（**黑底** #000 白边 2px，84×84）
```

### 10.2 ① sink：删掉的括号必须有出口

改动只有一处签名：

```python
def strip_action_parentheticals(text, sink=None):
```

**返回值语义完全不变**（仍是字符串）⇒ 全部既有调用方零影响。
`sink` 只在**每道子闸真的删了东西**时 append —— 不能在函数末尾统一"猜"，否则拿到的是
猜出来的旁白，不是实际删掉的。

★ 己闸（发声直显 `（NYEH HEH HEH!）`）原本是"转译不删"，这轮让它**也记一笔**：
那正是 asgore 的招牌大笑，不记就等于把最典型的一条信号丢了。

★★★ **实现方式有坑，写清楚免得下次再踩**：不能把回调包成闭包去记账。

```python
# ✗ 第一版（真撞了 check188/check189 两条老锁）
def _rescue_voice_note(m):
    out = _rescue_voice(m)
    if out != m.group(0):
        _note(m.group(0))
    return out
t = _ANY_PAREN_RE.sub(_rescue_voice_note, text)

# ✓ 定稿：先扫一遍记账，再**裸名**交给 sub
if sink is not None:
    for _mv in _ANY_PAREN_RE.finditer(text):
        if _rescue_voice(_mv) != _mv.group(0):
            _note(_mv.group(0))
t = _ANY_PAREN_RE.sub(_rescue_voice, text)
```

理由三条，缺一条都不行：`check189 D3` 钉「`_rescue_voice` 必须是**模块级**函数」；
`check188 D3`/`check189 D2` 按**回调名**判闸序；`probe188.py` 靠 monkeypatch
`E._rescue_voice` 关闸做对照实验。包一层闭包，这三处**全部静默失效**。

★ 空括号 `（）` / 纯空白 / 纯标点**不记**（负控制：不该记的别记）。

### 10.3 ② 情绪映射：顺序即优先级

`ACT_EMOTION_RULES` 是**有序**规则表，`re.search`（不是 `match`，「不好意思地笑了笑」的情绪词不在开头）：

| 靠前 | 结果 | 为什么要压过谁 |
|---|---|---|
| `苦笑|强颜|勉强…笑` | `sad` | 必须压过 `笑`→smile |
| `尴尬|不好意思|讪` | `shy` | 同上 |
| `大笑|狂笑|哈{2,}|HEH|NYEH` | `laugh` | 同上 |
| …（哭/怒/惊/害羞/担心/思考/困惑/严肃/累/兴奋/感激/得意/受伤） | | |
| `笑|微笑|含笑|轻笑` | `smile` | 笼统规则，排最后 |
| 全不中 | **`neutral`** | 兜底，**不许空** |

### 10.4 ③ 别名链：本轮最难的一环（踩了三个坑）

`_char_face_candidates(emo)` 把情绪键展开成"这个角色**可能**有的名字"，供逐级试。

**坑 1：不能只认 `normal`。** 实测原作各家"正常脸"名字不统一：

| 角色 | 正常脸叫 | 情绪数 |
|---|---|---|
| `hy_ace` / `hy_ed` | `normal` | 6 / 4 |
| `hy_ceroba_ketsukane` | `default`（也有 neutral） | 28 |
| **`hy_chujin_ketsukane`** | **只有 `neutral`，没有 normal/default** | 8 |
| `hy_mooch` / `hy_moray` / `hy_starlo` / `hy_axis` | `normal` | 15 / 12 / 44 / 9 |

⇒ 候选链末尾固定补 **`normal, neutral, default, plain`** 四个，缺一个 chujin 就永远贴不出图。

**坑 2：`get_face_for` 的缓存键必须带角色 id。** 不同角色的 `normal.png` 是不同图片，
只用文件名当键会**串图**。

**坑 3（最后一道保险）：** 候选链一路没命中时，调 `any_face_for(char_id)` 拿该角色**任意一张**。
宁可这张表情不够准 —— 用户已明确说会后期微调；而贴不出来会让头像**停在上一个角色脸上**，
那是明显的错。

### 10.5 ④ NPC 也换表情（旧口径作废）

`dialogue_ui.add_dialogue` 的 NPC 分支原来写着：

> NPC 的话**直接落历史区**：不走打字机、不换表情 ——
> 打字机与表情位都是 **Ralsei 的显示位**，借来显示别人会看起来像他在说。

**这条口径的前提是"只有 Ralsei 有表情素材"**。现在 8 个黄魂 + 21 个 OneShot 角色
都有自己的脸，前提不成立 ⇒ 改掉。用户同轮原话：
`一视同仁，不再是主体为 ralsei 的项目了`。

★ 打字机**仍然不借**（那是 Ralsei 的逐字节奏，与贴图无关），只借贴图。

#### ★★★ 10.5.1 差点只改了一半：NPC 台词**不走** `add_dialogue`

第一版只改了 `add_dialogue` 的 NPC 分支。后来查调用点才发现：

```
add_dialogue("ralsei", ...)   ← 只有 4 处调用，speaker 全是 "ralsei"
add_npc_line(label, text)      ← NPC 台词的**主路径**（npc_speak 回调走它）
```

也就是说 `add_dialogue` 的 NPC 分支要 `_is_npc_speaker(speaker)` 为真才走，而
**实际没人这么调** ⇒ 只改那里等于没改，NPC 头像永远不变。

⇒ 补 `add_npc_line(label, text, char_id=None)`，并在 `npc_speak` 的回调里传 `npc_id`。
这一条写成了判据 **D4b**（AST 查签名 + 查调用处真的传了），否则以后有人改回去不会报错。

### 10.5.2 ★★ Ralsei 自己那条链也得补，否则等于接了一半

`ACT_EMOTION_RULES` 吐的是**短键**（`smile` / `laugh` / `cry` / `love` / `smug` / `hurt`），
而 Ralsei 的 `_FACE_MAP` 原来只有长键（`happy_very` / `sad_force_smile` …）。

`_resolve_face_name` 对未知键的兜底是**拼 `face_` 前缀** ⇒ 会去找 `face_smile.png`、
`face_cry.png` 这种**不存在的文件** ⇒ `set_face` 查出缺失 ⇒ 回退 `face_normal`
⇒ **Ralsei 括号里的笑被吃掉**，NPC 那条链接得再好，主宠身上是白接的。

⇒ 补 6 条映射（**全部指向已存在的素材**，不新建文件）：

| 通用键 | → Ralsei 素材 |
|---|---|
| `smile` | `face_normal_smile_little` |
| `laugh` | `face_happy_very` |
| `cry` | `face_sad with a little hopeless` |
| `love` | `face_shy with touched and happy` |
| `smug` | `face_happy and playful` |
| `hurt` | `face_a little sad` |

其余 12 个通用键（neutral/happy/sad/angry/surprised/shy/worried/thinking/confused/
serious/tired/excited）本表早有，不重复登记。

判据 **C6** 拿 `ralsei_face/` 的实际文件清单验：18 个通用键**全部**能落到真实 png（50 个素材，0 落空）。


### 10.6 ⑤ 纯黑底板 = 一行 CSS

```css
QLabel { background-color: #000000; border: 2px solid #ffffff; }   /* 原为 transparent */
```

这就是 §7.2 那 64 帧"纯白线看不见"的**全部解法** —— 素材一个像素没动。

`preview_box190.py` 离线复现了渲染规则（84×84 / 2px 白边 / 784 居中 KeepAspectRatio），
产物 `face_boxes.png`：8 个角色黑底上**全部清晰可辨、无空格**。

### 10.7 已知缺口（如实登记，本轮**不做**）

`（尴尬地笑了笑）` 这类**不被删**的括号**不触发表情**。

原因：第188轮锁 `A22g` 明确"裸「笑」故意留在 `_ACTION_VERBS` 之外"（`（笑不出来）`
会被误伤），戊闸的 `_BARE_LABEL_RE` 也只认"整段是标签"。动它要改已锁定的护栏，
需要单独拍口径 —— 不在本轮顺手扩大改动面。

### 10.8 本轮套件 `check190.py`（57 条，全绿）

| 段 | 条数 | 守住什么 |
|---|---|---|
| A sink 通道 | 6 | 删掉的能吐出来、返回值不变、空括号不记 |
| B 情绪映射 | 10 | 具体规则压过笼统规则、兜底不空 |
| C 别名链 | 6 | 末尾四个底图名、未知键不吞、**Ralsei 侧 18 键全覆盖** |
| D 接线 | 8 | AST 找 `sink=` 关键字；**NPC 主路径 `add_npc_line`**；底色是 #000 |
| **E 素材可达** | **5** | **8 id × 18 键笛卡尔积全部能落到真实图** + 端到端台词→png |
| G 旁白/三类分流 | 14 | 能不能换表情决定"换脸"还是"说旁白"；场景/内在两类**不许**冒旁白 |
| **H 表演层** | **5** | 双通道分离 · 动画名真实存在 · 定时器驱动 · 外壳结构 · 钩子接线 |
| F 自检 | 3 | 条数 / 只读 / `[PASS]` 字面量 |

★ E 段是核心：它不测"函数返回了值"，而是拿**真实 manifest** 验"一定贴得出图"
—— 这才是"难匹配也得匹配"的硬证据。E5 更进一步：拿 5 句真实形态的台词，
一路跑到 `os.path.isfile(那个 png)`。

★ H2 是这轮最有价值的一条：**动画名写错时，`play_animation_once` 只静默返回
False**，任何行为断言都看不出来（看起来"在演"，其实永远不演）。所以它直接拿
`assets/animations.json` 的 115 个组名核对。

---

## 11. 续：没有表情可用的括号 → 交给旁白（**已落地**）

用户口径：

> `括号里的东西有些没有表情的那就用旁白，你还记得旁白是啥，对吧，
> 到时候就单独把那些括号交给旁白说就好`
>
> （追问"什么算没表情"）`就是没表情素材可以用来当做那个括号里的东西用的时候`

### 11.1 判据是**素材层**，不是语义层

关键决定：**"有没有表情"看的是这个角色有没有那张图，不是"这段括号像不像表情"**。

```
「（苦笑）算了」 × mooch      → mooch 没有 sad/tired 系的图 → 旁白
「（苦笑）算了」 × chujin     → 有 big_sad（在 sad 的别名链里）→ 换脸
```

同一句话、两只角色、两种结果 —— 这是"素材层判据"最直观的证明，
`e2e_narr190.py` 的 CASES 就是照这个矩阵写的（期望值全部按真实 manifest 算）。

### 11.2 一个必须想清楚的边界："正常脸"不算有表情

用户说的是"没表情素材**可以用来当作那个括号里的东西用**"。
所以候选链走到 `_CHAR_FACE_BASE_NAMES`（`normal/neutral/default/plain`）就**中断**：

```python
for nm in _char_face_candidates(face_type):
    if nm in _CHAR_FACE_BASE_NAMES:
        break                      # ★ 再往下都是底图，命中也不代表"有这张脸"
    if has_f(char_id, nm):
        return True
```

唯一例外是**规则显式命中 `neutral`**（`点头|摇头|温柔|安心|平静|放松|咳`）——
那时正常脸就是它的正解，不该多冒一行旁白（`G6` 守这条）。

### 11.3 为什么要第二个出口，而不是改 `act_to_emotion`

`act_to_emotion` 的"**永远返回非空**"是 `check190 B` 段 10 条老锁钉住的
（用户口径"难匹配也得匹配"）。要判"有没有真匹配到"，只能加**第二个出口**：

```python
def act_to_emotion_ex(act):     # → (emo, hit)
def act_to_emotion(act):        # 老接口，语义一字未动
    return act_to_emotion_ex(act)[0]
```

### 11.4 旁白长什么样

无 `▸`、无说话人、斜体、`#a9a29a`。有 `▸` 就成了"有个名字叫旁白的人"（`G7` 守）。

★ 顺序：**旁白在台词之前**（括号是动作，动作先于说话）。这一条我用**像素**验过：
`order190b.py` 按颜色扫图，旁白 `y=63..75`、台词 `y=86..99`。
（中途我看图看反过一次，所以最后改成按 RGB 判定，不靠眼睛。）

---

## 12. 三类括号的边界（**已落地**，含一次返工）

用户先后三条口径，把它们逼成了三类：

| 类别 | 例 | 台词留字 | 出旁白 | 留时间 |
|---|---|---|---|---|
| 场景交互 | 推开门 / 走到窗边 / 拿起杯子 | ✘ | ✘ | — |
| **内在活动** | 想了想 / 犹豫 / 沉默片刻 | ✘ | ✘ | ✔ |
| 外在表现 | 叹气 / 苦笑 / 蹲下 / 叉腰 | ✘ | ✔ | ✔（旁白本身是节奏） |
| 其余（原样保留） | 笑不出来 / SANS! STOP BEING LAZY! | ✔ | ✘ | — |

### 12.1 返工记录：我把"不用连想一想都转"读错了

第一版我把它读成"**原样保留在台词里**"，并写进了报告和注释。用户当场纠正：

> `不不不，想一想这类的不留，旁白也只是负责，动作类，
> 像是每一个想一想都播那就太麻烦了`

正确理解是：**连字都不要（删掉）**，而且**不许**冒旁白。
"太麻烦了"指的不是"留着麻烦"，而是"每句都播一屏太吵"。

### 12.2 实现：三张表 + 一个出口分流

```
_SCENE_ACT_VERBS   场景交互  → 删，不说
_INNER_ACT_VERBS   内在活动  → 删，不说（但有 pause 通道）
_SELF_ACT_VERBS    外在表现  → 删，说成旁白
```

**为什么不并进 `_EXT_ACT_DENY`**：那张是否定表（命中 = "不认成动作"），
命中后括号**原样留在台词里**；这次要的是**删掉**，方向相反。

**为什么不在各闸里逐个判内在**：内在词会从甲/丙/戊**任意一道**漏出来
（`犹豫`走戊、`沉默片刻`走丙、`想了想`走末闸）。逐个改闸等于留一堆漏点，
所以放在**唯一出口 `_note()`** 里分流 —— 天然全覆盖。

### 12.3 顺带修掉的同族缺口

`（点了点头）` / `（叹了口气）` 这类 **V了V** 形态：`点头` 被 `了` 拆开，
任何表都拼不上，原样显示给用户。补了 `叹了口气|皱了皱眉|抿起眉头` 等固定短语 +
`_SELF_ACT_VERBS` 单列条目。

---

## 13. 表演层：留时间 + 用动画（**已落地**）

用户两条口径：

> `但一定要留时间如果有，那就用动画表示哦`
> `角色做出表情的时候原作有些时候也会配合一些外部动画来加强表示`

### 13.1 内在活动：字删了，但时间要留

两个**分开**的通道（合成一个就分不清"该说话"还是"该停顿"）：

```python
strip_action_parentheticals(text, sink=acts, pause_sink=inner)
```

- `sink` → 换表情 / 说旁白
- `pause_sink` → 只用来**留时间**

`main` 侧：`_pending_inner_acts` + `peek/pop_pending_inner_acts()`。
`_event_say` 三个前置条件缺一不可：真有内在活动 / 不是 streamed / 当前没在打字。
停顿 = `min(420ms × 条数, 900ms)`。

★ **为什么用 `QTimer.singleShot` 而不是等动画播完的回调**：
动画可能被 `change_animation` 的状态锁拦下（`play_animation_once` 返回 False），
回调就永远不来 ⇒ **台词永远不显示**。沉默是这里最坏的失败方式。
定时器不依赖动画是否播成功，最坏只是"停顿有了、动画没演"。（`H3` 守这条）

★ 动画选 `look_up`：`animations.json` 115 组里**没有** `think`，逐个比对后
最贴"抬头发呆"（4 帧 × 0.13s ≈ 0.52s，与 420ms 同量级）。

### 13.2 表情配外部动画

只给 4 个强情绪配、三重节制：

| 节制 | 值 | 为什么 |
|---|---|---|
| 只 4 个情绪 | `happy→laugh` / `surprised→surprised` / `cry→cry` / `sad→sad` | 用户说"有些时候"，每个表情都抖反而吵 |
| 同表情冷却 | 2.5s | 连聊三句不该抖三次 |
| 表情没变不演 | — | 缩放重贴、连续同情绪都不该触发 |

★ 实现结构：`set_face` 是**外层壳**，先 `_set_face_apply()` 贴图，再
`_maybe_expression_anim()` 通知宿主。不能把动画直接塞进内层 —— 内层有**两条贴图
分支**（角色素材 / Ralsei 老路径），逐个加调用迟早漏一条。

★ 只给**宠物本体**演：`char_id` 非空直接跳过。NPC 说话换的是 NPC 的脸，
让 Ralsei 的身体替别人做动作是错的。

---

## 14. 待办：一框一条（**未开工**，等口径）

用户：`对话框也是要原作的哦，别一个对话框装n多条信息` ⇒ 追问后定为
`原作不就是一句话一个框吗，按原作`，且旁白**单独一页**。

- **NPC 侧已改**：`add_npc_line` 每句清空历史区（`_npc_line_begin()`）——
  一个框只装当前这一条。这是"擦掉前一句"，不是"翻过去"。
- **Ralsei 侧未改**：现在是第 52 轮的"一轮一条、同拍多句并排"，
  `dialog_turn52` 的 `H4` 明确钉着"同一拍的连续两句都在（不丢信息）"。

彻底按原作要引入**翻页队列**（页只增不删 + `_page_idx` + 单击/Enter/自动推进），
方案已给出但**未动手** —— 它会改动第 52 轮的既有契约，需要单独一轮做，
不能和本轮的括号分流混在一起。

---

## 15. 续三①：口癖从「配额」改成「看当下场景」（**已落地**）

用户逐字：`不必要把口癖卡那么死，主要是符合当下场景`

### 15.1 先纠一个我自己的误读

"卡得死"不是"用得太频繁"，是**到点就交作业**：不管对方在说什么，都要把口头禅塞进去。
所以这活不是调频次，是换判据 —— 从**数字**换成**场合**。

### 15.2 为什么必须连"强化语"一起删

第189轮 §10.1 已经量过，直接引账（不是我的判断）：

- 只加频次句时，`ot_kidd` / `ut_monster_kid` 的 `Yo` 命中 **48/48 → 24/24，一个不差**；
- 根因是同一份人设里还留着「这是你的**标志**」「**不要忘记**“Yo!”」「最**标志性**的口头禅」
  ⇒ **强化语的压力压过频次句**；
- 真正生效的是 `welp` 那条写法：「不是每轮都要来一次，多数轮次你只是正常说完就停」——
  **没有数字，但有行为描述**。

⇒ 本轮口径：**删强化语 + 配额换场景 + 每份仍留一条行为上限**。
最后那条是本次的底线：**放松 ≠ 放任**（`check190b B3` 逐份点名钉着）。

### 15.3 落点

| 位置 | 改法 |
|---|---|
| `npc_persona.SPEAK_RULES` | 新增两句，插在 `PERSONA_TONE_HUMAN` **之前**（它要当真后缀，`check113h A2` 守着）⇒ machine 档 `replace()` 掉四句人性话后这条仍在 |
| `asgore` | `Howdy` 配额 → 「有人进来打招呼的时候…看场合，招呼打过了就不必再带」；台词段的「只偶尔用，别每轮都拿它开场」→「是打招呼时的话」 |
| `lancer` | 删「**标志性**笑声」；`本大爷` 删「十句里一两句」；「你**经常**说出…」→「你自我介绍时会说…」 |
| `ot_kidd` | 删「**经常**用 Yo 作为**口头禅**」；两处配额改场景；删「这是你的**标志**」「**不要忘记**…**最标志性**」；补一条中性正例 |
| `ut_monster_kid` | 同上三处 + 「一轮里一两次就够」删除；补一条中性正例 |
| `ot_muffet` | `亲爱的/小可爱`：「十次里一两次」→「招呼客人的时候会叫…但不是每句都带——多数句子直接说事」；删「**经常**…**标志性**声音，你会在句子开头、中间或结尾笑出来」（这条本身在鼓励高频）；删「**不要忘记**…**最标志性**」 |
| `ot_sans` / `ut_sans` | 「一轮里一两个就够」→「不是每句都要塞一个」；删「这是你的**标志**，也是你的保护色」（**保护色留下**）；删「**不要忘记**你的笑话…这是你的**标志**」 |

★ 中性正例用的是「嗯，好啊。」「那我们现在去吗？」——第189轮 §9.1 的 A/B 已证
**例句才是杠杆**，而含口癖的例句越多，命中率越高。

### 15.4 施工事故：行内替换工具把 7 份人设全写成了 LF

第189轮 §6.2 同款。`core.autocrlf = true`（仓库存 LF、工作区出 CRLF）⇒
全 LF 会让 `sha256 == sha256_lf`（正常应当不同），`_personas.json` 的派生口径就乱了，
下次谁 `checkout` 一份干净工作区，又会变回"不同" ⇒ **假回滚**。

- 实测改前每份的 bare-LF **都连续落在文件尾部**（拿未改的 `susie.txt` 验证：
  bare LF 行号 109~117，正是尾块那一段）⇒ 重建规则是「前 (n−1−K) 个分隔符 CRLF，
  最后 K 个 LF」，K 逐份实测：`asgore/lancer=9`、`ot_kidd/ut_monster_kid/ot_muffet=10`、
  `ot_sans/ut_sans=8`。
- ★ 不套用 `fixeol189.py` 的 `body + '\r\n\n' + tail` 公式：那份只有 asgore 一份（K=9），
  套上去会把 `ot_kidd` 那份多出的空行抹掉。工具 `_tools/fixeol190.py`（幂等 + 三条自证）。
- 修完复核：7 份的 `CRLF/bareLF` 与改前**逐份相同**，`git diff --numstat` 只有 2~5 行/份
  （不是整文件重写），`sha256 != sha256_lf`。

### 15.5 判据：`check190b` **17 条**

A 规则面 5 · B 人设面 5 · C 索引面 1 · D 负控制 3 · E 自检 3。

★★ 本套件自己踩了两个坑（都留在注释里，也都在变异里复现过）：

1. `NEW_RULE` 两半第一版**都取自同一句**，于是"删掉第二句"照样绿（M2 实测）；
2. `A3/A4` 第一版判的是**常量自己**而不是文件 ⇒ 恒真 —— 往新句里塞「过度」、塞一条引号例句
   根本不影响它们（M4/M5 全绿才暴露）。现在按语义关键词从 `SPEAK_RULES` 的值里捞"新增段"再判。

变异 **11/11 全抓**（`mutate190b.py`，每条断言"红数 >0 且 <17"，整文件还原并核 sha1，双跑一致）。
其中一个"无害变异"第一版拿"人设里加两个字"，实测红 C1 —— 那是**正确**的
（改了人设字节却没重算 `_personas.json`），**用人设字节做无害变异本身就是错的夹具**，已换成改注释。

### 15.6 连带刷新（都是"引账"，不是调判据）

`model_conc57 A9` avg 7634→7633 · `check113 C2b` 偏移 +10 · `check113g A1` 值 372→443、
`A7 persona@269→340` · `check113h A2` rules 372→443、`A7` human 557→628 ·
`check134 B1b` prompt 5312→5383。全部是"规则变长"的必然结果，逐条看过 diff 后
`--update` 刷基线（**在默认环境下刷**，没加 `QT_QPA_PLATFORM`）。
`check81 G5` 先红后绿 —— 那条判据正是"新套件必须固化进基线"，`--update` 后消失，属设计预期。

---

## 16. 续三②：NPC 也做动画 —— **前提不成立，未开工，等裁定**

用户：`动画又不是只有 ralsei 有，其他也做`，并选了形态 `原地微动作`。

### 16.1 查证结果（这条必须先讲，它推翻了我的方案前提）

我原方案假设"NPC 有立绘，只是没接动画"。**查盘后这个前提不成立**：

| 查了什么 | 结果 |
|---|---|
| `sprite_label` | 全项目**只有一只**（`main.py:1552`），画的就是桌宠本体 |
| `npc_bodies` | 只有 `npc_placement.Body`（x/y/facing/mode…）—— **纯数据**，没有任何渲染方消费 |
| `assets/sprites/{hy,os,ot,ut}` | 163/81/… 张真 PNG（`dalv_down_0..3` 这类四方向×4 帧），**除了 `ghost/` 之外零引用** |
| 拼名逻辑（`%s_down_%d`） | 全项目搜不到 ⇒ 没人按角色拼过帧文件名 |
| 房间数据 | `assets/npc/_rooms/` 只有一份 `room_memories113.json`，不含角色对象 |

⇒ **NPC 目前在桌面上没有立绘**：他们只有位置（交互命中、相机取景用）和对话头像。
所以"给 NPC 加微动作"不是接一个钩子，而是**先要有一层 NPC 立绘渲染**。

### 16.2 为什么不在本轮顺手做

给 NPC 上立绘会一次性踩到一串已冻结的契约：

- 遮挡与 z 序（第178/179轮：按屏幕 Y、`HWND_TOP == 0` 是假值、"站谁上面"优先于 Y）；
- 2.5D 可站矩形 / DWM 扩展边框（`BBA` 裁定）；
- 相机平移与缩放幂等（§107~110：`scoped_size()` / `ui_scale()` / `resize(整屏)` 的顺序）；
- 世界门控与桌面白名单（`world_gate` 是唯一判据，`DESKTOP_ALLOWED_IDS` 已定"只有主角团+lancer 能上桌面"）。

这已经是"加功能"，不是本轮"放松口癖"的量级。**没动一行代码**，如实登记。

### 16.3 待裁定（三选一，都不在本轮动手）

- **A. 先只做 Ralsei 的补全**：把表情→动画的覆盖面补齐（现有 4 个强情绪 → 按 `animations.json` 的 115 组扩），
  NPC 侧维持"只有表情头像"。最小、无副作用。
- **B. 给 NPC 上立绘**（新功能）：先做"静止站立的一张底板"，再谈微动作。
  需要单独立一轮，并且要为上面那串契约各写一条判据。
- **C. 只做对话期的表演**：NPC 说话时，在对话框那种"角色本体"位置用走路帧做原地微动作
  （不涉及桌面 z 序/相机，只碰 `dialogue_ui` 的贴图位置）。**风险最小的一条**，
  但它演的是"对话框里的立绘"，不是"桌面上的那个人"——形态要和用户再确认一次。

---

## 17. 续三③：翻页队列 —— 仍未开工

见 §14，方案不变，等本轮①②收口后单独做。






