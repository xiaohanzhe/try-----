# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

> **详细契约（§4.1–4.12）、验证脚本教训（§5）、人味改造线全文（§6.1–§6.9）、历轮索引（§7–§9）已拆到同目录
> `参考-契约与历轮（详版）.md`**（约 48KB，**不自动注入，用时 Read**）。本文件只留**每轮都必须遵守**的铁律、速查契约与当前状态。

## 0. 铁律
- 每轮改动完成即 **commit + push**（"以免后期找不到"）；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根 `代码质量复审报告_*.md`（人味线用 `人味*.md`）；证据进 `code-quality-audit/<轮次>/_evidence/`；
  侦察 `_recon/`（gitignore）。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（**24 套件 / 1092 PASS / 全 IDENTICAL**）。
- 下载/生成物默认落 `E:\Download`（临时件 `_tmp\` 用后即删）；仓库内产物留项目目录；系统默认下载目录不动。
- G2 会跑 `compileall` → 可能改写被跟踪的 `src/__pycache__/*.pyc` → 收工前 `git checkout --`。

## 1. 环境（**逐条全文见参考 §1**）
1. **Bash 工具不可用** → 一律 PowerShell。**PowerShell stdout 常不回传** → 命令内
   `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在会静默 exit 1 → 先建目录）。
2. **起进程**只能 `&` + `run_in_background:true`（`cmd /c`、`Start-Process`、WMI 全被拦）；
   **杀进程** `Stop-Process`/`taskkill` 静默失效 → Python+psutil 按 cmdline 匹配（分步跑）。
3. **删文件**用 `[System.IO.File]::Delete()`（管道 `Remove-Item` 静默无效）。
4. Python 一律 **`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— G2 与所有套件必须用它；
   托管 venv(3.13) 缺 `bs4` → `round5_smoke` 假 FAIL。
5. **代理端口现查为准**（`netstat -ano | findstr LISTENING` 或读注入 `HTTP_PROXY`）。2026-09-18 实测 7897 可用。
   **换端口前先直接试一次。**
6. **E 盘是外接盘、会掉线**（判在线看 `Get-Disk`）→ 本地中转站是可用性必需。
7. **safe-delete 守卫按目标路径累计删除计数**（阈值 50）：症状 = **进程在 import 期就被杀**（批量跑套件表现为
   "多套件同时 exit=1 PASS=0 + 假 DIFF"）。已在应用侧根治。**通则：见"计数恒定"先干掉触发源，别急着下确定性结论。**
8. **证据/报告一律让 Python 自己写 UTF-8**：绝不用 `& py x.py *> o.txt` / `| Out-File -Encoding utf8` 捕获原生
   stdout（按 GBK **有损**解码 → 中文**真损坏**，踩 3 次）；搬运用 `Copy-Item`。**`Write` 覆盖带 BOM 文件会保留 BOM**
   → 去 BOM 必须 Python 重写。校验器 `code-quality-audit/tools/check_evidence_encoding.py`（`--out` 自写、`--strict`）。
   **"能力自评失准"比"能力不足"更危险。**
9. **注入的 `current_time` 会滞后于系统真实时间** → 凡落盘带日期的产物先 `Get-Date` 校准；错了 `git mv` 改名。
10. 别用 PowerShell 管道读中文元数据（`ollama show` 全乱码）→ 走 REST API + 显式 UTF-8。
11. **`github.com` 主站可能整段不可达而 `api.github.com` 仍 200**：此时 `git push` 必失败。
    处置：**提交照做 → 如实报告 → 稍后重试**。**别因 push 失败就怀疑凭据或改 git 配置。**

## 2. git push（**完整配方见 skill `win-git-utf8-push` + 参考 §2**）
- 症状：退出码 128 且全静默 = 非交互 GCM 取不到凭据 → 用 `git credential fill` 取密 + `-c credential.helper=`
  + `-c http.extraheader="Authorization: Basic <b64>"` + 代理；**端口现查**；重试 3–5 次。
- **核验外发用 `git ls-remote`（带同头）> 看退出码。令牌别写进仓库文件。**
- **提交信息用 Write 写 UTF-8 文件 + `git commit -F <文件>`**（`-m @'...'@` 遇带空格英文引号会被 PS 5.1 拆 argv
  → 提交没发生、push 退 0 **假成功**）；**别用 `Out-File -Encoding utf8`**（加 BOM；且 `Write` 覆盖带 BOM 文件会**保留 BOM**
  → 必须换新路径重写）。校验前 3 字节应 `231,172,172`，`239,187,191` 即 BOM。**提交后必核 `git log --oneline -1`。**

## 3. 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有，未认证 401/404）；main→origin/main。
  GitHub 连接器只覆盖公开库，看不到本仓库（404）。
- 真机起：`Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → **甩飞、抛物线只能离屏断言**。

## 4. 勿回退契约（**全文见参考 §4.1–§4.12**）
- **多屏**：禁用 `QApplication.desktop().availableGeometry()`（只返主屏 → "瞬移"）；用 `_virtual_screen_rect()`；钳 `dt≤0.1s`。
- **甩飞/抛物线**：判定只在 `mouseReleaseEvent`（`_drag_samples` 0.12s）；初速只由松手速度定（等比缩放 + **矢量和**限幅）；
  `_fall_vy0` 只第一帧记录。
- **动画**：`fps=6`；自主说话唯一入口 `start_autonomous_speech()`，**AI 关闭必须沉默、不得回落内置台词**。
  **特殊动画（#13）来源只三类**（ai_driver / 用户显式交互 / 物理状态机）；**环境自动触发不得自行播动画**，
  只能 `ai_driver.note_event()` 上报；播放期 `_special_anim_locked()` 禁移动。
- **多跳联想**：`HOP_TIER_FLOOR={1:weak,2:weak,3:mid}` + **中转资格** `_BRIDGE_MIN_RANK=mid`（弱边可到达、不可再出发）；
  **PPR 只加权不准入**；`graph.paths()` 只吃 `seed_map()` 归一化 dict。
- **抽词**唯一入口 `conversation_focus.extract_keywords`（三层择优、**不返回空**）；`EDGE_TOPOLOGY` **默认仍是 `clique`**；
  密度靠**输入端**压，**不靠砍边**。
- **存储两层**：vault=`E:\RalseiMemory\`（读永远优先），staging=`%LOCALAPPDATA%\RalseiPet\`；`data_store` 是**唯一入口**；
  迁移**只复制不搬走**、落选者留档 `.old`；**初始化环**用 `modules/lazy_log.LazyLogger`。
  **jieba 是软依赖**（`modules/text_segmenter.py`），失败一律静默回落内置。
- **建楼（参考 §4.9，本项目最贵的一条线，勿凭直觉"重做"）**：楼层 = 窗口的**可见区域**，`floor_visible_contains`
  是**唯一判据**；**禁用 `Qt.WindowStaysOnTopHint`** → `_apply_pet_z_order()`（**必须在 `show()` 之后**）；
  坠落只看**层高比较**，起因按 `is_floor_valid(old_floor)` 分流；生气时长由 `_fall_reason` **纯派生**；
  **甩飞路径必须显式 `self._fall_reason = None`**；跳/爬 `_jump_kind_for_span`；**不做"逐层小跳"**；
  ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户当年原话口径，不许再改**。
- **DPI**：写探针/裸进程脚本**必须先建 `QApplication` 再读任何坐标**。
- **G2 封闭性**：`HERMETIC_IDS` 注入临时 `RALSEI_MEMORY_DIR`；**`save_baseline` 是合并模式**。
- **误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 跨线程已由 `pyqtSignal` 排主线程；
  `reset_special_states` 零调用；原子写/回收站删除已正确防御。

## 5. 验证脚本教训（**全文见参考 §5 + §5.1，改断言前必读**）
- 源码级断言别用 `"字面量" in 源码` → `code_only_src()`；**含字符串字面量的 needle 必须走 `code_no_comment()`**（5 次踩）。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制必须成对**；断言**断行为不断赋值**、别写在死代码上。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）** —— 镜像：**"没改也没人调用"要么接线、要么删**。
- **描述/断言里别写会随代码增长的数字**（`ralsei:v2`、`FROM qwen2.5:3b` 都假红）。
- **A/B 先断言 A ≠ B**（取"旧值"若改动**已先提交** → A == B，探针退化成自己跟自己比**且非常像真的**）：
  取**父版本** + **md5 相同即 `SystemExit`** + `--old-rev`。
- **对照组要重复跑，先量尺子的公差**（±2 条就是噪声）；**计数会被反向激励**（特征率 100% 那版内容最差）
  → **永远先读原文再看计数**。
- **提示词里分组标签本身就是可能被输出的词**；**别为禁用项追加具体反例**。
- 离屏**无字体** → `QPainter.drawText` 静默不画；**PIL 可直接 `ImageFont.truetype('C:\Windows\Fonts\msyh.ttc')`**。
- **删 Ollama 模型看 blobs 目录**（标称 10.4GB 实际 6.6GB）；**删完必须真发一次 `/api/chat`**。

## 6. 人味改造线（2026-09-18 ~ 19）（**全文见参考 §6.1–§6.9**）
报告 `Ralsei对话人味诊断与训练方案_2026-09-18.md` + `人味第四轮报告_2026-09-19.md` +
`人味改造_世界观与禁语兜底_2026-09-19.md`；证据 `code-quality-audit/人味改造-2026-09-18/_evidence/`；
回归锁 `persona_chat`(**88**) / `s8_stream`(**69**) / `s7_event_speech`(**135**)，**均已进 G2**。**三套件都不联网、不调 Ollama。**
- **人设单一真源 = `ralsei_pet/assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**不要**只写 Modelfile
  （Ollama 用 messages 的 system **整体替换** Modelfile 的 SYSTEM → 写模型里的人设一次都不生效）。
  → **本机唯一可行的"训练"杠杆**（真 LoRA 不可行，见 §6.8）。persona **是 prompt 不是文档**：不许 markdown。
- **persona 完整性锁（改 persona 必须全保住）**：A1–A11 + A12 三条接法规则 + A12b 反向控制（无成对示范）+
  **A13–A17 世界观节**（有节 / 七锚：黑暗喷泉·光之民·暗之民·两位光之英雄·Kris·Susie·Lancer / 使用约束 /
  "瞒过同伴" / 负控制无元游戏词）+ F1/F7。**别再放整句示范**（4B 会逐字背）；但"先接住主人那件事"的**行为锚不能丢**。
- **世界观节（用户硬要求"他知道他该知道的游戏内容"）**：persona 的「我知道的世界」。**依据取原作语料不取我记忆**
  （`analyze_ralsei_worldview.py` 统计 853 条 Ralsei 原台词 → `_evidence/ralsei_worldview_2026-09-19.txt`）。
  **必须带使用约束**（主人不问不主动讲 / 别硬拐话题），否则退化成"设定倾倒"。Ch3–4 设定名先 WebSearch 核实。
- **判退只看"和自己最近说过的（recent）重复"**，不是"像 persona 示范"。**C7/C8 是防回退断言**。
- **采样参数必须落 Modelfile**（`/v1/chat/completions` **静默忽略 `num_ctx` 与 `repeat_penalty`**）→ 参数 A/B 走原生端点。
- **输出护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级，别乱调）**：
  **0a** 句中括号动作（只删那段；**必须排在 0b 之前**）→ **0b** 剥 markdown →
  **0c** 禁说清单（出戏＋客服腔；**必须排在 0b 之后**；判据**与事件链路同源**，从 `event_speech` 导入，
  **不许另立第二份表**）→ 1 自问自答截断 → 2 车轱辘话判退 → 3 超长截断。
  **判退后必须重采样一次**。锁：C18b / **C20–C23** / **H1–H4**。
  **S8 流式**：`iter_lines(chunk_size=1)`（**流式收益的一半**）；流式只做"前缀安全"清洗，护栏负责"最终算数"；
  重采样前先 `_stream_reset()` 擦干净。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**；唯一出口 `speak_event(kind, pool, face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → **返回 `""` 沉默**）；**禁止 import Qt / 项目内模块**（初始化环）。
  输出闸：出戏 ＋ 客服腔禁语（`_BANNED_PATTERNS`，按**动词块**收）＋ 旁白化（句首括号/星号整句作废）＋
  句中括号动作（`strip_action_parentheticals`，**与对话链路共用**）。**lean 请求**：`speak_event` 是**唯一**
  传 `lean=True` 处（system 只放 persona）→ 保 KV 前缀缓存（否则首字 +1.19s，超 `EVENT_SPEAK_FIRST_TOKEN_MS=1200`）。
- **`ralsei:v3`（现用底座）= `qwen3:4b-instruct-2507-q4_K_M`** + 原采样参数（num_ctx 8192 / temp 0.85 / top_p 0.92 /
  repeat_penalty 1.15 / num_predict 256），由 `assets/ralsei.modelfile` build。**⚠️ 换底座不能只改 config.json**
  （`api_client` 只发 temperature+max_tokens）→ **必须 `ollama create <新tag> -f ralsei.modelfile`**。
  **4B 判退 0/28**；7B 又慢又平→**已否决**。`ollama pull` 客户端设 `HTTP_PROXY` **对 daemon 无效**。

## 7. 历轮索引 / H4-H5 / 遗留（详见参考 §7–§9）
- **7–8** 路径 import 修复 + #10~#13（抖动/坠落误判/斜抛/特殊动画）。**9–11** `conversation_focus` /
  `memory_store` / `memory_graph`（多跳联想 + 抽词剪刀 + 择优 clique）。**12** jieba 软依赖 + `data_store` 收口。
  **13** 建楼遮挡判定 + 层数 + 渲染层序 + DPI 定论。**14** 楼层判定接线。**15** 建楼死代码清理。
  **16** 建楼只读复检（`verify_build_req_audit.py` 是**修复前快照**、不在 G2）。**17** 缺口批次 A。**18** 批次 B + S8 流式。
  **19** S7 batch 2（`b25e91d`）+ 底座换型 v3（`5a42e8a`）+ 人味第四轮 + 第 4 道闸（`f1aba0f`）+ 世界观节与禁语兜底。
- **H4/H5 上帝类拆分**（用户排期"单独做"）：基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**S1/S2/S3 完成**；
  G2 ✅ / G3 ✅ / G4 ✅；**G1 改为"每项 PR 内做该项专属零引用筛查"**；**Wave 1 顺序 W1-3→W1-4→W1-1→W1-2→W1-6**
  （第一项 `GamesController`）；**Wave 1 旧行号区间已全部失效 → 开工前必须重跑 `scan_method_index.py`**。
- **遗留**：① **真机实测（用户做，2026-09-19 明确"还没办法实测"→ 整块搁置）**：遮挡 / 上下动手感 /
  边缘掉落不生气而关窗生气 / **世界观节 A/B 行为探针** —— **契约级+单元级已锁，真机行为级未验**。
  ② `climb_to_top_window()` 仍走裸窗口 ③ 程序目录 `.bak` 与 `code-quality-audit/` 编码告警存量未清理（等用户点头）
  ④ `E:\RalseiMemory\logs\ralsei_pet.log` 在 exFAT 上 `os.rename` 撞已存在目标 → `WinError 1` → **日志永不滚动**
  （独立基础设施缺陷，未修）⑤ S7 第二批剩余 ~11 处候选**不阻塞**。
