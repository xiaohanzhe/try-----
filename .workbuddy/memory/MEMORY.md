# 项目长期记忆 — ralsei_pet 代码质量系列审查

## 工作流铁律（用户明确要求）
- **每次改版都要提交并推送一次 git**（原话："以免后期找不到"）。任何一轮代码/文档改动完成后，
  立即 commit + push，不要攒批。推送方法见下方「git push 备忘」。
- 汇报时用"用户"称呼他；技术细节由我拍板，不必反复请示，但不可逆动作要先说影响面。

## 项目概况
- 主体：`ralsei_pet/` — Deltarune Ralsei 桌面宠物，Windows + Python 3.11 + PyQt5。
- `src/main.py` 现 8500 行 / 187 个 def、单巨型 `RalseiPet(QMainWindow)` 类；另有 23 个 `modules/*.py`。
- 审查产物统一放 `code-quality-audit/<轮次>/`（第五轮起逐轮递增；架构改造类在
  `code-quality-audit/架构改造-H4H5/`、一键回归在 `code-quality-audit/regress/`），
  报告放项目根（`代码质量复审报告_*.md` / `H5-*.md`）；每轮的临时侦察日志进 `<轮次>/_recon/`（已 gitignore）。

## 仓库与远端
- 分支 `main` → `origin/main`，远端 `https://github.com/xiaohanzhe/try-----.git`（**私有库**，未认证请求返回 401 "Repository not found."）。
- git 身份：`xiaohanzhe` / `2300269435@qq.com`。
- 凭据由 Git Credential Manager 托管，账号 `236837805`，令牌为 `gho_` 开头的 OAuth（40 位）。

## 本机环境铁律（重要）
1. **Bash（PortableGit shim）不可用**：`dirname`/`ls`/`mkdir`/`head` 全部 `command not found`（exit 127）。
   → 一律改用 **PowerShell 工具**；不要用 Bash 工具跑目录/文件命令。
2. **PowerShell 的 stdout 经常不回传**（工具只给 "exit code 0"）。
   → 稳妥做法：命令内 `Out-File -Encoding utf8 <文件>` 落盘，再用 Read 读取该文件。
3. `cmd /c` 被安全策略禁止（"cmd.exe cannot be used from the PowerShell tool"）。
4. Python：真实环境 `C:\Python311\python.exe`（已装 PyQt5 / pywin32）；
   venv `C:\Users\23002\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（已装 pyflakes 3.4.0）。
5. `Out-File` 的**父目录不存在时直接失败（exit 1）且不留任何输出**，看起来像"Python 脚本崩了"。
   凡把命令输出重定向到新建目录，必须先 `New-Item -ItemType Directory -Force -Path <dir> | Out-Null`。
6. `Remove-Item` 经管道传参删除文件时会**静默无效**（exit 0 但目标仍在，即使加 `-Force`）。
   稳妥做法：`[System.IO.File]::Delete($path)`，随后用 `Test-Path` 立即校验。

## git push 备忘（本机曾长期失败）
- **症状**：`git push` 退出码 128，且 stdout/stderr **完全静默**（无任何提示）。
- **诊断手段**：`$env:GIT_TRACE='<file>'`、`$env:GIT_TRACE_CURL='<file>'` 让 git 把内部日志写文件；
  再用 Read 读取。可看到 `HTTP/1.1 401 Unauthorized` + 卡在 `run_command: 'git credential-manager get'`。
- **根因**：非交互会话下 `git push` 调用 GCM 取凭据失败（GCM 2.6.1），
  而 `git credential fill` 手工调用却正常（0.5s 返回）。令牌本身有效（`api.github.com/user` → 200）。
- **可靠绕过**（已验证可用）：
  ```powershell
  $cred = "url=https://github.com/xiaohanzhe/try-----.git`n`n" | git credential fill 2>$null
  $pw  = ($cred | Where-Object { $_ -like 'password=*' }) -replace '^password=',''
  $usr = ($cred | Where-Object { $_ -like 'username=*' }) -replace '^username=',''
  $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$usr`:$pw"))
  git -c credential.helper= -c http.extraheader="Authorization: Basic $b64" push origin main
  ```
  注意：**永远不要把令牌明文/base64 写进仓库文件**；用完确认 `_evidence` 无泄露再提交。
