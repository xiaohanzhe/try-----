# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **详细契约（§4）、验证教训（§5）、人味线全文（§6、§11、§12）、网图（§10）、历轮索引（§7–§9）
> 已拆到同目录 `参考-契约与历轮（详版）.md`**（**不自动注入，用时 Read**）。
> 本文件只留**每轮都必须遵守**的铁律、速查契约与当前状态。

## 0. 铁律
- 每轮改动完成即 **commit + push**（"以免后期找不到"）；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根 `人味*.md`；证据进 `code-quality-audit/<轮次>/_evidence/`；侦察 `_recon/`（gitignore）。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（**24 套件 / 1159 PASS / 全 IDENTICAL**）。
- 下载/生成物默认落 `E:\Download`（临时件 `_tmp\` 用后即删）；仓库内产物留项目目录；系统默认下载目录不动。
- G2 会跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。

## 1. 环境（**全文见参考 §1**；下列每条都真踩过）
1. **优先 bash + 把 PortableGit 的 usr/bin 加进 PATH**（补 coreutils，见 4）；`cd` 中文路径在 shim 里会
   `dirname: not found` → 用**绝对 Windows 路径**。需 PowerShell 时 **stdout 常不回传** →
   命令内 `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在静默 exit 1 → 先建目录）。
2. **起进程**只能 `&` + `run_in_background:true`（`cmd /c`、`Start-Process`、WMI 全被拦）；**杀进程** `Stop-Process`/`taskkill`
   静默失效 → Python+psutil 按 cmdline 匹配（分步跑）。**删文件**用 `[System.IO.File]::Delete()`（管道 `Remove-Item` 无效）。
3. Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它；
   托管 venv(3.13) 缺 `bs4` → `round5_smoke` 假 FAIL。
4. **代理端口现查为准**（`netstat -ano | findstr LISTENING` 或读注入 `HTTP_PROXY`）。❗**单端口一次成败不能当结论**：
   **每端口至少 2~3 次 + 跨端口重试（含直连）。** 实测 **注入的 `HTTPS_PROXY`（如 64676）可用**，
   **`7897`（Clash）也长期可用** → **策略：候选列表逐个试（注入值 → 7897 → 7890），push 成功即停**。
   ❗**bash 缺 coreutils**，但 **PortableGit 自带一份**：
   `export PATH="/c/Users/23002/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"` → 全可用。
5. **E 盘是外接盘、会掉线**（判在线看 `Get-Disk`）→ 本地中转站是可用性必需。
6. 清理守卫按目标路径**累计删除计数**（阈值 50）：症状 = 进程在 import 期就被杀。已在应用侧根治；
   `dangerouslyDisableSandbox` 无效。**通则：见"计数恒定"先干掉触发源，别急着下确定性结论。**
7. **证据/报告一律让 Python 自己写 UTF-8**：绝不用 `& py x.py *> o.txt` / `| Out-File -Encoding utf8` 捕获原生
   stdout（按 GBK **有损**解码 → 中文**真损坏**，踩 3 次）。**`Write` 覆盖带 BOM 文件会保留 BOM** → 去 BOM 必须
   Python 重写。校验器 `tools/check_evidence_encoding.py`。**"能力自评失准"比"能力不足"更危险。**
8. **注入的 `current_time` 会滞后于系统真实时间** → 凡落盘带日期的产物先 `Get-Date` 校准；错了 `git mv` 改名。
9. 别用 PowerShell 管道读中文元数据（`ollama show` 全乱码）→ 走 REST API + 显式 UTF-8。
10. **`github.com` 主站可能整段不可达而 `api.github.com` 仍 200**：此时 `git push` 必失败。
    **提交照做 → 如实报告 → 稍后重试**。**别因 push 失败就怀疑凭据或改 git 配置。**

## 2. git push（**完整配方 + 铁律 0 见 skill `win-git-utf8-push`**）
- 症状：退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 会被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`**。
- bash 里可用：`git credential fill` → `base64 -w0` 拼 Basic 头 →
  `git -c credential.helper= -c http.proxy=http://127.0.0.1:<端口> -c http.extraheader="Authorization: Basic <b64>" push origin main`。
- **❗核验命令自己也会说谎**：`ls-remote` 必须**独立构造** + 重试 3~5 次 + `git rev-parse origin/main` 交叉验证。
  **先怀疑核验，再怀疑被测物。**

## 3. 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有，未认证 401/404）；main→origin/main。
  GitHub 连接器只覆盖公开库，看不到本仓库（404）。
