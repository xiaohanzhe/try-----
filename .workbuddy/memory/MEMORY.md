# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

> **详细契约（§4.1–4.12）、验证脚本教训（§5）、人味改造线全文（§6.1–§6.10）、世界观网图（§10）、历轮索引（§7–§9）
> 已拆到同目录 `参考-契约与历轮（详版）.md`**（**不自动注入，用时 Read**）。本文件只留**每轮都必须遵守**的铁律、速查契约与当前状态。

## 0. 铁律
- 每轮改动完成即 **commit + push**（"以免后期找不到"）；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根 `代码质量复审报告_*.md`（人味线用 `人味*.md`）；证据进 `code-quality-audit/<轮次>/_evidence/`；
  侦察 `_recon/`（gitignore）。
- 改代码前先跑 G2 `code-quality-audit/regress/run_all.py`（**24 套件 / 1145 PASS / 全 IDENTICAL**）。
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
5. **代理端口现查为准**（`netstat -ano | findstr LISTENING` 或读注入 `HTTP_PROXY`）。
   ❗**2026-09-19 更正：任何单个端口的一次成败都不能当结论。** 实测 64676 一次 `CONNECT tunnel failed 502`、
   下一次 200；7897 一次 `schannel` 握手失败、下一次就过。**每端口至少 2~3 次 + 跨端口重试。**
   另：`github.com`（push 目标）**直连 443 不通**，但走代理 curl 200；`api.github.com` 直连就通。
   → **`ls-remote`/`push` 失败 ≠ 网络不通 ≠ 端口选错**（详见 skill `win-git-utf8-push` 铁律 0.2）。
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

## 2. git push（**完整配方见 skill `win-git-utf8-push` + 参考 §2，照抄即可**）
- 症状：退出码 128 且全静默 = 非交互 GCM 取不到凭据；**提交信息必须 Write 写 UTF-8 文件 + `git commit -F`**
  （`-m @'...'@` 会被 PS 5.1 拆 argv → push 退 0 **假成功**）；**提交后必核 `git log --oneline -1`。**
- **❗核验命令自己也会说谎**：`ls-remote` 绝不从别的命令 argv 切片复用（拼出非法命令 → 恒空 → 误报"没落地"），
  必须**独立构造** + 重试 3~5 次 + `git rev-parse origin/main` 交叉验证。**先怀疑核验，再怀疑被测物。**

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
  **新增底层模块（如 `relationship`/`worldview_recall`）一律零项目内 import**（初始化环）。
- **世界观网图**（第二十一轮，**全文见参考 §10**）：`assets/ralsei_worldview.md` 块头下写
  `@@> 本键 -> 邻键, 邻键` 声明边；`worldview_recall.load_graph()` → `(blocks, adj, dangling)`；
  `recall()` = 关键词取种子 → **只在名额没用满时沿种子出边补邻块，只扩一层、不越 MAX_BLOCKS**。
  **两条铁律**：① **邻块不要求自己被 cue 命中**（加同门槛 = 扩图永不开火）；② **不做二阶扩图**。
  **添新块必须同时给反向边**。⚠️ **`A in rev[B]` 检反向是恒真判据**（正确判据 `b.key in adj[t]`，
  它曾掩盖图里 4 条真单向边）；**鉴别力体检必须改文件**（`adj` 是解析期算的，改内存 → 假 P）。
- **建楼（参考 §4.9，本项目最贵的一条线，勿凭直觉"重做"）**：楼层 = 窗口的**可见区域**，`floor_visible_contains`
  是**唯一判据**；**禁用 `Qt.WindowStaysOnTopHint`** → `_apply_pet_z_order()`（**必须在 `show()` 之后**）；
  坠落只看**层高比较**，起因按 `is_floor_valid(old_floor)` 分流；生气时长由 `_fall_reason` **纯派生**；
  **甩飞路径必须显式 `self._fall_reason = None`**；跳/爬 `_jump_kind_for_span`；**不做"逐层小跳"**；
  ⚠️ **`climb_1_*`=朝右 / `climb_0_degrees_*`=朝前 是用户当年原话口径，不许再改**。