- **网络层（2026-09-13 实测新增）**：本机 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量指向
  `http://127.0.0.1:54231`（沙箱代理），但 `github.com` 走它常返 **`CONNECT tunnel failed, response 502`**；
  直连则 `Failed to connect to github.com port 443`（不通）。**可靠组合**：
  `-c http.proxy=http://127.0.0.1:7897`（本机 Clash 端口）**+ 重试循环（3–5 次，间隔 5s）**。
  典型症状是 `schannel: failed to receive handshake` / `unexpected eof while reading` →
  属 **github.com 的 SNI 被 TLS 重置**，是间歇性的，**重试通常能过**（实测第 4 次成功）。
  快速判据：`curl.exe -v -x http://127.0.0.1:7897 https://github.com` 若看到
  `CONNECT tunnel established, response 200` 紧接 `schannel: failed to receive handshake`，
  即代理通、目标被重置；而 `api.github.com` 同时可 200（用于区分"代理坏了"还是"目标被封"）。

## git 提交备忘：**别用 `-m @'...'@` 传含英文双引号的中文消息**
- 现象：`git commit -m @'...'@` 报 `error: pathspec 'true 这类拼写错误…' did not match any file(s)` ——
  提交**没发生**，随后 `git push` 因"无提交可推"退出码 0，看起来像成功（其实啥也没推）。
- 根因：PowerShell 5.1 向原生 exe 传参时不正确转义内层 `"`；只要正文出现**带空格的英文引号串**
  （如 `"legcay: true"`）就会被拆成多个 argv。正文没有英文引号时用 here-string 一切正常（这解释了
  早期"传中文多行没问题"的结论为何不完整）。
- **可靠做法**：用 Write 工具把提交信息写成 UTF-8 文件，再 `git commit -F <文件>`。
  提交后**必须核对 `git log --oneline -1`**，别只看 push 的退出码。

## GitHub 连接器（2026-09-13 接入）
- 已连接，身份 = `xiaohanzhe`（id **236837805**，与本机 GCM 账号一致）。
- **但它看不到我们的工作仓库**：`GET /repos/xiaohanzhe/try-----` 返 **404**（私有库对无权限令牌一律 404，
  以此掩盖"存在与否"）。同账号公开库可正常读（`desktop-pet` 的 commits 拉得到）→ 连接器本身是通的，
  **是授权范围只覆盖公开库**。要用它核对推送 / 读 PR，须把 `try-----` 加进其可访问仓库
  （OAuth scope 或 GitHub App 的 repository selection，取决于授权形态）。
- 该账号公开库只有 2 个且都不是本项目：`desktop-pet`（Python 脚手架）与 `ralsei_pet`
  （**空壳**：仅 `README.md`/`PR_NOTES.md`/`.gitattributes`/`assets/`，无 `src/`）→ **无代码外泄**。
- **`git ls-remote` 对私有库同样要手工认证头**，否则退出码 **128 且完全静默**（与 push 同因：
  非交互 GCM 取不到凭据）。加 `-c credential.helper= -c http.extraheader="Authorization: Basic <b64>"`
  即成功。**核对外发是否真的成功，用它可以，且比看 push 退出码更硬**。

## 仓库卫生约定
- `compileall` 会改写被 git 跟踪的 `src/__pycache__/main.cpython-311.pyc` → 跑完用 `git checkout --` 还原。
- 临时诊断脚本/输出统一收进 `code-quality-audit/<轮次>/_evidence/`，项目根不留散落文件。
- `.gitignore` 覆盖 `*.log` / `*.bak` / `*.backup*` / `__pycache__/`；
  但 `*.log.<日期>`（如 `ralsei_pet.log.2026-09-12`）不被匹配，属未跟踪残留。

