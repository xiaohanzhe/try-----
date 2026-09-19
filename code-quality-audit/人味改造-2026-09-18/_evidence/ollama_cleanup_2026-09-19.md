# 旧 Ollama 模型清理（2026-09-19）

用户口径：「其他的可以删一删了」。清理动作**执行前**已说明影响面。

## 为什么现在能删

Ollama 在 09-19 11:10 自动更新失败（写坏了推理二进制）后已修好：
`OllamaSetup.exe /VERYSILENT` 重装 → daemon 0.34.2、`llama-server.exe` 回来、
`/api/chat` 实测出话。删模型必须在"确认线上还能推理"之后做，否则分不清
"删模型删坏了"和"本来就坏着"。

## 模型存放位置（先查清楚，别拿 C 盘空闲当证据）

`%LOCALAPPDATA%\Ollama\models\blobs` **不存在** → 默认路径没用。实测：

- `OLLAMA_MODELS` 环境变量 = `None`
- `ollama list` 可用，输出按 UTF-8 解：
  ```
  NAME                             ID              SIZE      MODIFIED
  ralsei:v3                        eb03d55cc270    2.5 GB    5 hours ago
  qwen3:4b-instruct-2507-q4_K_M    0edcdef34593    2.5 GB    5 hours ago
  ```

## blobs 目录探测

- `D:\ollama\models\blobs` 不存在
- `E:\ollama\models\blobs` 不存在
- `C:\Users\23002\.ollama\models\blobs` **存在**：7 个 blob，合计 2.33 GB

> 关键：`ralsei:v3` 是 `FROM qwen3:4b-instruct-2507-q4_K_M` 建的、没有新增权重层，
> 所以**两者共用同一个 2.33 GB 的 blob**。清理后 blobs 目录 = 2.33 GB 正好等于
> 一个底座 —— 这就是共用的证据。

## 删除结果

| 模型 | `ollama list` 标称 | 处置 |
|---|---|---|
| `ralsei:v2`（3B，旧线上） | 1.9 GB | 删除 |
| `ralsei:latest`（3B，最旧） | 1.9 GB | 删除 |
| `qwen2.5:3b`（ralsei:latest 的底座） | 1.9 GB | 删除 |
| `qwen2.5:7b-instruct`（第七轮 7B 评估参照） | 4.7 GB | 删除 |
| `ralsei:v3`（4B，**现线上**） | 2.5 GB | **保留** |
| `qwen3:4b-instruct-2507-q4_K_M`（v3 底座） | 2.5 GB | **保留** |

四个 `ollama rm` 全部 `exit=0`、输出 `deleted '...'`。删除后 `ollama list` 只剩两个。

**实际释放约 6.6 GB，不是标称的 10.4 GB。** 标称相减（1.9×3 + 4.7）会多算：
`ralsei:v2` / `ralsei:latest` 与底座 `qwen2.5:3b` **共用同一个 blob**，删三个只掉一份。
按 blobs 目录反推：清理后 2.33 GB，清理前 ≈ 2.33 + 1.9 + 4.7 ≈ 8.9 GB。
（**教训：删模型看 `ollama list` 的 SIZE 相加会高估释放量，要看 blobs 目录。**）

## 保留项可用性核验（不只看 /api/tags）

`POST /api/chat`（model=ralsei:v3）→ 「在呢，有什么我可以帮你的吗？😊」

> ⚠ 这句话听着偏"助手腔"（"有什么我可以帮你的吗"）是**正常现象**，不是回归：
> 裸调 `/api/chat` 没带 system，用的是 Modelfile 里的 SYSTEM =
> `You are Qwen ... a helpful assistant`。App 每次对话都会用 persona 覆盖它。
> 这条同时验证了"**persona 是唯一的角色来源**"这个机制还在。

## 不可逆性

- `ralsei:v2` / `ralsei:latest` 可由 `ralsei_pet/assets/ralsei.modelfile` 重建，
  但底座 `qwen2.5:3b` 已删，重建需重新拉取 1.9 GB。
- `qwen2.5:7b-instruct` 需重新拉取 4.7 GB。
- 仓库内对这几个名字的引用全部是**历史报告/证据**（记录性质），不参与运行；
  线上代码与配置只认 `ralsei:v3`（`ralsei_pet/config.json`、`ralsei.modelfile` 已核）。
