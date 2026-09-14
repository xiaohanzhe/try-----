# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌面宠物）

## 铁律
- **每轮改动完成即 commit + push**（用户原话"以免后期找不到"），不攒批。
- 称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- 报告放项目根（`代码质量复审报告_*.md` / `H5-*.md`），证据 `code-quality-audit/<轮次>/`，
  侦察日志 `<轮次>/_recon/`（gitignore），要留痕的进 `_evidence/`。
- 改代码前先跑 `code-quality-audit/regress/run_all.py`（PYTHONHASHSEED=0）。

## 项目结构
- `ralsei_pet/src/main.py`（~8600 行，单巨型 `RalseiPet(QMainWindow)`）+ `ralsei_pet/modules/*.py`(23)。
- 远端 `https://github.com/xiaohanzhe/try-----.git`（私有，未认证返 401/404）；分支 main→origin/main。
- GitHub 连接器已接（身份 xiaohanzhe/236837805）但**授权只覆盖公开库**，看不到本仓库（404）。

## 本机环境铁律
1. **Bash 工具不可用**（shim 下 `ls`/`cd`/`dirname` 全 command not found）。一律用 **PowerShell 工具**；
   目录/文件列表用 Glob/Read，别用 shell。
2. PowerShell **stdout 常不回传** → 命令内 `Out-File -Encoding utf8 <文件>` 落盘再 Read。
3. **起进程被拦**：`cmd /c`、`Start-Process`、`New-Object Diagnostics.Process`、WMI 均不可用
   （Start-Process 不报错但进程没起）。只能用 call 操作符 `&` + 工具 `run_in_background:true`。
4. **杀进程**：`Stop-Process`/`taskkill` 静默失效 → 用 Python + psutil 按 cmdline 匹配杀。
5. **删文件**：管道 `Remove-Item` 静默无效 → `[System.IO.File]::Delete($p)` + `Test-Path` 校验。
6. `Out-File` 父目录不存在会 exit 1 且无输出 → 先 `New-Item -ItemType Directory -Force`。
7. Python：`C:\Python311\python.exe`（PyQt5/pywin32/psutil）；venv
   `C:\Users\23002\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（pyflakes）。
8. 本机有沙箱代理 `127.0.0.1:54231`（对 github 常 502）；Clash 在 `127.0.0.1:7897`（可用）。

## git push（退出码 128 且全静默 = 非交互 GCM 取不到凭据）
```powershell
$cred = "url=https://github.com/xiaohanzhe/try-----.git`n`n" | git credential fill 2>$null
$pw  = ($cred | ? { $_ -like 'password=*' }) -replace '^password=',''
$usr = ($cred | ? { $_ -like 'username=*' }) -replace '^username=',''
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$usr`:$pw"))
git -c credential.helper= -c http.proxy=http://127.0.0.1:7897 `
    -c http.extraheader="Authorization: Basic $b64" push origin main   # 重试 3–5 次