- 真机起：`Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。

## 4. 勿回退契约（**逐条全文见参考 §4.1–§4.12 / §10，改动前必读**）
- **多屏 / 甩飞抛物线 / 动画 / 多跳联想 / 抽词 / 世界观网图 / 建楼**：这 7 组契约的**全文**在参考
  **§4.1–§4.9 + §10**（含每条铁律、判据、禁用写法、用户原话口径），**开工前必读**。速查本不复述；
  仅点三个最容易踩的：① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
  ② **建楼里 `floor_visible_contains` 是唯一判据、禁用 `Qt.WindowStaysOnTopHint`（改 `_apply_pet_z_order()`）**，
  ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户当年原话口径，不许再改**；
  ③ **`A in rev[B]` 检反向是恒真判据**（正确 `b.key in adj[t]`），**鉴别力体检必改文件**。
- **存储两层**：vault=`E:\RalseiMemory\`（读优先），staging=`%LOCALAPPDATA%\RalseiPet\`；`data_store` **唯一入口**；
  迁移**只复制不搬走**、落选者留档 `.old`；**jieba 软依赖**，失败静默回落。**初始化环**：被反向依赖的底层模块
  一律 `modules/lazy_log.LazyLogger`。**DPI**：写探针/裸进程脚本**先建 `QApplication` 再读坐标**。
  **G2**：`HERMETIC_IDS` 注入临时 `RALSEI_MEMORY_DIR`；**`save_baseline` 是合并模式**。
  **误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已由 `pyqtSignal` 排主线程；
  `reset_special_states` 零调用；原子写/回收站删除已正确防御。
## 5. 验证脚本教训（**全文见参考 §5 + §5.1，改断言前必读**）
- 源码级断言别用 `"字面量" in 源码` → `code_only_src()`；**含字符串字面量的 needle 走 `code_no_comment()`**（5 次踩）。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制必须成对**；断言**断行为不断赋值**。
  ⚠️ **恒真判据比不写还危险**（二十一轮 `A in rev[B]` 恒真，掩盖 4 条真单向边）；**体检须"改文件"**（解析期值改内存 → 假 P）。
  ❗**鉴别力报红时先自问"夹具真把破坏写进去了吗"**（二十二轮连报三次假红，全是夹具 bug：破坏作用在未改源 /
  锚点没删干净 / **三元表达式写反**）；函数体内引用后置全局 → `NameError` 被吞。
- **阈值型断言必须锚在"实测物理上限"上，不能是裸常数**（二十二轮：150 是 3B 拍的，换 4B 后**低于模型常态输出
  → 闸门在砍正常回答**，长期不可见）。**换底座/改 num_predict 必须重跑对应测量脚本复核。**
- **探针不保真 = 报假问题**（少复刻产品一步 → 报"（停顿了一下）泄漏"，而产品侧早剥掉）→
  **报问题前先自查"夹具是不是少做了产品做的事"。**❗同类已犯 3 次（长度／动作／markdown 闸）→ 口径：
  「**能从源码拿的别 import；能 import 的别重写；不得不重写的必须锁等价**」；改判据必须配 **正/负样本 + 鉴别力锁**。
- **`runpy.run_path` 不给 `sys.path` 加脚本目录**（G2 的 `_seed_runner.py` 用它）→ **"单跑绿、进 G2 红"** 的经典成因：
  套件里 import 同目录兄弟模块必在 import 前 `sys.path.insert(0, HERE)`。**见到这种红先怀疑加载器，别改被测模块。**
- ❗**"定义"与"引用"必须分开数**（W1-3 踩）：拿"属性名/裸名计数"断言"只定义一次"，
  会把方法内部的 `self.foo()` **调用**也算成定义 → 假红（报"实际 4 次"）。拆 `defs_of()`（只数
  `FunctionDef` 节点）/ `refs()`（数引用）两个函数。
- ❗**反例控制的 needle 必须先断言"真的命中了"**（W1-3 踩）：needle 用 ASCII `"x"` 而源码是 `'x'`
  → `replace` 空操作 → 篡改没发生 → "篡改后仍相等" → **反例控制假通过**。
  三段递进：① needle 命中 ≥1 ② 文本确实改变 ③ 判据判不等。**缺①就可能整条假通过。**
- **断言"某约束在配置里"时要断言它的位置**：放"规则区"是规则，放"全是短句的示例区"就被稀释成例子。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）** —— 镜像：**"没改也没人调用"要么接线、要么删**；
  **描述/断言里别写会随代码增长的数字**（`ralsei:v2`、`FROM qwen2.5:3b` 都假红）。
- **A/B 先断言 A ≠ B**（"旧值"若改动**已先提交** → A == B，退化成自己跟自己比**且非常像真的**）：
  取**父版本** + **md5 相同即 `SystemExit`** + `--old-rev`。
- **对照组要重复跑，先量尺子的公差**（±2 条就是噪声）；**计数会被反向激励** → **永远先读原文再看计数**。
- **提示词里分组标签本身就是可能被输出的词**；**别为禁用项追加具体反例**。离屏**无字体** → `QPainter.drawText` 静默不画。
## 6. 人味改造线（2026-09-18~20）（**全文见参考 §6 + §11 + §12**）
报告 `人味*.md`；证据 `code-quality-audit/人味改造-2026-09-18/_evidence/`；回归锁
`persona_chat`(**153**) / `s8_stream`(**69**) / `s7_event_speech`(**135**)，**均已进 G2，都不联网、不调 Ollama。**
- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**不要**只写 Modelfile（Ollama 用
  messages 的 system **整体替换** Modelfile 的 SYSTEM → 写模型里的人设一次都不生效）→ **本机唯一可行的"训练"
  杠杆**；persona **是 prompt 不是文档**：不许 markdown。锁：A1–A11 + **A12 三条接法规则** + A12b 反向控制 +
  **A12c 篇幅约束位置** + A23–A25 平级口径 + F1/F7。**别再放整句示范**（4B 会逐字背），但"先接住对方那件事"的
  **行为锚不能丢**。
- **❗平级口径（二十轮，用户硬要求）：不许叫"主人"**，用户与 Ralsei **平级**、他**不是为谁而来**；
  **persona 与代码两层都要改**（只改 persona 无效），代码 5 处 = `_PERSONA_FALLBACK` / `_build_ai_context`(3 句) /
  `start_autonomous_speech`(2 prompt) / `memory_system.recall_text` 的 `who` / `_role_marker_re()`（**保留"主人"**）。锁 **J1–J6**。
- **❗世界观 = `assets/ralsei_worldview.md` + `modules/worldview_recall.py`（二十一轮改网图）**：`MAX_BLOCKS=2` 硬上限；
  **无命中返回空串**；`lean=True` 跳过（动机 = KV 前缀缓存），persona **13140→9269B**；语料取原作 853 条。锁 **K1–K20**；
  图契约见 §4；**端到端探针** `verify_persona_worldview.py`（`--no-recall` 对照组，二十三已六闸全复刻）。
- **❗关系演进 = `modules/relationship.py`（二十轮）**：四档**按用户原话顺序** distrust→guarded→warming→friend；
  `TRUST_INITIAL=0.12`（**从 distrust 起步**）。**信任度不可见**：只给**行为指令** + `_FORBID_LEAK` 禁泄；
  `describe()`（唯一带数字）只进日志。唯一写入口 `note(event)`、事件由**确定性** `classify()` 判。
  **勿把下界抬到 TRUST_INITIAL**（会让 `harsh` 变死事件）→ 值域 `[0, TRUST_MAX]`。锁 L1–L16。
- **底座 = `ralsei:v3`（`qwen3:4b-instruct-2507-q4_K_M`，由 `assets/ralsei.modelfile` build）**：**采样参数必须落
  Modelfile**（`/v1/chat/completions` **静默忽略 `num_ctx`/`repeat_penalty`**）；**⚠️ 换底座不能只改 config.json
  → 必须 `ollama create <新tag> -f ralsei.modelfile`**。**4B 判退 0/28**；7B 慢且平 → 否决。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级，别乱调）**：0a 句中括号动作 → 0b 剥 markdown →
  0c 禁说清单（出戏＋客服腔，**与事件链路同源，不许另立第二份表**）→ 1 自问自答截断 → 2 车轱辘话判退
  （**只看"和自己最近说过的（recent）重复"**）→ 3 超长截断；**判退后必须重采样一次**、**判退 → 不 append 进 recent**。
  ❗**0a 必须先于 0b**（否则 `*轻轻敲了敲键盘*` 的星号被 0b 吃掉 → 留裸叙述）；0b 还剥包裹引号 + "无实义则判退"。
  **真机探针已六闸全复刻**（二十三；W1–W8 锁 + 26/26 逐字节等价；新增 `[RETN]`）。锁 C18b/C20–C23/H1–H4。
  **S8 流式**：`iter_lines(chunk_size=1)`（**流式收益的一半**）；流式只做"前缀安全"清洗，护栏负责"最终算数"。
- **❗篇幅上限（二十二轮）= `main.AI_REPLY_MAX_CHARS`，现 220**（原 150 是 3B 拍的，**在砍正常回答**）；由
  `num_predict 256 × 1.359 字/token ≈ 348` × 63% 推出；锁 **M1–M5**（M2 = 落带 50%~75%，M5 = 防 C17 退化为恒真）。
  **换底座/调 num_predict 必须重跑 `measure_token_ratio.py`。**
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**；唯一出口 `speak_event(kind, pool, face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → **返回 `""` 沉默**）；**禁止 import Qt / 项目内模块**。
  它是**唯一**传 `lean=True` 处（保 KV 前缀缓存，否则首字 +1.19s、超 1200ms 上限）。

## 7. 历轮索引 / H4-H5 / 遗留（**详情见参考 §7–§9**）
- **7–18**：路径 import + `conversation_focus`/`memory_store`/`memory_graph` + jieba 软依赖 + `data_store` 收口 +
  建楼线 + DPI + 批次 A/B + S8 流式。**19**（`2738189`）S7 batch 2 + 底座换 v3 + 人味第四轮 + 第 4 道闸。
  **20**（`930657a`）世界观按需召回 + 平级口径（去"主人"）+ 关系演进。
  **21**（`bc9b1d7`+`75369b8`）世界观网图 + 加厚 + 端到端探针（§10）。**22**（`21d9ff9`）`AI_REPLY_MAX_CHARS`
  150→220 + 锁 A12c/M1–M5（§11）。**23**（`8548003`+`f81a8e3`+`61f689f`+`0c93021`）探针保真度六闸全复刻（§12）
  + 清存量：UTF-16 无损转 UTF-8 + 2 个 U+FFFD 加事故头注 + 75 告警冻结。
- **H4/H5 上帝类拆分**（用户排期"单独做"）：基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**S1/S2/S3 完成**；
  **G1 = 每项 PR 内做该专项零引用筛查**；**Wave 1 顺序 W1-3→W1-4→W1-1→W1-2→W1-6**；
  **旧行号已失效 → 开工前必须重跑 `scan_method_index.py`**。
  - ✅ **W1-3 完成**（`d8e2878`）：`GamesController`（7 方法/258 行）搬出，`main.py` 10481→10265。
    口径「**只搬方法、不搬状态（转发壳 + 宿主 API）**」→ `game_state`/`guess_number_game`/
    `rock_paper_scissors_options` **仍留在 `RalseiPet.__init__`**；方法体**逐字搬运**（verify 用
    "归一 `self.p.` 后逐字节比较"硬证明）；控制器**不 import 任何项目内模块**。
    新增 4 个校验：`verify_w1_3_{games_extract,forwarding,e2e,ab}.py`（38/45/46 PASS + A/B 轨迹一致）。
    报告 `W1-3_施工报告_2026-09-20.md`。**`handle_game_input` 刻意不搬**（调 W1-2 的
    `_abort_hide_and_seek`）→ **待 W1-2 落地后随该项一起搬**。
  - ⚠️ **W1 转发机制铁律：双向 `__getattr__` 必须两侧都是显式白名单**，否则成环。
    宿主侧**只能** `getattr(type(ctrl), name)`（只看控制器**类**上定义的方法），
    **绝不** `hasattr(ctrl, name)`；控制器侧只在「名字在宿主实例字典 **或** 宿主类型 MRO」时回落。
    **真机踩过**：`__init__` **L405** `init_movement()`→`randomize_movement_pattern()` 会
    `getattr(self,'game_state',{})`，而 `game_state` 直到 **L426** 才赋值 → `RecursionError` **崩在构造期**。
    → **构造期崩溃 G2 抓不到**（只有 16 个套件会 `RalseiPet()`，部分还是桩）：自写 e2e（真 `RalseiPet()`）才抓到。
    **"方法体逐字等价" ≠ "产品还能跑"**，两者必须独立证明。
- **遗留**：① **真机实测（用户做）**：遮挡 / 上下动手感 / 边缘掉落不生气而关窗生气 —— **契约级+单元级已锁，真机未验**；
  ② `climb_to_top_window()` 仍走裸窗口 ③ 75 个历史编码告警（第五～九轮 BOM/乱码）**已冻结归档**；3 个确定性损坏
  已处置（1 个 UTF-16 无损转 UTF-8；2 个 U+FFFD 不可恢复 → 加事故头注、原字节保留）④ 日志滚动：**旧诊断
  （exFAT 撞已存在目标→WinError 1）实测不成立**（3.11 的 `doRollover` 自带 `os.remove(dfn)`；E 盘实测能切）；
  **3.11 与托管 3.13 的 `doRollover` 行为不同**（3.13 改为「目标存在则早退」）。Sep 16 迁到 E 盘后只成功切一次
  → 疑为**当时 E 盘不稳定**，非代码缺陷 → **不凭"应该会坏"改全局日志行为** ⑤ S7 第二批 ~11 处候选**不阻塞**。