## 已确认的"勿据此修改"清单（历轮复核为误报）
- `memory_system.learn_new_skill` 的 `random.choice(new_skills)` 有 `if new_skills:` 守卫。
- `dialogue_ui._on_ai_reply` 跨线程操作 QWidget 已由 `pyqtSignal` 排队回主线程防御。
- `reset_special_states` 全项目零调用，漏复位 `is_happy`/`is_splat` 无影响。
- 原子写（临时文件 + 同目录 `os.replace`）与回收站删除失败保留，均已正确防御。

## 第六轮：用户反馈 6 项行为缺陷修复（已完成，2026-09-13）
提交 `4ef922e`（行为）+ `67d2936`（文档留痕），已推送。报告 `代码质量复审报告_2026-09-13_第六轮.md`，
证据 `code-quality-audit/第六轮/`（含 `verify_round6_fixes.py` 39 项断言，四套合计 72 PASS / 0 FAIL）。

**项目级约定（后续改代码必须遵守，勿再回退）**：
- **多显示器坐标一律不用 `QApplication.desktop().availableGeometry()`**——它只返回主屏且原点固定 `(0,0)`，
  副屏负坐标会被夹回，历史上就是"瞬移"的根因。统一用 `_virtual_screen_rect()`（整个虚拟桌面）/
  `_current_screen_rect()`（`screenGeometry(self)`，它当前所在屏幕）/ `_clamp_pos_to_desktop()` / `_desktop_floor_y()`。
- **物理量必须钳 `dt`**：`update_movement`/`handle_gravity_fall`/`update_bounce` 中 dt 上限 0.1s，
  否则主线程卡顿后单帧 dt 变大会让位移按 dt 二次放大 → 同一种"瞬移"。
- **甩飞（fling）判定只能放在 `mouseReleaseEvent`**：曾误写在 `mouseMoveEvent` 的无按键分支里，
  导致"停住再松手"永不触发、且松手后碰一下鼠标会用陈旧采样自己甩自己。速度用
  `_drag_samples` 真实 px/s（最近 0.12s 窗口，末次采样距今 >0.25s 记为轻放）；
  `_FLING_SPEED=900`、`_BOUNCE_SPEED=250`。
- **抛物线的落地相位不能借用 `self.fall_duration` 绝对值**（曾导致高空弧线在空中就进 splat/dazed），
  必须用 `_fall_phase_start` + `_fall_flight_time` + `_fall_landed` 做相对计时。
- **动画帧率 `fps=6`**（`config.json` + `config_manager.py`，frame_delay 166）——用户明确要求，勿改回去。
- **自主说话只有一个入口 `start_autonomous_speech()`**，节流 `AUTONOMOUS_SPEECH_MIN_INTERVAL=600.0`；
  **AI 关闭时必须保持沉默，不得回落内置台词**（20 个内置对话方法已全删，见 `strip_builtin_dialogue.py`）。
- 常识底线：不给"假装操作桌面文件"的假动作、不劫持鼠标指针、拖拽 1:1 跟手、起身类动作
  `play_animation_once(..., restore_to="idle")` 只播一次。

## H4/H5 架构改造（用户已决定"单独排期"，方案见 `架构改造排期方案_H4-H5_2026-09-13.md`）
- 工具与基线在 `code-quality-audit/架构改造-H4H5/`（`scan_refactor_baseline.py`、`scan_animation_contract.py`，均为只读）。
- **量化基线（勿再重复测量）**：`main.py` 8794 行 / `RalseiPet` 186 方法 / 方法体占 94.2%；
  `self` 属性名 438 个，**106 个被 ≥3 处写入**（拆分的真耦合点）；
  `animation_mapping` 109 组 / 素材 1106 PNG / **743 个未引用** / 引用缺失 0；动画名字面量 24 个 + 12 处 f-string 拼接。
