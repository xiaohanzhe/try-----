# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **全文（§0–§20）在 `参考-契约与历轮（详版）.md`**（**不自动注入，改动前 Read**）。
> 本文件只留**每轮必守的铁律 + 历轮索引 + 待裁定**。细则一律去详版对应 §。

## 0. 铁律
- 每轮改动完成即 **commit + push**；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根；证据进 `code-quality-audit/<轮次>/_evidence/`。下载/生成物落 `E:\Download`（临时件 `_tmp\` 用后即删）；
  仓库内产物留项目目录。
- ❗**仓库根 = `try - 副本`**（`ralsei_pet` 是其子目录）→ 跑 G2 的 cwd 是仓库根。
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有）；main→origin/main。真机起：
  `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（现 **26 套件 / 1359 PASS / 全 IDENTICAL**）。
  G2 跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。
  ★ **改了套件断言/文案 → 用 `--only <suite> --update`（合并模式）重建基线**，别全量 update。

## 1. 环境（详版 §1 / §18 / §19）
- ⚠️ **Bash 工具常整个坏掉**（`ls`/`head`/`cat`/`tail`/`dirname` 全 127）→ **一律 Python + PowerShell 工具**；
  `Glob`/`Grep`/`Read` 照常。❗`2>$null` 报 `ambiguous redirect`；❗**别从 Bash 里调 PowerShell**（安全策略拦）；
  PS **stdout 常不回传** → 命令内 `Out-File -Encoding utf8` 再 Read。
- **起进程**只能 `&` + `run_in_background:true`；**杀进程**用 Python+psutil；**删文件**用 `[System.IO.File]::Delete()`；
  **`wmic` 已移除** → `Get-CimInstance`。
- Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它。
- **代理端口现查为准**；**单端口一次成败不是结论**。**git 用 `shutil.which("git")`**。
- **E 盘会掉线**（`Write` 报 `ENOENT … mkdir '\\?'`）；❗**E 盘 exFAT 不能当探针沙箱** → 用本地 NTFS `%TEMP%\`。
- 清理守卫按路径**累计删除计数**（阈值 50）：症状 = **进程在 import 期就被杀**。**见"计数恒定"先干掉触发源。**
- **证据/报告一律让 Python 自写 UTF-8**；`Write` 覆盖带 BOM 文件**会保留 BOM**。
  ❗**"能力自评失准"比"能力不足"更危险**。
- **注入的 `current_time` 会滞后** → 落盘带日期的产物先 `Get-Date` 校准。
- **`github.com` 主站不可达而 `api.github.com` 仍 200** 时会 push 失败 → **提交照做 + 如实报告 + 稍后重试**，
  **别怀疑凭据或改 git 配置**。
- ⭐ **仓库两套换行口径**（`autocrlf=true` + 无 `.gitattributes`，详版 §8.6.5）⇒ **编辑必须保持原 EOL**；
  逐字节参照系只能用 `git cat-file blob`。
- ⭐ **git 对中文路径加引号转义** ⇒ 核验文件存在性**必须** `git ls-files -z` + `surrogateescape`（否则误报 MISSING）。
- ⭐ **Ollama 日志 = 性能金矿**：`%LOCALAPPDATA%\Ollama\server.log` 的 `slot print_timing` 行含
  `prompt eval time`/`eval time`/`total time`，**逐次推理全记录**。

## 2. git push（配方见 skill `win-git-utf8-push`）
- 退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`**。
- ❗**核验命令自己也会说谎**：`ls-remote` 独立构造 + 重试 3~5 次 + `git rev-parse` 交叉验证。
- ❗⭐**提交信息编码的正确判据 = 逐字节比对**（`git cat-file commit HEAD` 的 message **vs** 源文件），
  **别记"魔法字节序列"**；❗**且必须按行 `rstrip()`** —— **git 会剥掉每行的行尾空格**，
  忽略它会把"空白规范化"误报成"编码损坏"（第 31 轮踩过：`@1392: commit=0x0A src=0x20`，
  按行 rstrip 后 60 行逐行一致 = IDENTICAL）。
  ⇒ **先怀疑核验判据，再怀疑被测物。**
- ❗**`subprocess.run(input=...)` 必须喂 bytes**（str → `TypeError` 被吞 → push 整段静默跳过，**看着像网络问题**）。