```
- 令牌**别写进仓库文件**。核对外发用 `git ls-remote origin refs/heads/main` 加同样头，比看退出码硬。
- **提交信息用 Write 写 UTF-8 文件 + `git commit -F <文件>`**：`-m @'...'@` 遇"带空格的英文引号串"
  会被 PS 5.1 拆 argv → 提交没发生、push 退 0 假成功。提交后必核 `git log --oneline -1`。

## 真机起停宠物
- `Set-Location ralsei_pet; & C:\Python311\python.exe src\main.py` + `run_in_background:true`。
- 单实例锁 `Global\RalseiPetMutex`；没干净退出会残留互斥量 → 用 psutil 杀（`_recon/kill_pet_py.py`）。
- 窗口是**透明非置顶** FramelessWindow → 会被遮挡、模拟拖拽命中透明区（穿透）→
  **甩飞/抛物线做不了真机验证，只能离屏断言**。

## 仓库卫生
- `compileall` 会改写被跟踪的 `src/__pycache__/main.cpython-311.pyc` → 跑完 `git checkout --` 还原。
- `.gitignore` 覆盖 `*.log`/`*.bak`/`__pycache__/`/`*_recon/`，但 `*.log.<日期>` 不匹配（未跟踪残留）。

## 历轮结论
- **误报清单（勿据此改）**：`learn_new_skill` 有 `if new_skills:` 守卫；`_on_ai_reply` 跨线程已由
  `pyqtSignal` 排主线程；`reset_special_states` 零调用故漏复位无影响；原子写/回收站删除已正确防御。
- **第六轮约定（勿回退）**：多屏**禁用** `QApplication.desktop().availableGeometry()`（只返主屏→历史"瞬移"
  根因），用 `_virtual_screen_rect()`/`_current_screen_rect()`/`_clamp_pos_to_desktop()`/`_desktop_floor_y()`；
  物理量必须钳 `dt≤0.1s`；甩飞判定只能在 `mouseReleaseEvent`（`_drag_samples` 0.12s 窗口，
  `_FLING_SPEED=900`/`_BOUNCE_SPEED=250`）；落地相位用 `_fall_phase_start`+`_fall_flight_time` 相对计时；
  动画 `fps=6`；自主说话唯一入口 `start_autonomous_speech()`，**AI 关闭必须沉默**（内置台词已全删）；
  不劫持鼠标、拖拽 1:1、起身类 `play_animation_once(...,restore_to="idle")` 只播一次。
- **第七轮**：R7-1 按 README 路径启动 `ModuleNotFoundError: logger_utils` → 已修
  （`desktop_interaction.py` 加 try/except + `main.py` 把 `<root>/modules` 加进 sys.path）。
  教训：**凡"测试里预置了环境"的地方都要留一条"按真实路径跑"的对照**。

## H4/H5 架构改造（用户排期"单独做"）
- 工具/基线 `code-quality-audit/架构改造-H4H5/`（只读）。**量化基线（勿重测）**：`main.py` 8794 行 /
  `RalseiPet` 186 方法；`self` 属性 438 个、106 个被 ≥3 处写；`animation_mapping` 109 组/1106 PNG/
  743 未引用/缺失 0；动画名字面量 24 + 12 处 f-string；运行时 `sprites`=489（1084 帧对象）。
- **两个坑**：① 不能拿 `scan_and_group_assets` 全量替代硬编码（mapping 承载别名+故意缺省+前缀回退，
  全量入组会重现灰块占位帧）；② 不能停用自动扫描（会让 `frame_container_size` (222,110)→(136,71)，用户可见）。
- **H5 三条契约**：`comment` 必为非空字符串数组；加载器对未知字段只 warning → 须锁"入库无未知键"；自动扫描不可降级。
- **H5 进度 S1/S2/S3 全完成**（S1 `animation_misses` 账本 17/17；S2 `b099e4c` 配置外化
  `ralsei_pet/assets/animations.json` schema=1/109 组/377 帧，单向 AST 导出、JSON 优先异常回落，等价性已证；
  S3 `94e4902` 4 组别名改 `alias_of`+28 组 `legacy:true`）。
- 已知未修：`change_animation` 从长到短回退 vs `update_animation` 内嵌块只取前两段。
- 下一步：真机跑一轮取真实未命中清单（S2/S3 只证等价、未证覆盖完整）。

## 第八轮（行为缺陷，进行中）
- 已完成并推送：**#10 对话框 ▼ 抖动 + 滚动**（`024b6aa`，`verify_round8_dialogue.py` 20/20）、
  **#11 坠落/摔倒误判**（`cc9471d`，`verify_round8_floor.py` 16/16，按"建楼要求"文档）。
- 待办：#12 斜抛轨迹 + 卡动画 + 空中二次抓取（代码已改，验证中）；#13 特殊动画 AI 独占/播完不打断/
  不边播边走/待机需静止≥3min；#14 G2 断言更新+全绿；#15 对话全 AI 接管 + 原作风格聊天框原型
  （**不直接改 `dialogue_ui.py`**）+ 多人对话预留 + 完整"建楼"楼层系统 + bilibili 窗口摆放。
