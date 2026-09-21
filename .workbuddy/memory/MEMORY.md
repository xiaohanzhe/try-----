# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **详细全文（§4 契约 / §5 验证教训 / §6 人味线 / §8 H4-H5 / §10–§15）在
> `参考-契约与历轮（详版）.md`**（**不自动注入，改动前 Read**）。
> 本文件只留**每轮必须遵守**的铁律 + 速查契约 + 当前状态。

## 0. 铁律
- 每轮改动完成即 **commit + push**（"以免后期找不到"）；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根；证据进 `code-quality-audit/<轮次>/_evidence/`（`_recon/` gitignore）。
  下载/生成物默认落 `E:\Download`（临时件 `_tmp\` 用后即删）；仓库内产物留项目目录。
- ❗**仓库根 = `try - 副本`**（`ralsei_pet` 只是其子目录）→ 跑 G2 的 cwd 是仓库根。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（**24 套件 / 1169 PASS / 全 IDENTICAL**）。
  G2 跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。

## 1. 环境（**全文见参考 §1**）
1. ⚠️ **本沙箱 Bash 工具经常整个坏掉**（`dirname`/`ls`/`mkdir`/`head`/`cat` 全 exit 127）→ **一律 PowerShell + Python**；
   `Glob`/`Grep`/`Read` 照常可用。**带反斜杠路径经 Bash 传 Python 会吃分隔符** → 用**正斜杠**。
   PS **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在静默 exit）。
   ❗**`& py x.py *> o.txt` 产生 UTF-16 二进制**（Read 报 "Cannot display binary"）→ 脚本内自写 UTF-8。
2. **起进程**只能 `&` + `run_in_background:true`；**杀进程** `Stop-Process`/`taskkill` 静默失效 →
   Python+psutil 按 cmdline 匹配（分步跑）。**删文件**用 `[System.IO.File]::Delete()`。
3. Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它。
4. **代理端口现查为准**（读注入 `HTTP_PROXY`）。❗**单端口一次成败不能当结论**：每端口 2~3 次 + 跨端口重试（含直连）；
   候选逐个试、成功即停。**换端口前先直接试一次。** ⭐**git 路径别硬编码**：`PortableGit\versions\1.2.0\bin\git.exe`
   **不存在**（真身 `...\1.2.0\cmd\git.exe`）→ 一律 `shutil.which("git")`（= `D:\Program Files\Git\cmd\git.EXE`）。
5. **E 盘外接盘会掉线**（判在线看 `Get-Disk`）→ 本地中转站是可用性必需。❗**E 盘 exFAT → 不能当探针沙箱**
   （`os.makedirs` → `OSError [WinError 1]`）→ 沙箱放本地 NTFS `%TEMP%\`。
6. 清理守卫按目标路径**累计删除计数**（阈值 50）：症状 = 进程在 import 期就被杀。**通则：见"计数恒定"先干掉触发源。**
7. **证据/报告一律让 Python 自己写 UTF-8**：绝不用 `& py x.py *> o.txt` / `| Out-File -Encoding utf8` 捕获原生 stdout
   （按 GBK 有损解码 → 中文真损坏，踩 3 次）。**`Write` 覆盖带 BOM 文件会保留 BOM** → 去 BOM 必须 Python 重写。
   校验器 `tools/check_evidence_encoding.py`。❗**别让脚本和 shell 重定向写同一文件**。
   ❗**"能力自评失准"比"能力不足"更危险**。
8. **注入的 `current_time` 会滞后于系统真实时间** → 落盘带日期的产物先 `Get-Date` 校准。
9. 别用 PowerShell 管道读中文元数据（`ollama show` 全乱码）→ 走 REST API + 显式 UTF-8。
10. **`github.com` 主站可能整段不可达而 `api.github.com` 仍 200**：此时 `git push` 必失败 →
    **提交照做 → 如实报告 → 稍后重试**。**别因 push 失败就怀疑凭据或改 git 配置。**
11. ⭐ **仓库两套换行口径**（`core.autocrlf=true` + **无 `.gitattributes`**，**全文 §8.6.5**）：
    双口径（blob=LF/worktree=CRLF）**14 个** / 单口径 **58 个**（含 `main.py`、所有 `*_controller.py`）⇒
    ① **`git status` 对这 14 个看不见差异** → **编辑必须保持原 EOL**；② **逐字节参照系只能用 `git cat-file blob`**
    （`git archive` 会 LF→CRLF、**不能用**）；③ `git ls-tree` 给特殊字符路径**加引号** → `-r -z` + `surrogateescape`；
    ④ `git ls-tree HEAD:<subdir>` **剥前缀** → **必须从仓库根列 + 自检布局**。

## 2. git push（**完整配方 + 铁律 0/0.1/0.2/0.3 见 skill `win-git-utf8-push`**）
- 症状：退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`**。
- **❗核验命令自己也会说谎**：`ls-remote` 必须**独立构造** + 重试 3~5 次 + `git rev-parse HEAD` 交叉验证。
  **先怀疑核验，再怀疑被测物。**
