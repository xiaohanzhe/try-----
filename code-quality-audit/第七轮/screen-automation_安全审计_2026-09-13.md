# `screen-automation` 技能安全审计报告

- 日期：2026-09-13
- 对象：`屏幕自动化` / `screen-automation` **v1.1.29**（`skillId=skill_2097387188794126336`）
- 来源：WorkBuddy 推荐市场 → 安装到 `~/.workbuddy/skills/screen-automation/`
- 安装依据：用户明确指示"可以，那就装"

---

## 0. 结论

**安全，可直接用。未发现 P0 / P1 级风险。**

但有两条必须先说清楚的**事实约束**：

1. **技能目前是空壳。** 它只是"方法 + 安全约束"层，真正执行屏幕动作的是一个**独立的外部桌面程序**
   `ScreenAutomationHelper.exe`（厂商 `xiaozs.com`）。该程序**本机未安装**（实测见 §3），
   所以现阶段这个技能做不了任何事。
2. **本次审计的边界**：我审的是**技能包内的全部文件**。桌面端 exe 本体**不在可审计范围内**——
   是否信任该厂商的程序，需要用户独立判断。

---

## 1. 审计方法与一个流程偏差（如实记录）

常规流程要求：装第三方技能**前**先加载 `skills-security-check` 做审计。本环境**没有这个技能**
（调用 `Skill(skills-security-check)` 报 `Can not find skill`）。

因此改用替代路径，并明确其取舍：

> **先安装 → 装完立刻对落盘文件逐个人工审计 → 审计通过前绝不调用该技能。**

替代路径的边界：技能文件落在磁盘上本身不会执行任何东西，风险出现在**被调用**时；
所以"先装后审、审完再用"在这一情形下风险可控。但它**不能**替代对二进制本体的审计。

审计动作：逐文件通读 + 全包危险模式正则扫描（见 §2.2）。

---

## 2. 逐文件结论

### 2.1 文件清单与判定

| 文件 | 大小 | 判定 | 说明 |
|---|---|---|---|
| `SKILL.md` | 8.1 KB | 通过 | 方法说明 + 安全边界；见 §2.3 |
| `scripts/resolve_cli.ps1` | 1.1 KB | 通过 | 受限路径解析，见下 |
| `scripts/resolve_cli.sh` | 0.5 KB | 通过 | macOS 路径解析，同构 |
| `scripts/workflow_dev.ps1` | 15.6 KB | 通过 | `ValidateSet` 收紧的薄转发层 |
| `scripts/workflow_dev.sh` | 5.8 KB | 通过 | macOS 版，同构 |
| `references/agent-bridge.md` | 5.5 KB | 通过 | 纯文档；隐私/授权规则 |
| `references/workflow-standard.md` | 26.6 KB | 通过 | 纯文档；流程语言规范 |
| `agents/openai.yaml` | 0.3 KB | 通过 | 仅展示用元数据 |
| `_skillhub_meta.json` | 0.6 KB | 通过 | 市场来源与图标 CDN 地址 |
| `_icon.png` | 29.3 KB | — | 图片 |

### 2.2 危险模式扫描（全包）

正则：`curl|wget|Invoke-WebRequest|Invoke-RestMethod|Invoke-Expression|iex|base64|api[_-]?key|secret|token|http(s)://`
（大小写不敏感）

**命中项只有三类，全部无害**：

- 图标 CDN：`openplatform-cdn.codebuddy.cn/...`（推荐市场自身下发图标）
- 官网首页：`https://www.xiaozs.com/sah/`
- 官网下载页：`.../downloads/windows/latest`、`.../downloads/mac/latest`（**仅在文档里作为指引**，
  且同段明写"未经同意不下载、安装、重启或升级"）

**未命中**：无 `curl` / `wget` / `Invoke-WebRequest` / `Invoke-Expression` / `iex` / `base64` /
命令拼接 / 混淆 / 编码载荷 / 凭据读取。

### 2.3 `SKILL.md` 的安全姿态（正面证据）

它自己写下了相当强的约束，且与脚本实现一致：

- 不得猜测安装位置、**递归扫描用户目录**、或用其他输入工具绕过小助手；
- **未经同意不下载、安装、重启或升级**；
- 密码、验证码、密钥、支付信息**不得写入日志、流程或结果**，需要时让用户在界面内自行输入；
- 截图/屏幕内容**外发到外部模型前，必须说明 Provider、范围和用途并取得确认**，避开无关隐私；
- 不扩大用户授权、不后台接管未确认窗口；
- **用户说暂停/停止/取消时立即停止**；
- 能力码不得猜测、索取、记录、代输或绕过。

### 2.4 脚本实现与文档声明是否一致（关键核验）

`resolve_cli.ps1` 的候选顺序：

```
显式 -Executable  →  $env:SCREEN_AUTOMATION_HELPER_EXE  →  固定路径
%LOCALAPPDATA%\Programs\Xiaozs\ScreenAutomationHelper\  →  HKCU App Paths 注册项
→  HKCU Uninstall\{F174BA6D-570B-4F87-A453-84AA66C4A0CB}  →  Get-Command（PATH）
```

**不递归扫目录、不下载、不发网络请求**，全部落空时直接 `throw`。
—— 与 SKILL.md"不得递归扫描用户目录"的声明**一致**。这是本次审计里最关键的一致性核验。

`workflow_dev.ps1`：动作名用 `ValidateSet` 白名单（约 50 项）收紧，全部转发给
`ScreenAutomationHelper.exe cli ...`。**唯一的写盘操作**是 `prepare-update`：把某个已安装流程的
程序包目录复制到「文档\屏幕自动化小助手\流程开发\<id>-<时间戳>\」——目标路径明确、有界。

---

## 3. 实测：桌面端未安装（技能当前为空壳）

