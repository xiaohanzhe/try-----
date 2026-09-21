# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **详细全文（§4 契约 / §5 验证教训 / §6 人味线 / §7 历轮 / §8.1–§8.6 H4-H5 / §10–§13）
> 在 `参考-契约与历轮（详版）.md`**（**不自动注入，改动前 Read**）。
> 本文件只留**每轮必须遵守**的铁律 + 速查契约 + 当前状态。

## 0. 铁律
- 每轮改动完成即 **commit + push**（"以免后期找不到"）；称呼"用户"；技术细节我拍板；不可逆动作先说影响面。
- 报告放项目根；证据进 `code-quality-audit/<轮次>/_evidence/`（`_recon/` gitignore）。
  下载/生成物默认落 `E:\Download`（临时件 `_tmp\` 用后即删）；仓库内产物留项目目录。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（**24 套件 / 1164 PASS / 全 IDENTICAL**）。
  G2 跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。

## 1. 环境（**全文见参考 §1**）
1. ⚠️ **本沙箱 Bash 工具经常整个坏掉**（`dirname`/`ls`/`mkdir`/`head`/`cat` 全 exit 127）→ **一律 PowerShell + Python**；
   `Glob`/`Grep`/`Read` 照常可用。**带反斜杠路径经 Bash 传 Python 会吃分隔符** → 用**正斜杠**。
   PS **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在静默 exit 1）。
2. **起进程**只能 `&` + `run_in_background:true`；**杀进程** `Stop-Process`/`taskkill` 静默失效 →
   Python+psutil 按 cmdline 匹配（分步跑）。**删文件**用 `[System.IO.File]::Delete()`。
3. Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它；
   托管 venv(3.13) 缺 `bs4` → `round5_smoke` 假 FAIL。
4. **代理端口现查为准**（读注入 `HTTP_PROXY`）。❗**单端口一次成败不能当结论**：每端口 2~3 次 + 跨端口重试（含直连）；
   候选逐个试、成功即停。**换端口前先直接试一次。**
5. **E 盘外接盘会掉线**（判在线看 `Get-Disk`）→ 本地中转站是可用性必需。❗**E 盘 exFAT → 不能当探针沙箱**
   （`os.makedirs` → `OSError [WinError 1]`）→ 沙箱放本地 NTFS `%TEMP%\`。
6. 清理守卫按目标路径**累计删除计数**（阈值 50）：症状 = 进程在 import 期就被杀。已在应用侧根治；
   `dangerouslyDisableSandbox` 无效。**通则：见"计数恒定"先干掉触发源。**
7. **证据/报告一律让 Python 自己写 UTF-8**：绝不用 `& py x.py *> o.txt` / `| Out-File -Encoding utf8` 捕获原生 stdout
   （按 GBK 有损解码 → 中文真损坏，踩 3 次）。**`Write` 覆盖带 BOM 文件会保留 BOM** → 去 BOM 必须 Python 重写。
   校验器 `tools/check_evidence_encoding.py`。❗**别让脚本和 shell 重定向写同一文件**。
8. **注入的 `current_time` 会滞后于系统真实时间** → 落盘带日期的产物先 `Get-Date` 校准。
9. 别用 PowerShell 管道读中文元数据（`ollama show` 全乱码）→ 走 REST API + 显式 UTF-8。
10. **`github.com` 主站可能整段不可达而 `api.github.com` 仍 200**：此时 `git push` 必失败 →
    **提交照做 → 如实报告 → 稍后重试**。**别因 push 失败就怀疑凭据或改 git 配置。**
11. **"能力自评失准"比"能力不足"更危险**（以为 `Out-File -Encoding utf8` 能保真 → 真损坏还自认没问题）。12. ⭐ **仓库两套换行口径**（本机 `core.autocrlf=true` + **无 `.gitattributes`**，**全文 §8.6.5**）：
    **双口径**（blob=LF / worktree=CRLF）**14 个**（`dialogue_ui`/`ai_driver`/`pet_ai`/`dialogue_system`/`sound_manager`/
    `entertainment_system`/`pet_interaction`/`energy_hunger`/`config_manager`/`customization_system`/`api_client`/`diag30`/
    `diag_screen`/`diag_state`）；**单口径 58 个**（含 `main.py`、所有 `*_controller.py`）。
    ⇒ ① **`git status` 对这 14 个看不见差异** → **编辑必须保持原 EOL**；
    ② **逐字节参照系只能用 `git cat-file blob`**，`git archive` 会 LF→CRLF、**不能用**；
    ③ `git ls-tree` 会给特殊字符路径**加引号** → 用 `-r -z` + `surrogateescape`；
    ④ `git ls-tree HEAD:<subdir>` **剥前缀** → **必须从仓库根列 + 自检布局**。

## 2. git push（**完整配方 + 铁律 0 见 skill `win-git-utf8-push`**）
- 症状：退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`**。
- **❗核验命令自己也会说谎**：`ls-remote` 必须**独立构造** + 重试 3~5 次 + `git rev-parse origin/main` 交叉验证。
  **先怀疑核验，再怀疑被测物。** `git credential fill` **必带 `host`/`path`**，否则 `missing host field`。

