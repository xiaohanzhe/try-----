# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

## 铁律
- **每轮改动完成即 commit + push**（"以免后期找不到"）。称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根（`代码质量复审报告_*.md`）；证据进 `code-quality-audit/<轮次>/`，侦察日志 `_recon/`（gitignore），
  留痕进 `_evidence/`。改代码前跑 G2 `code-quality-audit/regress/run_all.py`（现 **16 套件**）。
- **下载/生成物默认落 `E:\Download`**（临时件 `E:\Download\_tmp\` 用后即删）；例外：仓库内产物留项目目录。
  系统默认下载目录**不动**。E 盘会掉线（见环境铁律 8）。

## 环境铁律
1. **Bash 工具不可用** → 一律 **PowerShell**；列目录用 Glob/Read。
2. PowerShell **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 再 Read（父目录不存在会 exit 1 且无输出
   → 先 `New-Item -ItemType Directory -Force`）。
3. **起进程**：`cmd /c`、`Start-Process`、WMI 全被拦 → 只能 `&` + `run_in_background:true`。
4. **杀进程**：`Stop-Process`/`taskkill` 静默失效 → Python + psutil 按 cmdline 匹配。
5. **删文件**：管道 `Remove-Item` 静默无效 → `[System.IO.File]::Delete()` + `Test-Path` 校验。
6. Python：**`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil/jieba）—— **G2 与所有套件必须用它**；
   托管 venv（3.13）缺 `bs4` → `round5_smoke` 假 FAIL。（`run_all.py` 按 `REGRESS_PYTHON` 自动选。）
7. 代理：沙箱 `127.0.0.1:54231`（对 github 常 502）；Clash `127.0.0.1:7897`（可用）。
8. **E 盘是外接盘、会掉线**（`Get-Volume` 只剩 C/D、`Get-Disk` 仅一块 NVMe 即掉线）→ "本地中转站"是**可用性必需**。

## git push（退出码 128 且全静默 = 非交互 GCM 取不到凭据）
```powershell
$cred = "url=https://github.com/xiaohanzhe/try-----.git`n`n" | git credential fill 2>$null
$pw  = ($cred | ? { $_ -like 'password=*' }) -replace '^password=',''
$usr = ($cred | ? { $_ -like 'username=*' }) -replace '^username=',''
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$usr`:$pw"))
git -c credential.helper= -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 `
    -c http.extraheader="Authorization: Basic $b64" push origin main   # 重试 3–5 次
```
- 令牌别写进仓库文件。核验外发用 `git ls-remote origin refs/heads/main`（加同样头），比看退出码硬。
- **提交信息用 Write 写 UTF-8 文件 + `git commit -F <文件>`**：`-m @'...'@` 遇"带空格的英文引号串"会被 PS 5.1
  拆 argv → 提交没发生、push 退 0 假成功。提交后必核 `git log --oneline -1`。

## 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有，未认证 401/404）；main→origin/main。GitHub 连接器只覆盖
  公开库，看不到本仓库（404）。
