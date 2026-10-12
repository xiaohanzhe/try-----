# 第111轮取证 —— #47「Niko 的家」彩蛋（永远进不去的那扇门）

> 用户口径（逐字，见详版 §109.2）：
> 「**不是进 oneshot 的门，是进 niko 的家，因为原作没有 niko 家的素材，所以才设计了那个彩蛋**」
> 「**永远进不去**」· 三连确认 ①「你确定吗？」 ②「你这样的行为可能导致世界崩坏，你真的确定吗？」
> ③「你真的不再考虑考虑了吗？」· 选项「我再考虑考虑」/「我确定！！！」
> ⇒ 选「我确定！！！」⇒ **伴随三角符文的高级爆炸特效** ⇒ 选项变回「我再考虑考虑」。
>
> 铁律（逐字）：「**一切根据原作**」「**一定要看录像而不是只读后台输出**」「**记得录屏自检**」。

---

## 0. 一句话结论

**已实现并三重验证通过**：#47 彩蛋在两台机器路径上都跑通 —— 离屏判据 **42/42 PASS**（进 G2）、
真机录屏自检 **15/15 PASS**（不进 G2，因离屏 `QMessageBox.exec_()` 会 SIGSEGV）、
**人眼复核 4 张真机抓帧**（三句台词 / 「我确定！！！」按钮 / **透明火球** / 仍停在桌面）。
过程中修掉 **2 个真 bug**（透明层失效、违反 `WindowStaysOnTopHint` 硬契约）＋ **1 条恒真判据**。

---

## 1. 交付物

| 类别 | 文件 | 说明 |
|---|---|---|
| 爆炸素材 | `ralsei_pet/assets/scenes/objs/spr_realisticexplosion_0..16.png` | 17 帧，71×100 RGBA（Deltarune ch1 原作导出） |
| 光门素材 | `…/objs/niko_door_portal.png` `niko_portal_rays.png` `niko_sparkle_blue1.png` `niko_sparkle_red1.png` | OneShot XNB 导出（**已入库，彩蛋门前置光效尚未接线**） |
| 产品代码 | `ralsei_pet/modules/item_interact.py`（+~75 行） | `NIKO_HOME_EGG_TEXT` / `NIKO_HOME_EGG_DOOR` / `NikoHomeDoorProp` / `build_props(on_egg=)` |
| 产品代码 | `ralsei_pet/src/main.py`（+~120 行） | `_niko_home_egg` / `_niko_home_ask` / `_niko_home_explode` + `build_props` 调用点接线 |
| 离屏判据 | `_tools/check111.py` | **42 条**（A1~A14c 结构 / B1~B11 行为 / C1~C3 负控制）→ 进 G2 |
| 真机录屏 | `_tools/rec111.py` | **15 条**（G0~G6）→ **不进 G2**（离屏 SIGSEGV） |
| 素材提取 | `_tools/extract111.py` | **可复现**：自写 XNB 解析器 + UTMT csx 内联（`--run` 开关） |
| 真机抓帧 | `_evidence/frames111/k000~k003*.png` | 4 张，~1.97 MB/张 |
| 门位可视化 | `_evidence/doors_rebuilt.png` | 由真机 `plan_frame` 输出重建（见 §5） |
| 录屏元数据 | `_evidence/rec111_meta.txt` | 15 条判据逐条 + 快照 mark |

---

## 2. 素材提取（端到端可复现）

### 2.1 爆炸帧：UTMT CLI 导 sprite

**正确 API 链**（本轮打通，踩了 4 次编译错才定位）：

```
UndertaleModCli.exe load <data.win> -s <script.csx>
  ← stdout 必须落文件 + stdin=subprocess.DEVNULL；CWD 设 exe 所在目录
csx: EnsureDataLoaded() → Data.Sprites
     s.Textures[i] 是 UndertaleSprite.TextureEntry（★ 不是 TexturePageItem）
       ⇒ 取 .Texture 才得到 UndertaleTexturePageItem
     导出用官方范式：using (TextureWorker w = new TextureWorker())
                    w.ExportAsPNG(pageItem, path, null, padded)
```

★ **不需要自己 `System.Drawing` 剪裁** —— 脚本上下文无 `System.Drawing.Bitmap`
（`CS0234` 就是被这个坑出来的）。改用官方 `ExportSpecificSprites.csx` 的 `TextureWorker`
范式后 **一次成功**导出 17 帧。

★ **导出目录 = `Path.GetDirectoryName(FilePath)`**（即 data.win 旁边）
⇒ 必须对 **data.win 副本**跑（否则污染用户游戏目录）。`extract111.py` 先
`shutil.copyfile(DR_DATA, TMP/data.win)` 再跑 ⇒ 导出落 `TMP/fx_spr`。

**验证**：`爆炸帧: 17 个`。

### 2.2 OneShot 贴图：自写 XNB 解析器

MonoGame `XNA Framework Content` 二进制格式（**从零写出，错了 3 次偏移**）：