## 3. 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有）；main→origin/main。真机起：
  `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。

## 4. 勿回退契约（**全文见参考 §4.1–§4.12 / §10，改动前必读**）
- **13 组契约**（多屏/甩飞/动画/联想/抽词/网图/建楼/存储/初始化环/jieba/DPI/G2 封闭性/误报清单）**全文**在
  **§4.1–§4.12 + §10**（含铁律、判据、禁用写法、**用户原话口径**），**开工前必读**。四个最容易踩：  ① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
  ② **建楼 `floor_visible_contains` 是唯一判据、禁用 `Qt.WindowStaysOnTopHint`（改 `_apply_pet_z_order()`）**，
     ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户原话口径，不许再改**；
  ③ **`A in rev[B]` 检反向是恒真判据**（正确 `b.key in adj[t]`）；**鉴别力体检必改文件**；
  ④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\` 读优先，staging=`%LOCALAPPDATA%\RalseiPet\`，
     迁移**只复制不搬走**）；被反向依赖的底层模块一律 `modules/lazy_log.LazyLogger`；裸进程脚本**先建 `QApplication` 再读坐标**。
- **误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已由 `pyqtSignal` 排主线程；`reset_special_states` 零调用。

## 5. 验证脚本教训（**全文见参考 §5/§5.1–§5.4/§8.4/§8.6，改断言前必读**）- **源级断言别用 `"字面量" in 源码`** → `code_only_src()`；含字面量走 `code_no_comment()`（**7 次踩**）；
  **docstring 是字符串不是代码**。**能上 AST 就上 AST**（W1-7 实测：裸文本匹配把**注释**当代码 → 假红）。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制成对**；**断行为不断赋值**；**恒真判据比不写还危险**；
  ❗**报红先自问"夹具真把破坏写进去了吗"**（连报 3 次假红全是夹具 bug）。**阈值型断言锚"实测物理上限"**；
  **换底座/改 num_predict 必须重跑测量脚本**。
- **探针不保真 = 报假问题** →「**能从源码拿的别 import；能 import 的别重写；不得不重写必须锁等价**」；
  **`runpy.run_path` 不给 `sys.path` 加脚本目录** → **"单跑绿、进 G2 红"**（**先怀疑加载器**）。- ❗**"定义"与"引用"分开数**；❗**反例 needle 先断言"真的命中"**；❗**改写要断言命中次数**（0 次＝假装成功）；
  ❗**`ast.walk` 找导入会钻进方法体 → 误判局部 import**（只遍历 `Module.body`）。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）** —— 镜像：**"没改也没人调用"要么接线、要么删**。
- ❗❗**detail/断言里别写会随代码增长的数字**（**§5.3**）：`len`／**`index`**／差值**全会漂**；唯一不漂是**纯布尔**。
- ❗❗**探针源码清洗器别手搓，用 `ast.unparse`**（**§5.4**，含可抄实现）。- **A/B 三大纪律 + 失效谱四形态**（**全文 §8.4 + §8.6.3**）：
  ① **两侧都真的跑到了**（结果一致 ＋ **两侧均无异常**）；② **搬运类 A、B 是两个文件**，提取函数**别预设宿主类名**，
  stub **一次装齐整组方法**；③ **桩必须实现真契约**（缺 `Screen.center()` 会**两侧同抛**）；④ **桩打在「方法体里 `self`
  的那张类」上**，不是宿主类 —— 塞进宿主**实例字典**会被 `__getattr__` 第 1 条白名单**绕过**（W1-6 实测真去调了 Excel）。
  **失效谱**：(1) 都没跑到；(2) 都抛同一异常；(3) **跑了但落点被探针形态抹平**（最险）；
  ⭐ **(4) 参照系不是父版本**（W1-3 的 A/B 实测：快照 = 父版本 + 当轮转发壳，+49/零删除、7 方法仍在宿主
  ⇒ 比的是"有壳无搬 vs 有壳已搬"，**鉴别力为零且非常像真的**）。
  - **反控自己也会假**：撤兜底要撤**对**名字（`_log` ≠ `_log_`）；**"反控通过"比"探针假绿"更危险**；**防御性 `except` 把 P0 变静默**。
  - ⭐⭐ **断言分层**：**A/B 的尺子必须两版都该全绿** ⇒ **描述"搬运本身"的归属断言不能进共享 e2e**（否则 A 必红、
    A/B 报的是"断言放错层"不是产品缺陷）。**归属进专测，行为进 e2e。**
  - **A/B 只证"两版等价"，不证"落点正确"**；凡涉及「**`self` 指谁**」的改动**必须有非 A/B 的独立维度**（e2e 真实例）。
- **A/B 先断言 A ≠ B**（"旧值"若**已先提交** → A == B，退化成自己跟自己比**且非常像真的**）：取**父版本** +
  **md5 相同即 `SystemExit`**。**对照组重复跑、先量尺子公差**（±2 条＝噪声）；**计数会被反向激励** → **永远先读原文再看计数**。

## 6. 人味改造线（2026-09-18~20）（**全文见参考 §6/§11/§12，动手前必读**）
回归锁 `persona_chat`(153)/`s8_stream`(69)/`s7_event_speech`(135)，**均进 G2，不联网、不调 Ollama。**
- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**不要**只写 Modelfile —— Ollama 用
  messages 的 system **整体替换** Modelfile 的 SYSTEM → 写进模型的人设一次都不生效 → **本机唯一可行"训练"杠杆**。
  persona **是 prompt 不是文档**（不许 markdown）；**别放整句示范**（4B 会逐字背），但"先接住对方那件事"的**行为锚不能丢**。锁 **A1–A12c/F1/F7**。
- **❗平级口径（用户硬要求）：不许叫"主人"**，用户与 Ralsei **平级**、他**不是为谁而来**，**persona + 代码两层都要改**（锁 J1–J6）。
- **世界观** = `assets/ralsei_worldview.md` + `modules/worldview_recall.py`（`MAX_BLOCKS=2`、**无命中返回空串**），锁 K1–K20。
- **关系演进** = `modules/relationship.py`（四档 distrust→guarded→warming→friend、`TRUST_INITIAL=0.12` 起于 distrust；
  **信任度不可见**、唯一写入口 `note(event)`；**勿把下界抬到 TRUST_INITIAL** → `harsh` 变死事件），锁 L1–L16。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**、唯一出口 `speak_event(kind,pool,face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → 返回 `""` 沉默）；**禁 import Qt / 项目内模块**。
- **底座 = `ralsei:v3`（`qwen3:4b-instruct-2507-q4_K_M`）**：**采样参数必须落 Modelfile**（`/v1/chat/completions`
  **静默忽略 `num_ctx`/`repeat_penalty`**）；**换底座必须 `ollama create <新tag> -f ralsei.modelfile`**。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级）**：0a 句中括号动作 → 0b 剥 markdown → 0c 禁说清单
  （**与事件链路同源，不许另立第二份表**）→ 1 自问自答截断 → 2 车轱辘话判退（**只看 recent 重复**）→ 3 超长截断；
  **判退后必须重采样一次**、**判退不 append 进 recent**。❗**0a 必须先于 0b**。锁 C18b/C20–C23/H1–H4。
  **S8 流式**：`iter_lines(chunk_size=1)`；流式只做"前缀安全"清洗。
- **❗篇幅上限 = `main.AI_REPLY_MAX_CHARS`，现 220**；**换底座/调 num_predict 必须重跑 `measure_token_ratio.py`**。锁 M1–M5。

## 7. H4/H5 上帝类拆分（**全文见参考 §8.1–§8.6**）
- 基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**S1/S2/S3 完成**；**G1 = 每项 PR 内做该专项零引用筛查**；
  **Wave 1 七项全部 ✅ 收官**（顺序 W1-3→W1-4→W1-1→W1-2→W1-6，+W1-7 补搬）；**Wave 3 不在范围**。
  `W1-3 GamesController d8e2878`｜`W1-4 VideoController 2d288c9/cc03ca4`｜`W1-1 SpellFlowController 26bb8c8/9770e39`｜
  `W1-2 HideAndSeekController e245f13`｜`W1-5 office 死代码清理`｜`W1-6 FileSheetController（4 业务/469 行，9375→9019、
  方法 175→170）`｜⭐`W1-7 handle_game_input→games（业务方法全部归位）bf8feaa`。
- ❗**`scan_method_index.py` 只是线索，不是范围定义**（名字前缀启发式）——**四类偏差都出现过**：
  漏标（W1-1 `_tick_*`/`_cast_*`、W1-4 `_*video*`、**W1-6 `_open_desktop_item_by_name`**）／误纳（W1-2 `_hide_ralsei`）／
  **W1-6 跨区散布**（7 方法横跨 L4222–4584 与 L8511–8591 ⇒「物理连续块」假设**不成立**）⇒
  **照索引施工会留下"被搬走的方法所调用的方法" → 运行期 `AttributeError` 被 `except` 吞掉 = 静默功能失效**。
  **必须与排期方案交叉核对（方案为准）+ 逐方法人工确认**；**⚠️ 方案本身也会错**（行号全漂、列已删方法、把**分层**当重复）→ **两边都验**。
- ⚠️ **W1 转发铁律：双向 `__getattr__` 两侧都须显式白名单**，否则成环（真机踩过）：宿主侧**只能** `getattr(type(ctrl),name)`，
  **绝不** `hasattr(ctrl,name)`；控制器侧只在「名字在宿主实例字典 **或** 宿主类型 MRO」时回落。
  **`RecursionError` 崩在构造期 → G2 抓不到** → 自写 e2e 才抓到。**新增控制器后，前序控制器的第 3 条白名单（兄弟控制器）必须同步扩**；
  **`_CONTROLLER_ATTRS` 在 `main.py` L506**，**第 3 条正是把 `self._abort_hide_and_seek` → `HideAndSeekController` 送过去的链（W1-7 实测必需）**。- ❗❗**W1 搬运铁律 8 条 + A/B 结构性盲区**（**逐条全文见 §8.2/§8.3/§8.4**）：① `self` 传出去救不了 → `QTimer(self.p)`；
  ② 控制器**必实现 `__setattr__`**（判据＝宿主**已拥有**、**必跳过 `'p'`**）；③ **新状态名在宿主 `init_systems()` 预声明**（**不是 `__init__`**）；
  ④ `_log` 用 `_log_()`；⑤ 锁的定位器跟代码搬家；⑥ `_log.` → `self._log_().`；⑦ **`os.`/`time.`/`random` 是"裸 Attribute 根"**
  （只扫"裸 Call 的 name"**完全看不见**）→ 逐个确认模块级 import；⑧ 桩打在「方法体里 `self` 的那张类」上 + 夹具噪声查表归一。
  ★★ **A/B 盲区**：`types.MethodType(fn, stub)` 下 `self` 即 **stub** ⇒ **铁律 7/1/2/3 在 A/B 中结构上不可见**。
  **A/B 只答"行为是否一致"**；铁律由 **e2e（真控制器实例）** 负责。**别用 A/B 的"没差别"去否定铁律。**

## 8. 遗留 / 交接（**详情见参考 §9 + §13.1 + 今日日志**）
1. **「预声明规则」升格为 H4/H5 正式施工口径**（搬运铁律 ③ 的核心，仍散落各报告）。
2. **铁律 6–9 条 + A/B 失效谱四形态写进总口径文档**。
3. **W1-6 的 B 块 3 个 `check_*_content` 留给 H4「文件反应」专项**。
4. **真机手感实测（需用户侧）**：遮挡 / 上下动手感 / 边缘掉落不生气而关窗生气 —— **契约级+单元级已锁，真机未验**。
5. **仓库换行口径（加 `.gitattributes`）是改变仓库约定的动作，应先议后动**。
6. `climb_to_top_window()` 仍走裸窗口；编码告警存量**已冻结归档**；日志滚动**旧诊断不成立 → 不凭"应该会坏"改全局日志行为**；
   S7 第二批 ~11 处**不阻塞**；`.bak`/`.backup_*` 未删（等用户点头）。