- **DPI**：写探针/裸进程脚本**必须先建 `QApplication` 再读任何坐标**。
- **G2 封闭性**：`HERMETIC_IDS` 注入临时 `RALSEI_MEMORY_DIR`；**`save_baseline` 是合并模式**。
- **误报清单（勿据此改）**：`learn_new_skill` 有守卫；`_on_ai_reply` 已由 `pyqtSignal` 排主线程；
  `reset_special_states` 零调用；原子写/回收站删除已正确防御。

## 5. 验证脚本教训（**全文见参考 §5 + §5.1，改断言前必读**）
- 源码级断言别用 `"字面量" in 源码` → `code_only_src()`；**含字符串字面量的 needle 走 `code_no_comment()`**（5 次踩）。
- **回归锁必须有鉴别力**（两侧同值＝没测）；**正/负控制必须成对**；断言**断行为不断赋值**、别写在死代码上。
  ⚠️ **恒真判据比不写还危险**（写反了以为测过了）：第二十一轮 `A in rev[B]` 检反向恒真，掩盖了图里 4 条真单向边。
  **体检鉴别力必须"改文件"**（解析期算的 `adj`/`dangling` 改内存 → 假 P）。
- **"函数写对了" ≠ "产品用上了"（最贵坑，4 次）** —— 镜像：**"没改也没人调用"要么接线、要么删**。
- **描述/断言里别写会随代码增长的数字**（`ralsei:v2`、`FROM qwen2.5:3b` 都假红）。
- **A/B 先断言 A ≠ B**（"旧值"若改动**已先提交** → A == B，退化成自己跟自己比**且非常像真的**）：
  取**父版本** + **md5 相同即 `SystemExit`** + `--old-rev`。
- **对照组要重复跑，先量尺子的公差**（±2 条就是噪声）；**计数会被反向激励** → **永远先读原文再看计数**。
- **提示词里分组标签本身就是可能被输出的词**；**别为禁用项追加具体反例**。
- 离屏**无字体** → `QPainter.drawText` 静默不画；**PIL 用 `ImageFont.truetype('C:\Windows\Fonts\msyh.ttc')`**。
- **删 Ollama 模型看 blobs 目录**（标称 10.4GB 实际 6.6GB）；**删完必须真发一次 `/api/chat`**。
- **❗核验命令自己也会说谎 —— 先怀疑核验，再怀疑被测物**（见 §2 第 2 条）。**核验命令必须独立构造。**

## 6. 人味改造线（2026-09-18 ~ 20）（**全文见参考 §6.1–§6.10**）
报告 `人味*.md` / `第二十一轮报告_*.md`；证据 `code-quality-audit/人味改造-2026-09-18/_evidence/`；
回归锁 `persona_chat`(**139**) / `s8_stream`(**69**) / `s7_event_speech`(**135**)，**均已进 G2**。**三套件都不联网、不调 Ollama。**
- **人设单一真源 = `ralsei_pet/assets/ralsei_persona.md`**（每次对话读出来当 `system`）。**不要**只写 Modelfile
  （Ollama 用 messages 的 system **整体替换** Modelfile 的 SYSTEM → 写模型里的人设一次都不生效）。
  → **本机唯一可行的"训练"杠杆**（真 LoRA 不可行，见 §6.8）。persona **是 prompt 不是文档**：不许 markdown。
- **persona 完整性锁**：A1–A11 + A12 三条接法规则 + A12b 反向控制 + **A23–A25 平级口径** + F1/F7。
  **别再放整句示范**（4B 会逐字背）；但"先接住对方那件事"的**行为锚不能丢**。
- **❗平级口径（第二十轮，用户硬要求）**：**不许叫"主人"**，用户与 Ralsei **平级**，他**不是为谁而来**
  （「他只是来了仅此而已」）。**persona 与代码两层都要改**（只改 persona 无效）：persona 22→1 处；
  代码 5 处 = `_PERSONA_FALLBACK` / `_build_ai_context`(3 句) / `start_autonomous_speech`(2 prompt) /
  `memory_system.recall_text` 的 `who` / `_role_marker_re()`（**保留"主人"**，识别旧遗留标记）。锁 **J1–J6**。
- **❗世界观 = `assets/ralsei_worldview.md` + `modules/worldview_recall.py`**（第二十轮拆出，**第二十一轮改网图**）。
  `MAX_BLOCKS=2` 硬上限；**无命中返回空串**；`lean=True` 跳过；**动机是 KV 前缀缓存**，persona **13140→9269B**。
  **依据取原作语料不取我记忆**（`analyze_ralsei_worldview.py` 统计 853 条原台词）。锁 **K1–K20**；图契约见 §4。
  **端到端行为探针** `code-quality-audit/人味改造-2026-09-18/verify_persona_worldview.py`（`--no-recall` 为对照组）。