```
头 = 'XNB'(3) + platform(1,'d'=Windows) + version(1,5) + flags(1,0=未压缩) + fileSize(4 LE)
     ⇒ 共 10 字节
之后：7-bit 读取器个数 → 每个读取器名是 **NUL 终止 UTF-8 串**（★ 没有长度前缀！）
      → 7-bit sharedResourceCount
      → ★★ 固定还有 4 字节（实测 00 00 00 01）⇒ 对象从 p+4 开始
        （漏掉它会把 width 读成 height —— 本轮连错三次才定位）
Texture2D 对象 = format(int32 BE) + width + height + mipCount + dataLen + BGRA 像素
```

★ **整型是小端 LE**（`struct.unpack_from('<iiii', …)` / `'<i'`；`40 00 00 00` = 64）。
  ⚠️ 别与 PNG 混淆 —— PNG 的 chunk 长度/CRC 才是**大端**（`struct.pack('>I', …)`），
  本仓库 `extract111.py` 自写 PNG 编码时用的是大端，两者**不要搞反**。
  `format=0` 是 `SurfaceFormat.Color`（BGRA ⇒ 导出 PNG 需 R↔B 互换）。
★ 3 次偏移错误的定位手段：**穷举扫 `start in 56..72` × 大小端**，找 `fmt==0 and dlen==w*h*4`
的唯一候选 ⇒ 命中 `start=65` 且**小端** ⇒ 定 `i = p + 4`。

**验证**：5 个 XNB 全部自洽 —— `sparkle_blue1` 64×64 / `door_portal` 192×128 /
`portal_rays` 64×384 / `door_light` 192×256 / `DOORS` 64×128。

---

## 3. 两个真 bug（不是测试问题）

### 3.1 爆炸层是"一整块不透明黑方块"

**症状**：实机抓帧 `k001_boom.png` 首版 = 黑方块盖住屏幕。
**根因**：带 **parent** 的 `QLabel` **不会**让 `Qt.WA_TranslucentBackground` 生效
（Qt 只在**顶层窗口**上应用该属性）。
**修法**：**无 parent 的顶层窗口** + `FramelessWindowHint | Tool | WindowTransparentForInput`
+ `WA_TranslucentBackground` + `WA_TransparentForMouseEvents` + `WA_ShowWithoutActivating`。
**复核**：复跑抓帧显示**带透明的火球**（Minecraft 窗口与壁纸正常透出，见 `k001_boom.png`）。

### 3.2 违反硬契约 `WindowStaysOnTopHint`

**症状**：第一版给爆炸窗口加了 `WindowStaysOnTopHint` ⇒ `round13_build` 的 `E1` 判据报红
（"main.py 里已无 WindowStaysOnTopHint"）。
**修法**：删掉该 flag，改用 `raise_()`。
**教训**：记忆铁律「建楼…**禁 `WindowStaysOnTopHint`**」是硬契约，必须遵守。

---

## 4. 恒真判据陷阱（M3，**判据侧**）

**症状**：`check111` 的 A4~A6 原本用 `'台词' in src_ii`，但三句台词在 `item_interact.py` 里
**各出现两次**（常量定义 + 类 docstring 复述口径）⇒ 变异测试 M3（改常量）**报绿 = 判据失效**。
**修法**：改走 `ast.walk` 找 `NIKO_HOME_EGG_TEXT` 赋值的 `ast.Tuple` **逐元素取值比对**；
A7a/A7b 也改成"AST 字符串常量集合"判据。
**复核**：变异测试 **7/7 全红**且**还原字节一致**。

★ 另修：M2 锚点缺失（`target_scene=None,\n                          routes=None,` 是错的，
实际同一行；且源码 CRLF 而锚点用 LF）⇒ **LF 归一化匹配 + 写回保持原 EOL**。
★ `check111 C1` 报 `IndexError`：`ghost_<uuid>` 场景在路由表无条目 ⇒ 门根本不建（既有契约
"查不到就不建"）⇒ 断言改成"两条都是正确行为"。

---

## 5. 门位可视化（附加取证：`doors_rebuilt.png`）

**为什么需要**：`rec111` 只 `pet.show()` 后立刻走彩蛋交互，**没让主循环跑够** ⇒ 场景层没渲染，
抓帧里看不到门。为确认"4 扇门真贴屏幕边框"另做了一轮探针。

**取证方式**（★ 结论须如实标注这是**产品输出的可视化**，不是产品截图）：
场景画布是**透明非置顶**层（既定契约）⇒ 前台窗口会盖住它、`QWidget.grab()` 对透明层返回空
⇒ 改用**确定性重建**：从产品真路径 `plan_frame()` 取 obj 名 + rect（**不含我自己编的坐标**），
把 sprite 贴到视口画布上。

**真机实测输出**（`viewport=(1066, 800)`，即 2560×1600 上 4:3 内接矩形，scale=3.333）：

| 门 | rect (x, y, w, h) | 位置 |
|---|---|---|
| OneShot（正上） | `(460, 0, 147, 187)` | 上边正中 ✅ |
| Niko 的家（正下） | `(460, 613, 147, 187)` | 下边正中 ✅ |
| UT（正左） | `(0, 306, 147, 187)` | 左边正中 ✅ |
| Deltarune（正右） | `(919, 306, 147, 187)` | 右边正中 ✅ |

