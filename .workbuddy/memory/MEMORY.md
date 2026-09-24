# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **全文（§0–§45）在 `参考-契约与历轮（详版）.md`**（不注入）。本文件只留**铁律 + 索引 + 待裁定**。
> ⚠️ 注入上限 = **10,000 字符**（JS `content.length`＝UTF-16 码元，超限**砍尾**）；`js_len(t)=len(t.strip().encode('utf-16-le'))//2`；用户级 `~/.workbuddy/MEMORY.md` = **4,000**。❗禁用「字节数／行数」判（假安全，§41.1）⇒ 压缩前**先补详版 + 逐令牌回验**（skill `agent-memory-compaction`）。

## 0. 铁律
- 每轮改动即 **commit + push**；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。报告放项目根、证据进 `code-quality-audit/<轮次>/_evidence/`、下载/生成物落 `E:\Download`（`_tmp\` 用后即删）；**仓库内产物留项目目录**。
- ❗**仓库根 = `try - 副本`**（`ralsei_pet` 是其子目录）⇒ **跑 G2 的 cwd 是仓库根**。远端 `https://github.com/xiaohanzhe/try-----.git`（★**公开**），main→origin/main。真机起 `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py`（后台）；单实例锁 `Global\RalseiPetMutex`；窗口透明非置顶 ⇒ **甩飞/抛物线只能离屏断言**。
- 改代码前先跑 G2 `regress/run_all.py`（**40 套件 / PASS=1843 / 全 IDENTICAL**）；★ 改断言/文案 → `--only <suite> --update`（**合并模式**）。
- ★ **只读优先、改动最小化**；★"写了 N 个文件"必须 `os.listdir` 查磁盘；★★ **回归套件不许依赖"用后即删"的临时区** ⇒ 判据要的事实**蒸馏进仓库**。
- ❗❗**改过"重要核心文件"必须复检**：可编译／结构／编码／恒真判据复查／**逐令牌回验**／工作区干净，逐项 PASS/FAIL 落盘（skill `core-file-recheck`）。

