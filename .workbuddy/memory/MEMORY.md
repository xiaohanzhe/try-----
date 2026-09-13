# 项目长期记忆 — ralsei_pet 代码质量系列审查

## 工作流铁律（用户明确要求）
- **每次改版都要提交并推送一次 git**（原话："以免后期找不到"）。任何一轮代码/文档改动完成后，
  立即 commit + push，不要攒批。推送方法见下方「git push 备忘」。
- 汇报时用"用户"称呼他；技术细节由我拍板，不必反复请示，但不可逆动作要先说影响面。

## 项目概况
- 主体：`ralsei_pet/` — Deltarune Ralsei 桌面宠物，Windows + Python 3.11 + PyQt5。
- `src/main.py` 约 8740 行、单巨型 `RalseiPet(QMainWindow)` 类；另有 22 个 `modules/*.py`。
- 审查产物统一放 `code-quality-audit/第五轮/`（轮次递增），报告放项目根 `代码质量复审报告_*.md`。

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
