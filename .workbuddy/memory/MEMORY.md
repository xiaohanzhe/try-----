# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

## 铁律与称呼
- **每轮改动完成即 commit + push**（用户原话"以免后期找不到"），不攒批。称呼"用户"；技术细节我拍板；
  不可逆/对外动作先说影响面。
- 报告放项目根（`代码质量复审报告_*.md` / `H5-*.md`）；证据 `code-quality-audit/<轮次>/`，
  侦察日志进 `<轮次>/_recon/`（gitignore），要留痕的进 `_evidence/`。
- 改代码前跑 G2：`code-quality-audit/regress/run_all.py`（11 套件）。

## 环境铁律
1. **Bash 工具不可用**（`ls`/`cd`/`dirname` 全 command not found）→ 一律 **PowerShell 工具**；列目录用 Glob/Read。
2. PowerShell **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 再 Read。
   父目录不存在会 exit 1 且无输出（像"脚本崩了"）→ 先 `New-Item -ItemType Directory -Force`。
3. **起进程**：`cmd /c`、`Start-Process`、WMI 全被拦/静默失败 → 只能 `&` + `run_in_background:true`。
4. **杀进程**：`Stop-Process`/`taskkill` 静默失效 → Python + psutil 按 cmdline 匹配。
5. **删文件**：管道 `Remove-Item` 静默无效 → `[System.IO.File]::Delete()` + `Test-Path` 校验。
6. Python：**`C:\Python311\python.exe`**（PyQt5/pywin32/bs4/psutil）—— **G2 与所有套件必须用它**；
   托管 venv（3.13）缺 `bs4` → `round5_smoke` 假 FAIL。（`run_all.py` 已按
   `REGRESS_PYTHON`>`C:\Python311\python.exe` 自动选并打印表头。）
7. 代理：沙箱 `127.0.0.1:54231`（对 github 常 502）；Clash `127.0.0.1:7897`（可用）。

## git push（退出码 128 且全静默 = 非交互 GCM 取不到凭据）
```powershell
$cred = "url=https://github.com/xiaohanzhe/try-----.git`n`n" | git credential fill 2>$null
$pw  = ($cred | ? { $_ -like 'password=*' }) -replace '^password=',''
$usr = ($cred | ? { $_ -like 'username=*' }) -replace '^username=',''
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$usr`:$pw"))
git -c credential.helper= -c http.proxy=http://127.0.0.1:7897 `
    -c http.extraheader="Authorization: Basic $b64" push origin main   # 重试 3–5 次
