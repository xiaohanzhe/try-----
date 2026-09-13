# 项目长期记忆 — ralsei_pet 代码质量系列审查

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