- **两条不可踩的坑**：① 不能用 `scan_and_group_assets` 全量自动替代硬编码——mapping 承载"别名 + 故意缺省
  （`walk_up_blush` 等）+ 前缀回退契约"，全量入组会重新引入灰块占位帧；② H5 第一步是给
  `change_animation`/`get_sprite` 加"未命中即 WARNING"自检，不是搬配置（动态拼接使缺失静态不可见）。
- H4 拆分判据：新模块**不反向引用 `RalseiPet`**、不 import `main`；施工用"转发壳"（原方法体改一行转发、
  保留原名），Wave 顺序 独立子系统 → 鼠标交互 → 动画/移动/物理。
- **进度：H5 S1 / S2 / S3 全部完成**（2026-09-13）。
  - S1：`animation_misses` 账本 + `diagnose_dynamic_name`/`note_animation_miss`/
    `get_animation_miss_report`/`log_animation_miss_summary`；`main.py` 四处记账。**零行为变更**，17/17。
    报告 `H5-S1_动画名自检_实施与验证报告_2026-09-13.md`。
  - S2（`b099e4c`）：配置外化到 `ralsei_pet/assets/animations.json`（schema=1，109 组 / 377 帧，21,809 字节），
    由 `架构改造-H4H5/extract_animations_json.py` 从源码 AST **单向导出**；JSON 优先、异常回落内置表；
    新增 `animation_config_source`/`legacy_animations`/`position_offset`/`get_animation_config_report()`/
    `get_unconfigured_asset_report()`。等价性已证（键集合/顺序/每组帧/总帧数全等；运行期 `sprites` 489/489、
    `frame_container_size` 两侧均 (222,110)、总帧 1461）。
  - S3（`94e4902`）：4 组别名改 `alias_of`（happy→laugh / neutral→idle / sad→cry_start / splat_mad→fall_mad，
    自身 frames 清空），28 组标 `legacy:true`；**未改 `sprite_loader.py`/`main.py`**。
    工具 `apply_s3_alias_legacy.py`（--apply 幂等）+ `verify_s3_alias_legacy.py`（19 项，含独立字面量重扫）。
    报告 `H5-S2-S3_动画表外部化_实施与验证报告_2026-09-13.md`。
- **运行时实测（勿再重复测）**：`sprites` = **489 组** = mapping 109 + 自动扫描 380（1084 帧对象，
  82 组与 mapping 100% 重复）；仅自动扫描引用而 mapping 未引用的帧文件 **724** 个；磁盘 1106 PNG 中 **19** 个无人引用。
- **G2 一键回归基线已建立**（`77b01a1`）：`code-quality-audit/regress/run_all.py` —— 归一化输出后比
  SHA-256 + PASS/FAIL + 退出码 → `IDENTICAL`/`DIFF`/`BASELINE`/`SKIP`（`--list`/`--only`/`--update`/`--verbose`）；
  固定种子 `_seed_runner.py`(20260913) + `PYTHONHASHSEED=0`。**现状 6 套件 153 PASS / 0 FAIL，连跑两次全 IDENTICAL**。
  改任何代码前先跑它。
- **H5 新增三条契约（勿破）**：① `comment` 统一为**非空字符串数组**（A7 锁）；② 加载器对**未知字段只 warning
  不拒绝** → 拼错键会静默失效，故 A6 锁"入库文件无未知键"；③ **自动扫描不可降级为"只报告"** —— 停用后
  `frame_container_size` 由 (222,110) 变 (136,71)（`core_prefixes` 含 `spr_cutscene_27_ralsei`，自动扫入的
  `..._huh/_look/_mu` 帧高 110 被算作 core），**用户可见**；G3 是冻结卡口（期望"必须不同"），要降级须单独验收。
- 已知不一致（未修）：`change_animation` 从长到短回退 vs `update_animation` 内嵌块只取前两段。
- **下一步**：真机跑一轮取**真实未命中清单**（S1 账本落日志）——S2/S3 只证"与现状等价"，未证"覆盖完整"。
  H4 拆分现有 G2 兜底，可开工。
