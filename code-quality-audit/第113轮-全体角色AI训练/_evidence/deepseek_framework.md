# DeepSeek 新开源的框架：下了、读了、结论是"用不上"

- 日期：2026-10-24
- 用户原话：「deepseek 最近开源了他们的框架，要是这对你训练 AI 有帮助那就下载下来参考吧」
- 参考副本：`E:\Download\_ref_deepinfer2`（`--depth 1`，348 个文件；**只读参考，不入仓库**）

## 1. 到底是哪个框架

| 仓库 | 是什么 | 发布时间 | 对本项目有用吗 |
|---|---|---|---|
| **DeepInfer**（`deepseek-ai/DeepInfer`） | DeepSeek 线上**推理**框架（不是训练框架） | 2026-10-20 | ❌ 用不上（见 §2） |
| **deepseek-harness** | Agent 工具框架（TypeScript，插件化，"Everything is a Plugin"） | 2026-08 起，10-23 仍在更新 | ❌ 不是训练/推理框架 |
| **DeepSpec** + DSpark | 推测解码**草稿模型**训练工具链（MIT） | 2026-06-27 | ❌ 需要 8 卡；裸机 CPU 无从谈起 |
| TileLang / DeepGEMM / FlashMLA / DeepEP | 算子与通信库 | 2026-09-30 | ❌ 无 GPU |

按时间点（"最近"）与"框架"两个字，用户指的应是 **DeepInfer**。

## 2. 为什么用不上（三条硬门槛，任何一条都过不去）

1. **硬件**：README 明确 `NVIDIA SM100 GPUs` 或 `Huawei Ascend 950 NPUs`；
   本机 `nvidia-smi` 不存在，18 核 CPU / 33.9 GB 内存，**没有 GPU**。
2. **平台**：要求 **Linux** + GCC ≥ 13 + Python 3.12 + CUDA 13 / CANN 9.2；
   我们是 Windows + Python 3.11。
3. **模型**：只支持 **DeepSeek-V4.1-Flash**（MoE 大模型）；我们跑的是
   `ralsei:v4` = qwen2.5-7b q4_K_M（Ollama/GGUF）。

⇒ 硬塞进来不会有任何收益。**这一条我不打算包装成"有参考价值"。**

## 3. 但它有三处思路，和本项目已经踩过的坑对得上

| DeepInfer 的做法 | 我们这边的现状 | 结论 |
|---|---|---|
| 前缀缓存 / KV 复用（同前缀只算一次） | 已用：`keep_alive=30m` + 稳定 system。实测同一角色第 1 轮 **50.2s**（prefill 40.8s / 2000 tok）→ 第 2 轮 **0.74s** | ✅ 已在用，属"同一件事" |
| 确定性采样（`DEEPINFER_BATCH_INVARIANT` + 固定 `seq_seed`） | 本轮训练的每次重采样都用 `stable_seed(id, phase, turn, attempt)`，同输入可复现 | ✅ 已在本轮落地 |
| 结构化输出（regex / JSON Schema / EBNF 约束解码） | **没接**。`build_follow_prompt` 现在是"求模型只回一个词"，靠 `parse_follow_choice` 白名单兜底 | ⚠️ 可做但未做（登记，不在本轮动） |

第三条如果要做，走 Ollama 的 `format` 字段给 `follow/stay/rally/leave` 上 JSON Schema，
能把"模型回了半句解释 ⇒ 解析失败 ⇒ 退默认不跟"这条概率压到 0。
但它是**运行时行为改动**，和本轮"只做离线训练"的范围不重叠，所以只登记。

## 4. 一句话

DeepSeek 这次开源的是**推理加速**，不是训练；本机没有它需要的硬件。
本轮"训练"落在 **L1 层（prompt + 语料 + 评测闭环）**，权重没动 —— 这是没有 GPU 时的诚实做法，
不是"用 DeepSeek 框架训出来的"。
