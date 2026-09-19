# 证据：Ollama 自动更新中途中断，导致本机无法推理（2026-09-19）

**结论：不是本项目改坏的，也不是我改坏的。是 Ollama 自己的自动更新器把服务杀掉了、
然后没装完。当前本机 Ollama 能启动、能列模型，但一推理就 500。**

## 时间线（全部来自本机日志/文件时间戳，非推测）

| 时刻 | 事件 | 出处 |
|---|---|---|
| 11:10:08 | `ollama list` 正常，daemon 版本 **0.34.0**；日志里 updater 已在跑 | `ollama list` 输出 |
| 11:10:12 | updater 发现新版本 **0.34.2**，安装包已下载 | `ollama` stdout |
| 11:11:26 | Inno Setup 开始安装，日志记录 `Created temporary directory: ...\Temp\is-R5YSV2I3X7.tmp` | `%LOCALAPPDATA%\Ollama\upgrade.log` |
| 11:11:27 | `Shutting down applications using our files. (forced)` —— **日志到此为止，没有安装成功/失败的收尾行** | 同上（文件 LastWriteTime = 11:11:27） |
| 11:11:27 | `lib\ollama\` 目录 mtime 变成 11:11:27（**内容被删**） | 目录时间戳 |
| 11:20:11 | 我手动 `ollama serve`，服务起得来（`Listening on 127.0.0.1:11434 (version 0.34.0)`） | serve 日志 |
| 11:20:31 | 第一次推理即失败 | 见下 |

## 直接证据（serve 自己的报错）

```
level=INFO source=sched.go:591 msg="failed to create server" model=ralsei:v3
error="error starting llama-server: llama-server binary not found (checked:
  ...\Programs\Ollama\lib\ollama\llama-server.exe,
  ...\Programs\lib\ollama\llama-server.exe,
  ...\Programs\Ollama\build\lib\ollama\llama-server.exe,
  ...\Ollama\dist\windows-amd64\lib\ollama\llama-server.exe,
  ...). Run 'cmake -S llama/server --preset cpu && cmake --build --preset cpu' first"
```

## 现状盘点

- `%LOCALAPPDATA%\Programs\Ollama\` 里 `ollama.exe` / `ollama app.exe` 还是 **09-09 的旧版**（升级没替换成功）。
- `lib\ollama\` 里只剩 `rocm_v7_1\`、`vulkan\`、两个 license 文件 ——
  **所有推理器二进制（llama-server.exe 等）都不在了**。
- `/api/tags` 正常（6 个模型都在，blob 都没丢）：`ralsei:v3` · `qwen3:4b-instruct-2507-q4_K_M` ·
  `qwen2.5:7b-instruct` · `ralsei:v2` · `ralsei:latest` · `qwen2.5:3b`。
- `/api/chat` 一律 **HTTP 500**（**模型权重没坏，坏的是推理器可执行文件**）。
- 安装包还在，且是 Ollama 自己下载并已校验过的：
  `%LOCALAPPDATA%\Ollama\OllamaSetup.exe`（1,569,993,232 字节，mtime 09-18 10:58）。
- Inno 的临时解包目录 `Temp\is-R5YSV2I3X7.tmp` 只剩 `_isetup`（压缩包体），
  **里面没有解压好的 llama-server.exe** → 无法"只把文件拷回来"地修复。

## 影响面

1. **桌宠现在是哑的**：对话与事件台词都走 Ollama；按新的设计（`pool=None`），
   AI 不可用时**沉默**而不是回落内置台词 —— 所以表现是"它不说话"，不会报错。
2. 口吻 A/B 探针（`probe_ralsei_voice.py`）**跑不成**：产物里 68 条全是
   `HTTP Error 500`（该文件已保留为"本次受阻"的留痕，含下面的汇总行 0/0）。
3. `ollama rm`（删旧模型）也用不了 —— 它同样要 daemon 能干活。

## 修复路径（需要用户决定，因为是"装应用"而不是改代码）

- **A. 用户自己重启 / 完成 Ollama 更新**（最省事）：重新打开 Ollama 桌面端，
  它通常会接着把 0.34.2 装完并恢复 `lib\ollama\` 下的推理器。
- **B. 授权我跑那个已经下载好的安装包**：`%LOCALAPPDATA%\Ollama\OllamaSetup.exe`
  （用户级安装、无需管理员，日志显示 `Administrative install mode: No`）。
- **C. 什么都不做**：桌宠保持安静，代码侧工作照常（G2 不需要 Ollama）。