- 真机起：`Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。单实例锁
  `Global\RalseiPetMutex`，残留用 psutil 杀。窗口透明非置顶 FramelessWindow → 被遮挡/鼠标穿透 → **甩飞、抛物线
  只能离屏断言**。
- 卫生：`compileall` 会改写被跟踪的 `src/__pycache__/*.pyc` → 跑完 `git checkout --`。`.gitignore` 覆盖 `*.log`/
  `*.bak`/`__pycache__/`/`code-quality-audit/*/_recon/`/`regress/_out/`；`*.log.<日期>` 不匹配（未跟踪残留）。

## 勿回退契约（改代码必须遵守）
- **多屏**禁用 `QApplication.desktop().availableGeometry()`（只返主屏→"瞬移"根因），用 `_virtual_screen_rect()`/
  `_current_screen_rect()`/`_clamp_pos_to_desktop()`/`_desktop_floor_y()`。物理量必须钳 `dt≤0.1s`（否则卡顿后单帧
  dt 变大 → 位移二次放大 → 同一种"瞬移"）。
- **甩飞/抛物线**：判定只能在 `mouseReleaseEvent`（`_drag_samples` 0.12s 窗口，`_FLING_SPEED=900`/`_BOUNCE_SPEED=250`）；
  初速只由松手速度定（等比缩放 + **矢量和**限幅）；`_fall_vy0` 只在第一帧记录；清理点共用 `_FALL_VELOCITY_ATTRS`/
  `_FALL_STATE_ATTRS`；落地相位 `_fall_phase_start`+`_fall_flight_time`+`_fall_landed`；空中接住减速积分
  `s=v0·t·(1-t/(2·dur))`。
- 动画 `fps=6`（`config.json`+`config_manager.py`）；自主说话唯一入口 `start_autonomous_speech()`
  （`AUTONOMOUS_SPEECH_MIN_INTERVAL=600.0`），**AI 关闭必须沉默、不得回落内置台词**；不劫持鼠标、拖拽 1:1、
  起身类 `play_animation_once(...,restore_to="idle")` 只播一次。
- **特殊动画（#13）**：来源只三类 —— ① `ai_driver` 决策 ② 用户显式交互 ③ 物理状态机（fall/splat/land/jump/wake）。
  **环境自动触发不得自行播动画**，只能 `ai_driver.note_event()` 上报观察（`react_to_desktop_element`→
  `_note_desktop_observation`、`_react_to_video` 已收编）；`update_animation_by_emotion` 与 `on_mouse_hover` 已空实现。
  播放期 `_special_anim_locked()` 禁移动且 **force 也不能打断**；待机循环需原地静止 ≥`IDLE_LOOP_MIN_SECONDS=180` 才推进帧；
  切换位置一致靠 `_anim_anchor_offset`/`_compose_anchored_sprite` 按 alpha 包围盒中心对齐（idle 偏移 (-20,+2.5)）。
- **多跳联想（第十轮）**：分层边 strong/mid/weak + hub 惩罚（IDF×度 ∈[0.25,1]）+ 路径打分
  （∏边权×∏节点权×`HOP_DECAY=0.72`^跳数）+ `RecallBudget`。铁律：① 门槛 `HOP_TIER_FLOOR={1:weak,2:weak,3:mid}` +
  **中转资格** `_BRIDGE_MIN_RANK=mid`（弱边**可到达、不可再出发**）—— 静态 `{1:weak,2:mid,3:strong}` 在真实语料
  （98% 弱边）下锁死多跳；② **PPR 只加权不准入**（`kw *= 1 + PPR_MIX×ppr_norm`），准入永远由路径分定（加进关键词分
  会让被剪掉的 hub 词复活）。`assoc` 是 property、`_graph` 是唯一真源；`graph.paths()` 只吃 `seed_map()` 归一化 dict
  （传 list → `seeds.items()` 抛错被防御性 except 吞 → **多跳静默返回空**）。
- **联想输入端（第十一/十二轮）**：① 抽词唯一入口 `conversation_focus.extract_keywords`（**三层择优**：
  `_from_segmenter`→`_extract(strict=True)`→`_extract(strict=False)` 兜底，**不返回空**）。碎片治理靠**位置专员剪刀**
  （`_STOP_MULTI`/`_EDGE_FUNC`/`_INNER_FUNC`+`_INNER_VERB`/`_EDGE_VERB`/`_TAIL_FUNC`，每把只盯一字符位）+ **免伤名单
  `_KEEP_WORDS`**。`_ngrams` **按位置生成**（顺序即语义）。`set_segmenter(fn)` 是注入点，**抛异常/返回空都回落内置**。
  ② `memory_graph.EDGE_TOPOLOGY` **默认仍是 `clique`**（勿凭直觉改 star/chain）：star/chain 精确率更高（55% vs 50%）、
  密度更低（0.83 vs 3.26 边/点），**但过不了多跳可达闸门** —— 强制 `代码—熬夜—咖啡` 时 clique stage2/3 通，
  star/chain **强边也断链**。密度靠**输入端**压，**不靠砍边**。回归锁 B13–B17。
- **存储两层（第十二轮）**：vault=`E:\RalseiMemory\`（卷标含"肖翰哲"，复用 `memory_store` 设备发现）；
  staging=`%LOCALAPPDATA%\RalseiPet\`（E 离线落脚点）。**读永远 vault 优先**，E 回来由 `migrate_from_staging()` 搬。
  `data_store` 是**唯一入口**（`artifact_path`/`app_file`/`data_root`）；7 类产物（logs、crash.log、config.json、
  customization_config.json、entertainment_data.json、growth_data.json、jieba.cache）全走它。收编历史遗留**只复制不搬走**
  （仓库里被跟踪的默认模板不能删）。迁移五约：先探 `_movable`（占用跳过）→ copy 校长度才删源 → 同名比 mtime 留新、
  落选者 `.old` → 只删空目录不递归 → vault==staging 拒搬。**`data_store` 禁用模块级 logger**（改惰性 `_LazyLogger`）：
  否则 `logger_utils`→`import data_store`→未执行完 → 日志目录**永久钉死兜底值**；配合 `logger_utils._log_dir()`
  **失败不缓存** + `_init_logging` 重入护栏。回归锁 C2。
- **jieba 是软依赖（第十二轮）**：适配层 `modules/text_segmenter.py`，`install()` 走 `set_segmenter`，没装/加载失败/
  切词抛异常一律静默回落内置；后台预热；`calls`/`fallbacks` 计数；可选 `jieba_userdict.txt`。**词边界归适配器，
  停用词/长度/去重仍归 `_from_segmenter()`（唯一一份）**。实测六句 56→14 词条。G2 需归一化 `Loading model cost X seconds`。
- **误报清单（勿据此改）**：`learn_new_skill` 有 `if new_skills:` 守卫；`_on_ai_reply` 跨线程已由 `pyqtSignal` 排主线程；
  `reset_special_states` 零调用；原子写/回收站删除已正确防御。

## 验证脚本教训（第八轮）
- **别用 `"字面量" in 源码` 做源码级断言**（注释/文档串会误命中）。用 `code_only()`（tokenize 剥 COMMENT/STRING）；
  但 **`tokenize` 不产空白 token** → 拼回必须 `' '.join`（`''.join` 会把 `import heapq` 粘成 `importheapq`）；
  比较两侧先 `re.sub(r'\s+','',...)`，加 X0 自检。找**字符串字面量 needle** 要用 `code_no_comment()`（只剥注释）。
- **防御性 `except` 必须配异常计数**（一轮里 `paths()` 收到 list 抛错被静默吞 → "多跳永远返回空"）。
- 顺序断言限定在**目标函数体内**（`func_src(name)`），不能用全文件 `.index()`（会命中别的函数 → 判反）。
- 行为级断言优先于字符串断言；`SimpleNamespace` 桩要 `types.MethodType` 绑实例方法。

## 历轮（细节见 `.workbuddy/memory/<日期>.md` 与对应报告）
- 7：README 路径启动 `ModuleNotFoundError: logger_utils` 已修（教训：凡"测试里预置环境"处都要留"按真实路径跑"的对照）。
- 8：#10 对话框 ▼ 抖动（`024b6aa`）/#11 坠落误判（`cc9471d`）/#12 斜抛+空中二次抓+卡动画（`654da19`）/#13 特殊动画治理。
  待办 #14 G2 断言、#15 对话全 AI 接管 + 原作风格聊天框原型（**不直接改 `dialogue_ui.py`**）+ 多人对话预留 +
  "建楼"楼层系统 + bilibili 窗口摆放（PPT 类软件打开则不开）。
- 9（`..._第九轮.md`）：话题锚 `conversation_focus.py`（**换题只能用户发起**，`brief()` 唯一出口）+ 20s 自动隐藏 +
  自主开口不打断 + 拟人记忆 `memory_store.py`。自检 105/0，G2 13/360。真机 `E:\RalseiMemory\memory.json`。
- 10（`..._第十轮.md` `e9f6b00`）：`memory_graph.py` 566 行 + `recall()` 五段管线。自检 98/0，G2 14/459。
- 11（`..._第十一轮.md` `e8795da`/`6ef6fe2`）：抽词剪刀（碎片 -39%）+ 拓扑实测择优（clique）。自检 64/0，G2 15/523。
- 12（`..._第十二轮.md` `289023c`）：jieba 软依赖接入 + `data_store.py` 收口 7 类产物。自检 54/0，G2 16/579。
  局限：E 盘离线 → vault 仅环境变量模拟验证待补真机；程序目录历史开发日志未删（待用户点头）。

## H4/H5 架构改造（用户排期"单独做"）
- 工具/基线 `code-quality-audit/架构改造-H4H5/`（只读）。**量化基线（勿重测）**：`main.py` 8794 行/`RalseiPet` 186 方法；
  `self` 属性 438、106 个被 ≥3 处写；`animation_mapping` 109 组/1106 PNG/743 未引用/缺失 0；动画名字面量 24+12 f-string；
  运行时 `sprites`=489。
- **两坑**：① 不能拿 `scan_and_group_assets` 全量替代硬编码（mapping 载别名+故意缺省+前缀回退，全量入组会重现灰块）；
  ② 不能停用自动扫描（`frame_container_size` (222,110)→(136,71)，用户可见）。
- **H5 契约**：`comment` 必为非空字符串数组；未知字段只 warning → 须锁"入库无未知键"；自动扫描不可降级。
- **S1/S2/S3 全完成**（S1 未命中 17/17；S2 `b099e4c` 外化 `assets/animations.json` schema=1/109 组/377 帧，AST 单向
  导出 + JSON 优先异常回落，等价已证；S3 `94e4902` 别名/legacy 显式化）。未修：`change_animation` 长→短回退 vs
  `update_animation` 内嵌块只取前两段。下一步：真机取真实未命中清单。
