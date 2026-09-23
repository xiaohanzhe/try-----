# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **全文（§0–§39）在 `参考-契约与历轮（详版）.md`**（**不自动注入，改动前 Read**）。
> 本文件只留**每轮必守的铁律 + 索引 + 待裁定**。
> ⚠️ 注入上限（**代码实证**，非估算）：**≤ 200 行 且 ≤ 25,000 字节**（按 `utf-8` **字节数**判，不是字符数；超限从尾部砍）⇒ 现 110 行 / 20.7 KB ✅ **在限内**。
> ⚠️ 服务端另发过一条「exceeded the size limit」提醒，但本地产物里**查无此文案**、阈值未证实 ⇒ 以 200 行 / 25 KB 为准，别据传闻乱压。
> **压缩前必须先把细则补进详版**（skill `agent-memory-compaction`）+ **逐令牌回验**。

## 0. 铁律
- 每轮改动完成即 **commit + push**；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根；证据进 `code-quality-audit/<轮次>/_evidence/`；下载/生成物落 `E:\Download`（临时件 `_tmp\` 用后即删）；**仓库内产物留项目目录**。
- ❗**仓库根 = `try - 副本`**（`ralsei_pet` 是子目录）⇒ **跑 G2 的 cwd 是仓库根**。
- 远端 `https://github.com/xiaohanzhe/try-----.git`（★**公开**），main→origin/main。真机起：`Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`；单实例锁 `Global\RalseiPetMutex`；窗口透明非置顶 FramelessWindow ⇒ **甩飞/抛物线只能离屏断言**。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（现 **32 套件 / PASS=1517 / 全 IDENTICAL**）；它跑 `compileall` 会改写被跟踪的 `src/__pycache__/*.pyc` ⇒ 收工前 `git checkout --`；★ 改了断言/文案 → `--only <suite> --update`（**合并模式**），**别全量 update**。❗**判据消息里别印绝对行号/会漂的计数**（第38轮：main.py 头插 19 行 ⇒ `round34b` 与内容无关地假 DIFF ⇒ 假 DIFF 会养成"看都不看就 update"的习惯）。
- ★ **只读优先、改动最小化**：审查阶段不改被审文件；修复一次只动必要处，每处配独立断言。
- ❗❗**改过"重要核心文件"必须复检**（用户口径）→ 可编译 / 结构 / 编码 / 恒真判据复查 / **逐令牌回验** / 工作区干净，逐项 PASS/FAIL 落盘（skill `core-file-recheck`）。**别只说"改完了"。**
- ★★ **"我写了 N 个文件"必须 `os.listdir` 查磁盘**（第38轮：生成器只数内存 list ⇒ 报 61/61 PASS，磁盘只 12 个）。