门尺寸 `147×187` = 贴图 `44×56` × scale `3.333` ✅（`check89 E3` 同款判据）。
贴图 = **任意门** `spr_darkdoor`（44×56 / 3 帧，用户「桌面上那个用任意门」）。
⇒ 与用户口径「**正上（oneshot），正下（niko家），正左（ut），正右（三角符文）**」
「**挨着屏幕边框**」**逐条吻合**（见 `_evidence/doors_rebuilt.png`）。

---

## 6. 三重验证结果

### 6.1 离屏判据 `check111` —— **42/42 PASS**（进 G2）

```
A1~A14c  结构层（常量逐字 / AST 取 `ast.Tuple` 元素 / `target_scene=None` 结构锁 / 接线）
B1~B11   行为层（含 build_props 不给 on_egg 时的**真逻辑洞** B9/B10/B11）
C1~C3    负控制
变异测试  7/7 全红 + 还原字节一致
```

★ **B9/B10/B11 锁的真洞**：首版 `build_props` 只判 `(sid,letter)` ⇒ 仍建 `NikoHomeDoorProp`
（一扇"点了没反应"的假门）；更糟的是会 **fall through** 到 `elif letter and tgt` 用**假路由**
建普通门（变"能进门"）。修法 = 显式 `if 彩蛋: if on_egg: 建彩蛋 else: 不建` —— **绝不 fall through**。

### 6.2 真机录屏 `rec111` —— **15/15 PASS**（不进 G2）

★ **不进 G2 的原因**：`QMessageBox.exec_()` 在 `QT_QPA_PLATFORM=offscreen` 下 **SIGSEGV**
（RC=139 / 3221225477）⇒ 它属 `verify105`/`verify107` 那类**独立验收件**。

关键判据：
- `G1` 桌面场景里真有 `NikoHomeDoorProp`；`G1b` 其 `target_scene` 为空（**结构上不存在能进的目标**）
- `G2` 确认框被问 **3 次**；`G2b/G2c` 第 3 次按钮文案 = 「我确定！！！」；`G2d` 三次都点"确定"
- `G3` 三句台词逐字播出（顺序也对）
- **`G4 ★★★ 彩蛋执行前后场景 id 不变`（`desktop` → `desktop`）= 真的没进门**
- `G4b` 爆炸播完仍停在桌面；`G4c` 负控制（否则"不变"可能是两边都 None）
- `G5b` 爆炸帧索引真在推进（boom=7 → after=8）—— 不是"挂了个空引用"

### 6.3 人眼复核 4 张真机抓帧

| 帧 | 内容 |
|---|---|
| `k000_desktop.png` | Ralsei 说话框 + 「你确定吗？」 + 「我确定」/「我再考虑考虑」 |
| `k001_boom.png` | **透明火球**（修 §3.1 后）+ 「你真的不再考虑考虑了吗？」 + 「我确定！！！」 |
| `k002_after_egg.png` | 三连确认 + 爆炸之后 |
| `k003_after_fx.png` | 爆炸播完之后（仍停在桌面） |

⇒ 三句台词逐字可见、按钮文案正确、**火球透出背景**（透明层真的生效）、全程未进任何场景。

---

## 7. 受影响的 G2 套件与处置

| 套件 | 现象 | 处置 |
|---|---|---|
| `round13_build` | `E1` 报红（`WindowStaysOnTopHint`） | 修产品代码（§3.2）→ **IDENTICAL** ✅ |
| `check76` | `C5a` 假红（`setPixmap` 2→3 处） | 判据改为只统计 `sprite_label.setPixmap` → **IDENTICAL** ✅ |
| `check89` | `F1` 假红（探针没传 `on_egg` ⇒ 只建 3 扇） | 探针镜像产品调用点 + 拆 F1a/F1b + `_push` 改**按门字母** → **69/69 PASS** |
| `objects_round44` | DIFF（objs 71→92） | 预期变化（新增 21 素材）→ `--update` |
| `items_round68` | DIFF（objs 71→92） | 同上 → `--update` |
| `check81` | `G5` FAIL（`缺=['check111']`） | **正是它守的语义**（入列 SUITES 未固化）→ `--update` 消除 |

★ **`check89` 的探针教训**（夹具不保真）：探针不传 `on_egg` ⇒ 彩蛋门按契约**根本不建** ⇒
只能看到 3 个普通门 ⇒ `props_n == 4` 恒假红。**修法**：探针**必须镜像产品调用点**
（传只观测的 `on_egg` 桩），并把 `_push` 从**按下标**改为**按门字母**（彩蛋门 `target_scene=None`
⇒ 旧下标假设失效）。

---

## 8. 尚未做的（如实登记）

- **彩蛋门前置光效**：`niko_door_portal` / `niko_portal_rays` / `niko_sparkle_*` **已入库但未接线**。
- **爆炸落点**：当前 = 屏幕正中（用户**未指定位置**）⇒ 保持。
- **桌面 4 门的"贴边框"视觉打磨**：几何已对（§5），但门与桌宠的层级/遮挡关系未进一步调。
