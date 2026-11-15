# 第190轮 · 括号转表情（表情/动作素材普查与还原）

> 用户口径（2026-11-15，本轮六条）
> 1. `不不不，全做，现在一视同仁，不再是主体为ralsei的项目了`
> 2. `反正在原作的解包里应该有全套的，你看一下，都做，没有的也不用改动`
> 3. `我记得你不是在E盘有解包后的文件吗`
> 4. `那齐全的就正常做，没有的不动就好，记住，一定要验证哦`
> 5. **（关键质疑）`有没有可能有些原版头像就是没颜色只是黑白呢`**
> 6. **（看到三版对照后裁定）`ok，按原样来就好`** ⇒ 素材**一个像素不改**

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
| 本轮产品代码改动 | **零**（`ralsei_pet/` 只新增素材，代码一个字节没动） |
| 状态 | 素材已落地并验证；**待确认一项**：气泡里的肖像格是否统一用深色底板（§7.2） |

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

## 9. 待用户确认

### 9.1 气泡里的肖像格要不要统一深色底板

**这不是要不要改素材的问题，素材保持原样不动**。是 UI 排版问题，起因是 §7.2 那个实测：

| 组 | 帧 | 贴浅色气泡的实际后果 |
|---|---|---|
| 黑底白线（axis / ceroba / chujin） | 79 | 一块黑牌，边界明显 |
| 透明底黑剪影（ace / mooch） | 21 | 能看，但和上面观感不一致 |
| **纯白线透明底（ed / moray / starlo）** | **64** | **完全看不见** |

| 方案 | 做法 | 后果 |
|---|---|---|
| **A（我倾向）** | 气泡里肖像格固定一块**深色圆角底板**（如 `#2A2C33`），肖像按原尺寸贴上去 | 79 帧的黑矩形"融进"底板看不出来，64 帧的白线也看得清；观感统一，素材零改动 |
| B | 肖像格用**纯黑**底板 | 同上，且最接近游戏内黑屏观感；但与项目现有气泡配色可能冲突 |
| C | 什么都不做，肖像直接贴气泡 | 64 帧直接看不见 —— 已出图 `bubble_ctx.png` 佐证 |

**默认按 A 推进**（用户回不同意见再改）。等确认后再做产品侧接线（下文 9.2）。

### 9.2 产品侧接线的改造点（已摸清，**未动一行代码**）

`modules/event_speech.py:773 strip_action_parentheticals(text)` 目前**只返回删完后的字符串**，
被删掉的括号内容**没有任何出口**。要"括号 → 表情/动作"，必须让它把删掉的东西吐出来。

最安全的设计（对全部既有调用方零影响）：

```python
def strip_action_parentheticals(text, sink=None):
    ...
    if sink is not None:
        sink.append(被删原片段)   # 只有显式传 sink 的调用方拿得到
    return t                       # 返回值语义完全不变
```

**关键约束**：`sink` 必须在**每一道子闸真的删了东西**时记录，不能在函数末尾统一"猜"
——否则拿到的是猜出来的旁白，不是实际删掉的。

**为什么映射表可以很小**：第188轮那 231 轮实测里，被删的括号形态只有 **16 种**
（`（笑）`42 次 / `（微笑）`39 / `（NYEH HEH HEH!）`19 / `（苦笑）`6 / `（思考片刻）`3 …）
⇒ 关键词匹配足够，不需要大词表。匹配不上的**只做动作、不换表情**（不猜）。

### 9.3 本轮回归

`code-quality-audit/regress/run_all.py`：**186 套件 / PASS=8222 / FAIL=0**，
只有 `check99` 判 `IDENTICAL*`（真机 log 交错产生的空行噪声，剔空行后逐行全等，**未刷基线**）。
⇒ 190 个素材替换**没有**撞到任何既有判据。


