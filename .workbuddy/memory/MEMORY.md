# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

## 铁律
- **每轮改动完成即 commit + push**（"以免后期找不到"）。称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根（`代码质量复审报告_*.md`）；证据进 `code-quality-audit/<轮次>/`，侦察 `_recon/`（gitignore），
  留痕 `_evidence/`。改代码前跑 G2 `code-quality-audit/regress/run_all.py`（现 **23 套件 / 925 PASS**）。
- **下载/生成物默认落 `E:\Download`**（临时件 `_tmp\` 用后即删）；仓库内产物留项目目录。系统默认下载目录**不动**。

## 环境铁律
1. **Bash 工具不可用** → 一律 **PowerShell**；列目录用 Glob/Read。
2. PowerShell **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在会 exit 1 且无输出
   → 先建目录）。
3. **起进程**：`cmd /c`、`Start-Process`、WMI 全被拦 → 只能 `&` + `run_in_background:true`。
4. **杀进程**：`Stop-Process`/`taskkill` 静默失效 → Python+psutil 按 cmdline 匹配（会连带结束所在 shell，分步跑）。
5. **删文件**：管道 `Remove-Item` 静默无效 → `[System.IO.File]::Delete()` + `Test-Path` 校验。
6. Python：**`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— **G2 与所有套件必须用它**；
   托管 venv（3.13）缺 `bs4` → `round5_smoke` 假 FAIL。
7. 代理：**沙箱注入端口会变，现查为准**（`netstat -ano | findstr LISTENING` 找 `127.0.0.1:<port>`，
   或读沙箱注入的 `HTTP_PROXY`）。**2026-09-18 实测 Clash `7897` 又好了**：
   `git push` 与 `ls-remote` 走 7897 一次过，`a37f136..ee39227` + 远端哈希核验一致。
   → 旧记录"7897 对 GitHub TLS 直接握手失败"**作废（它是当时的状态，不是恒定事实）**；
   换端口前先直接试一次，别照抄旧结论。
8. **E 盘是外接盘、会掉线**（`Get-Volume` 只剩 C/D、`Get-Disk` 仅一块 NVMe 即掉线）→ "本地中转站"是**可用性必需**。
   判在线看 `Get-Disk`/`Win32_DiskDrive`；注册表 `\DosDevices\E:` 只是**历史挂载记录**，不能当在线证据。
9. **Agent 沙箱有 safe-delete 守卫，按目标路径累计删除计数**（阈值 50，`count=51` 即触发）。症状：**进程在
   import/初始化阶段就被杀**，stdout 只剩一行 `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {...}`；
   批量跑套件时表现为**多个套件同时 `exit=1 PASS=0` + 假 DIFF**（看着像代码全崩，实为测试自伤）。
   **【第十三轮已推翻旧结论】**旧记录说"计数恒定 160 → 确定性拦截、与预算无关"——**错**：计数就是累计删除数，
   恒定的原因是**一次默认启动就删十几次**（`_is_writable_dir` 每次调用都真的建/写/删 `.write_probe`）。
   已在应用侧根治（`_is_writable_dir` 加零副作用快路径 `os.access`；快路径**不缓存**以免拔盘检不出），
   **默认启动方式在沙箱内现已能正常跑起来**（证据 `第十三轮/_evidence/round13_default_launch_ok.md`）。
   另注：`dangerouslyDisableSandbox` 对它无效。
   **通则：见到"计数恒定"别急着下"确定性"结论——把触发源干掉再看还发生不发生。**
10. **证据/报告一律让 Python 自己写 UTF-8，绝不用 PowerShell 捕获原生程序 stdout**：`& py x.py *> o.txt`、
   `... | Out-File -Encoding utf8` 会把输出的**字节按控制台代码页（GBK）解码再按 UTF-8 重写** → 中文二次编码
   成读不懂的方块字（**文件内容真坏了，不是显示问题**）。第十三轮我就这么把两份真机证据写坏并推送了。
   · 正确：脚本内 `open(path,'w',encoding='utf-8')` 自写（探针的 `_out_*.txt` 即此法）；搬运用 `Copy-Item`
   （逐字节，不经编码转换）。
   · **`Write` 工具覆盖一个原本带 BOM 的文件时会保留 BOM**（内容更新、BOM 还在）→ 去 BOM 必须用 Python 重写。
   · 校验工具 `code-quality-audit/tools/check_evidence_encoding.py`（`--out` 自写报告、`--strict` 让告警也算失败；
     **确定性损坏** = 非法 UTF-8 / U+FFFD；**告警** = BOM / 疑似乱码绊线）。
   · **别信教科书式往返判据**（`text.encode('gbk').decode('utf-8')` 成功即乱码）：PowerShell 那次解码是**有损**的，
     往返直接抛异常 → 判据永不触发 → 报出 `mojibake=0` 的**假清白**。**"能力自评失准"比"能力不足"更危险**：
     一个报 0 的检查器会让人以为已经验过了。现用"命中 ≥2 个特征字"的绊线 + 明确标注"会误报、需人工确认"。
   · 存量：`code-quality-audit/` 263 个文本文件里 1 个确定性损坏（`第六轮/_evidence/_diff_numstat.txt` 是 UTF-16）、
     70 个告警（全带 BOM，其中 29 个真乱码），成因都是早期几轮的 PowerShell 捕获；**未擅自清理，待用户点头**。
9. **注入的 `current_time` 会滞后于系统真实时间**：2026-09-18 注入值写"09-16 00:22"，`Get-Date` 实测
   **2026-09-18 00:07**。**凡落盘带日期的产物（报告名/日志名），先 `Get-Date` 校准**；错了就 `git mv` 改名
   （未推送时可直接 `--amend`）。
10. **别用 PowerShell 管道读中文元数据**：`ollama show --modelfile` 经管道读出全是 GBK 乱码
    （`浣犳槸涓€涓鑹叉壆婕?AI`），会误判"模型内容已损坏"。**改走 REST API + 显式 UTF-8**（本轮 `probe_ralsei.py`）。
11. **`github.com` 主站可能整段不可达而 `api.github.com` 仍 200**：此时 `git push` 必失败
    （本轮 3 代理 ×3 次 + 7 个备用 IP 全 `000`），但 **api.github.com 通**。
    处置：**提交照做（本地不丢）→ 如实报告网络阻塞 → 稍后重试**（本轮 ~25 分钟后自行恢复）。
    **别因 push 失败就怀疑凭据或改 git 配置。**

## git push（退出码 128 且全静默 = 非交互 GCM 取不到凭据）
```powershell
$cred = "url=https://github.com/xiaohanzhe/try-----.git`n`n" | git credential fill 2>$null
$pw  = ($cred | ? { $_ -like 'password=*' }) -replace '^password=',''
$usr = ($cred | ? { $_ -like 'username=*' }) -replace '^username=',''
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$usr`:$pw"))
git -c credential.helper= -c http.proxy=http://127.0.0.1:57186 -c https.proxy=http://127.0.0.1:57186 `
    -c http.extraheader="Authorization: Basic $b64" push origin main   # 端口现查；重试 3–5 次
```

- **推送结果**：`TRY1: 41ffecd..f1f8079  main -> main` 一次过是常态。
- **旧记录作废**：曾写"沙箱 54231 / Clash 7897"。54231 已不顺；**7897 对 GitHub TLS 直接握手失败**。- 令牌别写进仓库文件。核验外发用 `git ls-remote origin refs/heads/main`（加同样头），比看退出码硬。
- **提交信息用 Write 写 UTF-8 文件 + `git commit -F <文件>`**：`-m @'...'@` 遇带空格的英文引号串会被 PS 5.1 拆
  argv → 提交没发生、push 退 0 假成功。提交后必核 `git log --oneline -1`。
  **别用 `Out-File -Encoding utf8` 写提交信息**：PS 5.1 会加 **BOM**，标题首位多出一个不可见字符（`git log` 里显示成 `锘`）；用 `Write` 工具写（无 BOM）。
  **第十八轮又踩一次，并发现"修法也有坑"**：已经用 `Out-File` 写坏了之后，**不能**用 `Write` 工具去覆盖修复 ——
  它在**原本带 BOM** 的文件上会**保留 BOM**（内容更新、BOM 还在）→ 第一次 amend 仍然是脏标题。
  **必须换个新路径重新写**（新文件才无 BOM），或用 Python `open(...,'w',encoding='utf-8')` 重写；
  **校验**：读前 3 字节（中文标题应是 `231,172,172`，出现 `239,187,191` 就是 BOM）。
  成本提示：这一步每次都要 `--amend`（**未推送**时安全；已推送就得靠后续提交兜），所以**第一次就别用 `Out-File`**。

## 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有，未认证 401/404）；main→origin/main。GitHub 连接器只覆盖
  公开库，看不到本仓库（404）。
- 真机起：`Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → 被遮挡/鼠标穿透 → **甩飞、抛物线
  只能离屏断言**。
- 卫生：`compileall` 会改写被跟踪的 `src/__pycache__/*.pyc` → 跑完 `git checkout --`。`.gitignore` 覆盖 `*.log`/
  `*.bak`/`__pycache__/`/`code-quality-audit/*/_recon/`/`regress/_out/`；`*.log.<日期>` 不匹配。

## 勿回退契约（改代码必须遵守）
- **多屏**禁用 `QApplication.desktop().availableGeometry()`（只返主屏→"瞬移"根因），用 `_virtual_screen_rect()`/
  `_current_screen_rect()`/`_clamp_pos_to_desktop()`/`_desktop_floor_y()`。物理量必须钳 `dt≤0.1s`（否则卡顿后单帧
  dt 变大 → 位移二次放大 → 同一种"瞬移"）。
- **甩飞/抛物线**：判定只能在 `mouseReleaseEvent`（`_drag_samples` 0.12s 窗口，`_FLING_SPEED=900`/`_BOUNCE_SPEED=250`）；
  初速只由松手速度定（等比缩放 + **矢量和**限幅）；`_fall_vy0` 只在第一帧记录；清理点共用 `_FALL_VELOCITY_ATTRS`/
  `_FALL_STATE_ATTRS`；落地相位 `_fall_phase_start`+`_fall_flight_time`+`_fall_landed`；空中接住减速积分
  `s=v0·t·(1-t/(2·dur))`。
