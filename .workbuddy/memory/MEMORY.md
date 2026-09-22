# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **全文（§0–§19）在 `参考-契约与历轮（详版）.md`**（**不自动注入，改动前 Read**）。
> 本文件只留**每轮必守的铁律** + **历轮索引 + 待裁定**。细则一律去详版对应 §。

## 0. 铁律
- 每轮改动完成即 **commit + push**；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根；证据进 `code-quality-audit/<轮次>/_evidence/`。下载/生成物落 `E:\Download`（临时件 `_tmp\` 用后即删）；
  仓库内产物留项目目录。
- ❗**仓库根 = `try - 副本`**（`ralsei_pet` 是其子目录）→ 跑 G2 的 cwd 是仓库根。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（现 **26 套件 / 1358 PASS / 全 IDENTICAL**）。
  G2 跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。

## 1. 环境（详版 §1 / §18 / §19）
- ⚠️ **Bash 工具常整个坏掉**（`ls`/`head`/`cat`/`tail`/`dirname` 全 127）→ **一律 Python + PowerShell 工具**；
  `Glob`/`Grep`/`Read` 照常。❗`2>$null` 报 `ambiguous redirect`；❗**别从 Bash 里调 PowerShell**（安全策略拦）；
  PS **stdout 常不回传** → 命令内 `Out-File -Encoding utf8` 再 Read。
- **起进程**只能 `&` + `run_in_background:true`；**杀进程**用 Python+psutil；**删文件**用 `[System.IO.File]::Delete()`；
  **`wmic` 已移除** → `Get-CimInstance`。
- Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它。
- **代理端口现查为准**；**单端口一次成败不是结论**。**git 用 `shutil.which("git")`**。
- **E 盘会掉线**（`Write` 报 `ENOENT … mkdir '\\?'`）；❗**E 盘 exFAT 不能当探针沙箱** → 用本地 NTFS
  `C:\Users\23002\AppData\Local\Temp\`。
- 清理守卫按路径**累计删除计数**（阈值 50）：症状 = **进程在 import 期就被杀**。**见"计数恒定"先干掉触发源。**
- **证据/报告一律让 Python 自写 UTF-8**；`Write` 覆盖带 BOM 文件**会保留 BOM**。
  ❗**"能力自评失准"比"能力不足"更危险**。
- **注入的 `current_time` 会滞后** → 落盘带日期的产物先 `Get-Date` 校准。
- **`github.com` 主站不可达而 `api.github.com` 仍 200** 时会 push 失败 → **提交照做 + 如实报告 + 稍后重试**，
  **别怀疑凭据或改 git 配置**。
- ⭐ **仓库两套换行口径**（`autocrlf=true` + 无 `.gitattributes`，详版 §8.6.5）⇒ **编辑必须保持原 EOL**；
  逐字节参照系只能用 `git cat-file blob`。
- ⭐ **Ollama 日志 = 性能金矿**：`%LOCALAPPDATA%\Ollama\server.log` 的 `slot print_timing` 行含
  `prompt eval time`/`eval time`/`total time`，**逐次推理全记录**。
- ⭐ **git 对中文路径加引号转义** ⇒ 核验文件存在性**必须** `git ls-files -z` + `surrogateescape`（否则误报 MISSING）。

## 2. git push（配方见 skill `win-git-utf8-push`）
- 退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`**。
- ❗**核验命令自己也会说谎**：`ls-remote` 独立构造 + 重试 3~5 次 + `git rev-parse` 交叉验证。**先怀疑核验，再怀疑被测物。**
- ❗⭐**提交信息编码的正确判据 = 逐字节比对**：`git cat-file commit HEAD` 的 message **vs** 源文件 → `IDENTICAL`。
  **别记"魔法字节序列"**（第 29 轮我记错：`场` = U+573A = `229,156,186`，我写 `231,172,172` → 差点误报编码损坏）。
- ❗**`subprocess.run(input=...)` 必须喂 bytes**（str → `TypeError` 被吞 → push 整段静默跳过，**看着像网络问题**）。

