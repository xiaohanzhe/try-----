# 真机确认记录 —— 括号动作闸（2026-09-19 16:17~16:18）

## 做法

```
Set-Location ralsei_pet
& C:\Python311\python.exe src\main.py        # 后台起（本沙箱只有 & + run_in_background 这一条路）
```

结束：Python + psutil 按 cmdline 匹配 `python * src\main.py`（`Stop-Process`/`taskkill` 在本沙箱静默失效）。

## 结果

| 项 | 观察 |
|---|---|
| 启动 | 16:17:48 `已启用 jieba 分词`；16:17:48 `animations.json 加载 112 组动画` |
| 运行 | 16:18:01 `[anim-miss] 动画名不存在: 'walk_down_sleep' → 回退 'walk_down'`（已知的正常回退） |
| **本次改动的异常** | **无**。stderr 里没有任何来自 `event_speech` / `_clean_ai_reply` 的 Traceback |
| 进程收尾 | `python src\main.py` (pid=42712) 已结束，复核残留 = 0 |

## 顺带发现（**与本次改动无关**，未修）

`E:\RalseiMemory\logs\ralsei_pet.log` 滚动失败：

```
--- Logging error ---
OSError: [WinError 1] 函数不正确。:
  'E:\RalseiMemory\logs\ralsei_pet.log' -> 'E:\RalseiMemory\logs\ralsei_pet.log.2026-09-18'
File "C:\Python311\Lib\logging\handlers.py", line 115, in rotate
    os.rename(source, dest)
```

- 起因：`RotatingFileHandler.doRollover()` 在 **exFAT 的 E 盘**上 `os.rename` 到已存在的目标名会失败
  （目标 `ralsei_pet.log.2026-09-18` 已存在 → WinError 1）。
- 影响：日志**无法滚动**，每次触发滚动都会往 stderr 打一段 Traceback；日志文件会一直变大。
- 归属：**日志基础设施**的缺陷，与括号动作闸无因果关系（改动只动了 `_clean_ai_reply` / `guard_reaction` 的文本处理）。
- 处置：**本轮不修**（会动到全局日志行为，属于独立一件事），记在此处待排期。

## 为什么"真机"只到这一步

本次改动是**纯文本函数**（`strip_action_parentheticals`）加两处接线。它能出问题的两种方式各有对应证据：

1. **规则本身错**（误杀正常台词）→ 用 **574 条真实中文模型输出 + 853 条原作台词 + 7 条中文负控制**
   量化，误伤 0；见 `paren_gate_2026-09-19.txt`。
2. **接线没接上 / 接错**（改了没人调用）→ 由离线断言守：
   `main.py:336` 导入、`main.py:7891`（`_clean_ai_reply` 0a 步）、`event_speech.py:354`（`guard_reaction`）三处调用，
   且 `persona_chat` C18/C18b/C18c/C19、`s7_event_speech` A22/A22b/A22c/A22d 是**行为级**断言（喂字符串看返回值）。

GUI 起来之后人**无法与宠物对话**（透明非置顶 FramelessWindow，需要主人手动打字 + 等 Ollama 推理），
所以"起来跑一遍"能提供的新信息就只有"进程不崩"这一条 —— 已经拿到。
真正的对话链路效果要在主人真人对话时观察（**本轮的"闪现"代价只会在真人对答时看到**）。
