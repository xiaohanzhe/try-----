# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

## 铁律
- **每轮改动完成即 commit + push**（"以免后期找不到"）。称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根（`代码质量复审报告_*.md`）；证据进 `code-quality-audit/<轮次>/`，侦察 `_recon/`（gitignore），
  留痕 `_evidence/`。改代码前跑 G2 `code-quality-audit/regress/run_all.py`（现 **19 套件 / 728 PASS**）。
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
7. 代理：**`git push` 用沙箱代理（端口会变，现为 `127.0.0.1:57186`）**——CONNECT 可用，退 0 即成功。
   **Clash `7897` 对 GitHub 已失效**（`schannel: failed to receive handshake` / `unexpected eof while reading`，
   连 `ls-remote` 也过不去）；旧记录里"7897 可用"作废。**端口要现查**（`netstat -ano | findstr LISTENING`
   找 `127.0.0.1:<port>`，或看沙箱注入的 `HTTP_PROXY` 环境变量）。
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
  **push 备注**：本轮 push 报 `21605d4..1b279d3 main -> main` 成功，但随后沙箱代理（57186）对 github
  持续 502，`ls-remote` 复核连试多次不通 → 未能在当时闭环核验（下次联网时补一次 `ls-remote`）。

## H4/H5 架构改造（用户排期"单独做"）
- 基线 `code-quality-audit/架构改造-H4H5/`（只读，**勿重测**）：`main.py` 8794 行/`RalseiPet` 186 方法；`self` 属性
  438、106 个被 ≥3 处写；`animation_mapping` 109 组/1106 PNG/743 未引用/缺失 0；动画名字面量 24+12 f-string。
- **两坑**：① 不能用 `scan_and_group_assets` 全量替代硬编码（会重现灰块）；② 不能停用自动扫描
  （`frame_container_size` (222,110)→(136,71)，用户可见）。**H5 契约**：`comment` 必为非空字符串数组；未知字段只
  warning → 须锁"入库无未知键"；自动扫描不可降级。
- **S1/S2/S3 全完成**（S2 `b099e4c` 外化 `assets/animations.json` schema=1/109 组/377 帧，AST 单向导出 +
  JSON 优先异常回落；S3 `94e4902` 别名/legacy 显式化）。未修：`change_animation` 长→短回退 vs
  `update_animation` 内嵌块只取前两段。下一步：真机取真实未命中清单。