| 探测点 | 结果 |
|---|---|
| `%LOCALAPPDATA%\Programs\Xiaozs\ScreenAutomationHelper\ScreenAutomationHelper.exe` | **不存在** |
| `HKCU:\...\App Paths\ScreenAutomationHelper.exe` | **不存在** |
| `HKCU:\...\Uninstall\{F174BA6D-...}_is1` | **不存在** |
| PATH 中 `Get-Command ScreenAutomationHelper.exe` | **未找到** |
| 运行官方 `scripts/resolve_cli.ps1` | 抛「未找到屏幕自动化小助手」 |

**结论**：技能已就位，但**必须另装桌面端才可用**。安装包地址（技能给出的官方指引）：
`https://www.xiaozs.com/sah/downloads/windows/latest`。

由于 SKILL.md 明令"未经同意不下载、安装、重启或升级"，**此处停在用户决策**。

---

## 4. 使用前必须知道的另外两点

1. **部分能力是付费的**：「Agent 接入」「VLM 屏幕理解」「浏览器增强」属可选扩展，可能需要
   **能力码**（向开发者购买后在桌面端自行激活）。技能明令不得猜测/索取/记录/代输/绕过能力码。
   即：装好桌面端也**不等于**这些高级能力可用。
2. **VLM 路径会把屏幕内容发出去**：启用「VLM 屏幕理解」后，选定区域的截图会被发送到所配置的视觉模型。
   技能要求执行前必须说明 Provider 与范围并取得确认，但这仍属把屏幕内容送出本机的场景——
   涉及敏感内容时要留意。

---

## 5. 装上之后能解决什么（预期收益）

本项目的六轮行为修复里，"甩飞（fling）"「拖拽 1:1 跟手」「抛物线落地相位」这类缺陷，
目前**只能靠离屏模拟脚本**验证，无法在真实运行的桌宠上做鼠标拖拽。

该技能提供的正是这条链路：
`window list-visible` 确认目标窗口 → `task begin/observe` → `task drag --start --end --duration`
/ `task click` / `task write` / `task hotkey` → 重新 `task observe` 验证画面变化。

也就是说：装上桌面端后，**"真机拖拽 + 操作后复看"这条验证路径才能打通**。

---

## 6. 待用户决策

1. 是否安装桌面端 `屏幕自动化小助手`（来自 `xiaozs.com`，非本仓库、非市场内分发）？
   —— 我不代为下载安装。
2. 若需要「Agent 接入 / VLM 屏幕理解」等高级能力，是否愿意购买并自行激活能力码？

在两题有答案之前，该技能保持"已安装、不使用"状态。

---

## 7. 附记（20:5x）：下载与验签记录 —— **停在执行前的最后一步**

用户指示"装，但尽量别用付费能力"。桌面端安装包已下载并验签完毕，**尚未执行安装**。

### 7.1 真实下载路径（技能给的地址不是直链）

- `.../sah/downloads/windows/latest` → **301** → `.../latest/`，返回 **HTML 落地页**（不是二进制）。
- 落地页提供两个入口：
  - `?arch=x64&format=exe` —— **直链**，`Content-Disposition: ...ScreenAutomationHelper-Windows-x64-latest.exe`
  - `.../sah/downloads/zip/latest` —— **301 跳百度网盘**（`pan.baidu.com/s/...`），需登录/提取码，**脚本化不可行**

实际采用：`https://www.xiaozs.com/sah/downloads/windows/latest/?arch=x64&format=exe`

### 7.2 已核验的事实

| 项 | 值 |
|---|---|
| 文件大小 | **76,364,367 字节**（与 HEAD 的 `Content-Length` 一致 → 下载完整） |
| SHA-256 | `D7CD1686826FB3ED635788BF2D01418DEAA9B7CA763A7D0A5470B9A9D0407F1A` |
| 厂商（`VersionInfo.CompanyName`） | 小助手网络 |
| 产品名 / 版本 | 屏幕自动化小助手 / **0.17.13** |
| **数字签名** | **`NotSigned`** —— 无 Authenticode 签名，**无签名证书** |
| 安装器类型 | **Inno Setup**（全文件扫描命中 `Inno Setup` + `rDlPtS` 标记） |
| 安装范围 | **按用户**：卸载键位于 `HKCU\...\Uninstall\{F174BA6D-...}_is1`，目标 `%LOCALAPPDATA%\Programs\Xiaozs\...` → **不需要管理员权限** |

### 7.3 为什么停在这里

**未签名**意味着：没有发布者身份绑定、没有篡改检测，Windows SmartScreen 会拦一次。
而这个程序的能力恰恰是**读取屏幕 + 注入鼠标键盘**——权限最高的一类软件。
76 MB 二进制**不在我能审计的范围内**，我无法排除它包含任何行为。

所以需要用户对"**安装一个无签名的读屏/控屏程序**"这件事**本身**明确点头，
而不只是对"装桌面端"这个笼统的想法点头。这是执行前的最后一道闸门。

### 7.4 装法（已勘明，待执行）

- 默认安装即落到技能查找的路径（`%LOCALAPPDATA%\Programs\Xiaozs\ScreenAutomationHelper\`），**无需提权**。
- 可静默安装：`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`（Inno Setup 标准开关）。
- 卸载：自带卸载器（HKCU 卸载键 `{F174BA6D-570B-4F87-A453-84AA66C4A0CB}_is1`）。
- **免费路线已确认**：基础屏幕能力（`window list-visible` / `task begin|observe|find|wait|click|drag|scroll|write|hotkey`）
  属**本地能力，无需能力码**；只有「Agent 接入」「VLM 屏幕理解」「浏览器增强」才需要付费激活 ——
  按用户要求，本次**一概不碰**。