## 1. 环境（细则 §1/§18/§19/§21/§23.10/§37.5/§37.8）
- ⚠️ **Bash 常整体坏掉**（`ls/head/cat/tail` 全 127）→ **一律 Python + Write/Read**；`Glob/Grep/Read`／`cd && git` 照常。❗别从 Bash 调 PowerShell；❗❗**别内联 `python -c`**（反引号被吞）。**报告一律 Python 自写 UTF-8**；`current_time` 滞后 → 先 `Get-Date`；❗**"能力自评失准"比"能力不足"更危险**。- Python 一律 **`C:\Python311\python.exe`**；起进程 `&`+`run_in_background:true`，杀进程用 Python+psutil。★ 大目录遍历**先 `os.listdir` 只列一次**。
- ❗❗**临时/备份绝不放工作区**（会被 `git add -A` 记为删除并提交）⇒ 一律 `E:\Download\_tmp\`；**提交前必看 `git diff --cached --numstat`，deletions >1000 停手**。❗**清理守卫按路径累计删除计数（50）**：症状 = **import 期被 SIGTERM、零输出**；移出索引用 `git rm --cached`。★★ **写入通道会整体失效**（~25min 自愈）：已有文件写/改/移全被拒、**新建文件正常** ⇒ 只产新文件 + 换版本号名。
- ⭐⭐ **代理端口逐端口实测 CONNECT 再选**（`7897` 通／`7375` 死）。⭐ **无 `.gitattributes` 而 `autocrlf=true`** ⇒ **编辑保持原 EOL**（参照只用 `git cat-file blob`）；中文路径 ⇒ `git ls-files -z` + `surrogateescape`。

## 2. git push（skill `win-git-utf8-push`；**§39.5 + §37.13**）
- 提交信息 **Write 写 UTF-8 文件 + `git commit -F`**（`-m @'...'@` 被 PS 5.1 拆 argv ⇒ 退 0 **假成功**）；提交后必核 `git log --oneline -1`。`subprocess.run(input=...)` **必须喂 bytes**（str ⇒ `TypeError` 被吞 ⇒ 静默跳过，像网络问题）。
- ❗**核验命令自己会说谎** ⇒ `ls-remote` **独立构造** + 重试 3~5 次 + `git rev-parse origin/main` 交叉验证。★ **本仓库公开 ⇒ `ls-remote` 是恒真判据**。
- ★★ 两根因：**TLS** = `schannel` 吊销检查必失败 ⇒ 加 `-c http.sslBackend=openssl -c http.sslCAInfo=<系统CA PEM> -c http.version=HTTP/1.1`；**凭据** = 宿主注入 `credential.helper=helper-selector` **不读** Win 凭据管理器 ⇒ 弹 GUI 挂死 ⇒ **直取 GCM**（`GCM_CREDENTIAL_STORE=wincredman`，非 "windows"；`GCM_INTERACTIVE=never` + `-c credential.helper=` + `http.extraheader=`）。
- ★ **工具** `_tools/gitpush.py` 一把跑完（add→numstat 守卫→commit -F→GCM→push→双向核验）。⛔ **绝不循环重试 push**。

## 3. 勿回退契约（详版 **§4.1–§4.12 + §10 + §23.9**，开工前必读）
13 组契约。最易踩六条：
① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
② **建楼**（细则 **§4.9**）：`floor_visible_contains` **唯一判据**、**禁用 `Qt.WindowStaysOnTopHint`**、**甩飞必须显式 `_fall_reason = None`**、**先 `show()` 再调 z 序**、判定函数**模块级**；⚠️ **`climb_1_*`=朝右／`climb_0_degrees_*`=朝前**；
③ **`A in rev[B]` 检反向是恒真判据**；**鉴别力体检必改文件**；
④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\`，迁移**只复制不搬走**）；被反向依赖的底层模块一律 `lazy_log.LazyLogger`；裸进程脚本**先建 `QApplication` 再读坐标**；
⑤ **G2 `run_all.py` 有 `HERMETIC_IDS`**；`save_baseline` **合并模式**；★★ **新套件必须 `print('[PASS] %s')` 字面量**（`run_all.py:425` 按 `[PASS]`/`[OK]` 计数；写 `"  PASS  msg"` ⇒ **PASS 恒 0**）；放 `code-quality-audit/<轮次>/` ⇒ `ROOT=os.path.join(HERE,'..','..')`。
**误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已 `pyqtSignal`；`reset_special_states` 零调用；`pet_interaction.py` **零接线**（§11）。

## 4. 验证脚本教训（详版 **§5 + §23.4/§23.5/§23.12/§35.6 + §41.6/§43.7/§44.6**）
- ⭐**能上 AST 就上 AST**：`code_only_src()` **会剥 STRING token** ⇒ 断言**字面量**必恒假（**踩 7 次**）；含字面量走 `code_no_comment()`；❗扫属性要同时扫 `ast.Constant` 里的同名字符串。
- **恒真判据比不写还危险**；**正/负控制成对**；**断行为/结构不断赋值**；❗**报红先自问"夹具真把破坏写进去了吗"**、★★ **再怀疑判据本身**（38/40/42 轮共 7 次均在判据侧）。**探针不保真=报假问题**（踩 5 次）⇒ **能从源码拿的别 import／能 import 的别重写／不得不重写必须锁等价**；★★★ **行为判据必须用真实量级输入**；**需真人操作的判据严禁离线模拟**；**"函数写对了"≠"产品用上了"（最贵坑）**；**A/B 先断言 A ≠ B**；**「删掉重复行」≠「去掉重」**（以**运行时等价**为准）。
- ★★★ **反汇编/解析器必须先过 A/B 锚点**（43轮）：**"提取成功"≠"提取正确"** ⇒ 先设 3 个"已知真值"站点、**全命中才用其输出**（实例：GMS2 实参**从右往左压栈**、变量 push 也占一槽；每脚本**两个 code**：`gml_Script_X` 空桩 ins=0／`gml_GlobalScript_X` 真体 ⇒ §44.6）。★ **字段名也要先探**（44轮）⇒ `UndertaleSprite` 速度字段真名 = `GMS2PlaybackSpeed`（写 `Speed`/`PlaybackSpeed` **不存在** ⇒ 静默 null ⇒ **全表假数据**，险致「原作无动画」误判，§45.10.3）。
- ★ **判据别拿"源码字面量"代替"产物输出"**（44轮）：查 `'[PASS] '` 源码串会漏（运行时才拼）⇒ **真跑一次数输出行**。★ **复检动作不许改变被测状态**（`py_compile` 产 `.pyc` 污染工作区 ⇒ 改 `ast.parse`，§45.10.5）。

## 5. 人味改造线（细则 **§23.13.1 + §6.1–§6.10**）
回归锁 `persona_chat`(156)／`s8_stream`(69)／`s7_event_speech`(138)，均进 G2、不联网。**人设单一真源 = `assets/ralsei_persona.md`**（**别只写 Modelfile** —— messages 的 system **整体替换**它）；**禁 markdown**、**❗不许叫"主人"**、**K3 < 10000 B**。★★ **失真头号来源 = "可逐字搬走的固定例句"**（锁 **A12d**）；**"口癖多"≠ 全砍**（真结巴仅 8.3%）。**护栏 `_clean_ai_reply(reply, recent=)` 顺序即优先级**（0a 括号→0b markdown→0c 禁说→1 自问自答截断→2 判退「只看 recent」→3 超长）；**判退必重采样**、**不 append 进 recent**。**`AI_REPLY_MAX_CHARS` = 220**；余下（`TRUST_INITIAL=0.12`／`ralsei:v4`／**A12e**）见 §23.13.1。

## 6. H4/H5 上帝类拆分（详版 §8.1–§8.6；Wave 1 已完成，**休眠线**）
基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**预声明区 = 宿主 `init_systems()`**（`main.py` L660，**不是 `__init__`**）。⚠️ **W1 转发铁律**：宿主侧**只能** `getattr(type(ctrl),name)`、**绝不** `hasattr(ctrl,name)`（崩在构造期 ⇒ G2 抓不到）；`_CONTROLLER_ATTRS` 在 L512；详见 §8.5/§8.6。

## 7. 场景系统线 / 原作素材 ★ 动手前**必须 Read 详版 §16/§36/§37/§39~§45**
用户口径：**「把原作的世界搬到桌面上…桌面也会被我当成一个场景」**＋**「一切根据原作」**＋**「所有 room 排序/连接按原作 = 场景复现，连动态效果也做」**（传送门/首站见 §11）。
- ★★★ **原作「换房」与「背景移动」（§44）**：**背景移动 = 相机平移，不是视差**（ch1 **1014 层** `HSpeed`/`VSpeed` 非零 = **0**、`EffectType` 恒 null）。相机 **现实 320×240（2×）／暗世界 640×480（1:1）**、`GMS2FPS=30`、每帧硬跟随+四向钳制。**换房 ≈0.92s**（`obj_fadeout` 淡出 0.417s → `room_goto*` → 淡入 0.417s）。★★★ **对象索引跨章不稳定 ⇒ 跨章按名字**。
- ★ **原作门机制（§43.2）**：`obj_doorA~F` = `Data.Rooms` **下标 ±1/±2/±3**（**A+1／B-1／C+2** 已实证，须同字母 `obj_marker` 校验）；`obj_doorX`／`W` = **表驱动双向**；`obj_doorAny` 无代码；**门全 `visible:False`**，落点 = `obj_marker*`；★ **「排序」＝「连接」**、**无门 = 不可达**。
- **桌面接入（§43.6）**：桌面 = **独立前置章**；放**暗之泉**（`spr_fountainedge`）→ 切 `ch1.room_town_north`。**范围 = 原作全部 1,251 间，含暗世界**。
- **规模**：五章 **1,251 room** ⇒ **1,013 场景**；`(章,区域)` **61** 分片。`_original_rooms.json`**id == `Data.Rooms` index**；`_room_order.json`（1,251 全序）＋`_room_graph.json`（782 边）。
- **★ 两种载体（坑）**：分片 `_zone.<ch>.<区>.json`（**顶层 `scenes`**）／独立 `<scene_id>.json`（**`objects` 在顶层**）；独立文件的 `original_room_id` **只在 `_index.json`**。★ 分片名以 `_` 开头 ⇒ `startswith('_')` 一刀切**漏全部**。
- **命名 = 不译**（`区域中文名·尾段原样` + `name_raw`）。**素材**：真背景 **157 / 1,013**、近似 **856**；**判据真源 = `第39轮/_tools/bg_common.py::classify()`**。**工具 UTMT CLI v0.9.2.0**；背景在 `room.Layers`。⚠️ 早期 `ROOM/SPRT/OBJT.json` **不可信**。
- ★★★ **objects 补全（§45.10.2）**：5,523 实例里仅 **2,067（37.4%）能映射 sprite**，余 3,456 是**纯逻辑锚点**（`visible=false` 不该画）⇒ **532 场景 / 2,043 条**；8 个未登记房间（24 条）**有意不产**。
- ★★★ **动效 = sprite 逐帧（§45.10.3）**：背景 HSpeed/效果/瓦片/Sequence **全 0**，唯一载体 = 多帧 sprite（523/1097）；`GMS2PlaybackSpeed=1`+`FPS=30` ⇒ **33.3ms/帧**，本产品 **105 条带动画**。
- ⚠️ **P1 前置**：`dump_rooms.csx` **缺 4 项**（层几何 `XOffset/YOffset/HSpeed/VSpeed`／`LegacyTiles` 几何／`TileData` 真矩阵／实例变换）⇒ **§42.6**。

## 8. 性能线 ★ 铁律（详版 §17.3/§18/§19/§20.3）
- 硬件：Core Ultra 5 125H + **Arc 核显 + 31.6 GiB 内存**；Ollama **纯 CPU** ⇒ **Vulkan 救不回冷 prefill**。
- ★★★ **首字（TTF）铁律**：决定首字的是「**KV 前缀缓存是否命中**」，不是模型大小/prompt 长度（4B **36.82s→1.91s**；7B **103.6s→0.55s**）⇒ **每轮必变的部分压到 system 最末尾**；★ prefill 远慢于 decode ⇒ 体感的"慢" = **首字慢**；第31轮方案 = **平均首字 4.601s** ✅（验收 ≤ **5s**）。**默认底座 `ralsei:v4`** = `qwen2.5:7b-instruct-q4_K_M`；❗模型目录 = `C:\Users\23002\.ollama\models`。

## 9. 用户口径（**优先于我的技术判断，违者返工**）
- **「prompt 尽量完整」** ⇒ 提速只能靠**缓存／后端／换模型质量**，不许砍 prompt。**「用 7B 目的就是让他贴合人物并且不出 bug」** ⇒ 动机是**质量**。**「结巴…这有点不好」**=**减少但**不许到 0（真结巴 8.3%）；❗**未实现**：结巴率随 trust **下降**、只在紧张时 ⇒ **待排期**。**「开机自启…是选项，不是硬性代码」** ⇒ 配置项（默认 false），留到收尾。
- ★★ **当前主轴**：**场景系统**（36–44轮）；**移动/行为**已收（34轮）；**严查现有基础代码纰漏**；**这一阶段完全 ok 才进下一阶段**。★★ **工作方式（34轮）**：「**不必要每次变完一轮就暂停一次，大可以你测完了没问题后，然后按照你的计划来**」⇒ **测绿了就按计划连续推进**。
- ★★ **记忆口径**：「**只要不影响读取就 OK，但影响的话就尽量别动**」＋41「**记忆不要随便修改，三思而后行**」⇒ 门槛：**实证超限或被要求** + 先补详版 + 逐令牌回验 + **改动守恒**，否则不动。
- ★ **范围修正（42轮）**：41 轮"所有 room 按原作"只是起点；42 轮明确「**和原作一样，暗世界也做**」⇒ 范围 = **原作全部 1,251 间**。★ **历轮口径**：36 按原版路线／37 自行反编译／38 走到哪亮到哪／39-40 授权自主推进。

## 10. 历轮索引（**详版 §14–§45 有完整版** + 各轮报告）**26–44**：H4H5／AI 失真／场景 P0／路由／首字／7B／结巴／移动严查／素材反编译（87 背景）／1,013 场景+P0 接线／真背景 157（856 留空）／40 注入上限／41 原作复现取证／**42 门机制全解 + 五章拓扑（782 边/1,251 间）**／**43 换房 ≈0.92s + 相机平移（零视差）**／**44 原作对话框复刻 + 渲染层落地（`dr_textbox`/`scene_render`/`scene_canvas`）+ 路由 v2（26→443）+ 复检 + ★续做 objects 补全（2,043 条/532 场景，`8824e81`）+ 动效=sprite 逐帧（105 条/33.3ms，`555c797`）**（§41~§45.10）。
`8f95f5e` `21b520d` `7b9d10a` `8824e81` `555c797`（38~39 全表见详版 §41.10）

## 11. 🔴 待用户裁定（**全文见详版 §23.13.3＋§36.8＋§37.11＋§39.10＋§40.8＋§43.6＋§44.8＋§45.9**）
1. ★★ **Q1 已拍板（41+42轮）**：所有 room 排序/连接按原作 = 场景复现（含动态效果）；**传送门 = 暗之泉**、**第一站 = `room_town_north`**、**范围含暗世界** ⇒ 157 真背景只是起点、**856 留空项按原作补齐**（含 Q4 78/87）。❗平铺画布口径待重议（1280／`clamp(rh/rw,0.5,0.9)`）。
2. **Q2/Q3 仍待**：`ch1.kris_room` 640×480 放大件是否换回｜2 处选层（`torielclass`→`bg_lang_ja_torielclass`／`dw_castle_restaurant`→柜台层）是否定向覆盖（需 GML 语言门控证据）。3. 低优先：场景粒度｜BGM｜原作版权｜`dialogue_ui._rule_reply()` 罐头皮｜`.gitattributes` 换行｜`src/` 顶层 `.bak`/`test_*`/`monitor_*.txt`（**不得批量删**）｜自启+预热。
4. ★ **P3**：`nearest_visible_point`／`get_jump_destinations` 闭区间 vs `_rect_tuple` 半开；`_sleep` 拼错（35轮）；`play_animation_once` 51 处仅 8 处传 `restore_to`；`pet_interaction.py`（365 行零接线）→ A 删／B 接线／**C 暂缓**；动态结巴率是否进 `relationship.py`。
5. ★ **44轮**（§45.9/§45.10）：✅ objects 补全 + 动效 + 逐章验收**已完成**；余 `_original_rooms.json` 加 `scope` 改名；路由 30.6%→`obj_doorAny/W/X`；`SCENE_LAYER_ENABLED` 默认 False 待定开关。
6. ★ **42/43轮**（§42.6/§44.8）：落点表未配对导出 `entries`；`initwd`/`initht` 来源未定位；`global.darkzone`/`plot` 取值域；**相机/过渡/深度是否落码**待拍板；ch2~ch5 未做 `view43` 普查；扩 `dump_rooms.csx`（4 项）+ 重跑五章。