- 动画 `fps=6`；自主说话唯一入口 `start_autonomous_speech()`（`AUTONOMOUS_SPEECH_MIN_INTERVAL=600.0`），
  **AI 关闭必须沉默、不得回落内置台词**；不劫持鼠标、拖拽 1:1、起身类 `play_animation_once(...,restore_to="idle")` 只播一次。
- **特殊动画（#13）**：来源只三类 —— ① `ai_driver` 决策 ② 用户显式交互 ③ 物理状态机（fall/splat/land/jump/wake）。
  **环境自动触发不得自行播动画**，只能 `ai_driver.note_event()` 上报观察（`react_to_desktop_element`→
  `_note_desktop_observation`、`_react_to_video` 已收编）；`update_animation_by_emotion` 与 `on_mouse_hover` 已空实现。
  播放期 `_special_anim_locked()` 禁移动且 **force 也不能打断**；待机循环需原地静止 ≥`IDLE_LOOP_MIN_SECONDS=180` 才推进帧；
  切换位置一致靠 `_anim_anchor_offset`/`_compose_anchored_sprite` 按 alpha 包围盒中心对齐（idle 偏移 (-20,+2.5)）。
- **多跳联想（第十轮）**：分层边 + hub 惩罚（IDF×度 ∈[0.25,1]）+ 路径打分（∏边权×∏节点权×`HOP_DECAY=0.72`^跳数）
  + `RecallBudget`。铁律：① 门槛 `HOP_TIER_FLOOR={1:weak,2:weak,3:mid}` + **中转资格** `_BRIDGE_MIN_RANK=mid`
  （弱边**可到达、不可再出发**）—— 静态 `{1:weak,2:mid,3:strong}` 在真实语料（98% 弱边）下锁死多跳；
  ② **PPR 只加权不准入**（`kw *= 1 + PPR_MIX×ppr_norm`），准入永远由路径分定。`assoc` 是 property、`_graph` 是唯一
  真源；`graph.paths()` 只吃 `seed_map()` 归一化 dict（传 list → `seeds.items()` 抛错被吞 → **多跳静默返回空**）。
- **联想输入端（第十一/十二轮）**：① 抽词唯一入口 `conversation_focus.extract_keywords`（**三层择优**：
  `_from_segmenter`→`_extract(strict=True)`→`_extract(strict=False)` 兜底，**不返回空**）。碎片治理靠**位置专员剪刀**
  （`_STOP_MULTI`/`_EDGE_FUNC`/`_INNER_FUNC`+`_INNER_VERB`/`_EDGE_VERB`/`_TAIL_FUNC`，每把只盯一字符位）+ **免伤名单
  `_KEEP_WORDS`**。`_ngrams` **按位置生成**。`set_segmenter(fn)` 是注入点，**抛异常/返回空都回落内置**。
  ② `memory_graph.EDGE_TOPOLOGY` **默认仍是 `clique`**（勿凭直觉改 star/chain）：star/chain 精确率更高（55% vs 50%）、
  密度更低（0.83 vs 3.26 边/点），**但过不了多跳可达闸门** —— 强制 `代码—熬夜—咖啡` 时 clique stage2/3 通，
  star/chain **强边也断链**。密度靠**输入端**压，**不靠砍边**。回归锁 B13–B17。