- ❗**`subprocess.run(input=...)` 必须喂 bytes**（str → `TypeError`，异常被吞 → push 整段静默跳过，
  看起来像网络问题，**其实 commit 早成功**）→ `input=b"url=...\n\n"`；取凭据必须包 try + 打印醒目失败标记。

## 3. 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有）；main→origin/main。真机起：
  `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。

## 4. 勿回退契约（**全文见参考 §4.1–§4.12 / §10，改动前必读**）
**13 组契约**（多屏/甩飞/动画/联想/抽词/网图/建楼/存储/初始化环/jieba/DPI/G2 封闭性/误报清单）**全文**在
**§4.1–§4.12 + §10**（含铁律、判据、禁用写法、**用户原话口径**），**开工前必读**。四个最容易踩：
  ① **`availableGeometry()` 只返主屏 → 必用 `_virtual_screen_rect()`**；
  ② **建楼 `floor_visible_contains` 是唯一判据、禁用 `Qt.WindowStaysOnTopHint`（改 `_apply_pet_z_order()`）**，
     ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户原话口径，不许再改**；
  ③ **`A in rev[B]` 检反向是恒真判据**（正确 `b.key in adj[t]`）；**鉴别力体检必改文件**；
  ④ `data_store` 是**唯一入口**（vault=`E:\RalseiMemory\` 读优先，staging=`%LOCALAPPDATA%\RalseiPet\`，
     迁移**只复制不搬走**）；被反向依赖的底层模块一律 `modules/lazy_log.LazyLogger`；裸进程脚本**先建 `QApplication` 再读坐标**。
**误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已由 `pyqtSignal` 排主线程；`reset_special_states` 零调用。

## 5. 验证脚本教训（**全文见参考 §5/§5.1–§5.4/§8.4/§8.6，改断言前必读**）
- **源级断言别用 `"字面量" in 源码`** → `code_only_src()`；含字面量走 `code_no_comment()`（**7 次踩**）；
  **能上 AST 就上 AST**。**回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制成对**；**断行为不断赋值**；
  **恒真判据比不写还危险**；❗**报红先自问"夹具真把破坏写进去了吗"**。
- **探针不保真 = 报假问题** →「**能从源码拿的别 import；能 import 的别重写；不得不重写必须锁等价**」；
  ❗❗**"分类器写得太窄"和"闸有洞"长得一模一样** → **必须拿产品函数逐条复核，不能只看探针计数**
  （第27轮：探针报"括号残留 4 处"，复核后 **3/4 是探针误报**）。
- ❗**detail/断言里别写会随代码增长的数字**（`len`/`index`/差值全漂）；唯一不漂是**纯布尔**。
  ❗**探针源码清洗器别手搓，用 `ast.unparse`**。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）** —— 镜像：**"没改也没人调用"要么接线、要么删**。
- **A/B 纪律**：① 两侧都真跑到 ② **先断言 A ≠ B**（"旧值"若已提交 → A==B；取**父版本** + md5 相同即 `SystemExit`）
  ③ 桩打在「方法体里 `self` 的那张类」上 ④ **失效谱第 4 形态「参照系不是父版本」最险**（+49/零删除、方法仍在宿主
  ⇒ 鉴别力为零且非常像真的）⑤ **断言分层** = 归属断言进专测、行为断言进 e2e ⑥ **A/B 只证"两版等价"**。
  **对照组重复跑、先量尺子公差**（±2 条＝噪声）；**计数会被反向激励** → **永远先读原文再看计数**。

## 6. 人味改造线（2026-09-18~22）（**全文见参考 §6/§11/§12/§14.3/§15，动手前必读**）
回归锁 `persona_chat`(156)/`s8_stream`(69)/`s7_event_speech`(137)，**均进 G2，不联网、不调 Ollama。**
- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**不要**只写 Modelfile —— Ollama 用
  messages 的 system **整体替换** Modelfile 的 SYSTEM → 写进模型的人设一次都不生效 → **本机唯一可行"训练"杠杆**。
  persona **是 prompt 不是文档**（不许 markdown）。
- **❗平级口径（用户硬要求）：不许叫"主人"**，用户与 Ralsei **平级**、他**不是为谁而来**，**persona + 代码两层都要改**（J1–J6）。
- **世界观** = `assets/ralsei_worldview.md` + `modules/worldview_recall.py`（`MAX_BLOCKS=2`、**无命中返回空串**），锁 K1–K20。
- **关系演进** = `modules/relationship.py`（四档 distrust→guarded→warming→friend、`TRUST_INITIAL=0.12` 起于 distrust；
  **信任度不可见**、唯一写入口 `note(event)`；**勿把下界抬到 TRUST_INITIAL** → `harsh` 变死事件），锁 L1–L16。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**、唯一出口 `speak_event(kind,pool,face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → 返回 `""` 沉默）；**禁 import Qt / 项目内模块**。
- **底座 = `ralsei:v3`（`qwen3:4b-instruct-2507-q4_K_M`）**：**采样参数必须落 Modelfile**
  （`/v1/chat/completions` **静默忽略 `num_ctx`/`repeat_penalty`**）；**换底座必须 `ollama create <新tag> -f ralsei.modelfile`**。
- ★★ **失真头号来源 = persona 里"可逐字搬走的固定例句"，不是模型不行**
  （真机 24 条：开头复读 **62%**，**只有 4 个起手式**覆盖全部命中）。**改后降到 33%**。
  **铁律：persona 示例区不许出现"按场合分组 + 冒号 + 固定例句"** —— 这个**格式本身**就在教 4B"这场合该说这句"。
  删掉后 A/B 实测 **61% → 28%**；**只要那串字还在 persona 里，4B 就会搬** ⇒ 改成"情形描述 + 每次自己现造"才有效。锁 **A12d**。
- ★★ **失真③ 反"伪造共同经历"**：用户**没去过黑暗世界**，模型会把"我自己的过去"写成"我们那时候一起…"
  = **替他伪造记忆**。persona 已明令"只能说成我自己的过去"。锁 **A12e**。
- **persona 体积上限**：**K3 锁 < 10KB**（现 9752 B，已接近）→ **下次加内容前必须先瘦身**。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级）**：0a 句中括号动作 → 0b 剥 markdown → 0c 禁说清单
  （**与事件链路同源，不许另立第二份表**）→ 1 自问自答截断 → 2 车轱辘话判退（**只看 recent 重复**）→ 3 超长截断；
  **判退后必须重采样一次**、**判退不 append 进 recent**。❗**0a 必须先于 0b**。锁 C18b/C20–C23/H1–H4。
  **S8 流式**：`iter_lines(chunk_size=1)`；流式只做"前缀安全"清洗。
- ★ **括号旁白共三形态**：甲 动作词开头（`（歪头）`）→ `_ACTION_PAREN_RE`；乙 句首括号 → `looks_like_narration` 整句作废；
  丙 **描述性旁白**（`（心里有点慌）`）→ **`_NARRATION_INNER`**（第27轮加；改前实测 5 形态**全漏**）。
  ★★ **判据是「抓形态特征」不是「首词白名单」** —— 窄白名单会**把合法心里话一起误杀**（第27轮真踩）。
  **分界 = 这段是不是角色的「话语」**：第一人称的话 → 留；从外部描述自己 → 删。**误杀比漏过更糟。**
  锁 **A22e（正控制）+ A22f（反控制，与 A22c 成对）**。
- **❗篇幅上限 = `main.AI_REPLY_MAX_CHARS`，现 220**；**换底座/调 num_predict 必须重跑 `measure_token_ratio.py`**。锁 M1–M5。
- ⚠️ **第 26 轮发现（已处置）**：`_clean_ai_reply` 在 `start_autonomous_speech._on_reply`(`main.py:4620`)
  **未传 `recent`** → 自主开口跳过车轱辘判退（第 26 轮 P3 已补传 + B13b 锁）。

## 7. H4/H5 上帝类拆分（**全文见参考 §8.1–§8.6**）
- 基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**S1/S2/S3 完成**；**G1 = 每项 PR 内做该专项零引用筛查**；
  **Wave 1 七项全部 ✅ 收官 + 第 26 轮复审判"合格"**；**Wave 3 不在范围**。
  ★**预声明区 = 宿主 `init_systems()`**（`main.py` **L660**，状态块 L770–806；**不是 `__init__`**）。
- ❗**`scan_method_index.py` 只是线索，不是范围定义**（名字前缀启发式）——**四类偏差都出现过**：
  漏标／误纳／**W1-6 跨区散布**／**方案自身错** ⇒ **必须与排期方案交叉核对 + 逐方法人工确认**。
- ⚠️ **W1 转发铁律：双向 `__getattr__` 两侧都须显式白名单**，否则成环（真机踩过）：宿主侧**只能**
  `getattr(type(ctrl),name)`，**绝不** `hasattr(ctrl,name)`。**`RecursionError` 崩在构造期 → G2 抓不到**。
  **`_CONTROLLER_ATTRS` 在 `main.py` L512**。
- ❗❗**W1 搬运铁律 8 条 + A/B 结构性盲区**（**逐条全文见总口径 §2/§3**）：① `self` 传出去救不了 → `QTimer(self.p)`；
  ② 控制器**必实现 `__setattr__`**（判据＝宿主**已拥有**、**必跳过 `'p'`**）；③ 新状态名在 `init_systems()` 预声明；
  ④ `_log` 用 `_log_()`；⑤ 锁的定位器跟代码搬家；⑥ `_log.` → `self._log_().`；⑦ **`os.`/`time.`/`random` 是"裸 Attribute 根"**
  （只扫"裸 Call 的 name"**完全看不见**）；⑧ 桩打在「方法体里 `self` 的那张类」上。
  ★★ **A/B 盲区**：`types.MethodType(fn, stub)` 下 `self` 即 **stub** ⇒ **铁律 1/2/3 在 A/B 中结构上不可见**。

## 8. 第 26 轮复审 + 处置（**全文见参考 §14 + `第二十六轮处置报告_2026-09-21.md`**）
- ✅ **处置已施工**（commit `5c0a3e7` + `d5ab8d4`）：**P1 死代码实删 8 个**（报告只点名 4 —— ★**正则口径漏判 4**，
  改 **AST 口径**后现形，全是 **W1-3/W1-4 搬迁残留**）⇒ **铁律：零引用筛查一律走 AST，不走正则**；
  **P2 补异常日志 6 处**；**P3 两处**（`paintEvent` try/finally + 自主开口补传 `recent`）。
  ★ **锁 B12/B13 升级为 AST 结构断言 + B13b** ⇒ **铁律：回归锁断行为/结构，别断赋值/写法。**
- **假绿灾区（已补日志）**：`main.py:6849-6916` 连续 7 个 `except Exception: pass` 建 AI 上下文。
- **❗P0 仍待用户裁定**：`dialogue_ui.py:1259-1270` `_rule_reply()` 罐头皮 + 回落点 `:1325`/`:1346`
  ⇒ 「AI 关必沉默」是否也管"用户主动打字" = 产品决策。
- **待办**：真机手感实测（用户侧）｜`.gitattributes` 换行口径（**先议后动**）｜`_tmp`/`.bak` 存量（**等用户点头，不得批量删**）｜
  H4「文件反应」专项（3 个 `check_*_content`，活跃不可删）。

## 9. 第 27 轮 AI 失真治理（**全文见参考 §15 + `第二十七轮AI失真治理报告_2026-09-22.md`**）
- ✅ **已施工 + 真机验收 + 提交推送**（`685f98b` 产品 + `51919da`/`3d732fb` 记忆，`ls-remote` 核验 **SYNCED=True**）。
- **三源全治**：① 开头复读 **62% → 33%**；② 括号旁白 5 形态全漏 → **全部被拦**（新增第 3 道闸）；③ 编造共同经历 → **0 处**。
- **未达标但判为可接受**：33% 里剩 3 种全是**短促语气起音**（`诶！`/`我、我……`）= **Ralsei 人设特征**（原作结巴是标志）
  → 清零等于砍特征。**下一轮杠杆若还嫌模板感重 = 采样侧（temperature/repeat_penalty），但本轮无证据支持动它**。
  锁 A12d/A12e/A22e/A22f（+4，G2 1165 → **1169**）。
- **G2 终态**：`PASS=1169 FAIL=0 套件=24` / `IDENTICAL=24 DIFF=0 rc=0`。