# 第96轮b · 机器侧证据汇总

## 1. 全量 G2 终验（零 DIFF）

命令：`C:\Python311\python.exe code-quality-audit\regress\run_all.py`
（经 `_tools/run_g2.py` 用 subprocess 捕获，绕开本会话 shell 管道的偶发 SIGTERM）

```
RC = 0
非 IDENTICAL 套件行：（无）
合计：PASS=4638 FAIL=0  套件=88
【问题】段：无
```

相对第95轮终验（4621 / 87）：**判据 +17**（全部来自新增 `check96b`），**套件 +1**。

### 过程中出现过的 1 次预期 DIFF（已归因并重建）

`check81` 的 `G5` 判据打印：

```
-[PASS] G5 ... suite=87 baseline=87 缺=无
+[PASS] G5 ... suite=88 baseline=88 缺=无
```

⇒ 这是**新套件正确接入**的必然表现（判据本身仍 `[PASS]`），非缺陷。
处置：`run_all.py --only check81 --update`（合并模式，其余套件基线不动）。

## 2. `check96b` 单独结果（17/17）

```
合计 17 条判据  PASS=17  FAIL=0
```

（完整输出见同目录 `check96b.txt`）

## 3. 破坏性验证（`mutate96b.py`）

```
[基线] rc=0 PASS=17 FAIL=0
[M1 换回 ==]              rc=1 FAIL=4  判据=['C1','C2','C4','D3b']  ✅
[M2 开关外加回直写对话]    rc=1 FAIL=2  判据=['B1','B2']             ✅
[M3 开关改 True]          rc=1 FAIL=1  判据=['B0b']                ✅
[M4 开关短路]             rc=0 FAIL=0  （如实不报红，按设计不覆盖该形态）✅
```

## 4. 候选3 真机探针（`probe96b_canned.py`）

### 修前

```
  calls_delta = 2        ← react_to_desktop_element 触发了 2 次 add_dialogue/show_dialogue
  speak_delta = 0        ← 完全没经过 speak_event（绕过唯一入口）
  speak_none_ret = ''    ；speak_none_calls = 0     ← 负控制：pool=None 沉默 ✅
  speak_pool_ret = '这是一句内置台词。'；speak_pool_calls = 2  ← 正控制：会说 ✅

  add_dialogue 总调用 10 次，其中：
    ('ralsei', '这是文本文件呢！ 纸做的东西要小心处理哦！', 'normal')   ← 用户可见的罐头台词
```

### 修后

```
  calls_delta = 0        ← 不再绕过入口 ✅
  speak_delta = 0
  speak_none_calls = 0   ← 负控制仍沉默 ✅
  speak_pool_calls = 2   ← 正控制仍会说 ✅

  add_dialogue 总调用 8 次 ——「这是文本文件呢！…」已消失
```

## 5. 核心文件复检（`recheck96b_final.py`）

```
合计  PASS=43  FAIL=0
```

六类：① 可编译（7 个 .py 走 `ast.parse`，不产 `.pyc`）② 结构锚点（main.py 4 条 · run_all.py 2 条 · REPORT.md 6 章节）
③ 编码（10 文件无 BOM / 无 U+FFFD；`main.py` EOL 仍纯 CRLF 15092）④ 恒真判据（3 个脚本各 0 命中）
⑤ 逐令牌回验（5 文件共 25 令牌）⑥ 工作区（暂存区空 · 删除 0 · 改动 4）

### 复检自身抓到并修掉的 2 条**假红**（"判据也是被测物"第 N 例）

1. ④ 的正则假定 `desc` 与 `id` 同行格式 ⇒ `NoneType.group` 崩 ⇒ 改为按起点切片。
2. ⑤ "不再存在 `add_dialogue("ralsei", reaction[`" **没剥注释** ⇒ 命中的是我自己
   9455 行那段描述旧写法的注释 ⇒ 假红。修 = 先剥行注释再查
   （与 `check96b` C4、95 轮 D1 **同一个坑的第三次发作**）。

## 6. 环境异常记录

- 本会话 shell 对 `run_all.py` 输出**管道/重定向**偶发 `SIGTERM` 零输出（连续 3 次）；
  改用 Python `subprocess` 捕获后稳定 ⇒ 已固化为 `_tools/run_g2.py`。
- `E:\Download\_tmp\` 写入**间歇性**报 `Invalid request code`（E 盘瞬时故障，记忆已有记录）
  ⇒ 临时输出改落 `%TEMP%`。
- 短录制探测触发 `rec96.py` 的 `REC96_PURGE`：把第96轮的 `frames/` **整目录改名归档**
  （177 张 → `frames_prev_20261007_192846/`）。**这是脚本的设计行为**（删除守卫阈值 50，
  超限即改名归档而不是逐文件删）。已**原样还原**：`frames` 恢复 177 张，
  我那 2 张探测帧移入本轮 `_evidence/probe96b_frames/`；被覆盖的 5 个 `rec96_*.txt/csv`
  已 `git checkout` 还原。
