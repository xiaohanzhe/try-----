# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **详细契约（§4）、验证教训（§5）、人味线（§6、§11、§12）、网图（§10）、历轮索引（§7–§9）、
> H4/H5 全文（§8.1–§8.4）已拆到同目录 `参考-契约与历轮（详版）.md`**（**不自动注入，用时 Read**）。
> 本文件只留**每轮都必须遵守**的铁律、速查契约与当前状态。

## 0. 铁律
- 每轮改动完成即 **commit + push**（"以免后期找不到"）；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根 `人味*.md` / `code-quality-audit/架构改造-H4H5/W1-*.md`；证据进 `code-quality-audit/<轮次>/_evidence/`
  （侦察 `_recon/`，gitignore）。下载/生成物默认落 `E:\Download`（临时件 `_tmp\` 用后即删）；仓库内产物留项目目录。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（**24 套件 / 1163 PASS / 全 IDENTICAL**）。
  G2 会跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。
## 1. 环境（**全文见参考 §1**；下列每条都真踩过）
1. ⚠️ **本沙箱 Bash 工具经常整个坏掉**（`dirname`/`ls`/`mkdir`/`cd`/`head`/`cat` 全 exit 127）→ **一律 PowerShell + Python**；
   `Glob`/`Grep`/`Read` 照常可用。**带反斜杠的路径经 Bash 传给 Python 会被吃掉分隔符** → 用**正斜杠**。
   PS **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在静默 exit 1）。
2. **起进程**只能 `&` + `run_in_background:true`；**杀进程** `Stop-Process`/`taskkill` 静默失效 →
   Python+psutil 按 cmdline 匹配（分步跑）。**删文件**用 `[System.IO.File]::Delete()`。
3. Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它；
   托管 venv(3.13) 缺 `bs4` → `round5_smoke` 假 FAIL。
4. **代理端口现查为准**（读注入 `HTTP_PROXY`，2026-09-20 为 **64676**）。❗**单端口一次成败不能当结论**：
   每端口至少 2~3 次 + 跨端口重试（含直连）；候选（注入值 → 7897 → 7890）逐个试，成功即停。
5. **E 盘是外接盘、会掉线**（判在线看 `Get-Disk`）→ 本地中转站是可用性必需。❗**E 盘是 exFAT**：
   **不能当探针沙箱**（`os.makedirs` → `OSError [WinError 1]`）→ 沙箱放本地 NTFS `%TEMP%\`。
6. 清理守卫按目标路径**累计删除计数**（阈值 50）：症状 = 进程在 import 期就被杀。已在应用侧根治；
   `dangerouslyDisableSandbox` 无效。**通则：见"计数恒定"先干掉触发源，别急着下确定性结论。**
7. **证据/报告一律让 Python 自己写 UTF-8**：绝不用 `& py x.py *> o.txt` / `| Out-File -Encoding utf8` 捕获原生 stdout
   （按 GBK 有损解码 → 中文真损坏，踩 3 次）。**`Write` 覆盖带 BOM 文件会保留 BOM** → 去 BOM 必须 Python 重写。
   校验器 `tools/check_evidence_encoding.py`。
8. **注入的 `current_time` 会滞后于系统真实时间** → 落盘带日期的产物先 `Get-Date` 校准。
9. 别用 PowerShell 管道读中文元数据（`ollama show` 全乱码）→ 走 REST API + 显式 UTF-8。
10. **`github.com` 主站可能整段不可达而 `api.github.com` 仍 200**：此时 `git push` 必失败 →
    **提交照做 → 如实报告 → 稍后重试**。**别因 push 失败就怀疑凭据或改 git 配置。**
11. **"能力自评失准"比"能力不足"更危险**（例：以为 `Out-File -Encoding utf8` 能保真 → 真损坏还自认没问题）。
## 2. git push（**完整配方 + 铁律 0 见 skill `win-git-utf8-push`**）
- 症状：退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`**。
- **❗核验命令自己也会说谎**：`ls-remote` 必须**独立构造** + 重试 3~5 次 + `git rev-parse origin/main` 交叉验证。
  **先怀疑核验，再怀疑被测物。**
- **端口**：注入的 `HTTP_PROXY` 实测可用（2026-09-20 为 **64676**）；候选（注入值 → 7897 → 7890）逐个试。