- **❗关系演进（第二十轮）= `modules/relationship.py`**：四档**按用户原话顺序** distrust→guarded→warming→friend；
  `TRUST_INITIAL=0.12`（**从 distrust 起步，不是朋友**）。**信任度不可见**：给模型的只有**行为指令**
  （无数字无档位名）+ `_FORBID_LEAK` 禁泄；`describe()`（唯一带数字）只进日志。
  唯一写入口 `note(event)`；事件由**确定性** `classify()`（关键词表，不调模型）判定。
  **勿把下界抬到 TRUST_INITIAL**（那会让 `harsh` 变死事件）→ 值域 `[0, TRUST_MAX]`。锁 L1–L16。
- **AI 底座**：`ralsei:v3` = `qwen3:4b-instruct-2507-q4_K_M`（由 `assets/ralsei.modelfile` build）。
  **采样参数必须落 Modelfile**（`/v1/chat/completions` **静默忽略 `num_ctx`/`repeat_penalty`**）；
  **⚠️ 换底座不能只改 config.json → 必须 `ollama create <新tag> -f ralsei.modelfile`**。**4B 判退 0/28**；7B 慢且平→否决。
- **输出护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级，别乱调）**：0a 句中括号动作 → 0b 剥 markdown →
  0c 禁说清单（出戏＋客服腔，**与事件链路同源，不许另立第二份表**）→ 1 自问自答截断 → 2 车轱辘话判退
  （**判退只看"和自己最近说过的（recent）重复"**）→ 3 超长截断；**判退后必须重采样一次**。锁 C18b/C20–C23/H1–H4。
  **S8 流式**：`iter_lines(chunk_size=1)`（**流式收益的一半**）；流式只做"前缀安全"清洗，护栏负责"最终算数"。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**；唯一出口 `speak_event(kind, pool, face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → **返回 `""` 沉默**）；**禁止 import Qt / 项目内模块**。
  `speak_event` 是**唯一**传 `lean=True` 处（system 只放 persona）→ 保 KV 前缀缓存（否则首字 +1.19s，超 1200ms 上限）。

## 7. 历轮索引 / H4-H5 / 遗留（详见参考 §7–§9）
- **7–8** 路径 import 修复 + #10~#13。**9–11** `conversation_focus`/`memory_store`/`memory_graph`。
  **12** jieba 软依赖 + `data_store` 收口。**13–18** 建楼线 + DPI + 批次 A/B + S8 流式。
  **19** S7 batch 2 + 底座换型 v3 + 人味第四轮 + 第 4 道闸 + 世界观节与禁语兜底（`2738189`）。
  **20**（`930657a`）**世界观按需召回 + 平级口径（去"主人"）+ 关系演进**（详见参考 §6.10）。
  **21**（`bc9b1d7` + `75369b8`）**世界观网图 + 内容加厚 + 端到端探针**（详见参考 §10）。
- **H4/H5 上帝类拆分**（用户排期"单独做"）：基线 `code-quality-audit/架构改造-H4H5/`（**勿重测**）；**S1/S2/S3 完成**；
  G2/G3/G4 ✅；**G1 改为"每项 PR 内做该项专属零引用筛查"**；**Wave 1 顺序 W1-3→W1-4→W1-1→W1-2→W1-6**
  （首项 `GamesController`）；**旧行号已失效 → 开工前必须重跑 `scan_method_index.py`**。
- **遗留**：① **真机实测（用户做）**：遮挡 / 上下动手感 / 边缘掉落不生气而关窗生气 ——
  **契约级+单元级已锁，真机行为级未验**。**世界观召回的真机行为探针已在第二十一轮跑过**（端到端 12 PASS）。
  ② `climb_to_top_window()` 仍走裸窗口 ③ `.bak` 与 `code-quality-audit/` 编码告警存量未清（等用户点头）
  ④ `E:\RalseiMemory\logs\ralsei_pet.log` 在 exFAT 上 `os.rename` 撞已存在目标 → `WinError 1` → **日志永不滚动**（未修）
  ⑤ S7 第二批剩余 ~11 处候选**不阻塞**。