- **存储两层（第十二/补丁）**：vault=`E:\RalseiMemory\`（卷标含"肖翰哲"，复用 `memory_store` 设备发现，**真机已确认**）；
  staging=`%LOCALAPPDATA%\RalseiPet\`（E 离线落脚点）。**读永远 vault 优先**，E 回来由 `migrate_from_staging()` 搬。
  `data_store` 是**唯一入口**（`artifact_path`/`app_file`/`data_root`）；7 类产物（logs、crash.log、config.json、
  customization_config.json、entertainment_data.json、growth_data.json、jieba.cache）全走它。收编历史遗留**只复制不搬走**
  （被跟踪的默认模板不能删）。迁移五约：先探 `_movable`（占用跳过）→ copy 校长度才删源 → 同名比 mtime 留新、
  **落选者一律留档 `.old`**（含"源更旧"这支 —— 只 skip 会让中转站永远清不空、`staging_has_data()` 恒 True）
  → 只删空目录不递归 → vault==staging 拒搬。
- **初始化环（第十二轮，补丁修全）**：`logger_utils → data_store → memory_store → logger_utils` 是**间接**环；链上
  **任何一环**在 import 期要 logger 就会成环，后果是 `vault_root()` 把"依赖未就绪"误判成"设备离线"→ `_log_dir()`
  **把错误的中转站路径缓存下来**（E 在线也写错地方）。铁律：**被反向依赖的底层模块一律用 `modules/lazy_log.LazyLogger`**
  （`data_store`/`memory_store` 已改；它自己不 import 项目内模块）。配合 `logger_utils._log_dir()` **失败不缓存** +
  `_init_logging` 重入护栏。回归锁 C2（**须有鉴别力**）+ D11/D12。
- **jieba 是软依赖（第十二轮）**：适配层 `modules/text_segmenter.py`，`install()` 走 `set_segmenter`，没装/加载失败/
  切词抛异常一律静默回落内置；后台预热；`calls`/`fallbacks` 计数；可选 `jieba_userdict.txt`。**词边界归适配器，
  停用词/长度/去重仍归 `_from_segmenter()`（唯一一份）**。实测六句 56→14 词条。G2 需归一化 `Loading model cost X seconds`。
- **「建楼」遮挡 / 层数 / 层序（第十三轮，按 Windows 原生口径）**：**楼层 = 窗口的"可见区域"，不是整矩形**。
  ① 几何：`_cut(rect,hole)` 最多切 4 块、**产出天然两两不重叠** → `sum(面积)` 精确；`visible_subrects(target,blockers)`
  依次切。`MIN_FLOOR_VISIBLE_AREA=40*40`（语义是**"够不够站"**，不是"有没有缝"：1px 缝 1000px² 不成层，4px 4000px² 成层）。
  ② 编号：`platform_height=(n-i)*5` **按名次**（前=高），`DESKTOP_IDENTITY='desktop'` 恒 0 层；**通用规则：可见面积
  跌破阈值 = 该层"暂时不存在"，且它**不再遮挡更低窗口**。③ 查询：`floor_visible_contains` 是**唯一判据**，
  站立/下落/跳跃/边缘全走它；`get_drop_destination`/`find_support_below` 只取"**下面第一个**能接住的"（不许跨层）；
  `get_current_floor` **几何优先**，`WindowFromPoint` 只在几何判到桌面时做"**只向上**的兜底"（否则 G2 变随机测试）。
  ④ 渲染：**禁用 `Qt.WindowStaysOnTopHint`**（永久置顶 = 遮挡从渲染层就失效，用户原话"根本没遮挡关系"）；
  改用 `_apply_pet_z_order()` → `SetWindowPos(pet, insertAfter=所站楼板)`，**让系统算遮挡**。`get_insert_after_hwnd` /
  `set_window_behind` 原是全项目零调用的死代码，现已接活（4 处：1s tick / 落地 / `show()` 之后 / 松手）。
  **顺序铁律：`show()` 有"提到前面"的副作用 → 必须 `show()` 之后再调 z 序。**
  ⑤ `desktop_interaction` 助手：`get_frame_rect`(DWM `DWMWA_EXTENDED_FRAME_BOUNDS`=9，**不含 DWM 隐形阴影/调整边框**)、
  `is_cloaked`(=14 幽灵窗口：挂起 UWP/别的虚拟桌面)、`window_from_point`(=`WindowFromPoint`+`GetAncestor(GA_ROOT=2)`，
  防返子控件)、`get_window_pid`。**枚举按进程排除自身**（不再靠标题里有没"Ralsei"——会误伤同名窗且漏掉本进程对话框）；
  排除 `WS_EX_TOOLWINDOW`/`WS_EX_NOACTIVATE`。**64 位坑：`WindowFromPoint`/`GetAncestor` 的 `restype` 必须显式
  `c_void_p`**，否则 HWND 高位被截断且**静默失效**（同 `OpenProcess` 老坑）。窗口表**不再自带 `platform_height`**
  （原 `z_order*5` 是第二套编号 → 删掉，`floor_manager` 唯一真源）。`is_floor_valid` **不再要求四边逐一相等**
  （DWM 1px 抖动会让楼板反复"消失"→ 无故坠落）。回归锁 `verify_round13_build.py` A–G 71 项。
- **「建楼」上下动 / 落到某层（第十四轮）**：**楼层系统是跳跃的唯一入口** —— `check_nearby_windows` 里
  `fm = self._floors_for_jump()` 拿到楼层就规划、拿不到就**直接 return**。
  【第十五轮更新】那句"下面还有裸窗口矩形兜底段"**已不存在**：整段（154 行）删掉了 ——
  `floors` 空 ⟺ 一个可见窗口都没有 ⟹ 本来就没有可跳的楼板，旧段在那种情况下同样无对象可枚举。要点：
  ① **上跳落点必须过可见区域门** —— `_floor_entry_plan` 出落点后 `nearest_visible_point` 吸附；
     触发几何照旧"贴边 `NEAR=60px`"（手感不变，判据换掉），别改成"横向覆盖就跳"（会一路狂跳）。
  ② **下跳显式取相邻下一层** `adjacent_lower_floor`（按 `platform_height` 名次；**桌面返回 `None`**），
     不能从 `get_jump_destinations` 结果里"顺便拿" —— 那里按 x 范围过滤，而"半个身子探出楼板"恰好
     x 已出范围 → 会被漏掉。**不穿透**是硬要求。
  ③ **`current_window` 已降级为派生缓存**（原来与 `current_floor` 是**两套真源** → 站在窗口上却按桌面判）。
     **唯一写点** `_sync_window_cache_from_floor(floor)`（不删，三十多处还在读）；入口
     （走路换楼板 / 跳跃落地 / 重力落地）全收口到它；重力落地里手写的裸 dict 构造已删。
     【第十五轮更新】"走路换楼板"那条 `update_floor` 已删 → 只剩 `check_window_movement` 一个入口。
  ④ **落地当场结算**：`handle_jump` 完成帧必须写 `current_floor`+`current_platform_z`、同步缓存、
     **立刻** `_apply_pet_z_order()`（原来要等 1s 节拍，落地那一瞬层级是错的）、播 `land` 一次。
     低速落到**窗口层**也要 `play_animation_once("land")`（原来直接 `idle` → 看着像平移）。
  ⑤ **坠落按起因分流**：`start_falling(..., reason=)`；`reason=='floor_removed'`（只由"用户抽走楼板"
     两个入口传：关窗 / 窗口没跟上）→ `fall_mad` + `max_fall_duration=5.0`；**"自己走到边缘掉下去"
     "跳跃被判穿透"不带起因**（不算用户行为，不误用生气动画）。回归锁 `verify_round14_move.py` A–G 41 项。
- **「建楼」死代码清理 + 坠落起因修正（第十五轮）**：清掉"**没改也没人调用**"的那一堆（本项目最贵坑的
  另一面，前几轮踩的是"改了没人调用"）：
  ① **删 `main.py::check_nearby_windows` 尾部裸矩形段（154 行）** —— 它是第十三轮**口径错误的活样本**
     （跳到被遮部分 / 站在窗口上把目标声明成桌面 = 穿透）。不可达，但谁挪掉早返回 bug 立刻复活。
  ② **删 `main.py::update_floor`（67 行）** —— 第五轮 F3 就点名的**零调用漂移副本**（与
     `check_window_movement` 逐行重复且已不一致）、H4/H5 排期方案 G1 优先清理项。
     **它的独有行为（桌面被新窗口覆盖 → `found_window` 情绪）本来就不可达 → 未迁移，等于没有回退。**
  ③ **删 `floor_manager::find_support_below`（`get_drop_destination` 的重复实现）/ `is_on_floor_edge`（无消费者）**。
  ④ **接线 `is_floor_valid`**（自第五轮起就在死引用清单里）：`check_window_movement` 里
     "脚下不再是窗口楼板"要分两种成因 —— `is_floor_valid(old_floor)` 为真 = **窗口还开着 ⇒ 宠物自己走出了
     楼板边缘**（要求："就直直掉下去，落到下面第一块能接住的楼板"）→ `start_falling()` 常规动画；
     为假 = **用户关窗把楼板抽走** → `start_falling(reason='floor_removed')` 生气 ≥5s。
     **原实现一律按"用户行为"→ 宠物被赶到边缘也会生气，与要求正好相反（真 bug）。**
     用"窗口还在不在"而不是"离边缘 ≤N px"判：楼层检查是 **1s 节拍**，宠物一秒能走几百像素，
     距离阈值必漏判；窗口在不在与节拍无关。
  ⑤ **不许误删**：`start_jump` 的裸窗口回落分支**必须留着** —— 还有两个活调用方
     （`climb_to_top_window()` / `command_manager.py:78`）。回归锁 `verify_round15_cleanup.py` A–D 30 项
     + 真机冒烟 `_probe_smoke.py`（真 `RalseiPet()`，不是 stub）。`main.py` 9373→9172 行。
- **DPI 量纲（第十三轮，差点改错方向）**：`Qt` 建 `QApplication` 时把进程设成 per-monitor-v2 DPI 感知；**在那之前**
  进程 DPI 不感知 → `GetWindowRect`/`GetSystemMetrics` 被 Windows 按系统缩放**虚拟化**（本机 150%：物理 2560×1600
  回报 1707×1067），而 **`DwmGetWindowAttribute` 永远返回物理像素** → 混用会得出"DWM 矩形正好 1.5 倍"的假象。
  真机宠物活在 QApplication 里 → **楼层(DWM) 与宠物(Qt) 同量纲**（实测 Qt 2560×1600 / `devicePixelRatio=1.0`，
  三种 GetWindowRect 口径与 DWM 完全一致）。**写探针/裸进程脚本必须先建 `QApplication` 再读任何坐标**，且
  先打印"量纲自检"（`第十三轮/_probe_dpi.py` 即此用）。
- **G2 测试封闭性（第十三轮）**：`run_all.py` 有 `HERMETIC_IDS` —— 凡会实例化 App / 触碰存储的套件统一注入临时
  `RALSEI_MEMORY_DIR`（`find_device_dir` 见到即 return，**连探针都不跑**），既防污染用户真实 E 盘、也防上一条的守卫。
  **`save_baseline` 是合并模式**（原为整体重写 → `--only X --update` 会**静默抹掉其余套件基线**，而输出看着一切正常；
  基线是 H4/H5 改造的唯一安全性判据，不能有这种一键抹除路径）。
- **误报清单（勿据此改）**：`learn_new_skill` 有 `if new_skills:` 守卫；`_on_ai_reply` 跨线程已由 `pyqtSignal` 排主线程；
  `reset_special_states` 零调用；原子写/回收站删除已正确防御。

- **「建楼」坠落路径（第十七轮，**勿回退**）**：触发坠落只看**层高比较**（`new_h < old_h`，取自
  `platform_height`）—— ① 自己走出边缘→桌面 ② 关窗→桌面 ③ **关窗→下方还有窗口**（要求第30行的原例）
  ④ 新窗盖旧窗（`new>old`）**不摔**（要求 ⑪）。起因分流仍在 `is_floor_valid(old_floor)`：
  **窗口还在 ⇒ 自己走出去**（常规动画）；**窗口没了 ⇒ 用户抽走楼板**（生气）。
  **生气动画的时长与素材由起因 `_fall_reason` 纯派生**（模块级 `_fall_splat_hold(pet)` /
  `_splat_animation_name(pet)`，文件头）：关窗 ≥5s / 挪楼板 ≥3s / 无起因 1.0s；素材 `splat_mad`
  （此前全项目零调用）。落地结算（`trigger_splat` / `handle_fall`）**只读不写**。
  坑：① 旧的 `max_fall_duration = 5.0/3.0` 是**死参数**（只有 `handle_fall` 读，而 `start_falling` 把
  `is_falling` 置 False → 走 `handle_gravity_fall`）→ 已删，别再写回去；② `handle_fall` 的 splat 阶段
  时长别再硬编码 `1.0`；③ 甩飞路径**必须显式 `self._fall_reason = None`**（否则上一次关窗的起因残留 →
  甩飞也播生气版并停 5s）；④ 判定函数放**模块级**、**不要**做成 `RalseiPet` 方法 —— 多个历史套件用
  `SimpleNamespace` 轻量桩驱动 `RalseiPet.handle_fall(stub, ...)`，加实例方法会当场 AttributeError
  崩掉三个套件。回归锁 `第十七轮/verify_round17_build_fall.py`（18 项，已进 G2）。

- **「建楼」层高闸门 + 跳/攀爬衔接（第十八轮批次 B，**勿回退**）**：`check_window_movement` 里新增闸门 ——
  `walk_induced = (new_h != old_h and getattr(self,'is_moving',False) and is_floor_valid(old_floor))`，
  成立则先试 `_start_climb_transition`；**上楼够不着 ⇒ 保持原楼层**（不许退回"静默提升"，那就是缺口 G3 本身），
  **下楼够不着 ⇒ 服从重力**（要求⑭）。**入口只用既有属性** → 历史轻量桩（无 `is_moving`）仍走被动路径
  （这是 21 套件全 IDENTICAL 的原因，别为了"更准"去加新属性）。
  ① **跳还是爬 = 单点选型**：`start_jump` 按 `_jump_kind_for_span(|Δplatform_height|)` 决定，`≤CLIMB_SPAN_JUMP_MAX=5`
     用 `jump` 家族、更大用 `climb_*`；结果存 `_jump_anim_override`，**`handle_jump` 每帧必须先读它**
     （否则第二帧被 `jump` 顶掉＝白切）。两条入口共用这一份判据，别在调用方各写一份。
  ② **落点"先让开再吸附"**（用户："要预留一定距离哦，别看着和垂直起跳一样"）：`_climb_hdir`（优先沿用走路朝向）
     → `cur ± CLIMB_HORIZONTAL_RUN(90)` 各取候选 → `_climb_probe_landing` 吸附进**可见区域** + 位移上限
     `CLIMB_LANDING_MAX_TRAVEL(320)` → `_climb_landing` 两方向择优（`CLIMB_MIN_RESERVE=24`）。
  ③ **摔扁门槛**：唯一入口 `_should_splat_on_landing`（两个落点共用）= 速度 >150 **且** 落差
     ≥ `FALL_SPLAT_MIN_DROP=10`（两层）；"主动下来"那一半天然不成立（走路走跳/爬链路，不进坠落状态机）。
     `_fall_from_height` 进入坠落时记一次；`_landing_drop_height` **必须夹到 ≥0**（落差是物理量不是有向坐标差）。
  ④ **不做"逐层小跳"（本轮最重要的取舍，勿凭直觉改回去）**：用户说过"不能一次性跳上跨度很高的楼层……只能相邻"，
     但**在这套几何下逐层会卡死** —— 楼层名次＝z 序，宠物被判到第 N 层正因它的位置落在**最前面**那块板的
     **可见区域**里，而那正是第 N−1/N−2 层**被挡住**的地方，中间层在该位置**没有可见区域** → 逐层第一步就
     吸附失败 → 每步 False → **宠物永远上不去**（"进不去窗口"，比改前更糟）。故跨层**换素材不换落点**
     （攀爬素材 + 320px 位移上限）。前提已被 `第十八轮` I 组断言钉住（I1 下层在同一位置无可见区域）。
  ⑤ **素材**：`climb_right`(5，`spr_ralsei_climb_1_*`) / `climb_left`(5，**上面那组的水平镜像**，真落盘) /
     `climb_front`(6，`spr_ralsei_climb_0_degrees_*`)；**没有朝后的**（"那样也用不上"）。三组同时进
     `_builtin_animation_mapping` 与 `animations.json`。回落后方：素材不在库 → `_climb_animation_name` 返回 None
     → 回落 `jump` 家族（**不切灰块**）。新增后 `frame_container_size` 仍 `(222,110)`（两处来源都是）——
     没碰 H4/H5 那条"用户可见画布"红线。回归锁 `第十八轮/verify_round18_climb.py`（53 项，已进 G2）。
  素材镜像的生成/校验脚本 `第十八轮/make_climb_left_assets.py`（幂等；**逐像素断言镜像关系** ——
  只比尺寸/文件名都拦不住"原样复制"）。
  ⚠️ **【2026-09-17 二次复核：推翻"推翻"】—— `climb_right = climb_1_*` / `climb_front = climb_0_degrees_*`
  是用户当年的原话口径，配置本来就是对的，不许再改。**
  权威证据 = 用户 `AskUserQuestion` 答复原文（会话 jsonl）："`spr_ralsei_climb_1_0~4.png` 这是朝向右边的素材；
  `spr_ralsei_climb_0_degrees_0~5.png` 这是朝向前面的素材；然后相反方向的你就给他翻转一下就好，
  没有朝后面的因为那样也用不上"。逐条对得上三组注册；运行时渲染（`第十八轮/_evidence/climb_frames_preview.png`：
  侧视朝右 / 镜像朝左 / 正面朝前，`missing_or_null=无`、`frame_container_size=(222,110)`）+
  `round18_climb` G2 套件 **53 PASS / 0 FAIL / IDENTICAL** 双证。
  **上一轮那条"我挑错了组、朝向本来是六组"的结论已作废** —— 它的错在拿"磁盘上还有 45°/90°/poses/climb_2~6 等
  冗余变体"去推翻"用户明确指名的两组"，把**冗余**当成了**指认错误**；"`0_degrees` 是背面/无脸"的描述也与
  转角命名（0°=正面）冲突。完整留痕：`架构改造-H4H5/_evidence/climb_注册核对_2026-09-17.md`。
  未注册的 6 个变体（`climb_2~6` / `45_degrees` / `90_degrees` / `poses` / `poses_alt` / 基础 `climb`）清单已列在
  该文件 §5 —— **用户若要的是它们，给个行号即可改**，但**不得再自作主张推翻用户指认**。
  哈希结论仍然有效的部分：`climb_0_degrees`(6) 与基础 `climb`(4) 同图；`climb_90_degrees`(6) = `climb_1~6` 各第 0 帧；
  `climb_left` ⇔ `climb_1` 逐帧严格镜像（唯一一对）。
## 「建楼」要求：已核实实现面 + 6 个缺口（第十六轮行为级复检，**勿凭直觉"重做"**）
- 已实现（断言 A1–B4）：每窗一层且 `floor['rect']==window['rect']`；`platform_height=(n−i)×5`（最前最高、桌面 0）；
  可见面积 < `MIN_FLOOR_VISIBLE_AREA`(1600px²) 即不成楼层**且不再遮挡更低的窗口**；`floor_visible_contains` 只认可见区域；
  上跳落点过 `nearest_visible_point`（推远 >200px 放弃）；`adjacent_lower_floor` 显式逐层；`_apply_pet_z_order` 插位；
  `WindowStaysOnTopHint` 已移除。
- **缺口（4 批次；A、B 已修完，C/D 未动）**：
  1. ~~**⑬ 生气动画 ≥5s 不成立**~~ **→ 第十七轮已修**，见上一条。
  2. ~~**⑧/⑩ 下方还有窗口时不坠落**（要求原文第 30 行的例子）~~ **→ 第十七轮已修**（层高判据）。
  3. ~~**⑤ 走路没有层高闸门**：站桌面走进窗口可见区域被**直接提升**到该层，不跳不摔~~ **→ 第十八轮已修**
     （层高闸门 + 跳/攀爬衔接，见上一条）；⚠️ 与之配套的"跨层是否逐层"见第十八轮条目 ④（**判定不可行**）。
  4. **⑨ 偏差（保留）**：位移 >400px 不跟随改失足（为最大化/还原）；要求字面是"必须跟着"。
  5. **`climb_to_top_window()` 仍走裸窗口**（挑最前面那个窗口，按定义不会被盖，暂不出问题）。
  6. **①③ 偏差（保留）**：窗口"只被遮住一部分但可见 <1600px²"直接不成楼层，要求字面只说"完全盖住"才不存在。
- 另：⑩ 的"立刻" = 1 秒节拍（`floor_check_interval`）→ 最长 1s 延迟，登记为已知。
- **第十六轮那份只读复检套件（`第十六轮/verify_build_req_audit.py`，40 项）是"修复前"的历史快照**：
  F 组 `[GAP]` 断言故意断言缺陷，A 批次修完后已翻转为 FAIL，**这是设计如此、不是回归**；
  它**不在 G2 清单里**（文件头已加注）。"修复后必须成立"的行为由 `第十七轮/verify_round17_build_fall.py` 锁住。

## 验证脚本教训（第八轮）
- **别用 `"字面量" in 源码` 做源码级断言**（注释/文档串会误命中）。用 `code_only()`（tokenize 剥 COMMENT/STRING）；
  但 **`tokenize` 不产空白 token** → 拼回必须 `' '.join`（`''.join` 会把 `import heapq` 粘成 `importheapq`）；
  比较两侧先 `re.sub(r'\s+','',...)`，加 X0 自检。找**字符串字面量 needle** 要用 `code_no_comment()`。
- **防御性 `except` 必须配异常计数**（一轮里 `paths()` 收到 list 抛错被静默吞 → "多跳永远返回空"）。
- **回归锁必须有鉴别力**：断言两侧若可能同值就等于没测（第十二轮 C2 环境把中转站钉成数据根 + 关设备，
  正确/错误路径同值 → 间接环漏网）。写断言前先问"坏了这行还会是 True 吗"。
- 顺序断言限定在**目标函数体内**；行为级断言优先；`SimpleNamespace` 桩要 `types.MethodType` 绑实例方法。
- **解析算法必须有"算法无关"的独立 oracle 交叉验证**（第十三轮）：`visible_subrects`（矩形相减）的"两两不重叠 +
  面积和正确"用**采样网格**（10px 打点逐点判可见、数点数）反向核对。两者一解析一暴力，对得上才可信 ——
  否则就是在**验自己手算错的期望值**（本轮我确实把两处重叠遮挡的期望面积重复扣了）。
  纯几何/纯计数类断言尤其要这样：**先让"独立方法"同意，再谈结论。**
- **桩必须跟着真实方法面走**：第十三轮 `handle_gravity_fall` 新增 `_apply_pet_z_order()` 调用 →
  `第八轮/PetStub` 缺方法直接 AttributeError（`round8_floor` 16→11）；**第十四轮同一坑又踩一次**
  （缺 `_sync_window_cache_from_floor` → AttributeError；补上后 `start_falling` 又因多了 `reason` → TypeError）；
  **第十五轮第 3 次**（`check_window_movement` 要调 `is_floor_valid` → `第八轮/FakeFloorManager` 缺它）。
  **改了被测对象的对外调用面，就要同步扫一遍所有桩**；顺手把新要求**加严进老套件**（W6→+W6b）。
  好消息：补桩后 `round8_floor` 输出**一字未变**（IDENTICAL）—— 说明补桩没有改变任何既有断言的结论，
  这正是"桩只是方法面的镜像"的证明。
- **别把断言写在死代码上**（第十五轮）：第十四轮 G5b 断的是 `update_floor` 体里的
  `start_falling(reason='floor_removed')` 字符串 —— 而 `update_floor` **从来没被调用过**，
  那条断言永远为真、什么也没保护。**断言死代码 ≡ 断言一个常量。**
  写源码级断言前先问："这段代码真的会被执行吗？"；本轮已把它改成锁"死代码不该长回来"。
- **大块删除用"行级手术 + 断言 + 编译校验"，不要手工重排版**：删 154/67 行这种规模，
  逐行 `old_string` 匹配一次打错就白干。脚本按行号定位、**断言落点正确**
  （同名 `get_all_visible_windows()` 全文件 10 处 → 必须确认取到 `check_nearby_windows` 那一处、
  且上溯最近的 `def` 就是它），删完 `py_compile` + 跑 G2。注意 **main.py 是 CRLF、floor_manager 是 LF** →
  一律 `newline=''` 读写、匹配时 `rstrip('\r')`，只做整行增删（见 `第十五轮/_evidence/round15_surgery_log.txt`）。
- **"函数写对了"不等于"产品用上了"——本项目最贵的坑（已第 3 次）**：第八轮 z 序两函数、
  第十三轮三个可见区域判定（`get_jump_destinations`/`find_support_below`/`is_on_floor_edge`）
  都是**零调用死代码**，套件测的是"函数对不对"，**没有一条断言"产品调没调用"**。
  第十三轮换判据后真机没生效，根因就在这。**写断言的铁律**：凡是"改判据"的轮次，
  必须加**行为级接线断言** —— 用**故意缺掉回落依赖**的 stub（第十四轮 A2/A2c：stub 不给
  `desktop_interaction`）驱动**真实的**产品入口函数，一旦代码偷回旧路 → 立刻 `AttributeError`。
  **"改了 A 却没接线到 B" 要当独立交付项来验，不能算在"A 的套件过了"里。**
- **它的镜像问题：没改也没人调用的（第十五轮）**：死代码不只是"占地方" ——
  `check_nearby_windows` 尾部那段是**第十三轮口径错误的活样本**，留着就等于把 bug 冻结在原地等人复活。
  本轮定了处置口径：**要么接线、要么删**，不留第三种状态。
  查死代码最省事的两个来源：`第五轮/_evidence/_deadrefs_filtered_view.txt`（零引用方法清单，
  `is_floor_valid`/`update_floor` 都在里面）+ H4/H5 排期方案 §G1。
- **桩必须跟着真实方法面走（第 4 次，第十七轮）**：`handle_fall` 里调了一个**新的实例方法** →
  `round6_verify`（39 项掉到 20）与 `round8_fling` **当场 `AttributeError` 崩在半路**（exit=1 但 FAIL=0，
  症状是"套件自己炸了"而不是断言失败）。**修法不是给每个桩补方法，而是把这类"被判据调用的纯函数"放到模块级** ——
  模块级函数由 `main` 的全局命名空间解析，桩不需要知道任何事（`_FALL_VELOCITY_ATTRS` 当初就是这么落的）。
- **断言要断行为，不要断赋值（第十七轮）**：`round14` 的 G1 断言 `_p_user.max_fall_duration >= 5.0`
  静静绿了一年多，而"生气动画至少 5s"**从未成立**（那条赋值是死参数）。识别信号：
  **断言里的量在产品里没有任何行为依赖它**。替代写法：把状态机真的推进（第十七轮 B3 推 100 帧 ×0.05s，
  量出进入晕乎的时刻 = 5.0 / 3.0 / 1.0s）。**能推进状态机量出来的，就别只检查一行赋值。**
- **"测试自己坏了"比"测试没写"更危险（第十八轮，最值钱的一条）**：桩**形状**写错（扁平的
  `SimpleNamespace(sprites=...)`，而函数读的是 `pet.sprite_loader.sprites`）→ 函数**恒返回 None** →
  "素材不在库应返回 None"这条**负控制必然通过＝没测**（假绿）。它是被**配对的正控制**（"素材在库应返回名字"）
  红了才揪出来的。**铁律：正/负控制必须成对**；只留负控制时，"测试自己坏了"可以一直绿下去。
  另：**断言失败详情要能诊断** —— detail 写 `None` 时红了只有 `<<< None`，分不清"名字错"还是"桩错"；
  改成打印实际返回值 + 库里的键，一眼定位。**断言失败要把现场交出来。**
- **源码级 needle 含字符串字面量 → 必须走 `func_lit`（第十八轮，第 4 次踩；2026-09-18 第 5 次）**：`func_code` 把 STRING token
  一起剥掉，`getattr(self,'_jump_anim_override',None)` 这个 needle 里的属性名是字符串字面量 → 剥完变成
  `getattr(self,,None)` → **永远搜不到 → 假红**。定式：**含引号的 needle 用 `func_lit`（只剥注释），
  再用一条**不含引号**的 needle 在 `func_code` 上补一刀，两边互证**。
  本轮不再靠"记得"——加了 **X0 自检**把两个视图的语义钉住（`func_code` 搜不到字面量 / `func_lit` 搜得到 /
  两者都搜不到注释）：**工具的语义本身也要有断言**，否则它一变形，下面所有断言一起失真。
  **2026-09-18 人味套件首跑又栽在这上面（B3/B4/B6/B7/B12/F8 六条假红）**：新写的
  `code_no_comment()` 一定要配套留着，**凡 needle 里出现引号、`\n`、或任何会被 tokenize 当成 STRING 的片段，
  一律先走它**；`code_only_src` 只用于"纯标识符/语法结构"类 needle。
  另一个同源坑：**`\s+` 全抹会让 needle 里的空格消失** → needle 自己也不能带空格（写成 `recent=[cfor_r,...]`）。
- **离屏环境没有字体（第十八轮）**：Qt 打 `QFontDatabase: Cannot find font directory`，
  **`QPainter.drawText` 静默不画**（素材对照图第一版整行标题一个字都没有，连试两版才发现）。
  headless 出图**不能靠文字** → 改用色带 + 外部图例（同名 `.txt`）。同理：**别把"看不见"当成"画对了"**。
- **列表推导手滑多打一层（第十八轮）**：`[n for n in (... for n in n) if ...]` → `NameError: name 'n' is not defined`，
  报错点在推导式内部、traceback 只给行号，看不出是"手滑" → **先展平再筛**，别把嵌套推导写成一行。
- **证据必须 Python 自己写（第 2 次踩，见环境铁律 10）**：本轮第一遍跑套件用 `Out-File -Encoding utf8` 收
  PowerShell 管道里的 python stdout，读回来是"涓婃ゼ"这种乱码（能猜出 PASS/FAIL 但**不能当证据**）。
  项目里早有现成套路（`第十七轮/run_round17.py` 的"runpy + StringIO + 自己写文件"）→
  **先找项目里已有的工具/套路，再动手写**，别第 N 次重造并重踩。

## 历轮（细节见 `.workbuddy/memory/<日期>.md` 与对应报告）
- 7–8：README 路径 import 修复；#10 ▼ 抖动 `024b6aa` / #11 坠落误判 `cc9471d` / #12 斜抛+空中二次抓+卡动画
  `654da19` / #13 特殊动画治理。待办 #14 G2 断言、#15 对话全 AI 接管 + 原作风格聊天框（**不直接改 `dialogue_ui.py`**）
  + 多人对话预留 + "建楼"楼层 + bilibili 窗口摆放（PPT 类软件打开则不开）。
- 9 `conversation_focus.py` + 20s 自动隐藏 + 自主开口不打断 + 拟人记忆 `memory_store.py`（105/0，G2 13/360）。
- 10 `e9f6b00` `memory_graph.py`（98/0，G2 14/459）。11 `e8795da`/`6ef6fe2` 抽词剪刀 + 拓扑实测择优 clique（64/0，G2 15/523）。
- 12 `289023c` + **补丁** `d2f36c6`/`55e4a4c`：jieba 软依赖 + `data_store.py` 收口 7 类产物；补丁 **E 盘真机确认通过**
  （日志/记忆/缓存全落 `E:\RalseiMemory`，中转站为空）+ 修间接初始化环（`lazy_log`）+ 迁移落选留档。
  58/0，G2 16 套件 584 PASS/全 IDENTICAL。局限：日志跨期只留档不追加；程序目录历史开发日志未删。
  **原"默认启动被沙箱确定性拦住"的结论已在第十三轮推翻并关闭**（见环境铁律 9）。
- 13 `代码质量复审报告_2026-09-16_第十三轮.md`：**「建楼」遮挡判定 + 窗口层数 + 渲染层序（Windows 原生口径）**。
  三处硬伤 = ① `rect.contains(rect)` 把"被遮 90%"当整块楼板 ② `get_current_floor` 不看遮挡 ③ **`WindowStaysOnTopHint`
  强制置顶让遮挡从渲染层就失效**（最要紧，且 `get_insert_after_hwnd`/`set_window_behind` 本是零调用死代码，已接活）。
  顺带：`_is_writable_dir` 零副作用快路径（修 G2 自伤 + **默认启动现已能在沙箱跑起来**）、`save_baseline` 合并模式、
  DPI 量纲陷阱定论。71/0，G2 **17 套件 655 PASS**/全 IDENTICAL。真机证据 `第十三轮/_evidence/`。
  **下一步**：让用户在真机肉眼确认"宠物会被前台窗口盖住"（沙箱内透明非置顶窗被遮挡时鼠标事件打不到，只能离屏断言）。
- 14 `41ffecd`（批次一 上下动/接线）+ `9960e89`（批次二 落地/生气动画）+ `f1f8079`（补交报告）：
  **把第十三轮"写对没接线"的楼层判定接进产品路径**。三处症状 → 三处收口：① 跳落点过可见区域门
  ② 下跳显式取相邻层（不穿透）③ `current_window` 降级派生缓存（消第二真源）。落地当场结算 + z 序 +
  `land` 动画；关窗 → `fall_mad` ≥5s。41/0，G2 **18 套件 697 PASS**/全 IDENTICAL。报告
  `代码质量复审报告_2026-09-16_第十四轮.md`；证据 `第十四轮/_evidence/`（编码 0 损坏 0 告警）。
  **遗留**：① 真机肉眼确认上下动/落地（只能用户做）② `check_nearby_windows` 尾部旧裸矩形兜底段仍留
  （只在"零桌面窗口"时走到，建议下轮清理）③ `is_on_floor_edge`/`find_support_below` **仍零调用**（要么接活要么删）。
- 15 `1b279d3`：**建楼死代码清干净 + 一个被错判的坠落起因**。兑现第十四轮 §八 两条待办并扩大：
  删 `check_nearby_windows` 尾部裸矩形段（154 行）/ `update_floor`（67 行）/ `find_support_below` /
  `is_on_floor_edge`；接线 `is_floor_valid` 修掉"宠物自己走出楼板也播生气动画"（与要求相反的真 bug）。
  `main.py` 9373→9172 行（+40/−241）。30/0，G2 **19 套件 728 PASS**/全 IDENTICAL（round13 71→72、
  round14 文案变更，均为有意）；另跑真机启动路径冒烟（真 `RalseiPet()`，四条链全过）。
  报告 `代码质量复审报告_2026-09-17_第十五轮.md`；证据 `第十五轮/_evidence/`（8 份，编码 0 损坏 0 告警）。
  **遗留**：① 真机肉眼确认"走到边缘掉下去不再生气 / 关窗仍生气"② `climb_to_top_window()` 仍走裸窗口路径
  （故意没动：它挑的是最前面那个窗口，按定义不会被盖住）③ `update_floor` 独有的 `found_window` 情绪
  当前本就不可达、本轮未恢复 ④ 程序目录三个本地 `.bak`/`.backup_*` 备份文件未删（等用户点头）。
  **push 备注**：本轮 push 期间沙箱代理（57186）对 github 一度持续 502（`ls-remote` 连试多次不通），
  但两次 push 自报成功、随后代理恢复时 `ls-remote` 复核 **远端 == 本地 == `cc8c7c5`** → 已闭环。
  **代理抖动时不要只看退出码，但也要等它恢复后补一次 `ls-remote`**。

- 16 `建楼要求复检与缺口计划_2026-09-17.md`：**「建楼」要求行为级复检（只读，未改产品代码）**。
  用户："复检一下到底实没实现那些要求，没有的话那就把它也加到计划里就好"。13 条要求 + 3 铁律 + 2 动画要求
  里 **7 条已实现**（①②③④⑥⑦⑫）、**5 条部分**（⑤⑧⑨⑩⑪，缺口全在下落路径）、**2 条动画要求实际不成立**（⑬⑭）。
  复检新建 `第十六轮/verify_build_req_audit.py`（40 项断言，F 组**故意断言当前缺陷**、名字带 `[GAP]`，
  修好后必须翻转 → 逐条列出 6 缺口；**不入 G2**，与第十三轮 `probe_*` 同规格）。40/0；G2 **19 套件 728 PASS**
  /全 IDENTICAL（没动产品代码 → 与基线逐字节一致）。**更正了第十三轮"13 条没有漏项"的结论**。
  计划 4 批次：A＝G2+G1 一起修"下落路径"（含把 `splat_mad` 接活）；B＝G3 层高闸门（待用户拍板）；C＝G5 收编；
  D＝三条有意偏差只登记。**下一步：等用户对批次 B 拍板 + 授权开做批次 A。**

- 17 `代码质量复审报告_2026-09-17_第十七轮.md`：**「建楼」缺口批次 A —— 把"下落路径"修对（G2 判据 + G1 生气时长）**。
  用户："好的，那接下来继续按照原计划进行吧"；随后澄清 **"原计划"指的是 H4/H5 上帝类拆分**，
  但允许先把手上这批建楼缺口做完 → 所以本轮 = 批次 A，做完回 H4/H5。
  两条缺口都修完：**G2** 触发坠落改**层高比较**（关窗后下方还有窗口也要掉，即要求第30行的原例）；
  **G1** 生气动画改由起因 `_fall_reason` **纯派生**（模块级 `_fall_splat_hold(pet)` / `_splat_animation_name(pet)`），
  落地不再被普通 `splat` 顶掉，`splat_mad` 接活。自检 18/0；G2 **20 套件 746 PASS / 0 FAIL / 全 IDENTICAL**
  （唯一有意变更：round14 G1 断言改名"派生时长" —— 旧断言 `max_fall_duration >= 5.0` 断的是**死参数**，
  一直是 PASS 却什么也没锁住）。
  **教训**：①「判据写对了 ≠ 判据被问到」（`is_floor_valid` 被上游门条件挡住 → 调用计数 0）；
  ② 别把时长再存一份实例属性（双真源）→ 改纯派生；③ **判定函数必须放模块级**（第一次写成实例方法，
  `round6_verify` / `round8_fling` 的轻量桩当场 AttributeError 崩在半路）；④ **断言要断行为不要断赋值**
  （round14 那条绿了一年多而要求从未成立；新 B3 直接把阶段机推进 100 帧量出停留 5.0s/3.0s/1.0s）。
  另外给第十六轮只读复检套件加注"历史快照：修复后 GAP 断言必然翻转，这是设计如此不是回归"。

- 18 `4eae2d8` `代码质量复审报告_2026-09-17_第十八轮.md`：**「建楼」缺口批次 B —— G3 层高闸门 + 换层全接跳/攀爬**。
  用户拍板："楼层层高变换必须靠跳衔接"/"走进更低楼层也一样，**下楼也用跳别用掉落**"/"**要预留一定距离**，
  别看着和垂直起跳一样"/"跨**度低的时候跳，跨度高的时候爬**"/"摔扁只在**层数比较高且掉下来（非主动）**时触发"。
  改法：闸门（`walk_induced`，只用既有属性 `is_moving`+`is_floor_valid`）→ `_start_climb_transition`
  （`_climb_hdir`/`_climb_probe_landing`/`_climb_landing`）；**跳还是爬在 `start_jump` 单点选型**
  （`_jump_kind_for_span`，存 `_jump_anim_override`，`handle_jump` 每帧优先读）；摔扁收敛成
  `_should_splat_on_landing`（速度>150 **且** 落差 ≥`FALL_SPLAT_MIN_DROP=10`）；三组攀爬素材登记两张表
  （`climb_left` = `climb_right` 的**水平镜像**，一次性生成真落盘）。自检 **53/0**；
  G2 **21 套件 799 PASS / 0 FAIL / 全 IDENTICAL**（新增 `round18_climb`；4 处有意变更**全是组数计数行**：
  组 109→112、载入 489→493、帧 1461→1482、样本 501→505、导出 21319→22156 字节；`frame_container_size` 仍 `(222,110)`）。
  真机跑 30s **0 ERROR/0 WARNING**；另出**素材实渲染图**（`_evidence/climb_frames_preview.png`，非灰块占位）。
  **取舍**：用户"只能相邻"做了**否决性论证**（逐层小跳会因中间层被遮挡而卡死，I 组断言钉住前提）。
  **教训**：① 桩形状错 → 负控制**假绿**（正/负控制必须成对）；② 含字符串 needle 走 `func_lit` + **X0 工具自检**
  （第 4 次踩）；③ 失败详情要能诊断（`detail=None` 等于没说）；④ 离屏**没字体**、`drawText` 静默不画；
  ⑤ 证据必须 Python 自己写（第 2 次踩 PS 捕获毁中文）；⑥ 列表推导别手滑多打一层。

- 18（并行线）`ee39227`：**对话 AI「人味」改造（L1 全做）** —— 与"建楼批次 B"同轮号，但**另一条线**。
  用户："他这个AI没有活人味，你给看看怎么训练一下" → 拍板 **L1 全做**；口径
  **"保存性能的前提下既要有 Deltarune 世界观，又要让他们知道现在自己生活在电脑桌面上"**。
  交付：`assets/ralsei_persona.md`（新增）+ `assets/ralsei.modelfile` + `ralsei:v2`
  + `main.py` 接线重写与 4 个新方法 + `dialogue_ui` 关键词收紧 + 新 G2 套件 `persona_chat`。
  **端到端实测：完重 0 / 违禁套话 0 / markdown 残留 0**；G2 **22 套件 857 PASS 全 IDENTICAL**。
  **本轮最值钱的两次自我推翻**（详见上方「对话 AI 人味改造」条）：示范不能删、判退只能看 recent。
  **教训**：① `/v1` 忽略 `num_ctx`/`repeat_penalty` → 参数必须落 Modelfile；
  ② persona 是 prompt 不是文档；③ 护栏要在"复刻链路的 e2e"里验收（直接调护栏会得出"成功率 0%"的假象）；
  ④ 探针判据里的白名单写窄了会把"想要的结巴（我、我）"误报成缺陷 → **先读原始文本再信计数**；
  ⑤ **测试桩漂移 ≠ 真回归**：`round6_verify` 4 条挂是桩没绑新方法，且 `g2_after.txt` 是**修复前**的旧数据
  —— 动手 debug 前**先看产物时间戳**。

## H4/H5 架构改造（用户排期"单独做"）
- 基线 `code-quality-audit/架构改造-H4H5/`（只读，**勿重测**）：`main.py` 8794 行/`RalseiPet` 186 方法；`self` 属性
  438、106 个被 ≥3 处写；`animation_mapping` 109 组/1106 PNG/743 未引用/缺失 0；动画名字面量 24+12 f-string。
- **两坑**：① 不能用 `scan_and_group_assets` 全量替代硬编码（会重现灰块）；② 不能停用自动扫描
  （`frame_container_size` (222,110)→(136,71)，用户可见）。**H5 契约**：`comment` 必为非空字符串数组；未知字段只
  warning → 须锁"入库无未知键"；自动扫描不可降级。
- **S1/S2/S3 全完成**（S2 `b099e4c` 外化 `assets/animations.json` schema=1/109 组/377 帧，AST 单向导出 +
  JSON 优先异常回落；S3 `94e4902` 别名/legacy 显式化）。未修：`change_animation` 长→短回退 vs
  `update_animation` 内嵌块只取前两段。下一步：真机取真实未命中清单。

### 闸门状态（2026-09-17 **已重扫 + 已裁定**）
- **G2 ✅**（`code-quality-audit/regress/run_all.py`，**2026-09-18 起 23 套件 / 925 PASS / 全 IDENTICAL**
  —— 新增 `persona_chat`(58) 与 `s8_stream`(68)）、**G3 ✅**、**G4 ✅**（H5 S1–S3）
- **G1 ✗ → 改为"每项 PR 内做该项专属零引用筛查"**（方案 §8 决策 2 已按"技术细节我拍板"落定，
  **不再整体清 185 项**）。新工具 `架构改造-H4H5/scan_zero_refs.py`（**AST 计名字引用点，不做字符串匹配**，
  防注释/文档串误命中）→ `_evidence/zero_refs.txt`。
- **G1 重扫结论（2026-09-17）**：① 排期点名的 **W1-5（17 个办公 `check_*`）已不复存在** —— 第六轮删除，
  留痕 `main.py:5002-5003`，`check_browser_windows`/`check_ppt_windows`/`check_excel_table_needs`
  **全项目 AST 零引用**确认，等价能力在 `modules/desktop_interaction.py` → **W1-5 从 Wave 1 划掉**；
  ② 新查出 1 个全项目零引用方法 `create_person_name_table`（4057，56 行）。
- **当前基线（2026-09-17 复扫，勿重测）**：`main.py` **9588 行**；`RalseiPet` **191 方法 / 方法体 8772 行**。
  工具 `架构改造-H4H5/scan_method_index.py`（ast）→ `_evidence/method_index.{txt,json}`（含起止行/行数/Wave 归属）。

⚠️ **2026-09-18 更新**：人味改造（`ee39227`）在 `RalseiPet` 里**新增 4 个方法**
（`_build_persona_prompt` / `_ai_chat_options` / `_clean_ai_reply` / `_is_repeat_of_recent`）；
S8 流式（`761b7e0`）又加了 `_emit_delta` / `_on_api_delta` / `_ai_stream_enabled` / `_sanitize_partial_reply`
等与 `_md_strip_re` / `_role_marker_re`（类方法）。
`main.py` 实测 **9952 行 / 530781 字节**（Python 计数，2026-09-18 核），
**“9588 行”与下面 Wave 1 的行号区间全部失效**。
开工前**必须重跑 `scan_method_index.py`**，不要照抄 6186–6449 这类旧区间。

### Wave 1 施工顺序（已定，行号为本轮实测）
**W1-3 → W1-4 → W1-1 → W1-2 → W1-6**（自包含度优先）。W1-3 游戏 = `GamesController`
（`main.py` **6186–6449**，7 方法 / 258 行，**块内闭合、零互写**，入口仅 `dialogue_ui.py:1445/1449/1453`）
—— **第一项**。W1-4 视频 `main.py` 4427–4751（8 方法 / 289 行，分组器曾漏标中间 3 个 `_*video*` 私有方法）；
W1-1 施法 8748–9040（4 方法 / 290 行）；W1-2 躲猫猫 9050–9402（12 方法 / 342 行；`_hide_ralsei` 445 是
**托盘隐藏**属别处，勿并入）；W1-6 文件表格 ~370 行（**先处置死代码**）。**Wave 3 明确不在本次范围。**


### G3 属性归属表（交付物 + 口径铁律）
- 交付物 `H4-G3_属性归属表_2026-09-17.md`（**由脚本渲染，勿手改数字**）；工具
  `架构改造-H4H5/scan_attribute_ownership.py`（只读 AST，自检 X1–X7）+ `make_g3_report.py`（渲染器）；
  证据 `_evidence/attribute_ownership.{txt,json}`。提交 `cca9666` + `5404b3f`（日期更正 rename）。
- 数字：名字全景 **458 = 真属性 286 + `self.foo()` 调用位 172**（474 个调用点）；**16 分区 / 未归类 0**；
  真耦合点 **111** 条（"写出现次数≥3"111 ／ "写方法数≥3"93）；**必备接口 138 条**（= 反向 import 的唯一诱因清单）；
  **Wave 1 内部互写仅 4 条**（W1-2 `_hide_stage`/`_hide_obstacles`/`_hide_folder_path` ← W1-1，
  W1-1 `_spell_auto_suspended` ← W1-2）→ Wave 1 唯一真阻塞项。
- **口径铁律**：统计 `self.<name>` 必须区分**赋值 / 读取 / 调用位** —— `self.foo()` 是**调用不是读**；
  "从未被赋值 且（被调用过 或 是本类直接方法）"判为方法 / Qt 内置，**整条移出属性表并单独成段**（禁止静默丢弃）。
  v1 不区分 → 172 个方法名灌进属性表、`UNCLASSIFIED` 300 条大半是噪声，**表看着齐全其实不可用**。
- **Wave 1 施工口径（已定案）**：**只搬方法、不搬状态**（转发壳 + 宿主 API）→ 新模块不反向 `import main`、
  G2 基线逐字节一致。属性留在宿主 ≠ 阻塞；真正的阻塞只有"两个待拆模块互相写同一属性"。
- **顺带查出（交 G1）**：悬空读 3 —— `_cached_scale_factor`（main.py:7675/7835，**缓存永远取默认 2.0**）、
  `ai_thread`（main.py:8630，**8630–8632 收尾逻辑整段死代码**）、`is_being_thrown`（main.py:7562，恒 False）；
  另有死参数候选 **59** 个（赋过值但从无读取，只列不判）。
- **长表交付物铁律**：扫描器出证据 json + 渲染器出报告 md，**禁止手抄数字**（本轮 249 行）；
  自检要在"被删条目仍可访问的快照"上做断言（X5 初版查已删字典 → `KeyError`）。
- **日期铁律**：注入的 `current_time` **可能过期**（本轮差 1 天，09-16 vs 实际 09-17）→
  日期一律取系统时间（`Get-Date` / `git log --format=%ci` / `time.strftime`），**不许写死**。

### 素材分组补漏（H5 §4.1，**只读报告器，不许自动接管配置**）
- 工具 `架构改造-H4H5/scan_asset_groups.py`（自检 X1–X7）；证据 `_evidence/asset_groups.{txt,json}`；
  图库 `素材分组总览_2026-09-17.html`（**已 gitignore**，重生成一条命令）。提交 `1689e1f`。
- **基线（2026-09-17，勿重测）**：`deltarune_ralsei/*.png` **1111**（0.85 MB）；命名分组 **380**；家族 **19**；
  `animations.json` **112 组 / 379 帧**；**已登记 82 / 部分引用 20 / 未引用 278**；配置引用但磁盘缺失 **0**。
  另两个素材目录：`ralsei_face`（50 PNG + 1 txt，要求 §11 的 50 个 face 状态**在这里**，不在 `deltarune_ralsei`）、
  `textbox`（3 PNG + 1 SVG + 1 README）。**扫描器只覆盖 `deltarune_ralsei`。**
- **命名归组口径**：`spr_` 前缀去掉 → 去 `.png` → **末段纯数字 ⇒ seq，其余是 base**；否则整段是 base、seq=None。
  故 `spr_ralsei_hurt.png` 与 `_hurt_0.png` 同组；`spr_ralsei_climb_1_0..4` ⇒ base `ralsei_climb_1`。
  **家族 = `base.split('_',1)[0]`**。**别名要展开**：`alias_of` 指向的是**组名**不是文件名，
  不展开会把复用组误判成"未引用"。
- **大而可复算的产物不入库**：1111 张共 0.85 MB ⇒ 图库 base64 全内联成单文件 1.44 MB，
  **不需要 http server**（绕开 file:// 被拦）；像素图要 `image-rendering: pixelated` + 棋盘底衬
  （PNG 有透明通道）；每卡勾选框 + 底部 textarea 自动汇总组名，用户圈完直接粘回来。
- **流程是三段**：① 分组+展示 ② 用户圈掉不需要的 ③ 对账要求文件查缺补漏。
  本轮只做 ①，**零回写 `animations.json`**（H5 §4.1 定性为"补漏报告器"）。
  已知线索：要求点名的 `teacup_ralsei_land_*` 磁盘上**没有**（磁盘只有 `teacup_ralsei`/`_tea`/`_tea2`）。
- **对照图工具** `架构改造-H4H5/make_asset_contact_sheet.py`（按命名分组放大铺开、带行号/帧号/登记状态）。
  **PIL 能直接 `ImageFont.truetype('C:\Windows\Fonts\msyh.ttc')` 拿到字体** —— 与"沙箱里 Qt
  `QFontDatabase` 没字体、`drawText` 静默不画"是两件事，别因为 Qt 那条就不在图上写字。

## 对话 AI 化现状（2026-09-17 调查，**待办 #15 未做，别写成做了**）
- 用户感受"还是很死板"，事实是**"AI 优先 + 规则旁路 + 内置兜底"混合体**，不是全 AI 接管。
- **三个死板来源**：① `dialogue_ui.py:1055` 先试 `handle_chat_commands`（约 50 条关键词→固定回复
  `1319-1497`），再 `handle_game_input:1062` / `handle_file_commands:1499-1593`，**命中即 return，
  AI 收不到**；自由闲聊是这条链走到底的最后一支（`1085` 起）。② AI 失败/关闭回落 `dialogue_system`
  （最大的写死池：问候 8 + 13 类模板各 8 + 约 44 话题×8 + 上下文模板，`dialogue_system.py:29-581`
  与 `663-1273`）；另有 `emotion_system.get_dialogue_for_emotion:1180`、`weather_system:40-65`、
  `desktop_interaction.get_special_file_reaction:2464`、`autonomous_agent:104-137`。
  ③ 事件台词 100% 规则：`main.py` 约 131 处 `add_dialogue`；点击/抚摸 `5250-5846`、
  摔落惊醒 `3271-3358`/`3717`、桌面反应 `3930`、陪看视频 `4626`（**已标 `TODO(#15)` @ `4637`**）。
- **已按"全权 AI"做对的一条，勿回退**：`start_autonomous_speech`（`main.py:5059`）内容只由 AI 生成，
  AI 不可用**保持沉默**（`5072-5074`）。
- **开关** `api.enabled`（`config.json:4`；代码默认 False `config_manager.py:57`，本机已 true，
  Ollama `ralsei`）。`HTTPLocalAI.chat` 是**同步 requests**（`api_client.py:174/279`），
  **严禁主线程调用**（`177-180`）→ 一律线程（`main.py:7200` / `ai_driver.py:358`）。
- **UI 打字机**：**原先**是"假打字机"（`stream: False` 先拿完整答复再逐字、固定 20s 隐藏 `163`、
  固定 540×180 `188`、上限 380 `274`）→ **S8 已改成真流式**（见上「S8 流式输出」条）；20s 隐藏/尺寸未动。
- **上下文不差（别说成无状态单轮）**：`main.py:7133` `_build_ai_context() + text`（时段/天气/心情/
  精力饥饿/偏好 `7202-7263`）+ 6 轮历史 `7136` + 话题锚 `7165` + `recall_text` `7176`。
  **但**：历史只 6 轮（缓冲 8 `dialogue_ui.py:347`）、**桌面观察不进 chat prompt**（只进
  `ai_driver.note_event` `main.py:4640`）、**`memory_graph.py` 在 `main.py` 零引用**（多跳联想没接进对话）。
- **未定项（勿猜）**：除三条显式 `return` 外，其余 `add_dialogue` 与 AI 回调**无统一串行化**，
  运行时顺序静态判不出。

### 人味根因实测（2026-09-18，报告 `Ralsei对话人味诊断与训练方案_2026-09-18.md`，提交 `bc49043`）
证据在 `code-quality-audit/人味诊断-2026-09-18/_evidence/`（`probe_ralsei.py` / `ab_ralsei.py`，均只读）。
1. **`ralsei:latest` = `qwen2.5:3b` 衍生**（3.1B / Q4_K_M / ctx 32768）；`/api/show.parameters` 为 **None**
   → temperature/top_p/repeat_penalty/**num_ctx 全走服务端默认**。
2. **决定性：App 自带 system 会「整体替换」Modelfile 的 SYSTEM（不是叠加）**。
   `prompt_eval_count`：不传 system=**1237**（2003 字角色圣经生效）／传 system=**41**。
   → **模型里那份角色设定从未生效过**（凶手 `main.py:7141-7158`）。**改这条的前景最大。**
3. **`num_ctx` 实测 ≈ 2048**（5400 字符长提示词 → `prompt_eval_count=2050`），角色设定本身占 1237
   → 6 轮历史 + 联想必被静默截断。**必须显式传 `num_ctx=8192`。**
4. **A/B 四组（同模型/同问题/同温度，只换提示词）**：现状 4 题里 3 题复读「你还好吗／要不要休息一下」
   —— **源头是现行 system 把口头禅写成了示例，3B 当模板抄**。2026-09-12 报告自己列的 5 条实测回复里
   已有 3 条带这句 → **上一轮"训练"埋的雷，勿再往 system 里堆示例口头禅**。
   只用模型自带设定会**把用户当 Kris 跑进剧情**（通篇绑 Kris/Susie/黑暗世界），不能直接用。
   temp 0.9 出全场最好的两条，但会**自问自答续写 + 跑旁白**（200 tokens 用满）→ 活度要配护栏，不是升温。
5. **更正上一轮记载**：`memory_graph` **已接进对话链路** —— `memory_system.py:1297` import `MemoryGraph`，
   `recall_text`（`memory_system.py:1481`）被 `main.py:7178` 调用。之前记的"零引用"只对 `main.py` 文件内成立。
6. **关键词硬拦截实测 34 条**（不是约 50 条），`dialogue_ui.py:1319-1475`，纯 `kw in raw` 无边界：
   `哭`/`游戏`/`状态`/`天气`/`精力`/`饿了吗` 等高危子串会把正经闲聊截胡。
7. 硬件（为"换 7B"决策）：**Intel Core Ultra 5 125H + Intel Arc 核显，无 NVIDIA 独显**，RAM 33.9 GB
   → 3B 的 ~2s 是 CPU/核显推理；7B 可行但预计 5~12s。
8. **状态：诊断 + L1 施工 + S8 流式都已完成**（用户拍板"L1 全做"、随后"继续按计划执行"）。
   施工记录见报告第九节（L1）与第十节（S8）；契约见下两条。
   **只剩 S7（131 处事件台词分批交 AI）顺延**（改动面大，单独一轮；须守第 13 条铁律：环境自动触发
   只能 `ai_driver.note_event()` 上报、**不得自行播动画**；短促罐头反应保持即时，长台词才交 AI）。

### 对话 AI 人味改造（第十八轮并行线，2026-09-18，提交 `ee39227`，**勿回退**）
报告 `Ralsei对话人味诊断与训练方案_2026-09-18.md`（第 9 节为施工记录）；
证据 `code-quality-audit/人味改造-2026-09-18/_evidence/`；**回归锁 `persona_chat`（58 项，已进 G2）**。
**它不联网、不调 Ollama** —— 模型质量天生不可复现，不进基线。

- **人设单一真源 = `ralsei_pet/assets/ralsei_persona.md`**（App 每次对话读它当 system 发过去）。
  **不要**只写进 Modelfile —— Ollama 用 messages 里的 system **整体替换** Modelfile 的 SYSTEM。
  **persona 文件是 prompt 不是文档**：里面不许出现 markdown（`**`/`#`/`>`），3B 会照学，
  而对话框是逐字打字机渲染 → 星号原样给用户看（实测输出过 `**听到也让我心里暖暖的**`）。
- **采样参数必须落 Modelfile**（`assets/ralsei.modelfile` → `ralsei:v2`）：
  **`/v1/chat/completions` 静默忽略 `num_ctx` 与 `repeat_penalty`**（顶层/options 都无效），
  只有原生 `/api/chat` 的 `options` 或 Modelfile 的 `PARAMETER` 生效。
  → **参数 A/B 必须走原生端点**，否则会得到"改了没区别"的假结论。
- **用户消息保持纯原话**，`_build_ai_context()`（`【此刻】…`）/话题锚/记忆召回一律挂 **system 尾部**。
  拼在用户消息前会被当成"用户说的话"并复述成回答。
- **输出护栏 `_clean_ai_reply(reply, recent=)`** 四步：markdown 剥除 → 自问自答续写截断 →
  **车轱辘话判退** → 超长截断。**判退后必须重采样一次**（温度 +0.1 封顶 1.0 + `_RETRY_NUDGE`），
  **不许直接丢弃** —— 交互链路 `dialogue_ui._on_ai_reply` 在 reply 为空时会 `_rule_reply()`
  回落内置台词，比照抄更出戏。
- **两条被实测推翻过的设计（别再改回去）**：
  ① **persona 的 few-shot 示范不能删** —— 删掉后 3B 口吻明显退化（"我明白你的心情了"这种禁令套话都出来了）。
     反证留档 `_evidence/behavior_check2_无示范对照.*`。
  ② **判退条件只能是"和自己最近说过的话（recent）重复"，不是"像 persona 示范句"** ——
     3B 对「我好喜欢你呀」会 3/3 稳定吐示范句；一律判退 → *判退→重采样→还是照抄→None→内置台词*。
     示范句第一次说没问题，出戏的是**同一句反复出现**。
     套件 `persona_chat` 留了 **C7/C8 防回退断言**（等于示范句 + recent 为空 → **必须放行**）。
- 判据两条互补：整体 `difflib` ≥ 0.82（抓改两三个字）**∪** 最长公共匹配块 ≥ 12 字
  （抓"整体 ratio 只有 0.74 但后半段原样搬"）。`recent` 由 `chat_with_ai` 从 history 抽 `role=='assistant'`。
- 交互对话与自主开口**共用同一套护栏**；`_on_reply` 对护栏本身有防御 try/except
  （护栏抛异常被宽 except 吞掉会把"已发起"误判 False → 第六轮 B2/B3/B7/B8 就这么挂过）。
- **关键词拦截收紧**（`dialogue_ui`）：软闲聊（天气/哭/游戏/状态/精力/唱歌…）要"指令式命中"
  （`_is_command_phrase`：去掉关键词后剩字 ≤ `CMD_EXTRA_ALLOWANCE=2`）才截胡；
  真正驱动动作的硬指令在 `_HARD_CMDS`，仍走子串。
- **已知局限**：偶发"滑字"（`诪、诪` 本应是 `诶、诶？！`，约 1/10）。**不要为它加启发式护栏或改采样参数** ——
  `repeat_penalty` 1.15/1.00 × `top_p` 0.92/0.90 各 3 次采样的探针里真滑字 0 次、1.00 组无改善。
  归入 3B 能力上限，由 L2（换底座）解决。
- 指标口径（复现时照这个算）：同题重复率 / 违禁套话率 / 格式残留率 / 判退率。
  本轮实测：9 次调用（重采样 2 次）→ 完全重复 0、违禁套话 0、markdown 残留 0。

### S8 流式输出（第十八轮并行线二，2026-09-18，提交 `761b7e0`，**勿回退**）
报告第十节为施工记录；证据 `code-quality-audit/人味改造-2026-09-18/_evidence/s8_*`；
**回归锁 `s8_stream`（68 项，已进 G2）**。**不打网络、不调 Ollama。**

- **`LocalAIBase.chat_stream` 是具体方法、不是 `abstractmethod`**（默认回落 `chat()` + 单分片回调）——
  否则 `LocalAIStub` 与用户 `register_provider()` 的实现被迫改造，App 一升级就崩在用户那边。锁 A1/A2。
- **`requests.iter_lines()` 必须显式 `chunk_size=1`**：默认按 512 字节攒批 → 首字 0.45s（吃掉近一半收益）；
  `chunk_size=1` / `resp.raw.readline()` 才是 0.23s（非流式首字节=全文 6.02s）。**这条是流式收益的一半，别省。**
- **流式只做"前缀安全"清洗**（剥 markdown / 截自问自答）；判退与超长截断**只留给收尾**
  `_clean_ai_reply`。两条规则**共用同一份定义**（`_md_strip_re()` / `_role_marker_re()` 类方法），
  否则规则漂移 = 字打出去又被改掉。一句话：**流式负责"看着像人话"，护栏负责"最终算数"**。
- **流式清洗不可能对所有文本前缀单调**：`1. `（等点号后空白）与 `主人：`（等冒号）这类规则必然让
  **已显示的 1~2 字符**被延后剥掉。**不要试着改规则消掉它**（试过"提前剥"会把 `1.5 倍` 误伤成 `5 倍`）；
  正解 = 调用方（`dialogue_ui.stream_delta`）检测"新结果不是已显示内容的前缀"→ **整段替换**。锁 C9/C11。
- **流式与"判退重采样"天然冲突**：判退发生在收完之后，被判退的半句**已经在屏幕上** →
  重采样前**必须先发 `None` 分片**（`_stream_reset()` 回「……」）把屏幕擦干净，否则新句粘在旧句后。
  且流式路径下 `_on_ai_reply` **不能**调 `_ai_thinking_off()`（它清 `typing_text` → 已显示内容一闪而逝再重打）。
  锁 B7/B13、D7/D8、D14。
- **UI 结构本来就不用改**：打字机 = `typing_text`（全文）+ `typing_index`（进度）+ QTimer 渲染
  `typing_text[:index]` → **只要让 `typing_text` 可追加**，`typing_index` 留原位，下一拍自然往新内容上打。
  新增状态位只有一个 `_streaming`（"队列暂时打完但消息还没收完"）。
- **`_ai_delta_gen` 世代号丢弃过期分片**；`_on_api_delta` **故意不清 sink**（清了会误杀新请求的接收端）。
  开关 `api.stream`（`config.json` / `config_manager.py`，**默认 True**，一键关闭）。
- **Qt 跨线程投递必须单独验**（本项目最贵的坑"写了 A 没接线到 B"）：A~D 组只测到函数级，
  而分片是*工作线程 emit → 主线程槽执行*，这条链断掉 → **流式一个字都不显示**。
  F 组用真 `QApplication` + `QObject` + 真 `pyqtSignal` + `processEvents()` 断言"按序投递 +
  丢弃过期世代 + reset 顺序严格保持"。**凡涉及跨线程信号，都要有这样一组真事件循环的断言。**
- 实测（4 问 e2e）：首字中位 **0.43s** / 最快 0.31s；完全重复 0；markdown 残渣 0；
  "屏幕最终 ≠ 护栏定稿" **0 例**。
- **教训 11–16（写断言相关）已并入上方「验证脚本教训」**：`func_src` 取错函数（基类/别的 `__init__`）、
  含字面量用 `code_no_comment` vs 结构性用 `code_only_src`、`code_only_src` 抹缩进后别忘中间的 `try:`、
  计数型断言绑实现细节（`persona_chat` B5 已改成"两处请求都走同一 `_ask` 助手"）。