## 3. 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有）；main→origin/main。真机起：
  `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。

## 4. 勿回退契约（**逐条全文见参考 §4.1–§4.12 / §10，改动前必读**）
- **多屏 / 甩飞抛物线 / 动画 / 多跳联想 / 抽词 / 世界观网图 / 建楼 / 存储两层 / 初始化环 / jieba 软依赖 /
  DPI / G2 封闭性 / 误报清单**：13 组契约**全文**在参考 **§4.1–§4.12 + §10**（含铁律、判据、禁用写法、
  用户原话口径），**开工前必读**；速查本不复述，仅点四个最容易踩的：
  ① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
  ② **建楼里 `floor_visible_contains` 是唯一判据、禁用 `Qt.WindowStaysOnTopHint`（改 `_apply_pet_z_order()`）**，
     ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户当年原话口径，不许再改**；
  ③ **`A in rev[B]` 检反向是恒真判据**（正确 `b.key in adj[t]`），**鉴别力体检必改文件**；
  ④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\` 读优先，staging=`%LOCALAPPDATA%\RalseiPet\`，
     迁移**只复制不搬走**）；被反向依赖的底层模块一律 `modules/lazy_log.LazyLogger`；
     裸进程脚本**先建 `QApplication` 再读坐标**。
- **误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已由 `pyqtSignal` 排主线程；
  `reset_special_states` 零调用。
## 5. 验证脚本教训（**全文见参考 §5 + §5.1 + §5.2 + §8.4，改断言前必读**）
- **源级断言别用 `"字面量" in 源码`** → `code_only_src()`；含字面量的 needle 走 `code_no_comment()`（5 次踩）。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制成对**；**断行为不断赋值**；**恒真判据比不写还危险**；
  **体检须"改文件"**（改内存 → 假 P）；❗**报红先自问"夹具真把破坏写进去了吗"**（连报 3 次假红全是夹具 bug）。
- **阈值型断言必须锚在"实测物理上限"**，不能是裸常数；**换底座/改 num_predict 必须重跑测量脚本**。
- **探针不保真 = 报假问题** → 「**能从源码拿的别 import；能 import 的别重写；不得不重写必须锁等价**」；
  **`runpy.run_path` 不给 `sys.path` 加脚本目录** → **"单跑绿、进 G2 红"**（**先怀疑加载器**）。
- ❗**"定义"与"引用"分开数**；❗**反例 needle 先断言"真的命中"**；❗**改写要断言命中次数**（0 次＝假装成功）；
  ❗**`ast.walk` 找导入会钻进方法体 → 误判局部 import**（只遍历 `Module.body`）。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）** —— 镜像：**"没改也没人调用"要么接线、要么删**；
  **描述/断言里别写会随代码增长的数字**（`ralsei:v2`、`FROM qwen2.5:3b` 都假红）。
- **A/B 先断言 A ≠ B**（"旧值"若**已先提交** → A == B，退化成自己跟自己比**且非常像真的**）：取**父版本** +
  **md5 相同即 `SystemExit`**。**对照组要重复跑，先量尺子的公差**（±2 条＝噪声）；**计数会被反向激励** →
  **永远先读原文再看计数**。
- **反控自己也会假**：① 场景要选"**必然命中**那一行"的；② 撤兜底要撤**对**名字（`_log` ≠ `_log_`）；
  ③ 必须加断言证明**好版本真的执行到了那行**。**"反控通过"比"探针假绿"更危险**。**防御性 `except` 会把 P0 变成静默**。
- **❗❗A/B 三大纪律 + 失效谱三形态**（**全文见参考 §8.4**）：① **必须守「两侧都真的跑到了」**——每场景两组断言：
  结果一致 ＋ **两侧均无异常**（`「A 与 B 相同」在 A、B 都失败时同样成立`）；② **搬运类 A/B 的 A、B 是两个文件**
  （父版 vs 新模块）；提取函数**别预设宿主类名**；stub **一次装齐整组方法 + 单独绑辅助方法**；③ **桩必须实现真契约**
  （缺 `Screen.center()`/`QTimer.singleShot` 会**两侧同抛**，A/B 依旧"一致"）；**夹具噪声要归一**（自增序号在
  **目录名**里，`basename()` 抹不掉 → 用**查表**的稳定逻辑名）；④ **失效谱三形态**：都没跑到 / 都抛同一异常 /
  **跑了但落点被探针形态抹平**（第 3 种最险，**A/B 永远发现不了自己漏了什么**）。
  ⇒ **A/B 只能证明"两版行为等价"，不能证明"改动落点正确"**；凡涉及「**`self` 指谁**」的改动
  （搬运铁律 1/3/4/6 全是这类）**必须有非 A/B 的独立维度**（e2e 真实例）。
## 6. 人味改造线（2026-09-18~20）（**全文见参考 §6 + §11 + §12**）
回归锁 `persona_chat`(**153**) / `s8_stream`(**69**) / `s7_event_speech`(**135**)，**均进 G2，不联网、不调 Ollama。**
- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**不要**只写 Modelfile —— Ollama 用
  messages 的 system **整体替换** Modelfile 的 SYSTEM → 写在模型里的人设一次都不生效 → **本机唯一可行的"训练"杠杆**。
  persona **是 prompt 不是文档**：不许 markdown。**别再放整句示范**（4B 会逐字背），但"先接住对方那件事"的
  **行为锚不能丢**（由规则承担）。锁 **A1–A12c + F1/F7**。
- **补充速查**：**❗平级口径（用户硬要求）：不许叫"主人"**，用户与 Ralsei **平级**、他**不是为谁而来**，
  **persona 与代码两层都要改**（只改 persona 无效），锁 **J1–J6**；**世界观 = `assets/ralsei_worldview.md` +
  `modules/worldview_recall.py`**（`MAX_BLOCKS=2` 硬上限、**无命中返回空串**、`lean=True` 跳过），锁 **K1–K20**；
  **关系演进 = `modules/relationship.py`**（四档按用户原话顺序 distrust→guarded→warming→friend、
  `TRUST_INITIAL=0.12` 从 distrust 起步；**信任度不可见**、唯一写入口 `note(event)`；**勿把下界抬到 TRUST_INITIAL**
  → 会让 `harsh` 变死事件），锁 L1–L16。**S7 事件台词** `modules/event_speech.py`：档位表是**白名单**；
  唯一出口 `speak_event(kind, pool, face)`；**`pool=None` = 不给内置台词**（AI 失败/判退 → **返回 `""` 沉默**）；
  **禁止 import Qt / 项目内模块**。
- **底座 = `ralsei:v3`（`qwen3:4b-instruct-2507-q4_K_M`）**：**采样参数必须落 Modelfile**（`/v1/chat/completions`
  **静默忽略 `num_ctx`/`repeat_penalty`**）；**⚠️ 换底座必须 `ollama create <新tag> -f ralsei.modelfile`**。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级，别乱调）**：0a 句中括号动作 → 0b 剥 markdown →
  0c 禁说清单（**与事件链路同源，不许另立第二份表**）→ 1 自问自答截断 → 2 车轱辘话判退（**只看 recent 重复**）
  → 3 超长截断；**判退后必须重采样一次**、**判退 → 不 append 进 recent**。❗**0a 必须先于 0b**。
  锁 C18b/C20–C23/H1–H4。**S8 流式**：`iter_lines(chunk_size=1)`；流式只做"前缀安全"清洗。
- **❗篇幅上限 = `main.AI_REPLY_MAX_CHARS`，现 220**（原 150 是 3B 拍的，**在砍正常回答**）；
  **换底座/调 num_predict 必须重跑 `measure_token_ratio.py`**。锁 **M1–M5**。
## 7. 历轮索引 / H4-H5 / 遗留（**详情见参考 §7–§9**）
- **历轮 7–24**：详见参考 §7 + 今日日志。要点：**7–18** 路径 import / 联想三件套 / jieba / `data_store` 收口 /
  建楼线 / DPI / 批次 A/B / S8 流式；**19** S7 batch2 + 底座 v3 + 人味四轮；**20** 世界观按需召回 + 平级口径 + 关系演进；
  **21** 世界观网图（§10）；**22** 篇幅 150→220（§11）；**23** 探针保真度六闸复刻（§12）+ 清存量；
  **24** H4/H5 Wave1 四项连做（§8.1–§8.4）+ 第 7 条搬运铁律 + **A/B 失效谱三形态**。
- **H4/H5 上帝类拆分**（用户排期"单独做"）：基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；
  **S1/S2/S3 完成**；**G1 = 每项 PR 内做该专项零引用筛查**；
  **Wave 1 顺序 W1-3→W1-4→W1-1→W1-2→W1-6**（**W1-3/W1-4/W1-1/W1-2 ✅**）；
  **旧行号已失效 → 开工前必须重跑 `scan_method_index.py`**；**剩余仅 W1-6（文件表 7 方法 / ~399 行）**。
  - ❗**`scan_method_index.py` 既漏标也误纳 → 只是下界 + 线索，不是范围定义**（`group_of()` 是名字前缀启发式）：
    W1-1 漏标 `_tick_*`/`_cast_*`（报 2/63，实为 4/290）；W1-4 漏标 `_*video*`；**W1-2 反向误纳 `_hide_ralsei`
    （托盘隐藏，L558/17 行）** → 照抄索引会把托盘功能一起搬走。**必须与排期方案 `架构改造排期方案_H4-H5_2026-09-13.md`
    交叉核对（以方案为准）+ 人工确认"物理连续块"边界；两个方向都要防。**
  - ⚠️ **W1 转发铁律：双向 `__getattr__` 两侧都须显式白名单**，否则成环（真机踩过）：宿主侧**只能**
    `getattr(type(ctrl), name)`，**绝不** `hasattr(ctrl, name)`；控制器侧只在「名字在宿主实例字典 **或** 宿主类型 MRO」
    时回落。**`RecursionError` 崩在构造期 → G2 抓不到**（仅 16 套件会 `RalseiPet()`）→ 自写 e2e 才抓到。
    **新增控制器后，前序控制器的第 3 条白名单（兄弟控制器）必须同步扩**（W1-2 靠它调 W1-1 的 `_cast_spell_then`）。
  - ✅ 四项均**已推送**：**W1-3**（`d8e2878`）`GamesController` 7/258；**W1-4**（`2d288c9`/`cc03ca4`）`VideoController` 8/289；
    **W1-1**（`26bb8c8`/`9770e39`）`SpellFlowController` 4/290；**W1-2**（本轮）`HideAndSeekController` **12/342**，
    9713→**9375**、方法数 195→**183**、新模块 **527 行**；三维全绿 **UNIT 64/0 · E2E 82/0 · A/B 82/0**，
    G1 11 名字零死代码，G2 **1163 PASS/0 FAIL/24 套件**。**全文见参考 §8.1–§8.4。**
  - ❗❗**W1 搬运铁律 7 条（全属"逐字等价测不出来"）** —— 搬前必读参考 §8.2/§8.3/§8.4：
    ① `self` **当对象传出去**救不了 → `QTimer(self.p)` + 补 Qt 导入；② 控制器**必须实现 `__setattr__`**
    （判据＝宿主**已拥有**该名；**必跳过 `'p'`**）；③ **新状态名必须在宿主预声明**（⚠️ 本项目在 **`init_systems()`**，
    **不是 `__init__`**；验证扫描面 = **整个类体 − 搬走的方法**）；④ `_log` 用普通方法 `_log_()` 取宿主模块同一对象；
    ⑤ **锁的定位器跟着代码搬家**，**禁止**弱化成"找不到就跳过"；⑥ **`_log.` 必须改写成 `self._log_().`**，
    不允许裸 `_log_()`（`_log_` 是**实例方法**，裸调用抛 `NameError`；藏在 `except Exception:` 里从未被覆盖 →
    **「没被覆盖的分支 = 没被测过的代码」**，每搬一项加动态哨兵）；⑦ **`os.`/`time.`/`random` 是"裸 Attribute 根"**，
    不是 Name-func 调用 —— 只扫"裸 Call 的 name"会**完全看不见**它们（W1-2 漏了 11 处 `os.` 站点）→
    逐个确认有**模块级** import。
- **遗留**：① **真机实测（用户做）**：遮挡 / 上下动手感 / 边缘掉落不生气而关窗生气 —— **契约级+单元级已锁，真机未验**；
  ② `climb_to_top_window()` 仍走裸窗口 ③ 75 个历史编码告警**已冻结归档** ④ 日志滚动：**旧诊断实测不成立**
  （3.11 `doRollover` 自带 `os.remove(dfn)`；3.13 改为"目标存在则早退"）→ **不凭"应该会坏"改全局日志行为** ⑤ S7 第二批 ~11 处**不阻塞**。