## 3. 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有）；main→origin/main。真机起：
  `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。

## 4. 勿回退契约（**全文详版 §4.1–§4.12 + §10，开工前必读**）
13 组契约（多屏/甩飞/动画/联想/抽词/网图/建楼/存储/初始化环/jieba/DPI/G2 封闭性/误报清单）。四个最易踩：
① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
② **建楼 `floor_visible_contains` 是唯一判据、禁用 `Qt.WindowStaysOnTopHint`**，
  ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户原话口径，不许再改**；
③ **`A in rev[B]` 检反向是恒真判据**；**鉴别力体检必改文件**；
④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\` 读优先，迁移**只复制不搬走**）；
  被反向依赖的底层模块一律 `lazy_log.LazyLogger`；裸进程脚本**先建 `QApplication` 再读坐标**。
**误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已 `pyqtSignal` 排主线程；`reset_special_states` 零调用。

## 5. 验证脚本教训（**全文详版 §5 各节 + §8.4/§8.6，改断言前必读**）
- ⭐**能上 AST 就上 AST**：`code_only_src()` **会剥 STRING token** → 断言**字面量**必恒假/恒红（**踩 7 次**），
  它只适合断言**标识符/运算符**；含字面量走 `code_no_comment()`。**零引用筛查一律走 AST**。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制成对**；**断行为/结构不断赋值/写法**；
  **恒真判据比不写还危险**；❗**报红先自问"夹具真把破坏写进去了吗"**。
- **探针不保真 = 报假问题** →「**能从源码拿的别 import；能 import 的别重写；不得不重写必须锁等价**」；
  ❗❗**"分类器太窄"和"闸有洞"长得一样** → **必须拿产品函数逐条复核，不能只看探针计数**。
- ❗**detail/断言里别写会随代码增长的数字**（`len`/`index` 全漂）；唯一不漂是**纯布尔**。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）**；镜像：**"没改也没人调用"要么接线、要么删**。
- ⭐**两个断言同时报红，处置方向可能相反**（第 29 轮 J3 改探针 / J6 改数据）→ **先读原文再定**。
- **A/B 纪律**：① 两侧都真跑到 ② **先断言 A ≠ B**（"旧值"若已提交 → A==B；取**父版本**）③ 桩打在
  「方法体里 `self` 的那张类」上 ④ **失效谱第 4 形态「参照系不是父版本」最险** ⑤ 断言分层
  ⑥ **A/B 只证"两版等价"**。**对照组重复跑、先量尺子公差**（±2 条＝噪声）；**先读原文再看计数**。
- ⭐❌ **测性能必须用产品真实输入**：第 29 轮用**短 system 裸测** 4B 首字 0.6~0.7s 报"合格"，
  第 30 轮用**产品真实 persona（2322 tok）**实测 = **36.82s**（差 50 倍）。**简化输入会给出反向结论。**

## 6. 人味改造线（**全文详版 §6/§11/§12/§14.3/§15，动手前必读**）
回归锁 `persona_chat`(156)/`s8_stream`(69)/`s7_event_speech`(137)，**均进 G2、不联网、不调 Ollama**。
- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**别只写 Modelfile** ——
  Ollama 用 messages 的 system **整体替换** Modelfile 的 SYSTEM → 写进模型的人设**一次都不生效**
  → **本机唯一可行"训练"杠杆**。persona **是 prompt 不是文档**（不许 markdown）。
- **❗平级口径（用户硬要求）：不许叫"主人"**，用户与 Ralsei **平级**、他**不是为谁而来**，**persona + 代码两层都要改**。
- **世界观** = `ralsei_worldview.md` + `modules/worldview_recall.py`（`MAX_BLOCKS=2`、**无命中返回空串**）。
- **关系演进** = `modules/relationship.py`（四档、`TRUST_INITIAL=0.12` 起于 distrust；**信任度不可见**、
  唯一写入口 `note(event)`；**勿把下界抬到 TRUST_INITIAL** → `harsh` 变死事件）。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**、唯一出口 `speak_event(kind,pool,face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → 返回 `""` 沉默）；**禁 import Qt / 项目内模块**。
- **底座 = `ralsei:v3`（`qwen3:4b-instruct-2507-q4_K_M`）**：**采样参数必须落 Modelfile**
  （`/v1/chat/completions` **静默忽略 `num_ctx`/`repeat_penalty`**）；**换底座必须 `ollama create <新tag> -f ralsei.modelfile`**。
- ★★ **失真头号来源 = persona 里"可逐字搬走的固定例句"，不是模型不行**（真机 24 条：开头复读 **62% → 33%**）。
  **铁律：persona 示例区不许出现"按场合分组 + 冒号 + 固定例句"** —— 这个**格式本身**就在教 4B"这场合该说这句"。
  **只要那串字还在 persona 里，4B 就会搬** ⇒ 改成"情形描述 + 每次自己现造"才有效。锁 **A12d**。
- ★★ **反"伪造共同经历"**：用户**没去过黑暗世界**，模型会把"我的过去"写成"我们那时候一起…" = **替他伪造记忆**。
  persona 已明令"只能说成我自己的过去"。锁 **A12e**。
- **persona 体积上限 K3 < 10KB**（现 9752 B，已接近）→ **加内容前必须先瘦身**。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级）**：0a 句中括号动作 → 0b 剥 markdown → 0c 禁说清单
  （**与事件链路同源，不许另立第二份**）→ 1 自问自答截断 → 2 车轱辘话判退（**只看 recent 重复**）→ 3 超长截断；
  **判退后必须重采样一次**、**判退不 append 进 recent**。❗**0a 必须先于 0b**。**S8 流式**：`iter_lines(chunk_size=1)`。
- ★ **括号旁白共三形态**：甲 动作词开头 → `_ACTION_PAREN_RE`；乙 句首括号 → `looks_like_narration` 整句作废；
  丙 **描述性旁白** → **`_NARRATION_INNER`**。★ **判据是「抓形态特征」不是「首词白名单」** ——
  窄白名单会**把合法心里话一起误杀**。**分界 = 这段是不是角色的「话语」**：第一人称的话 → 留；外部描述自己 → 删。
  **误杀比漏过更糟。** 锁 A22e（正）+ A22f（反）。
- **❗篇幅上限 = `main.AI_REPLY_MAX_CHARS`，现 220**；**换底座/调 num_predict 必须重跑 `measure_token_ratio.py`**。
- ⚠️ 已处置：`_clean_ai_reply` 在 `start_autonomous_speech._on_reply`(`main.py:4620`) 曾**未传 `recent`**（第 26 轮 P3 补 + B13b 锁）。

## 7. H4/H5 上帝类拆分（**全文详版 §8.1–§8.6**）
- 基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**Wave 1 七项全部 ✅ + 第 26 轮复审判"合格"**；**Wave 3 不在范围**。
  ★**预声明区 = 宿主 `init_systems()`**（`main.py` L660，状态块 L770–806；**不是 `__init__`**）。
- ❗**`scan_method_index.py` 只是线索，不是范围定义** —— **四类偏差都出现过**（漏标/误纳/跨区散布/方案自身错）
  ⇒ **必须与排期方案交叉核对 + 逐方法人工确认**。
- ⚠️ **W1 转发铁律：双向 `__getattr__` 两侧都须显式白名单**：宿主侧**只能** `getattr(type(ctrl),name)`，
  **绝不** `hasattr(ctrl,name)`。**`RecursionError` 崩在构造期 → G2 抓不到**。`_CONTROLLER_ATTRS` 在 `main.py` L512。
- ❗❗**W1 搬运铁律 8 条 + A/B 结构性盲区**（全文见详版）：① `self` 传出去救不了 → `QTimer(self.p)`；
  ② 控制器**必实现 `__setattr__`**（判据＝宿主**已拥有**、**必跳过 `'p'`**）；③ 新状态名在 `init_systems()` 预声明；
  ④ `_log` 用 `_log_()`；⑤ 锁的定位器跟代码搬家；⑥ `_log.` → `self._log_().`；⑦ **`os.`/`time.`/`random` 是"裸 Attribute 根"**；
  ⑧ 桩打在「方法体里 `self` 的那张类」上。★★ **A/B 盲区**：`MethodType(fn, stub)` 下 `self` 即 **stub**
  ⇒ **铁律 1/2/3 在 A/B 中结构上不可见**。

## 8. 场景系统线（第 28–30 轮，**全文详版 §16/§17/§18/§19**）
用户口径：**「把原作的世界搬到桌面上…桌面也会被我当成一个场景」** + **「一切根据原作」**。
- **第 28 轮 P0**（`0aba480`）：`scene_system.py`（数据层纯函数）+ `scene_controller.py`（接线层）+
  `assets/scenes/*.json` + `main.py` 四处接线；锁 `scene_p0`。G2 1250/25。
  ★★ **P0 判据 = 「不切场景时零行为变化」**：`switch()` **只写状态**、不动画面/定时器/物理；
  `desktop.json` 的 `bg/bgm/objects` 全空 → **P1 接上渲染层也一像素不变**。
  **一旦 P0 就改了画面，这条最强判据就丢了。**
- **第 29 轮 路由层**（`52d5514`）：`modules/scene_routing.py`（**纯标准库、零 Qt、零项目内业务 import**）+
  `assets/scenes/_routes.json`；锁 `scene_routing`（**106 项**）。G2 **1358/26**。
  ★★ **路由是数据，不是代码** —— 规则全在 JSON，代码只做「读 + 匹配」。
  分层：**语境 → `match()`（纯函数）→ route `{to,reason,priority}` → `follow_route()` → `switch()`**。
  **匹配语义**：`when_scene/area/chapter` 相等 + `"*"` 通配；`when_mood/event` 单值或数组；
  `when_keywords` **OR 语义**（与其余键的 AND **刻意不同**）；排序 = `priority` 升序 → **命中数降序** → 声明序。
  **三条设计律**：① 匹配不到返回 `None`（**绝不伪造默认路线**）② 坏规则跳过不作废整张表 ③ 未知键一律放行。
  ★★ **零行为变化**：路由层**没有自动调用方**、**只有 `follow_route` 允许调 `switch`**（锁 H1–H5）。
  ★ **`destinations()` 过滤未登记场景** → 防 AI 被送往「路由表写了但场景不存在」处（表现为「**走了一半停住**」，难查）。
  ★ **`_as_set()` 坑**：`set("abc")` → `{'a','b','c'}` ⇒ 字符串一律当**单个值**。
- ★ **原作机制**（GML 实证 `scr_roomname`）：房间 ID **扁平整数**；**同一 id 不同章是不同房间** ⇒
  **id 必须与 chapter 联合才唯一**（**印证三级模型，chapter 必须显式存**）；显示名是**两段式**（父 + 子地点）
  ⇒ 我们 `describe()` 的「章节、区域、场景」是**同一结构**；★ **原作没有显式"区域"结构**
  ⇒ **我们显式化成 area 层比原作强**。**房间数 Ch1~Ch5 = 20/20/8/19/20，合计 87 间**
  （落档 `原作场景线路研究_2026-09-22.md`）。
- ★ **为什么现在不登记原作场景**：**素材还没做** → 登记了切过去 = **一个空场景** = 「**世界突然变白**」，**比不切更糟**。
  **落地三步（零改代码）**：① `_index.json` 登记 → ② 放 `<scene_id>.json` → ③ `_routes.json` 加规则。

## 9. 性能线（第 29–30 轮，**全文详版 §17.3/§18/§19**）
- **硬件真相**：Intel Core Ultra 5 125H + **Intel Arc 核显 + 31.6 GiB 内存**，**无独显、无独立 VRAM**。
  用户说"32GB 显存"→ 实为**内存**。Ollama 跑**纯 CPU**（`library=cpu`、`size_vram=0`、
  **无 `ggml-vulkan/cuda/dml.dll`**，Ollama 0.34.2 未带 Vulkan 后端）。
- **4B 实测**（**219 次真实推理**，源 `server.log`，证据 `_evidence/4b_server_log_perf.txt`）：
  **avg 8.07 tok/s**；**12 tok=1.49s / 20 tok=2.48s / 40 tok=4.96s**。
- ★★★ **第 30 轮用产品真实 persona 实测首字（TTF）**（证据 `_evidence/ttf_measure.txt`）：
  | 场景 | prompt tok | 首字 | 生成 tok/s | 整句 |
  |---|---|---|---|---|
  | 短 system | 21 | **0.33s** | 10.2 | 3.92s |
  | persona（冷） | 2322 | **36.82s** ← 真问题 | 8.4 | 2.63s |
  | persona+3轮历史 | 2363 | **1.91s** | 8.3 | 2.54s |
  ★★ **同一 prompt 长度差 19 倍** ⇒ **决定首字的是「KV cache 是否命中」**（场景 3 复用场景 2 前缀），
  **不是单纯的 prompt 长度**（推翻第 29 轮简化结论）。**⇒ 「首字 1~3s」可靠 prompt 缓存实现，不必动内容。**
  ★ **prefill（首字）远慢于 decode（生成）** ⇒ 用户体感的"慢"= 首字慢，与"生成速度"无关。
- **7B**：外推 ≈ **4.61 tok/s**（**全是外推，非实测**）；磁盘留 **48.08%** 的 `-partial`（2.097/4.361 GB），
  **可续传**（`ollama pull qwen2.5:7b-instruct-q4_K_M`，不会从头）。
  ★★ **进度判断铁律**：`-partial` 是**稀疏预分配**（文件大小与进度无关）；16 个 `-partial-N` 每 ~60 字节是
  **进度标记不是分片**。**唯一可信进度源 = `/api/pull` 的 `completed`/`total`**。
  ❗**不得自动重启下载推进器**（用户已取消过 `_pump7b2.py`）。

## 10. 用户口径（**优先于我的技术判断，违者返工**）
- **「prompt 尽量完整」** —— 明确否决"砍 prompt 长度"路线 ⇒ 提速只能靠**缓存 / 后端 / 换模型质量**。
- **「1~3s 是首字的延迟」** —— 验收指标 = **TTF**，不是整句。
- **「用 7B 目的就是让他贴合人物并且不出 bug」** —— 动机是**质量**（人设贴合 / 减少格式崩坏），**不是速度**。
- **「一切根据原作」** —— 场景/线路/命名以原作 GML 实证为准。

## 11. 历轮索引（细节去详版 + `.workbuddy/memory/<日期>.md` + 对应报告）

| 轮 | 主题 | 详版 | 状态 |
|---|---|---|---|
| 26 | 首轮全项目复审 + H4/H5 处置 | §14 | ✅ `5c0a3e7`/`d5ab8d4` |
| 27 | AI 失真治理（三源全治） | §15 | ✅ `685f98b`；复读 62%→33% |
| 28 | 场景系统 P0（留接口） | §16 | ✅ `0aba480`；G2 1250/25 |
| 29 | 场景路由层 + 7B 评估 | §17/§18 | ✅ `52d5514`；G2 1358/26 |
| 30 | 产品链路首字实测 + 用户口径纠正 | §19 | 🔄 本轮 |

## 12. 🔴 待用户裁定（**开工前必看**）
1. **7B 怎么处理**（用户要求接、目的=贴合人物+不出 bug）：**是否授权续下**（推进器曾被取消，不自动重启）？
   **是否试 Vulkan 后端**（核显加速 = 唯一"保 prompt 完整性又把首字拉进 1~3s"的路；需先验证
   Ollama 能否加载 Vulkan 后端 dll）？以及 **7B 装好后是否设为默认**？
2. **场景美术素材来源**（**P1 开工前唯一阻塞项**）：`<仓根>/deltarune_ralsei/` 1111 张 PNG **全是角色精灵**；
   `assets/sprites/`、`assets/faces/` **空目录**；全仓库搜 `bg_`/`tileset`/`room_`/`map_` **零命中**
   → **A 程序化生成 / B 用户截图 / C 重绘 → 推荐 A+B**。
3. 另：场景粒度 ｜ 是否要 BGM（现 `sound_manager` **只有 3 音效、无 BGM 能力**）｜ 原作版权尺度。
4. **沿用第 26 轮**：`dialogue_ui._rule_reply()` 罐头皮 ⇒ 「AI 关必沉默」是否也管"用户主动打字"。
5. **待办**：真机手感实测（用户侧）｜`.gitattributes` 换行口径（**先议后动**）｜`_tmp`/`.bak` 存量
   （**等用户点头，不得批量删**）｜H4「文件反应」专项。