## 3. 勿回退契约（**全文详版 §4.1–§4.12 + §10，开工前必读**）
13 组契约（多屏/甩飞/动画/联想/抽词/网图/建楼/存储/初始化环/jieba/DPI/G2 封闭性/误报清单）。四个最易踩：
① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
② **建楼 `floor_visible_contains` 是唯一判据、禁用 `Qt.WindowStaysOnTopHint`**，
  ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户原话口径，不许再改**；
③ **`A in rev[B]` 检反向是恒真判据**；**鉴别力体检必改文件**；
④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\` 读优先，迁移**只复制不搬走**）；
  被反向依赖的底层模块一律 `lazy_log.LazyLogger`；裸进程脚本**先建 `QApplication` 再读坐标**。
**误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已 `pyqtSignal` 排主线程；`reset_special_states` 零调用。

## 4. 验证脚本教训（**全文详版 §5 各节 + §8.4/§8.6，改断言前必读**）
- ⭐**能上 AST 就上 AST**：`code_only_src()` **会剥 STRING token** → 断言**字面量**必恒假/恒红（**踩 7 次**）；
  含字面量走 `code_no_comment()`。**零引用筛查一律走 AST**。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制成对**；**断行为/结构不断赋值/写法**；
  **恒真判据比不写还危险**；❗**报红先自问"夹具真把破坏写进去了吗"**。**恒红 ≠ 抓破坏**。
- **探针不保真 = 报假问题** →「**能从源码拿的别 import；能 import 的别重写；不得不重写必须锁等价**」；
  ❗❗**"分类器太窄"和"闸有洞"长得一样** → **必须拿产品函数逐条复核，不能只看探针计数**。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）**；镜像：**"没改也没人调用"要么接线、要么删**。
- ⭐**两个断言同时报红，处置方向可能相反** → **先读原文再定**。
- **A/B 纪律**：先断言 **A ≠ B**（"旧值"若已提交 → A==B，取**父版本**）；桩打在「方法体里 `self` 的那张类」；
  **A/B 只证"两版等价"**。**对照组重复跑、先量尺子公差**；**先读原文再看计数**。
- ⭐❌ **测性能必须用产品真实输入**：裸测 4B 首字 0.6~0.7s 报"合格"，**产品真 persona 实测 36.82s**（50 倍）。
  **简化输入会给出反向结论。**

## 5. 人味改造线（**全文详版 §6/§11/§12/§14.3/§15/§20，动手前必读**）
回归锁 `persona_chat`(156)/`s8_stream`(69)/`s7_event_speech`(138)，**均进 G2、不联网、不调 Ollama**。
- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**别只写 Modelfile** ——
  Ollama 用 messages 的 system **整体替换** Modelfile 的 SYSTEM → 写进模型的人设**一次都不生效**。
  persona **是 prompt 不是文档**（不许 markdown，`**` 会被学走，第 31 轮被锁 **A11** 抓住）。
  **❗用户与 Ralsei 平级：不许叫"主人"**（persona + 代码两层）。**体积上限 K3 < 10000 B**（现 **9946 B**）
  ⇒ **加内容前必须先瘦身**。
- **世界观** = `ralsei_worldview.md` + `modules/worldview_recall.py`（`MAX_BLOCKS=2`、**无命中返回空串**）。
- **关系演进** = `modules/relationship.py`（四档、`TRUST_INITIAL=0.12` 起于 distrust；**信任度不可见**、
  唯一写入口 `note(event)`；**勿把下界抬到 TRUST_INITIAL** → `harsh` 变死事件）。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**、唯一出口 `speak_event(kind,pool,face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → 返回 `""` 沉默）；**禁 import Qt / 项目内模块**。
- **底座 = `ralsei:v4`（7B，第 31 轮起为默认）**；旧 `ralsei:v3`（4B）仍在，**回退只需改 `config.json`**。
  **采样参数必须落 Modelfile**（`/v1/chat/completions` **静默忽略 `num_ctx`/`repeat_penalty`**）；
  **换底座必须 `ollama create <新tag> -f ralsei.modelfile`**（复用 blob，**不重下**）。
- ★★ **失真头号来源 = persona 里"可逐字搬走的固定例句"**（真机 24 条：开头复读 **62% → 33%**）。
  **铁律：persona 示例区不许出现"按场合分组 + 冒号 + 固定例句"**（这个**格式本身**就在教模型照搬）
  ⇒ 只能改成"情形描述 + 每次自己现造"。锁 **A12d**。
- ★★ **第 31 轮同源复现 = 治「固定开场白」**（用户口径「他经常说结巴的话」= **太多了要减少**）。
  **先取证**：**真结巴只有 8.3%**（属人物真实性，**不追求降到 0**）；真凶是
  **「诶？」起头 75% / 「诶？这样啊……」50% / 省略号 83% / 反问结尾 75%**。
  根因同上：persona 把"诶"排语气词第一位 ⇒ 模型每次抓它。**处置见详版 §20.4**；
  A/B 实测「诶？」起头 **75%→0%**、语气词起头 83%→16.7%、省略号 83%→25%，**真结巴未涨**。
  ★ **教训**：用户说"某口癖太多"时**先分清"真口癖"（人物真实性，别砍）和"固定模板句"（失真，必须砍）**；
  取证口径 = **用产品真 persona 打多组、分类计数**。
- ★★ **反"伪造共同经历"**：用户**没去过黑暗世界**，模型会把"我的过去"写成"我们那时候一起…"。锁 **A12e**。
  ⚠️ **第 31 轮实测 7B 仍会犯**，且**护栏管不了它**（护栏只治括号旁白）→ 属 persona 服从性问题，**需继续观察**。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级）**：0a 句中括号动作 → 0b 剥 markdown → 0c 禁说清单
  （**与事件链路同源，不许另立第二份**）→ 1 自问自答截断 → 2 车轱辘话判退（**只看 recent 重复**）→ 3 超长截断；
  **判退后必须重采样一次**、**判退不 append 进 recent**。❗**0a 必须先于 0b**。**S8 流式**：`iter_lines(chunk_size=1)`。
- ★ **括号旁白三形态**：甲 动作词开头 → `_ACTION_PAREN_RE`；乙 句首括号 → `looks_like_narration` 整句作废；
  丙 **描述性旁白** → **`_NARRATION_INNER`**。★ **判据是「抓形态特征」不是「首词白名单」** ——
  窄白名单会**把合法心里话一起误杀**。**分界 = 这段是不是角色的「话语」**：第一人称 → 留；外部描述自己 → 删。
  **误杀比漏过更糟。** 锁 A22e（正）+ A22f（反）+ A22g（防放宽误杀）。
  ★ **第 31 轮补漏**：`（轻叹）` 漏过（`轻` 不在修饰语表、`叹` 在动词表 ⇒ 中间"轻"让整条不匹配）。
  修法：修饰语表补 `轻`、动词表补 `哼|嗤|摸|轻笑`；❗**刻意不加裸 `笑`**（会误杀合法台词 `（笑不出来）`）。
  ⇒ **洞不只在"动词表不全"，"修饰语+动词"的组合形态是另一类洞**。**函数真名 = `strip_action_parentheticals`**。
- **❗篇幅上限 = `main.AI_REPLY_MAX_CHARS`，现 220**；**换底座/调 num_predict 必须重跑 `measure_token_ratio.py`**。
- ⚠️ 已处置：`_clean_ai_reply` 在 `start_autonomous_speech._on_reply`(`main.py:4620`) 曾**未传 `recent`**（第 26 轮补 + B13b 锁）。

## 6. H4/H5 上帝类拆分（**全文详版 §8.1–§8.6**）
- 基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**Wave 1 七项 ✅ + 第 26 轮复审判"合格"**；**Wave 3 不在范围**。
  ★**预声明区 = 宿主 `init_systems()`**（`main.py` L660，状态块 L770–806；**不是 `__init__`**）。
- ❗**`scan_method_index.py` 只是线索，不是范围定义** —— **四类偏差都出现过**（漏标/误纳/跨区散布/方案自身错）
  ⇒ **必须与排期方案交叉核对 + 逐方法人工确认**。
- ⚠️ **W1 转发铁律：双向 `__getattr__` 两侧都须显式白名单**：宿主侧**只能** `getattr(type(ctrl),name)`，
  **绝不** `hasattr(ctrl,name)`。**`RecursionError` 崩在构造期 → G2 抓不到**。`_CONTROLLER_ATTRS` 在 `main.py` L512。
- ❗❗**W1 搬运铁律 8 条 + A/B 结构性盲区 → 详版 §8.5**。

## 7. 场景系统线 / 原作机制（第 28–31 轮，**全文详版 §16/§17/§18/§19/§20**）
用户口径：**「把原作的世界搬到桌面上…桌面也会被我当成一个场景」** + **「一切根据原作」**。
- **P0**（`0aba480`）：`scene_system.py`（数据层纯函数）+ `scene_controller.py`（接线层）+ `assets/scenes/*.json`；
  ★★ **P0 判据 =「不切场景时零行为变化」**：`switch()` **只写状态**、不动画面/定时器/物理；
  **一旦 P0 就改了画面，这条最强判据就丢了**。
- **路由层**（`52d5514`，锁 `scene_routing` 106 项）：`modules/scene_routing.py`（**纯标准库、零 Qt**）+
  `assets/scenes/_routes.json`。★★ **路由是数据，不是代码**（规则全在 JSON，代码只做「读 + 匹配」）。
  语义：`when_scene/area/chapter` 相等 + `"*"` 通配；`when_mood/event` 单值或数组；
  **`when_keywords` 是 OR**（与其余键的 AND **刻意不同**）；排序 = `priority` 升序 → 命中数降序 → 声明序。
  **三律**：① 匹配不到返回 `None`（**绝不伪造默认路线**）② 坏规则跳过 ③ 未知键放行。
  ★ **只有 `follow_route` 允许调 `switch`**（锁 H1–H5）；**`destinations()` 过滤未登记场景**
  （否则 AI 被送往不存在的房间，表现为"走了一半停住"，难查）。
  ★ **`_as_set()` 坑**：`set("abc")` → `{'a','b','c'}` ⇒ 字符串一律当**单个值**。
- ★ **原作机制**（GML 实证 `scr_roomname`）：房间 ID **扁平整数**；**同一 id 不同章是不同房间**
  ⇒ **id 必须与 chapter 联合才唯一**；显示名**两段式**；★ **原作没有显式"区域"结构**，我们显式化成 area 更强。
  **房间数 Ch1~Ch5 = 20/20/8/19/20，合计 87 间**（`原作场景线路研究_2026-09-22.md`）。
- ★ **为什么现在不登记原作场景**：**素材还没做** → 切过去 = **一个空场景** = 「**世界突然变白**」，**比不切更糟**。
  **落地三步（零改代码）**：① `_index.json` 登记 → ② 放 `<scene_id>.json` → ③ `_routes.json` 加规则。

## 8. 性能线（第 29–31 轮，**全文详版 §17.3/§18/§19/§20.3**）
- **硬件真相**：Intel Core Ultra 5 125H + **Intel Arc 核显 + 31.6 GiB 内存**，**无独显、无独立 VRAM**。
  用户说"32GB 显存"→ 实为**内存**。Ollama 跑**纯 CPU**（`library=cpu`、`size_vram=0`）⇒ **Vulkan 救不回冷 prefill**。
- **4B 实测**（219 次真实推理，源 `server.log`）：**avg 8.07 tok/s**；**12 tok=1.49s / 20 tok=2.48s / 40 tok=4.96s**。
- ★★★ **首字（TTF）铁律（第 30–31 轮核心机制）**：
  **决定首字的是「KV 前缀缓存是否命中」，不是模型大小、也不是 prompt 长度。**
  · 4B 产品真 persona（2322 tok）：**冷启 36.82s** vs **复用前缀 1.91s**（同长度差 19 倍）。
  · 7B 同 prompt（2050 tok）：**冷启 103.6s vs 命中 0.55s（190 倍）**。
  · 变化段"位置"差 **29.4 倍**（靠前 73.44s / 末尾 2.50s）；**前缀连续时 2509 tok 首字只要 0.207s**。
  ⇒ **必须把"每轮必变"的部分压到 system 最末尾**（persona 稳定前缀才复用得上）。
  ★ **prefill（首字）远慢于 decode（生成）** ⇒ 用户体感的"慢" = **首字慢**。
- **★ 第 31 轮采用方案**（`_evidence/ttf_strategy_7b.txt`）：**变化段压末尾 + 历史折进 system** = **平均首字 4.601s** ✅
  （原状 6.549s 超标；"状态塞 user" 2.808s 达标但**第 18 轮已否**）。
  ★ 副产品：历史带 `[他]/[你]` 前缀折进 system 后，模型对"谁说了什么"理解**反而更准**。
- **7B**：**已装好**（`ralsei:v4` = `qwen2.5:7b-instruct-q4_K_M`，4.68 GB），**第 31 轮起为默认底座**。
  ★★ **进度判断铁律**：`-partial` 是**稀疏预分配**（大小与进度无关）；16 个 `-partial-N` 是
  **进度标记不是分片**。**唯一可信进度源 = `/api/pull` 的 `completed`/`total`**。
  ❗**`/api/pull` 探测提前 `break` → 日志报 `context canceled`**，看着像网络故障。
  ❗**Ollama 模型目录 = `C:\Users\23002\.ollama\models`**（**不是** `%LOCALAPPDATA%\Ollama\models`）。

## 9. 用户口径（**优先于我的技术判断，违者返工**）
- **「prompt 尽量完整」** —— 明确否决"砍 prompt 长度"路线 ⇒ 提速只能靠**缓存 / 后端 / 换模型质量**。
- **「1~3s 是首字的延迟」** —— 验收指标 = **TTF**，不是整句（第 31 轮放宽到 **5s**）。
- **「用 7B 目的就是让他贴合人物并且不出 bug」** —— 动机是**质量**（人设贴合 / 减少格式崩坏），**不是速度**。
- **「7B 为默认吧」** —— 第 31 轮已落 `config.json` + `ralsei:v4`；**回退只需把 config 改回 `ralsei:v3`**。
- **「他经常说结巴的话，这有点不好」**（澄清后）= **太多了要减少** —— 但**不许砍到 0**：
  真结巴是人物真实性的一部分（实测本来只有 8.3%）。要治的是**固定模板句**（见 §5）。
  ❗**用户还暗含两点尚未实现**：结巴率应**随熟悉度（trust）提升而下降** + **只在紧急/紧张时出现**
  （原话「会随着熟悉度提升慢慢下降，除非遇到什么紧急情况这类的（就是人会在什么时候结巴）」）
  ⇒ 方向 = **接进 `relationship.py` 的档位做动态结巴率**，**待排期**。
- **「开机自启…是选项，不是硬性代码」+「后期等咱项目结束的时候」** —— 做成配置项（默认 false），
  **实现留到项目收尾**（第 31 轮只预留 `startup` 段）。
- **「一切根据原作」** —— 场景/线路/命名以原作 GML 实证为准。

## 10. 历轮索引（细节去详版 + `.workbuddy/memory/<日期>.md` + 对应报告）

| 轮 | 主题 | 详版 | 状态 |
|---|---|---|---|
| 26 | 首轮全项目复审 + H4/H5 处置 | §14 | ✅ `5c0a3e7`/`d5ab8d4` |
| 27 | AI 失真治理（三源全治） | §15 | ✅ `685f98b`；复读 62%→33% |
| 28 | 场景系统 P0（留接口） | §16 | ✅ `0aba480`；G2 1250/25 |
| 29 | 场景路由层 + 7B 评估 | §17/§18 | ✅ `52d5514`；G2 1358/26 |
| 30 | 产品链路首字实测 + 用户口径纠正 | §19 | ✅ `aaa89f8`/`8b4d50c` |
| 31 | 7B 设默认 + 首字进 5s + 治固定开场白 | §20 | ✅ `eb806e4`；G2 **1359/26** |

## 11. 🔴 待用户裁定（**开工前必看**）
1. **场景美术素材来源**（**P1 开工前唯一阻塞项**）：`<仓根>/deltarune_ralsei/` 1111 张 PNG **全是角色精灵**；
   `assets/sprites/`、`assets/faces/` **空目录**；全仓库搜 `bg_`/`tileset`/`room_`/`map_` **零命中**
   → **A 程序化生成 / B 用户截图 / C 重绘 → 推荐 A+B**。
2. 另：场景粒度 ｜ 是否要 BGM（现 `sound_manager` **只有 3 音效、无 BGM 能力**）｜ 原作版权尺度。
3. **动态结巴率**（见 §9 用户口径）：是否接进 `relationship.py` 档位。
4. **沿用第 26 轮**：`dialogue_ui._rule_reply()` 罐头皮 ⇒ 「AI 关必沉默」是否也管"用户主动打字"。
5. **待办**：真机手感实测（用户侧）｜`.gitattributes` 换行口径（**先议后动**）｜`_tmp`/`.bak` 存量
   （**等用户点头，不得批量删**）｜H4「文件反应」专项。
6. **开机自启 + 预热**（用户口径：**「后期等咱项目结束的时候」**）—— 实现留到项目收尾。
7. 是否试 **Vulkan 后端**（已实测：**救不回冷 prefill**）。