## 1. 环境（详版 §1/§18/§19/§21/§23.10/§37.5/§37.8）
- ⚠️ **Bash 常整体坏掉**（`ls/head/cat/tail` 全 127）→ **一律 Python + Write/Read**；`Glob/Grep/Read`/`cd && git` 照常。❗别从 Bash 调 PowerShell（stdout 不回传）；❗❗**别内联 `python -c`**（反引号被吞）。
- **起进程** `&` + `run_in_background:true`；**杀进程** Python+psutil；`wmic` 已移除 → `Get-CimInstance`。Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）。
- ❗❗**体检/临时备份绝不放工作区**（第34轮续三：整目录被 `git add -A` 记为删除并提交 ⇒ 磁盘真删）⇒ 一律 `E:\Download\_tmp\`；**提交前必看 `git diff --cached --numstat`，deletions >1000 立刻停手**。
- ❗**清理守卫按路径累计删除计数（阈值 50）**：症状 = **import 期被 SIGTERM、零输出**；"移出索引但留磁盘"用 **`git rm --cached`**；**先干掉触发源**。
- ★★ **写入通道会整体失效**（第37轮，~25min 自愈）：已有文件写/改/移全被拒、**新建文件正常** ⇒ 绕法 = 只产新文件 + 脚本换版本号名；判据 = `%TEMP%`/仓库 `.git`/目标目录 三探针（§37）。
- ⭐⭐ **代理端口必须"逐端口实测 CONNECT"再选**（`7897` 通 / `7375` 死）；盲试 ⇒ push 卡 19 分钟且不留输出。
- **证据/报告一律 Python 自写 UTF-8**；❗**"能力自评失准"比"能力不足"更危险**；注入的 `current_time` 滞后 → 先 `Get-Date` 校准。
- ⭐ **无 `.gitattributes` 而 `autocrlf=true`** ⇒ **编辑必须保持原 EOL**，逐字节参照系只用 `git cat-file blob`；❗`git checkout` 还原后**必须复查 EOL**；中文路径被转义 ⇒ 核验存在性**必须** `git ls-files -z` + `surrogateescape`。❗★ **大目录遍历别"逐个名字 glob"**（上千名字 × 2.3 万项 ⇒ 被 SIGTERM）⇒ **先 `os.listdir` 只列一次**。
- ★★ **记忆注入上限 = 200 行 / 25,000 字节**（`utf-8` **字节数**，不是字符数；代码实证 `buildAgentMemoryPrompt`）⇒ 见 `truncated` 提醒**先量再压**，在限内就**别压**（第38轮据错判据压缩 ⇒ 白丢 4 个令牌，详版 §39.11）。

## 2. git push（skill `win-git-utf8-push`；细则 **§39.5**）
- 提交信息 **Write 写 UTF-8 文件 + `git commit -F`**（`-m @'...'@` 被 PS 5.1 拆 argv ⇒ 退 0 **假成功**）；提交后必核 `git log --oneline -1`。`subprocess.run(input=...)` **必须喂 bytes**（str → `TypeError` 被吞 ⇒ push 静默跳过，像网络问题）。
- ❗**核验命令自己也会说谎** ⇒ `ls-remote` **独立构造** + 重试 3~5 次 + `git rev-parse origin/main` 交叉验证。★ **本仓库公开 ⇒ `ls-remote` 是恒真判据**（匿名也能列 ref，≠ 凭据可用；第38轮据此误判后 push 挂死）。
- ★★ 两根因与正解（详见 §39.5）：**TLS** = `schannel` 吊销检查必失败（`CRYPT_E_NO_REVOCATION_CHECK`）⇒ `-c http.sslBackend=openssl -c http.sslCAInfo=<系统CA PEM> -c http.version=HTTP/1.1`（PEM 用 PowerShell 导 `Cert:\*Root`+`CA`）；**凭据** = 宿主注入的 `credential.helper=helper-selector` **不读** Win 凭据管理器 ⇒ 弹 GUI 挂死（确诊 = psutil 扫 `git-credential-helper-selector.exe`）⇒ **直取 GCM**：`GCM_CREDENTIAL_STORE=wincredman`（**不是 "windows"**）/ `GCM_INTERACTIVE=never` + `-c credential.helper=` + `http.extraheader=Authorization: Basic <b64>`。
- ★ **工具** `_tools/gitpush.py` 一把跑完（add → numstat 守卫 → commit -F → GCM → push → 双向核验）。⛔ **绝不循环重试 push**（每次 = 一个弹窗）。

## 3. 勿回退契约（详版 **§4.1–§4.12 + §10 + §23.9**，开工前必读）
13 组契约（多屏/甩飞/动画/联想/抽词/网图/**建楼**/存储/初始化环/jieba/DPI/G2 封闭性/误报清单）。最易踩六条：
① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
② 建楼：**`floor_visible_contains` 是唯一判据**、**禁用 `Qt.WindowStaysOnTopHint`**；`get_drop_destination`/`find_support_below` **只取"下面第一个"**；`get_current_floor` 几何优先、`WindowFromPoint` 只做**"只向上"**兜底；⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前**；★ 不做"逐层小跳"；★ **`show()` 有"提到前面"副作用 ⇒ 先 `show()` 再调 z 序**；★ **甩飞路径必须显式 `self._fall_reason = None`**；★ 判定函数放**模块级**（套件用 `SimpleNamespace` 桩）；
③ **`A in rev[B]` 检反向是恒真判据**；**鉴别力体检必改文件**；
④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\`，迁移**只复制不搬走**）；被反向依赖的底层模块一律 `lazy_log.LazyLogger`；裸进程脚本**先建 `QApplication` 再读坐标**；
⑤ **G2 `run_all.py` 有 `HERMETIC_IDS`**；`save_baseline` 是**合并模式**；
⑥ ★★ **新套件必须 `print('[PASS] %s')` 字面量** —— `run_all.py:425` 用 `re.findall(r'\[PASS\]|\[\s*OK\s*\]', text)` 计数，写成 `"  PASS  msg"` 会让 **PASS 恒为 0**；新套件放 `code-quality-audit/<轮次>/` ⇒ `ROOT = os.path.join(HERE,'..','..')`（**两层**）。
**误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已 `pyqtSignal` 排主线程；`reset_special_states` 零调用；`pet_interaction.py` **全模块零接线**（孤儿，AST 实证，**待裁定 §11.6**）。

## 4. 验证脚本教训（详版 **§5 + §8.4/§8.6 + §23.4/§23.5/§23.12/§35.6/§39.1**）
- ⭐**能上 AST 就上 AST**：`code_only_src()` **会剥 STRING token** ⇒ 断言**字面量**必恒假（**踩 7 次**）；含字面量走 `code_no_comment()`；零引用筛查一律走 AST；❗AST 扫属性必须同时扫 `ast.Constant` 里的同名字符串；★ **复检规则表别手抄** → 用 AST 从生成脚本抽出来 exec（第38轮）。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制成对**；**断行为/结构不断赋值/写法**；**恒真判据比不写还危险**；❗**报红先自问"夹具真把破坏写进去了吗"**；⭐**两个断言同时报红，处置方向可能相反** ⇒ **先读原文再定**。★★ **报红先怀疑判据本身**（第38轮 5 次报红/报绿全在判据侧：目录名拼错 / 反面控制选错 / 口径定错 / 只数内存不查磁盘 / 裸 JSON 形状弄错）。
- **探针不保真 = 报假问题**（**已踩 4 次**）→「**能从源码拿的别 import；能 import 的别重写；不得不重写必须锁等价**」；❗❗**"分类器太窄"和"闸有洞"长得一样** ⇒ 必须拿产品函数逐条复核。★★ **任何"缺陷成立/修复无效"的结论，先复核探针**。
- ★★★ **测行为判据必须用真实量级输入**（裸测 4B 首字 0.6~0.7s 报"合格"，产品真 persona 实测 36.82s）；★★ **需真人操作的行为判据（抚摸/拖拽/甩飞体感）严禁离线模拟下结论**（要保真只能**真机打点落 CSV**）；**连续两次探针失真 ⇒ 停下来质疑方法本身**。
- ★★ **跨进程比对屏幕坐标前先确认 DPI 感知一致**；**能从运行时读到的量就别推算**；**零可见后果的口径不一致归 P3**。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）**；镜像：**"没改也没人调用"要么接线、要么删**。
- **A/B 纪律**：先断言 **A ≠ B**（旧值若已提交 → 取**父版本** `git cat-file`）；桩打在「方法体里 `self` 的那张类」；**A/B 只证"两版等价"**。★★ **「删掉重复行」≠「去掉重」**：以**运行时等价**为准。

## 5. 人味改造线 ★ 动手前**必须 Read 详版 §23.13.1**
回归锁 `persona_chat`(156)/`s8_stream`(69)/`s7_event_speech`(138)，**均进 G2、不联网、不调 Ollama**。
- **人设单一真源 = `assets/ralsei_persona.md`**（每次读出来当 `system`）。**别只写 Modelfile**（Ollama 用 messages 的 system **整体替换** Modelfile 的 SYSTEM）。persona **是 prompt 不是文档**（禁 markdown）；**❗不许叫"主人"**（persona + 代码两层）；**上限 K3 < 10000 B**（现 9946 B）⇒ **加内容前必须先瘦身**。
- ★★ **失真头号来源 = persona 里"可逐字搬走的固定例句"** ⇒ **示例区不许"按场合分组 + 冒号 + 固定例句"**（**格式本身**就在教照搬）。锁 **A12d**。★★ **"口癖多"≠ 全砍**：**真口癖**（真结巴仅 8.3%）**属人物真实性、别砍**；**固定模板句必须砍**。
- **护栏 `_clean_ai_reply(reply, recent=)` 顺序 = 优先级**：0a 句中括号动作 → 0b 剥 markdown → 0c 禁说清单 → 1 自问自答截断 → 2 车轱辘话判退（**只看 recent**）→ 3 超长截断；❗**0a 先于 0b**；**判退后必须重采样一次**、**判退不 append 进 recent**；★ **括号旁白判据 =「抓形态特征」不是「首词白名单」**；❗**刻意不加裸 `笑`**。
- **❗`main.AI_REPLY_MAX_CHARS` 现 220**；**换底座/调 num_predict 必重跑 `measure_token_ratio.py`**。
- `relationship.py`（`TRUST_INITIAL=0.12`；`harsh` 别变死事件）/ `event_speech.py`（唯一出口 `speak_event`、`pool=None`→沉默）、`ralsei:v4` 回退法、**S8 流式 `iter_lines(chunk_size=1)`**、**A12e 反伪造共同经历** → **细则全在 §23.13.1**。

## 6. H4/H5 上帝类拆分（详版 §8.1–§8.6；Wave 1 已完成，休眠线）
- 基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）。**预声明区 = 宿主 `init_systems()`**（`main.py` L660；**不是 `__init__`**）。
- ⚠️ **W1 转发铁律**：双向 `__getattr__` 两侧都须显式白名单，宿主侧**只能** `getattr(type(ctrl),name)`、**绝不** `hasattr(ctrl,name)`（**`RecursionError` 崩在构造期 ⇒ G2 抓不到**）；`_CONTROLLER_ATTRS` 在 L512。❗`scan_method_index.py` 只是线索；**搬运铁律 8 条 → §8.5**。

## 7. 场景系统线 / 原作素材 ★ 动手前**必须 Read 详版 §16/§23.13.2/§36/§37/§39**
用户口径：**「把原作的世界搬到桌面上…桌面也会被我当成一个场景」** + **「一切根据原作」** + **「把所有都拿出来啊，别就拿87个」**。
- ★★ **P0 判据 =「不切场景时零行为变化」**：`switch()` **只写状态**、不动画面/定时器/物理。`bg` 字段**尚无渲染层消费**。
- ★★ **路由是数据，不是代码**：`modules/scene_routing.py`（**纯标准库、零 Qt**）+ `assets/scenes/_routes.json`。**三律**：① 匹配不到返回 `None` ② 坏规则跳过 ③ 未知键放行。★ **只有 `follow_route` 允许调 `switch`**。
- ★★★ **排序键 `(priority 升序, -score 降序, 声明序)` ⇒ `priority` 压过 `score`** ⇒ **兜底给低 priority 会把所有剧情路线判死刑**。分层：1xx~5xx 剧情推进 / 7xx 软触发 / 8xx 场景内细节 / 9xx 归处 / 10000 兜底。`_FALLBACK_PRIORITY` 是**死常量**（待修）。
- ★★ **房间真相（第38轮修正）**：五章共 **1,251 room**，可当场景 **1,013**（`maybe` 37 / `nonscene` 201）；`_original_rooms.json` 只是 `scr_roomname()`（**存档点地点名**）的转写 = **90 个官方命名地点**（87 已登记）⇒ **它是地点名全集，不是房间全集**。`scr_get_room_list()` 是**跨章共享注册表**（≠ 本章清单）。`scr_roomname(arg0)` 的 arg0 = `rooms_map` 下标。区域 32 个 / `(章,区域)` **61 个**。
- ★ **原作机制**（GML 实证，仍有效）：房间 ID = **扁平整数 + 章号进万位**（`chapter*10000+local`）；**显示名两段式**（"区域"由 ` - ` 前缀反推）；**`room_goto` 只管"换"** ⇒ 路由与渲染必须分层。
- ★★ **数据两来源**：独立 `<scene_id>.json`（87 锚点，**未动**）+ 区域分片 `_zone.<章>.<区>.json`（926 新场景 / 61 文件）。`load_scene(sid, dir, entry)` **独立文件优先**；独立文件坏掉**不静默换源**。**`switch()` 必须把 entry 传下去**，否则 926 个场景全加载失败。实测：索引 3.5ms / 单片 0.79ms / 61 片 48.5ms / 增量 0.74MB（1,013 个小文件全读 = 835ms ⇒ 分片是正解）。
- ★ **命名口径 = 不译**：`区域中文名·尾段原样`（去掉命名空间与区域词）+ `name_raw` 溯源。**译名 = 伪造本地化**，违反「算不出 → 绝不伪装」。⚠️ **数字/单字母 token 是区分符，别当噪声丢**。926 个新场景 `bg: null` + `bg_source: "none"`，**不编造区域代表素材**。
- ★★ **P0 接线已落（第38轮）**：`main.py` `init_systems()` 末尾调 `self.scene.load()` + `load_routes()`（只读 JSON + 写宿主状态、零消费者 ⇒ 零行为变化；两者永不抛且幂等）。真机 **10/10**（`_evidence/真机_P0接线验证.txt`），含负控制。**P1 才是渲染层**。
- ★ **原作素材**：`data.win`（GMS2）用 **UTMT CLI v0.9.2.0**（`E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe`，必须关 stdin）；**背景在 `room.Layers`**（`Backgrounds` 空）；**多数房间没背景精灵**（147 房里只 40 层带 `bg_sprite`）⇒ 兜底 = "区域代表素材 + 平铺"；**真背景原样提取，只有平铺才合成画布**（9 真 / 78 区域）。87/87 已就位。⚠️ 早期解析的 `ROOM/SPRT/OBJT.json` **不可信**。

## 8. 性能线 ★ 铁律（详版 §17.3/§18/§19/§20.3）
- **硬件**：Core Ultra 5 125H + **Arc 核显 + 31.6 GiB 内存**，**无独显无独立 VRAM**（"32GB 显存"实为内存）；Ollama 跑**纯 CPU** ⇒ **Vulkan 救不回冷 prefill**。
- ★★★ **首字（TTF）铁律**：**决定首字的是「KV 前缀缓存是否命中」**，不是模型大小、也不是 prompt 长度。4B 真 persona：**冷启 36.82s** vs **命中 1.91s**（19 倍）；7B：**103.6s vs 0.55s**（190 倍）⇒ **每轮必变的部分压到 system 最末尾**。★ **prefill 远慢于 decode** ⇒ 用户体感的"慢" = **首字慢**。★ **第31轮方案**（变化段压末尾 + 历史折进 system）= **平均首字 4.601s** ✅（验收 TTF ≤ **5s**）。
- **7B**：`ralsei:v4` = `qwen2.5:7b-instruct-q4_K_M`（4.68 GB），**默认底座**；❗**模型目录 = `C:\Users\23002\.ollama\models`**（**不是** `%LOCALAPPDATA%\Ollama\models`）。

## 9. 用户口径（**优先于我的技术判断，违者返工**）
- **「prompt 尽量完整」** ⇒ 提速只能靠**缓存 / 后端 / 换模型质量**，不许砍 prompt。
- **「用 7B 目的就是让他贴合人物并且不出 bug」** ⇒ 动机是**质量**，不是速度。**「7B 为默认吧」**已落。
- **「他经常说结巴的话，这有点不好」** = **太多了要减少**，但**不许砍到 0**（真结巴仅 8.3%）；❗**暗含两点尚未实现**：结巴率随 trust **下降** + 只在紧急/紧张时出现 ⇒ **待排期**。
- **「开机自启…是选项，不是硬性代码」+「后期等咱项目结束的时候」** ⇒ 配置项（默认 false），留到收尾。
- ★★ **当前主轴**：**场景系统**（第36–38轮）；**移动/行为**已收（第34轮）；**严查现有基础代码纰漏**；**这一阶段完全 ok 才进下一阶段**。
- ★★ **工作方式（第34轮）**：**「不必要每次变完一轮就暂停一次，大可以你测完了没问题后，然后按照你的计划来」** ⇒ **测完绿了就按自己的计划连续推进**。
- ★ **36轮**：「**开始按照原版的路线**…**场景系统完全遵循原作逻辑**，**桌面当默认场景**」。**37轮**：「**我不会导出，要不还是你自己反编译出来吧**」。**38轮**：「**别一次性加载全部房间…像是拿火把赶夜路，走到哪亮到哪**」「**记得严格些，做完了仔细复查**」「**复检一下有没有纰漏**」。

## 10. 历轮索引（细节见详版 §14–§39 + 当日 `.md` + 项目根报告）
- **26–31**：复审+H4H5 / AI 失真 / 场景 P0 / 路由层 / 首字实测 / 7B 默认（§14–§20）
- **32–33**：结巴取证（真凶=固定模板）+ 换窗口/游戏源勘察（§22）
- **34**：移动/行为严查 + 跳跃统一 + 楼层 F7 + 存储/配置 4 缺陷（§23；G2 1427/29）｜**34续**：交互接线 / 动画播放 / 移动核心 F34-1 / F34-4 隐私断链 + **modules 误删事故（已恢复）**（§23.12–§23.15，`8f95f5e`/`438aa87`/`fe14b59`，1450/31）
- **35**：真机 10 分钟监测（8 判据全 PASS）+ F35-1/F35-4（§35；5 次判据失真全在工具侧）
- **36**：按原作路线排场景（88 场景 + 26 路由，G2 **1500/32**；**priority 压过 score**）（§36）
- **37**：反编译原作素材 → **87 张场景背景落地**（§37）
- **38**：审查已写代码（21/21 + 36/36 + 11/11 + 15/15）+ 抓出「场景只有原作 8%」P0 → **全量落地 1,013 场景 / 61 区域分片** + **push 链路三根因** + **P0 接线（真机 10/10）** + 3 处代码瑕疵 + `_original_rooms.json` 修正（20/20/9/20/26）+ **修掉我自己的记忆上限错判据**（G2 **1517/32**）（§39，`6ea5998`/`f117aed`/`7e848f1`/`270e970`/`af12a3b`/收尾）

## 11. 🔴 待用户裁定（详版 §23.13.3 + §36.8 + §37.11 + §39.10；开工前必看）
1. **场景美术**：87 张已就位；❗**78/87 是"区域代表素材"近似**够不够？❗平铺画布（宽 1280 / 高 `1280×clamp(rh/rw,0.5,0.9)`）是否接受？❗**926 新场景暂无背景**（待 §11.11）。
2. 场景粒度 ｜ BGM（`sound_manager` **只有 3 音效、无 BGM 能力**）｜ 原作版权尺度 ｜ `dialogue_ui._rule_reply()` 罐头皮 ⇒「AI 关必沉默」是否也管"用户主动打字"。
3. **待办**：真机手感实测（用户侧）｜`.gitattributes` 换行口径（**先议后动**）｜`src/` 顶层 `.bak`/`test_*`/`monitor_*.txt` 存量（**等用户点头，不得批量删**）｜H4「文件反应」专项。
4. **开机自启 + 预热 / Vulkan 后端**（实测**救不回冷 prefill**）—— 留到收尾。
5. ★ **P3 遗留**：死函数清理 / 空闲分支补 3 条件 / 5 个孤儿状态位复位 / 楼层 2 处区间口径不一致（`nearest_visible_point`、`get_jump_destinations` 用闭区间 vs `_rect_tuple` 半开，差 1px）/ **35轮** `_sleep` 名拼错（「小憩走路」从未生效）/ `play_animation_once` 51 处调用仅 8 处传 `restore_to`。
6. ★★ `pet_interaction.py`（365 行，**全模块零接线**，AST 实证）→ **A 删除 / B 接线 / C 暂缓**，**建议 C**。
7. ★ **36轮遗留**：**`progress` 概念（房间级推进，P2）**；**动态结巴率**是否接进 `relationship.py` 档位。
8. ★ **37轮遗留均已结清**（E3 升级 + E3b/E3c；ch1 `rooms_map.json` 重跑属不成立）。
9. ★★ **38轮遗留（P0 部分已结清）**：~~`load()` 未接线~~ / ~~3 处瑕疵~~ / ~~`_original_rooms.json`~~ **均已修**。**剩**：**路由重建**（现 26 条只覆盖 ch1~ch5 主线，1,014 场景可达面未铺开 —— 属设计决策，待用户过目）；**#17 为 926 个新场景补真实背景**（原作多数房间本就没背景精灵，硬造 = 编造，须先定口径）。
10. ★ **#17 待办**：为 926 个新场景补真实背景素材（沿用第37轮管线）。