```
- 令牌别写进仓库文件。外发核验用 `git ls-remote origin refs/heads/main` 加同样头，比看退出码硬。
- **提交信息用 Write 写 UTF-8 文件 + `git commit -F <文件>`**：`-m @'...'@` 遇"带空格的英文引号串"
  会被 PS 5.1 拆 argv → 提交没发生、push 退 0 假成功。提交后必核 `git log --oneline -1`。

## 仓库与真机
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有，未认证 401/404）；main→origin/main。
  GitHub 连接器已接（xiaohanzhe/236837805）但**只覆盖公开库**，看不到本仓库（404）。
- 真机起：`Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background`。
  单实例锁 `Global\RalseiPetMutex`，残留用 psutil 杀。窗口是透明非置顶 FramelessWindow →
  会被遮挡/鼠标穿透 → **甩飞、抛物线只能离屏断言，做不了真机验证**。
- 卫生：`compileall` 会改写被跟踪的 `src/__pycache__/main.cpython-311.pyc` → 跑完 `git checkout --`。
  `.gitignore` 覆盖 `*.log`/`*.bak`/`__pycache__/`/`code-quality-audit/*/_recon/`/`regress/_out/`；
  `*.log.<日期>` 不匹配（未跟踪残留）。

## 勿回退契约（改代码必须遵守）
- **多屏**禁用 `QApplication.desktop().availableGeometry()`（只返主屏→历史"瞬移"根因），用
  `_virtual_screen_rect()`/`_current_screen_rect()`/`_clamp_pos_to_desktop()`/`_desktop_floor_y()`。
- 物理量必须钳 `dt≤0.1s`（否则卡顿后单帧 dt 变大使位移二次放大 → 同一种"瞬移"）。
- **甩飞/抛物线**：判定只能在 `mouseReleaseEvent`（`_drag_samples` 0.12s 窗口，
  `_FLING_SPEED=900`/`_BOUNCE_SPEED=250`）；初速只由松手速度定（等比缩放 + **矢量和**限幅）；
  `_fall_vy0` 只在飞行第一帧记录；清理点共用模块级 `_FALL_VELOCITY_ATTRS`/`_FALL_STATE_ATTRS`；
  落地相位用 `_fall_phase_start`+`_fall_flight_time`+`_fall_landed`；空中接住减速是积分
  `s=v0·t·(1-t/(2·dur))`。
- 动画 `fps=6`（`config.json` + `config_manager.py`，frame_delay 166）；自主说话唯一入口
  `start_autonomous_speech()`（`AUTONOMOUS_SPEECH_MIN_INTERVAL=600.0`），**AI 关闭必须沉默、
  不得回落内置台词**；不劫持鼠标、拖拽 1:1、起身类 `play_animation_once(...,restore_to="idle")` 只播一次。
- **特殊动画（#13）**：来源只允许三类 —— ① `ai_driver` 决策 ② 用户显式交互（点击/菜单/抚摸/游戏）
  ③ 物理状态机（fall/splat/land/jump/wake）。**环境自动触发不得自行播动画**，只能
  `ai_driver.note_event()` 上报观察（`react_to_desktop_element`→`_note_desktop_observation`、
  `_react_to_video` 已收编）；`update_animation_by_emotion` 与 `on_mouse_hover` 已空实现。
  播放期 `_special_anim_locked()` 禁移动且 **force 也不能打断**；待机循环需原地静止
  ≥`IDLE_LOOP_MIN_SECONDS=180` 才推进帧；动画切换位置一致靠 `_anim_anchor_offset`/
  `_compose_anchored_sprite` 按 alpha 包围盒中心对齐（idle 偏移 (-20,+2.5)）。
- **多跳联想（第十轮）**：分层边（strong/mid/weak）+ hub 惩罚（IDF×度，∈[0.25,1]）+ 路径打分
  （∏边权×∏节点权×`HOP_DECAY=0.72`^跳数）+ `RecallBudget` 预算截断。两条铁律：
  ① 跳层门槛用 `HOP_TIER_FLOOR={1:weak,2:weak,3:mid}` + **中转资格** `_BRIDGE_MIN_RANK=mid`
  （弱边**可到达、不可再出发**）—— 写成静态 `{1:weak,2:mid,3:strong}` 会在真实语料（98% 弱边）
  下把多跳整体锁死；
  ② **PPR 只加权不准入**（`kw *= 1 + PPR_MIX×ppr_norm`），准入永远由路径分决定 —— 一旦把 PPR
  加进关键词分，被路径剪掉的 hub 词会被复活（R2c 抓到过）。
  且 `assoc` 是 property、`_graph` 是唯一真源；`graph.paths()` 只吃 `seed_map()` 归一化后的 dict
  （传 list 会 `seeds.items()` 抛错并被防御性 except 吞掉 → **多跳静默返回空**）。
- **误报清单（勿据此改）**：`learn_new_skill` 有 `if new_skills:` 守卫；`_on_ai_reply` 跨线程已由
  `pyqtSignal` 排主线程；`reset_special_states` 零调用；原子写/回收站删除已正确防御。

## 验证脚本教训（第八轮踩过）
- **别用 `"字面量" in 源码` 做源码级断言**：注释与文档字符串会误命中。用 `code_only()`
  （tokenize 剥 COMMENT/STRING 再扫）。**但 `tokenize` 不产空白 token** → 拼回必须 `' '.join`
  （用 `''.join` 会把 `import heapq` 粘成 `importheapq`，子串断言恒假）；比较两侧都先
  `re.sub(r'\s+','',...)`，并加一条"自检自检"的 X0 用例。
- **防御性 `except` 必须配异常计数**：一轮里 `paths()` 收到 list 抛 `AttributeError` 被静默吞掉，
  表现为"多跳永远返回空"，排查成本极高。
- 顺序断言必须限定在**目标函数体内**（`func_src(name)`），不能用全文件 `.index()`（会取到别的函数里
  更早的同名串 → 顺序判反）。
- 行为级断言优先于字符串断言；`SimpleNamespace` 桩要 `types.MethodType` 绑实例方法。

## 历轮
- 第七轮：按 README 路径启动 `ModuleNotFoundError: logger_utils` 已修（`desktop_interaction` 加
  try/except + `main` 把 `<root>/modules` 入 sys.path）。教训：**凡"测试里预置环境"的地方都要留一条
  "按真实路径跑"的对照**。
- 第八轮：#10 对话框 ▼ 抖动/滚动（`024b6aa`）、#11 坠落/摔倒误判（`cc9471d`）、
  #12 斜抛+空中二次抓住+卡动画（`654da19`）、#13 特殊动画治理（见上）。
  待办：#14 G2 断言更新；#15 对话全 AI 接管 + 原作风格聊天框原型（**不直接改 `dialogue_ui.py`**）
  + 多人对话预留 + 完整"建楼"楼层系统 + bilibili 窗口摆放（PPT 类工作软件打开则不开）。
- 第九轮（2026-09-15，**已完成**）：用户四诉求 —— ① AI 对话别突然切话题 ② 对话框 20s 无输入自动消失，
  但鼠标在输入栏上/正在输入时不能消失 ③ 10 分钟自主开口不打断正在进行的聊天 ④ 记忆系统拟人化。
  全部落地并纳入 G2（见当日日志 `2026-09-15.md` 与 `代码质量复审报告_2026-09-15_第九轮.md`）。
  要点：新增 `modules/conversation_focus.py`（话题锚，**换题只能由用户发起**，`brief()` 是唯一影响模型的出口）
  与 `modules/memory_store.py`（**卷标含"肖翰哲"的盘 → `RalseiMemory\`，否则 `<桌面>\memory\`**；
  先复制校验再删源、落选者挪 `memory.old.json`）；`memory_system.py` 加拟人层
  `fragments`/`keys`/`digests`/`assoc` + `forget_cycle`/`recall`/`recall_text`/`reconstruct_scene`/`reset_all`；
  `dialogue_ui` 加 `AUTO_HIDE_MS=20000`/`has_active_conversation`/`_mouse_on_input(global_pos=None)`/`_note_memory`。
  自检 **105 PASS / 0 FAIL**，G2 **13 套件 / 360 PASS / 全 IDENTICAL**。真机：`E:\RalseiMemory\memory.json`。

## H4/H5 架构改造（用户排期"单独做"）
- 工具/基线 `code-quality-audit/架构改造-H4H5/`（只读）。**量化基线（勿重测）**：`main.py` 8794 行 /
  `RalseiPet` 186 方法；`self` 属性 438 个、106 个被 ≥3 处写；`animation_mapping` 109 组/1106 PNG/
  743 未引用/缺失 0；动画名字面量 24 + 12 处 f-string；运行时 `sprites`=489。
- **两个坑**：① 不能拿 `scan_and_group_assets` 全量替代硬编码（mapping 承载别名+故意缺省+前缀回退，
  全量入组会重现灰块占位帧）；② 不能停用自动扫描（`frame_container_size` (222,110)→(136,71)，用户可见）。
- **H5 契约**：`comment` 必为非空字符串数组；未知字段只 warning → 须锁"入库无未知键"；自动扫描不可降级。
- **S1/S2/S3 全完成**（S1 未命中账本 17/17；S2 `b099e4c` 配置外化 `assets/animations.json`
  schema=1/109 组/377 帧，单向 AST 导出 + JSON 优先异常回落，等价已证；S3 `94e4902` 别名/legacy 显式化）。
  已知未修：`change_animation` 长→短回退 vs `update_animation` 内嵌块只取前两段。下一步：真机取真实
  未命中清单（S2/S3 只证等价、未证覆盖完整）。
